import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)

from app.utils.config import settings


class DatabaseManager:
    """
    Async database manager with failover support.
    Handles automatic failover between main and standby databases.
    """
    
    def __init__(self):
        self.db_uris = [
            settings.make_async_uri(settings.DB_HOST),
            settings.make_async_uri(settings.DB_HOST_STANDBY),
        ]
        self.sync_uris = [
            settings.make_sync_uri(settings.DB_HOST),
            settings.make_sync_uri(settings.DB_HOST_STANDBY),
        ]
        self.current_db_index: int = 0
        self.engine: Optional[AsyncEngine] = None
        self.async_session_maker: Optional[async_sessionmaker[AsyncSession]] = None
        self._lock = asyncio.Lock()
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = True
        
    @property
    def current_db(self) -> str:
        return self.db_uris[self.current_db_index]
    
    def _create_engine(self, uri: str) -> AsyncEngine:
        """Create an async engine with connection pooling"""
        return create_async_engine(
            uri,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=5,
            max_overflow=10,
            pool_timeout=5,
            echo=False,
        )
    
    async def check_db_available(self, uri: str, timeout: float = 2.0, silent: bool = False) -> bool:
        """Check if a database is available"""
        engine = None
        try:
            # Use NullPool for quick health checks to avoid connection pooling issues
            engine = create_async_engine(
                uri,
                poolclass=NullPool,
            )
            
            # Use asyncio.wait_for to enforce timeout
            async def do_check():
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            
            await asyncio.wait_for(do_check(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            if not silent:
                print(f"❌ DB check timed out for {uri}")
            return False
        except Exception as e:
            if not silent:
                print(f"❌ DB check failed for {uri}: {e}")
            return False
        finally:
            if engine:
                try:
                    await engine.dispose()
                except Exception:
                    pass
    
    async def wait_for_any_db(self, max_retries: int = 30, retry_delay: float = 2.0) -> Optional[int]:
        """Wait for either main or standby DB to become available"""
        print("⏳ Waiting for database to become available...")
        
        for attempt in range(max_retries):
            # Check main DB
            if await self.check_db_available(self.db_uris[0]):
                print(f"✅ Main DB available (attempt {attempt + 1})")
                return 0
            
            # Check standby DB
            if await self.check_db_available(self.db_uris[1]):
                print(f"✅ Standby DB available (attempt {attempt + 1})")
                return 1
            
            print(f"⏳ No DB available yet (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)
        
        return None
    
    async def initialize(self) -> None:
        """Initialize database connection and start monitoring"""
        # Wait for any available DB
        db_index = await self.wait_for_any_db(max_retries=30, retry_delay=2)
        
        if db_index is None:
            raise RuntimeError("⛔ Neither MAIN nor STANDBY DB available after 60 seconds!")
        
        self.current_db_index = db_index
        self.engine = self._create_engine(self.current_db)
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        
        print(f"🎯 Initial DB set to: {self.current_db}")
        if db_index == 0:
            print("✅ Connected to MAIN DB")
        else:
            print("✅ Connected to STANDBY DB")
        
        # Create tables
        await self.create_tables_with_retries()
        
        # Start monitoring
        print("🚀 Starting DB monitor task...")
        self._monitor_task = asyncio.create_task(self.monitor_db())
    
    async def create_tables_with_retries(self, retries: int = 5) -> None:
        """Create database tables with retry logic"""
        from app.models.base import Base
        from app.models.user import User
        from app.models.message import Message
        
        while retries > 0:
            try:
                async with self.engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                print("✅ Tables created successfully.")
                return
            except Exception as e:
                retries -= 1
                if retries == 0:
                    raise RuntimeError(f"❌ Failed to create tables: {e}")
                print(f"⏳ Failed to create tables, retrying... ({e})")
                await asyncio.sleep(2)
    
    async def switch_db(self, new_index: int) -> bool:
        """Safely switch to a different database"""
        async with self._lock:
            if self.current_db_index == new_index:
                print(f"ℹ️ Already using DB {new_index}, no switch needed")
                return True
            
            new_uri = self.db_uris[new_index]
            print(f"🔄🔄🔄 SWITCHING from {self.current_db} to {new_uri}...")
            
            try:
                # Create new engine
                print("🔄 Step 1: Creating new engine...")
                new_engine = self._create_engine(new_uri)
                
                # Test connection
                print("🔄 Step 2: Testing new connection...")
                async with new_engine.connect() as conn:
                    result = await conn.execute(text("SELECT 1"))
                    print(f"🔄 Test query result: {result.fetchone()}")
                
                # Dispose old engine
                print("🔄 Step 3: Disposing old engine...")
                if self.engine:
                    await self.engine.dispose()
                
                # Switch
                print("🔄 Step 4: Switching to new engine...")
                old_db = self.current_db
                self.engine = new_engine
                self.current_db_index = new_index
                self.async_session_maker = async_sessionmaker(
                    self.engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autocommit=False,
                    autoflush=False,
                )
                
                print(f"✅✅✅ Successfully switched from {old_db} to {new_uri}")
                return True
                
            except Exception as e:
                print(f"❌❌❌ Failed to switch to {new_uri}: {e}")
                import traceback
                traceback.print_exc()
                return False
    
    async def monitor_db(self) -> None:
        """Monitor DB health and perform failover when current DB dies"""
        print("🔍 DB Monitor task started")
        check_counter = 0
        
        while self._running:
            await asyncio.sleep(1)  # Check every second
            check_counter += 1
            
            # Log every 30 seconds to show monitor is alive
            if check_counter % 30 == 0:
                db_name = "MAIN" if self.current_db_index == 0 else "STANDBY"
                print(f"🔍 Monitor heartbeat: Using {db_name} DB")
            
            try:
                # Check current DB health
                current_alive = await self.check_db_available(self.current_db, timeout=3)
                
                if not current_alive:
                    # Current DB is down, switch to the other one
                    other_index = 1 if self.current_db_index == 0 else 0
                    other_uri = self.db_uris[other_index]
                    
                    print(f"⚠️⚠️⚠️ CURRENT DB DOWN! Current: {self.current_db}, Trying: {other_uri}")
                    
                    # Try multiple times to connect to the standby
                    for retry in range(5):
                        print(f"🔄 Failover attempt {retry + 1}/5...")
                        other_alive = await self.check_db_available(other_uri, timeout=3)
                        print(f"🔍 Other DB ({other_uri}) alive: {other_alive}")
                        
                        if other_alive:
                            print(f"✅✅✅ Switching to {other_uri}...")
                            success = await self.switch_db(other_index)
                            if success:
                                print(f"✅✅✅ SUCCESSFULLY SWITCHED TO {other_uri}")
                                break
                            else:
                                print(f"❌❌❌ FAILED TO SWITCH TO {other_uri}")
                        else:
                            print(f"❌ Other DB ({other_uri}) not ready yet, waiting 2s...")
                            await asyncio.sleep(2)
                    else:
                        print(f"❌❌❌ All failover attempts failed!")
                        
            except asyncio.CancelledError:
                print("🛑 Monitor task cancelled")
                break
            except Exception as e:
                print(f"❌ Monitor error: {e}")
                import traceback
                traceback.print_exc()
        
        print("🛑 DB Monitor task stopped")
    
    async def shutdown(self) -> None:
        """Cleanup resources"""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        if self.engine:
            await self.engine.dispose()
            print("✅ Database connections closed")
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session with automatic cleanup"""
        if not self.async_session_maker:
            raise RuntimeError("Database not initialized")
        
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


# Global database manager instance
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions in FastAPI routes"""
    async with db_manager.session() as session:
        yield session

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.utils.config import settings
from app.utils.database import db_manager
from app.routers import auth, users, messages, google_auth, two_factor
from app.routers.socketio_server import socket_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown"""
    # Startup
    print("🚀 Starting FastAPI application...")
    await db_manager.initialize()
    print("✅ Application started successfully")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down FastAPI application...")
    await db_manager.shutdown()
    print("✅ Application shut down successfully")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    app = FastAPI(
        title="MyNet Chat API",
        description="Chat application API with full async support",
        version="2.0.0",
        lifespan=lifespan
    )
    
    # Configure CORS
    origins = settings.origins_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(auth.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(messages.router, prefix="/api")
    app.include_router(google_auth.router, prefix="/api")
    app.include_router(two_factor.router, prefix="/api")
    
    # Mount Socket.IO app for WebSocket support
    app.mount("/api/socket.io", socket_app)
    
    return app


# Create the app instance
app = create_app()

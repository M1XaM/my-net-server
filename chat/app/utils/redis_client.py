"""
Redis client utility for managing online users and chat state.
"""
import os
import json
from typing import Dict, Any, Optional, List
import redis.asyncio as redis
from functools import lru_cache


class RedisSettings:
    """Redis connection settings"""
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    
    # Key prefixes
    ONLINE_USERS_KEY = "chat:online_users"
    USER_DATA_PREFIX = "chat:user:"


@lru_cache()
def get_redis_settings() -> RedisSettings:
    return RedisSettings()


redis_settings = get_redis_settings()


class RedisManager:
    """
    Async Redis client manager for chat application.
    Handles online users tracking using Redis Hash.
    """
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
    
    async def get_client(self) -> redis.Redis:
        """Get or create Redis client"""
        if self._client is None:
            self._client = redis.Redis(
                host=redis_settings.REDIS_HOST,
                port=redis_settings.REDIS_PORT,
                password=redis_settings.REDIS_PASSWORD,
                db=redis_settings.REDIS_DB,
                decode_responses=True
            )
        return self._client
    
    async def close(self) -> None:
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            self._client = None
    
    # Online Users Management
    async def add_online_user(self, user_id: str, user_data: Dict[str, Any]) -> None:
        """Add a user to the online users set"""
        client = await self.get_client()
        await client.hset(
            redis_settings.ONLINE_USERS_KEY,
            user_id,
            json.dumps(user_data)
        )
    
    async def remove_online_user(self, user_id: str) -> None:
        """Remove a user from the online users set"""
        client = await self.get_client()
        await client.hdel(redis_settings.ONLINE_USERS_KEY, user_id)
    
    async def get_online_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific online user's data"""
        client = await self.get_client()
        data = await client.hget(redis_settings.ONLINE_USERS_KEY, user_id)
        if data:
            return json.loads(data)
        return None
    
    async def get_all_online_users(self) -> Dict[str, Dict[str, Any]]:
        """Get all online users"""
        client = await self.get_client()
        all_users = await client.hgetall(redis_settings.ONLINE_USERS_KEY)
        return {user_id: json.loads(data) for user_id, data in all_users.items()}
    
    async def get_online_users_list(self) -> List[Dict[str, Any]]:
        """Get list of all online users' data"""
        users = await self.get_all_online_users()
        return list(users.values())
    
    async def get_online_users_count(self) -> int:
        """Get count of online users"""
        client = await self.get_client()
        return await client.hlen(redis_settings.ONLINE_USERS_KEY)
    
    async def is_user_online(self, user_id: str) -> bool:
        """Check if a user is online"""
        client = await self.get_client()
        return await client.hexists(redis_settings.ONLINE_USERS_KEY, user_id)
    
    async def clear_all_online_users(self) -> int:
        """Clear all online users (for testing/reset)"""
        client = await self.get_client()
        count = await client.hlen(redis_settings.ONLINE_USERS_KEY)
        await client.delete(redis_settings.ONLINE_USERS_KEY)
        return count
    
    # Health check
    async def ping(self) -> bool:
        """Check if Redis is available"""
        try:
            client = await self.get_client()
            return await client.ping()
        except Exception:
            return False


# Global Redis manager instance
redis_manager = RedisManager()


# Convenience functions for direct usage
async def add_online_user(user_id: str, user_data: Dict[str, Any]) -> None:
    await redis_manager.add_online_user(user_id, user_data)


async def remove_online_user(user_id: str) -> None:
    await redis_manager.remove_online_user(user_id)


async def get_online_users() -> Dict[str, Any]:
    """Get online users in the format expected by chat service"""
    users = await redis_manager.get_online_users_list()
    count = len(users)
    return {
        'count': count,
        'users': users
    }


async def is_user_online(user_id: str) -> bool:
    return await redis_manager.is_user_online(str(user_id))


async def clear_all_connections() -> Dict[str, Any]:
    """Clear all online users"""
    count = await redis_manager.clear_all_online_users()
    return {
        'message': f'Cleared {count} online users',
        'previous_count': count
    }

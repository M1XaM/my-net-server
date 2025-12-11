from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import user_repository

async def get_all_users_formatted(db: AsyncSession) -> List[Dict[str, Any]]:
    """
    Get all users and format them for API response
    
    Returns:
        List of user dictionaries with id and username
    """
    users = await user_repository.get_all_users(db)
    
    return [
        {
            'id': user.id,
            'username': user.username
        }
        for user in users
    ]

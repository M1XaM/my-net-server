"""
Chat service - handles all chat-related business logic.
Manages online users (via Redis) and message operations.
"""
from typing import Dict, Any, Optional, Tuple, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import message_repository
from app.utils.database import db_manager
from app.utils.security import sanitize_message
from app.utils.redis_client import redis_manager


# ============================================================================
# Online Users Management (Redis)
# ============================================================================

async def add_online_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add user to online list and return updated list"""
    user_id = str(user_data['id'])
    await redis_manager.add_online_user(user_id, user_data)
    return await get_online_users()


async def remove_online_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove user from online list and return updated list"""
    user_id = str(user_data['id'])
    await redis_manager.remove_online_user(user_id)
    return await get_online_users()


async def get_online_users() -> Dict[str, Any]:
    """Get all online users"""
    users = await redis_manager.get_online_users_list()
    return {'count': len(users), 'users': users}


async def is_user_online(user_id: str) -> bool:
    """Check if user is online"""
    return await redis_manager.is_user_online(str(user_id))


# ============================================================================
# Room Management
# ============================================================================

def create_room_name(user_id: str, other_id: str) -> str:
    """Create consistent room name for two users"""
    ids = sorted([str(user_id), str(other_id)])
    return f"{ids[0]}_{ids[1]}"


def validate_join_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """Validate join room request data"""
    if not data or not isinstance(data, dict):
        return False, 'Invalid data format', None, None
    
    user_id = data.get('user_id')
    other_id = data.get('other_id')
    
    if not user_id or not other_id:
        return False, 'user_id and other_id are required', None, None
    
    try:
        UUID(str(user_id))
        UUID(str(other_id))
    except (ValueError, TypeError):
        return False, 'Invalid UUID format', None, None
    
    return True, None, str(user_id), str(other_id)


# ============================================================================
# Message Operations
# ============================================================================

async def send_message(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """
    Process and save a message.
    Handles its own database session.
    
    Returns: (success, error_message, formatted_message, room_name)
    """
    # Validate input
    sender_id = data.get('sender_id')
    receiver_id = data.get('receiver_id')
    content = data.get('content', '').strip()
    
    if not sender_id or not receiver_id:
        return False, 'sender_id and receiver_id are required', None, None
    
    if not content:
        return False, 'Message content cannot be empty', None, None
    
    try:
        sender_uuid = UUID(str(sender_id))
        receiver_uuid = UUID(str(receiver_id))
    except (ValueError, TypeError):
        return False, 'Invalid UUID format', None, None
    
    # Sanitize content
    sanitized_content = sanitize_message(content)
    
    # Save to database
    async with db_manager.session() as db:
        success, result, status_code = await message_repository.save_message(
            db, sender_uuid, receiver_uuid, sanitized_content
        )
        
        if not success:
            return False, result.get('error', 'Failed to save message'), None, None
        
        message = result
        formatted = {
            'id': str(message.id),
            'sender_id': str(message.sender_id),
            'receiver_id': str(message.receiver_id),
            'content': message.content,
            'timestamp': message.timestamp.isoformat() if message.timestamp else None
        }
        
        room_name = create_room_name(sender_id, receiver_id)
        return True, None, formatted, room_name


async def get_conversation(user_id: UUID, other_id: UUID) -> Tuple[bool, List[Dict[str, Any]] | Dict, int]:
    """
    Fetch messages between two users.
    Handles its own database session.
    """
    async with db_manager.session() as db:
        success, result, status_code = await message_repository.get_conversation(db, user_id, other_id)
        
        if not success:
            return False, result, status_code
        
        messages = [
            {
                'id': str(m.id),
                'sender_id': str(m.sender_id),
                'receiver_id': str(m.receiver_id),
                'content': m.content,
                'timestamp': m.timestamp.isoformat() if m.timestamp else None
            }
            for m in result
        ]
        return True, messages, 200

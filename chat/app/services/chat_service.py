from typing import Dict, Any, Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import message_repository

from app.utils.security import sanitize_message
from app.utils.redis_client import (
    redis_manager,
    get_online_users as redis_get_online_users,
    is_user_online as redis_is_user_online,
    clear_all_connections as redis_clear_all_connections
)


async def handle_user_connection(user_data: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Handle user connection - add user to online users list (Redis)
    
    Args:
        user_data: User data dictionary containing 'id' key (as string UUID)
        
    Returns:
        Tuple of (success, error_message, updated_users)
    """
    user_id = str(user_data['id'])
    await redis_manager.add_online_user(user_id, user_data)
    
    return True, None, await redis_get_online_users()


async def handle_user_disconnection(user_data: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Handle user disconnection - remove user from online users list (Redis)
    
    Args:
        user_data: User data dictionary containing 'id' key (as string UUID)
        
    Returns:
        Tuple of (success, error_message, updated_users)
    """
    user_id = str(user_data['id'])
    await redis_manager.remove_online_user(user_id)
    
    return True, None, await redis_get_online_users()


async def get_online_users() -> Dict[str, Any]:
    """
    Get all online users from Redis
    
    Returns:
        Dictionary with online users information
    """
    return await redis_get_online_users()


async def is_user_online(user_id: str) -> bool:
    """
    Check if a specific user is online (via Redis)
    
    Args:
        user_id: User ID (string UUID) to check
        
    Returns:
        True if user is online, False otherwise
    """
    return await redis_is_user_online(str(user_id))


def create_chat_room(user_id: str, other_id: str) -> str:
    """
    Create a consistent room identifier for two users
    
    Args:
        user_id: First user ID (string UUID)
        other_id: Second user ID (string UUID)
        
    Returns:
        Room identifier string
    """
    ids = sorted([str(user_id), str(other_id)])
    return f"{ids[0]}_{ids[1]}"


def validate_message_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[UUID], Optional[UUID], Optional[str]]:
    """
    Validate and sanitize message data
    
    Args:
        data: Message data dictionary (already validated by router)
        
    Returns:
        Tuple of (is_valid, error_message, sender_id, receiver_id, content)
    """
    sender_id = UUID(data.get('sender_id'))
    receiver_id = UUID(data.get('receiver_id'))
    content = data.get('content', '').strip()
    
    # Sanitize content for XSS prevention (business logic)
    sanitized_content = sanitize_message(content)
    
    return True, None, sender_id, receiver_id, sanitized_content


async def process_message(
    db: AsyncSession,
    sender_id: UUID,
    receiver_id: UUID,
    content: str
) -> Dict[str, Any] | Tuple[bool, Dict, int]:
    """
    Process and save a message
    
    Args:
        db: Database session
        sender_id: ID of the message sender
        receiver_id: ID of the message receiver
        content: Message content (already sanitized)
        
    Returns:
        Formatted message dictionary or error tuple
    """
    success, result, status_code = await message_repository.save_message(
        db, sender_id, receiver_id, content
    )
    if not success:
        return False, {"error": result.get("error")}, status_code
    
    message = result
    return {
        'id': str(message.id),
        'sender_id': str(message.sender_id),
        'receiver_id': str(message.receiver_id),
        'content': message.content,
        'timestamp': message.timestamp.isoformat() if message.timestamp else None
    }


async def handle_send_message(
    db: AsyncSession,
    data: Dict[str, Any]
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """
    Handle send message request
    
    Args:
        db: Database session
        data: Message data dictionary
        
    Returns:
        Tuple of (success, error_message, formatted_message, room_name)
    """
    is_valid, error_msg, sender_id, receiver_id, content = validate_message_data(data)
    if not is_valid:
        return False, error_msg, None, None
    
    try:
        formatted_message = await process_message(db, sender_id, receiver_id, content)
    except ValueError as e:
        return False, str(e), None, None
    
    room_name = create_chat_room(sender_id, receiver_id)
    
    return True, None, formatted_message, room_name


def validate_join_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Validate join room data from WebSocket messages
    Note: WebSocket messages bypass router validation, so basic checks are needed here
    
    Args:
        data: Join room data dictionary
        
    Returns:
        Tuple of (is_valid, error_message, user_id, other_id)
    """
    if not data or not isinstance(data, dict):
        return False, 'Invalid join data format', None, None
    
    user_id = data.get('user_id')
    other_id = data.get('other_id')
    
    if user_id is None or other_id is None:
        return False, 'Both user_id and other_id are required', None, None
    
    try:
        # Validate they are valid UUIDs
        UUID(str(user_id))
        UUID(str(other_id))
        user_id = str(user_id)
        other_id = str(other_id)
    except (ValueError, TypeError):
        return False, 'User IDs must be valid UUIDs', None, None
    
    return True, None, user_id, other_id


async def get_user_rooms(user_id: str) -> Dict[str, Any]:
    """
    Get all rooms a user is potentially in
    """
    user_rooms = []
    user_id_str = str(user_id)
    
    online_users = await redis_manager.get_all_online_users()
    for online_user_id in online_users.keys():
        if online_user_id != user_id_str:
            room_name = create_chat_room(user_id_str, online_user_id)
            user_rooms.append({
                'room': room_name,
                'other_user_id': online_user_id
            })
    
    return {
        'user_id': user_id_str,
        'rooms': user_rooms,
        'room_count': len(user_rooms)
    }


async def broadcast_online_users() -> Dict[str, Any]:
    """Get online users for broadcasting"""
    users = await redis_manager.get_online_users_list()
    return {'users': users}


async def clear_all_connections() -> Dict[str, Any]:
    """Clear all online users (for testing/reset purposes)"""
    return await redis_clear_all_connections()

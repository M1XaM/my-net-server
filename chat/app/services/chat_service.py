from typing import Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import message_repository

from app.utils.security import sanitize_message

_online_users: Dict[int, Dict[str, Any]] = {}


def handle_user_connection(user_data: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Handle user connection - add user to online users list
    
    Args:
        user_data: User data dictionary containing 'id' key
        
    Returns:
        Tuple of (success, error_message, updated_users)
    """
    if not user_data or 'id' not in user_data:
        return False, 'Invalid user data', {}
    
    user_id = user_data['id']
    _online_users[user_id] = user_data
    
    return True, None, get_online_users()


def handle_user_disconnection(user_data: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Handle user disconnection - remove user from online users list
    
    Args:
        user_data: User data dictionary containing 'id' key
        
    Returns:
        Tuple of (success, error_message, updated_users)
    """
    if not user_data or 'id' not in user_data:
        return False, 'Invalid user data', {}
    
    user_id = user_data['id']
    _online_users.pop(user_id, None)
    
    return True, None, get_online_users()


def get_online_users() -> Dict[str, Any]:
    """
    Get all online users
    
    Returns:
        Dictionary with online users information
    """
    return {
        'count': len(_online_users),
        'users': list(_online_users.values())
    }


def is_user_online(user_id: int) -> bool:
    """
    Check if a specific user is online
    
    Args:
        user_id: User ID to check
        
    Returns:
        True if user is online, False otherwise
    """
    return user_id in _online_users


def create_chat_room(user_id: int, other_id: int) -> str:
    """
    Create a consistent room identifier for two users
    
    Args:
        user_id: First user ID
        other_id: Second user ID
        
    Returns:
        Room identifier string
    """
    return f"{min(user_id, other_id)}_{max(user_id, other_id)}"


def validate_message_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[int], Optional[int], Optional[str]]:
    """
    Validate message data
    
    Args:
        data: Message data dictionary
        
    Returns:
        Tuple of (is_valid, error_message, sender_id, receiver_id, content)
    """
    sender_id = data.get('sender_id')
    receiver_id = data.get('receiver_id')
    content = data.get('content')
    
    if not sender_id or not receiver_id or not content:
        return False, 'Missing required fields', None, None, None
    
    try:
        sender_id = int(sender_id)
        receiver_id = int(receiver_id)
    except (ValueError, TypeError):
        return False, 'Invalid user IDs', None, None, None
    
    if sender_id <= 0 or receiver_id <= 0:
        return False, 'User IDs must be positive integers', None, None, None
    
    if not isinstance(content, str) or not content.strip():
        return False, 'Message content cannot be empty', None, None, None
    
    sanitized_content = sanitize_message(content)
    
    return True, None, sender_id, receiver_id, sanitized_content


async def process_message(
    db: AsyncSession,
    sender_id: int,
    receiver_id: int,
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
        'id': message.id,
        'sender_id': message.sender_id,
        'receiver_id': message.receiver_id,
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


def validate_join_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[int], Optional[int]]:
    """
    Validate join room data
    
    Args:
        data: Join room data dictionary
        
    Returns:
        Tuple of (is_valid, error_message, user_id, other_id)
    """
    user_id = data.get('user_id')
    other_id = data.get('other_id')
    
    if not user_id or not other_id:
        return False, 'Missing user_id or other_id', None, None
    
    try:
        user_id = int(user_id)
        other_id = int(other_id)
    except (ValueError, TypeError):
        return False, 'Invalid user IDs', None, None
    
    if user_id <= 0 or other_id <= 0:
        return False, 'User IDs must be positive integers', None, None
    
    return True, None, user_id, other_id


def get_user_rooms(user_id: int) -> Dict[str, Any]:
    """
    Get all rooms a user is potentially in
    """
    user_rooms = []
    
    for online_user_id in _online_users.keys():
        if online_user_id != user_id:
            room_name = create_chat_room(user_id, online_user_id)
            user_rooms.append({
                'room': room_name,
                'other_user_id': online_user_id
            })
    
    return {
        'user_id': user_id,
        'rooms': user_rooms,
        'room_count': len(user_rooms)
    }


def broadcast_online_users() -> Dict[str, Any]:
    """Get online users for broadcasting"""
    return {'users': list(_online_users.values())}


def clear_all_connections() -> Dict[str, Any]:
    """Clear all online users (for testing/reset purposes)"""
    global _online_users
    user_count = len(_online_users)
    _online_users = {}
    
    return {
        'message': f'Cleared {user_count} online users',
        'previous_count': user_count
    }

"""
Socket.IO server - handles real-time WebSocket communication.
Clean implementation using python-socketio with FastAPI.
"""
import socketio

from app.services import chat_service
from app.utils.config import settings

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=settings.origins_list,
    logger=False,
    engineio_logger=False
)

# ASGI app for mounting
socket_app = socketio.ASGIApp(sio, socketio_path='')


@sio.event
async def connect(sid, environ):
    """Client connected"""
    await sio.emit('connection_success', {'sid': sid}, to=sid)


@sio.event
async def disconnect(sid):
    """Client disconnected"""
    pass


@sio.event
async def join(sid, data):
    """Join a chat room"""
    valid, error, user_id, other_id = chat_service.validate_join_data(data)
    
    if not valid:
        await sio.emit('join_error', {'error': error}, to=sid)
        return
    
    room = chat_service.create_room_name(user_id, other_id)
    await sio.enter_room(sid, room)
    
    await sio.emit('user_joined', {'user_id': user_id, 'room': room}, room=room, skip_sid=sid)
    await sio.emit('join_success', {'room': room, 'user_id': user_id, 'other_id': other_id}, to=sid)


@sio.event
async def send_message(sid, data):
    """Send a message"""
    # Validate message length
    content = data.get('content', '') if isinstance(data, dict) else ''
    if len(content) > 100000:
        await sio.emit('message_error', {'error': 'Message exceeds maximum length of 100000 characters'}, to=sid)
        return
    
    success, error, message, room = await chat_service.send_message(data)
    
    if not success:
        await sio.emit('message_error', {'error': error}, to=sid)
        return
    
    # Ensure sender is in the room
    await sio.enter_room(sid, room)
    
    # Send to sender
    await sio.emit('receive_message', message, to=sid)
    # Broadcast to room (excluding sender)
    await sio.emit('receive_message', message, room=room, skip_sid=sid)
    # Confirm delivery
    await sio.emit('message_delivered', {'message_id': message['id'], 'timestamp': message['timestamp']}, to=sid)


@sio.event
async def user_connected(sid, user_data):
    """User came online"""
    updated = await chat_service.add_online_user(user_data)
    await sio.emit('users_list', updated['users'])


@sio.event
async def user_disconnected(sid, user_data):
    """User went offline"""
    updated = await chat_service.remove_online_user(user_data)
    await sio.emit('users_list', updated['users'])


@sio.event
async def typing(sid, data):
    """Typing indicator"""
    user_id = data.get('user_id')
    other_id = data.get('other_id')
    
    if user_id and other_id:
        room = chat_service.create_room_name(user_id, other_id)
        await sio.emit('user_typing', {
            'user_id': user_id,
            'is_typing': data.get('is_typing', False)
        }, room=room, skip_sid=sid)


@sio.event
async def get_online_users(sid):
    """Get online users list"""
    users = await chat_service.get_online_users()
    await sio.emit('online_users_response', users, to=sid)


@sio.event
async def check_user_online(sid, data):
    """Check if specific user is online"""
    user_id = data.get('user_id')
    
    if not user_id:
        await sio.emit('user_online_status', {'error': 'Missing user_id'}, to=sid)
        return
    
    is_online = await chat_service.is_user_online(str(user_id))
    await sio.emit('user_online_status', {'user_id': user_id, 'is_online': is_online}, to=sid)

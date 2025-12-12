"""
Socket.IO server implementation using python-socketio with FastAPI.
This provides full compatibility with Socket.IO clients.
"""
import socketio
from typing import Dict, Any

from app.services import chat_service

from app.utils.database import db_manager
from app.utils.config import settings

# Create Socket.IO server with async support
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=settings.origins_list,
    logger=True,
    engineio_logger=True
)

# Create ASGI app for Socket.IO
socket_app = socketio.ASGIApp(sio, socketio_path='')


@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    print(f"Client connected: {sid}")
    await sio.emit('connection_success', {
        'sid': sid,
        'message': 'Connected to chat server'
    }, to=sid)


@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    print(f"Client disconnected: {sid}")


@sio.event
async def join(sid, data):
    """Handle join room event"""
    is_valid, error_msg, user_id, other_id = chat_service.validate_join_data(data)
    
    if not is_valid:
        print(f"Invalid join data: {error_msg}")
        await sio.emit('join_error', {'error': error_msg}, to=sid)
        return
    
    room = f"{min(user_id, other_id)}_{max(user_id, other_id)}"
    await sio.enter_room(sid, room)
    print(f"✅ User {user_id} (sid={sid}) joined room {room}")
    rooms = sio.rooms(sid)
    print(f"📋 Room {room} members: {rooms}")
    
    # Notify others in room
    await sio.emit('user_joined', {
        'user_id': user_id,
        'room': room
    }, room=room, skip_sid=sid)
    
    # Confirm to sender
    await sio.emit('join_success', {
        'room': room,
        'user_id': user_id,
        'other_id': other_id
    }, to=sid)


@sio.event
async def send_message(sid, data):
    """Handle send message event"""
    print(f"📥 Received send_message from {sid}: {data}")
    
    # Extract sender and receiver IDs
    sender_id = data.get('sender_id')
    receiver_id = data.get('receiver_id')
    
    # Calculate room name (use string comparison for UUIDs)
    room_name = None
    if sender_id and receiver_id:
        # Sort UUIDs as strings to create consistent room name
        ids = sorted([str(sender_id), str(receiver_id)])
        room_name = f"{ids[0]}_{ids[1]}"
        # Enter the room
        await sio.enter_room(sid, room_name)
        rooms = sio.rooms(sid)
        print(f"🔄 Entered room {room_name}, current rooms: {rooms}")
    
    async with db_manager.session() as db:
        success, error_msg, formatted_message, room_name_from_service = await chat_service.handle_send_message(
            db, data
        )
    
    if not success:
        print(f"Message send error: {error_msg}")
        await sio.emit('message_error', {'error': error_msg}, to=sid)
        return
    
    room_name = room_name_from_service or room_name
    print(f"📨 Formatted message: {formatted_message}")
    print(f"📨 Sending to sid={sid}, room={room_name}")
    
    # Send directly to sender first (guaranteed delivery)
    print(f"🔴 Emitting receive_message to sid {sid}")
    await sio.emit('receive_message', formatted_message, to=sid)
    print(f"🟢 Emitted receive_message to sid {sid}")
    
    # Also broadcast to room for other participants (skip sender to avoid duplicate)
    await sio.emit('receive_message', formatted_message, room=room_name, skip_sid=sid)
    
    # Confirm delivery
    print(f"🔴 Emitting message_delivered to sid {sid}")
    await sio.emit('message_delivered', {
        'message_id': formatted_message['id'],
        'timestamp': formatted_message['timestamp']
    }, to=sid)
    print(f"🟢 Emitted message_delivered to sid {sid}")


@sio.event
async def user_connected(sid, user_data):
    """Handle user connection event"""
    success, error_msg, updated_users = await chat_service.handle_user_connection(user_data)
    
    if not success:
        print(f"User connection error: {error_msg}")
        return
    
    # Broadcast updated users list to all
    await sio.emit('users_list', updated_users['users'])


@sio.event
async def user_disconnected(sid, user_data):
    """Handle user disconnection event"""
    success, error_msg, updated_users = await chat_service.handle_user_disconnection(user_data)
    
    if not success:
        print(f"User disconnection error: {error_msg}")
        return
    
    # Broadcast updated users list to all
    await sio.emit('users_list', updated_users['users'])


@sio.event
async def typing(sid, data):
    """Handle typing indicator event"""
    user_id = data.get('user_id')
    other_id = data.get('other_id')
    is_typing = data.get('is_typing', False)
    
    if not user_id or not other_id:
        return
    
    room = f"{min(user_id, other_id)}_{max(user_id, other_id)}"
    
    await sio.emit('user_typing', {
        'user_id': user_id,
        'is_typing': is_typing
    }, room=room, skip_sid=sid)


@sio.event
async def get_online_users(sid):
    """Handle get online users request"""
    online_users_data = await chat_service.get_online_users()
    await sio.emit('online_users_response', online_users_data, to=sid)


@sio.event
async def check_user_online(sid, data):
    """Handle check if user is online request"""
    user_id = data.get('user_id')
    
    if not user_id:
        await sio.emit('user_online_status', {'error': 'Missing user_id'}, to=sid)
        return
    
    try:
        user_id = int(user_id)
        is_online = await chat_service.is_user_online(user_id)
        
        await sio.emit('user_online_status', {
            'user_id': user_id,
            'is_online': is_online
        }, to=sid)
    except (ValueError, TypeError):
        await sio.emit('user_online_status', {'error': 'Invalid user_id'}, to=sid)

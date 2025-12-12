from typing import Dict, Any, Set
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import chat_service
from app.utils.database import db_manager


class ConnectionManager:
    """Manages WebSocket connections and rooms"""
    
    def __init__(self):
        # Map of websocket to session ID
        self.active_connections: Dict[WebSocket, str] = {}
        # Map of room name to set of websockets
        self.rooms: Dict[str, Set[WebSocket]] = {}
        # Map of session ID to websocket
        self.sid_to_websocket: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket) -> str:
        """Accept connection and generate session ID"""
        await websocket.accept()
        sid = str(id(websocket))
        self.active_connections[websocket] = sid
        self.sid_to_websocket[sid] = websocket
        return sid
    
    def disconnect(self, websocket: WebSocket) -> None:
        """Remove connection and clean up rooms"""
        if websocket in self.active_connections:
            sid = self.active_connections[websocket]
            del self.sid_to_websocket[sid]
            del self.active_connections[websocket]
        
        # Remove from all rooms
        for room_sockets in self.rooms.values():
            room_sockets.discard(websocket)
    
    def join_room(self, websocket: WebSocket, room: str) -> None:
        """Add websocket to a room"""
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(websocket)
    
    def leave_room(self, websocket: WebSocket, room: str) -> None:
        """Remove websocket from a room"""
        if room in self.rooms:
            self.rooms[room].discard(websocket)
    
    async def send_personal(self, websocket: WebSocket, data: dict) -> None:
        """Send message to a specific websocket"""
        try:
            await websocket.send_json(data)
        except Exception:
            pass
    
    async def broadcast_to_room(
        self,
        room: str,
        data: dict,
        exclude: WebSocket | None = None
    ) -> None:
        """Broadcast message to all connections in a room"""
        if room not in self.rooms:
            return
        
        for websocket in self.rooms[room]:
            if websocket != exclude:
                await self.send_personal(websocket, data)
    
    async def broadcast_all(self, data: dict) -> None:
        """Broadcast message to all connected clients"""
        for websocket in self.active_connections:
            await self.send_personal(websocket, data)
    
    def get_sid(self, websocket: WebSocket) -> str | None:
        """Get session ID for a websocket"""
        return self.active_connections.get(websocket)


# Global connection manager
manager = ConnectionManager()


async def handle_websocket_message(
    websocket: WebSocket,
    data: Dict[str, Any]
) -> None:
    """Route websocket messages to appropriate handlers"""
    event = data.get('event')
    payload = data.get('data', {})
    
    if event == 'join':
        await handle_join(websocket, payload)
    elif event == 'send_message':
        await handle_send_message(websocket, payload)
    elif event == 'user_connected':
        await handle_user_connected(websocket, payload)
    elif event == 'user_disconnected':
        await handle_user_disconnected(websocket, payload)
    elif event == 'typing':
        await handle_typing(websocket, payload)
    elif event == 'get_online_users':
        await handle_get_online_users(websocket)
    elif event == 'check_user_online':
        await handle_check_user_online(websocket, payload)


async def handle_join(websocket: WebSocket, data: Dict[str, Any]) -> None:
    """Handle join room event"""
    is_valid, error_msg, user_id, other_id = chat_service.validate_join_data(data)
    
    if not is_valid:
        print(f"Invalid join data: {error_msg}")
        await manager.send_personal(websocket, {
            'event': 'join_error',
            'data': {'error': error_msg}
        })
        return
    
    room = f"{min(user_id, other_id)}_{max(user_id, other_id)}"
    manager.join_room(websocket, room)
    
    # Notify others in room
    await manager.broadcast_to_room(
        room,
        {
            'event': 'user_joined',
            'data': {
                'user_id': user_id,
                'room': room
            }
        },
        exclude=websocket
    )
    
    # Confirm to sender
    await manager.send_personal(websocket, {
        'event': 'join_success',
        'data': {
            'room': room,
            'user_id': user_id,
            'other_id': other_id
        }
    })


async def handle_send_message(websocket: WebSocket, data: Dict[str, Any]) -> None:
    """Handle send message event"""
    async with db_manager.session() as db:
        success, error_msg, formatted_message, room_name = await chat_service.handle_send_message(
            db, data
        )
    
    if not success:
        print(f"Message send error: {error_msg}")
        await manager.send_personal(websocket, {
            'event': 'message_error',
            'data': {'error': error_msg}
        })
        return
    
    # Broadcast to room
    await manager.broadcast_to_room(
        room_name,
        {
            'event': 'receive_message',
            'data': formatted_message
        }
    )
    
    # Confirm delivery
    await manager.send_personal(websocket, {
        'event': 'message_delivered',
        'data': {
            'message_id': formatted_message['id'],
            'timestamp': formatted_message['timestamp']
        }
    })


async def handle_user_connected(websocket: WebSocket, user_data: Dict[str, Any]) -> None:
    """Handle user connection event"""
    success, error_msg, updated_users = await chat_service.handle_user_connection(user_data)
    
    if not success:
        print(f"User connection error: {error_msg}")
        return
    
    # Broadcast updated users list to all
    await manager.broadcast_all({
        'event': 'users_list',
        'data': updated_users['users']
    })


async def handle_user_disconnected(websocket: WebSocket, user_data: Dict[str, Any]) -> None:
    """Handle user disconnection event"""
    success, error_msg, updated_users = await chat_service.handle_user_disconnection(user_data)
    
    if not success:
        print(f"User disconnection error: {error_msg}")
        return
    
    # Broadcast updated users list to all
    await manager.broadcast_all({
        'event': 'users_list',
        'data': updated_users['users']
    })


async def handle_typing(websocket: WebSocket, data: Dict[str, Any]) -> None:
    """Handle typing indicator event"""
    user_id = data.get('user_id')
    other_id = data.get('other_id')
    is_typing = data.get('is_typing', False)
    
    if not user_id or not other_id:
        return
    
    room = f"{min(user_id, other_id)}_{max(user_id, other_id)}"
    
    await manager.broadcast_to_room(
        room,
        {
            'event': 'user_typing',
            'data': {
                'user_id': user_id,
                'is_typing': is_typing
            }
        },
        exclude=websocket
    )


async def handle_get_online_users(websocket: WebSocket) -> None:
    """Handle get online users request"""
    online_users_data = await chat_service.get_online_users()
    await manager.send_personal(websocket, {
        'event': 'online_users_response',
        'data': online_users_data
    })


async def handle_check_user_online(websocket: WebSocket, data: Dict[str, Any]) -> None:
    """Handle check if user is online request"""
    user_id = data.get('user_id')
    
    if not user_id:
        await manager.send_personal(websocket, {
            'event': 'user_online_status',
            'data': {'error': 'Missing user_id'}
        })
        return
    
    try:
        user_id = int(user_id)
        is_online = await chat_service.is_user_online(user_id)
        
        await manager.send_personal(websocket, {
            'event': 'user_online_status',
            'data': {
                'user_id': user_id,
                'is_online': is_online
            }
        })
    except (ValueError, TypeError):
        await manager.send_personal(websocket, {
            'event': 'user_online_status',
            'data': {'error': 'Invalid user_id'}
        })


async def websocket_endpoint(websocket: WebSocket) -> None:
    """Main WebSocket endpoint handler"""
    sid = await manager.connect(websocket)
    
    # Send connection success
    await manager.send_personal(websocket, {
        'event': 'connection_success',
        'data': {
            'sid': sid,
            'message': 'Connected to chat server'
        }
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            await handle_websocket_message(websocket, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

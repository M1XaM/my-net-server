from typing import Dict, Any, Set, Optional
import json
import asyncio
from fastapi import WebSocket, WebSocketDisconnect

from app.services import chat_service
from app.utils.database import db_manager


class SocketIOManager:
    """
    Manages WebSocket connections with Socket.IO-like protocol.
    Supports: connect, disconnect, emit, rooms, broadcast
    """
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # sid -> websocket
        self.websocket_to_sid: Dict[WebSocket, str] = {}
        self.rooms: Dict[str, Set[str]] = {}  # room_name -> set of sids
        self.sid_rooms: Dict[str, Set[str]] = {}  # sid -> set of rooms
        self._sid_counter = 0
    
    def _generate_sid(self) -> str:
        """Generate a unique session ID"""
        self._sid_counter += 1
        return f"sid_{self._sid_counter}_{id(asyncio.current_task())}"
    
    async def connect(self, websocket: WebSocket) -> str:
        """Accept connection and return session ID"""
        await websocket.accept()
        sid = self._generate_sid()
        self.active_connections[sid] = websocket
        self.websocket_to_sid[websocket] = sid
        self.sid_rooms[sid] = set()
        return sid
    
    def disconnect(self, websocket: WebSocket) -> Optional[str]:
        """Disconnect and cleanup"""
        sid = self.websocket_to_sid.get(websocket)
        if not sid:
            return None
        
        # Leave all rooms
        for room in list(self.sid_rooms.get(sid, [])):
            self.leave_room(sid, room)
        
        # Cleanup
        del self.active_connections[sid]
        del self.websocket_to_sid[websocket]
        del self.sid_rooms[sid]
        
        return sid
    
    def join_room(self, sid: str, room: str) -> None:
        """Join a room"""
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(sid)
        self.sid_rooms[sid].add(room)
    
    def leave_room(self, sid: str, room: str) -> None:
        """Leave a room"""
        if room in self.rooms:
            self.rooms[room].discard(sid)
            if not self.rooms[room]:
                del self.rooms[room]
        if sid in self.sid_rooms:
            self.sid_rooms[sid].discard(room)
    
    async def emit(
        self,
        event: str,
        data: Any,
        to: Optional[str] = None,
        room: Optional[str] = None,
        skip_sid: Optional[str] = None
    ) -> None:
        """
        Emit an event.
        - to: specific sid to send to
        - room: broadcast to all in room
        - skip_sid: exclude this sid from broadcast
        """
        message = json.dumps({"event": event, "data": data})
        
        if to:
            # Send to specific client
            ws = self.active_connections.get(to)
            if ws:
                try:
                    await ws.send_text(message)
                except Exception:
                    pass
        elif room:
            # Broadcast to room
            for sid in self.rooms.get(room, set()):
                if sid != skip_sid:
                    ws = self.active_connections.get(sid)
                    if ws:
                        try:
                            await ws.send_text(message)
                        except Exception:
                            pass
        else:
            # Broadcast to all
            for sid, ws in self.active_connections.items():
                if sid != skip_sid:
                    try:
                        await ws.send_text(message)
                    except Exception:
                        pass
    
    def get_sid(self, websocket: WebSocket) -> Optional[str]:
        """Get session ID for a websocket"""
        return self.websocket_to_sid.get(websocket)


# Global manager
sio = SocketIOManager()


async def handle_connect(websocket: WebSocket, sid: str) -> None:
    """Handle client connection"""
    await sio.emit('connection_success', {
        'sid': sid,
        'message': 'Connected to chat server'
    }, to=sid)


async def handle_join(websocket: WebSocket, sid: str, data: Dict[str, Any]) -> None:
    """Handle join room event"""
    is_valid, error_msg, user_id, other_id = chat_service.validate_join_data(data)
    
    if not is_valid:
        print(f"Invalid join data: {error_msg}")
        await sio.emit('join_error', {'error': error_msg}, to=sid)
        return
    
    room = f"{min(user_id, other_id)}_{max(user_id, other_id)}"
    sio.join_room(sid, room)
    
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


async def handle_send_message(websocket: WebSocket, sid: str, data: Dict[str, Any]) -> None:
    """Handle send message event"""
    async with db_manager.session() as db:
        success, error_msg, formatted_message, room_name = await chat_service.handle_send_message(
            db, data
        )
    
    if not success:
        print(f"Message send error: {error_msg}")
        await sio.emit('message_error', {'error': error_msg}, to=sid)
        return
    
    # Broadcast to room
    await sio.emit('receive_message', formatted_message, room=room_name)
    
    # Confirm delivery
    await sio.emit('message_delivered', {
        'message_id': formatted_message['id'],
        'timestamp': formatted_message['timestamp']
    }, to=sid)


async def handle_user_connected(websocket: WebSocket, sid: str, user_data: Dict[str, Any]) -> None:
    """Handle user connection event"""
    success, error_msg, updated_users = await chat_service.handle_user_connection(user_data)
    
    if not success:
        print(f"User connection error: {error_msg}")
        return
    
    # Broadcast updated users list to all
    await sio.emit('users_list', updated_users['users'])


async def handle_user_disconnected(websocket: WebSocket, sid: str, user_data: Dict[str, Any]) -> None:
    """Handle user disconnection event"""
    success, error_msg, updated_users = await chat_service.handle_user_disconnection(user_data)
    
    if not success:
        print(f"User disconnection error: {error_msg}")
        return
    
    # Broadcast updated users list to all
    await sio.emit('users_list', updated_users['users'])


async def handle_typing(websocket: WebSocket, sid: str, data: Dict[str, Any]) -> None:
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


async def handle_get_online_users(websocket: WebSocket, sid: str) -> None:
    """Handle get online users request"""
    online_users_data = await chat_service.get_online_users()
    await sio.emit('online_users_response', online_users_data, to=sid)


async def handle_check_user_online(websocket: WebSocket, sid: str, data: Dict[str, Any]) -> None:
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


# Event handlers map
EVENT_HANDLERS = {
    'join': handle_join,
    'send_message': handle_send_message,
    'user_connected': handle_user_connected,
    'user_disconnected': handle_user_disconnected,
    'typing': handle_typing,
    'get_online_users': handle_get_online_users,
    'check_user_online': handle_check_user_online,
}


async def socketio_endpoint(websocket: WebSocket) -> None:
    """
    Socket.IO compatible WebSocket endpoint.
    Expects messages in format: {"event": "event_name", "data": {...}}
    """
    sid = await sio.connect(websocket)
    
    try:
        # Send connection success
        await handle_connect(websocket, sid)
        
        while True:
            # Receive message
            raw_data = await websocket.receive_text()
            
            try:
                message = json.loads(raw_data)
                event = message.get('event')
                data = message.get('data', {})
                
                # Route to handler
                handler = EVENT_HANDLERS.get(event)
                if handler:
                    if event in ('get_online_users',):
                        await handler(websocket, sid)
                    else:
                        await handler(websocket, sid, data)
                else:
                    print(f"Unknown event: {event}")
                    
            except json.JSONDecodeError:
                print(f"Invalid JSON received: {raw_data}")
                
    except WebSocketDisconnect:
        sio.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        sio.disconnect(websocket)

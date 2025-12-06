from flask import request
from flask_socketio import join_room, emit

from app.services import chat_service

def register_socket_events(socketio):
    @socketio.on('connect')
    def handle_connect():
        """
        Handle client connection event
        """        
        emit('connection_success', {
            'sid': request.sid,
            'message': 'Connected to chat server'
        })
    

    @socketio.on('join')
    def handle_join(data):
        is_valid, error_msg, user_id, other_id = chat_service.validate_join_data(data)
        
        if not is_valid:
            print(f"Invalid join data: {error_msg}")
            emit('join_error', {'error': error_msg})
            return
        
        room = f"{min(user_id, other_id)}_{max(user_id, other_id)}"
        join_room(room)
                
        emit('user_joined', {
            'user_id': user_id,
            'room': room
        }, room=room, skip_sid=request.sid)

        emit('join_success', {
            'room': room,
            'user_id': user_id,
            'other_id': other_id
        })
    

    @socketio.on('send_message')
    def handle_send_message(data):
        success, error_msg, formatted_message, room_name = chat_service.handle_send_message(data)
        
        if not success:
            print(f"Message send error: {error_msg}")
            emit('message_error', {'error': error_msg})
            return
        
        emit('receive_message', formatted_message, room=room_name)
        emit('message_delivered', {
            'message_id': formatted_message['id'],
            'timestamp': formatted_message['timestamp']
        })
    

    @socketio.on('user_connected')
    def handle_user_connected(user_data):
        success, error_msg, updated_users = chat_service.handle_user_connection(user_data)
        
        if not success:
            print(f"User connection error: {error_msg}")
            return
        
        emit('users_list', updated_users['users'], broadcast=True)    

    @socketio.on('user_disconnected')
    def handle_user_disconnected(user_data):
        success, error_msg, updated_users = chat_service.handle_user_disconnection(user_data)
        
        if not success:
            print(f"User disconnection error: {error_msg}")
            return
        
        emit('users_list', updated_users['users'], broadcast=True)
    

    @socketio.on('disconnect')
    def handle_disconnect():
        pass
    
    @socketio.on('typing')
    def handle_typing(data):
        user_id = data.get('user_id')
        other_id = data.get('other_id')
        is_typing = data.get('is_typing', False)
        
        if not user_id or not other_id:
            return
        
        room = f"{min(user_id, other_id)}_{max(user_id, other_id)}"
        
        emit('user_typing', {
            'user_id': user_id,
            'is_typing': is_typing
        }, room=room, skip_sid=request.sid)
    

    @socketio.on('get_online_users')
    def handle_get_online_users():
        online_users_data = chat_service.get_online_users()
        emit('online_users_response', online_users_data)
    

    @socketio.on('check_user_online')
    def handle_check_user_online(data):
        user_id = data.get('user_id')
        
        if not user_id:
            emit('user_online_status', {'error': 'Missing user_id'})
            return
        
        try:
            user_id = int(user_id)
            is_online = chat_service.is_user_online(user_id)
            
            emit('user_online_status', {
                'user_id': user_id,
                'is_online': is_online
            })
        except (ValueError, TypeError):
            emit('user_online_status', {'error': 'Invalid user_id'})
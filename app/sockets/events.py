from flask_socketio import join_room, emit
from flask import request
from app.models.message import Message

online_users = {}

def register_socket_events(socketio):

    @socketio.on('connect')
    def handle_connect():
        print(f"Client connected: {request.sid}")

    @socketio.on('join')
    def handle_join(data):
        user_id = data.get('user_id')
        other_id = data.get('other_id')
        if user_id and other_id:
            room = f"{min(user_id, other_id)}_{max(user_id, other_id)}"
            join_room(room)
            print(f"User {user_id} joined room {room}")

    @socketio.on('send_message')
    def handle_send_message(data):
        from app import db
        
        sender_id = data.get('sender_id')
        receiver_id = data.get('receiver_id')
        content = data.get('content')

        if not sender_id or not receiver_id or not content:
            return

        message = Message(sender_id=sender_id, receiver_id=receiver_id, content=content)
        db.session.add(message)
        db.session.commit()

        room = f"{min(sender_id, receiver_id)}_{max(sender_id, receiver_id)}"
        emit('receive_message', {
            'id': message.id,
            'sender_id': message.sender_id,
            'receiver_id': message.receiver_id,
            'content': message.content,
            'timestamp': message.timestamp.isoformat()
        }, room=room)

    @socketio.on('user_connected')
    def handle_user_connected(user_data):
        if not user_data or 'id' not in user_data:
            print(f"Invalid user data received: {user_data}")
            return
            
        user_id = user_data['id']
        online_users[user_id] = user_data
        emit('users_list', list(online_users.values()), broadcast=True)

    @socketio.on('user_disconnected')
    def handle_user_disconnected(user_data):
        if user_data and 'id' in user_data:
            user_id = user_data['id']
            online_users.pop(user_id, None)
            emit('users_list', list(online_users.values()), broadcast=True)
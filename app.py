from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room
import os, time
from sqlalchemy.exc import IntegrityError, OperationalError

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")  # Allow cross-origin connections

# Database config
DB_USER = os.getenv('DB_USER', 'chat_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'chat_password')
DB_HOST = os.getenv('DB_HOST', 'db')
DB_NAME = os.getenv('DB_NAME', 'chatdb')

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

# DB init
def init_db():
    retries = 10
    while retries > 0:
        try:
            with app.app_context():
                db.create_all()
            print("✅ Database initialized successfully!")
            break
        except OperationalError as e:
            print(f"⏳ DB not ready ({e}), retrying in 5s...")
            retries -= 1
            time.sleep(5)
    else:
        raise Exception("❌ Could not connect to DB")

# REST endpoints for login/register/users
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    if not username:
        return jsonify({'error': 'Username required'}), 400

    new_user = User(username=username)
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'id': new_user.id, 'username': new_user.username}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Username exists'}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    if not username:
        return jsonify({'error': 'Username required'}), 400

    user = User.query.filter_by(username=username).first()
    if user:
        return jsonify({'id': user.id, 'username': user.username}), 200
    else:
        return jsonify({'error': 'User not found'}), 404

@app.route('/api/users', methods=['GET'])
def get_users():
    users = User.query.order_by(User.username).all()
    return jsonify([{'id': u.id, 'username': u.username} for u in users])

# SocketIO events
@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('join')
def handle_join(data):
    """Join a chat room (room = 'user1_user2')"""
    user_id = data.get('user_id')
    other_id = data.get('other_id')
    if user_id and other_id:
        room = f"{min(user_id, other_id)}_{max(user_id, other_id)}"
        join_room(room)
        print(f"User {user_id} joined room {room}")

@socketio.on('send_message')
def handle_send_message(data):
    """Receive a message and broadcast to room"""
    sender_id = data.get('sender_id')
    receiver_id = data.get('receiver_id')
    content = data.get('content')

    if not sender_id or not receiver_id or not content:
        return

    # Save to DB
    message = Message(sender_id=sender_id, receiver_id=receiver_id, content=content)
    db.session.add(message)
    db.session.commit()

    # Send message to both users in the room
    room = f"{min(sender_id, receiver_id)}_{max(sender_id, receiver_id)}"
    emit('receive_message', {
        'id': message.id,
        'sender_id': message.sender_id,
        'receiver_id': message.receiver_id,
        'content': message.content,
        'timestamp': message.timestamp.isoformat()
    }, room=room)

online_users = {}

@socketio.on('user_connected')
def handle_user_connected(user_data):
    # Add safety checks for the user_data
    if not user_data or 'id' not in user_data:
        print(f"Invalid user data received: {user_data}")
        return
        
    user_id = user_data['id']
    online_users[user_id] = user_data
    # broadcast the updated list to all clients
    emit('users_list', list(online_users.values()), broadcast=True)

@socketio.on('user_disconnected')
def handle_user_disconnected(user_data):
    if user_data and 'id' in user_data:
        user_id = user_data['id']
        online_users.pop(user_id, None)
        emit('users_list', list(online_users.values()), broadcast=True)


@app.route('/api/messages/<int:user_id>/<int:other_id>', methods=['GET'])
def get_messages(user_id, other_id):
    # Get messages between two users
    messages = Message.query.filter(
        ((Message.sender_id == user_id) & (Message.receiver_id == other_id)) |
        ((Message.sender_id == other_id) & (Message.receiver_id == user_id))
    ).order_by(Message.timestamp.asc()).all()
    
    return jsonify([{
        'id': m.id,
        'sender_id': m.sender_id,
        'receiver_id': m.receiver_id,
        'content': m.content,
        'timestamp': m.timestamp.isoformat()
    } for m in messages])

if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=5000)
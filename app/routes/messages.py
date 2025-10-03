from flask import Blueprint, jsonify
from app.models.message import Message

messages_bp = Blueprint('messages', __name__)

@messages_bp.route('/messages/<int:user_id>/<int:other_id>', methods=['GET'])
def get_messages(user_id, other_id):
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
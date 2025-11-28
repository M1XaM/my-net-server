from flask import Blueprint, jsonify, request
import requests

from app.models.message import Message
from app.utils.jwt_utils import jwt_required

messages_bp = Blueprint('messages', __name__)

@messages_bp.route('/messages/<int:user_id>/<int:other_id>', methods=['GET'])
@jwt_required
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

@messages_bp.route('/messages/run-code', methods=['POST'])
@jwt_required
def run_code():
    data = request.get_json(silent=True)
    if not data or 'code' not in data:
        return jsonify({'error': 'missing code'}), 400

    code = data['code']

    try:
        # Send code to the downstream executor endpoint
        resp = requests.post('http://runner:8080/run-code', json={'code': code}, timeout=10)

        # Try to parse JSON output, fallback to plain text
        try:
            body = resp.json()
        except ValueError:
            body = resp.text

        return jsonify({
            'status': resp.status_code,
            'body': body
        }), resp.status_code

    except requests.exceptions.Timeout:
        return jsonify({'error': 'executor timed out'}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 502

from flask import Blueprint, jsonify, request

from app.services import message_service
from app.utils.jwt_utils import jwt_required

messages_bp = Blueprint('messages', __name__)

@messages_bp.route('/messages/<int:user_id>/<int:other_id>', methods=['GET'])
@jwt_required
def get_messages(user_id, other_id):
    success, messages, status_code = message_service.fetch_conversation_messages(user_id, other_id)
    if not success:
        return jsonify(messages), status_code
    return jsonify(messages), 200

@messages_bp.route('/messages/run-code', methods=['POST'])
@jwt_required
def run_code():
    data = request.get_json()
    if not data or 'code' not in data:
        return jsonify({'error': 'Invalid request, missing code'}), 400
    
    success, result, status_code = message_service.execute_code_via_runner(data.get('code'))
    if not success:
        return jsonify({'error': result}), status_code
    
    return jsonify(result), status_code
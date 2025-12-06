from flask import Blueprint, jsonify

from app.services import user_service
from app.utils.jwt_utils import jwt_required

users_bp = Blueprint('users', __name__)

@users_bp.route('/users', methods=['GET'])
@jwt_required
def get_users():
    """
    Get all users (original endpoint)
    
    Returns:
        JSON array of users with id and username
    """
    try:
        users = user_service.get_all_users_formatted()
        
        return jsonify(users), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch users'}), 500
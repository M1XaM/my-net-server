from flask import Blueprint, jsonify
from app.models.user import User
from app.utils.jwt_utils import jwt_required


users_bp = Blueprint('users', __name__)

@users_bp.route('/users', methods=['GET'])
@jwt_required
def get_users():
    users = User.query.order_by(User._username).all()
    return jsonify([{'id': u.id, 'username': u.username} for u in users])
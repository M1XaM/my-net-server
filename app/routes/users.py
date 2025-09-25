from flask import Blueprint, jsonify
from app.models import User
from werkzeug.security import generate_password_hash, check_password_hash


users_bp = Blueprint('users', __name__)

@users_bp.route('/users', methods=['GET'])
def get_users():
    users = User.query.order_by(User.username).all()
    return jsonify([{'id': u.id, 'username': u.username} for u in users])
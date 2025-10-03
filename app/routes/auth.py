from flask import Blueprint, request, jsonify
from app import db
from app.utils.encrypt import hash_username
from app.models.user import User
from sqlalchemy.exc import IntegrityError

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    if not password:
        return jsonify({'error': 'Password required'}), 400

    # Create new user
    new_user = User()
    new_user.username = username  # This will encrypt and hash the username
    new_user.set_password(password)  # Hash the password
    
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({
            'id': new_user.id,
            'username': username
        }), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Username already exists'}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    if not password:
        return jsonify({'error': 'Password required'}), 400

    # Find user by hashed username
    user = User.query.filter_by(username_hash=hash_username(username)).first()
    
    if user and user.check_password(password):
        return jsonify({
            'id': user.id,
            'username': user.username  # This will decrypt automatically
        }), 200
    else:
        return jsonify({'error': 'Invalid username or password'}), 401
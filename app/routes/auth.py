from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
import traceback
from app.utils.csrf_utils import generate_csrf_token, csrf_protect


from app import db
from app.models.user import User
from app.utils.encrypt import hash_username
from app.utils.jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_token
)

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
    new_user.set_password(password) # hash passwors

    try:
        db.session.add(new_user)
        db.session.commit()
        access_token = create_access_token(new_user.id)  # JWT
        refresh_token = create_refresh_token(new_user.id)  # JWT refresh
        csrf_token = generate_csrf_token()

        response = jsonify({
            'id': new_user.id,
            'username': username,
            'access_token': access_token,
            'csrf_token': csrf_token

        })
        response.set_cookie('refresh_token', refresh_token, httponly=True, secure=True, samesite='Strict')
        return response, 201
    except IntegrityError:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'error': 'Username already exists'}), 400


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    totp_token = data.get('totp_token')  # NEW: optional 2FA code

    if not username:
        return jsonify({'error': 'Username required'}), 400
    if not password:
        return jsonify({'error': 'Password required'}), 400

    # Find user
    user = User.query.filter_by(username_hash=hash_username(username)).first()

    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid username or password'}), 401

    # NEW: Check if 2FA is enabled
    if user.totp_enabled:
        if not totp_token:
            # Tell frontend: "you need to provide 2FA code"
            return jsonify({
                'requires_2fa': True,
                'message': 'Please provide 2FA code'
            }), 200

        # Verify the 2FA code
        from app.utils.totp import verify_totp
        if not verify_totp(user.totp_secret, totp_token):
            return jsonify({'error': 'Invalid 2FA code'}), 401

    # Normal login flow (create tokens, etc.)
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    csrf_token = generate_csrf_token()

    response = jsonify({
        'id': user.id,
        'username': user.username,
        'access_token': access_token,
        'csrf_token': csrf_token,
        'totp_enabled': user.totp_enabled
    })
    response.set_cookie('refresh_token', refresh_token, httponly=True, secure=True, samesite='Strict')
    return response, 200

@auth_bp.route('/token/refresh', methods=['POST'])
def refresh_token():
    refresh_token = request.cookies.get('refresh_token')
    payload = decode_token(refresh_token)
    if not payload or payload.get('type') != 'refresh':
        return jsonify({'error': 'Invalid refresh token'}), 401
    user_id = payload['user_id']
    access_token = create_access_token(user_id)
    new_refresh_token = create_refresh_token(user_id)
    csrf_token = generate_csrf_token()
    response = jsonify({'access_token': access_token, 'csrf_token': csrf_token})

    response.set_cookie('refresh_token', new_refresh_token, httponly=True, secure=True, samesite='Strict')
    return response

@auth_bp.route('/logout', methods=['POST'])
def logout():
    response = jsonify({'message': 'Logged out'})
    response.set_cookie('refresh_token', '', expires=0)
    return response
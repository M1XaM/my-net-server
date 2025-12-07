from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
import traceback
import random
import string
import re
from datetime import datetime, timedelta, timezone
from app.utils.csrf_utils import generate_csrf_token, csrf_protect
from app import db
from app.models.user import User
from app.utils.email_service import send_verification_email
from app.utils.encrypt import hash_username
from app.utils.jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_token
)

auth_bp = Blueprint('auth', __name__)

def is_valid_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def generate_verification_code():
    """Generate a 6-digit random verification code"""
    return ''. join(random.choices(string. digits, k=6))

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip()

    # Validate required fields
    if not username:
        return jsonify({'error': 'Username required'}), 400
    if not password:
        return jsonify({'error': 'Password required'}), 400
    if not email:
        return jsonify({'error': 'Email required'}), 400

    # Validate email format
    if not is_valid_email(email):
        return jsonify({'error': 'Invalid email format'}), 400

    # Check if email already exists
    existing_email = User.query.filter_by(email=email).first()
    if existing_email:
        return jsonify({'error': 'Email already registered'}), 400

    # Create new user
    new_user = User()
    new_user.username = username
    new_user.set_password(password)
    new_user.email = email
    new_user.is_email_verified = False

    # Generate 6-digit verification code
    verification_code = generate_verification_code()
    new_user.verification_code = verification_code
    new_user.verification_code_expires_at = datetime.now(timezone. utc) + timedelta(minutes=15)

    try:
        db.session.add(new_user)
        db.session.commit()

        send_verification_email(email, verification_code, username)
        print(f"📧 Verification code for {email}: {verification_code}")

        return jsonify({
            'status': 'pending_verification',
            'user_id': new_user.id,
            'email': email,
            'message': 'Verification code sent to your email.  Please verify to complete registration.'
        }), 201

    except IntegrityError as e:
        traceback.print_exc()
        db.session.rollback()
        error_message = str(e. orig) if hasattr(e, 'orig') else str(e)
        if 'email' in error_message. lower():
            return jsonify({'error': 'Email already exists'}), 400
        return jsonify({'error': 'Username already exists'}), 400


@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    """✅ Verify email with 6-digit code"""
    data = request.get_json()
    user_id = data.get('user_id')
    verification_code = data.get('verification_code')

    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
    if not verification_code:
        return jsonify({'error': 'Verification code required'}), 400

    user = User.query.get(user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    # ✅ Check if already verified
    if user.is_email_verified:
        return jsonify({'error': 'Email already verified'}), 400

    # ✅ Check if code matches
    if user.verification_code != verification_code:
        return jsonify({'error': 'Invalid verification code'}), 400

    # ✅ Check if code expired - FIX: Make comparison timezone-naive
    if user.verification_code_expires_at:
        # Convert to naive datetime for comparison
        expires_at = user.verification_code_expires_at
        if isinstance(expires_at, datetime) and expires_at.tzinfo is not None:
            # If it's timezone-aware, convert to naive UTC
            expires_at = expires_at.replace(tzinfo=None)

        current_time = datetime.now()  # ✅ Use naive datetime
        if current_time > expires_at:
            return jsonify({'error': 'Verification code expired'}), 400

    # ✅ Mark as verified and clear code
    user.is_email_verified = True
    user.verification_code = None
    user.verification_code_expires_at = None

    try:
        db.session.commit()

        # ✅ Generate tokens for auto-login
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        csrf_token = generate_csrf_token()

        response = jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'access_token': access_token,
            'csrf_token': csrf_token,
            'message': 'Email verified successfully!'
        })
        response.set_cookie('refresh_token', refresh_token, httponly=True, secure=True, samesite='Strict')
        return response, 200

    except Exception as e:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'error': 'Error verifying email'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request. get_json()
    username = data.get('username')
    password = data.get('password')
    totp_token = data.get('totp_token')

    if not username:
        return jsonify({'error': 'Username required'}), 400
    if not password:
        return jsonify({'error': 'Password required'}), 400

    # Find user by hashed username
    user = User.query. filter_by(username_hash=hash_username(username)). first()

    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid username or password'}), 401

    # Email must be verified
    if not user. is_email_verified:
        return jsonify({'error': 'Please verify your email before logging in'}), 403

    # Check if 2FA is enabled
    if user.totp_enabled:
        if not totp_token:
            return jsonify({
                'requires_2fa': True,
                'message': 'Please provide 2FA code'
            }), 200

        from app.utils.totp import verify_totp
        if not verify_totp(user.totp_secret, totp_token):
            return jsonify({'error': 'Invalid 2FA code'}), 401

    # Normal login flow
    access_token = create_access_token(user. id)
    refresh_token = create_refresh_token(user. id)
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
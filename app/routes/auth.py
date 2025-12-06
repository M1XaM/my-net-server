from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
import traceback
from datetime import datetime, timedelta
from app.utils.csrf_utils import generate_csrf_token, csrf_protect


from app import db
from app.models.user import User
from app.models.email_verification import EmailVerification
from app.utils.encrypt import hash_username
from app.utils.jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_token
)
from app.utils.email_utils import send_verification_email

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    if not password:
        return jsonify({'error': 'Password required'}), 400
    if not email:
        return jsonify({'error': 'Email required'}), 400

    # Create new user (unverified)
    new_user = User()
    new_user.username = username  # This will encrypt and hash the username
    new_user.set_password(password) # hash password
    new_user.email = email
    new_user.is_email_verified = False

    try:
        db.session.add(new_user)
        db.session.commit()
        
        # Generate verification token
        token = EmailVerification.generate_token()
        verification = EmailVerification(
            user_id=new_user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db.session.add(verification)
        db.session.commit()
        
        # Send verification email
        send_verification_email(email, username, token)
        
        return jsonify({
            'message': 'Registration successful. Please check your email to verify your account.',
            'email': email
        }), 201
    except IntegrityError as e:
        traceback.print_exc()
        db.session.rollback()
        error_message = str(e.orig) if hasattr(e, 'orig') else str(e)
        if 'email' in error_message.lower():
            return jsonify({'error': 'Email already exists'}), 400
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
        # Check if email is verified
        if not user.is_email_verified:
            return jsonify({'error': 'Please verify your email before logging in'}), 403
        
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        csrf_token = generate_csrf_token()

        response = jsonify({
            'id': user.id,
            'username': user.username,
            'access_token': access_token,
            'csrf_token': csrf_token

        })
        response.set_cookie('refresh_token', refresh_token, httponly=True, secure=True, samesite='Strict')
        return response, 200
    else:
        return jsonify({'error': 'Invalid username or password'}), 401

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

@auth_bp.route('/verify-email', methods=['GET'])
def verify_email():
    token = request.args.get('token')
    
    if not token:
        return jsonify({'error': 'Verification token required'}), 400
    
    # Find verification record
    verification = EmailVerification.query.filter_by(token=token).first()
    
    if not verification:
        return jsonify({'error': 'Invalid verification token'}), 400
    
    if not verification.is_valid():
        if verification.is_used:
            return jsonify({'error': 'This verification link has already been used'}), 400
        if verification.is_expired():
            return jsonify({'error': 'This verification link has expired'}), 400
    
    # Mark user as verified
    user = User.query.get(verification.user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user.is_email_verified = True
    user.email_verified_at = datetime.utcnow()
    verification.is_used = True
    
    try:
        db.session.commit()
        return jsonify({
            'message': 'Email verified successfully. You can now log in.',
            'username': user.username
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({'error': 'Failed to verify email'}), 500

@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    data = request.get_json()
    email = data.get('email')
    
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    # Find user by email
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user.is_email_verified:
        return jsonify({'error': 'Email already verified'}), 400
    
    # Invalidate old tokens
    old_verifications = EmailVerification.query.filter_by(
        user_id=user.id,
        is_used=False
    ).all()
    for old_verification in old_verifications:
        old_verification.is_used = True
    
    # Generate new verification token
    token = EmailVerification.generate_token()
    verification = EmailVerification(
        user_id=user.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )
    db.session.add(verification)
    
    try:
        db.session.commit()
        # Send verification email
        send_verification_email(email, user.username, token)
        return jsonify({
            'message': 'Verification email sent. Please check your inbox.'
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({'error': 'Failed to send verification email'}), 500
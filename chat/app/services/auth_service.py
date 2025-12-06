import traceback
from datetime import datetime

from app.repositories.user_repository import get_by_email, create_user, get_by_username, get_by_id, mark_email_as_verified
from app.services.email_service import send_verification_email
from app.utils.csrf_utils import generate_csrf_token
from app.utils.totp_utils import verify_totp
from app.utils.jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_token
)

def register_user(username, password, email):
    existing_email = get_by_email(email)
    if existing_email:
        return False, {'error': 'Email already registered'}, 400
    
    succes, result, status_code = create_user(username=username, password=password, email=email)

    if not succes:
        return False, {'error': result.get('error', 'Registration failed')}, status_code

    send_verification_email(email, result.get("verification_code"), username)

    return True, {"user_id": result.get("user_id")}, 200  # not passing verfication code to the controller 

def login_user(username, password, totp_token):
    """
    Authenticate and login user
    Returns: (success, data, status_code)
    """
    try:
        user = get_by_username(username)
    except Exception:
        # Something went wrong querying the DB — log and return a server error
        traceback.print_exc()
        return False, {'error': 'Internal server error during login'}, 500, None

    if not user or not user.check_password(password):
        return False, {'error': 'Invalid username or password'}, 401, None
    if not user. is_email_verified:
        return False, {'error': 'Please verify your email before logging in'}, 403, None

    if user.totp_enabled:
        if not totp_token:
            return False, {
                'requires_2fa': True,
                'message': 'Please provide 2FA code'
            }, 200, None
        if not verify_totp(user.totp_secret, totp_token):
            return False, {'error': 'Invalid 2FA code'}, 401, None

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    csrf_token = generate_csrf_token()

    return True, {
        'id': user.id,
        'username': user.username,
        'access_token': access_token,
        'csrf_token': csrf_token,
        'totp_enabled': user.totp_enabled,
    }, 200, refresh_token


def refresh_access_token(refresh_token):
    """
    Generate new access token using refresh token
    Returns: (success, data, status_code)
    """
    if not refresh_token:
        return False, {'error': 'Refresh token required'}, 401

    try:
        # Decode and validate refresh token
        payload = decode_token(refresh_token)
        if not payload or payload.get('type') != 'refresh':
            return False, {'error': 'Invalid refresh token'}, 401

        # Generate new tokens
        user_id = payload['user_id']
        access_token = create_access_token(user_id)
        new_refresh_token = create_refresh_token(user_id)
        csrf_token = generate_csrf_token()

        return True, {
            'tokens': {
                'access_token': access_token,
                'refresh_token': new_refresh_token,
                'csrf_token': csrf_token
            }
        }, 200

    except Exception as e:
        # Token validation or generation failed
        traceback.print_exc()
        return False, {'error': 'Token refresh failed'}, 401

# Optional: Helper function for token management
def create_auth_tokens(user_id):
    """Create all authentication tokens for a user"""
    return {
        'access_token': create_access_token(user_id),
        'refresh_token': create_refresh_token(user_id),
        'csrf_token': generate_csrf_token()
    }

# Optional: Function to extract common response formatting
def format_auth_response(success, data, status_code):
    """Format authentication response"""
    if success:
        return {
            'success': True,
            'data': data,
            'status_code': status_code
        }
    else:
        return {
            'success': False,
            'error': data.get('error'),
            'status_code': status_code
        }

def verify_email(user_id, verification_code):
    user = get_by_id(user_id)

    if not user:
        return False, {'error': 'User not found'}, 404
    if user.is_email_verified:
        return False, {'error': 'Email already verified'}, 400
    if user.verification_code != verification_code:
        return False, {'error': 'Invalid verification code'}, 400
    if user.verification_code_expires_at:
        # Convert to naive datetime for comparison
        expires_at = user.verification_code_expires_at
        if isinstance(expires_at, datetime) and expires_at.tzinfo is not None:
            # If it's timezone-aware, convert to naive UTC
            expires_at = expires_at.replace(tzinfo=None)

        current_time = datetime.now()  # Use naive datetime
        if current_time > expires_at:
            return False, {'error': 'Verification code expired'}, 400

    mark_email_as_verified(user)

    # Generate tokens for auto-login
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    csrf_token = generate_csrf_token()

    return True, {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "access_token": access_token,
        "csrf_token": csrf_token,
        "refresh_token": refresh_token
    }, 200
import traceback
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import user_repository
from app.services.email_service import send_verification_email_async

from app.utils.security import (
    generate_csrf_token,
    verify_totp,
    create_access_token,
    create_refresh_token,
    decode_token,
)


async def register_user(
    db: AsyncSession,
    username: str,
    password: str,
    email: str
) -> tuple[bool, dict, int]:
    """Register a new user and send verification email"""
    # Check for existing email
    existing_email = await user_repository.get_by_email(db, email)
    if existing_email:
        return False, {'error': 'An account with this email address already exists'}, 409
    
    # Check for existing username
    existing_username = await user_repository.get_by_username(db, username)
    if existing_username:
        return False, {'error': 'This username is already taken. Please choose a different one'}, 409
    
    success, result, status_code = await user_repository.create_user(
        db, username=username, password=password, email=email
    )

    if not success:
        error_msg = result.get('error', 'Registration failed')
        if 'email' in error_msg.lower():
            return False, {'error': 'An account with this email address already exists'}, 409
        if 'username' in error_msg.lower():
            return False, {'error': 'This username is already taken. Please choose a different one'}, 409
        return False, {'error': f'Registration failed: {error_msg}'}, status_code

    # Send verification email asynchronously
    await send_verification_email_async(email, result.get("verification_code"), username)

    return True, {"user_id": result.get("user_id")}, 200


async def login_user(
    db: AsyncSession,
    username: str,
    password: str,
    totp_token: str | None
) -> tuple[bool, dict, int, str | None]:
    """
    Authenticate and login user
    Returns: (success, data, status_code, refresh_token)
    """
    try:
        user = await user_repository.get_by_username(db, username)
    except Exception:
        traceback.print_exc()
        return False, {'error': 'An unexpected error occurred during login. Please try again'}, 500, None

    if not user or not user.check_password(password):
        return False, {'error': 'The username or password you entered is incorrect'}, 401, None
    
    if not user.is_email_verified:
        return False, {'error': 'Your email address has not been verified. Please check your inbox for the verification email'}, 403, None

    if user.totp_enabled:
        if not totp_token:
            return False, {
                'requires_2fa': True,
                'message': 'Two-factor authentication is enabled. Please enter your 6-digit authenticator code'
            }, 200, None
        if not verify_totp(user.totp_secret, totp_token):
            return False, {'error': 'The 2FA code you entered is invalid or has expired. Please try again with a new code'}, 401, None

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


async def refresh_access_token(refresh_token: str) -> tuple[bool, dict, int]:
    """
    Generate new access token using refresh token
    Returns: (success, data, status_code)
    """
    try:
        payload = decode_token(refresh_token)
        if not payload:
            return False, {'error': 'Your session has expired. Please log in again'}, 401
        
        if payload.get('type') != 'refresh':
            return False, {'error': 'Invalid token type. Expected a refresh token'}, 401

        user_id = payload.get('user_id')
        if not user_id or not isinstance(user_id, int):
            return False, {'error': 'Invalid token payload. Please log in again'}, 401
        
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

    except Exception:
        traceback.print_exc()
        return False, {'error': 'Failed to refresh your session. Please log in again'}, 401


def create_auth_tokens(user_id: int) -> dict:
    """Create all authentication tokens for a user"""
    return {
        'access_token': create_access_token(user_id),
        'refresh_token': create_refresh_token(user_id),
        'csrf_token': generate_csrf_token()
    }


async def verify_email(
    db: AsyncSession,
    user_id: int,
    verification_code: str
) -> tuple[bool, dict, int]:
    """Verify user's email with verification code\"\"\"\n    user = await user_repository.get_by_id(db, user_id)

    if not user:
        return False, {'error': 'No user found with the provided ID. The account may have been deleted'}, 404
    
    if user.is_email_verified:
        return False, {'error': 'This email address has already been verified. You can proceed to log in'}, 400
    
    if user.verification_code != verification_code:
        return False, {'error': 'The verification code you entered is incorrect. Please check and try again'}, 400
    
    if user.verification_code_expires_at:
        expires_at = user.verification_code_expires_at
        if isinstance(expires_at, datetime) and expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)

        current_time = datetime.now()
        if current_time > expires_at:
            return False, {'error': 'Your verification code has expired. Please request a new one'}, 400

    await user_repository.mark_email_as_verified(db, user)

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

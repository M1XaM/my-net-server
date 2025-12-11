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
    existing_email = await user_repository.get_by_email(db, email)
    if existing_email:
        return False, {'error': 'Email already registered'}, 400
    
    success, result, status_code = await user_repository.create_user(
        db, username=username, password=password, email=email
    )

    if not success:
        return False, {'error': result.get('error', 'Registration failed')}, status_code

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
        return False, {'error': 'Internal server error during login'}, 500, None

    if not user or not user.check_password(password):
        return False, {'error': 'Invalid username or password'}, 401, None
    
    if not user.is_email_verified:
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


async def refresh_access_token(refresh_token: str) -> tuple[bool, dict, int]:
    """
    Generate new access token using refresh token
    Returns: (success, data, status_code)
    """
    if not refresh_token:
        return False, {'error': 'Refresh token required'}, 401

    try:
        payload = decode_token(refresh_token)
        if not payload or payload.get('type') != 'refresh':
            return False, {'error': 'Invalid refresh token'}, 401

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

    except Exception:
        traceback.print_exc()
        return False, {'error': 'Token refresh failed'}, 401


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
    """Verify user's email with verification code"""
    user = await user_repository.get_by_id(db, user_id)

    if not user:
        return False, {'error': 'User not found'}, 404
    if user.is_email_verified:
        return False, {'error': 'Email already verified'}, 400
    if user.verification_code != verification_code:
        return False, {'error': 'Invalid verification code'}, 400
    
    if user.verification_code_expires_at:
        expires_at = user.verification_code_expires_at
        if isinstance(expires_at, datetime) and expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)

        current_time = datetime.now()
        if current_time > expires_at:
            return False, {'error': 'Verification code expired'}, 400

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

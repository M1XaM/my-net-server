from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import traceback

from app.models.user import User
from app.utils.encryption import hash_username
from app.utils.security import generate_verification_code


async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
    email: str
) -> tuple[bool, dict[str, Any], int]:
    """Create a new user with email verification"""
    new_user = User()
    new_user.username = username
    new_user.set_password(password)
    
    verification_code = generate_verification_code()
    new_user.email = email
    new_user.is_email_verified = False
    new_user.verification_code = verification_code
    new_user.verification_code_expires_at = datetime.utcnow() + timedelta(minutes=15)  # Use naive UTC datetime

    try:
        db.add(new_user)
        await db.flush()
        await db.refresh(new_user)
        
        return True, {
            "verification_code": verification_code,
            "user_id": new_user.id
        }, 200

    except IntegrityError as e:
        await db.rollback()
        error_message = str(e.orig) if hasattr(e, 'orig') else str(e)

        if 'email' in error_message.lower():
            result = {"error": 'Email already exists'}
        elif 'username' in error_message.lower():
            result = {"error": 'Username already exists'}
        else:
            result = {"error": error_message}

        traceback.print_exc()
        return False, result, 500


async def mark_email_as_verified(db: AsyncSession, user: User) -> None:
    """Mark a user's email as verified"""
    user.is_email_verified = True
    user.verification_code = None
    user.verification_code_expires_at = None
    await db.flush()


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    """Get user by email"""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_by_username(db: AsyncSession, username: str) -> User | None:
    """Get user by hashed username"""
    hashed = hash_username(username)
    result = await db.execute(select(User).where(User.username_hash == hashed))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Get user by ID"""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_all_users(db: AsyncSession) -> list[User]:
    """Return all users ordered by username"""
    result = await db.execute(select(User).order_by(User._username))
    return list(result.scalars().all())


async def get_by_google_id(db: AsyncSession, google_id: str) -> User | None:
    """Get user by Google ID"""
    result = await db.execute(select(User).where(User.google_id == google_id))
    return result.scalar_one_or_none()


async def get_or_create_google_user(
    db: AsyncSession,
    google_id: str,
    username: str,
    email: str
) -> User:
    """Get existing user or create new Google user"""
    user = await get_by_google_id(db, google_id)
    
    if not user:
        try:
            user = await create_google_user(db, username, google_id, email)
        except IntegrityError as e:
            raise ValueError(f"Failed to create user: {str(e)}")
    
    return user


async def create_google_user(
    db: AsyncSession,
    username: str,
    google_id: str,
    email: str
) -> User:
    """Create a new user from Google OAuth"""
    user = User()
    user.username = username
    user.google_id = google_id
    user.password_hash = None
    user.email = email
    user.is_email_verified = True  # Google users are pre-verified
    user.email_verified_at = datetime.utcnow()  # Use naive UTC datetime for asyncpg

    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def save_user_totp_setup(db: AsyncSession, user: User, secret: str) -> None:
    """Saves the generated TOTP secret for a user"""
    user.totp_secret = secret
    await db.flush()


async def enable_user_totp(db: AsyncSession, user: User) -> None:
    """Sets the user's TOTP as enabled"""
    user.totp_enabled = True
    await db.flush()


async def disable_user_totp(db: AsyncSession, user: User) -> None:
    """Disables the user's TOTP and clears the secret"""
    user.totp_enabled = False
    user.totp_secret = None
    await db.flush()

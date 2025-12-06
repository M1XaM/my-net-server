import traceback
from typing import Any
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta, timezone

from app import db
from app.models.user import User
from app.utils.encryption_utils import hash_username
from app.utils.auth_utils import generate_verification_code

def create_user(username: str, password: str, email: str) -> tuple[bool, dict[str, Any], int]:
    new_user = User()
    new_user.username = username
    new_user.set_password(password)
    
    verification_code = generate_verification_code()
    new_user.email = email
    new_user.is_email_verified = False
    new_user.verification_code = verification_code
    new_user.verification_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    result = {}

    try:
        db.session.add(new_user)
        db.session.commit()

        return True, {
            "verification_code": verification_code,
            "user_id": new_user.id
        }, 200

    except IntegrityError as e:
        db.session.rollback()
        error_message = str(e.orig) if hasattr(e, 'orig') else str(e)

        if 'email' in error_message.lower():
            result = {"error": 'Email already exists'}
        elif 'username' in error_message.lower():
            result = {"error": 'Username already exists'}
        else:
            result = {"error": error_message}

        traceback.print_exc()
        return False, result, 500

    finally:
        db.session.close()

def mark_email_as_verified(user: User) -> None:
    user.is_email_verified = True
    user.verification_code = None
    user.verification_code_expires_at = None
    db.session.commit()

def get_by_email(email: str) -> User | None:
    return User.query.filter_by(email=email).first()

def get_by_username(username: str):
    """Get user by hashed username."""
    hashed = hash_username(username)
    return User.query.filter_by(username_hash=hashed).first()

def get_by_id(user_id: int) -> User | None:
    return User.query.get(user_id)

def get_all_users():
    """Return all users ordered by username."""
    return User.query.order_by(User._username).all()

def get_by_google_id(google_id: str) -> User | None:
    return User.query.filter_by(google_id=google_id).first()

def get_or_create_google_user(google_id: str, username: str, email: str):
    """Get existing user or create new Google user"""
    user = get_by_google_id(google_id)
    
    if not user:
        try:
            user = create_google_user(
                username=username,
                google_id=google_id,
                email=email
            )
        except IntegrityError as e:
            # Handle potential duplicate username/email
            raise ValueError(f"Failed to create user: {str(e)}")
    
    return user

def create_google_user(username: str, google_id: str, email: str) -> User:
    user = User(
        username=username,
        google_id=google_id,
        password_hash=None,
        email=email,
        is_email_verified=True,  # Google users are pre-verified
        email_verified_at=datetime.now(timezone.utc),
    )

    db.session.add(user)
    db.session.commit()
    db.session.refresh(user)
    return user

def save_user_totp_setup(user: User, secret: str) -> None:
    """Saves the generated TOTP secret for a user."""
    user.totp_secret = secret
    db.session.commit()

def enable_user_totp(user: User) -> None:
    """Sets the user's TOTP as enabled."""
    user.totp_enabled = True
    db.session.commit()

def disable_user_totp(user: User) -> None:
    """Disables the user's TOTP and clears the secret."""
    user.totp_enabled = False
    user.totp_secret = None
    db.session.commit()
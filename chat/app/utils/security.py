import random
import string
import re
import secrets
import datetime
from typing import Optional

import jwt
import pyotp
import qrcode
import io
import base64

from app.utils.config import settings


# ========== Verification Code ==========

def generate_verification_code() -> str:
    """Generate a 6-digit random verification code"""
    return ''.join(random.choices(string.digits, k=6))


# ========== Email Validation ==========

def is_valid_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# ========== CSRF ==========

def generate_csrf_token() -> str:
    """Generate a CSRF token"""
    return secrets.token_urlsafe(32)


# ========== JWT ==========

def create_access_token(user_id: int) -> str:
    """Create an access token for a user"""
    exp = datetime.datetime.now() + datetime.timedelta(minutes=60)
    payload = {"user_id": user_id, "exp": exp}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id: int) -> str:
    """Create a refresh token for a user"""
    exp = datetime.datetime.now() + datetime.timedelta(days=7)
    payload = {"user_id": user_id, "exp": exp, "type": "refresh"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ========== TOTP ==========

def generate_totp_secret() -> str:
    """Generate a new TOTP secret"""
    return pyotp.random_base32()


def get_totp_uri(username: str, secret: str) -> str:
    """Get TOTP provisioning URI for QR code"""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(
        name=username,
        issuer_name="ChatApp"
    )


def verify_totp(secret: str, token: str) -> bool:
    """Verify a TOTP token"""
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=1)


def generate_qr_code(uri: str) -> str:
    """Generate a QR code as base64 string"""
    img = qrcode.make(uri)
    
    buffered = io.BytesIO()
    img.save(buffered)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return f'data:image/png;base64,{img_str}'


# ========== Sanitization ==========

import bleach

def sanitize_message(content: str | None) -> str:
    """Sanitize message content to prevent XSS"""
    if content is None:
        return ''
    if not isinstance(content, str):
        content = str(content)
    
    return bleach.clean(content, tags=[], attributes={}, strip=True)

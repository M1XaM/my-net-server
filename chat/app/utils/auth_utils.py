import random
import string
import re

def generate_verification_code():
    """Generate a 6-digit random verification code"""
    return ''. join(random.choices(string.digits, k=6))

def is_valid_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def set_refresh_token_cookie(response, refresh_token):
    """Set refresh token in HTTP-only cookie"""
    response.set_cookie(
        'refresh_token',
        refresh_token,
        httponly=True,
        secure=True,
        samesite='Strict',
        path='/auth/token/refresh'  # Optional: restrict cookie path
    )
    return response
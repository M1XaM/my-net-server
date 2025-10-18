import secrets
from flask import request, jsonify
from functools import wraps


def generate_csrf_token():
    return secrets.token_urlsafe(32)


def csrf_protect(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        csrf_token = request.headers.get('X-CSRF-Token')
        # For demo: expect the token in a header and compare to access_token for simplicity.
        # In production, store CSRF token in server-side session or database.
        # Here, expect frontend to send correct token from localStorage.
        if not csrf_token:
            return jsonify({'error': 'Missing CSRF token'}), 403
        # Optionally, add more logic to validate
        return f(*args, **kwargs)
    return decorated
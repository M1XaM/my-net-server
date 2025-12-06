from flask import Blueprint, request, jsonify

from app.services import auth_service
from app.utils.auth_utils import (
    set_refresh_token_cookie,
    is_valid_email
)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip()
    if not username:
        return jsonify({'error': 'Username required'}), 400
    if not password:
        return jsonify({'error': 'Password required'}), 400
    if not email or not is_valid_email(email):
        return jsonify({'error': 'Invalid email format'}), 400

    success, result, status_code = auth_service.register_user(username, password, email)
    if not success:
        return jsonify(result), 409 if 'already' in result.get("error") else 400

    return jsonify({
            'status': 'pending_verification',
            'user_id': result.get("user_id"),
            'email': email,
            'message': 'Verification code sent to your email.  Please verify to complete registration.'
        }), 201

@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    """ Verify email with 6-digit code"""
    data = request.get_json()
    user_id = data.get('user_id')
    verification_code = data.get('verification_code')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
    if not verification_code:
        return jsonify({'error': 'Verification code required'}), 400

    succes, result, status = auth_service.verify_email(user_id, verification_code)
    if not succes:
        return jsonify(result), status

    response = jsonify({
        'id': result["id"],
        'username': result["username"],
        'email': result["email"],
        'access_token': result["access_token"],
        'csrf_token': result["csrf_token"],
        'message': 'Email verified successfully!'
    })
    response.set_cookie('refresh_token', result["refresh_token"], httponly=True, secure=True, samesite='Strict')
    return response, 200

@auth_bp.route('/login', methods=['POST'])
def login():
    """Handle login API request"""
    data = request.get_json()
    username = data.get('username') if data else None
    password = data.get('password') if data else None
    totp_token = data.get('totp_token')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    # Pass the optional totp_token to the service — the service will tell us
    # if 2FA is required or handle invalid 2FA.
    success, result, status_code, refresh_token = auth_service.login_user(username, password, totp_token)
    if not success:
        return jsonify(result), status_code
    
    response = jsonify(result)
    response.set_cookie('refresh_token', refresh_token, httponly=True, secure=True, samesite='Strict')
    return response, status_code

@auth_bp.route('/token/refresh', methods=['POST'])
def refresh_token():
    """Handle token refresh API request"""
    refresh_token = request.cookies.get('refresh_token')
    if not refresh_token:
        return jsonify({'error': 'Refresh token missing'}), 401
    
    success, result, status_code = auth_service.refresh_access_token(refresh_token)
    if not success:
        return jsonify(result), status_code
    
    response = jsonify({
        'access_token': result['tokens']['access_token'],
        'csrf_token': result['tokens']['csrf_token']
    })
    response = set_refresh_token_cookie(response, result['tokens']['refresh_token'])
    return response, status_code

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Handle logout API request"""
    response = jsonify({'message': 'Logged out'})
    response.set_cookie('refresh_token', '', expires=0)
    return response, 200

@auth_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200
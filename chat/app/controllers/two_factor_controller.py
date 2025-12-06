from flask import Blueprint, request, jsonify
from app.utils.jwt_utils import jwt_required
from app.services.email_service import setup_totp, enable_totp, disable_totp 

two_factor_bp = Blueprint('two_factor', __name__)

@two_factor_bp.route('/2fa/setup', methods=['POST'])
@jwt_required
def setup_2fa_route():
    """Generate QR code for user to scan"""
    user_id = request.user_id 
    
    secret, qr_code, error = setup_totp(user_id)

    if error == 'User not found':
        return jsonify({'error': error}), 404

    return jsonify({
        'secret': secret,
        'qr_code': qr_code
    }), 200

@two_factor_bp.route('/2fa/enable', methods=['POST'])
@jwt_required
def enable_2fa_route():
    """Enable 2FA after user confirms it works"""
    data = request.get_json()
    token = data.get('token')
    user_id = request.user_id

    error = enable_totp(user_id, token)

    if error:
        status_code = 400
        if error == 'Token required':
            status_code = 400
        elif error == 'Setup 2FA first':
            status_code = 400
        elif error == 'Invalid token':
            status_code = 400
        
        return jsonify({'error': error}), status_code

    return jsonify({'message': '2FA enabled'}), 200

@two_factor_bp.route('/2fa/disable', methods=['POST'])
@jwt_required
def disable_2fa_route():
    """Disable 2FA"""
    data = request.get_json()
    token = data.get('token')
    user_id = request.user_id

    error = disable_totp(user_id, token)

    if error:
        status_code = 400
        if error == 'Token required':
            status_code = 400
        elif error == 'User not found':
            status_code = 404
        elif error == 'Invalid token':
            status_code = 400
            
        return jsonify({'error': error}), status_code

    return jsonify({'message': '2FA disabled'}), 200
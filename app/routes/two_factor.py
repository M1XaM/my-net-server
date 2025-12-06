from flask import Blueprint, request, jsonify
from app import db
from app.models.user import User
from app.utils.jwt_utils import jwt_required
from app.utils.totp import generate_secret, get_totp_uri, verify_totp, generate_qr_code

two_factor_bp = Blueprint('two_factor', __name__)


@two_factor_bp.route('/2fa/setup', methods=['POST'])
@jwt_required
def setup_2fa():
    """Generate QR code for user to scan"""
    user = User.query.get(request.user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    secret = generate_secret()
    user.totp_secret = secret
    db.session.commit()

    # Create QR code
    uri = get_totp_uri(user.username, secret)
    qr_code = generate_qr_code(uri)

    return jsonify({
        'secret': secret,
        'qr_code': qr_code
    }), 200


@two_factor_bp.route('/2fa/enable', methods=['POST'])
@jwt_required
def enable_2fa():
    """Enable 2FA after user confirms it works"""
    data = request.get_json()
    token = data.get('token')

    if not token:
        return jsonify({'error': 'Token required'}), 400

    user = User.query.get(request.user_id)

    if not user or not user.totp_secret:
        return jsonify({'error': 'Setup 2FA first'}), 400

    # Verify the token works
    if verify_totp(user.totp_secret, token):
        user.totp_enabled = True
        db.session.commit()
        return jsonify({'message': '2FA enabled'}), 200
    else:
        return jsonify({'error': 'Invalid token'}), 400


@two_factor_bp.route('/2fa/disable', methods=['POST'])
@jwt_required
def disable_2fa():
    """Disable 2FA"""
    data = request.get_json()
    token = data.get('token')

    if not token:
        return jsonify({'error': 'Token required'}), 400

    user = User.query.get(request.user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Verify token before disabling
    if verify_totp(user.totp_secret, token):
        user.totp_enabled = False
        user.totp_secret = None
        db.session.commit()
        return jsonify({'message': '2FA disabled'}), 200
    else:
        return jsonify({'error': 'Invalid token'}), 400
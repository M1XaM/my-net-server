from flask import request, redirect, jsonify, Blueprint, current_app, Response

from app.services import google_auth_service

google_auth_bp = Blueprint("google_auth", __name__)

@google_auth_bp.route("/google/url", methods=["GET"])
def get_google_oauth_redirect_uri():
    """Redirect user to Google OAuth URL"""
    try:
        uri = google_auth_service.get_oauth_redirect_url()
        headers = {
            'Location': uri,
            'Content-Length': '0',
            'Cache-Control': 'no-store'
        }
        return Response(status=302, headers=headers)
    except Exception:
        return jsonify({"error": "Failed to generate OAuth URL"}), 500


@google_auth_bp.route("/google/callback", methods=["POST"])
def handle_google_callback():
    """Handle Google OAuth callback"""
    data = request.get_json()
    
    is_valid, code, state, error_message = google_auth_service.validate_callback_data(data)
    if not is_valid:
        return jsonify({"error": error_message}), 400
    
    client_id = current_app.config.get('OAUTH_GOOGLE_CLIENT_ID')
    client_secret = current_app.config.get('OAUTH_GOOGLE_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        return jsonify({"error": "OAuth configuration missing"}), 500
    
    success, result, status_code = google_auth_service.handle_google_callback_sync(
        code=code,
        state=state,
        client_id=client_id,
        client_secret=client_secret
    )
    
    if success:
        response = jsonify({"user": result["user"]})
        response.set_cookie(
            'refresh_token',
            result["tokens"]["refresh_token"],
            httponly=True,
            secure=True,
            samesite='Strict'
        )
        return response, status_code
    else:
        return jsonify(result), status_code
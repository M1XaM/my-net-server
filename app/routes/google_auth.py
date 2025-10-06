from flask import request, redirect, jsonify, Blueprint, current_app
import aiohttp
import asyncio
import jwt

from app import db
from app.models.user import User
from app.utils.state_storage import state_storage
from app.utils.oauth_google import generate_google_oauth_redirect_uri
from app.utils.jwt_utils import create_access_token, create_refresh_token

google_auth_bp = Blueprint("google_auth", __name__)

@google_auth_bp.route("/google/url", methods=["GET"])
def get_google_oauth_redirect_uri():
    uri = generate_google_oauth_redirect_uri()
    return redirect(uri, code=302)

@google_auth_bp.route("/google/callback", methods=["POST"])
def handle_code():
    data = request.get_json()
    code = data.get("code")
    state = data.get("state")

    if state not in state_storage:
        return jsonify({"detail": "Invalid state parameter"}), 400
    else:
        print("Стейт корректный")

    async def fetch_google_data():
        google_token_url = "https://oauth2.googleapis.com/token"

        async with aiohttp.ClientSession() as session:
            # Exchange code for tokens
            async with session.post(
                url=google_token_url,
                data={
                    "client_id": current_app.config['OAUTH_GOOGLE_CLIENT_ID'],
                    "client_secret": current_app.config['OAUTH_GOOGLE_CLIENT_SECRET'],
                    "grant_type": "authorization_code",
                    "redirect_uri": "https://localhost/auth/google",
                    "code": code,
                },
                ssl=False,
            ) as response:
                res = await response.json()
                print(f"{res=}")
                id_token = res["id_token"]
                access_token = res["access_token"]

                user_data = jwt.decode(
                    id_token,
                    algorithms=["RS256"],
                    options={"verify_signature": False},  # WARNING: only for testing
                )
                return {"user": user_data, "access_token": access_token}

    result = asyncio.run(fetch_google_data())
    print("Google fetch result:", result)  # DEBUG

    user_info = result.get("user", {})
    print("User info:", user_info)  # DEBUG

    google_id = user_info.get("sub")
    email = user_info.get("email")
    name = user_info.get("name") or email

    if not google_id:
        return jsonify({"error": "Invalid Google user data"}), 400

    # Lookup or create user
    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User(
            username=name,
            password_hash=None,  # Google login users have no password
            google_id=google_id,
            email=email
        )
        db.session.add(user)
        db.session.commit()

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    
    response = jsonify({
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "google_id": user.google_id,
            "access_token": access_token,
        }
    })
    response.set_cookie('refresh_token', refresh_token, httponly=True, secure=True, samesite='Strict')
    return response

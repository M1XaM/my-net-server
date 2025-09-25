from flask import Blueprint, request, redirect, jsonify
import aiohttp
import asyncio
import jwt
import logging
from .state_storage import state_storage
from .oauth_google import generate_google_oauth_redirect_uri
from .config import settings


router = Blueprint("auth2", __name__, url_prefix="/api/auth")


@router.route("/google/url", methods=["GET"])
def get_google_oauth_redirect_uri():
    logging.info('first')
    uri = generate_google_oauth_redirect_uri()
    logging.info('next')
    logging.info(uri)
    return redirect(uri, code=302)


@router.route("/google/callback", methods=["POST"])
def handle_code():
    from app.models import User
    from app import db
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
                    "client_id": settings.OAUTH_GOOGLE_CLIENT_ID,
                    "client_secret": settings.OAUTH_GOOGLE_CLIENT_SECRET,
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
            # Fetch Google Drive files
    #         async with session.get(
    #             url="https://www.googleapis.com/drive/v3/files",
    #             headers={"Authorization": f"Bearer {access_token}"},
    #             ssl=False,
    #         ) as response:
    #             res = await response.json()
    #             files = [item["name"] for item in res.get("files", [])]
    #
    #     return {"user": user_data, "files": files}
    #
    # result = asyncio.run(fetch_google_data())
    # return jsonify(result)
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
            username_hash=None,  # if you hash usernames, handle here
            password_hash=None,  # Google login users have no password
            google_id=google_id,
            email=email
        )
        db.session.add(user)
        db.session.commit()

    return jsonify({
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "google_id": user.google_id,
        }
    })

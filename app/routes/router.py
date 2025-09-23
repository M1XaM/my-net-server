from flask import Blueprint, request, redirect, jsonify
import aiohttp
import asyncio
import jwt

from .state_storage import state_storage
from .oauth_google import generate_google_oauth_redirect_uri
from .config import settings

router = Blueprint("auth2", __name__, url_prefix="/auth")


@router.route("/google/url", methods=["GET"])
def get_google_oauth_redirect_uri():
    uri = generate_google_oauth_redirect_uri()
    return redirect(uri, code=302)


@router.route("/google/callback", methods=["POST"])
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
                    "client_id": settings.OAUTH_GOOGLE_CLIENT_ID,
                    "client_secret": settings.OAUTH_GOOGLE_CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "redirect_uri": "http://localhost:3000/auth/google",
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

            # Fetch Google Drive files
            async with session.get(
                url="https://www.googleapis.com/drive/v3/files",
                headers={"Authorization": f"Bearer {access_token}"},
                ssl=False,
            ) as response:
                res = await response.json()
                files = [item["name"] for item in res.get("files", [])]

        return {"user": user_data, "files": files}

    result = asyncio.run(fetch_google_data())
    return jsonify(result)

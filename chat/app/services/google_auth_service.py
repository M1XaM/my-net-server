import jwt
import aiohttp
import urllib.parse
import secrets
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import user_repository
from app.utils.security import create_access_token, create_refresh_token
from app.utils.config import settings


# State storage for OAuth
state_storage: set = set()


def generate_google_oauth_redirect_uri() -> str:
    """Generate Google OAuth redirect URI"""
    random_state = secrets.token_urlsafe(16)
    state_storage.add(random_state)

    query_params = {
        "client_id": settings.OAUTH_GOOGLE_CLIENT_ID,
        "redirect_uri": "https://localhost/auth/google",
        "response_type": "code",
        "scope": " ".join([
            "openid",
            "profile",
            "email",
        ]),
        "access_type": "offline",
        "state": random_state,
        "prompt": "select_account consent"
    }
    
    query_string = urllib.parse.urlencode(query_params, quote_via=urllib.parse.quote)
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    return f"{base_url}?{query_string}"


def get_oauth_redirect_url() -> str:
    """Generate Google OAuth redirect URI"""
    return generate_google_oauth_redirect_uri()


def validate_state(state: str) -> Tuple[bool, Optional[str]]:
    """Validate the OAuth state parameter against stored states"""
    if state not in state_storage:
        return False, "Invalid or expired OAuth state. Please start the authentication process again"
    return True, None


async def exchange_code_for_token(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str = "https://localhost/auth/google"
) -> Dict[str, Any]:
    """Exchange authorization code for Google tokens"""
    google_token_url = "https://oauth2.googleapis.com/token"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=google_token_url,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
                ssl=False,
            ) as response:
                if response.status != 200:
                    error_data = await response.json()
                    error_description = error_data.get('error_description', error_data.get('error', 'Unknown error'))
                    raise Exception(f"Google authentication failed: {error_description}")
                
                return await response.json()
    except aiohttp.ClientError as e:
        raise Exception(f"Unable to connect to Google authentication servers: {str(e)}")


def decode_google_token(id_token: str) -> Dict[str, Any]:
    """Decode Google ID token (without signature verification for testing)"""
    return jwt.decode(
        id_token,
        algorithms=["RS256"],
        options={"verify_signature": False}
    )


def extract_user_info(decoded_token: Dict[str, Any]) -> Tuple[str, str, str]:
    """Extract user information from decoded Google token"""
    google_id = decoded_token.get("sub")
    email = decoded_token.get("email")
    name = decoded_token.get("name") or email or f"user_{google_id}"
    
    if not google_id:
        raise ValueError("Google user ID is missing from the authentication response")
    
    if not email:
        raise ValueError("Email address is required but was not provided by Google. Please ensure your Google account has a verified email")
    
    return google_id, email, name


def create_auth_response(user) -> Dict[str, Any]:
    """Create authentication response with tokens"""
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    
    return {
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "google_id": user.google_id,
            "access_token": access_token,
        },
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    }


async def handle_google_callback(
    db: AsyncSession,
    code: str,
    state: str,
    client_id: str,
    client_secret: str
) -> Tuple[bool, Dict[str, Any], int]:
    """
    Handle Google OAuth callback
    Returns: (success, data, status_code)
    """
    is_valid, error_message = validate_state(state)
    if not is_valid:
        return False, {"error": error_message}, 400
    
    # Remove used state to prevent replay attacks
    state_storage.discard(state)
    
    try:
        token_response = await exchange_code_for_token(
            code=code,
            client_id=client_id,
            client_secret=client_secret
        )
        
        id_token = token_response.get("id_token")
        if not id_token:
            return False, {"error": "Google did not return an identity token. Please try again"}, 400
            
        decoded_token = decode_google_token(id_token)
        
        google_id, email, name = extract_user_info(decoded_token)
        
        user = await user_repository.get_or_create_google_user(db, google_id, name, email)
        
        auth_data = create_auth_response(user)
        
        return True, auth_data, 200
        
    except ValueError as e:
        return False, {"error": str(e)}, 400
    except Exception as e:
        error_msg = str(e)
        if "authentication failed" in error_msg.lower():
            return False, {"error": error_msg}, 400
        print(f"Google OAuth error: {error_msg}")
        return False, {"error": "Google authentication failed. Please try again"}, 500


def validate_callback_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """Extract and return callback data (validation done in router)"""
    code = data.get("code", "").strip()
    state = data.get("state", "").strip()
    
    return True, code, state, None

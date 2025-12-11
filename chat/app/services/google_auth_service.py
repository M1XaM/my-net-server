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
    """Validate the OAuth state parameter"""
    if state not in state_storage:
        return False, "Invalid state parameter"
    return True, None


async def exchange_code_for_token(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str = "https://localhost/auth/google"
) -> Dict[str, Any]:
    """Exchange authorization code for Google tokens"""
    google_token_url = "https://oauth2.googleapis.com/token"
    
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
                raise Exception(f"Google token exchange failed: {error_data}")
            
            return await response.json()


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
        raise ValueError("Invalid Google user data: missing sub field")
    
    return google_id, email, name


def create_auth_response(user) -> Dict[str, Any]:
    """Create authentication response with tokens"""
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    
    return {
        "user": {
            "id": user.id,
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
        return False, {"detail": error_message}, 400
    
    try:
        token_response = await exchange_code_for_token(
            code=code,
            client_id=client_id,
            client_secret=client_secret
        )
        
        id_token = token_response.get("id_token")
        if not id_token:
            return False, {"error": "No ID token in response"}, 400
            
        decoded_token = decode_google_token(id_token)
        
        google_id, email, name = extract_user_info(decoded_token)
        
        user = await user_repository.get_or_create_google_user(db, google_id, name, email)
        
        auth_data = create_auth_response(user)
        
        return True, auth_data, 200
        
    except ValueError as e:
        return False, {"error": str(e)}, 400
    except Exception as e:
        print(f"Google OAuth error: {str(e)}")
        return False, {"error": "Authentication failed"}, 500


def validate_callback_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """Validate callback request data"""
    code = data.get("code")
    state = data.get("state")
    
    if not code:
        return False, None, None, "Missing authorization code"
    if not state:
        return False, None, None, "Missing state parameter"
    
    return True, code, state, None

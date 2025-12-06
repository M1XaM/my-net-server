import jwt
import aiohttp
import asyncio
from typing import Dict, Any, Tuple, Optional

from app.repositories.user_repository import get_or_create_google_user
from app.utils.oauth_google_utils import state_storage, generate_google_oauth_redirect_uri
from app.utils.jwt_utils import create_access_token, create_refresh_token

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
            
            res = await response.json()
            return res


def decode_google_token(id_token: str) -> Dict[str, Any]:
    """Decode Google ID token (without signature verification for testing)"""
    # WARNING: In production, you should verify the signature
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
    code: str,
    state: str,
    client_id: str,
    client_secret: str
) -> Tuple[bool, Dict[str, Any], int]:
    """
    Handle Google OAuth callback
    Returns: (success, data, status_code)
    """
    # Validate state
    is_valid, error_message = validate_state(state)
    if not is_valid:
        return False, {"detail": error_message}, 400
    
    try:
        # Exchange code for tokens
        token_response = await exchange_code_for_token(
            code=code,
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Decode ID token
        id_token = token_response.get("id_token")
        if not id_token:
            return False, {"error": "No ID token in response"}, 400
            
        decoded_token = decode_google_token(id_token)
        
        # Extract user info
        google_id, email, name = extract_user_info(decoded_token)
        
        # Get or create user
        user = get_or_create_google_user(google_id, name, email)
        
        # Create auth response
        auth_data = create_auth_response(user)
        
        return True, auth_data, 200
        
    except ValueError as e:
        # Business logic errors
        return False, {"error": str(e)}, 400
    except Exception as e:
        # Unexpected errors
        print(f"Google OAuth error: {str(e)}")
        return False, {"error": "Authentication failed"}, 500


# Synchronous wrapper for async function
def handle_google_callback_sync(
    code: str,
    state: str,
    client_id: str,
    client_secret: str
) -> Tuple[bool, Dict[str, Any], int]:
    """
    Synchronous wrapper for async callback handler
    """
    try:
        return asyncio.run(
            handle_google_callback(code, state, client_id, client_secret)
        )
    except RuntimeError as e:
        # Handle case where event loop is already running
        if "asyncio.run() cannot be called from a running event loop" in str(e):
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(
                handle_google_callback(code, state, client_id, client_secret)
            )
        raise


# Additional helper functions
def validate_callback_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """Validate callback request data"""
    code = data.get("code")
    state = data.get("state")
    
    if not code:
        return False, None, None, "Missing authorization code"
    if not state:
        return False, None, None, "Missing state parameter"
    
    return True, code, state, None
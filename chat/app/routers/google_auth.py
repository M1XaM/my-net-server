from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.utils.database import get_db
from app.utils.config import settings
from app.services import google_auth_service

router = APIRouter(prefix="/auth", tags=["google_auth"])


class GoogleCallbackRequest(BaseModel):
    code: str
    state: str


@router.get("/google/url")
async def get_google_oauth_redirect_uri():
    """Redirect user to Google OAuth URL"""
    try:
        uri = google_auth_service.get_oauth_redirect_url()
        if not uri:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate Google login URL. Please try again"
            )
        return RedirectResponse(
            url=uri,
            status_code=302,
            headers={
                'Cache-Control': 'no-store'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail="Unable to initiate Google authentication. Please try again later"
        )


@router.post("/google/callback")
async def handle_google_callback(
    request: GoogleCallbackRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Handle Google OAuth callback"""
    # Validate code
    if not request.code:
        raise HTTPException(
            status_code=400, 
            detail="Authorization code from Google is missing. Please try logging in again"
        )
    
    code = request.code.strip()
    if not code:
        raise HTTPException(
            status_code=400, 
            detail="Authorization code cannot be empty"
        )
    
    # Validate state
    if not request.state:
        raise HTTPException(
            status_code=400, 
            detail="OAuth security state is missing. Please try logging in again"
        )
    
    state = request.state.strip()
    if not state:
        raise HTTPException(
            status_code=400, 
            detail="OAuth security state cannot be empty"
        )
    
    is_valid, code_val, state_val, error_message = google_auth_service.validate_callback_data(
        {"code": code, "state": state}
    )
    
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_message)
    
    client_id = settings.OAUTH_GOOGLE_CLIENT_ID
    client_secret = settings.OAUTH_GOOGLE_CLIENT_SECRET
    
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500, 
            detail="Google authentication is not properly configured. Please contact support"
        )
    
    success, result, status_code = await google_auth_service.handle_google_callback(
        db,
        code=code_val,
        state=state_val,
        client_id=client_id,
        client_secret=client_secret
    )
    
    if success:
        response.set_cookie(
            key='refresh_token',
            value=result["tokens"]["refresh_token"],
            httponly=True,
            secure=True,
            samesite='strict'
        )
        return {"user": result["user"]}
    else:
        raise HTTPException(status_code=status_code, detail=result.get("error"))

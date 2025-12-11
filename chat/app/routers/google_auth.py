from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.utils.database import get_db
from app.utils.config import settings
from app.services import google_auth_service

# Note: After migration, change to:
# from app.services import google_auth_service

router = APIRouter(prefix="/auth", tags=["google_auth"])


class GoogleCallbackRequest(BaseModel):
    code: str
    state: str


@router.get("/google/url")
async def get_google_oauth_redirect_uri():
    """Redirect user to Google OAuth URL"""
    try:
        uri = google_auth_service.get_oauth_redirect_url()
        return RedirectResponse(
            url=uri,
            status_code=302,
            headers={
                'Cache-Control': 'no-store'
            }
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to generate OAuth URL")


@router.post("/google/callback")
async def handle_google_callback(
    request: GoogleCallbackRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Handle Google OAuth callback"""
    is_valid, code, state, error_message = google_auth_service.validate_callback_data(
        {"code": request.code, "state": request.state}
    )
    
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_message)
    
    client_id = settings.OAUTH_GOOGLE_CLIENT_ID
    client_secret = settings.OAUTH_GOOGLE_CLIENT_SECRET
    
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="OAuth configuration missing")
    
    success, result, status_code = await google_auth_service.handle_google_callback(
        db,
        code=code,
        state=state,
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

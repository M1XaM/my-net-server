from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.utils.database import get_db
from app.utils.dependencies import CurrentUserId
from app.services.email_service import setup_totp, enable_totp, disable_totp

router = APIRouter(tags=["two_factor"])


class TwoFactorTokenRequest(BaseModel):
    token: Optional[str] = None


@router.post("/2fa/setup")
async def setup_2fa_route(
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db)
):
    """Generate QR code for user to scan"""
    secret, qr_code, error = await setup_totp(db, user_id)

    if error:
        if 'not found' in error.lower():
            raise HTTPException(status_code=404, detail=error)
        raise HTTPException(status_code=400, detail=error)

    return {
        'secret': secret,
        'qr_code': qr_code,
        'message': 'Scan this QR code with your authenticator app (e.g., Google Authenticator, Authy)'
    }


@router.post("/2fa/enable")
async def enable_2fa_route(
    request: TwoFactorTokenRequest,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db)
):
    """Enable 2FA after user confirms it works"""
    token = request.token.strip() if request.token else None
    
    if not token:
        raise HTTPException(
            status_code=400, 
            detail="A 6-digit code from your authenticator app is required to enable 2FA"
        )
    
    if len(token) != 6 or not token.isdigit():
        raise HTTPException(
            status_code=400, 
            detail="The verification code must be exactly 6 digits"
        )
    
    error = await enable_totp(db, user_id, token)

    if error:
        status_code = 400
        if 'not found' in error.lower():
            status_code = 404
        elif 'setup' in error.lower():
            status_code = 400
        
        raise HTTPException(status_code=status_code, detail=error)

    return {
        'message': '2FA has been successfully enabled on your account. You will need your authenticator app to log in'
    }


@router.post("/2fa/disable")
async def disable_2fa_route(
    request: TwoFactorTokenRequest,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db)
):
    """Disable 2FA"""
    token = request.token.strip() if request.token else None
    
    if not token:
        raise HTTPException(
            status_code=400, 
            detail="A 6-digit code from your authenticator app is required to disable 2FA"
        )
    
    if len(token) != 6 or not token.isdigit():
        raise HTTPException(
            status_code=400, 
            detail="The verification code must be exactly 6 digits"
        )
    
    error = await disable_totp(db, user_id, token)

    if error:
        status_code = 400
        if 'not found' in error.lower():
            status_code = 404
        elif 'not enabled' in error.lower() or 'missing' in error.lower():
            status_code = 400
            
        raise HTTPException(status_code=status_code, detail=error)

    return {
        'message': '2FA has been successfully disabled on your account'
    }

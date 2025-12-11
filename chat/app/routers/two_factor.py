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

    if error == 'User not found':
        raise HTTPException(status_code=404, detail=error)

    return {
        'secret': secret,
        'qr_code': qr_code
    }


@router.post("/2fa/enable")
async def enable_2fa_route(
    request: TwoFactorTokenRequest,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db)
):
    """Enable 2FA after user confirms it works"""
    error = await enable_totp(db, user_id, request.token)

    if error:
        status_code = 400
        if error == 'Token required':
            status_code = 400
        elif error == 'Setup 2FA first':
            status_code = 400
        elif error == 'Invalid token':
            status_code = 400
        
        raise HTTPException(status_code=status_code, detail=error)

    return {'message': '2FA enabled'}


@router.post("/2fa/disable")
async def disable_2fa_route(
    request: TwoFactorTokenRequest,
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db)
):
    """Disable 2FA"""
    error = await disable_totp(db, user_id, request.token)

    if error:
        status_code = 400
        if error == 'Token required':
            status_code = 400
        elif error == 'User not found':
            status_code = 404
        elif error == 'Invalid token':
            status_code = 400
            
        raise HTTPException(status_code=status_code, detail=error)

    return {'message': '2FA disabled'}

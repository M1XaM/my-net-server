from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.utils.database import get_db
from app.services import auth_service

from app.utils.security import is_valid_email

router = APIRouter(tags=["auth"])

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    user_id: int
    verification_code: str


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_token: Optional[str] = None


@router.post("/register")
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    username = request.username.strip()
    password = request.password.strip()
    email = request.email.strip()
    
    if not username:
        raise HTTPException(status_code=400, detail="Username required")
    if not password:
        raise HTTPException(status_code=400, detail="Password required")
    if not email or not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    success, result, status_code = await auth_service.register_user(db, username, password, email)
    
    if not success:
        status = 409 if 'already' in result.get("error", "") else 400
        raise HTTPException(status_code=status, detail=result.get("error"))

    return {
        'status': 'pending_verification',
        'user_id': result.get("user_id"),
        'email': email,
        'message': 'Verification code sent to your email. Please verify to complete registration.'
    }


@router.post("/verify-email")
async def verify_email(
    request: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify email with 6-digit code"""
    if not request.user_id:
        raise HTTPException(status_code=400, detail="User ID required")
    if not request.verification_code:
        raise HTTPException(status_code=400, detail="Verification code required")

    success, result, status = await auth_service.verify_email(
        db, request.user_id, request.verification_code
    )
    
    if not success:
        raise HTTPException(status_code=status, detail=result.get("error"))

    response = Response(status_code=200)
    response.set_cookie(
        key='refresh_token',
        value=result["refresh_token"],
        httponly=True,
        secure=True,
        samesite='strict'
    )
    
    # Return JSON with cookie set
    return {
        'id': result["id"],
        'username': result["username"],
        'email': result["email"],
        'access_token': result["access_token"],
        'csrf_token': result["csrf_token"],
        'message': 'Email verified successfully!'
    }


@router.post("/login")
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Handle login API request"""
    if not request.username or not request.password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    success, result, status_code, refresh_token = await auth_service.login_user(
        db, request.username, request.password, request.totp_token
    )
    
    if not success:
        if status_code == 200:  # 2FA required case
            return result
        raise HTTPException(status_code=status_code, detail=result.get("error"))
    
    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite='strict'
    )
    
    return result


@router.post("/token/refresh")
async def refresh_token(
    request: Request,
    response: Response
):
    """Handle token refresh API request"""
    refresh_token = request.cookies.get('refresh_token')
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    
    success, result, status_code = await auth_service.refresh_access_token(refresh_token)
    
    if not success:
        raise HTTPException(status_code=status_code, detail=result.get("error"))
    
    response.set_cookie(
        key='refresh_token',
        value=result['tokens']['refresh_token'],
        httponly=True,
        secure=True,
        samesite='strict'
    )
    
    return {
        'access_token': result['tokens']['access_token'],
        'csrf_token': result['tokens']['csrf_token']
    }


@router.post("/logout")
async def logout(response: Response):
    """Handle logout API request"""
    response.delete_cookie('refresh_token')
    return {'message': 'Logged out'}


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {'status': 'healthy'}

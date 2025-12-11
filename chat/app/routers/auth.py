from uuid import UUID
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
    user_id: str  # UUID as string
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
    # Input validation
    username = request.username.strip() if request.username else ""
    password = request.password.strip() if request.password else ""
    email = request.email.strip().lower() if request.email else ""
    
    # Username validation
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters long")
    if len(username) > 50:
        raise HTTPException(status_code=400, detail="Username must not exceed 50 characters")
    if not username.replace('_', '').replace('-', '').isalnum():
        raise HTTPException(status_code=400, detail="Username can only contain letters, numbers, underscores, and hyphens")
    
    # Password validation
    if not password:
        raise HTTPException(status_code=400, detail="Password is required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
    if len(password) > 128:
        raise HTTPException(status_code=400, detail="Password must not exceed 128 characters")
    
    # Email validation
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    if len(email) > 255:
        raise HTTPException(status_code=400, detail="Email must not exceed 255 characters")
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Please provide a valid email address (e.g., user@example.com)")

    success, result, status_code = await auth_service.register_user(db, username, password, email)
    
    if not success:
        error_msg = result.get("error", "Registration failed")
        raise HTTPException(status_code=status_code, detail=error_msg)

    return {
        'status': 'pending_verification',
        'user_id': result.get("user_id"),
        'email': email,
        'message': 'A verification code has been sent to your email. Please enter it to complete registration.'
    }


@router.post("/verify-email")
async def verify_email(
    request: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify email with 6-digit code"""
    if not request.user_id:
        raise HTTPException(status_code=400, detail="User ID is required to verify your email")
    
    try:
        user_uuid = UUID(request.user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="User ID must be a valid UUID")
    
    if not request.verification_code:
        raise HTTPException(status_code=400, detail="Verification code is required")
    
    code = request.verification_code.strip()
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=400, detail="Verification code must be exactly 6 digits")

    success, result, status = await auth_service.verify_email(
        db, user_uuid, code
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
        'message': 'Your email has been verified successfully! You are now logged in.'
    }


@router.post("/login")
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Handle login API request"""
    username = request.username.strip() if request.username else ""
    password = request.password.strip() if request.password else ""
    
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if not password:
        raise HTTPException(status_code=400, detail="Password is required")
    
    totp_token = None
    if request.totp_token:
        totp_token = request.totp_token.strip()
        if totp_token and (len(totp_token) != 6 or not totp_token.isdigit()):
            raise HTTPException(status_code=400, detail="2FA code must be exactly 6 digits")

    success, result, status_code, refresh_token = await auth_service.login_user(
        db, username, password, totp_token
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
        raise HTTPException(
            status_code=401, 
            detail="Your session has expired. Please log in again"
        )
    
    refresh_token = refresh_token.strip()
    if not refresh_token:
        raise HTTPException(
            status_code=401, 
            detail="Invalid session token. Please log in again"
        )
    
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

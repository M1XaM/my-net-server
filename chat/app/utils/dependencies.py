from typing import Annotated
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from app.utils.security import decode_token

logging.basicConfig(level=logging.INFO)
security = HTTPBearer()


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> int:
    """
    Dependency for extracting and validating JWT token from Authorization header.
    Returns the user_id from the token.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is required. Please log in to access this resource",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token cannot be empty. Please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired or the token is invalid. Please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get('user_id')
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is malformed. Please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not isinstance(user_id, int) or user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identity in token. Please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logging.info(f'JWT passed for user_id={user_id}')
    return user_id


# Type alias for dependency injection
CurrentUserId = Annotated[int, Depends(get_current_user_id)]

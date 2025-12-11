from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_db
from app.utils.dependencies import CurrentUserId
from app.services import user_service

router = APIRouter(tags=["users"])


@router.get("/users")
async def get_users(
    user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all users (requires authentication)
    
    Returns:
        JSON array of users with id and username
    """
    if not user_id or user_id <= 0:
        raise HTTPException(
            status_code=400, 
            detail="Valid authentication is required to fetch users"
        )
    
    try:
        users = await user_service.get_all_users_formatted(db)
        return users
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail="Unable to fetch users at this time. Please try again later"
        )

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.utils.database import get_db
from app.utils.dependencies import CurrentUserId
from app.services import message_service

router = APIRouter(tags=["messages"])


class RunCodeRequest(BaseModel):
    code: str


@router.get("/messages/{user_id}/{other_id}")
async def get_messages(
    user_id: int,
    other_id: int,
    current_user_id: CurrentUserId,
    db: AsyncSession = Depends(get_db)
):
    """Get messages between two users"""
    success, messages, status_code = await message_service.fetch_conversation_messages(
        db, user_id, other_id
    )
    
    if not success:
        raise HTTPException(status_code=status_code, detail=messages.get("error"))
    
    return messages


@router.post("/messages/run-code")
async def run_code(
    request: RunCodeRequest,
    current_user_id: CurrentUserId
):
    """Run code via the runner service"""
    if not request.code:
        raise HTTPException(status_code=400, detail="Invalid request, missing code")
    
    success, result, status_code = await message_service.execute_code_via_runner(request.code)
    
    if not success:
        raise HTTPException(status_code=status_code, detail=result.get("error"))
    
    return result

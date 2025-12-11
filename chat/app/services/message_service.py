import httpx
from typing import Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import message_repository


async def fetch_conversation_messages(
    db: AsyncSession,
    user_id: int,
    other_id: int
) -> Tuple[bool, List[Dict[str, Any]] | Dict, int]:
    """
    Fetch conversation messages between two users
    
    Args:
        db: Database session
        user_id: ID of the current user
        other_id: ID of the other user in conversation
        
    Returns:
        Tuple of (success, messages, status_code)
    """
    success, result, _ = await message_repository.get_conversation(db, user_id, other_id)
    if not success:
        return False, {"error": result}, 500
    
    return True, [
        {
            'id': m.id,
            'sender_id': m.sender_id,
            'receiver_id': m.receiver_id,
            'content': m.content,
            'timestamp': m.timestamp.isoformat() if m.timestamp else None
        }
        for m in result
    ], 200


async def execute_code_via_runner(code: str, timeout: int = 10) -> Tuple[bool, dict, int]:
    """Execute code via the runner service asynchronously"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                'http://runner:8080/run-code',
                json={'code': code},
                timeout=timeout
            )
            
            try:
                body = resp.json()
            except ValueError:
                body = resp.text
            
            return True, body, resp.status_code
            
    except httpx.TimeoutException:
        return False, {'error': 'executor timed out'}, 504
    except httpx.ConnectError:
        return False, {'error': 'cannot connect to executor'}, 502
    except httpx.RequestError as e:
        return False, {'error': str(e)}, 502
    except Exception as e:
        return False, {'error': f'executor error: {str(e)}'}, 500

import httpx
from typing import Dict, Any, List, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import message_repository


async def fetch_conversation_messages(
    db: AsyncSession,
    user_id: UUID,
    other_id: UUID
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
    try:
        success, result, _ = await message_repository.get_conversation(db, user_id, other_id)
        if not success:
            error_msg = result if isinstance(result, str) else result.get("error", "Failed to fetch messages")
            return False, {"error": f"Unable to retrieve conversation: {error_msg}"}, 500
        
        return True, [
            {
                'id': str(m.id),
                'sender_id': str(m.sender_id),
                'receiver_id': str(m.receiver_id),
                'content': m.content,
                'timestamp': m.timestamp.isoformat() if m.timestamp else None
            }
            for m in result
        ], 200
    except Exception as e:
        return False, {"error": f"An unexpected error occurred while fetching messages: {str(e)}"}, 500


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
                body = {'output': resp.text} if resp.text else {'error': 'Empty response from code runner'}
            
            if resp.status_code >= 400:
                error_msg = body.get('error', 'Code execution failed') if isinstance(body, dict) else 'Code execution failed'
                return False, {'error': error_msg}, resp.status_code
            
            return True, body, resp.status_code
            
    except httpx.TimeoutException:
        return False, {'error': f'Code execution timed out after {timeout} seconds. Your code may be taking too long or stuck in an infinite loop'}, 504
    except httpx.ConnectError:
        return False, {'error': 'Unable to connect to the code execution service. Please try again later'}, 502
    except httpx.RequestError as e:
        return False, {'error': f'Failed to communicate with code execution service: {str(e)}'}, 502
    except Exception as e:
        return False, {'error': f'An unexpected error occurred during code execution: {str(e)}'}, 500

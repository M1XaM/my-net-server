import httpx
import ssl
import logging
from typing import Dict, Any, List, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import message_repository
from app.utils.config import settings
from app.utils.kafka_client import kafka_manager

logger = logging.getLogger(__name__)


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


async def execute_code_via_runner(code: str, timeout: int = 10, user_id: str = "anonymous") -> Tuple[bool, dict, int]:
    """
    Execute code via Kafka message queue to the runner service.
    Falls back to HTTP if Kafka is unavailable.
    """
    # Try Kafka first
    try:
        if kafka_manager._initialized or settings.KAFKA_BOOTSTRAP_SERVERS:
            result = await kafka_manager.execute_code(code, user_id=user_id, timeout=timeout)
            
            if "error" in result and "status_code" in result:
                return False, {"error": result["error"]}, result["status_code"]
            
            return True, result, 200
            
    except Exception as e:
        logger.warning(f"Kafka execution failed, falling back to HTTP: {e}")
    
    # Fallback to HTTP
    return await _execute_code_via_http(code, timeout)


async def _execute_code_via_http(code: str, timeout: int = 10) -> Tuple[bool, dict, int]:
    """Execute code via HTTP to the runner service (fallback method)"""
    try:
        # Configure SSL context if using HTTPS
        http_client_kwargs = {}
        if settings.RUNNER_URL.startswith("https://") and settings.RUNNER_CA_CERT:
            ssl_context = ssl.create_default_context()
            ssl_context.load_verify_locations(settings.RUNNER_CA_CERT)
            http_client_kwargs["verify"] = ssl_context
        
        async with httpx.AsyncClient(**http_client_kwargs) as client:
            resp = await client.post(
                f'{settings.RUNNER_URL}/run-code',
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

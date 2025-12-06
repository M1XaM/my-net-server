import requests
from sqlalchemy.orm.query import Query
from typing import Dict, Any, List, Tuple, Optional

from app.repositories import message_repository

def fetch_conversation_messages(user_id: int, other_id: int) -> List[Dict[str, Any]]:
    """
    Fetch conversation messages between two users
    
    Args:
        user_id: ID of the current user
        other_id: ID of the other user in conversation
        
    Returns:
        List of message dictionaries
    """
    success, result, _ = message_repository.get_conversation(user_id, other_id)
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

def execute_code_via_runner(code: str, timeout: int = 10) -> Tuple[bool, dict, int]:
    try:
        resp = requests.post(
            'http://runner:8080/run-code',
            json={'code': code},
            timeout=timeout
        )
        
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
        
        return True, body, resp.status_code
        
    except requests.exceptions.Timeout:
        return False, {'error': 'executor timed out'}, 504
    except requests.exceptions.ConnectionError:
        return False, {'error': 'cannot connect to executor'}, 502
    except requests.exceptions.RequestException as e:
        return False, {'error': str(e)}, 502
    except Exception as e:
        return False, {'error': f'executor error: {str(e)}'}, 500
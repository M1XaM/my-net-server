from typing import List, Dict, Any
from app.repositories import user_repository


def get_all_users_formatted() -> List[Dict[str, Any]]:
    """
    Get all users and format them for API response
    
    Returns:
        List of user dictionaries with id and username
    """
    users = user_repository.get_all_users()
    
    return [
        {
            'id': user.id,
            'username': user.username
        }
        for user in users
    ]
from app import db
from app.models.message import Message
from app.models.user import User

def get_conversation(user_id: int, other_id: int):
    return True, Message.query.filter(
        ((Message.sender_id == user_id) & (Message.receiver_id == other_id)) |
        ((Message.sender_id == other_id) & (Message.receiver_id == user_id))
    ).order_by(Message.timestamp.asc()).all(), 200

def save_message(sender_id: int, receiver_id: int, content: str) -> Message:
    sender = User.query.get(sender_id)
    if not sender:
        return False, {"error": f"Sender with ID {sender_id} does not exist"}, 400
    
    receiver = User.query.get(receiver_id)
    if not receiver:
        return False, {"error": f"Sender with ID {receiver_id} does not exist"}, 400
    
    message = Message(sender_id=sender_id, receiver_id=receiver_id, content=content)
    db.session.add(message)
    db.session.commit()
    db.session.refresh(message)
    return True, message, 200

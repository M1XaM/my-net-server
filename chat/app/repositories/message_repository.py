from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.user import User


async def get_conversation(
    db: AsyncSession,
    user_id: int,
    other_id: int
) -> tuple[bool, list[Message] | dict, int]:
    """Get all messages between two users"""
    result = await db.execute(
        select(Message)
        .where(
            or_(
                and_(Message.sender_id == user_id, Message.receiver_id == other_id),
                and_(Message.sender_id == other_id, Message.receiver_id == user_id)
            )
        )
        .order_by(Message.timestamp.asc())
    )
    return True, list(result.scalars().all()), 200


async def save_message(
    db: AsyncSession,
    sender_id: int,
    receiver_id: int,
    content: str
) -> tuple[bool, Message | dict, int]:
    """Save a new message"""
    # Verify sender exists
    sender_result = await db.execute(select(User).where(User.id == sender_id))
    sender = sender_result.scalar_one_or_none()
    if not sender:
        return False, {"error": f"Sender with ID {sender_id} does not exist"}, 400
    
    # Verify receiver exists
    receiver_result = await db.execute(select(User).where(User.id == receiver_id))
    receiver = receiver_result.scalar_one_or_none()
    if not receiver:
        return False, {"error": f"Receiver with ID {receiver_id} does not exist"}, 400
    
    message = Message(sender_id=sender_id, receiver_id=receiver_id)
    message.content = content
    
    db.add(message)
    await db.flush()
    await db.refresh(message)
    return True, message, 200

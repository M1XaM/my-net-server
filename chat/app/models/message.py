from datetime import datetime
from sqlalchemy import Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.utils.encryption import encrypt, decrypt

class Message(Base):
    __tablename__ = 'messages'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    receiver_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    _content: Mapped[str] = mapped_column("content", Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    @property
    def content(self) -> str:
        return decrypt(self._content)
    
    @content.setter
    def content(self, value: str) -> None:
        self._content = encrypt(value)

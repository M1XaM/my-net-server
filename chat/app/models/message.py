from datetime import datetime
from uuid import UUID
from sqlalchemy import Text, DateTime, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.utils.encryption import encrypt, decrypt

class Message(Base):
    __tablename__ = 'messages'
    
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    sender_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    receiver_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    _content: Mapped[str] = mapped_column("content", Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    @property
    def content(self) -> str:
        return decrypt(self._content)
    
    @content.setter
    def content(self, value: str) -> None:
        self._content = encrypt(value)

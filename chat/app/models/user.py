from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import generate_password_hash, check_password_hash

from app.models.base import Base
from app.utils.encryption import encrypt, decrypt, hash_username


class User(Base):
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    _username: Mapped[str] = mapped_column("username", Text, unique=True, nullable=False)
    username_hash: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # Email verification fields
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    verification_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Two-Factor Authentication fields
    totp_secret: Mapped[str | None] = mapped_column(String(32), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    @property
    def username(self) -> str:
        return decrypt(self._username)
    
    @username.setter
    def username(self, value: str) -> None:
        self._username = encrypt(value)
        self.username_hash = hash_username(value)
    
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

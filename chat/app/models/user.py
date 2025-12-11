from datetime import datetime
from uuid import UUID
from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import generate_password_hash, check_password_hash

from app.models.base import Base
from app.utils.encryption import encrypt, decrypt, hash_username, hash_email, hash_google_id


class User(Base):
    __tablename__ = 'users'
    
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    
    # Username: encrypted for storage, hashed for lookup
    _username: Mapped[str] = mapped_column("username", Text, unique=True, nullable=False)
    username_hash: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    
    # Password: hashed (one-way)
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    
    # Google ID: encrypted for storage, hashed for lookup
    _google_id: Mapped[str | None] = mapped_column("google_id", Text, unique=True, nullable=True)
    google_id_hash: Mapped[str | None] = mapped_column(String(256), unique=True, nullable=True)
    
    # Email: encrypted for storage, hashed for lookup
    _email: Mapped[str | None] = mapped_column("email", Text, unique=True, nullable=True)
    email_hash: Mapped[str | None] = mapped_column(String(256), unique=True, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # Email verification fields (verification_code encrypted)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    _verification_code: Mapped[str | None] = mapped_column("verification_code", Text, nullable=True)
    verification_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Two-Factor Authentication fields (totp_secret encrypted)
    _totp_secret: Mapped[str | None] = mapped_column("totp_secret", Text, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Username property (encrypted + hashed)
    @property
    def username(self) -> str:
        return decrypt(self._username)
    
    @username.setter
    def username(self, value: str) -> None:
        self._username = encrypt(value)
        self.username_hash = hash_username(value)
    
    # Email property (encrypted + hashed, case-insensitive)
    @property
    def email(self) -> str | None:
        return decrypt(self._email) if self._email else None
    
    @email.setter
    def email(self, value: str | None) -> None:
        if value is None:
            self._email = None
            self.email_hash = None
        else:
            lowered = value.lower()
            self._email = encrypt(lowered)
            self.email_hash = hash_email(lowered)
    
    # Google ID property (encrypted + hashed)
    @property
    def google_id(self) -> str | None:
        return decrypt(self._google_id) if self._google_id else None
    
    @google_id.setter
    def google_id(self, value: str | None) -> None:
        if value is None:
            self._google_id = None
            self.google_id_hash = None
        else:
            self._google_id = encrypt(value)
            self.google_id_hash = hash_google_id(value)
    
    # Verification code property (encrypted only, no lookup needed)
    @property
    def verification_code(self) -> str | None:
        return decrypt(self._verification_code) if self._verification_code else None
    
    @verification_code.setter
    def verification_code(self, value: str | None) -> None:
        self._verification_code = encrypt(value) if value else None
    
    # TOTP secret property (encrypted only, no lookup needed)
    @property
    def totp_secret(self) -> str | None:
        return decrypt(self._totp_secret) if self._totp_secret else None
    
    @totp_secret.setter
    def totp_secret(self, value: str | None) -> None:
        self._totp_secret = encrypt(value) if value else None
    
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

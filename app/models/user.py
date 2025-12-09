from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from app.utils.encrypt import encrypt, decrypt, hash_username


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    _username = db.Column("username", db.Text, unique=True, nullable=False)
    username_hash = db.Column(db.String(256), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # ✅ Email verification with 6-digit code
    email_verified_at = db.Column(db.DateTime, nullable=True)
    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_code = db.Column(db.String(6), nullable=True)
    verification_code_expires_at = db.Column(db.DateTime, nullable=True)

    # ✅ Two-factor authentication
    totp_secret = db.Column(db.String(32), nullable=True)
    totp_enabled = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def username(self):
        return decrypt(self._username)

    @username.setter
    def username(self, value):
        self._username = encrypt(value)
        self.username_hash = hash_username(value)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
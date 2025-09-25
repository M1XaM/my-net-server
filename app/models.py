from app import db
from app.utils import encrypt, decrypt, hash_username
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    _username = db.Column("username", db.Text, unique=True, nullable=False)
    username_hash = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

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

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    _content = db.Column("content", db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    @property
    def content(self):
        return decrypt(self._content)

    @content.setter
    def content(self, value):
        self._content = encrypt(value)

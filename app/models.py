from app import db
from app.utils import encrypt, decrypt

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    _username = db.Column("username", db.Text, unique=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    @property
    def username(self):
        return decrypt(self._username)

    @username.setter
    def username(self, value):
        self._username = encrypt(value)

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

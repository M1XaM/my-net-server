from app import db
from app.utils.encryption_utils import encrypt, decrypt

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

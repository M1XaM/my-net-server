import os

class Config:
    DB_USER = os.getenv('DB_USER', 'chat_user')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'chat_password')
    DB_HOST = os.getenv('DB_HOST', 'db')
    DB_NAME = os.getenv('DB_NAME', 'chatdb')
    SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}?sslmode=require'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
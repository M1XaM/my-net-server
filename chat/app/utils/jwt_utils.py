from flask import request, jsonify, current_app
import jwt
import datetime
from functools import wraps
import logging

logging.basicConfig(level=logging.INFO)

def create_access_token(user_id):
    exp = datetime.datetime.now() + datetime.timedelta(minutes=60)
    payload = {"user_id": user_id, "exp": exp}
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")

def create_refresh_token(user_id):
    exp = datetime.datetime.now() + datetime.timedelta(days=7)
    payload = {"user_id": user_id, "exp": exp, "type": "refresh"}
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")

def decode_token(token):
    try:
        payload = jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing access token'}), 401
        token = auth_header.split(' ')[1]
        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        request.user_id = payload['user_id']
        logging.info('JWT passed, alll is working')
        logging.info(f'JWT passed for user_id={request.user_id}')

        return f(*args, **kwargs)
    return decorated
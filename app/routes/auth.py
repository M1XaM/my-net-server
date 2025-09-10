from flask import Blueprint, request, jsonify
from app import db
from app.models import User
from sqlalchemy.exc import IntegrityError

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    if not username:
        return jsonify({'error': 'Username required'}), 400

    new_user = User(username=username)
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'id': new_user.id, 'username': new_user.username}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Username exists'}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    if not username:
        return jsonify({'error': 'Username required'}), 400

    user = User.query.filter_by(username=username).first()
    if user:
        return jsonify({'id': user.id, 'username': user.username}), 200
    else:
        return jsonify({'error': 'User not found'}), 404
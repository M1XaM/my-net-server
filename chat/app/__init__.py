import threading
from flask import Flask, g
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

from app.utils.db_utils import DbInitialization
from app.utils.config import Config

db = SQLAlchemy()
socketio = SocketIO()
lock = threading.Lock()

db_helper = DbInitialization(db, socketio, lock)

def create_app():
    app = Flask(__name__)

    app.config.from_object('app.utils.config.Config')
    origins_list = [o.strip() for o in Config.CORS_ALLOWED_ORIGINS.split(',') if o.strip()] + ["https://localhost:5173"]
    if origins_list:
        CORS(app,supports_credentials=True, resources={r"/api/*": {"origins": origins_list}})
    else:
        CORS(app,supports_credentials=True,  resources={r"/api/*": {"origins": []}})

    socketio.init_app(app, cors_allowed_origins=(origins_list if origins_list else None), path="/api/socket.io")

    db_helper.setup_database_connection(app)

    from app.controllers.auth_controller import auth_bp
    from app.controllers.user_controller import users_bp
    from app.controllers.message_controller import messages_bp
    from app.controllers.google_auth_controller import google_auth_bp
    from app.controllers.two_factor_controller import two_factor_bp

    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(users_bp, url_prefix='/api')
    app.register_blueprint(messages_bp, url_prefix='/api')
    app.register_blueprint(google_auth_bp, url_prefix="/api/auth")
    app.register_blueprint(two_factor_bp, url_prefix="/api")

    from app.controllers.chat_controller import register_socket_events
    register_socket_events(socketio)

    return app
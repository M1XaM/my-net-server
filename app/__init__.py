from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

db = SQLAlchemy()
socketio = SocketIO()

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Config
    app.config.from_object('config.Config')
    
    # Initialize extensions
    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.users import users_bp
    from app.routes.messages import messages_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(users_bp, url_prefix='/api')
    app.register_blueprint(messages_bp, url_prefix='/api')
    
    # Import and register socket events
    from app.sockets.events import register_socket_events
    register_socket_events(socketio)
    
    return app
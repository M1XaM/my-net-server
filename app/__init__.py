from flask import Flask, g
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import time
import threading
from app.utils.db_utils import Db_initialization
from app.utils import config

db = SQLAlchemy()
socketio = SocketIO()
lock = threading.Lock()

db_uris = [
    config.Config.make_uri(config.Config.DB_HOST),
    config.Config.make_uri(config.Config.DB_HOST_STANDBY),
]

# Create the DB helper instance
db_helper = Db_initialization(db, socketio, lock, db_uris)


def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config.from_object('app.utils.config.Config')

    # Aggressive connection settings
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 5,
        'max_overflow': 10,
        'pool_timeout': 5,
        'connect_args': {
            'connect_timeout': 5,
            'keepalives': 1,
            'keepalives_idle': 5,
            'keepalives_interval': 2,
            'keepalives_count': 2,
        }
    }

    # Wait for any available DB
    available_db = db_helper.wait_for_any_db(max_retries=30, retry_delay=2)

    if not available_db:
        raise RuntimeError("⛔ Neither MAIN nor STANDBY DB available after 60 seconds!")

    app.config["SQLALCHEMY_DATABASE_URI"] = available_db
    db_helper.current_db = available_db

    print(f"🎯 Initial DB set to: {db_helper.current_db}")

    if available_db == db_uris[0]:
        print("✅ Connected to MAIN DB")
    else:
        print("✅ Connected to STANDBY DB")

    db.init_app(app)

    # Setup connection error handling
    db_helper.handle_db_connection_errors()

    # Import models before creating tables
    from app.models.user import User
    from app.models.message import Message

    retries = 5
    while retries > 0:
        try:
            with app.app_context():
                db.create_all()
                print("✅ Tables created successfully.")
            break
        except Exception as e:
            retries -= 1
            if retries == 0:
                raise RuntimeError(f"❌ Failed to create tables: {e}")
            print(f"⏳ Failed to create tables, retrying... ({e})")
            time.sleep(2)

    # Start monitoring thread
    print("🚀 Starting DB monitor thread...")
    threading.Thread(target=db_helper.monitor_db, args=(app,), daemon=True).start()

    socketio.init_app(app, cors_allowed_origins="*", path="/api/socket.io")

    from app.routes.auth import auth_bp
    from app.routes.users import users_bp
    from app.routes.messages import messages_bp
    from app.routes.google_auth import google_auth_bp

    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(users_bp, url_prefix='/api')
    app.register_blueprint(messages_bp, url_prefix='/api')
    app.register_blueprint(google_auth_bp, url_prefix="/api/auth")

    from app.sockets.events import register_socket_events
    register_socket_events(socketio)

    return app
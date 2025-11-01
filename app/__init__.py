from flask import Flask, g
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import time
import threading
from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError, DBAPIError, DisconnectionError

from app.utils import config

db = SQLAlchemy()
socketio = SocketIO()
lock = threading.Lock()

db_uris = [
    config.Config.make_uri(config.Config.DB_HOST),
    config.Config.make_uri(config.Config.DB_HOST_STANDBY),
]

current_db = None


def check_db_available(uri, timeout=2):
    """Check if a DB is available."""
    try:
        engine = create_engine(uri, connect_args={"connect_timeout": timeout})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception as e:
        print(f"❌ DB check failed for {uri}: {e}")
        return False


def wait_for_any_db(max_retries=30, retry_delay=2):
    """Wait for either main or standby DB to become available."""
    print("⏳ Waiting for database to become available...")

    for attempt in range(max_retries):
        if check_db_available(db_uris[0]):
            print(f"✅ Main DB available (attempt {attempt + 1})")
            return db_uris[0]

        if check_db_available(db_uris[1]):
            print(f"✅ Standby DB available (attempt {attempt + 1})")
            return db_uris[1]

        print(f"⏳ No DB available yet (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
        time.sleep(retry_delay)

    return None


def monitor_db(app):
    """Monitor DB health and perform failover"""
    global current_db

    print("🔍 DB Monitor thread started")

    while True:
        time.sleep(1)  # Check every second

        try:
            print(f"🔍 Checking current DB: {current_db}")

            # Check current DB health
            current_alive = check_db_available(current_db, timeout=2)

            print(f"🔍 Current DB ({current_db}) alive: {current_alive}")

            if not current_alive:
                # Current DB is down, switch to the other one
                other_db = db_uris[1] if current_db == db_uris[0] else db_uris[0]

                print(f"⚠️⚠️⚠️ CURRENT DB DOWN! Current: {current_db}, Trying: {other_db}")

                other_alive = check_db_available(other_db, timeout=2)
                print(f"🔍 Other DB ({other_db}) alive: {other_alive}")

                if other_alive:
                    print(f"✅✅✅ Switching to {other_db}...")
                    with app.app_context():
                        success = switch_db(app, other_db)
                        if success:
                            print(f"✅✅✅ SUCCESSFULLY SWITCHED TO {other_db}")
                        else:
                            print(f"❌❌❌ FAILED TO SWITCH TO {other_db}")
                else:
                    print(f"❌ Other DB ({other_db}) is also down!")

            # If on standby, check if main is back
            elif current_db == db_uris[1]:
                main_alive = check_db_available(db_uris[0], timeout=2)
                if main_alive:
                    print("✅ Main DB back online — switching to MAIN.")
                    with app.app_context():
                        switch_db(app, db_uris[0])

        except Exception as e:
            print(f"❌ Monitor error: {e}")
            import traceback
            traceback.print_exc()


def switch_db(app, uri):
    """Safely switch the DB URI at runtime."""
    global current_db

    with lock:
        if current_db == uri:
            print(f"ℹ️ Already using {uri}, no switch needed")
            return True

        print(f"🔄🔄🔄 SWITCHING from {current_db} to {uri}...")

        try:
            print("🔄 Step 1: Removing session...")
            db.session.remove()
        except Exception as e:
            print(f"⚠️ Session remove error (non-fatal): {e}")

        try:
            print("🔄 Step 2: Disposing old engine...")
            if hasattr(db, '_engine') and db._engine:
                db._engine.dispose()
        except Exception as e:
            print(f"⚠️ Engine dispose error (non-fatal): {e}")

        # Update config
        print(f"🔄 Step 3: Updating Flask config to {uri}...")
        app.config["SQLALCHEMY_DATABASE_URI"] = uri

        try:
            print("🔄 Step 4: Creating new engine manually...")
            # Create a new engine using SQLAlchemy directly
            from sqlalchemy import create_engine as sa_create_engine

            engine_options = app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {})
            new_engine = sa_create_engine(uri, **engine_options)

            print("🔄 Step 5: Testing new connection...")
            with new_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                print(f"🔄 Test query result: {result.fetchone()}")

            # Replace the engine in Flask-SQLAlchemy
            print("🔄 Step 6: Replacing engine in Flask-SQLAlchemy...")
            db._engine = new_engine
            if hasattr(db, 'engines'):
                db.engines[None] = new_engine

            old_db = current_db
            current_db = uri
            print(f"✅✅✅ Successfully switched from {old_db} to {uri}")
            return True
        except Exception as e:
            print(f"❌❌❌ Failed to switch to {uri}: {e}")
            import traceback
            traceback.print_exc()
            return False


def handle_db_connection_errors():
    """Pessimistic disconnection handling"""
    from sqlalchemy import event
    from sqlalchemy.pool import Pool

    @event.listens_for(Pool, "checkout")
    def check_connection(dbapi_conn, connection_record, connection_proxy):
        """Verify connection is alive before using it"""
        try:
            cursor = dbapi_conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
        except Exception:
            print("⚠️ Dead connection detected in pool, invalidating...")
            raise DisconnectionError()


def create_app():
    global current_db

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

    available_db = wait_for_any_db(max_retries=30, retry_delay=2)

    if not available_db:
        raise RuntimeError("⛔ Neither MAIN nor STANDBY DB available after 60 seconds!")

    app.config["SQLALCHEMY_DATABASE_URI"] = available_db
    current_db = available_db

    print(f"🎯 Initial DB set to: {current_db}")

    if available_db == db_uris[0]:
        print("✅ Connected to MAIN DB")
    else:
        print("✅ Connected to STANDBY DB")

    db.init_app(app)

    # Setup connection error handling
    handle_db_connection_errors()

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
    threading.Thread(target=monitor_db, args=(app,), daemon=True).start()

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
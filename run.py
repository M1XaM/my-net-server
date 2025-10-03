from app import create_app, socketio
from app.utils.connect_db import init_db

app = create_app()

if __name__ == '__main__':
    init_db(app)
    socketio.run(app, host='0.0.0.0', port=5000)
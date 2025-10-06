import time
from sqlalchemy.exc import OperationalError

from app import db

def init_db(app):
    retries = 10
    while retries > 0:
        try:
            with app.app_context():
                db.create_all()
            print("✅ Database initialized successfully!")
            break
        except OperationalError as e:
            print(f"⏳ DB not ready ({e}), retrying in 5s...")
            retries -= 1
            time.sleep(5)
    else:
        raise Exception("❌ Could not connect to DB")
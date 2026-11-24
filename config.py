import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "database", "gym.db")
from datetime import timedelta
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-later")
PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
LOG_DIR = os.path.join(BASE_DIR, "logs")
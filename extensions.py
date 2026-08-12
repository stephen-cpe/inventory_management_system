# extensions.py
# Flask extensions instantiated here, detached from the application instance.
# The app factory (app.create_app) calls init_app() on each of these so that
# multiple app instances (e.g. one per test) can share the same extension
# objects without cross-talk.
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

# Default login view; the app factory can override this if needed.
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
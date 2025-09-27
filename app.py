# -*- coding: utf-8 -*-
# Standard Library Imports
import os
import logging
from sqlalchemy import text
from logging.handlers import RotatingFileHandler
from flask import Flask
from extensions import db  # Import db from extensions
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from forms import ChangePasswordForm


# --- App Configuration ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-insecure-fallback-key')
db_url = os.environ.get('DATABASE_URL', 'sqlite:///inventory.db')
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {'check_same_thread': False}
}

# Initialize db
db.init_app(app)

csrf = CSRFProtect(app)


# --- Other Extensions ---
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# --- Logging Setup ---
log_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
log_handler = RotatingFileHandler('app.log', maxBytes=1024000, backupCount=10, encoding='utf-8')
log_handler.setFormatter(log_formatter)
log_level_str = os.environ.get('LOG_LEVEL', 'DEBUG').upper()
log_level = getattr(logging, log_level_str, logging.DEBUG)
log_handler.setLevel(log_level)
if not app.debug:
    app.logger.addHandler(log_handler)
app.logger.setLevel(log_level)
app.logger.info('Inventory App Starting Up...')
app.logger.info(f'Database URI: {db_url}')
if app.secret_key == 'dev-insecure-fallback-key':
    app.logger.warning('SECURITY WARNING: Using default SECRET_KEY. Set the SECRET_KEY environment variable for production!')

# --- Import Models and Routes ---
from models import *
from routes import *

# --- Jinja Filters ---
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M'):
    from datetime import date
    if value is None:
        return ''
    try:
        if isinstance(value, datetime):
            return value.strftime(format)
        elif isinstance(value, date):
            return value.strftime(format.split(' ')[0])
        else:
            try:
                if isinstance(value, str):
                    parsed_date = datetime.fromisoformat(value)
                    return parsed_date.strftime(format)
            except ValueError:
                pass
            return str(value)
    except Exception as e:
        app.logger.error(f"Error formatting date {value}: {str(e)}", exc_info=True)
        return str(value)

# --- CLI Commands ---
@app.cli.command("create-admin")
def create_admin():
    default_username = os.environ.get('ADMIN_USERNAME', 'admin')
    default_password = os.environ.get('ADMIN_PASSWORD', None)
    username = input(f"Enter admin username [{default_username}]: ").strip() or default_username
    if not username:
        print("Username cannot be empty.")
        return
    if User.query.filter_by(username=username).first():
        print(f"User '{username}' already exists.")
        return
    password = ""
    confirm_password = "-"
    while password != confirm_password:
        if default_password:
            use_env_pw = input("Use password from ADMIN_PASSWORD environment variable? (Y/n): ").strip().lower()
            if use_env_pw != 'n':
                password = default_password
                confirm_password = password
                print("Using password from environment variable.")
                break
        import getpass
        password = getpass.getpass("Enter admin password: ")
        if not password:
            print("Password cannot be empty.")
            password = ""
            confirm_password = "-"
            continue
        confirm_password = getpass.getpass("Confirm admin password: ")
        if password != confirm_password:
            print("Passwords do not match. Please try again.")
    admin_user = User(username=username, is_admin=True)
    admin_user.set_password(password)
    db.session.add(admin_user)
    try:
        db.session.commit()
        print(f"Admin user '{username}' created successfully.")
        app.logger.info(f"Admin user '{username}' created via CLI.")
    except Exception as e:
        db.session.rollback()
        print(f"Error creating admin user: {e}")
        app.logger.error(f"Error creating admin user '{username}' via CLI: {e}", exc_info=True)

@app.cli.command("reset-login-attempts")
def reset_login_attempts():
    """Resets failed login attempts for a specific user or all users."""
    username = input("Enter username to reset (leave blank to reset all): ").strip()
    
    if username:
        count = LoginAttempt.query.filter_by(username=username, successful=False).delete()
        print(f"Reset {count} failed login attempts for user '{username}'.")
        app.logger.info(f"Reset login attempts for user '{username}' via CLI.")
    else:
        count = LoginAttempt.query.filter_by(successful=False).delete()
        print(f"Reset {count} failed login attempts for all users.")
        app.logger.info("Reset all login attempts via CLI.")
    
    db.session.commit()

# --- Error Handling ---
@app.errorhandler(404)
def page_not_found(e):
    app.logger.warning(f"404 Not Found: {request.url} ({e})")
    return render_template('404.html'), 404

@app.errorhandler(403)
def forbidden_access(e):
    app.logger.warning(f"403 Forbidden: {request.url} by user '{current_user.username}' ({e})")
    return render_template('403.html'), 403

@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(f"500 Internal Server Error: {request.url} ({e})", exc_info=True)
    try:
        db.session.rollback()
        app.logger.info("Rolled back database session after 500 error.")
    except Exception as rollback_e:
        app.logger.error(f"Error during rollback after 500 error: {rollback_e}", exc_info=True)
    return render_template('500.html'), 500

@app.errorhandler(405)
def method_not_allowed(e):
    app.logger.warning(f"405 Method Not Allowed: {request.url}")
    return render_template('405.html'), 405

@app.errorhandler(400)
def bad_request(e):
    if 'CSRF' in str(e):
        flash('Invalid CSRF token. Please try again.', 'danger')
        return redirect(request.url)
    return render_template('400.html'), 400

# --- Main Execution ---
if __name__ == '__main__':
    app_debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    app.run(debug=app_debug, host=host, port=port)
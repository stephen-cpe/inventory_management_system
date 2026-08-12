# -*- coding: utf-8 -*-
# app.py
# Application factory for the Church Inventory System.
#
# The Flask app is created via create_app() so that tests can build an
# isolated instance with an in-memory SQLite database, while production
# uses the same factory with MySQL configuration from the environment.
#
# Extensions live in extensions.py and are init_app()'d here. Route
# handlers live in the blueprints package (blueprints.auth, .inventory, .csv)
# and are registered onto the app instance.
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, date

from flask import Flask, request, render_template, redirect, flash, url_for
from dotenv import load_dotenv

from extensions import db, migrate, login_manager, csrf
from models import User, LoginAttempt


def create_app(testing: bool = False) -> Flask:
    """Create and configure a Flask application instance.

    Args:
        testing: When True, use an in-memory SQLite database and disable
            CSRF so unit/functional tests can POST forms without tokens.
    """
    load_dotenv()

    app = Flask(__name__)

    # --- Configuration ---
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-insecure-fallback-key')
    if testing:
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
    else:
        db_url = os.environ.get(
            'DATABASE_URL',
            'mysql+pymysql://mysql_username:YourSuperSecretDBPassword@localhost/inventory_management_db'
        )
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    if not testing:
        # MySQL connection pool tuning. These options are not valid for
        # SQLite's default StaticPool/SingletonPool used in tests.
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 5,
            'pool_recycle': 280,
            'pool_pre_ping': True,
            'pool_timeout': 10,
            'max_overflow': 2,
        }

    # --- Initialize extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # --- Logging Setup ---
    if not testing:
        log_formatter = logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )
        log_level_str = os.environ.get('LOG_LEVEL', 'DEBUG').upper()
        log_level = getattr(logging, log_level_str, logging.DEBUG)

        # Prefer a rotating file handler for long-running deployments
        # (e.g. PythonAnywhere, EC2). On PaaS free tiers (Render, Railway,
        # Fly.io) the working directory is often read-only, so we fall back
        # to a stdout stream handler that the platform's own log drain
        # captures. Setting LOG_TO_STDOUT=1 forces the stream handler.
        log_to_stdout = os.environ.get('LOG_TO_STDOUT', '').lower() in ('1', 'true', 'yes')
        if not log_to_stdout:
            try:
                log_handler = RotatingFileHandler(
                    'app.log', maxBytes=1024000, backupCount=10, encoding='utf-8'
                )
                log_handler.setFormatter(log_formatter)
                log_handler.setLevel(log_level)
            except (OSError, PermissionError):
                log_to_stdout = True
        if log_to_stdout:
            log_handler = logging.StreamHandler()
            log_handler.setFormatter(log_formatter)
            log_handler.setLevel(log_level)

        if not app.debug:
            app.logger.addHandler(log_handler)
        app.logger.setLevel(log_level)
        app.logger.info('Inventory App Starting Up...')
        app.logger.info(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
        app.logger.info(f"Logging to: {'stdout' if log_to_stdout else 'app.log'}")
        if app.secret_key == 'dev-insecure-fallback-key':
            app.logger.warning(
                'SECURITY WARNING: Using default SECRET_KEY. '
                'Set the SECRET_KEY environment variable for production!'
            )

    # --- User loader ---
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --- Register blueprints ---
    from blueprints import auth_bp, inventory_bp, csv_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(csv_bp)

    # --- Jinja Filters ---
    @app.template_filter('datetimeformat')
    def datetimeformat(value, format='%Y-%m-%d %H:%M'):
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
    register_cli(app)

    # --- Enhanced Caching for Static Assets ---
    @app.after_request
    def add_header(response):
        if request.path.startswith('/static/'):
            response.cache_control.public = True
            response.cache_control.max_age = 86400
            if '?' in request.full_path:
                response.cache_control.max_age = 31536000  # versioned assets
        return response

    # --- Error Handling ---
    register_error_handlers(app)

    # --- Main Execution ---
    if __name__ == '__main__' and not testing:
        app_debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
        port = int(os.environ.get('PORT', 5000))
        host = os.environ.get('HOST', '0.0.0.0')
        app.run(debug=app_debug, host=host, port=port)

    return app


def register_cli(app: Flask) -> None:
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

    @app.cli.command("create-tables")
    def create_tables():
        """Create all tables defined by the SQLAlchemy models.

        Intended for PaaS deployments (Render, Railway, Fly.io) where the
        MySQL init_db.sql script cannot be run directly. On platforms with
        Alembic migrations enabled, prefer `flask db upgrade` instead.
        """
        db.create_all()
        print("All tables created.")
        app.logger.info("Tables created via create-tables CLI.")


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def page_not_found(e):
        app.logger.warning(f"404 Not Found: {request.url} ({e})")
        return render_template('404.html'), 404

    @app.errorhandler(403)
    def forbidden_access(e):
        username = current_user.username if current_user.is_authenticated else 'anonymous'
        app.logger.warning(f"403 Forbidden: {request.url} by user '{username}' ({e})")
        return render_template('403.html'), 403

    @app.errorhandler(500)
    def internal_server_error(e):
        app.logger.error(f"500 Internal Server Error: {request.url} ({e})", exc_info=True)
        try:
            db.session.rollback()
            db.session.remove()
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


# Module-level app for backwards compatibility with `flask run`,
# WSGI servers that import `from app import app`, and `flask` CLI.
app = create_app()
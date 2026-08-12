# wsgi.py
# Production WSGI entry point for gunicorn and other WSGI servers.
#
# This module creates the database tables on import (idempotent —
# db.create_all() skips tables that already exist) so that PaaS
# deployments don't need a separate pre-deploy/release command,
# which may be a paid feature (e.g. Render free tier).
#
# It can also auto-provision a default admin user on first boot when the
# AUTO_CREATE_ADMIN env var is set to a truthy value. This is intended
# for free-tier PaaS deployments (Render, Railway, Fly.io) that offer
# no shell/SSH access to run `flask create-admin`. The default password
# should be changed immediately via the Change Password page after
# first login.
#
# Usage:
#   gunicorn wsgi:app --workers 1 --threads 2 --timeout 60
#
# For PythonAnywhere / EC2 where init_db.sql is used, you can still
# import from app.py directly: `from app import app as application`
# — tables are managed via init_db.sql there, and db.create_all()
# here would be a harmless no-op anyway.
import os

from app import create_app
from extensions import db

app = create_app()

with app.app_context():
    db.create_all()

    # --- Auto-provision a default admin user (optional, opt-in) ---
    # Triggered when AUTO_CREATE_ADMIN is set to a truthy value
    # (e.g. "1", "true", "yes"). This is a convenience for free-tier
    # PaaS deployments that offer no shell/SSH access. The default
    # password is insecure by design — change it immediately after
    # first login via the Change Password page.
    if os.environ.get('AUTO_CREATE_ADMIN', '').lower() in ('1', 'true', 'yes'):
        from models import User
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        existing = User.query.filter_by(username=admin_username).first()
        if not existing:
            admin_password = os.environ.get('ADMIN_PASSWORD', 'Ch@ng3meA$@P')
            admin = User(username=admin_username, is_admin=True)
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            app.logger.info(
                f"Auto-created default admin user '{admin_username}'. "
                f"CHANGE THE DEFAULT PASSWORD IMMEDIATELY via the Change Password page."
            )
        else:
            app.logger.info(
                f"Auto-create admin skipped: user '{admin_username}' already exists."
            )
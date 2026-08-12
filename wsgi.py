# wsgi.py
# Production WSGI entry point for gunicorn and other WSGI servers.
#
# This module creates the database tables on import (idempotent —
# db.create_all() skips tables that already exist) so that PaaS
# deployments don't need a separate pre-deploy/release command,
# which may be a paid feature (e.g. Render free tier).
#
# Usage:
#   gunicorn wsgi:app --workers 1 --threads 2 --timeout 60
#
# For PythonAnywhere / EC2 where init_db.sql is used, you can still
# import from app.py directly: `from app import app as application`
# — tables are managed via init_db.sql there, and db.create_all()
# here would be a harmless no-op anyway.
from app import create_app
from extensions import db

app = create_app()

with app.app_context():
    db.create_all()
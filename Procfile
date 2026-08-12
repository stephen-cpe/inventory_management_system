# Procfile
# Used by Render and other PaaS that auto-detect a Procfile.
# - web: production WSGI server (gunicorn) serving the app
# - release: one-shot command run on each deploy to ensure tables exist;
#   idempotent because db.create_all() skips existing tables.
web: gunicorn "app:create_app()" --workers 1 --threads 2 --timeout 60
release: python -c "from app import create_app; from extensions import db; app=create_app(); app.app_context().__enter__(); db.create_all(); print('Tables OK')"
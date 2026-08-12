# Procfile
# Used by Render and other PaaS that auto-detect a Procfile.
#
# - web: production WSGI server (gunicorn) serving the app via wsgi.py,
#   which creates the database tables on import (idempotent —
#   db.create_all() skips existing tables). This avoids needing a
#   separate pre-deploy/release command, which is a paid feature on
#   some PaaS free tiers (e.g. Render).
web: gunicorn wsgi:app --workers 1 --threads 2 --timeout 60
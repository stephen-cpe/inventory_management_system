# blueprints/__init__.py
# Blueprint package. Each module registers a Flask Blueprint with a name
# that mirrors the previous endpoint names so url_for(...) calls in
# templates and routes keep working unchanged:
#
#   auth.*       -> auth.login, auth.logout, auth.register, auth.change_password
#   inventory.*  -> inventory.index, inventory.add_item, inventory.edit_items, ...
#   csv.*        -> csv.import_csv, csv.export_csv, csv.download_template
#
# The factory in app.py imports these and calls register_app() on each.
from .auth import auth as auth_bp
from .inventory import inventory as inventory_bp
from .csv import csv_bp as csv_bp

__all__ = ["auth_bp", "inventory_bp", "csv_bp"]
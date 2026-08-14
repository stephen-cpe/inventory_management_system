# Deployment Guide for PythonAnywhere (Developer Plan)

> **⚠️ Plan requirement:** This guide uses **MySQL**, which on PythonAnywhere requires a paid plan. The cheapest plan that includes MySQL access is the **Developer plan ($10/month)**. The free plan does not include MySQL, and external databases (e.g. Supabase Postgres) are also blocked on the free plan because outbound TCP to non-HTTP ports is restricted. If you want a free deployment, use the [Fly.io guide](Fly.io-guide.md), [Render guide](Render-guide.md), or [Railway guide](Railway-guide.md) instead.

This guide assumes you are starting with a fresh PythonAnywhere account on a plan that includes MySQL.

---

## 1. Create the Web App

1. From your **PythonAnywhere Dashboard/Home Page**:
   * Navigate to **Web → Add a new web app**.
   * Select **Manual configuration**.
   * Choose **Python 3.13**.
   * This will generate your default site:

     ```
     <username>.pythonanywhere.com
     ```

---

## 2. Set Up a Virtual Environment

1. Open a new **Bash console** from the Dashboard.
2. Create a virtual environment (it will be stored in `~/.virtualenvs/`):

```bash
mkvirtualenv myvirtualenv --python=/usr/bin/python3.13
```

> **Note:** `mkvirtualenv` is a PythonAnywhere helper command that creates a virtual environment inside `~/.virtualenvs/` and automatically configures it for use with `workon`.

The resulting path will be:
```
/home/<username>/.virtualenvs/myvirtualenv
```

---

## 3. Clone the Repository

In the Bash console, run:

```bash
cd ~
git clone https://github.com/stephen-cpe/inventory_management_system.git
cd inventory_management_system
```

---

## 4. Install Dependencies

Ensure your virtual environment is active (it should be by default after creation):

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. Initialize the Database

1. Go to the **Databases** tab and open a **MySQL console**.
2. Paste the full contents of `init_db.sql` into the console and execute.
   - This creates the initial database schema and tables.

> **Important**: This step must be completed before running Flask migrations, as it sets up the required database structure.

---

## 6. Configure Web App Settings

Go to the **Web** tab and set the following:

* **Source code:**
  ```
  /home/<username>/inventory_management_system
  ```

* **Virtualenv path:**
  ```
  /home/<username>/.virtualenvs/myvirtualenv
  ```

* **WSGI configuration file:**
  ```
  /var/www/<username>_pythonanywhere_com_wsgi.py
  ```

---

## 7. Edit the WSGI File

Click to edit your WSGI file and replace its contents with:

```python
import os
import sys

# Set environment variables
os.environ['SECRET_KEY'] = 'YourSuperSecretVeryLongKey'
os.environ['DATABASE_URL'] = 'mysql+pymysql://<mysql_username>:YourSuperSecretDBPassword@<username>.mysql.pythonanywhere-services.com/<mysql_username>$default'

# Add project directory to Python path
project_home = '/home/<username>/inventory_management_system'   # <-- REPLACE <username>!
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Import the Flask application
from app import app as application
```

> **⚠️ Replace placeholders before saving:**
> * `<username>` → your PythonAnywhere username. **This is the one that breaks the import if missed** — `project_home` must point at the real clone path.
> * `<mysql_username>` → your MySQL database username (usually the same as your PythonAnywhere username).
> * `YourSuperSecretDBPassword` → your MySQL database password.
> * `YourSuperSecretVeryLongKey` → a long random string (e.g. `python -c "import secrets;print(secrets.token_hex(32))"`).

---

## 8. Run Migrations and Create Admin User

Back in the Bash console, ensure environment variables are set for the session:

```bash
export DATABASE_URL='mysql+pymysql://<mysql_username>:YourSuperSecretDBPassword@<username>.mysql.pythonanywhere-services.com/<mysql_username>$default'
export SECRET_KEY='YourSuperSecretVeryLongKey'

cd ~/inventory_management_system

flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# Create the admin user
flask create-admin
```

> You’ll be prompted to enter a username and password for the admin account.

---

## 9. Reload the Web App

* Go to the **Web** tab.
* Click **Reload** to apply changes.
* Visit your site:

  ```
  https://<username>.pythonanywhere.com
  ```

---

## 10. Verification Steps

1. Log in using your admin credentials (`/login`).
2. If issues occur:
   * Check the **Error log** in the Web tab.
   * Review `app.log` in the project directory (logging is handled by a `RotatingFileHandler` configured in `app.py`).

---

## 11. Troubleshooting

| Symptom | Likely Cause / Fix |
|---------|-------------------|
| `ModuleNotFoundError: No module named 'app'` | The `project_home` path in the WSGI file still has the literal `<username>` placeholder. Replace it with your actual PythonAnywhere username. |
| `pymysql.err.OperationalError: ... Network is unreachable` | You are on the free plan, which blocks MySQL connections. Upgrade to the Developer plan ($10/month) or use a different platform. |
| `relation "..." does not exist` on first request | Tables weren't created. Re-run `init_db.sql` in the MySQL console (step 5), then run `flask db upgrade`. |
| `flask.cli.NoAppException` | Ensure `app.py` exports `create_app` (it does in the current repo). Run `python -c "from app import create_app"` locally to verify. |
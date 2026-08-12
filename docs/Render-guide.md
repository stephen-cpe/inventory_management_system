# Deployment Guide for Render (Free Tier)

This guide deploys the Church Inventory System to Render's free tier using a free Render Postgres database. No credit card is required to start.

## Disclaimer

* This project is intended for **educational, testing, and experimentation purposes only**.
* **Not suitable for production use**.
* Use at your own risk. No warranties, guarantees, or support are provided.

> **Important Render free-tier limits to know up front:**
> * **Free Postgres databases expire 30 days after creation.** After expiry you have a 14-day grace window to upgrade to a paid plan or the database (and all its data) is deleted. Set a calendar reminder.
> * Free web services **spin down after 15 minutes of inactivity**. The next request takes ~1 minute to wake up.
> * The web service filesystem is **ephemeral** — anything written to disk (logs, uploaded files) is lost on redeploy/spin-down. This is why we use Postgres, not SQLite, for persistence.
> * 750 free instance hours per month per workspace.

---

## 1. Push Your Code to GitHub

Render deploys from a Git repository. If your code is not yet on GitHub:

1. Create a new repository on GitHub (e.g. `inventory_management_system`).
2. Push your local code to it:
   ```bash
   git remote add origin https://github.com/<your-username>/inventory_management_system.git
   git branch -M main
   git push -u origin main
   ```
   Ensure the `Procfile`, `requirements.txt`, and the `app.py` app-factory version are all committed.

---

## 2. Create a Free Postgres Database on Render

1. Sign up / log in at [dashboard.render.com](https://dashboard.render.com).
2. Click **New** → **PostgreSQL**.
3. Fill in:
   * **Name:** `church-inventory-db` (or any name)
   * **Database:** `church_inventory`
   * **User:** Render will auto-generate a user (note the username).
   * **Region:** choose the one closest to you (e.g. `Oregon (US West)`).
   * **Instance Type:** **Free** (1 GB storage, expires in 30 days).
4. Click **Create Database**.
5. Once created, scroll down to the **Connections** section and copy the **Internal Database URL** — it looks like:
   ```
   postgres://<user>:<password>@<host>:5432/church_inventory
   ```
   Also copy the **External Database URL** (you'll need this if you run CLI commands from your own machine).

> Keep these URLs handy — you'll paste them into the web service in the next step.

---

## 3. Create the Web Service on Render

1. In the Render dashboard, click **New** → **Web Service**.
2. Connect your GitHub account and select your `inventory_management_system` repository.
3. Fill in:
   * **Name:** `church-inventory` (this becomes part of your URL: `https://church-inventory.onrender.com`)
   * **Region:** must match your Postgres region (so they can talk over the private network).
   * **Runtime:** **Python 3** (Render will detect the latest stable version).
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `gunicorn wsgi:app --workers 1 --threads 2 --timeout 60`
     * (The repo's `Procfile` already contains this command; Render auto-detects the Procfile, so you can leave the Start Command blank and Render will use the `web` line.)
   * **Instance Type:** **Free** (512 MB RAM / 0.1 CPU).
4. Click **Advanced** and add the following **Environment Variables**:

   | Key | Value |
   |-----|-------|
   | `SECRET_KEY` | A long random string (e.g. output of `python -c "import secrets;print(secrets.token_hex(32))"`) |
   | `DATABASE_URL` | Paste the **Internal Database URL** from step 2 (starts with `postgres://...`) |
   | `LOG_LEVEL` | `INFO` |
   | `LOG_TO_STDOUT` | `1` (forces logs to stdout so Render's log drain captures them; the app also auto-detects read-only filesystems) |
   | `FLASK_DEBUG` | `False` |

5. Click **Create Web Service**.

Render will now build the app (install dependencies from `requirements.txt`) and start gunicorn. The `wsgi.py` entry point automatically creates the database tables on import via `db.create_all()` (idempotent — it skips tables that already exist), so no separate pre-deploy command is needed. This replaces the `init_db.sql` step used in the MySQL guides.

> **Note:** Render's **Pre-Deploy Command** field is a paid-feature only. The free-tier workflow uses `wsgi.py` (which runs table creation as part of the normal process startup) instead, so you don't need the Pre-Deploy Command.

Watch the **Logs** tab to confirm gunicorn starts listening (you should see the app's startup log lines including "Inventory App Starting Up..." and "Database URI: ...").

---

## 4. Create the Admin User

Because Render's free web service has no SSH access, you'll create the admin user via the **Shell** tab in the Render dashboard.

1. In your web service page, click the **Shell** tab. The Shell tab is available on free web services while they're running (if the service is spun down, trigger a manual deploy or visit the URL to wake it first).
2. In the shell, run:
   ```bash
   flask create-admin
   ```
   You'll be prompted for a username and password.

> **Alternative if Shell is unavailable:** set `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables, then temporarily change the **Start Command** to a one-shot Python snippet that creates the admin, deploy once, then revert the Start Command:
> ```
> python -c "from app import create_app; from extensions import db; from models import User; import os; app=create_app(); app.app_context().__enter__(); db.create_all(); u=User(username=os.environ['ADMIN_USERNAME'], is_admin=True); u.set_password(os.environ['ADMIN_PASSWORD']); db.session.add(u); db.session.commit(); print('Admin created')"
> ```
> After it succeeds, revert the Start Command to the gunicorn line and remove the `ADMIN_*` environment variables.

---

## 5. Verify the Deployment

1. Visit your service URL:
   ```
   https://<your-service-name>.onrender.com
   ```
2. The first load may take ~60 seconds while the free instance spins up.
3. Log in with the admin credentials you created.
4. Add a test item, transfer, and disposal to confirm the database connection works.

---

## 6. Important Operational Notes

* **Spin-down:** After 15 minutes with no traffic, the web service spins down. The next visitor waits ~1 minute for it to wake. This is normal on the free tier.
* **Database expiry:** Your free Postgres expires in 30 days. You'll get an email warning. To keep the data, upgrade the database to a paid plan before expiry. Otherwise, recreate the database and re-run the pre-deploy command.
* **Logs:** Use the Render dashboard **Logs** tab. The app logs to stdout when `LOG_TO_STDOUT=1` is set (or when the filesystem is read-only, which it is on Render).
* **Custom domain:** You can add a custom domain in the web service settings (Render provides free managed TLS).
* **No persistent filesystem:** Do not rely on `app.log` or any file-based storage. All persistent data must live in Postgres.

---

## 7. Troubleshooting

| Symptom | Likely Cause / Fix |
|---------|-------------------|
| `psycopg2.OperationalError: could not connect to server` | `DATABASE_URL` is wrong, or the web service region doesn't match the Postgres region. Use the **Internal** URL. |
| `flask.cli.NoAppException` on Shell tab | Ensure `app.py` exports `create_app` (it does in the current repo). Run `python -c "from app import create_app"` locally to verify. |
| 500 on first request after deploy | Tables weren't created. `wsgi.py` runs `db.create_all()` on import — check the startup logs for "Inventory App Starting Up...". If missing, verify `wsgi.py` exists and the Start Command points to `gunicorn wsgi:app`. |
| App loads but CSS/icons missing | You're offline or the jsDelivr CDN is blocked. The Bootstrap CSS/JS/icons load from `cdn.jsdelivr.net`. |
| Service won't wake up / suspended | You've hit the 750 free instance hours/month limit. Wait until next month or upgrade. |
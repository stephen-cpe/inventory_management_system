# Deployment Guide for Railway (Free Tier)

This guide deploys the Church Inventory System to Railway's free tier using a Railway Postgres database.

## Disclaimer

* This project is intended for **educational, testing, and experimentation purposes only**.
* **Not suitable for production use**.
* Use at your own risk. No warranties, guarantees, or support are provided.

> **Important Railway free-tier limits to know up front:**
> * Railway's **Free** plan is $0/month and includes **$1 of monthly usage credits**. There is no permanently-free always-on service — $1 of usage does not last a full month for a 24/7 web service. This plan is best for short-lived demos and experimentation.
> * Resource usage is metered **per second**: CPU, memory, and egress all count against your credit. A small 0.5 GB / 0.1 vCPU service left running continuously will exhaust $1 in roughly a few days.
> * To keep a service running all month you need the **Hobby** plan ($5/month, includes $5 of credits).
> * Max per service on Free: 1 vCPU / 0.5 GB RAM, 1 replica, 3-day log history.
> * The filesystem is **ephemeral** — anything written to disk is lost on redeploy. This is why we use Postgres, not SQLite, for persistence.

---

## 1. Push Your Code to GitHub

Railway deploys from a Git repository. If your code is not yet on GitHub:

1. Create a new repository on GitHub (e.g. `inventory_management_system`).
2. Push your local code to it:
   ```bash
   git remote add origin https://github.com/<your-username>/inventory_management_system.git
   git branch -M main
   git push -u origin main
   ```
   Ensure the `Procfile`, `requirements.txt`, and the `app.py` app-factory version are all committed.

---

## 2. Create a Railway Account and Project

1. Sign up at [railway.com](https://railway.com) (log in with GitHub for the smoothest experience).
2. Click **New Project**.
3. Select **Deploy from GitHub repo** and choose your `inventory_management_system` repository.
   * If this is your first time, Railway will ask to connect your GitHub account and grant repo access.

---

## 3. Add a PostgreSQL Database

1. In your new Railway project, click **New** (top-right) → **Database** → **Add PostgreSQL**.
2. Railway provisions a managed Postgres instance and adds it to your project.
3. Click the new Postgres service in your project to open it, then go to the **Variables** tab.
4. You'll find a `DATABASE_URL` variable already defined (its value looks like `postgresql://...`). You'll reference this from the web service via a **service reference** (cleaner than copying the URL).

> Railway's Postgres is **not free forever** — it consumes your $1 monthly credit just like the web service. A mostly-idle Postgres instance plus a small web service will exhaust $1 in a few days on the Free plan.

---

## 4. Configure the Web Service

1. Back in your project, click your web service (the one created from your GitHub repo) to open it.
2. Go to the **Variables** tab and add the following:

   | Key | Value |
   |-----|-------|
   | `SECRET_KEY` | A long random string (e.g. run `python -c "import secrets;print(secrets.token_hex(32))"` locally) |
   | `DATABASE_URL` | Click the variable input, then **Reference Variable** → select the Postgres service's `DATABASE_URL`. This auto-links them so the web service always has the correct connection string. |
   | `LOG_LEVEL` | `INFO` |
   | `LOG_TO_STDOUT` | `1` (logs to stdout so Railway's log viewer captures them; the app also auto-detects read-only filesystems) |
   | `FLASK_DEBUG` | `False` |

3. Go to the **Settings** tab of the web service:
   * **Build Command:** Railway's Nixpacks builder auto-detects Python and runs `pip install -r requirements.txt` automatically — leave blank unless you want to override.
   * **Start Command:** `gunicorn wsgi:app --workers 1 --threads 2 --timeout 60`
     * The repo's `Procfile` already contains this; Railway can use it but explicitly setting the Start Command is more reliable.
   * Under **Custom Domains**, generate a Railway domain (e.g. `church-inventory.up.railway.app`).

4. Save the settings. Railway will trigger a new deployment. The `wsgi.py` entry point automatically creates the database tables on import via `db.create_all()` (idempotent — it skips tables that already exist), so no separate pre-deploy command is needed. This replaces the `init_db.sql` step used in the MySQL guides.

> **Note:** Railway does support a **Pre-Deploy Command** field, but it's optional here. The `wsgi.py` approach works uniformly across Render, Railway, and Fly.io without platform-specific pre-deploy configuration. If you prefer to keep table creation out of the web process, you can alternatively set the Pre-Deploy Command to:
> ```
> python -c "from app import create_app; from extensions import db; app=create_app(); app.app_context().__enter__(); db.create_all(); print('Tables OK')"
> ```

Watch the **Deployments** tab for the gunicorn startup message (you should see "Inventory App Starting Up..." in the logs).

---

## 5. Create the Admin User

Railway provides a web-based terminal, but the simplest approach for the free tier is the **auto-create admin** feature (same as Render). Two options:

### Option A: Auto-create on first boot (recommended)

Add these environment variables to your web service (same **Variables** tab as before):

   | Key | Value |
   |-----|-------|
   | `AUTO_CREATE_ADMIN` | `1` |
   | `ADMIN_USERNAME` | `admin` (or your preferred username) |
   | `ADMIN_PASSWORD` | A strong password of your choice |

On the next deploy, `wsgi.py` auto-creates the admin user on process startup. After your first login, change the password via the user menu → Change Password, then remove `ADMIN_PASSWORD` and `AUTO_CREATE_ADMIN` from the variables (good hygiene — the logic is idempotent but the password shouldn't sit in config long-term).

### Option B: Use Railway's web terminal

1. In your web service page, click the three-dot menu → **Start Terminal**.
2. In the terminal, run:
   ```bash
   flask create-admin
   ```
   You'll be prompted for a username and password.
3. After it succeeds, log in at your Railway domain.

---

## 6. Verify the Deployment

1. Visit your Railway domain:
   ```
   https://<your-service-name>.up.railway.app
   ```
2. Log in with the admin credentials you created.
3. Add a test item, perform a transfer, record a disposal, and check the CSV export to confirm Postgres is wired up.

---

## 7. Important Operational Notes

* **Credit exhaustion:** Watch your usage in the Railway dashboard. When your $1 monthly credit runs out, Railway will stop your services. To keep a service running continuously, upgrade to the Hobby plan ($5/month, includes $5 of credits) — that comfortably runs a small Flask + Postgres app for a month.
* **Ephemeral filesystem:** Do not rely on `app.log` or any file-based storage. All persistent data must live in Postgres.
* **Logs:** Use Railway's **Logs** tab. The app logs to stdout when `LOG_TO_STDOUT=1` is set.
* **Sleep/idle:** Unlike Render, Railway does not spin down idle services — but they keep consuming your credit per second regardless of traffic.
* **Auto-deploy:** By default, Railway redeploys on every push to `main`. You can disable this in the service's GitHub settings if you want manual control.

---

## 8. Troubleshooting

| Symptom | Likely Cause / Fix |
|---------|-------------------|
| `psycopg2.OperationalError: could not connect to server` | `DATABASE_URL` is wrong or the Postgres service isn't running. Use a **Reference Variable** instead of a hardcoded string. |
| `relation "inventory" does not exist` on first request | Tables weren't created. `wsgi.py` runs `db.create_all()` on import — check the startup logs. Verify the Start Command is `gunicorn wsgi:app ...` and `wsgi.py` exists in the repo root. |
| `flask.cli.NoAppException` | Ensure `app.py` exports `create_app` (it does in the current repo). Run `python -c "from app import create_app"` locally to verify. |
| App loads but CSS/icons missing | You're offline or the jsDelivr CDN is blocked. Bootstrap CSS/JS/icons load from `cdn.jsdelivr.net`. |
| Service suddenly stopped | You've exhausted the $1 free credit. Upgrade to Hobby or wait until next month. |
| Build fails on `psycopg2-binary` | Ensure `requirements.txt` includes `psycopg2-binary==2.9.10`. The current repo includes it. |
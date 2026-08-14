# Deployment Guide for Render (Free Tier)

This guide deploys the Inventory System to Render's free tier using a free Render Postgres database. No credit card is required to start.

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

## 1. Get the Source Code from GitHub

Render deploys from a Git repository that you own. Since the source code already lives in a public repository, you can **fork** it (so Render can deploy from your own copy) and optionally **clone** it locally for inspection or local testing.

### 1a. Fork the repository on GitHub

1. Go to the project's GitHub page: [https://github.com/stephen-cpe/inventory_management_system](https://github.com/stephen-cpe/inventory_management_system)
2. Click the **Fork** button in the top-right corner.
3. Choose your GitHub account as the destination. GitHub creates a copy under your account, e.g. `https://github.com/<your-username>/inventory_management_system`.

> **Why fork?** Render connects to a repository under *your* GitHub account. You need your own copy (a fork) so Render has permission to read and deploy it. You cannot point Render directly at `stephen-cpe/inventory_management_system` unless you are a collaborator on that repo.

### 1b. (Optional) Clone your fork locally

If you want to inspect, modify, or run the code locally before deploying:

```bash
git clone https://github.com/<your-username>/inventory_management_system.git
cd inventory_management_system
```

Alternatively, you can download a ZIP archive instead of using Git:
1. On your fork's GitHub page, click the green **Code** button → **Download ZIP**.
2. Extract the archive to a folder of your choice.

> The `Procfile`, `requirements.txt`, and the `app.py` app-factory version are all included in the repository — no additional setup is needed before connecting it to Render.

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
4. Add the following **Environment Variables**:

   | Key | Value |
   |-----|-------|
   | `SECRET_KEY` | A long random string (e.g. output of `python -c "import secrets;print(secrets.token_hex(32))"`) |
   | `DATABASE_URL` | Paste the **Internal Database URL** from step 2 (starts with `postgres://...`) |
   | `LOG_LEVEL` | `INFO` |
   | `LOG_TO_STDOUT` | `1` (forces logs to stdout so Render's log drain captures them; the app also auto-detects read-only filesystems) |
   | `FLASK_DEBUG` | `False` |
   | `AUTO_CREATE_ADMIN` | `1` (enables auto-creation of a default admin user on first boot — see step 4) |
   | `ADMIN_USERNAME` | `admin` (or your preferred username) |
   | `ADMIN_PASSWORD` | A strong password of your choice (e.g. `MyStr0ngP@ssw0rd!`). If omitted, an insecure built-in default is used — always set this. |

5. Click **Deploy Web Service**.

Render will now build the app (install dependencies from `requirements.txt`) and start gunicorn. The `wsgi.py` entry point automatically creates the database tables on import via `db.create_all()` (idempotent — it skips tables that already exist), so no separate pre-deploy command is needed. This replaces the `init_db.sql` step used in the MySQL guides.

> **Note:** Render's **Pre-Deploy Command** field is a paid-feature only. The free-tier workflow uses `wsgi.py` (which runs table creation as part of the normal process startup) instead, so you don't need the Pre-Deploy Command.

Watch the **Logs** tab to confirm gunicorn starts listening (you should see the app's startup log lines including "Inventory App Starting Up..." and "Database URI: ...").

---

## 4. Create the Admin User

Render's free tier offers **no Shell access and no Pre-Deploy Command** (both are paid features), so `flask create-admin` cannot be run interactively. Instead, the app supports **auto-creation of a default admin user on first boot** via the environment variables you set in step 3 (`AUTO_CREATE_ADMIN`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`).

On process startup, `wsgi.py` checks whether the admin user already exists. If not, it creates one with those credentials and logs: `Auto-created default admin user 'admin'. CHANGE THE DEFAULT PASSWORD IMMEDIATELY...`

**After your first successful login:**
1. Go to the user menu → **Change Password** and set a new one.
2. Remove `ADMIN_PASSWORD` and `AUTO_CREATE_ADMIN` from the Render environment variables (good hygiene — the logic is idempotent and won't re-create an existing user, but the password shouldn't sit in plaintext config long-term).

> **If you didn't set `ADMIN_PASSWORD` in step 3:** an insecure built-in default (`Ch@ng3meA$@P`) is used. **Always set a custom `ADMIN_PASSWORD`** for any deployment that's publicly accessible, and change it immediately after first login.

> **How it works:** The `wsgi.py` entry point runs `db.create_all()` and then, if `AUTO_CREATE_ADMIN` is set, checks for the admin user and creates it if missing. This all happens inside the normal web process, so no shell or pre-deploy command is needed.

---

## 5. Verify the Deployment

1. Visit your service URL:
   ```
   https://<your-service-name>.onrender.com
   ```
2. The first load may take ~60 seconds while the free instance spins up.
3. Log in with the admin credentials you configured in step 4.
4. **Immediately change the password** via the user menu → Change Password.
5. Add a test item, transfer, and disposal to confirm the database connection works.

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
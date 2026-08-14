# Deployment Guide for Fly.io (Free Trial + Cheapest Paid Tier)

This guide deploys the Inventory System to Fly.io. Fly.io's free trial is time-limited (2 VM-hours or 7 days, whichever comes first); after that you add a credit card and pay per second of usage. The cheapest practical configuration for this app is a single `shared-cpu-1x 256MB` Machine (~$2/month when running 24/7) plus a **Supabase** Postgres database (free tier). Fly.io no longer offers a free managed Postgres, so this guide uses Supabase for the database.

> **Prerequisite:** This guide assumes you have **already created a Supabase account and project**. You will need your Supabase project's **direct connection string** and **database password** — both are found in the Supabase dashboard under **Project Settings → Database → Connection string**.

## Disclaimer

* This project is intended for **educational, testing, and experimentation purposes only**.
* **Not suitable for production use**.
* Use at your own risk. No warranties, guarantees, or support are provided.

> **Important Fly.io free-trial limits to know up front:**
> * The free trial includes **2 total VM-hours** of machine runtime or **7 days**, whichever comes first. Trial machines also **auto-stop after 5 minutes** of inactivity.
> * After the trial you **must add a credit card** — there is no permanently-free tier. Fly.io is pay-as-you-go (per second).
> * The cheapest always-on configuration for this app is a single `shared-cpu-1x 256MB` Machine (~$1.94/month). The database lives on **Supabase** (free tier, separate from Fly.io billing).
> * The filesystem is **ephemeral** — anything written to disk is lost on redeploy. This is why we use Postgres (on Supabase), not SQLite, for persistence.

---

## 1. Install the Fly CLI and Sign Up

1. Install `flyctl`, the Fly.io command-line tool:

   **Windows (PowerShell):**
   ```powershell
   iwr https://fly.io/install.ps1 -useb | iex
   ```
   **macOS / Linux:**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. Sign up / log in:
   ```bash
   fly auth signup
   ```
   Follow the browser prompt to create a Fly.io account and a "personal" organization.

3. Verify your CLI works:
   ```bash
   fly version
   ```

---

## 2. Get the Source Code from GitHub (Optional but Recommended)

Fly.io can deploy directly from your local directory (no GitHub account or fork required). You just need a local copy of the source code to run `fly launch` from.

### 2a. Clone the repository

```bash
git clone https://github.com/stephen-cpe/inventory_management_system.git
cd inventory_management_system
```

### 2b. (Alternative) Download a ZIP archive

If you prefer not to use Git:

1. Go to [https://github.com/stephen-cpe/inventory_management_system](https://github.com/stephen-cpe/inventory_management_system).
2. Click the green **Code** button → **Download ZIP**.
3. Extract the archive to a folder of your choice and open a terminal in that folder.

> The `Procfile`, `requirements.txt`, and the `app.py` app-factory version are all included in the repository — no additional setup is needed before running `fly launch`.

> **Optional — fork for redeploying via GitHub:** If you later want Fly to auto-deploy from your own GitHub repo on every push, you can fork the repository (click **Fork** on the GitHub page) and clone your fork instead. For the simplest first-time deployment, cloning the public repo directly is sufficient.

---

## 3. Launch the App

From the root of your project directory (the one containing `app.py`), run:

```bash
fly launch
```

Fly will analyze your project and propose a configuration. When prompted:

1. **Detecting app type:** Fly should detect Python. Confirm yes.
2. **Choose an app name:** e.g. `church-inventory` (this becomes `https://church-inventory.fly.dev`).
3. **Choose a region:** pick the one closest to you (e.g. `sjc` for US West, `lhr` for London).
4. **Postgres database:** when Fly asks "Would you like to set up a Postgres database now?", answer **no**.
   * We are using **Supabase** for the database (external to Fly.io), so Fly does not need to provision one.
   * You will wire up the Supabase connection string in the next step.
5. **Would you like to deploy now?** Answer **yes** (or **no** if you'd rather set secrets first — either works).

Fly will generate a `fly.toml` file in your project root. Let it complete the first deploy, even if it fails on the database step (no `DATABASE_URL` yet) — we'll fix the configuration next.

---

## 4. Configure Environment Variables (Secrets)

Fly stores environment variables as "secrets". Set them from your project directory:

```bash
fly secrets set SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
fly secrets set LOG_LEVEL=INFO
fly secrets set LOG_TO_STDOUT=1
fly secrets set FLASK_DEBUG=False
```

### Set the Supabase `DATABASE_URL`

Fly's `fly launch` did **not** create a `DATABASE_URL` secret (we declined Fly's Postgres), so you must set it manually using your **Supabase direct connection string**.

> **Find it in Supabase:** Dashboard → your project → **Project Settings** → **Database** → **Connection string** → **Direct connection** (the URI, not the pooled/session-pooler one). It looks like:
> ```
> postgresql://postgres:[YOUR-PASSWORD]@db.<project-ref>.supabase.co:5432/postgres
> ```

Set it (replace the values with your own):

```bash
fly secrets set DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@db.vlmtxvnypwfvzlfplsrp.supabase.co:5432/postgres"
```

> **⚠️ URL-encode special characters in the password.** If your Supabase database password contains characters like `@`, `#`, `:`, `/`, or `?`, they will break the connection string. Encode them:
> | Character | Encoded |
> |-----------|---------|
> | `@` | `%40` |
> | `#` | `%23` |
> | `:` | `%3A` |
> | `/` | `%2F` |
> | `?` | `%3F` |
>
> **Example:** If your password is `sTr0ng_p@55w0rD#`, the URL-encoded value is `sTr0ng_p%4055w0rD%23`, so the full command becomes:
> ```bash
> fly secrets set DATABASE_URL="postgresql://postgres:sTr0ng_p%4055w0rD%23@db.vlmtxvnypwfvzlfplsrp.supabase.co:5432/postgres"
> ```
> A quick way to encode any password in Python:
> ```bash
> python -c "import urllib.parse; print(urllib.parse.quote('YOUR_PASSWORD', safe=''))"
> ```

> **Note:** Use the **direct connection** string (host `db.<project-ref>.supabase.co`), not the pooled/connection-pooler string (`aws-0-<region>.pooler.supabase.com`), unless you have tuned the app's pool settings. The direct connection works out of the box with SQLAlchemy's default pool.

Verify all secrets are set:

```bash
fly secrets list
```

You should see `DATABASE_URL`, `SECRET_KEY`, `LOG_LEVEL`, `LOG_TO_STDOUT`, and `FLASK_DEBUG`.

---

## 5. Configure the Dockerfile for Gunicorn

`fly launch` generates a `Dockerfile` and a `fly.toml` in your project root. By default the generated Dockerfile runs Flask's **development server** (`flask run`), which is fine for testing but not production-grade. For this app, switch it to **gunicorn** (the repo's `Procfile` already specifies gunicorn, but Fly's generated Dockerfile overrides it).

Open the generated `Dockerfile` and replace the last two lines:

**Before (generated):**
```dockerfile
EXPOSE 8080

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0", "--port=8080"]
```

**After (edited):**
```dockerfile
EXPOSE 8080

CMD ["gunicorn", "wsgi:app", "--workers", "1", "--threads", "2", "--timeout", "60", "--bind", "0.0.0.0:8080"]
```

Why:
* `gunicorn wsgi:app` uses the repo's `wsgi.py` entry point, which runs `db.create_all()` on import (idempotent — skips existing tables) and optionally auto-creates the admin user (see step 7). This replaces the `init_db.sql` step used in the MySQL guides and avoids the need for a `release_command`.
* `--bind 0.0.0.0:8080` must match the `internal_port` in `fly.toml` (see below).

### Check `fly.toml`

`fly launch` also generated a `fly.toml`. You generally do **not** need to edit it — just verify `internal_port` matches the port gunicorn binds to (8080). A typical generated file looks like:

```toml
app = 'inventory-management-system-earnest-rain-2934'
primary_region = 'sin'

[build]
[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = 'stop'
  auto_start_machines = true
  min_machines_running = 0
  processes = ['app']

[[vm]]
  memory = '1gb'
  cpus = 1
  memory_mb = 1024
```

Key points:
* `internal_port = 8080` must match gunicorn's `--bind 0.0.0.0:8080`. If you changed gunicorn to bind a different port, update this to match.
* `auto_stop_machines = 'stop'` and `auto_start_machines = true` let the machine sleep when idle (saves money on pay-as-you-go). The first request after sleep takes a few seconds to wake. (`'stop'` is the newer Fly.io schema value and is equivalent to the older `true`.)
* No `[processes]` block is needed — the start command lives in the Dockerfile `CMD` (Fly runs whatever the Dockerfile specifies).

> **Note on VM size:** `fly launch` may default to `1GB` RAM. For this small Flask app, `shared-cpu-1x 256MB` is sufficient and cheaper. You can change this later via `fly scale memory 256` or in the Fly dashboard. Reducing memory lowers cost but leaves less headroom for concurrent requests.

> **Optional — keep table creation out of the web process:** If you prefer to run `db.create_all()` as a separate pre-deploy step instead of on `wsgi.py` import, Fly.io supports a `[deploy]` section with a `release_command` (on all plans):
> ```toml
> [deploy]
>   release_command = "python -c \"from app import create_app; from extensions import db; app=create_app(); app.app_context().__enter__(); db.create_all(); print('Tables OK')\""
> ```
> Either approach works — `wsgi.py` is simpler and uniform across all three PaaS platforms.

---

## 6. Deploy

Run the deploy:

```bash
fly deploy
```

Watch the output for:
* `Inventory App Starting Up...` (from `wsgi.py` import) — confirms the app loaded and `db.create_all()` ran.
* `Started machine` and a clean health check — confirms gunicorn started and is listening on port 8000.

If the deploy fails, check the logs:

```bash
fly logs
```

---

## 7. Create the Admin User

Two options:

### Option A: Auto-create on first boot (recommended)

Set **all three** secrets in a **single** `fly secrets set` command so they take effect in the same restart. If you set them one at a time, each `fly secrets set` triggers a separate machine restart — and `wsgi.py` will auto-create the admin on the first restart using whatever secrets exist at that moment (falling back to the insecure built-in default password `Ch@ng3meA$@P` if `ADMIN_PASSWORD` isn't set yet).

```bash
fly secrets set AUTO_CREATE_ADMIN=1 ADMIN_USERNAME=admin ADMIN_PASSWORD=MyStr0ngP@ssw0rd!
```

> **⚠️ Set all three in one command.** Setting them separately is the most common cause of "wrong password" errors on first login — the admin gets created on the first restart with default credentials, and later restarts skip re-creation because the user already exists.

On the next deploy (or process restart), `wsgi.py` auto-creates the admin user on startup. After your first login, change the password via the user menu → Change Password, then remove the secrets:

```bash
fly secrets unset AUTO_CREATE_ADMIN ADMIN_PASSWORD
```

> **If you already hit the "wrong password" issue** (admin was created with the default password before `ADMIN_PASSWORD` was set), you can either:
> 1. Log in with the default password `Ch@ng3meA$@P` and change it via the UI, or
> 2. Reset it from a `fly ssh console` session:
>    ```bash
>    python -c "from app import create_app; from extensions import db; from models import User; app=create_app(); app.app_context().__enter__(); u=User.query.filter_by(username='admin').first(); u.set_password('MyStr0ngP@ssw0rd!'); db.session.commit(); print('Password reset OK')"
>    ```

### Option B: Use fly ssh console

Fly.io gives you direct shell access to running machines. After a successful deploy, run:

```bash
fly ssh console
```

This opens a shell inside the running container. Then run:

```bash
flask create-admin
```

You'll be prompted for a username and password. After it succeeds, type `exit` to leave the shell.

> If `flask` isn't on PATH inside the container, use the full Python command instead:
> ```bash
> python -c "from app import create_app; from extensions import db; from models import User; app=create_app(); app.app_context().__enter__(); u=User(username='admin', is_admin=True); u.set_password('YOUR_PASSWORD'); db.session.add(u); db.session.commit(); print('Admin created')"
> ```

---

## 8. Verify the Deployment

1. Visit your Fly URL:
   ```
   https://<your-app-name>.fly.dev
   ```
2. Log in with the admin credentials you created.
3. Add a test item, perform a transfer, record a disposal, and check the CSV export to confirm Postgres is wired up.

---

## 9. Important Operational Notes

* **Cost control:** The free trial lasts only 2 VM-hours / 7 days. After that, add a credit card. To minimize cost:
  * Keep `auto_stop_machines = true` so the machine sleeps when idle.
  * Use the smallest machine size (`shared-cpu-1x 256MB`) — sufficient for this Flask app.
  * The database runs on **Supabase** (free tier, billed separately from Fly.io).
* **Ephemeral filesystem:** Do not rely on `app.log` or any file-based storage. All persistent data must live in Postgres. The app's logging is configured to fall back to stdout (`LOG_TO_STDOUT=1`) which Fly's log drain captures.
* **Wake-up latency:** When `auto_stop_machines` is enabled, the first request after idle takes a few seconds to wake the machine. Subsequent requests are fast.
* **Custom domain:** Add a custom domain via `fly certs add yourdomain.com` (Fly provides free Let's Encrypt TLS).
* **Redeploying:** Run `fly deploy` from your project directory. The `wsgi.py` entry point re-runs `db.create_all()` automatically on each process start.

---

## 10. Troubleshooting

| Symptom | Likely Cause / Fix |
|---------|-------------------|
| `psycopg2.OperationalError: could not connect to server` | `DATABASE_URL` is wrong or the Supabase project is paused. Verify the connection string, ensure special characters in the password are URL-encoded (`@`→`%40`, `#`→`%23`), and check the Supabase dashboard that the project is active. Test connectivity from your machine with `psql "<DATABASE_URL>"`. |
| `relation "inventory" does not exist` on first request | Tables weren't created. `wsgi.py` runs `db.create_all()` on import — check `fly logs` for "Inventory App Starting Up...". Verify the start command uses `gunicorn wsgi:app ...` and `wsgi.py` exists in the repo root. |
| `flask.cli.NoAppException` | Ensure `app.py` exports `create_app` (it does in the current repo). Run `python -c "from app import create_app"` locally to verify. |
| App loads but CSS/icons missing | You're offline or the jsDelivr CDN is blocked. Bootstrap CSS/JS/icons load from `cdn.jsdelivr.net`. |
| `fly deploy` fails on `psycopg2-binary` build | Ensure `requirements.txt` includes `psycopg2-binary==2.9.10`. The current repo includes it. |
| Machine won't start / 502 on first request | `internal_port` in `fly.toml` doesn't match the port gunicorn binds to in the Dockerfile `CMD`. Both must be the same (the generated default is `8080`). |
| "Trial exhausted" message | Your 2-hour free trial is used up. Add a credit card in the Fly dashboard to continue. |
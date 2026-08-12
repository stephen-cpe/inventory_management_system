# Deployment Guide for Fly.io (Free Trial + Cheapest Paid Tier)

This guide deploys the Church Inventory System to Fly.io. Fly.io's free trial is time-limited (2 VM-hours or 7 days, whichever comes first); after that you add a credit card and pay per second of usage. The cheapest practical configuration for this app is a single `shared-cpu-1x 256MB` Machine (~$2/month when running 24/7) plus Fly Managed Postgres.

## Disclaimer

* This project is intended for **educational, testing, and experimentation purposes only**.
* **Not suitable for production use**.
* Use at your own risk. No warranties, guarantees, or support are provided.

> **Important Fly.io free-trial limits to know up front:**
> * The free trial includes **2 total VM-hours** of machine runtime or **7 days**, whichever comes first. Trial machines also **auto-stop after 5 minutes** of inactivity.
> * After the trial you **must add a credit card** — there is no permanently-free tier. Fly.io is pay-as-you-go (per second).
> * The cheapest always-on configuration for this app is a single `shared-cpu-1x 256MB` Machine (~$1.94/month) plus Fly Managed Postgres (see current Postgres pricing at the time of deployment). Total cost is a few dollars per month.
> * The filesystem is **ephemeral** — anything written to disk is lost on redeploy. This is why we use Postgres, not SQLite, for persistence.

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

## 2. Push Your Code to GitHub (Optional but Recommended)

Fly.io can deploy directly from your local directory (no GitHub required), but having your code on GitHub makes redeploying easier. If pushing to GitHub:

```bash
git remote add origin https://github.com/<your-username>/inventory_management_system.git
git branch -M main
git push -u origin main
```

Ensure the `Procfile`, `requirements.txt`, and the `app.py` app-factory version are all committed.

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
4. **Postgres database:** when Fly asks "Would you like to set up a Postgres database now?", answer **yes**.
   * Choose the smallest Postgres plan available (Fly Managed Postgres).
   * Note the connection string Fly generates — it will look like `postgres://...@top1.nearest.of.<app-name>-db.internal:5432`.
5. **Would you like to deploy now?** Answer **yes**.

Fly will generate a `fly.toml` file in your project root. Let it complete the first deploy, even if it fails on the database step — we'll fix the configuration next.

---

## 4. Configure Environment Variables (Secrets)

Fly stores environment variables as "secrets". Set them from your project directory:

```bash
fly secrets set SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
fly secrets set LOG_LEVEL=INFO
fly secrets set LOG_TO_STDOUT=1
fly secrets set FLASK_DEBUG=False
```

For the database URL, Fly's `fly launch` Postgres setup usually creates a `DATABASE_URL` secret automatically. Verify it exists:

```bash
fly secrets list
```

If `DATABASE_URL` is missing, set it manually using the connection string Fly gave you in step 3:

```bash
fly secrets set DATABASE_URL="postgres://<user>:<password>@<host>:5432/<dbname>"
```

> **Important:** For the web app to reach Postgres, use the **internal** hostname (ends in `.internal`) when the Postgres cluster is in the same Fly organization. The `fly pg attach` command does this for you automatically if you ran `fly launch` with Postgres enabled.

---

## 5. Configure the fly.toml for Gunicorn and Database Init

Open the generated `fly.toml` and ensure it contains the correct start command and a release command to create tables. It should look like this:

```toml
app = "church-inventory"
primary_region = "sjc"

[build]

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0

[processes]
  # The Procfile in the repo is also honored; this is explicit.
  web = "gunicorn 'app:create_app()' --workers 1 --threads 2 --timeout 60 --bind 0.0.0.0:8000"

[deploy]
  release_command = "python -c \"from app import create_app; from extensions import db; app=create_app(); app.app_context().__enter__(); db.create_all(); print('Tables OK')\""
```

Key points:
* `internal_port = 8000` must match the port gunicorn binds to (`--bind 0.0.0.0:8000`).
* `auto_stop_machines = true` and `auto_start_machines = true` let the machine sleep when idle (saves money on pay-as-you-go). The first request after sleep takes a few seconds to wake.
* The `release_command` runs before each deploy to create the database tables via `db.create_all()` (idempotent — skips existing tables). This replaces the `init_db.sql` step used in the MySQL guides.

If you prefer to keep the repo's `Procfile` as the source of truth for the start command, you can omit the `[processes]` block — Fly detects the `web` line in the `Procfile` automatically.

---

## 6. Deploy

Run the deploy:

```bash
fly deploy
```

Watch the output for:
* `Tables OK` (from the release command) — confirms the database schema was created.
* `Started machine` and a clean health check — confirms gunicorn started.

If the deploy fails, check the logs:

```bash
fly logs
```

---

## 7. Create the Admin User

Fly.io gives you direct shell access to running machines via `fly ssh`. After a successful deploy, run:

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
  * Use the smallest Fly Managed Postgres plan.
* **Ephemeral filesystem:** Do not rely on `app.log` or any file-based storage. All persistent data must live in Postgres. The app's logging is configured to fall back to stdout (`LOG_TO_STDOUT=1`) which Fly's log drain captures.
* **Wake-up latency:** When `auto_stop_machines` is enabled, the first request after idle takes a few seconds to wake the machine. Subsequent requests are fast.
* **Custom domain:** Add a custom domain via `fly certs add yourdomain.com` (Fly provides free Let's Encrypt TLS).
* **Redeploying:** Run `fly deploy` from your project directory. The release command re-runs `db.create_all()` automatically.

---

## 10. Troubleshooting

| Symptom | Likely Cause / Fix |
|---------|-------------------|
| `psycopg2.OperationalError: could not connect to server` | `DATABASE_URL` is wrong, or the web app and Postgres cluster aren't in the same Fly organization/region. Use the `.internal` hostname. Run `fly pg attach` to wire them up. |
| `relation "inventory" does not exist` on first request | Tables weren't created. Check `fly logs` for "Tables OK" from the release command. Re-run `fly deploy` or run the create_tables command via `fly ssh console`. |
| `flask.cli.NoAppException` | Ensure `app.py` exports `create_app` (it does in the current repo). Run `python -c "from app import create_app"` locally to verify. |
| App loads but CSS/icons missing | You're offline or the jsDelivr CDN is blocked. Bootstrap CSS/JS/icons load from `cdn.jsdelivr.net`. |
| `fly deploy` fails on `psycopg2-binary` build | Ensure `requirements.txt` includes `psycopg2-binary==2.9.10`. The current repo includes it. |
| Machine won't start / 502 on first request | `internal_port` in `fly.toml` doesn't match gunicorn's `--bind` port. Both must be `8000`. |
| "Trial exhausted" message | Your 2-hour free trial is used up. Add a credit card in the Fly dashboard to continue. |
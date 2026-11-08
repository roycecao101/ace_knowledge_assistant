# Ace Knowledge Assistant

FastAPI serves the existing employee and administrator pages and same-origin authentication APIs. The original page layouts and synthetic specimens are retained. Real administrative account controls use the existing table, form, panel, and dialog styling.

## Local setup

For the existing Google Drive installation, use the [current restart instructions](docs/dashboard-sync-fix.md#starting-from-vs-code). They load the private local environment before launching FastAPI. Keep the existing database and accounts; the fresh-install fixture instructions below are not required for a restart.

When upgrading to the consolidated administrator dashboard, run `python -m backend.offices` with the same `DATABASE_URL` as the server before restarting. This additive migration creates the persistent office catalog and required office labels, preserving all existing accounts, assignments, sessions, and knowledge records. It has already been applied to this workspace's existing database. See the [dashboard implementation and validation report](docs/admin-dashboard-cleanup.md).

From this project root, activate your existing virtual environment, then run:

```sh
python -m pip install -r backend/requirements.txt
python -m backend.seed_test_accounts --seed-test-accounts
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

If you need a virtual environment, run `python3 -m venv .venv` and `source .venv/bin/activate` first. A `.venv` was created during implementation.

The initializer creates the SQLite schema and inserts missing official test accounts. It never resets an existing PIN, password, or active status. Run without `--seed-test-accounts` to initialize only. Test seeding is explicitly restricted to development SQLite; do not seed or copy the test database into deployment. The default database is `backend/ace.db`, excluded from Git. Protect its directory and backups with OS permissions.

Open employee sign in at http://127.0.0.1:8000/login.html or administrator sign in at http://127.0.0.1:8000/admin-login.html.


These published fixtures are for local testing only. Credentials exist in the explicit fixture seed, never in browser assets. Stored credentials use salted Argon2id hashes. Generated PINs appear only in their creation/reset response and a dialog that clears on close, tab hiding, or after 60 seconds. Deliver them privately; there is no retrieval endpoint.

Employee home offices load from the authenticated account. Employees may switch the search office. Administrators may use Employee View with their existing administrator session. Logout invalidates the current server session. Logging into a new account in the same browser replaces its prior session.

## Security and operations

Sessions are opaque 256-bit random values; the database stores only their SHA-256 digest. Cookies are HttpOnly, SameSite=Strict, expire after eight hours, and become Secure with a `__Host-` name in production. Every authenticated mutation, including search and logout, requires a session-bound CSRF token held only in JavaScript memory. JSON login requests are protected by same-origin checks, cross-site fetch rejection, and the absence of cross-origin permissions. No browser credentials or tokens are stored in localStorage.

Every API request rechecks active status and credential version. Account deactivation and credential replacement invalidate prior sessions. Five failed attempts within 15 minutes lock the identifier for 15 minutes, including unknown identifiers; both account types receive generic login failures. Lockouts and administrator changes serialize through a shared database guard row. Deactivation and deletion cannot reduce the active administrator count below two. Password replacement requires at least 12 characters.

Set `APP_ENV=production` and `APP_ORIGIN=https://your-actual-host` behind HTTPS. The application rejects production configuration without HTTPS, restricts Host headers to the configured origin, sets HSTS, and never enables synthetic preview. For local use with `localhost` instead of `127.0.0.1`, set `APP_ORIGIN=http://localhost:8000`. Do not expose the development server publicly. Configure your reverse proxy to exclude request bodies, response bodies, credentials, and question contents from logs. Authentication attempt records contain only hashed role/identifier keys, failure counts, and timing, and are separate from search data. Establish a retention/cleanup policy for expired sessions and old attempt rows before deployment. Add perimeter rate limiting for distributed identifier spraying and monitor security events without search contents.

SQLAlchemy models and a `DATABASE_URL` setting provide a path to PostgreSQL. Install a PostgreSQL driver, provision the schema with a reviewed migration, and securely provision at least two real administrators before deployment. The local seed command intentionally refuses production and non-SQLite databases. Schema changes currently require explicit migrations; application startup does not mutate the schema or credentials.

Search uses the active approved document generation and verifies returned quotations locally. Knowledge Management consolidates Google Drive connection status, synchronization, indexed/unreadable document metadata, and folder settings. Office Management supports persistent office creation, unique names/codes, and the LIL/ADC aliases for Lilburn. Employee selectors and creation/edit forms use the database catalog. Re-sync after adding an office to apply its code and heading name to existing document scopes. Policy Guardian is a clean placeholder; its synthetic preview remains available. Questions and answers are not stored, and no employee usage analytics are created. Document extraction and search run locally without an external AI service. See the [ingestion guide](docs/ingestion.md) and [OAuth setup](docs/google-drive-oauth.md).

## Verification

```sh
python -m pytest -q
node --test tests/test_auth_client.cjs tests/test_employee_search_ui.cjs tests/test_admin_dashboard_ui.cjs
```

Tests use fresh temporary databases, fictional identities, and synthetic questions. They cover the official logins/home offices, failed attempts and lock duration, deactivation across clients, PIN/session invalidation, administrator access, role denial, administrator minimums, logout, unauthenticated searches, CSRF/origin checks, password constraints, expiration, one-time PIN creation, and idempotent seeding.

## Isolated synthetic preview

Stop using the old static-server preview command. Instead run:

```sh
python -m backend.preview
```

Open http://127.0.0.1:8081/index.html?preview=1 or http://127.0.0.1:8081/admin.html?preview=1. This separate loopback-only server enables a synthetic-only browser flag, loads no authentication/database modules, and exposes no API. Questions remain disabled and administrative actions remain fictional. The FastAPI server never supplies that flag; `?preview=1` grants no access there.

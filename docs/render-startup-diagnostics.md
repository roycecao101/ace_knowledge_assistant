# Render startup diagnosis

This procedure does not change application code, security checks, schema, accounts, or Drive grants. Run it in the deployed image with the service's environment, or from the same checkout/dependency environment in a clean operator shell configured as described in [Render deployment](render-deployment.md#5-explicit-database-initialization-from-your-computer). A local shell must use the database's external URL and have network access; Render uses its internal URL. Never source the repository `.env`, enable shell tracing, dump the environment, print exceptions, or paste connection strings into commands/history. Enter secrets with the existing hidden prompts. No deployment credentials were inspected in preparing this guide.

## What the error actually means

`Dockerfile` runs `python -m backend.serve`. Its `try` block imports `backend.main.app` (which executes `create_app()`), then parses `PORT`. **Any `Exception` in that block** becomes the quoted `Startup configuration failed…` message. It is not a diagnosis of database connectivity.

The explicit rejection conditions in that path are:

| Check | Rejection condition |
| --- | --- |
| Hosted environment | Any nonempty `RENDER`, `K_SERVICE`, or `CLOUD_RUN_JOB`, but `APP_ENV` is not exactly `production`. |
| Drive mode/source | Invalid `DRIVE_AUTH_MODE`; `oauth_local` in a hosted/nondevelopment process; production mode other than `adc`/`oauth_web`; production `KNOWLEDGE_SOURCE` other than exactly `drive`. |
| Render-specific | Nonempty `RENDER`, but mode is not `oauth_web` or `SYNC_EXECUTOR` is not exactly `database`. |
| Local paths | Any nonempty `GOOGLE_APPLICATION_CREDENTIALS`, `DRIVE_OAUTH_CLIENT_FILE`, `DRIVE_OAUTH_TOKEN_FILE`, or `SYNTHETIC_DOCUMENT_DIR` in production. |
| Folder | `DRIVE_KNOWLEDGE_FOLDER_ID` is not 1–200 ASCII letters, digits, underscores or hyphens. |
| Web OAuth identity | Trimmed `DRIVE_AUTHORIZED_EMAIL` fails `[^\s@]+@[^\s@]+\.[^\s@]+`. |
| Origin | `APP_ORIGIN` is not parseable HTTPS with a hostname, no username/password, **no path (including `/`)**, query or fragment, and port absent or 443. Malformed port/URL parsing can also raise. |
| Web client | `DRIVE_WEB_CLIENT_ID` does not end in `.apps.googleusercontent.com`, or `DRIVE_WEB_CLIENT_SECRET` is empty. These checks do not verify the credentials with Google. |
| Encryption | `DRIVE_TOKEN_ENCRYPTION_KEY` is missing, non-ASCII, or rejected by `Fernet` (requires a URL-safe base64 encoding of a 32-byte key). |
| Executor | Production web `SYNC_EXECUTOR` is neither `database` nor `cloud_run`; `cloud_run` lacks a `SYNC_JOB_RESOURCE` matching `projects/[a-z][a-z0-9-]+/locations/[a-z0-9-]+/jobs/[a-z][a-z0-9-]+`. Render already requires `database`. |
| Database construction | Missing explicit production database; malformed URL; driver other than `postgresql+psycopg` after normalization of `postgres`/`postgresql`; Render URL `sslmode` other than `require` (absence is accepted and upgraded to `require`). Missing Cloud SQL `DB_USER`/`DB_PASSWORD`/`DB_NAME` can raise if that fallback is selected. Use `DATABASE_URL` on Render. Engine/driver construction failures also qualify. |
| Port | `PORT` is not accepted by `int()` or is outside 1–65535; absent defaults to 8080. Leave Render's supplied value alone. |

Because the handler catches every import/construction exception, missing/incompatible dependencies, import errors, Argon2 dummy-hash initialization failures, and other unexpected exceptions in app construction can produce exactly the same message. The redundant production origin/local-source guards in `create_app()` are already covered by the stricter environment validation. `BOOTSTRAP_ADMINS` is removed by `serve` before import and cannot bootstrap the web process.

## Safe, read-only diagnostic

Run this from the repository root using the deployment's Python dependencies and environment. It prints fixed labels and PASS/FAIL/SKIP only, including when a library raises. It checks all Render configuration fields independently, invokes the real validation, and reads database readiness without migrating or bootstrapping. Database reads may take time if networking is unavailable. Do not add exception printing or SQL/debug logging.

```sh
python - <<'PY'
import contextlib
import io
import logging
import os
import re
from urllib.parse import urlsplit

logging.disable(logging.CRITICAL)
results = {}
def check(label, action):
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            ok = bool(action())
    except Exception:
        ok = False
    results[label] = ok
    print(('PASS ' if ok else 'FAIL ') + label)
    return ok

def exact(key, value):
    return check(key, lambda: os.getenv(key) == value)
def origin_ok():
    p = urlsplit(os.getenv('APP_ORIGIN', ''))
    return (p.scheme == 'https' and p.hostname and not p.username and not p.password
            and not p.path and not p.query and not p.fragment and p.port in (None, 443))
def cipher_ok():
    from cryptography.fernet import Fernet
    Fernet(os.environ['DRIVE_TOKEN_ENCRYPTION_KEY'].encode('ascii'))
    return True
def runtime_ok():
    from backend.runtime import validate_environment
    validate_environment(web=True)
    return True

a = exact('APP_ENV', 'production')
b = exact('RENDER', 'true')  # Diagnostic profile; runtime accepts any nonempty value.
exact('KNOWLEDGE_SOURCE', 'drive')
exact('DRIVE_AUTH_MODE', 'oauth_web')
exact('SYNC_EXECUTOR', 'database')
for key in ('GOOGLE_APPLICATION_CREDENTIALS', 'DRIVE_OAUTH_CLIENT_FILE',
            'DRIVE_OAUTH_TOKEN_FILE', 'SYNTHETIC_DOCUMENT_DIR'):
    check(key + ' absent/empty', lambda key=key: not os.getenv(key))
check('DRIVE_KNOWLEDGE_FOLDER_ID format', lambda: re.fullmatch(
    r'[A-Za-z0-9_-]{1,200}', os.getenv('DRIVE_KNOWLEDGE_FOLDER_ID', '')))
check('DRIVE_AUTHORIZED_EMAIL format', lambda: re.fullmatch(
    r'[^\s@]+@[^\s@]+\.[^\s@]+', os.getenv('DRIVE_AUTHORIZED_EMAIL', '').strip().casefold()))
check('APP_ORIGIN format', origin_ok)
check('DRIVE_WEB_CLIENT_ID suffix', lambda: os.getenv('DRIVE_WEB_CLIENT_ID', '').endswith('.apps.googleusercontent.com'))
check('DRIVE_WEB_CLIENT_SECRET present', lambda: bool(os.getenv('DRIVE_WEB_CLIENT_SECRET')))
check('DRIVE_TOKEN_ENCRYPTION_KEY format', cipher_ok)
check('PORT format/range', lambda: 1 <= int(os.getenv('PORT', '8080')) <= 65535)

def database_url_ok():
    from sqlalchemy.engine import make_url
    p = make_url(os.environ['DATABASE_URL'])
    return (p.drivername in ('postgres', 'postgresql', 'postgresql+psycopg')
            and p.query.get('sslmode', 'require') == 'require')
u = check('DATABASE_URL driver/TLS format', database_url_ok)
r = check('actual runtime validation', runtime_ok)

def app_ok():
    from backend.main import app
    return app is not None
check('actual app import/construction', app_ok)

if a and b and u and r:
    engine = None
    try:
        def construct():
            global engine, factory
            from backend.database import database
            engine, factory = database()
            return True
        if check('database engine construction', construct):
            def connect():
                from sqlalchemy import text
                with engine.connect() as db:
                    return db.scalar(text('SELECT 1')) == 1
            if check('database connectivity/query', connect):
                def schema():
                    from backend.migrate import ready
                    return ready(engine)
                if check('schema revision/tables/columns/singletons', schema):
                    def admins():
                        from sqlalchemy import select, func
                        from backend.models import Administrator
                        with factory() as db:
                            return db.scalar(select(func.count()).select_from(Administrator).where(
                                Administrator.active.is_(True))) >= 2
                    def folder():
                        from backend.knowledge_models import KnowledgeState
                        with factory() as db:
                            state = db.get(KnowledgeState, 1)
                            return state is not None and state.folder_id == os.environ['DRIVE_KNOWLEDGE_FOLDER_ID']
                    check('at least two active administrators', admins)
                    check('stored approved folder matches environment', folder)
                else:
                    print('SKIP administrator/folder reads until schema passes')
            else:
                print('SKIP schema/administrator/folder reads until connectivity passes')
    finally:
        if engine is not None:
            check('database engine cleanup', lambda: (engine.dispose(), True)[1])
else:
    print('SKIP database reads until production Render profile, URL and runtime validation pass')
raise SystemExit(0 if all(results.values()) else 1)
PY
```

A field failure names the requirement without disclosing its value. `actual runtime validation` and `actual app import/construction` exercise the real code rather than relying only on this checklist. If individual fields pass but app construction fails, reproduce with the exact deployed image/dependency set and investigate imports/dependencies in an isolated environment using fictional configuration; do not unsuppress live production tracebacks. Connectivity failure means check endpoint/network rules, database availability, authentication and TLS privately; the diagnostic intentionally does not distinguish these by printing server errors.

## Later startup gates and shortest correction sequence

After that import/port block succeeds, Uvicorn enters the production lifespan. Its separate fixed error is `Production is not ready. Check database connectivity and execute the release command.` It covers any exception while checking:

1. Database connectivity and `backend.migrate.ready(engine)`: every registered table and column exists, schema revision row 1 equals revision **2**, and `AdminGuard(1)` and `SyncRequest(1)` exist.
2. At least **two active** administrator rows exist.
3. `KnowledgeState(1)` exists and its folder ID equals `DRIVE_KNOWLEDGE_FOLDER_ID` exactly.

Migrations and administrator provisioning therefore **must precede successful web startup**, but do not themselves generate the quoted import-time error. Engine creation is lazy; incorrect database credentials or an unreachable server normally fail in lifespan instead.

The shortest supported recovery is:

1. Fix the failed configuration labels using the [deployment environment table](render-deployment.md#4-exact-web-settings-and-environment) and rerun diagnostics. Use the final exact HTTPS service origin, Web OAuth settings, persistent PostgreSQL URL, and existing saved Fernet key. Do not regenerate an existing encryption key as a generic repair: it protects stored Drive grants.
2. Against that same database, run the documented **explicit `backend.release` procedure**: on a fresh empty administrator table use its hidden-password bootstrap wrapper for two distinct real administrators; otherwise run `python -m backend.release`. This single release migrates, initializes singleton/office state, binds the approved folder, optionally bootstraps, and verifies two active administrators. It preserves existing accounts; bootstrap does not repair an existing table with too few active administrators. In that case use the established administrator account-management/recovery process. Require exit 0 and `Production schema and administrator prerequisites verified.` Do not run `seed_test_accounts` or attach bootstrap secrets to the web service.
3. Rerun diagnostics with Render's environment, then restart/redeploy using the unchanged Docker command. Verify `/healthz` and `/readyz`. No provider switch or security bypass is indicated by this error alone.

**Google configuration is required before startup; completed Google authorization is not.** The startup checks validate local configuration only: they do not contact Google, test client credentials, check Google Console redirect/consent settings, refresh tokens, inspect a `DriveGrant`, or require indexed documents. After the server starts, an administrator connects the approved Google account in Knowledge Management, with the Web client's authorized redirect URI set to `APP_ORIGIN` plus `/api/drive/oauth/callback`, then performs the documented sync procedure. A missing/revoked grant or incorrectly configured Google Console blocks connection/sync, not web startup.

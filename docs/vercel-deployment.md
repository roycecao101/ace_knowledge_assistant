# Vercel compatibility and operator deployment guide

Prepared November 8, 2026. Nothing has been deployed. Existing Render commands,
Dockerfile, backend requirements, local Uvicorn entrypoint, and database schema
remain unchanged. See [Render fallback](render-deployment.md) for that deployment.

Local verification: 455 existing backend tests, nine new Vercel regression tests,
and 32 frontend tests passed. Backend tests ran in the existing Python 3.14
development environment; this does not certify Python 3.12/Linux wheel packaging
or a Vercel build. Only existing dependency deprecation warnings were observed.

## Compatibility findings and remaining blockers

| Area | Finding and resolution |
| --- | --- |
| Entrypoint | `backend.serve` starts Uvicorn, which Vercel must not run. `pyproject.toml` explicitly selects `backend.main:app`, which defines the top-level FastAPI `app`. Root `main.py` remains a compatibility import only. Vercel supports lifespan events. |
| Frontend | HTML and assets are served by existing FastAPI routes. The bundle explicitly includes `frontend/**`. No static hosting rewrite, `public/` copy, CDN promotion override, or CORS change is used. `/index.html` and `/admin.html` retain session/role checks; both login pages remain available. |
| Database | Internal Render hosts cannot be reached from Vercel. Use the complete external Render hostname with certificate-verified TLS. Missing DB configuration and SQLite fail closed. Pool size is one plus one overflow per instance on Vercel; scaling still needs a connection budget. |
| Filesystem | Documents download into memory; parsing uses byte streams. Accounts, sessions, OAuth state, encrypted refresh tokens, document index, Find & Fix Log, and sync counters remain in PostgreSQL. No persistent function filesystem writes are introduced. Python/dependency caches are ephemeral and must never be relied on. |
| Startup | Production lifespan verifies schema, two active administrators, and approved folder. It neither migrates nor seeds. Hosted development, local OAuth files, synthetic sources, and Vercel previews are rejected. |
| Release | Vercel has no Render pre-deploy equivalent here. Run `backend.release` explicitly from a trusted operator environment before production deployment. Never run it in Build Command or on HTTP startup. |
| Synchronization | Existing full-snapshot sync has a 540-second extraction deadline and 600-second lease, plus database publication work. It is not safely bounded to Hobby's function duration. Run the existing finite CLI outside Vercel; dashboard requests remain durable. No Vercel cron route or detached thread is added. |
| OAuth hostname | Exact `APP_ORIGIN` also binds encrypted grants. Add the final callback URI to Google, set the matching origin, then reconnect as administrator. No wildcard preview hosts or automatic Host-header-derived callbacks. |
| Privacy | Lexical search, verified quotations, office filtering, and Find & Fix review are unchanged. No question history, external LLM, public document route, fake response, or authentication bypass is added. Host-level logging/privacy verification remains a launch blocker for confidential use. |

Vercel documents its [FastAPI entrypoint, lifespan, static handling and function configuration](https://vercel.com/docs/frameworks/backend/fastapi).
Render documents [external PostgreSQL URLs, TLS and network access rules](https://render.com/docs/postgresql-creating-connecting).

### Static file collection warning

`Warning: FastAPI static file collection failed. Static files will not be served
from the CDN.` comes from Vercel's build-time application import for static
discovery. It does not by itself identify the underlying import error or mean
the frontend files are missing. This application serves frontend files through
FastAPI `FileResponse` routes, with middleware and dashboard session checks.
`[tool.vercel.fastapi.static] cdn = false` in `pyproject.toml` explicitly disables
CDN collection. `frontend/**` remains included in the function bundle.

Redeploy after this configuration change. Verify `/login.html`, `/style.css`,
and `/assets/ace-logo.webp` load and unauthenticated `/index.html` and
`/admin.html` redirect to their login pages. If the function returns 500/503,
inspect runtime logs for the sanitized startup error and required production
settings; disabling static collection does not repair runtime configuration.

## Resource assessment

Current standard [Vercel function limits](https://vercel.com/docs/functions/limitations)
include a 500 MB uncompressed Python bundle, Hobby 2 GB memory, and a 300-second
Hobby maximum duration with Fluid compute. Pro/Enterprise offer 4 GB memory and
800 seconds generally available; extended duration and large bundles have
additional eligibility requirements. This configuration requests **60 seconds**
for web requests; search already has a 40-second application timeout. Do not
increase duration to run a nine-minute sync on Hobby.

Dependencies include native PyMuPDF, psycopg, cryptography, Argon2 and lxml
(via python-docx), plus Google's client library/discovery data. There is no
model-weight, Torch, embedding service, OCR binary or external LLM dependency.
Python is selected as 3.12 by `.python-version`, matching the Render Dockerfile.
The root manifest references the existing backend manifest, so Render dependency
installation remains unchanged. It currently includes pytest; removing it alone
would not address the heavy native dependencies. `.vercelignore` excludes local
environments, private files, caches and development artifacts from uploads.

The existing macOS development environment is about 280 MB installed, including
test dependencies. This is only an estimate: Linux wheels, transitive versions,
runtime overhead and actual tracing determine Vercel's bundle. No Linux/Vercel
build or live capacity test has been performed. On your first authorized build,
check function size in build output (temporarily set
`VERCEL_ANALYZE_BUILD_OUTPUT=1` if needed), require it below 500 MB, and inspect
the included files. Do not enable paid/beta capacity merely to bypass a failure.
Dependencies retain existing version ranges, so builds are not fully reproducible.

Keep 2 GB memory initially. Argon2 uses 64 MiB **per concurrent password check**;
search loads database passages; extraction expands compressed documents. The
100 MB source snapshot limit is not a peak-RAM bound. Measure cold/warm search,
simultaneous logins and peak memory with an approved corpus. Retain Argon2
settings. Function request/response payloads also have a 4.5 MB standard limit;
document bytes are not uploaded through these API routes.

## Prepare the external database connection

1. In Render, open the existing PostgreSQL resource → **Info → Connections**.
   Copy **External Database URL**, never Internal Database URL. Keep Render's
   web service on its original internal connection.
2. Use the full public DNS hostname ending in `.render.com`, not an IP address.
   Set query parameters `sslmode=verify-full&sslrootcert=system` (use `?` for the
   first query parameter and `&` thereafter). Replace any existing sslmode;
   don't append duplicate parameters. Vercel's code defaults to these values
   and rejects weaker SSL modes and host/hostaddr/service overrides. Current
   psycopg binary/libpq must support system trust roots; verify connectivity
   before launch and never resolve certificate failures by disabling validation.
3. Render **Info → Networking**: allow Vercel's actual outbound addresses and
   the trusted operator/job runner. Standard serverless egress can change;
   select a supported fixed-egress option if a narrow IP allowlist is required.
   A policy that forbids broad external access without fixed egress is a
   deployment blocker. Do not silently open `0.0.0.0/0`. Render's internal
   service connection remains available independently of external rules.
4. Select a Vercel function region near the Render database in **Settings →
   Functions → Function Region**. Budget connections across Render, Vercel,
   release tasks and sync jobs. Two connections per instance is a local pool
   limit, not a global cap. Configure platform scaling/concurrency controls or
   a compatible external pooler before high traffic; preserve session-level
   advisory locks for the migration command (use a direct connection there).
5. Take an approved backup before release changes. Use existing access controls
   and secret storage. Never paste connection URLs into issues, commits or logs.

## Production environment variables

If logs report `FASTAPI_ENTRYPOINT_NOT_FOUND`, ensure the repository-root
`pyproject.toml` is included with `[tool.vercel]` and `entrypoint = "backend.main:app"`.
Keep this pointed at the backend module, which preserves startup checks and safe
diagnostics. Commit and push the configuration, then deploy the updated commit.

If logs report `could not import "backend/main.py"`, read the final exception line.
The entrypoint now reports the exception class and any missing required Vercel
setting names, never setting values or the underlying exception text. An empty
missing-settings list does not validate the values: invalid OAuth configuration,
database URLs/TLS settings, hosted development mode, and Preview deployments
still fail closed. Local `.env` files are not loaded by this entrypoint.
Do not fix these failures by bypassing production validation. A successful import
also does not prove database connectivity or the lifespan release prerequisites.

In Vercel **Project → Settings → Environment Variables**, scope all of the
following to **Production only**. Mark secret values sensitive. Leave Preview
and Development without production secrets. Set them before the first deployment.

| Name | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `APP_ORIGIN` | `https://YOUR-FINAL-HOSTNAME` with no trailing slash/path |
| `DATABASE_URL` | External Render URL with TLS settings above; secret |
| `KNOWLEDGE_SOURCE` | `drive` |
| `DRIVE_AUTH_MODE` | `oauth_web` |
| `SYNC_EXECUTOR` | `database` |
| `DRIVE_AUTHORIZED_EMAIL` | Existing approved Google identity |
| `DRIVE_KNOWLEDGE_FOLDER_ID` | Existing approved private folder ID |
| `DRIVE_WEB_CLIENT_ID` | Google **Web application** OAuth client ID |
| `DRIVE_WEB_CLIENT_SECRET` | Same client's secret; sensitive |
| `DRIVE_TOKEN_ENCRYPTION_KEY` | Existing private Fernet key; sensitive |
| `PYTHONDONTWRITEBYTECODE` | `1` |

Vercel supplies `VERCEL=1` and `VERCEL_ENV=production`; do not override them.
Do not set `BOOTSTRAP_ADMINS` on Vercel. Do not copy a local `.env`, Desktop
OAuth token, service-account key, synthetic document path, `PORT`, `RENDER`, or
Cloud Run job variables. Do not configure an AI Gateway or LLM key.

## Explicit release and two-administrator bootstrap

Run this **before** deploying, from a trusted machine or finite CI release job
using this exact checkout. A Render shell with the appropriate environment may
also run the same command. This is an operator action, not part of Vercel build.

Install dependencies in a clean Python 3.12 virtual environment using
`python -m pip install -r backend/requirements.txt`. Inject the production
variables from the table using your secret manager or a private shell outside
the repository; do not put secret assignments in shell history. Also set
`VERCEL=1` and `VERCEL_ENV=production` in that operator process to exercise the
same external-host/TLS checks. Remove inherited local-source/OAuth-file and
Render/Cloud Run variables. These commands do not automatically load `.env`.

For the existing database, first use the existing real administrator accounts.
**Do not rebootstrap or reset their credentials.** If and only if this is a
new empty administrator table, privately provide `BOOTSTRAP_ADMINS` to the
release process as a JSON array of exactly two objects, each with `id`, `name`,
and `password`. Use two distinct real administrators and distinct strong
passwords of at least 16 characters. Obtain/store these through the existing
private credential channel; never use `seed_test_accounts` in production.
Existing accounts are not overwritten when a bootstrap value is supplied.

```sh
python -m backend.release
```

Require exit code zero and `Production schema and administrator prerequisites
verified.` This runs the existing additive/idempotent, PostgreSQL-locked
migrations, configures the approved folder, optionally bootstraps an empty
administrator table, and requires at least two active administrators. Remove
the bootstrap binding immediately afterward, even on failure. Deploy only
after success. Repeat the explicit release command for future schema changes;
serialize release jobs. Never migrate on every cold start or expose a migration
HTTP endpoint. Keep Render on schema-compatible code; future destructive
migrations need a separate rollback plan.

## Exact Vercel dashboard setup (manual; not executed)

1. Choose the stable project hostname/custom domain first. It must match
   `APP_ORIGIN`. A generated per-deployment URL is not the OAuth origin. If the
   chosen project name is unavailable, update the origin and Google callback
   to the actual assigned stable hostname before proceeding.
2. **Add New → Project → Import Git Repository**. Select this repository and
   branch. Set **Root Directory** to the repository root (`.`), not `backend`
   or `frontend`. Set **Framework Preset: FastAPI**. Python 3.12 comes from
   `.python-version`.
3. Under **Build and Output Settings**, leave framework defaults for install,
   build and output. No npm build, `backend.serve`, Uvicorn Start Command,
   release command, or frontend output directory. The root `requirements.txt`
   is the dependency manifest; `backend/main.py` is the entrypoint.
4. Add the Production-only environment variables above. Keep Fluid compute
   enabled and default 2 GB memory. `vercel.json` sets the web function duration
   to 60 seconds and includes the frontend. Do not add wildcard rewrites,
   `public/` copies, or `cdn: true` promotion of authenticated pages.
5. Before approving **Deploy**, finish the explicit release step and configure
   Google OAuth below. Git imports can immediately deploy when you click;
   this guide does not authorize that action automatically.
6. After a manual deployment, inspect **Settings → Domains** for the stable
   production domain and **Functions** for the single `main.py` function and
   selected region. If the hostname differs, correct `APP_ORIGIN` and Google
   callback and redeploy. Alias/per-deployment hosts are intentionally rejected
   by the existing exact Host check; do not broaden trusted hosts.
7. Inspect **Settings → Git** automatic-deployment settings. Keep production
   publication manually controlled while trying Vercel. Disable unnecessary
   preview deployments, or let them fail closed with no production secrets;
   this adapter rejects `VERCEL_ENV=preview`. Don't add production credentials
   to Preview to fix those failures.

## Google Drive Web OAuth

In Google Cloud Console **Google Auth Platform → Clients → your Web application
client** (or **APIs & Services → Credentials → OAuth 2.0 Client IDs**):

- Add the exact authorized redirect URI:
  `https://YOUR-FINAL-HOSTNAME/api/drive/oauth/callback`.
- Retain the existing Render callback for fallback. No wildcard URI is allowed.
  This is server-side OAuth; no browser Google SDK or JavaScript origin is
  needed by this application. Keep Drive API enabled, the existing readonly
  scope, consent restrictions and approved identity/folder permissions.
- Set Vercel and the sync runner to the same client ID, secret, encryption key,
  approved identity, folder, and **Vercel** `APP_ORIGIN`.
- Sign in at `/admin-login.html` and connect the approved identity in Knowledge
  Management. The old grant's binding includes the Render origin; merely copying
  the key and client secret cannot make it valid on Vercel. Reconnect rather
  than editing token rows or weakening the binding.

State, PKCE, one-use database consent, browser continuity, active administrator
validation, server-side token refresh and encrypted PostgreSQL grants remain
unchanged. The callback uses its existing temporary Secure/HttpOnly/Lax cookie;
application sessions remain Secure/HttpOnly/Strict. Employees cannot manage
connections. Never make the Drive folder or files public.

## Safe synchronization without an always-running worker

The supported minimal setup is **Vercel web + Render PostgreSQL + finite
operator/scheduled sync command**. It is not a fully Vercel-only ingestion
deployment. The existing local development scheduler remains development-only.

After OAuth reconnection, use the trusted environment described in the release
section, with `APP_ORIGIN` matching Vercel. Click Re-sync as administrator, then:

```sh
python -m backend.sync --if-due
```

This reads the durable request counter, claims the existing database lease,
downloads private Drive files into memory, verifies the approved identity,
extracts/indexes, publishes the discrepancy scan and new snapshot atomically,
and acknowledges only requests captured at the start of a successful run.
Requests arriving during execution remain queued. Failures keep the old index
and leave requests pending. An interrupted process releases no false success;
the lease expires after ten minutes so a later execution can retry. Never
delete a lease or mark queue counters complete manually.

For automation, schedule that **same command** on a trusted job runner with
the same secrets, dependency versions, external database access and memory.
Run every five minutes if prompt processing of dashboard requests is needed;
it also refreshes when the last success is at least 23 hours old. Serialize jobs,
allow at least 15 minutes per invocation, and monitor nonzero exits and the
dashboard's last-success timestamp. A busy lease is a safe skipped invocation;
the next run retries. This is a finite process that exits, not a continuously
running worker. No external job runner is provisioned by these changes.

For a manual-only trial, run the command after each requested refresh and at
least daily; the UI's `scheduled` response means **queued**, not completed.
Don't promise automatic/fresh synchronization until a runner is actually set up.

[Vercel Cron](https://vercel.com/docs/schedules/cron-jobs/usage-and-pricing)
invokes HTTP functions and inherits function limits. Hobby permits daily jobs
with hour-level scheduling precision; it cannot poll this queue every five
minutes. Cron alone neither runs the CLI nor extends its deadline. This patch
deliberately registers no cron endpoint. A future Vercel-only implementation
needs resumable bounded batches/durable workflow or queue consumers, protected
triggers, idempotent retries and publication that preserves the current lease
guarantees; moving `SyncService.run()` into `BackgroundTasks` is insufficient.

## Verification, privacy and Render fallback

Before confidential use, verify host/edge/runtime/database/runner logs exclude
question bodies, document text, credentials, tokens and OAuth callback query
values. The app suppresses private errors and does not log question history,
but Vercel's adapter/edge logging is outside `backend.serve`'s disabled Uvicorn
access logs. Confirm retention, access and redaction with the provider; if
required suppression is unavailable, confidential production use is blocked.
Do not enable request-body tracing, session replay, third-party analytics or
query-bearing log drains. Follow the existing application's data/privacy policy.

Rehearse at the final HTTPS hostname:

1. `/healthz` and `/readyz` return 200. Both login pages and stylesheet/logo
   assets load. Unauthenticated `/index.html` and `/admin.html` redirect to
   their appropriate logins. Wrong Host and cross-origin writes fail.
2. Verify both real administrators and authorized employees, failed credentials,
   logout/revocation, employee denial from admin routes, session-bound CSRF,
   and the minimum-two-active-admin guard. No preview or API docs are exposed.
3. Reconnect Google as admin; confirm readonly consent and approved identity.
   Run queued synchronization; verify last success and document counts. Search
   approved known material, inspect exact evidence, office filtering and Find &
   Fix Log. An unsupported question must retain the existing conservative answer.
4. Cold restart/redeploy: accounts, grants, queue counters, documents and index
   must survive in PostgreSQL. Test concurrent sync requests and a failed sync
   using approved nonconfidential fixtures; the prior snapshot must survive.
5. Inspect bundle size, peak RAM, cold response times, connection usage, scheduler
   outcomes and provider log controls. Local tests do not prove these cloud gates.

Leave Render's service, database, environment, Google callback and deployment
commands intact. To fall back, direct users to its original hostname (or restore
the custom domain and matching origin), configure the sync runner back to that
origin, and reconnect Google through the Render admin UI. One database has one
Drive grant: a reconnect on either host replaces it, so only one host should own
active Drive synchronization at a time. Searches can still read the shared
published index. Do not run conflicting schedulers; do not disconnect/revoke
the grant from the inactive host. Keep the same encryption key and client
configuration privately available. No database copy, credential reset, or
destructive schema change is needed for this compatibility patch.

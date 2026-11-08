# Free Render demonstration deployment

Prepared November 8, 2026. This replaces the paid Render plan. **Nothing has been provisioned, pushed, connected to Google, or deployed.** The steps below are for the operator to run manually. Use only fictional identities/documents and newly created demo credentials. Keep the existing local `.env`, SQLite database, Ace Drive account, documents and OAuth files untouched.

## Decision and cost boundary

Use **one Free Docker Web Service + one Free Render PostgreSQL database**, in a free workspace. Estimated infrastructure cost: **$0 within included usage**. Select the literal **Free** compute option for both resources. Do not select a paid plan, paid workspace, disk, worker, cron job, backup service, external scheduler, custom domain purchase or AI API. There is no Blueprint or automatic deployment workflow.

For a strict no-charge demo, use a free workspace without a payment method; do not attach billing to the demo Google project. Render can bill bandwidth/build overages when a payment method exists. If free eligibility is unavailable, a card/upgrade is required, or quota is exhausted, stop and leave the demo undeployed/suspended; do not fall back to paid resources. Do not change billing for an existing shared workspace: use a separate eligible demo workspace.

Compatibility is based on the repository's PostgreSQL adapter and production configuration, not a completed Render rehearsal. Free PostgreSQL supports the required relational storage. Keep the corpus tiny and presentation traffic modest; memory, build success and concurrent login/search performance still require live rehearsal. Retain one application worker and the existing Argon2 settings.

## What works and what is limited

| Capability | Free demonstration behavior |
| --- | --- |
| Employee and admin sign-in | Existing production authentication, private credentials, persisted accounts/sessions in PostgreSQL |
| Employee/admin/office management | Existing APIs, one-time random employee PINs, session revocation and two-active-admin minimum |
| Search, office/category filtering, verified quotes | Existing pipeline, after the fictional corpus is manually synchronized |
| Find & Fix Log | Existing scan and verified evidence comparison after each successful manual sync; human review remains required |
| Drive Web OAuth and manual ingestion | Supported with a separate demo Google account/project/folder and operator CLI below |
| Dashboard Re-sync | Persists a request; **no worker consumes it automatically**. Operator runs `python -m backend.sync --if-due` |
| Scheduled Google Drive synchronization | **Unavailable in this plan.** Existing hosted scheduling needs a separate executor. Render Cron Jobs have a $1 monthly minimum; none is created. Sleeping web services cannot supply reliable scheduling. No keep-alive pings or scheduler workaround is configured |
| Migrations/first account setup | Run explicitly from your computer against the demo database, before starting the web service; no paid pre-deploy step |
| Render shell / one-off jobs / persistent disk | Unavailable on free web instances; not needed for this procedure |
| Always-on availability | Web service sleeps after 15 idle minutes; waking takes about a minute. Restarts can interrupt requests |
| Database lifetime/recovery | Free PostgreSQL: 1 GB, expires after 30 days, inaccessible at expiry, deleted after a further 14 days; no managed backups. Only one free database per workspace |
| Long-term hosting | **Not provided by this expiring database plan.** Before expiry, retire the demo or manually recreate/reseed an eligible free database; never upgrade automatically |

Free web hours are shared across the workspace (750/month); exhausted hours suspend services. Bandwidth/build limits also apply. Accounts/indexes survive web restarts because they are in PostgreSQL, but are lost when the database is deleted. All these are host limits; no application feature or security control is removed. See [Render free instances](https://render.com/docs/free), [pre-deploy availability](https://render.com/docs/deploys#pre-deploy-command) and [cron billing](https://render.com/docs/cronjobs#compute-plans-and-billing).

## 1. Review the source and prepare fictional documents

Run from the repository root using your existing virtual environment:

```sh
source .venv/bin/activate
python scripts/check_deployment_source.py
python -m pytest -q
node --test tests/test_auth_client.cjs tests/test_employee_search_ui.cjs tests/test_admin_dashboard_ui.cjs
git diff --check
```

The audit reports filenames/categories only. It does not scan Git history or detect every secret. Review source and full Git history privately before connecting the private repository to Render. Remove and rotate any previously committed secret using your organization's process. Do not make the repository public. Commit/push reviewed code yourself only when ready; this guide performs neither operation.

Generate a small, wholly fictional corpus in a new temporary directory:

```sh
DEMO_DOCUMENT_DIR=$(mktemp -d /tmp/ace-fictional-demo.XXXXXX)
export DEMO_DOCUMENT_DIR
python scripts/create_synthetic_documents.py "$DEMO_DOCUMENT_DIR"
python - <<'PY'
import os
from pathlib import Path
from docx import Document
root = Path(os.environ['DEMO_DOCUMENT_DIR'])
for label, day in [('A', 'Monday'), ('B', 'Tuesday')]:
    doc = Document()
    doc.add_paragraph(f'Equipment inspection occurs every {day} before the fictional office opens.')
    doc.save(root / f'Fictional Inspection {label}.docx')
print('Fictional demo files created in:', root)
PY
```

This creates five documents: training DOCX, equipment PDF, intentionally unreadable PDF, and two conflicting inspection DOCX files. None is an Ace policy. Keep them outside Git and the container image. Upload **only those five PDF/DOCX files** through Google Drive's own interface into a new folder named `FICTIONAL DEMO ONLY` in a dedicated demo account. Do not upload the `.synthetic-only` marker, shortcuts, copied Ace policies or anything from the existing local corpus. Leave files at the folder root; recognized category subfolders can be used later. No browser-upload endpoint is added to the application.

## 2. Prepare separate, free Google authorization

The unchanged production app requires `KNOWLEDGE_SOURCE=drive` and valid Web OAuth configuration even for an initially empty demo. A free Google account's Drive storage and standard Drive API usage within quota are sufficient for these fixtures; no Workspace purchase, Google hosting, Cloud SQL, Cloud Run or service account is required. Use a separate demo project without a billing account. Google documents potential charges above API thresholds, so stay within the free quota and stop if billing is required: [Drive API limits/pricing](https://developers.google.com/workspace/drive/api/guides/limits).

1. Use a dedicated demo Google account containing only fictional material. Create a separate demo Google Cloud project; enable **Google Drive API** only.
2. Configure Google Auth Platform with **External / Testing** and add that demo Google account as a test user. Do not add judges as Google test users: they use the application's employee/admin login. Testing refresh tokens for this scope normally expire in seven days; reconnect before rehearsal/presentation as necessary. Follow any Google consent or verification restrictions; do not bypass them. See [Google refresh token expiration](https://developers.google.com/identity/protocols/oauth2#expiration).
3. Create an OAuth client of type **Web application**, dedicated to this demo. Register exactly `https://YOUR-SERVICE.onrender.com/api/drive/oauth/callback`. Use the actual available service hostname; if it changes, update the client, Render configuration and operator shell, then reconnect.
4. Record the demo account email, demo folder ID, new client ID and client secret privately. Do not reuse the existing Desktop client/token or Ace credentials. The app requests `drive.readonly`, which is account-wide API access; the app additionally enforces the approved folder tree, checks ancestry and ignores shortcuts. This is why the separate account matters.

Generate a new encryption key privately in the activated environment:

```sh
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Store it in your password manager and Render, not Git/chat. Reuse the same key for every operator command/redeploy. Refresh grants and consent verifiers are encrypted in the database; access tokens remain in backend memory.

## 3. Exact database settings

When you choose to begin manual provisioning: Render dashboard → **New → Postgres**.

| Setting | Value |
| --- | --- |
| Name | `ace-demo-db` |
| Database | `ace_demo` |
| User | Let Render generate it |
| Region | `Virginia` (`virginia`); use the same region for web |
| PostgreSQL version | `17` |
| Compute plan | **Free** |
| Storage | Included free 1 GB; no paid storage or autoscaling |
| External access | Remove `0.0.0.0/0`; allow only your current public IPv4 with `/32` during operator commands, then remove all rules |

Record the displayed expiration date; schedule the demonstration before it. The **Internal Database URL** belongs in Render. The **External Database URL** is used only from your computer. Never paste either URL into Git, commands containing literal passwords, chat, screenshots or logs. Render supports same-region internal connections with external access disabled. See [Postgres networking and access rules](https://render.com/docs/postgresql-creating-connecting).

The existing Render adapter enforces `sslmode=require`: encrypted transport with no plaintext fallback. Internal TLS uses self-signed certificates, so this is not certificate identity verification. This preserves the existing adapter; it is suitable only within the approved fictional-demo boundary, not a claim that confidential deployment has been approved.

## 4. Exact web settings and environment

These are settings to prepare; **Create Web Service starts a deployment**. Complete the database initialization in section 5 before clicking it. Choose an available service name/hostname in advance and use it consistently. If the actual hostname differs, correct the origin/OAuth settings before attempting login/consent.

Render → **New → Web Service**, private repository, reviewed release branch:

| Setting | Exact value |
| --- | --- |
| Name | `ace-demo` (or available equivalent) |
| Region | Same as database: Virginia |
| Runtime / language | **Docker** |
| Root Directory | Empty (repository root) |
| Dockerfile Path | `./Dockerfile` |
| Docker Build Context | `.` |
| Build Command | Unset; Docker builds the image. Dependency installation is `pip install --no-cache-dir -r backend/requirements.txt` inside the Dockerfile |
| Pre-Deploy Command | **Empty**; not available on Free |
| Docker Command | `python -m backend.serve` (also the Dockerfile default) |
| Health Check Path | `/readyz` |
| Compute plan | **Free** |
| Instances | `1` |
| Auto-Deploy | **Off** |
| Pull request previews | Disabled |
| Persistent disk | None |

Set only these application variables through the dashboard, directly on this demo service:

| Variable | Value |
| --- | --- |
| `APP_ENV` | `production` (also for this demo; never `development`) |
| `APP_ORIGIN` | `https://YOUR-SERVICE.onrender.com`, exact hostname, no trailing slash |
| `DATABASE_URL` | Demo database's **Internal Database URL** |
| `KNOWLEDGE_SOURCE` | `drive` |
| `DRIVE_AUTH_MODE` | `oauth_web` |
| `SYNC_EXECUTOR` | `database` (durable requests; manual operator consumes them) |
| `DRIVE_AUTHORIZED_EMAIL` | Dedicated demo Google account email |
| `DRIVE_KNOWLEDGE_FOLDER_ID` | New fictional-demo folder ID |
| `DRIVE_WEB_CLIENT_ID` | New demo Web client ID ending `.apps.googleusercontent.com` |
| `DRIVE_WEB_CLIENT_SECRET` | New demo Web client secret |
| `DRIVE_TOKEN_ENCRYPTION_KEY` | New demo Fernet key generated above |

Render supplies `RENDER` and `PORT`; do not override them on the service. No `SECRET_KEY` or JWT key is used. Do not set `BOOTSTRAP_ADMINS` on Render; setup is performed only by the local release command below. Do not import `.env`, upload secret files or set `GOOGLE_APPLICATION_CREDENTIALS`, Desktop OAuth paths, `SYNTHETIC_DOCUMENT_DIR`, Cloud SQL variables or `SYNC_JOB_RESOURCE`.

The Docker context is deny-by-default and copies only application Python, requirements, public frontend assets and the logo. Keep `.dockerignore` intact: no `COPY . .`, local documents, databases, tokens or secret build arguments. The frontend and API share one HTTPS origin, so no CORS or separate static hosting is required.

## 5. Explicit database initialization from your computer

Free services lack shell access, one-off jobs and pre-deploy commands. Run the existing release command locally against the **new empty demo PostgreSQL**, without changing the application entrypoint, enabling development mode or using the local fixture-account seed.

Temporarily allow only your public IP in the database access rules. Open a separate clean zsh shell so existing Ace environment values cannot carry over. These commands are for macOS/zsh, from this repository root:

```sh
env -i HOME="$HOME" PATH="$PATH" TERM="${TERM:-xterm}" /bin/zsh -f
cd /Users/royce/ace_knowledge_assistant
source .venv/bin/activate
export APP_ENV=production
export RENDER=true
export KNOWLEDGE_SOURCE=drive
export DRIVE_AUTH_MODE=oauth_web
export SYNC_EXECUTOR=database
export APP_ORIGIN=https://YOUR-SERVICE.onrender.com
export DRIVE_AUTHORIZED_EMAIL=YOUR_DEMO_ACCOUNT_EMAIL
export DRIVE_KNOWLEDGE_FOLDER_ID=YOUR_DEMO_FOLDER_ID
export DRIVE_WEB_CLIENT_ID=YOUR_DEMO_WEB_CLIENT_ID.apps.googleusercontent.com
read -rs 'DATABASE_URL?Paste demo EXTERNAL Database URL (hidden): '
export DATABASE_URL
print
read -rs 'DRIVE_WEB_CLIENT_SECRET?Paste demo Web client secret (hidden): '
export DRIVE_WEB_CLIENT_SECRET
print
read -rs 'DRIVE_TOKEN_ENCRYPTION_KEY?Paste the saved demo Fernet key (hidden): '
export DRIVE_TOKEN_ENCRYPTION_KEY
print
```

Replace the four nonsecret placeholders with the same values prepared for Render. The URL must be the newly created demo database, not a production database; keep its full hostname. Leave `sslmode` absent or set to `require`; the adapter adds/enforces `require`. `RENDER=true` in this operator shell deliberately applies the same Render production guards/TLS policy. No command loads `.env`.

For the **first initialization only**, run this wrapper around `backend.release`. It creates exactly two fictional administrators using privately chosen passwords (distinct, 16–256 characters); prompts do not echo credentials or store them in shell history:

```sh
python - <<'PY'
import getpass
import json
import os
from backend.release import main
entries = []
for identifier, name in [('demo-morgan', 'Morgan Fictional Demo'),
                         ('demo-avery', 'Avery Fictional Demo')]:
    password = getpass.getpass(f'New private password for {identifier}: ')
    confirmation = getpass.getpass('Confirm password: ')
    if password != confirmation or not 16 <= len(password) <= 256:
        raise SystemExit('Passwords must match and contain 16–256 characters.')
    entries.append({'id': identifier, 'name': name, 'password': password})
if entries[0]['password'] == entries[1]['password']:
    raise SystemExit('Choose distinct passwords.')
os.environ['BOOTSTRAP_ADMINS'] = json.dumps(entries)
raise SystemExit(main())
PY
```

Require exit status 0 and `Production schema and administrator prerequisites verified.` before creating the web service. The release migrates under the existing PostgreSQL advisory lock, initializes office/queue state, configures the demo folder and uses the existing administrator bootstrap/hash path. It does not contact Google or import documents. Never run `backend.seed_test_accounts` against the hosted database; its published local passwords are unsuitable for the public demo.

For subsequent reviewed schema releases, in the same clean configured operator environment, run only:

```sh
python -m backend.release
```

This is also the explicit initialization retry after successful bootstrap; it preserves existing accounts. Do not change the Docker Command to run migrations or seed accounts on every restart. Remove all external database IP rules after each operation. Exit the clean shell when finished; repeat the clean-shell configuration when needed later.

## 6. Manual first deployment and working logins

After successful initialization and review of every setting, **you** can click **Create Web Service**. Later releases use **Manual Deploy → Deploy latest commit** with Auto-Deploy still Off. No hook, CI deployment or API deployment command is configured here.

1. Wait for `/readyz` to return HTTP 200. `/healthz` checks process liveness only. On configuration/migration failure, fix values or run the explicit release; do not weaken guards.
2. Open `https://YOUR-SERVICE.onrender.com/admin-login.html`. Sign in as `demo-morgan` with its private password, then separately verify `demo-avery`.
3. In Employee Management create `DEMO-ALP-01` / `Jordan Fictional Demo` / `Alpharetta`, and `DEMO-NOR-01` / `Riley Fictional Demo` / `Norcross`. Save each generated eight-digit PIN privately when its one-time dialog appears. Use the normal reset action if missed. No fixed demo PIN or authentication bypass is introduced.
4. In a separate browser profile/private window, open `https://YOUR-SERVICE.onrender.com/login.html` and sign in with an employee ID and its generated PIN. Verify the expected home office. One browser profile shares a single account session, so switching accounts there replaces its previous login.
5. From admin Knowledge Management, connect **only the dedicated demo Google account**. Google consent verifies identity and folder inventory; consent itself does not ingest documents. Cancel if the selected account/folder contains real material.
6. Click **Re-sync**. Complete the manual sync procedure below, then refresh Knowledge Management and Find & Fix Log. Do not present the queued response as a finished synchronization.

Logins work before ingestion; employee search will have no approved results until the first successful sync. No standalone frontend upload, synthetic preview, hard-coded hosted credentials or local-document mode is enabled.

## 7. Manual Google Drive synchronization — no scheduled service

There is **no scheduled synchronization on this free deployment**. Re-sync buttons return HTTP 202 and queue a request in PostgreSQL; they cannot execute it alone. The UI's existing “scheduled” message means queued, not that a cron job exists. Explain this to demonstration administrators.

After Google authorization, temporarily allow your operator IP again. In the clean shell from section 5 (same demo OAuth configuration and key, **External** Database URL), run:

```sh
python -m backend.sync --if-due
```

This consumes pending requests and records their completion after successful publication. With no pending request it also runs if the last success is at least 23 hours old. It is a single invocation that exits, **not a scheduler**. To force a manual refresh without clicking Re-sync, run:

```sh
python -m backend.sync
```

The forced command updates the index but does not acknowledge queue counters; use `--if-due` after a dashboard request. Require `Synchronization succeeded.` and verify the new last-success timestamp/document counts in the dashboard. Failures retain the previous index; correct authorization or configuration, then retry. Remove all external IP rules and exit the clean shell afterward.

This runs the existing Drive adapter, extraction, ranking/indexing, quotation verification, discrepancy scan, lease and atomic publication. No document/query text goes to an external AI model. Synchronization executes on your computer and writes the demo index to PostgreSQL; it is not performed inside the sleeping web service. Never schedule this against real Ace data. A free external scheduler could be engineered separately, but is not configured or required here. Reliable Render-managed scheduled execution would require paid compute and remains excluded.

## 8. Rehearsal, privacy and retirement

Before sharing the link:

- Verify both administrator logins and both employees; verify wrong credentials fail, employees cannot open admin APIs, logout revokes access, and fewer than two active admins cannot be left.
- Verify successful search for `When do employees complete telescope orientation?` and Norcross's fictional assembly point. Confirm exact quotes, filenames/headings/pages and office filtering. Use All Categories for the root-level fixture files.
- Check the intentionally unreadable PDF in Unreadable Files. Ask `When does equipment inspection occur?`; inspect the fictional contradictory evidence in Find & Fix Log. Managers choose corrections; the application must not choose the “correct” policy automatically. Correct a fictional source in Drive and repeat manual sync to demonstrate resolution.
- Verify mobile login/search, dashboard navigation, one-time PIN handling and the manual Re-sync workflow. Test a manual web restart: accounts and the published index must persist. Rehearse after idle sleep and open the site shortly before presenting; do not promise immediate cold responses or use keep-alive automation.
- Check free resource usage and expiration. If the process runs out of memory, reduce only the fictional corpus/concurrent presentation load; retain hashing strength and all security controls. Do not select a paid plan to fix it.

Production behavior stays enabled: HTTPS origin/Host checks, Secure HttpOnly SameSite=Strict `__Host-` session cookie, server-side hashed opaque sessions, session-bound CSRF, role checks, login lockouts, Argon2id, credential/session invalidation, two-admin guard, office restrictions and disabled preview/API docs. Web OAuth retains state, PKCE, one-use browser continuity and encrypted grants. The temporary OAuth consent cookie alone uses SameSite=Lax. Application access logs are disabled and private errors suppressed.

Provider logs are separate: verify that edge/database logs exclude credential bodies, OAuth callback query strings, document/query contents and bound values. Existing local production privacy/logging approval requirements remain unresolved until verified with the host; fictional data does not justify exposing credentials. No PHI, real employees, real Ace policies or production grants belong in this demo. Restrict Render/repository access and enable MFA. Preserve private credential delivery and expired-session/login-attempt cleanup obligations from the application's operational policy.

Before database expiry, retire the demo or explicitly rebuild it on an eligible Free database: initialize schema/admins anew, update both connection URLs, create employees through the dashboard, reconnect the demo Drive account and re-sync. Old sessions and generated PINs do not transfer. Do not copy the real/local database to recover a demo. Reproducible fictional fixtures replace the need for a paid backup service. After the presentation, manually remove demo services/database and revoke the demo Google grant/client if no longer needed; this plan does not delete anything automatically.

Local tests validate application behavior, not Render availability, Google consent permissions, provider logs or measured free-instance capacity. A live manual rehearsal is still required. No cloud action is authorized or executed by applying this documentation change.

Preparation verification on November 8, 2026: **455 backend tests and 32 frontend tests passed** (existing dependency deprecation warnings only). Current-source audit and `git diff --check` passed. All documented zsh blocks and embedded Python parsed successfully. The exact documented fictional generator was exercised with a temporary SQLite database and the existing development-only source adapter: four documents indexed, one intentionally unreadable, orientation search succeeded, and inspection search/Find & Fix reported verified contradictory evidence. No real corpus, existing database or credentials were used in that fixture check. No application/security code was changed.

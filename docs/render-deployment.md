# Render production deployment

Prepared November 8, 2026. Nothing in this change deploys, pushes, connects to Google, reads private source documents, or changes the local `.env`/SQLite database. Use the manual dashboard procedure below. There is intentionally no one-click deployment button.

## New Web Service handoff

Select **Docker** on the current form, with the repository root left empty, Dockerfile `./Dockerfile`, and build context `.`. There is **no Render Build Command** for this runtime: Render builds the Dockerfile automatically. The Dockerfile's dependency-install command is `pip install --no-cache-dir -r backend/requirements.txt`; do not paste it into a native Python service configuration as a substitute for this Docker setup. Set **Pre-Deploy Command** to `python -m backend.release`, **Docker Command** to `python -m backend.serve`, and **Health Check Path** to `/readyz`. Keep automatic deploys and previews disabled. Do not initiate deployment until the prerequisites below are resolved.

The local code already contains the non-root Docker image, production configuration guards, PostgreSQL adapter, explicit schema release and two-administrator bootstrap, Web OAuth with encrypted grants, readiness checks, and a durable sync queue. The operator must still provision Render resources, configure the Google Web client and runtime secrets, approve data handling/logging, and perform a synthetic staging rehearsal.

Read-only GitHub verification on November 8, 2026 found `main` at `411e8dcc3e9e0ad84bae750f28634ee8518b99a6` (`Integrated Ace's official logo`). The deployment changes are uncommitted local modifications/new files and are **not pushed**. Review and commit/push them before Render builds the selected branch. No GitHub push or Render deployment was performed during preparation.

### Initial cost estimate

For the recommended one-instance web service and a small approved corpus:

| Resource | Recommended compute | Estimated USD/month |
| --- | --- | --- |
| Web | `1c-2g`, legacy Standard; 1 CPU / 2 GB RAM | $25 |
| Postgres | Paid `0.1c-256mb`, legacy Basic-256mb | $6 compute |
| Postgres storage | 5 GB | Budget $1.50 at $0.30/GB-month |
| Sync cron | `1c-2g`, legacy Standard | $0.00058 per active minute, $1 monthly minimum |

Budget **about $33.50/month at the cron minimum**, plus workspace subscription, excess usage, taxes and any larger compute/storage. A paid workspace is separate from paid service instances; if the organization selects the $25/month Pro workspace, budget about $58.50/month at the cron minimum. Actual cron runtime includes every five-minute check and document processing; this is not a measured workload estimate. For example, 3,000 active minutes cost about $1.74 for cron instead of $1. Confirm the displayed quote before provisioning. Prices checked against [Render pricing](https://render.com/pricing), [Render's current service price examples](https://render.com/articles/set-up-self-hosted-github-actions-runners-on-render), and [cron billing](https://render.com/docs/cronjobs) on November 8, 2026. Downsize only after memory/load rehearsal.

## Deployment blockers and prerequisites

Resolve these before importing confidential material or sharing access:

1. **Google authorization:** Desktop OAuth and Google Cloud attached ADC cannot be reused on Render. Create a separate **Web application** client and an organization-approved consent configuration. The implemented `oauth_web` flow uses administrator initiation, CSRF, a one-use state, PKCE, a browser nonce, an active administrator session, and the approved account/folder. No service-account key or domain-wide delegation is needed. Keep the Desktop client and local grant on your computer.
2. **Durable storage:** provision paid Render Postgres. Render web/cron filesystems are ephemeral and are not the database. Do not use SQLite, a free expiring database, or a copied local database in the image. The application rejects production SQLite. All accounts, office catalog, sessions, knowledge passages/indexes, Find & Fix state, encrypted Drive grants and sync requests live in Postgres.
3. **Privacy approval and logging:** the owner must approve the Render region, processors, account access and retention for the permitted Buildathon data. No PHI, patient information or unapproved documents. Verify with Render that edge/request logs exclude bodies, credentials and OAuth callback query strings, and that Postgres logs exclude bound parameter values and document/query contents. Render documents slow-query SQL logging; application log suppression does **not** control database or edge logging. If the required exclusions cannot be guaranteed, confidential production deployment is blocked. Rehearse with fictional documents only until resolved. Do not relax Buildathon requirements to use this host.
4. **Real accounts:** the initial production database needs at least two real administrators. No known test credentials are seeded. Create separate employee/judge accounts privately after initial setup.
5. **Live verification:** an operator must verify Google consent, Drive access, cron execution, PostgreSQL behavior, log exclusions and persistence on Render before judging. Local mocked tests cannot establish external account permissions or host behavior.

Read-only Drive consent grants API read access across the authorized account; the application additionally restricts every inventory/download to the approved folder tree, rechecks ancestry, and ignores shortcuts. Use a dedicated organization-controlled Google account with access only to the approved knowledge material. Do not authorize a personal account containing unrelated confidential material. If Workspace policy or Google verification prevents this Web OAuth strategy, stop and obtain organizational approval; do not substitute a Desktop token or create a JSON service-account key.

Google recommends library-based web-server OAuth and secure server-side token storage: [Web server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server), [OAuth security practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices). Render documents [database encryption, access and logs](https://render.com/docs/postgresql-creating-connecting).

## Architecture and security behavior

One Docker **Web Service** serves the existing frontend and `/api/*` from one HTTPS origin. No separate static site, CORS origin, frontend API hostname, file upload or public document directory is introduced. Styling, employee/admin authentication, session-bound CSRF, office filtering, verified quotations and Find & Fix behavior are retained. Production disables preview, interactive API docs, local sources, in-process scheduling and development account utilities.

`python -m backend.serve` listens on `0.0.0.0:$PORT` (8080 only as a fallback), with one worker, no reload, no application access logs, and no trust in client-supplied forwarded headers. Render terminates HTTPS. Secure `__Host-` session cookies remain HttpOnly and SameSite=Strict. The temporary Google-consent cookie is Secure/HttpOnly/SameSite=Lax so the callback can verify browser continuity; it does not authenticate application requests.

A separate Docker **Cron Job**, every five minutes, runs `python -m backend.sync --if-due`. Administrator Re-sync requests increment a persistent database queue. The job also synchronizes when the last success is at least 23 hours old. It exits immediately when current. A database lease prevents overlapping publishers, and atomic publication retains the previous searchable generation after failures. Pending requests survive restarts and retry after failures; a request arriving during a run remains pending. A crashed run's lease expires after ten minutes. This schedule depends on the cron job being enabled and healthy; it is not an exact wall-clock daily schedule.

Drive refresh tokens and PKCE verifiers are Fernet-encrypted in the private database. The encryption key and Web client secret are runtime secrets in Render, separate from the database. Access tokens exist only in backend memory. Consent validates Google account identity and performs metadata-only folder inventory before storing a grant. It does not ingest documents. All extraction, retrieval and discrepancy analysis remain local to your service; no external AI API receives document text or questions.

## 1. Review and push the code safely

Keep your existing local environment. Do not replace `.env`, change your local OAuth client, or run production commands against `backend/ace.db`.

Run locally:

```sh
python scripts/check_deployment_source.py
python -m pytest -q
node --test tests/test_auth_client.cjs tests/test_employee_search_ui.cjs tests/test_admin_dashboard_ui.cjs
git diff --check
```

Use your existing activated virtual environment. The source audit reports filenames/categories only, never secret values. It checks current tracked/unignored files, not Git history or every possible secret format. Review staged changes and perform a full-history secret scan privately before pushing. `.gitignore` does not untrack an already committed secret; rotate any exposed credentials, remove them from history and caches using your organization's process, and verify before connecting Render. Never paste credentials, document contents or query bodies into a support chat.

Commit the reviewed application/deployment changes, including all new `backend/*.py` modules, Docker files, tests and this guide, to the private repository and your selected release branch. Do not commit your `.env`, OAuth files, database, document exports, backups or bootstrap values. Do not make the repository public.

The Docker build uses a deny-by-default `.dockerignore` and copies only Python application code, requirements, existing public frontend assets and the logo. It does not run application code, seed accounts, access Drive, copy `.git`, or read credentials. The Dockerfile declares no secret `ARG` and no secret `ENV`. Render translates service variables to build arguments, but this Dockerfile never references them; do not add such references, secret files, a `COPY . .`, or environment dumps. See [Render Docker behavior](https://render.com/docs/docker).

If Docker is available, rehearse `docker build -t ace-render-check .` with no production secrets and inspect the image filesystem privately. This build is not required to change your local virtual environment. Rehearse release, OAuth and synchronization with a separate synthetic staging database/folder before using approved real data.

## 2. Create persistent Postgres

Render dashboard → **New → Postgres**:

| Setting | Value |
| --- | --- |
| Name | `ace-production-db` |
| Database | `ace` |
| User | Let Render generate it |
| Region | `Virginia` (`virginia`), subject to the owner's data-region approval; use the same region for all three resources |
| PostgreSQL version | `17` |
| Compute plan | Paid `0.1c-256mb` (legacy `basic-256mb`) or larger; select larger if rehearsal shows memory/storage pressure |
| Initial storage | `5 GB` or larger after measuring the approved corpus |
| External IP allow list | Empty list: disable all external database access |

Enable and verify paid-plan recovery/backups; retain a separately approved encrypted backup and test restoration privately. Use the **Internal Database URL** for both services. The application adds `sslmode=require` on Render. Internal Render certificates are self-signed, so this supplies encryption without authenticated certificate verification; confirm that this meets your organization's database transport requirements. If authenticated TLS is mandatory, this configuration needs an approved database endpoint supporting verification before deployment. No persistent web disk is necessary. See [Render Postgres connections and TLS](https://render.com/docs/postgresql-creating-connecting).

## 3. Create the Google Web client

In the organization's Google Cloud project, enable **Google Drive API**. Configure Google Auth Platform consent as **Internal** for an eligible Workspace organization, or another organization-approved production audience/status. An External app in Testing is unsuitable for reliable long-running sync: this scope's testing refresh grant normally expires after seven days. Restricted-scope verification and data-handling requirements may apply; confirm them with the organization. See [Google token expiration](https://developers.google.com/identity/protocols/oauth2#expiration).

Create an OAuth client of type **Web application**, dedicated to this hosted app. Add exactly this authorized redirect URI, substituting the actual Render hostname:

```text
https://YOUR-SERVICE.onrender.com/api/drive/oauth/callback
```

Do not add localhost or a wildcard to the production client. No JavaScript origin is required because Google tokens are exchanged only by the server. The Render hostname must match `APP_ORIGIN`. If Render allocates a different name than requested, update both before authorization. Keep your existing Desktop client for development.

Give the approved Google account Viewer access to the approved folder; avoid broader Drive sharing. Record its exact email and root folder ID privately. Review the permitted category subfolders using the existing ingestion guide. The app requests only `https://www.googleapis.com/auth/drive.readonly`; it does not request write scope, change ACLs, or follow shortcuts.

## 4. Configure secrets and application variables

Create a Render **Environment Group** named `ace-production` and link it only to the production web service and sync cron job. Restrict Render workspace membership and enable account MFA. Add these variables through the dashboard, never via Git:

| Variable | Exact value/source |
| --- | --- |
| `APP_ENV` | `production` |
| `APP_ORIGIN` | `https://YOUR-SERVICE.onrender.com` — exact origin, no trailing slash/path |
| `DATABASE_URL` | The paid database's **Internal Database URL**; same database for both services |
| `KNOWLEDGE_SOURCE` | `drive` |
| `DRIVE_AUTH_MODE` | `oauth_web` |
| `SYNC_EXECUTOR` | `database` |
| `DRIVE_AUTHORIZED_EMAIL` | Exact organization-approved Google account email |
| `DRIVE_KNOWLEDGE_FOLDER_ID` | Approved root folder ID, not its URL |
| `DRIVE_WEB_CLIENT_ID` | New **Web application** client ID, ending `.apps.googleusercontent.com` |
| `DRIVE_WEB_CLIENT_SECRET` | That Web client's secret |
| `DRIVE_TOKEN_ENCRYPTION_KEY` | A newly generated Fernet key, identical on web and cron; keep an independent secure backup |

Generate the encryption key privately with your existing Python environment:

```sh
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Copy the result directly into the Render environment group and your approved secret vault. Do not send the result here. Do not rotate/regenerate it on redeploy. This app already uses random opaque database sessions; there is no `SECRET_KEY` or JWT signing key to configure.

Render supplies `RENDER` and `PORT`; do not override them. Do **not** set `GOOGLE_APPLICATION_CREDENTIALS`, `DRIVE_OAUTH_CLIENT_FILE`, `DRIVE_OAUTH_TOKEN_FILE`, `SYNTHETIC_DOCUMENT_DIR`, Cloud SQL settings or `SYNC_JOB_RESOURCE` on Render. Do not upload any Desktop client/token, service-account JSON key, `.env` or document as a Render Secret File. Do not paste your entire local `.env` into Render.

For the **first web release only**, add `BOOTSTRAP_ADMINS` directly to the **web service**, outside the shared group. Its value is a JSON array of exactly two real administrators:

```json
[{"id":"YOUR_ADMIN_1","name":"First authorized administrator","password":"REPLACE_WITH_DISTINCT_RANDOM_PASSWORD_1"},{"id":"YOUR_ADMIN_2","name":"Second authorized administrator","password":"REPLACE_WITH_DISTINCT_RANDOM_PASSWORD_2"}]
```

Replace every placeholder. Use distinct random passwords of 16–256 characters; deliver them privately. This is the explicit initial account provisioning mechanism, not test seeding. Existing administrator tables are not overwritten. Remove `BOOTSTRAP_ADMINS` from Render immediately after the first successful release. The web entrypoint removes it from its application environment and never uses it; deletion from Render is still required. Do not put this value in the cron job, an env example, shell history, build command, or Git.

## 5. Exact Web Service settings

Render → **New → Web Service** → connect GitHub using Render's GitHub app. Grant access to **only the private Ace repository**. Choose the reviewed release branch; no deploy key or GitHub token belongs in your repository. See [Render Git provider setup](https://render.com/docs/git-provider).

| Setting | Value |
| --- | --- |
| Name | `ace-knowledge-assistant` (or available equivalent; use its actual hostname everywhere) |
| Source | Your private GitHub repository, reviewed release branch |
| Region | Same as Postgres |
| Language / runtime | `Docker` |
| Root Directory | Empty (repository root) |
| Dockerfile Path | `./Dockerfile` |
| Docker Build Context | `.` |
| Build Command | Not applicable for Docker; leave unset |
| Pre-Deploy Command | `python -m backend.release` |
| Docker Command | `python -m backend.serve` (or blank to use identical Dockerfile CMD) |
| Health Check Path | `/readyz` |
| Compute plan | Paid `1c-2g` (1 CPU / 2 GB; legacy `Standard`) initially; downsize only after corpus/Find & Fix rehearsal |
| Instances | `1` |
| Auto-Deploy | `Off` |
| Pull request previews | Disabled; never clone production data/secrets into previews |
| Persistent disk | None |
| Environment | Link `ace-production`; add first-release `BOOTSTRAP_ADMINS` only here |

The paid pre-deploy command performs an explicit additive, versioned schema migration under a PostgreSQL advisory lock, configures the approved folder, optionally bootstraps the initial two real administrators, and verifies prerequisites before traffic starts. Startup performs no schema changes and never seeds accounts. A wrong origin, missing runtime settings, missing schema/admins, or a mismatched approved folder stops startup. `/healthz` is liveness; `/readyz` checks database/schema readiness without exposing document metadata. The plan IDs above follow [Render's current compute-plan names](https://render.com/docs/compute-plans).

After completing the privacy/logging prerequisites and reviewing all values, **you** may initiate the manual deployment. This preparation has not initiated it. Remove the bootstrap variable after success and manually deploy again. Log in and create real employees or judge accounts via Employee Management, delivering generated PINs privately.

This provisions a separate production database and leaves local accounts, documents, OAuth and development data untouched. It does not silently transfer your local SQLite data or published test accounts. If existing real account records must be retained on the initial move, stop before bootstrapping and arrange a private, reviewed SQLite-to-Postgres data migration with the owner, preserving Argon2 hashes and office mappings and excluding development fixtures/sessions. Rebuild the document index from the approved Drive folder. Never upload your local database to GitHub or the Docker image.

## 6. Connect Google and create the scheduled job

Sign in at `https://YOUR-SERVICE.onrender.com/admin-login.html`. Open **Knowledge Management → Connect Google Drive**. Complete Google consent with the configured team account in the same browser. The callback verifies the initiating administrator remains active, the Google email matches and the approved folder is accessible. Follow **Return to Knowledge Management** on the completion page; this preserves Strict session cookies without weakening them. Denied consent, expired session/state, wrong account, missing offline grant, incorrect callback or restricted scope produces a generic failure. Reconnect after correcting the configuration. Never copy a code or token into the browser console or this chat.

Then Render → **New → Cron Job**:

| Setting | Value |
| --- | --- |
| Name | `ace-drive-sync` |
| Source and branch | Same private repository and reviewed commit as the web service |
| Region | Same as web/Postgres |
| Language | `Docker` |
| Root Directory | Empty |
| Dockerfile Path / Context | `./Dockerfile` / `.` |
| Schedule | `*/5 * * * *` (UTC) |
| Docker Command (Advanced) | `python -m backend.sync --if-due` — mandatory override of the web CMD |
| Compute plan | `1c-2g` (legacy `Standard`) initially, to allow document extraction and discrepancy analysis memory |
| Auto-Deploy | `Off` |
| Environment | Link the **same** `ace-production` group; no bootstrap variable |
| Persistent disk | None |

Use the cron job's **Runs** tab to verify execution. The application schedules daily work by last-success age and durable requests; the five-minute cron is the dispatcher. In the dashboard, save the approved folder if needed, then select **Re-sync now**. Expect processing on the next cron tick, usually within five minutes. A 202 response means queued, not completed. Require `sync_status=succeeded`, a recent `last_success`, and the expected indexed/unreadable counts before claiming success. Review metadata privately; do not paste document contents into logs or support. Find & Fix is generated atomically with the current index.

Do not click **Trigger Run** while a cron execution is active: Render cancels the existing run when manually triggering another. The database lease protects publication, but a cancelled run can delay a retry until lease expiry. Render also queues scheduled executions behind an active run. See [Render cron behavior](https://render.com/docs/cronjobs).

## 7. Release checklist before sharing with judges

- [ ] Organization approved Render, region, consent audience, approved folder/account, retention, and platform log exclusions; no PHI or unapproved documents.
- [ ] Repository stays private; staged files and history scanned; no credentials, source documents, databases or backups in Git/build context/image layers.
- [ ] Web and cron use the same paid private Postgres and encryption key; public database access is disabled; backups and restore tested.
- [ ] Pre-deploy release succeeds; two real administrators can sign in; known development identities cannot sign in; bootstrap secret removed from Render.
- [ ] Google consent uses the Web client, correct HTTPS redirect, approved email and read-only scope; refresh works across a service restart without browser interaction.
- [ ] `/readyz` returns 200; HTTPS cookies are Secure/HttpOnly/Strict; unknown hosts, preview routes, external origins and missing CSRF tokens are rejected; `/docs` is unavailable.
- [ ] Employee and admin sign-in URLs work in a private/incognito browser; employees cannot access administrator APIs/pages; deactivation/PIN reset invalidates existing sessions; two-admin minimum holds.
- [ ] Search returns verified sources for approved synthetic checks in each office/category; office selection and Lilburn's ADC alias work; unreadable documents stay excluded; privacy warning remains visible.
- [ ] Find & Fix Log lists supported issues, exact quotation pairs, offices and human review instructions; no automatic policy correction.
- [ ] Cron succeeds; Re-sync requests execute; revoked/expired Drive grants fail safely and retain the prior index; expired/crashed leases permit recovery; queued requests survive web restart.
- [ ] Manually redeploy web and cron at the same reviewed commit, then verify account/office changes, the existing index and administrator data survived; verify another scheduled sync.
- [ ] Application, edge, database and any attached monitoring logs contain no questions, answers, quotations, document content, credentials, callback codes or tokens. Use fictional sentinels to verify; do not test logging with real private data.
- [ ] Configure an organization-approved perimeter rate limit for login identifier spraying and non-content operational alerts. Review DB login lockouts, cron failures, stale `last_success`, storage and backup health. Expired sessions/old login-attempt records have an approved cleanup/retention schedule.
- [ ] Set judge accounts to the least role needed, share PINs/passwords privately, and plan deactivation and data cleanup after the event.

Share these two addresses only after the checklist passes:

```text
Employee:      https://YOUR-SERVICE.onrender.com/login.html
Administrator: https://YOUR-SERVICE.onrender.com/admin-login.html
```

These are separate login pages for the existing roles, not separate origins or separate Google logins. Both lead to the same protected application and API. Judges receive only access approved by the document owner.

## Operations, revocation, rotation and rollback

Keep automatic deploys and production previews off. Back up before schema changes; pause cron and wait for any active sync to finish, manually deploy the reviewed web/cron commit together, then resume cron. Release configuration refuses to change a folder during an active synchronization; retry after it completes or the crashed lease expires. Migrations are additive but an old image may reject a newer schema revision. Never blindly downgrade schema, delete the production database or reseed. Rehearse rollback using a restored private database and compatible code. Render database deletion removes recovery data; backups must be retained independently as policy requires.

If Google access expires or is revoked, an administrator reconnects through Knowledge Management. Existing search retains the previous successful index while sync reports failure; revoke employee/judge access if that retained corpus is no longer authorized. To disconnect, disable the sync cron, revoke the app grant in the approved Google account's security settings, and remove the encrypted `drive_grant` and outstanding `drive_consent` rows through an authorized private database session. Revoke application sessions/accounts and apply the organization's document/index/backup deletion procedure if the hosting authorization ends. Revocation alone does not erase previously indexed text.

For client-secret, account, origin or approved-folder changes, update both services and the Google configuration, run the release command via a manual web deploy, and reconnect. Changing the approved folder clears the active generation through explicit release configuration; old snapshots are removed after a successful new sync. To rotate the encryption key, stop sync, deploy the new key to both services, reconnect to replace the encrypted grant, and resume sync. The old grant cannot decrypt under the new key; keep the previous key in the approved vault only for approved backup recovery. Do not rotate a key by regenerating it independently on each service.

Keep HTTP wire debugging, SQL parameter tracing, APM body/header capture and document/query logging disabled. Diagnose using fixed failure categories, readiness, run exit status and private configuration review. Credentials and confidential documents should never be shared with the coding assistant for troubleshooting.

## Validation limits of this preparation

Local verification on November 8, 2026: **455 Python tests passed** (six dependency deprecation warnings), **32 frontend tests passed**, the current-source audit passed, and `git diff --check` passed. A read-only scan of all 142 blobs in the non-shallow local repository's reachable history found no private-artifact or known-secret-pattern findings using the source audit's suffix/pattern rules. This limited scan is not a comprehensive secret/privacy audit. These checks did not load the local `.env`, access Drive, or ingest private documents. The local environment uses Python 3.14, while the Dockerfile uses Python 3.12; the Docker image build remains unverified because the local Docker daemon is not running.

Automated tests use temporary SQLite fixtures, fictional credentials, mocked Google APIs and empty/synthetic inventories. They cover production configuration boundaries, cookie/CSRF/role behavior, Web OAuth state/PKCE/account binding, encrypted token storage, replay denial, durable queue retries, additive migrations and existing application regressions. They do not prove Workspace approval, Render edge/database logging settings, Google production verification, a live PostgreSQL migration, image build compatibility or deployed persistence. Complete the synthetic staging rehearsal and host checks above before production use.

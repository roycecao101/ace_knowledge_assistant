# Dashboard CSRF and Google Drive synchronization repair

Investigation and live verification: November 7, 2026. This report supersedes the outstanding-setup findings in `sync-connection-diagnosis.md`.

## CSRF root cause and correction

The session cookie is shared across tabs on the same hostname. The frontend previously fetched its session-bound CSRF token only when the page initialized and kept that token in page memory. Logging in again replaces the cookie and creates a new token, leaving other open pages with an old token. This mismatch was reproduced in regression tests. Signing out and back in, or loading a fresh page, temporarily aligns both values. The original browser request was not captured, so its exact history cannot be established retrospectively.

The database persists sessions and CSRF tokens; a normal FastAPI restart does not rotate them. A fresh page already obtains its current token from the uncached, authenticated `/api/auth/me` endpoint. No token is stored in localStorage or sessionStorage. `localhost` and `127.0.0.1` have separate cookie jars; switching hostnames requires its own sign-in. Cookies are shared across ports on the same hostname, so another instance of this application on another port can also replace them. No other listener on the checked application/static-server ports was observed during this investigation. The two port-8000 PIDs were one reload parent/worker pair.

The shared frontend client now recognizes a specific CSRF rejection header, retrieves the current session token, and retries the rejected operation once. The backend rejects the first request before its handler executes, so this recovery does not duplicate a successful mutation. Other authorization/origin errors and network failures are never retried. A different signed-in account requires a reload before any retry. Expired sessions redirect to sign-in; logout clears page authentication state. Invalid, missing, and malformed tokens remain rejected with HTTP 403. Employee search uses the same client while retaining its abort deadline and response validation.

Session expiry, active-account/version checks, HttpOnly/SameSite cookies, production Secure cookies, origin restrictions, and CSRF validation remain enforced.

## Synchronization root cause and correction

The actual Uvicorn reload parent (PID 66993, started at 15:07:43 local time) and worker (PID 69664 at the initial inspection) had **none** of `APP_ENV`, `KNOWLEDGE_SOURCE`, `DRIVE_AUTH_MODE`, the approved email/folder variables, or OAuth path variables in their inherited environment. They did use the project's virtual environment; the executable's Homebrew installation path alone did not mean the virtual environment was wrong.

The effective defaults were development, Drive, and **ADC**, rather than `oauth_local`. Consequently synchronization failed while constructing the Google credential/service client, **before folder inventory, downloads, extraction, indexing, or publication**. The saved failure was the missing/expired backend-credentials message. The CLI's successful local OAuth verification did not alter the already running server's environment. Reloading Python code also retains the reload parent's original environment.

The existing private OAuth receipt was verified and its approved folder matched the database's saved real folder ID. A metadata-only preflight refreshed the existing grant, checked the approved account, and inventoried seven downloadable files without downloading any document body. No new login or metadata-verification bypass was needed.

The identified server was stopped and restarted from this repository with `.venv/bin/python`, the existing database, and the same verified OAuth account/folder settings. Its normal scheduler performed the real synchronization. Startup logs now report source, auth mode, environment, and whether a virtual environment is active, without identifiers, paths, or secrets. Missing ADC credentials now explain when the server is using ADC and needs to be restarted with the local OAuth environment.

Failures identify a fixed workflow stage: source configuration, Google authorization, inventory, download/export, extraction, indexing/database update, publication, or old snapshot cleanup. Raw third-party exception messages are excluded. Saving an unchanged folder no longer clears a failed sync's error and makes an old success appear current. Invalid source modes fail explicitly. A saved folder must match the local OAuth pin before the Google client is constructed.

## Live results

The running FastAPI service completed synchronization with:

| Check | Result |
|---|---|
| `sync_status` | `succeeded` |
| `last_success` | November 7, 2026, 6:55:04 PM EST (`1794095704.370518` Unix seconds) |
| Indexed / unreadable documents | 7 / 0 |
| Approved inventory metadata | All seven IDs, filenames, MIME types, categories, and modification times matched |
| Indexed passages | 1,053; all passed source-quote verification and belong to the active approved generation |
| Previous document/index generations | Removed by successful atomic publication |
| Employee search | Local source-derived probe succeeded; every returned result was approved and source-verified |
| Existing account/session rows | Unchanged, checked using local comparison hashes |
| Served frontend assets | Match current files; `Cache-Control: no-store` |
| Unauthenticated administrator API | HTTP 401 |

Before the successful run there were three old document rows but no active generation after the real folder was saved. They were not available to employee search. The successful snapshot replacement removed them. Full-inventory reconciliation already handles additions, edits, renames, category moves, moves out of the approved tree, and deletions; regression coverage verifies replacement and failure retention. Folder ancestry and metadata-verification boundaries remain enforced.

Confidential filenames, contents, search queries, and returned quotations were inspected only inside local application processes and were not included in tool output or this report. No external AI service received documents. Drive calls remained scoped to the approved tree, plus the existing account identity check.

## Starting from VS Code

The server is already running on `http://127.0.0.1:8000`. Reload the administrator page once to load the updated JavaScript. The existing session remains valid until its normal expiry or logout. No new OAuth authorization is required now.

For future restarts, stop the current server with Ctrl+C in its owning terminal. The repair-started server is detached; identify its reload parent with `ps`/`lsof` and terminate that parent gracefully before launching a replacement. Never start a second instance on another port as a workaround. Check port ownership with:

```sh
lsof -nP -iTCP:8000 -sTCP:LISTEN
ps -axo pid,ppid,command | rg uvicorn
```

From a VS Code terminal:

```sh
cd /Users/royce/ace_knowledge_assistant
source .venv/bin/activate
set -a
source .env
set +a
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

The repair created root `.env`, git-ignored with mode `0600`, containing only the existing approved account/folder identifiers and credential paths, plus `APP_ENV=development`, `KNOWLEDGE_SOURCE=drive`, and `DRIVE_AUTH_MODE=oauth_local`. OAuth secrets and refresh credentials remain outside the repository in their existing private files. The application does not auto-load `.env`; `set -a` exports its settings to both the CLI and newly started FastAPI processes. Existing `DATABASE_URL` configuration must be preserved if you use a different database.

Startup should report `source=drive, auth=oauth_local, environment=development, project_venv=True`. Then open `http://127.0.0.1:8000/admin.html#sync` and check the completed status. HTTP 202 only means a sync was accepted; completion requires `succeeded` and an updated `last_success`. Runtime output for this repair is in `/tmp/ace-backend-current.log`.

## Files changed for this repair

- `backend/main.py`: explicit CSRF rejection marker, malformed-token handling, safe runtime diagnostics.
- `backend/sync_service.py`: fixed failure stages, environment guidance, source/folder validation, preservation of unchanged-folder failure status.
- `frontend/auth-client.js`: bounded session-aware CSRF recovery and abort-signal support.
- `frontend/script.js`: employee search uses the shared authenticated client.
- `tests/test_auth.py`, `tests/test_drive_oauth.py`, `tests/test_ingestion.py`, `tests/test_auth_client.cjs`: session/CSRF, OAuth gating/configuration, sync failures, reconciliation, and browser-client regressions.
- `README.md`, `docs/google-drive-oauth.md`, `docs/sync-connection-diagnosis.md`, this report, and private ignored `.env`: current operation and restart instructions.

Other pre-existing uncommitted changes were retained. No database initialization, reseeding, account deletion, credential replacement, or schema migration was performed.

## Validation

Final results: **156 Python tests passed**, **10 JavaScript tests passed**, and no test failures. The six Python warnings are dependency deprecations.

Run the isolated regression suites with:

```sh
.venv/bin/python -m pytest -q
node --test tests/test_auth_client.cjs
```

The Python suite covers session rotation and backend recreation, rejection of missing/invalid CSRF, role/origin restrictions, OAuth configuration/receipt enforcement, out-of-scope and moved files, PDF/DOCX/Google Docs extraction, unreadable reporting, sync failure stages, atomic replacement/rollback, concurrent leases, and approved-only search. JavaScript tests cover recovery, bounded retries, account changes, logout/expiry, request credentials, search timeout propagation, and response validation. `pip check`, JavaScript syntax checks, and `git diff --check` also passed. Python dependencies emitted deprecation warnings without test failures.

The repair did not operate the user's personal browser session. Live ingestion/search integrity was checked locally; authenticated endpoint and client behavior was verified with isolated test sessions.

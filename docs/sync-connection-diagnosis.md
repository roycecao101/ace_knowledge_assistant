# Synchronization connection diagnosis — November 7, 2026

**Superseded by the [dashboard CSRF and synchronization repair](dashboard-sync-fix.md).** The later investigation confirmed that the running server lacked the local OAuth environment. It has now been restarted with the existing verified settings and successfully synchronized the approved folder. The synthetic-folder and outstanding-setup findings below are historical.

The stale-process findings below describe the earlier diagnosis. Local Drive
authentication now supports installed-application OAuth; the current setup is
documented in [Google Drive OAuth for local development](google-drive-oauth.md).
Keep `iam.disableServiceAccountKeyCreation` enforced. No service-account JSON key
is required for local development.

## Cause and evidence

The backend on `127.0.0.1:8000` was started at 12:45:59 without `--reload`.
Its live `/openapi.json` contained account/authentication routes and the generic
administrator fallback, but none of the knowledge, documents, settings, or sync
routes present in `backend/main.py` on disk. Both served administrator JavaScript
files already matched the newer files on disk. Static assets are read for each
request; Python routes are loaded when the process starts.

`frontend/admin.js` supplies shared components and the isolated preview. The live
Synchronization view is in `frontend/live-admin.js`. It calls
`GET /api/admin/knowledge` for status and `POST /api/admin/sync` to start a job.
`frontend/auth-client.js` uses relative URLs and same-origin session cookies.
Those URLs match the current backend. `GET /api/admin/sync` is not a status API.

The old process routed the newer knowledge URL to the authenticated fallback,
which returns **HTTP 503**, `This service is not connected.` This conclusion is
based on the live route inventory and the fallback implementation; no personal
browser or authenticated live request was inspected. Unauthenticated live probes
returned **401**, as expected. There was no evidence of a 403, 404, or 500 causing
the reported message. A separate static server on port 8080 supplies no API; use
the FastAPI origin on port 8000 for the live application.

## Checks and fixes

- Restarted only the stale port-8000 backend with the project virtual environment,
  current code, and `--reload`. Its live OpenAPI now registers
  `GET /api/admin/knowledge`, `GET /api/admin/documents`,
  `POST /api/admin/sync`, and `PATCH /api/admin/settings`.
- Corrected the obsolete integration-contract comments in `frontend/admin.js`.
- Added safe startup route/schema diagnostics and a scheduler warning that logs
  only the exception class, without exception text or document contents.
- Excluded the unsupported-service fallback from OpenAPI to remove its duplicate
  operation-ID warning; its authentication and HTTP behavior are unchanged.
- Every requirement in `backend/requirements.txt` is installed in `.venv` at a
  compatible version; `pip check` reports no broken requirements.
- All four knowledge tables already exist. No initializer or migration was
  required, and no account, credential, or existing index was changed.
- Startup completed successfully. The prior process's output was attached to
  pipes, so historical startup output was not recoverable as a log file. The
  restarted process writes to `/tmp/ace-backend-5jjk68ci.log`.
- The full suite passed: **117 tests**. JavaScript syntax checks passed. Tests use
  temporary databases and fictional documents; they do not prove Google access.

## Manual Google configuration

The saved ID is the synthetic fixture `synthetic`, not a real Drive folder ID.
`KNOWLEDGE_SOURCE` was unset (defaults to `drive`),
`GOOGLE_APPLICATION_CREDENTIALS` was unset, and the standard local ADC file was
absent. A previous synthetic success timestamp does not establish Google access.
The API is not disabled by missing Google settings: an unconfigured folder blocks
job submission with 409, while missing credentials cause an accepted job to fail
and record an explanatory status. A 202 response alone is not a successful sync.

The technical owner must:

1. Follow the [OAuth setup guide](google-drive-oauth.md) to enable Drive API and
   create/download a **Desktop app OAuth client** in the Ace-owned project.
2. Move the downloaded client into a private directory outside Git, with mode
   `0700` on the directory and `0600` on the file. Configure only its path in
   `DRIVE_OAUTH_CLIENT_FILE`; never display or share the contents.
3. Set `DRIVE_AUTH_MODE=oauth_local`, `APP_ENV=development`,
   `KNOWLEDGE_SOURCE=drive`, `DRIVE_AUTHORIZED_EMAIL`, and
   `DRIVE_KNOWLEDGE_FOLDER_ID` using the approved team identity and folder.
4. Stop the backend during setup. Run `python -m backend.drive_oauth login`,
   then `python -m backend.drive_oauth verify`. The latter lists permitted
   metadata only and must succeed before ingestion is enabled. Review its output
   privately; do not send confidential filenames or documents to Codex.
5. Restart with that environment, save the same approved folder ID in the
   administrator dashboard, replacing `synthetic`, and use **Re-sync now** when
   authorized to import it. A real successful sync is still required before
   claiming documents are indexed. The existing `connection_verified` field
   continues to describe successful synchronization, not just metadata access.

Hosted authentication uses a dedicated attached service account with short-lived
credentials, or a separately implemented web OAuth flow, as documented in the
[OAuth guide](google-drive-oauth.md). Desktop OAuth is rejected in production.

## Launch and verify

The earlier diagnosis restarted the server. After completing OAuth setup above,
stop any existing port-8000 instance, then run from the project root in the same
terminal holding the OAuth environment variables:

```sh
cd /Users/royce/ace_knowledge_assistant
KNOWLEDGE_SOURCE=drive .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

The OAuth client file is configured by path only; no service-account key is
needed. No database or live credentials were changed by the OAuth implementation.
Schema setup for another existing database, if needed, is
`.venv/bin/python -m backend.initialize_knowledge` with the same `DATABASE_URL`.

Open `http://127.0.0.1:8000/admin-login.html`, sign in normally, then open
`/admin.html#sync`. In that page's Network panel, the status request should be
`GET /api/admin/knowledge` with HTTP 200. An unauthenticated terminal request
returns 401; this is expected, not a connection failure. The registered routes
can also be checked at `http://127.0.0.1:8000/docs`.

After manual authorization/configuration, **Re-sync now** should issue
`POST /api/admin/sync` with the existing session and CSRF token and receive 202.
Refresh/poll `GET /api/admin/knowledge` until `running` is false. Require
`sync_status: "succeeded"`, a new `last_success`, and no error for the actual
approved folder. Read any recorded Google authorization/access error if the job
fails. A 401 means sign in; 403 means authorization, origin, or CSRF rejection;
409 means missing folder or overlapping sync. Google-side errors are recorded in
job status rather than changing the earlier 202 response.

No personal Chrome browser or confidential Ace documents were accessed. No live
Drive synchronization was requested during diagnosis.

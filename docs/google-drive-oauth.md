# Google Drive OAuth for local development

The enforced `iam.disableServiceAccountKeyCreation` policy stays enabled. This setup uses a Google **Desktop app OAuth client**, not a service-account key. Google authorization supplies backend Drive access; the existing employee PINs, administrator passwords, sessions, database, indexing, sync controls, and search interfaces remain in use.

## 1. Prepare the team account and client

Have the technical owner identify the authorized **team Google account** and the approved knowledge-folder ID (the ID after `/folders/` in its Drive URL). The account must have Viewer access with download/export allowed. Use the organization's approved account, never an unrelated personal account. Existing approved category folders retain their exact names; unrecognized top-level subfolders and shortcuts are skipped. Direct root documents belong to All Categories. Descendants within recognized category folders inherit that category.

In the existing Google Cloud project:

1. Enable Google Drive API.
2. Configure Google Auth Platform branding, audience, and data access. Use an internal audience if the project and team belong to the same Workspace organization; otherwise follow the organization's approved audience and test-user process. Workspace API controls may require administrator approval.
3. Request only `https://www.googleapis.com/auth/drive.readonly`.
4. Create an OAuth client with application type **Desktop app**, then download its JSON file. No service-account key creation, policy exemption, domain-wide delegation, or public folder sharing is needed.

The selected scope permits listing metadata and downloading/exporting existing documents. `drive.metadata.readonly` cannot retrieve content; `drive.file` includes write permissions and does not support this existing-folder crawler without a separate per-file selection flow. Google does not offer a folder-restricted OAuth scope for this use. The application therefore pins the approved root and verifies ancestry before downloads; the account's Drive permissions remain the outer authorization boundary. Prefer a team account with access limited to the approved knowledge materials. See [Google's Drive scope reference](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).

## 2. Store the downloaded file privately

Run these commands yourself in a local terminal. Do not upload, paste, print, screenshot, or send the JSON contents, tokens, or company documents to Codex. Replace the download path with your actual filename; the contents require no editing.

```sh
umask 077
mkdir -p "$HOME/.config/ace-knowledge-assistant"
chmod 700 "$HOME/.config/ace-knowledge-assistant"
mv "$HOME/Downloads/client_secret_REPLACE_WITH_DOWNLOAD_NAME.json" "$HOME/.config/ace-knowledge-assistant/oauth-client.json"
chmod 600 "$HOME/.config/ace-knowledge-assistant/oauth-client.json"
```

Use a directory outside **every Git repository** and the web root, owned by your OS user, with directory mode `0700` and file mode `0600`. Symlink paths are rejected. The application validates these permissions and writes refresh credentials atomically with mode `0600`. Access tokens stay in backend memory and are omitted from the saved token file. The refresh token and client information are readable only by your OS user; protect that account and use full-disk encryption. These are private local files, not encrypted vault storage. Exclude them from shared/cloud backups. `.gitignore` also excludes common OAuth filenames as defense in depth; it is not the storage boundary.

## 3. Configure paths and approved identity

From the project root, in the same terminal used to launch the backend:

```sh
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
export APP_ENV=development
export KNOWLEDGE_SOURCE=drive
export DRIVE_AUTH_MODE=oauth_local
export DRIVE_AUTHORIZED_EMAIL='REPLACE_WITH_AUTHORIZED_TEAM_EMAIL'
export DRIVE_KNOWLEDGE_FOLDER_ID='REPLACE_WITH_APPROVED_FOLDER_ID'
export DRIVE_OAUTH_CLIENT_FILE="$HOME/.config/ace-knowledge-assistant/oauth-client.json"
export DRIVE_OAUTH_TOKEN_FILE="$HOME/.config/ace-knowledge-assistant/oauth-token.json"
```

The last two paths are also the defaults if unset. They must be distinct absolute paths. These variables contain paths and approved identifiers, never token or JSON contents. This application does not automatically load `.env`. Keep any persistent environment configuration outside Git and protect it with OS permissions. `GOOGLE_APPLICATION_CREDENTIALS` is not used in `oauth_local` mode; do not point it at this OAuth client download.

For this existing workstation, the November 7 dashboard repair saved those verified identifiers and paths in the root `.env` (git-ignored, mode `0600`). It contains no OAuth client secret, access token, or refresh token. In each new VS Code terminal, load it **before both CLI verification and server startup**:

```sh
cd /Users/royce/ace_knowledge_assistant
source .venv/bin/activate
set -a
source .env
set +a
```

Shell exports affect only processes started from that shell afterward. An already running Uvicorn process, including its reload worker, retains its original environment; `--reload` does not import exports from a different terminal. Stop the existing server with Ctrl+C before starting another instance. Use `lsof -nP -iTCP:8000 -sTCP:LISTEN` to identify a leftover server. A reload parent and its child sharing one socket are one server, not conflicting instances. Do not run a separate static server for the authenticated application. See the [dashboard repair report](dashboard-sync-fix.md) for observed results and restart instructions.

## 4. Authorize and verify metadata before ingestion

Stop the development backend while completing initial setup or changing credentials, so its daily scheduler cannot import documents during setup. Neither of these commands initializes or modifies the database, indexes text, or downloads document bodies:

```sh
python -m backend.drive_oauth login
python -m backend.drive_oauth verify
```

`login` opens the system browser with Google's supported installed-application flow: PKCE, OAuth state validation, a temporary random port bound to `127.0.0.1`, offline access, and a three-minute timeout. Choose the authorized team account and grant only Drive read-only access. The account picker hint is checked against the actual authenticated email via Drive's `about.get`; signing into another account is rejected. The callback does not print authorization codes or token responses. No Google OAuth callback or token route is added to FastAPI or frontend JavaScript. See [Google's desktop OAuth documentation](https://developers.google.com/identity/protocols/oauth2/native-app).

`verify` checks that account again, confirms the approved root is accessible, and lists **only permitted file metadata**: ID, filename, MIME type, modification time, category, and download capability. Review this list locally; do not paste confidential filenames into chat. A successful complete listing writes a verification receipt bound to this account, OAuth client, and approved folder. There are no document download/export calls. A failed or incomplete listing cannot enable ingestion. An empty list can verify connectivity but means there are no supported files in the permitted tree.

The runtime refuses ingestion without that receipt. Login resets it; changing the account, client, scopes, or folder requires another login and verification. Runtime use refreshes credentials without opening a browser and checks the Google account again. A metadata check verifies access, not that the documents have been indexed; the existing dashboard's `connection_verified` field continues to mean a successful full synchronization.

## 5. Use the existing administrator workflow

Keep the same `DATABASE_URL` if one is already configured. Existing installations with knowledge tables need no migration. If those tables have never been initialized, run `python -m backend.initialize_knowledge` with that database configuration. Do not reseed or replace an existing database.

```sh
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Sign in at `http://127.0.0.1:8000/admin-login.html`. In **Settings** or **Google Drive Synchronization**, save the same approved folder ID and use **Re-sync now**. A different ID is rejected even for administrators in local OAuth mode. A previously saved different root cannot be ingested. Saving a new root clears the old search generation as before. Once verified and configured, the existing daily scheduler may also synchronize while the server is online.

`POST /api/admin/sync` still requires an active administrator session and CSRF token. Employees cannot trigger sync or configure folders. HTTP 202 accepts a job; require `sync_status: "succeeded"`, a new `last_success`, and the expected indexed/unreadable list before claiming import succeeded. Employee search uses the existing endpoint and index. Failed syncs retain the previous index and expose only safe error guidance. Credential material never appears in these API responses.

Only a completed inventory authorizes a file download. Before each download/export the adapter rechecks that file's MIME type, trash state, download permission, and inventoried ancestor chain back to the approved root. Moves out of the allowed tree abort the snapshot. Drive does not provide a transactional tree snapshot; a concurrent change after these checks can still race a download. Stop edits during a sensitive initial import and synchronize again after source changes.

## Expiry, revocation, and troubleshooting

If a refresh grant expires or is revoked, stop the backend, repeat `login` and `verify`, then restart with the same environment. External OAuth apps in Testing normally receive refresh tokens that expire after seven days for this scope; Workspace session controls and revocation can shorten validity too. Have the owner configure an approved consent audience/status rather than relying on a testing grant for operations. See [Google's refresh-token expiry rules](https://developers.google.com/identity/protocols/oauth2#expiration).

For a wrong account, repeat login with the configured team identity. For 403, check Drive API enablement, Workspace API controls, folder Viewer sharing, and export restrictions. For 404, check the approved root ID and account access. Permission errors require directory mode `0700` and file mode `0600`. A new login deliberately requires verification again. Raw third-party errors, HTTP debug logs, and token bodies are suppressed. Keep HTTP wire debugging, APM request/header/body capture, proxy capture, and debugger variable dumps disabled in any environment holding these credentials.

To disconnect, stop the backend, revoke the application's grant in the team account's Google security settings, then remove the private token file yourself. Removing a local token file alone does not revoke the grant. Never commit either credential file.

## Hosted deployment

For **Render**, use the implemented `DRIVE_AUTH_MODE=oauth_web` strategy in the [Render deployment guide](render-deployment.md). It uses a separate Web application client, administrator-only consent initiation, state/PKCE, account/folder verification and encrypted offline grants in private Postgres, with the encryption key held separately in runtime secrets. The Desktop instructions above remain development-only. The Google Cloud ADC option below remains specific to attached Google Cloud identities; the final paragraph describes the original alternative design, now implemented for Render by `backend/drive_web_oauth.py`.

Desktop OAuth is explicitly rejected outside `APP_ENV=development`, including at FastAPI startup. Do not copy a developer refresh token or client file to hosting, and do not rely on an interactive desktop browser there.

The existing `DRIVE_AUTH_MODE=adc` path supports a **dedicated attached service account on Google Cloud**, using short-lived credentials from the runtime metadata service. Attach that identity to the hosting resource, enable Drive API, and share only the approved knowledge folder with its email as Viewer, subject to Workspace policy. Do not grant broad shared-drive membership or domain-wide delegation. Configure and verify that the runtime obtains the Drive read-only scope; on Compute Engine the VM access scopes must permit it. IAM roles alone do not grant access to Workspace Drive files. The hosting identity's Drive sharing must supply the folder boundary. No JSON key is created or mounted; `iam.disableServiceAccountKeyCreation` remains enforced. See [Google's attached-service-account setup](https://docs.cloud.google.com/docs/authentication/set-up-adc-attached-service-account).

Before enabling hosted synchronization, have the operator perform a metadata-only inventory under the deployed service identity and review its results in a private terminal. This can use `DriveClient().inventory(approved_folder_id)` without calling `read` or `SyncService.run`. Confirm both Drive scope and folder access on the actual host; a Cloud IAM check alone is insufficient. Keep the existing production HTTPS, secret/database storage, administrator access controls, and daily sync monitoring.

If Workspace policy requires user authorization, the **web-server OAuth authorization-code flow** is implemented for Render in `backend/drive_web_oauth.py`. Follow the [Render guide](render-deployment.md) for an organization-approved Web client, exact HTTPS callback, state/PKCE, administrator-session validation, encrypted offline grants in private managed Postgres, separately held runtime encryption key, and rotation/revocation procedures. Access and refresh tokens stay server-side. Do not repurpose the Desktop client for it. See [Google's web-server OAuth flow](https://developers.google.com/identity/protocols/oauth2/web-server).

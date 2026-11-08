# Core functionality completion report

## Inspection findings

The existing FastAPI application in `backend/main.py` serves the employee and administrator interfaces on the same origin. Authentication already uses employee PINs and administrator passwords, Argon2 hashes, opaque session cookies, session-bound CSRF tokens, active-account checks, and credential-version invalidation. This work preserves those mechanisms and all existing authentication routes.

The existing SQLAlchemy schema has account/session tables (`employees`, `administrators`, `authentication_sessions`, `login_attempts`, `admin_guard`) and knowledge tables (`knowledge_state`, `knowledge_documents`, `knowledge_passages`, `knowledge_terms`). Inspection confirmed these tables exist in the local SQLite database; no real document contents were read for development. No duplicate database, authentication system, upload endpoint, or external AI integration was introduced.

The repository already contained PDF/Word extraction, Google Docs export through the Drive API, full-inventory reconciliation, a database sync lease, an inverted keyword index, source quotation verification, local synthetic fixtures, authenticated employee search, and live administrator documents/settings panels. Before this pass, Overview omitted actual document counts and synchronization status; office headings missed codes and could classify incidental office mentions; topical keyword matches could pass without the requested fact; conflict detection missed weekdays and spelled-out quantities; and accepted background sync requests did not immediately reserve the job.

Development previews and their existing Policy Pulse specimens remain isolated behind the separate loopback preview server. No Policy Pulse, administrator conflict alerts, or other X-factor feature was implemented. Office management remains unconnected.

## Changes

- Overview now uses real indexed-document/unreadable-file counts and sync information. Sync panels distinguish a saved folder from a successful synchronization, show last attempt/success, update while running, and identify local synthetic ingestion explicitly. A request acknowledgement does not indicate successful synchronization.
- Synchronization claims its lease before HTTP 202, reports expired workers as failed, preserves the last successful snapshot on whole-job failure, and presents safe guidance for authentication, permission, missing-folder/file, rate-limit, and timeout failures. Per-file download/export restrictions and legacy Word documents appear in “Files I could not read.”
- Drive enumeration remains restricted to the configured root and recognized category subtrees, skips shortcuts, rejects incomplete listings, and guards repeated pagination and inventory limits. Full reconciliation handles additions, edits, renames, category/office moves, moves outside the approved tree, and deletions.
- Office headings accept initial office names or ALP/NOR/LIL/ADC codes; incidental mentions do not set scope. Section scope cannot expand the offices specified in a filename. Administrator metadata also reflects section-derived scope.
- Search applies office/category filters, verifies exact source membership and every normalized six-word sequence, retains decimals in quotations, checks short-quote boundaries, and rejects additional placeholder and non-answer cases. Heading-only matches cannot promote unrelated body sentences into supporting evidence. Near-identical numeric, spelled-out quantity, weekday, and polarity conflicts return both verified sources. Source metadata includes the Drive file ID.
- The employee not-found state displays exactly the specified fallback message. Search remains local and extractive: no questions or answers are written, and no documents are sent to an AI service.

## Files changed in this pass

| File | Purpose |
|---|---|
| `backend/document_indexer.py` | Exact quotation boundaries, decimal-safe sentence splitting, placeholders/non-answer exclusions |
| `backend/document_parser.py` | Section scope cannot expand filename office scope |
| `backend/drive_client.py` | Download capability, legacy Word reporting, enumeration guards |
| `backend/main.py` | Reserve synchronization before scheduling its background task |
| `backend/search.py` | Answer-intent checks, source metadata, additional conflicts, bounded retrieval/deadlines |
| `backend/sync_service.py` | Real counts/status, lease reservation, safe failure guidance, office metadata |
| `backend/taxonomy.py` | Leading filename/heading office labels and code recognition |
| `frontend/live-admin.js` | Live Overview counts/status, sync polling, readable/unreadable lists |
| `frontend/script.js` | Exact not-found fallback display |
| `tests/test_ingestion.py` | Expanded synthetic acceptance, failure, privacy, and end-to-end coverage |
| `README.md` | Completion-report link |
| `docs/ingestion.md` | Updated technical setup, behavior, and limitations |
| `docs/admin-ingestion-guide.md` | Updated administrator workflow |
| `docs/core-completion-report.md` | This report |

Pre-existing uncommitted changes in `README.md`, `backend/main.py`, `frontend/login.js`, and `tests/test_auth.py` were preserved. This pass did not edit the last two files. No commit or push was made.

## Dependencies and startup

No additional dependencies were needed in this pass. The existing requirements include FastAPI/Uvicorn, SQLAlchemy, Argon2, PyMuPDF for PDFs, python-docx for Word and exported Google Docs, and google-api-python-client/google-auth/google-auth-httplib2/httplib2 for authenticated Drive access. Pytest and HTTPX support automated tests. Dependency versions remain in `backend/requirements.txt`.

From the repository root:

```sh
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

For a fresh local development database only:

```sh
python -m backend.seed_test_accounts --seed-test-accounts
```

For an existing database, use the additive knowledge-table initializer, which preserves existing account records:

```sh
python -m backend.initialize_knowledge
```

Then start the existing application:

```sh
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Use `/admin-login.html` for administrator login and `/login.html` for employees. Local test identities are listed in the main README. Do not seed test accounts in production. Production requires reviewed schema provisioning, at least two real administrators, private database storage outside the checkout, `APP_ENV=production`, an HTTPS `APP_ORIGIN`, and appropriate hosting/proxy privacy configuration.

## Google Cloud configuration and authorization

1. Enable Google Drive API in your team's authorized Google Cloud project.
2. Provision a dedicated service account without domain-wide delegation or personal-user impersonation. Grant it **Viewer** access only to the team's approved knowledge folder. Use the team's separately authorized copy; the organizers' view-only starter folder is not the development knowledge base.
3. Ensure the organization permits sharing with the service-account address and permits download/export. Do not make the folder public or add broad shared-drive membership to work around restrictions.
4. For hosting, use an approved attached service account with short-lived runtime credentials and keep the organization's key-creation policy enforced. Local development now supports [installed-application OAuth](google-drive-oauth.md) with the authorized team account, private credential files outside Git, and metadata verification before ingestion. Never enter credentials in Settings or browser JavaScript. Leave `KNOWLEDGE_SOURCE` unset or set it to `drive` and remove synthetic-source settings.
5. Set `DATABASE_URL` to private storage outside this checkout before importing real documents. Configure access controls and backup retention/deletion. Disable proxy/APM/error-reporting capture of request/response bodies and SQL parameter logging.
6. Sign in as an administrator, open **Settings**, save the knowledge folder ID, and select **Re-sync now**. Check the actual last-success timestamp, error state, document counts, and unreadable list. Saving the ID alone does not verify access.

The application uses the read-only Drive OAuth scope, while the dedicated account's sharing permissions provide the folder access boundary; OAuth scope alone is not a folder restriction. Google documents [Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth), [sharing and inherited permissions](https://developers.google.com/workspace/drive/api/guides/manage-sharing), and [download/export and download capability](https://developers.google.com/workspace/drive/api/guides/manage-downloads). Detailed deployment and Workspace instructions are in [the ingestion guide](ingestion.md).

## Synchronization and employee testing

Add approved Google Docs, text PDFs, or `.docx` documents to the folder or its official category subfolders. Top-level documents apply to every category. Use office-prefixed filenames such as `ALP NOR - Example Policy.pdf`, or styled Word/Docs headings for office-specific sections. There is no website upload mechanism. Legacy `.doc` files must be converted in Drive.

Use **Re-sync now** in the authenticated dashboard. It returns a scheduled acknowledgement and then reports the job's actual outcome. Failed inventory/download/publication preserves the prior index; individual extraction/restriction failures exclude that file and show its reason. The running server checks every five minutes and synchronizes when the last success is 23 hours old. Keep a server instance running or use an external daily scheduler invoking `python -m backend.sync` with the same secure environment.

For a repeatable fictional local check:

```sh
python -m scripts.create_synthetic_documents
export KNOWLEDGE_SOURCE=local
export SYNTHETIC_DOCUMENT_DIR="$PWD/backend/data/synthetic"
python -m backend.sync --folder-id synthetic
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Use a fresh local database initialized as above. Sign in as an employee, choose **Alpharetta** and **All Categories**, and ask `When does equipment inspection occur?`. The source should be `ALP NOR - Fictional Equipment.pdf`, page 1, with the exact quotation `The fictional equipment inspection occurs every Thursday before opening.` Selecting Lilburn excludes this policy. Search `What is the submarine fuel allowance?` to exercise not-found. Restore Drive settings before deploying.

## Verification and remaining limits

Automated verification uses synthetic documents exclusively. The end-to-end test exercises the actual Drive adapter with its network transport mocked: administrator synchronization → Google Docs export/extraction/indexing → employee login → authenticated category-filtered search → verified exact source quotation. It compares database snapshots before/after search and checks captured logs to establish that questions, returned answers, and employee-search associations are not retained by application code. A returned quote can already be present in the database as approved source text; that is distinct from saving an employee response/history.

The automated suite covers all fifteen requested areas: PDF/Google Docs/Word extraction, office classification, every official category, exact quotation verification, unanswerable questions, conflicts, unreadable files, additions/modifications/renames/moves/deletions, unauthorized search/sync, immediate deactivation, and PIN/session invalidation. Additional cases exercise incomplete Drive inventories, stale leases, API failure acknowledgements, safe provider error messages, and retained snapshots after failure.

Final results: **116 passed** (55 existing cases plus 61 added cases), with six dependency deprecation warnings. Both JavaScript syntax checks and `git diff --check` passed.

Run:

```sh
python -m pytest -q
node --check frontend/live-admin.js
node --check frontend/script.js
git diff --check
```

A real team Google Drive connection has **not** been exercised, and no real Ace documents were imported. Live access remains dependent on the team's credentials, folder ID, and authorization. The isolated local HTTP server was reachable and served the login page. Browser visual verification was blocked because computer access to Chrome was not approved.

OCR is intentionally absent. Empty/image-only PDF pages are unreadable. Complex Word textboxes/embedded objects and sophisticated table relationships are not extracted. Lexical retrieval can miss paraphrases or cross-sentence answers; deterministic support/conflict checks do not cover arbitrary semantic entailment or contradictory wording. Those cases require acceptance testing and further work before claiming full semantic coverage. Hosting-level analytics/log retention must also be reviewed by the deployment owner; the application tests cannot certify third-party infrastructure.

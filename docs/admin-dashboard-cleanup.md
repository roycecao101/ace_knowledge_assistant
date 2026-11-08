# Administrator dashboard consolidation

Implemented November 7, 2026. Changes remain local for review before a GitHub commit/push.

## Navigation and behavior

The dashboard now has six sections, in order: Overview, Employee Management, Knowledge Management, Office Management, Admin Management, and Policy Guardian. Existing `#documents`, `#sync`, and `#settings` links resolve to Knowledge Management; `#pulse` resolves to Policy Guardian. Unknown hashes recover to Overview with the correct active navigation item. The existing responsive sidebar/horizontally scrolling mobile navigation, white/light-gray cards, navy typography, teal accents, and rounded styling are retained.

Knowledge Management contains Google Drive folder ID, last successful synchronization, most recent status, last attempt, Re-sync now, and Refresh status. It includes indexed document metadata (filename, category, office, modified date), unreadable file metadata and fixed extraction diagnostics, and the functional folder configuration form. Synchronization polls while running; settings are disabled during that period. Idle pages preserve unsaved settings. Folder changes retain the existing behavior: employee search pauses until the new folder successfully synchronizes. Backend OAuth configuration, account/folder pinning, synchronization leases, scheduled synchronization, and last-successful-snapshot retention after failed attempts remain intact. Fictional inference settings and budget estimates were preview specimens without functional backend controls; they are removed from the consolidated preview.

Office Management reads the database catalog and supports adding offices with unique names and codes. Required entries are Alpharetta (ALP), Norcross (NOR), and Lilburn (LIL, alias ADC). Codes accept 2–10 ASCII letters/digits, start with a letter, and are saved uppercase. Names are whitespace-normalized and compared case-insensitively. Duplicate codes, names, cross-name/code collisions, and Lilburn's reserved ADC alias receive HTTP 409; invalid input receives HTTP 422. Creation uses the existing transaction guard and database uniqueness constraints. There is no office deletion or rename UI.

Employees retain their existing string-valued home-office assignments. Employee creation and the new Edit employee form use the office catalog. Editing employee details invalidates stale employee sessions so changed office/profile context is refreshed at sign-in. Existing deactivation/reactivation, PIN reset, and administrator password controls are preserved. Form submissions prevent duplicate clicks and show failures inside the open dialog. One-time PIN dialogs retain their cleanup behavior and survive the queued close event of the preceding creation form.

Employee search loads its selector from authenticated `GET /api/offices`, retains the signed-in home office, and refreshes available offices on selector focus. The API validates search offices and employee assignments against the same catalog. Synchronization reads the catalog once per inventory and applies registered codes to filename scope and registered names/codes to Word/Google Docs heading scope. Existing company-wide, office-specific, category, scope intersection, and quotation verification behavior remains covered by regression tests. After adding an office, re-sync to classify existing documents using the new code/name. Approved Drive documents are never modified by these changes.

Policy Guardian had no live backend implementation. Its live page is a clean placeholder; the existing fictional policy comparisons remain in the separate synthetic preview.

## Files changed for this task

| Files | Purpose |
|---|---|
| `backend/offices.py` (new), `backend/models.py` | Persistent catalog, required office aliases, and additive migration |
| `backend/main.py` | Authenticated catalog APIs, administrator-only office creation, employee editing, catalog validation, missing-migration diagnostic |
| `backend/seed_test_accounts.py` | Include office initialization in fresh/test schema setup; existing accounts are not reseeded by the migration |
| `backend/taxonomy.py`, `backend/document_parser.py`, `backend/sync_service.py` | Database-driven synchronization scopes and allowlisted extraction diagnostics, including legacy failures |
| `frontend/admin.html`, `frontend/admin.js`, `frontend/live-admin.js`, `frontend/admin.css` | Six-section navigation, consolidated knowledge UI, office directory/forms, employee edit form, safe asynchronous forms and PIN cleanup |
| `frontend/script.js` | Dynamic employee office selector |
| `tests/test_admin_dashboard.py` (new) | Office/API/persistence/filtering/privacy regression tests |
| `tests/test_admin_dashboard_ui.cjs` (new) | Shipped dashboard scripts exercised with an in-memory DOM and synthetic API |
| `tests/test_employee_search_ui.cjs` | Dynamic selector coverage and updated endpoint fixtures |
| `README.md`, this report | Upgrade instructions and verification details |

Pre-existing uncommitted search, authentication, documentation, and test work was preserved. This table describes this task's edits rather than every entry in `git status`.

## Existing database migration

Run with the server's existing environment and database configuration before serving the updated backend:

```sh
python -m backend.offices
```

This command only creates the `offices` table and inserts the three required office catalog entries if missing. It does not reset or reseed accounts, change employee assignments, modify credentials/sessions, or rebuild the knowledge index. It is idempotent. The normal application's startup still performs no schema mutation.

The migration was applied to this workspace's existing database. A local comparison of hashes over every non-office table before and after migration confirmed all existing records were unchanged. No confidential rows, credentials, document contents, or employee-linked questions were printed. Future deployment databases require the same explicit migration with their own `DATABASE_URL`.

## Validation

Passed:

- `.venv/bin/python -m pytest -q`: **357 tests**.
- `node --test tests/test_auth_client.cjs tests/test_employee_search_ui.cjs tests/test_admin_dashboard_ui.cjs`: **24 tests**.
- JavaScript syntax checks and `git diff --check`.
- Read-only running-server verification: all three changed JavaScript assets matched disk; both office catalog endpoints rejected unauthenticated requests with HTTP 401.

Coverage includes office creation, normalized/duplicate/invalid codes and names, ADC alias collisions, concurrent duplicate creation, restart persistence, additive migration preservation, employee creation/editing, dynamic employee selector updates, new and existing office-specific scopes, company-wide/category filtering, administrator-only APIs, CSRF rejection, knowledge settings/synchronization, safe unreadable-file diagnostics, OAuth boundaries, employee search, source quotation verification, navigation aliases, and one-time PIN cleanup. Tests use temporary databases and synthetic documents. The Python suite emits dependency deprecation warnings but has no failures.

## Remaining limitations

- Policy Guardian is a placeholder, as requested for an unimplemented feature.
- New office scope labels take effect in existing documents after synchronization. Office changes themselves persist immediately.
- Visual browser and device-width verification was not completed: automatic approval review rejected Google Chrome access with “Computer Use was not approved to use Google Chrome.” Dashboard interactions were verified using the shipped scripts in an in-memory DOM; the existing responsive CSS was retained.
- A new live Google Drive synchronization was not triggered for this dashboard task. Synchronization and OAuth behavior passed automated regressions; approved Drive content and OAuth configuration were preserved.
- No Git commit or push was performed.

# Document ingestion and synchronization

For the new-document investigation, permission-language correction, and synthetic add/delete verification, see [newly synchronized document retrieval](added-document-retrieval-fix.md).

This extension reuses the existing SQLAlchemy database, authenticated sessions, CSRF checks, employee search page, and administrator layout. It adds no upload route. Documents and the index remain private on the backend. No AI service is used for extraction, retrieval, or quotation generation.

## Developer setup

```sh
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m backend.initialize_knowledge
```

The additive initializer creates four knowledge tables and their indexes without changing accounts, credentials, or existing authentication tables. Back up the database before deployment. On a fresh local installation, first follow the account initialization steps in the main README. Protect the database directory and backups; they contain private source documents. Production must use private storage outside the code checkout via `DATABASE_URL` and apply the same retention/deletion policy to backups. Do not place real documents in this repository.

Extraction and Drive dependencies in `backend/requirements.txt` include PyMuPDF, python-docx, google-api-python-client, google-auth, google-auth-httplib2, google-auth-oauthlib, and httplib2. The Google packages also install their normal transport/auth dependencies.

## Synthetic local synchronization

Generate fictional documents in the ignored local data directory:

```sh
python -m scripts.create_synthetic_documents
export KNOWLEDGE_SOURCE=local
export SYNTHETIC_DOCUMENT_DIR="$PWD/backend/data/synthetic"
python -m backend.sync --folder-id synthetic
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Use those environment settings in the server process too. The local adapter requires `.synthetic-only`, rejects symlinks outside its root, and refuses production. Use it exclusively for made-up documents. It is never exposed through a browser upload interface. Running the generator creates a text PDF, a Word document with office headings, and an intentionally unreadable blank PDF. Google Docs export is exercised with a mocked Drive transport in the tests.

Sign in as an administrator, open Document Management or Google Drive Synchronization, and select **Re-sync now**. Status refreshes automatically during an active synchronization; use **Refresh status** for an immediate check. The PDF `ALP NOR - Fictional Equipment.pdf` should show `indexed`; its blank counterpart appears under **Files I could not read**. In Employee View, choose Alpharetta and ask `When does equipment inspection occur?`. A successful result quotes the PDF with its exact filename, page 1, and Alpharetta/Norcross label. That PDF must not appear for Lilburn. Ask `When does telescope orientation occur?` to retrieve the company-wide Word quotation.

You can edit, rename, move between category folders, add, or delete fictional files and synchronize again. A successful full reconciliation reflects all these operations, including removal of deleted files from search.

## Connect the Google Drive folder

Deployment setup is performed by a technical owner once. Miriam's ongoing work is entirely through the dashboard and Google Drive.

1. Enable Google Drive API in an Ace-owned Google Cloud project with at least two named Ace owners.
2. For local development, follow the [installed-application OAuth guide](google-drive-oauth.md) using the authorized team account, pinned folder, private credential directory, and metadata verification. The remaining steps here describe hosted `DRIVE_AUTH_MODE=adc`. Create a dedicated service account used only for hosting, without creating a key. Do not enable domain-wide delegation or impersonate a Workspace user. Personal-user ADC is rejected; explicit `oauth_local` is the supported development user-authentication path.
3. Share only the knowledge folder with that service account as **Viewer**, ensuring downloads/export are allowed. Do not grant it membership in a broad shared drive, unrelated folder access, or domain-wide access. The read-only OAuth scope is not a folder permission boundary: the identity's Drive sharing permissions must provide that boundary. Review those permissions before deployment and periodically thereafter.
4. Use an attached dedicated service account on supported Google Cloud hosting with short-lived runtime credentials. Keep the enforced service-account key-creation policy enabled. If hosting requires user authorization, use the web-server OAuth deployment design in the [OAuth guide](google-drive-oauth.md); the local desktop client is not suitable. Never put credential JSON or tokens into dashboard settings, browser scripts, Git, logs, or screenshots. Runtime access tokens stay in backend process memory. Verify permitted metadata under the hosted identity before ingestion.
5. Leave `KNOWLEDGE_SOURCE` unset (or set it to `drive`), and remove the synthetic directory setting. In the authenticated dashboard, save the folder ID from the Drive folder URL, then select **Re-sync now**.
6. Review indexed and unreadable files. A new source folder immediately clears the active results until its first successful synchronization, preventing searches against the previously authorized root.

Workspace requirements: an Ace Workspace administrator must confirm the Drive sharing policy under **Apps → Google Workspace → Drive and Docs → Sharing settings** permits the dedicated service-account address to receive Viewer access (service accounts can be considered external). For shared drives, check the drive's restrictions on external users and access for nonmembers. Organizational API controls under **Security → Access and data control → API controls** and Cloud IAM policies must also permit this approved integration. Do not make the folder public or enable delegation as a workaround. If restricted sharing is prohibited, an Ace administrator must approve a narrowly scoped exception or provision an isolated Ace-managed knowledge drive/approved service identity that has no access to other materials; until authorized, the integration remains unavailable. Do not fall back to a developer's personal Drive account. Staff use the existing employee ID/PIN sessions and do not need Google accounts.

Google references: [sharing permissions](https://developers.google.com/workspace/drive/api/guides/manage-sharing), [Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth), [download and export](https://developers.google.com/workspace/drive/api/guides/manage-downloads), [shared-drive support](https://developers.google.com/workspace/drive/api/guides/enable-shareddrives).

Only direct children and approved category subfolders are enumerated. Descendants of a recognized category inherit its category. Unknown top-level subfolders and shortcuts are skipped intentionally. Category names must match the brief exactly. Top-level files belong to all categories. For the local filesystem only, use `Back Office - Clinical Operations` because `/` is a path separator; the Drive category remains `Back Office / Clinical Operations`.

## Synchronization and availability

The running FastAPI process checks every five minutes and attempts sync when the last success is at least 23 hours old, or no successful sync exists. Keep an application instance continuously running; a sleeping hosting plan cannot guarantee daily sync. Multiple workers coordinate with a database lease. An external scheduler may alternatively invoke `python -m backend.sync` at least daily using the same environment, database, and service identity. The operator CLI returns nonzero on failure.

`POST /api/admin/sync` requires the existing valid administrator session and CSRF header and claims a database lease before returning HTTP 202 to initiate a backend task; concurrent requests get HTTP 409. A browser-only animation cannot change sync state. `GET /api/admin/knowledge` (also `/api/admin/documents`) returns private document metadata and status, and `PATCH /api/admin/settings` accepts `{"folder_id":"..."}`. No API returns credentials. Refresh status after requesting sync. The response distinguishes a configured folder from one that has successfully synchronized, returns actual readable/unreadable document counts, and identifies local synthetic mode. Expired worker leases report failure. Missing/expired credentials, denied access, missing files/folders, rate limits, and timeouts have safe administrator guidance. Errors remain visible until another attempt; detailed raw third-party exceptions are intentionally not exposed or logged.

The service inventories the entire authorized subtree, downloads and parses it before taking a database write transaction, and inserts the replacement documents, passages, and inverted term index. Publishing the generation and removing old generations happen in one transaction. Search uses one generation selection inside its retrieval statement. Failed listing, downloading, or publication retains the old index and sets an administrator warning. A parser failure, a download/export restriction reported by Drive, or a legacy `.doc` file marks that individual file unreadable and removes any stale passages for it in the new snapshot. Deleted documents disappear only after a successful inventory, never because a partial listing failed. A crashed worker's lease expires after ten minutes; its stale snapshot cannot publish afterward.

Current protective limits: 25 MB per downloaded document, 100 MB total input per snapshot, 1000 files, 100 MB expanded Word archive, approximately nine minutes of sync work, and a ten-minute lease. Oversized downloads abort sync rather than silently omit files. Runtime monitoring should alert on the administrator-visible failure state. Large folders need reviewed streaming/staging improvements. A single Google API request has a 30-second transport timeout and bounded chunk retries. A failure can leave the prior index stale; restore connectivity/access and re-sync to reconcile deletions.

## Extraction, indexing, and verified search

Separate parser functions handle text PDFs and Word files. Google Docs are exported as DOCX through Drive, then use the same heading-aware Word parser. PDFs retain page numbers; Word and Docs retain nearest styled headings and table cells. Source text, original filename, Drive ID, MIME type, modification time, category, office scope, and SHA-256 content hash are private database fields. The hash covers downloaded/exported bytes. No actual company content is embedded in source code.

Office filename classification recognizes leading `ALP`, `NOR`, `LIL`, or `ADC` codes, including multiple codes separated by spaces, commas, slashes, or dashes. A separating dash before the policy title is recommended. Word/Docs office headings must begin with office names or codes (optionally `Office:`); an incidental mention such as `Travel to Norcross` does not restrict a section. Office headings inherit to subordinate headings and end at the next same-level or higher heading. A heading can narrow a filename’s office scope but cannot expand it. Other text is company-wide. Incidental mentions of Affordable Dental Care do not change scope. PDF office scope comes only from its filename.

`POST /api/search` first validates the active session and CSRF token, then the office and category. Shared query-language processing removes conversational framing, normalizes common inflections and possessives, and expands ordinary synonym families against existing indexed spellings. The phrase “time off” is matched as leave while retaining qualifiers such as paid, sick, annual, or unpaid. A single retrieval statement resolves the active generation, including during concurrent synchronization. Every substantive topic qualifier must still match the passage or heading; partial topic overlap alone is insufficient. Eligible results rank quotation-body matches ahead of heading-only context, then prefer focused passages. Display selection gives each eligible source a slot before taking more quotations from one source. Conflict checking considers all verified eligible candidates before the five-result display limit and applies the same word families while preserving conditions and polarity. Existing generations work without reindexing. See [the general retrieval repair](general-retrieval-fix.md) for the current diagnosis, synthetic regressions, and verification against the running server.

The [conversational retrieval update](conversational-retrieval.md) extends this local language layer with shared multiword equivalents (contact/reach out/get in touch, return/give back), procurement synonyms, complete policy-question framing, and permission/presence intent. Bringing or taking an object to work can match an explicit rule permitting or prohibiting that object's presence. Object identity is checked separately: permission for an object's cage, picture, or transport cannot answer permission for the object itself. A blanket rule for X can cover a question about pet X; a rule limited to pet X cannot establish a rule for all X. Unknown modifiers, unrelated actions, exceptions, amounts, approval and timing still require supporting evidence. No embedding model, external AI call, new dependency, database migration or re-sync is required. FastAPI must load the changed Python modules through development auto-reload or a restart.

Office/category eligibility is applied, placeholders, unanswered template fields, questions posed in documents, and assistant-directed content are excluded at ingestion. Amount/quantity questions require numeric evidence, schedule questions require time evidence, and location/person questions require relevant answer cues. An approved procedural instruction to contact someone is valid evidence. Headings alone cannot promote unrelated body sentences into supporting evidence; a short direct table value may use its heading as context. Only stored source spans are returned. The response supplies `status`, optional fixed `message`, and `results` containing `quote`, `filename`, `heading`, `page`, and `office`. Questions and answers are never written to a table or log by this code. Keep hosting/proxy tracing, error reporting, APM request-body capture, and analytics disabled for these endpoints. Do not enable SQL parameter logging: question terms are query parameters.

The employee not-found state displays only its required fallback message, without an added policy response. Before a quote is returned, the verifier requires exact source-span membership and checks every consecutive six-word window against normalized source text. Matching ignores case, whitespace, punctuation, bullet/dash style; exact span membership deliberately adds a stronger guard because the tool never reconstructs quotes. Quotes have at most 80 whitespace-separated words. Shorter than six words is allowed only for a whole sentence or table-cell excerpt. Replaced/tampered passage text fails verification. A document heading directed at the assistant blocks its section; directed clauses are omitted without rebuilding text around them. Ambiguous PDF section structure is handled conservatively.

No supporting verified passage returns exactly `I could not find this in Ace's approved materials.` Near-identical statements differing in numeric values (including zero through twelve spelled out), weekdays, or negation return both verified passages and exactly `These approved passages disagree. Please check with your manager which one applies.` A narrow counted-event duration comparison also recognizes differing schedules with preserved heading/table conditions. Missing index, database errors, and a 40-second server deadline return exactly `The assistant is unavailable right now. Please check the documents directly or ask your manager.` The existing browser also has a 45-second deadline.

## Functional scope and remaining limits

Search also recognizes a limited start/begin/commence word family on both sides of retrieval while keeping the action mandatory. See [the live employee follow-up](live-employee-search-fix.md) for runtime source fingerprints, opt-in development administrator stage counts, and live HTTP/rendering verification. No reindex is required for this word-family correction.

Implemented and covered by synthetic tests: PDF and Word extraction, mocked Google Docs export/indexing, filename/page/heading retention, office/category filters, full reconciliation, atomic failure retention, admin sync/settings access, unreadable-file reporting, quote tamper rejection, fixed fallback messages, and non-retention of questions. Existing authentication tests continue to pass.

The existing real Drive installation and active index were verified locally on November 7, 2026; see [the synchronization report](dashboard-sync-fix.md) and [employee search report](employee-search-fix.md). Automated regression tests use fictional documents and temporary databases. OCR is not implemented; empty/image-only PDF pages make the file unreadable, including mixed text/scan PDFs. Complex Word content such as textboxes/embedded objects is not extracted; styled heading quality affects office detection. Legacy Word `.doc` requires conversion to `.docx` or Google Docs in Drive and is reported as unreadable. Plain PDF layout does not reliably encode heading levels, so assistant-directed heading exclusion may conservatively exclude later text.

Keyword support checks are deliberately conservative and are not a general semantic entailment engine. Bounded contiguous source context, DOCX ancestor/table labels, and verified complete short source lines are supported; see [the Buildathon diagnosis](buildathon-retrieval-diagnosis.md) for exact failure stages and authenticated live verification. Paraphrases, ambiguous layouts, long/cross-page context, and complex tables may still yield not-found. Conflict detection recognizes near-identical quantity, weekday, and negation conflicts plus narrow counted-event duration disagreements with matching conditions; it does not recognize arbitrary semantic disagreements. Intent checks reject several classes of topical non-answers, but do not prove general semantic entailment. Unusual wording or complex policies require careful acceptance testing. Validate these limits with synthetic acceptance cases before go-live; do not claim broad semantic contradiction detection. Embeddings can later replace the candidate retrieval layer without replacing source verification or office filtering. There is no AI-written policy answer.

Office management and Policy Pulse remain the prior unconnected services; this ingestion task does not implement them or claim full buildathon compliance. Production deployment, retention enforcement, backup deletion, real administrator provisioning, monitoring, and handover into Ace's accounts remain deployment-owner tasks.

## Tests

```sh
python -m pytest -q
node --check frontend/live-admin.js
```

Tests create temporary private databases and fictional PDF/Word files. Google export uses a mocked media downloader. They cover both ingestion behavior and the original authentication/session controls. The end-to-end case uses the real Drive adapter with a mocked network transport, triggers administrator synchronization, signs in as an employee, retrieves an exact Google Docs quotation, and verifies unchanged database contents and no captured search logs. No external Google connection is asserted by this test. See `tests/test_ingestion.py` for acceptance cases and `tests/test_auth.py` for the existing session tests.

## Changed files

- `backend/knowledge_models.py`, `backend/models.py`: register document snapshots, passages, sync state/lease, and indexed terms alongside existing auth models.
- `backend/drive_client.py`, `backend/local_source.py`: restricted Drive and isolated synthetic adapters.
- `backend/document_parser.py`, `backend/document_indexer.py`, `backend/taxonomy.py`: format extraction, source spans, exclusions, classification, and verification.
- `backend/sync_service.py`, `backend/sync.py`: atomic reconciliation, scheduling support, and operator command.
- `backend/search.py`, `backend/main.py`: authenticated retrieval, scheduler lifecycle, and admin APIs.
- `backend/initialize_knowledge.py`: additive schema initialization for an existing deployment.
- `frontend/live-admin.js`: live documents/sync/settings panels using existing components.
- `scripts/create_synthetic_documents.py`, `tests/test_ingestion.py`: fictional fixtures and automated verification.
- `backend/requirements.txt`, `.gitignore`, `README.md`, `docs/ingestion.md`, `docs/admin-ingestion-guide.md`: dependencies, secret/data exclusions, and setup/operations instructions.

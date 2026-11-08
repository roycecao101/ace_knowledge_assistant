# Live employee search follow-up

Verified November 7, 2026, against `http://localhost:8000`.

## Finding and correction

The reported example question was reproduced through the running, authenticated HTTP API. Employee and administrator requests returned HTTP 200 with `status=not_found` in all three offices. The failure occurred in candidate retrieval, before office filtering, answer-evidence checks, quotation verification, or rendering.

The previous repair still required the event predicate to match literally after stemming. The generic start/begin verb family was not recognized. Read-only local analysis found three topic-covering passages, zero full-query matches, and one topic-covering passage passing both answer-evidence and exact-source verification. Only counts and fixed flags left the local process; source text and filenames were excluded.

`backend/search.py` now applies a limited start/begin/commence family to query terms and existing indexed vocabulary. SQL expands corresponding prefixes; the subsequent exact root check rejects lookalikes. The action remains mandatory, so end-only evidence cannot satisfy a start question. This is a general word-family rule with no example-question branches or embedded answers. Existing generations work without reindexing.

## Live verification

| Check | Observed result |
|---|---|
| Server ownership | Uvicorn reload parent PID 74558; initial worker 76574; replacement worker 79088 |
| Working directory / open database | This repository / `backend/ace.db` |
| Loaded search revision after repair | `ec07013484bd5020`, matching the current source fingerprint |
| Employee HTML, `script.js`, `auth-client.js` | HTTP 200; response bytes match current files |
| Cache headers | `Cache-Control: no-store` on HTML and JavaScript |
| Employee endpoint | Same-origin `POST /api/search` through `aceAuth.request`, with session cookie and CSRF token |
| Active documents / unreadable documents | 7 / 0; also confirmed by authenticated administrator metadata |
| Active passages / persisted term rows | 1,053 / 9,181 |
| Reported question after repair | HTTP 200, `found`, one verified result in all three offices |
| Live pipeline counts per office | retrieved=1; office/topic/evidence/quote rejected=0; accepted=1 |
| Actual HTTP response through shipped JS validator/renderer | One quote and matching filename, office, and heading/page; not-found message absent |
| Unauthenticated / missing-CSRF search | HTTP 401 / 403 |
| Database after probe cleanup | Local comparison hashes match for every table |

The API returns an import-time source fingerprint in `X-Ace-Search-Revision`, allowing the loaded module to be compared with disk. An authenticated administrator in development may explicitly request `X-Ace-Search-Diagnostics: counts`; the response includes only fixed integer stage counts in `X-Ace-Search-Trace`. Employees and production receive no stage trace. Traces are never logged or persisted. Category filtering remains in SQL, before the reported retrieved count.

Short-lived probe sessions for existing active accounts were removed in a `finally` block. Existing sessions, accounts, credentials, OAuth configuration, approved documents, and the index were unchanged. No synchronization was requested. HTTP response bodies stayed in local process memory; the frontend check received them over an in-memory subprocess pipe and emitted only flags/counts. No confidential contents, identifiers, credentials, tokens, or employee-linked questions were printed or added to fixtures.

The browser automation connection was unavailable. These checks establish a backend retrieval defect independently of browser caching, verify currently served assets, and exercise the real renderer with the live response in an in-memory DOM. They do not claim inspection of the user's existing tab, its memory, or selected filters. Reload that tab once to clear its previous displayed result.

## Security and regression checks

Authentication, origin enforcement, session/version checks, CSRF rejection/recovery, office/category eligibility, active-generation selection, exact source-span and six-word-window verification, quote limits, conflict handling, and server/browser deadlines remain enforced. No generated policy answers, external model calls, search history, usage analytics, or source-content logging were added.

Regressions use fictional telescope/observatory documents and temporary databases. Added cases cover verb variants in both directions, prefix lookalikes, start/end distinctions, qualifiers, unrelated topics, office/category exclusions, quote tampering, diagnostic access restrictions, production suppression, and citation rendering.

**182 Python tests and 14 JavaScript tests passed.** Python emitted six dependency deprecation warnings. JavaScript syntax checks and `git diff --check` passed.

```sh
.venv/bin/python -m pytest -q
node --test tests/test_auth_client.cjs tests/test_employee_search_ui.cjs
```

## Restart status

**No manual restart is required now.** The existing reload parent loaded the changed code; the live response fingerprint confirms it. No OAuth authorization, resynchronization, schema migration, or reseeding is required.

For a future manual restart, stop the existing reload parent gracefully in its owning terminal before launching this command sequence. Preserve the private environment; starting without it loses the existing local OAuth configuration.

```sh
cd /Users/royce/ace_knowledge_assistant
source .venv/bin/activate
set -a
source .env
set +a
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Retrieval remains conservative lexical search. The added family does not provide arbitrary semantic matching or general contradiction detection. Pre-existing workspace edits were preserved.

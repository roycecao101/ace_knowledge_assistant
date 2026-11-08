# Employee search repair

Follow-up: the original repair missed an event-verb equivalence in the reported employee question. See [the live follow-up](live-employee-search-fix.md) for the reproduced failure, correction, current runtime verification, and restart status. The results below describe the earlier repair.

Verified November 7, 2026, against the existing FastAPI service on port 8000.

## Root cause

The failure was in query processing and candidate retrieval. The SQL query required **every** remaining question word to occur in one passage or its heading. Conversational words such as "need" and "know" were mandatory search terms. Limited plural reduction also failed to connect ordinary forms such as "inspect", "inspected", and "inspection". Results disappeared before quote selection and source verification.

A local aggregate diagnostic constructed topic probes inside the application process without exposing their text. Adding "What do I need to know about ...?" to 963 indexed topics caused the old candidate condition to reject all 963. With the repair, 949 pass candidate matching and 941 also pass the answer-evidence and source-verification checks. These are diagnostic counts, not an accuracy benchmark or a claim that every paraphrase is supported. The original employee questions were not captured or inspected.

A second defect in answer selection rejected any instruction containing "ask", "consult", or "contact" unless the question asked "who". That incorrectly excluded valid procedural directions. The blanket exclusion was removed; requested amount, schedule, location, and person checks still apply.

## Index and pipeline findings

The server has the existing repository's `backend/ace.db` open. Its authenticated administrator metadata matches that database's active documents, saved folder, and last successful sync, November 7 at **7:00:58 PM EST**. No synchronization was triggered for this repair.

| Diagnostic | Result |
|---|---:|
| Active indexed documents | 7 |
| PDF / DOCX documents | 5 / 2 |
| Searchable passages | 1,053 |
| Persisted passage-term rows | 9,181 |
| Documents without extracted text | 0 |
| Empty passages / unreadable documents | 0 / 0 |
| Passages passing exact source verification | 1,053 |
| Passages with complete indexed term sets | 1,053 |
| Stale documents / passages / term rows | 0 / 0 / 0 |
| Company-wide passages | 762 |
| Alpharetta-and-Norcross passages | 282 |
| Norcross-only passages | 9 |

Each of the seven documents contains saved source text and searchable passages. Extraction and persistence succeeded for both formats. Successful publication already removes previous generations; no old synthetic generation is present. Authentication, office eligibility, and category filtering were functioning. "All Categories" documents remain available within specific category selections. All stored passages verify, so source verification was not the blanket cause. Backend exceptions and deadlines already return the distinct unavailable response rather than not-found.

## Fix and files

- `backend/search.py`: normalize request wording consistently in retrieval and evidence checks; match limited word forms against the existing inverted index; rank body evidence ahead of heading context; accept valid contact instructions.
- `tests/test_ingestion.py`: add 12 synthetic regression cases covering natural wording, word forms, ranking, qualifier preservation, contact instructions, conflict detection, prefix lookalikes, concurrent publication, and authenticated office/category filtering.
- `docs/ingestion.md`: update search behavior and live-verification status.
- `docs/employee-search-fix.md`: this report.

Retrieval resolves the active generation within one SQL statement. Full meaningful topic coverage remains required, and a prefix match must pass exact root matching before it can become evidence. Every returned quote still passes the original exact source-span verifier. Conflict checks precede display truncation. No database schema, document content, OAuth settings, account, existing session, CSRF behavior, dashboard, or approved-folder boundary changed. Pre-existing workspace edits were preserved.

## Tests and live verification

**168 Python tests passed; 10 JavaScript tests passed.** `git diff --check` passed. Python reported six dependency deprecation warnings.

| Acceptance case | Result |
|---|---|
| A: Supported question | Verified source quote, correct filename and office label, nearest Word heading or PDF page |
| B: Unsupported question | Exact required not-found message |
| C: Conflicting documents | Exact required disagreement message and both verified sources |
| D: Retrieval failure / timeout | Exact required unavailable message |
| E: Office filtering | Company-wide available to all offices; scoped evidence only in applicable offices |

The isolated regression suite uses fictional DOCX/PDF files and temporary databases. It also covers quote tampering, misleading headings, category exclusions, authentication, CSRF, OAuth, failed sync retention, and generation replacement.

Local runtime diagnostics against the live HTTP API confirmed employee authentication, successful verified retrieval, company-wide access in all three offices, office restrictions, exact unsupported response, HTTP 401 without authentication, HTTP 403 without CSRF, and employee denial from administrator metadata. Short-lived probe sessions were created for existing active accounts and removed afterward. Local before/after comparison hashes confirmed **all database tables unchanged** after cleanup. No existing account or session was changed.

Confidential source text, derived probe questions, quotations, filenames, account identifiers, cookies, and credentials remained inside local processes and were excluded from tool output and this report. No real source content was copied into regression fixtures or sent to an AI service. Actual approved documents were not modified.

## Next steps and limits

The existing Uvicorn reload process loaded the repair, and live HTTP checks exercised it successfully. **No FastAPI restart, new Google authorization, synchronization, or reindexing is needed now.** Refresh the employee interface once and retry a supported question.

Retrieval remains deterministic and lexical. Arbitrary synonyms, cross-sentence reasoning, and complex tables can still abstain. Conflict detection recognizes near-identical statements with different quantities, weekdays, or polarity; it does not establish arbitrary semantic disagreement. This repair adds no generated answers or external model calls.

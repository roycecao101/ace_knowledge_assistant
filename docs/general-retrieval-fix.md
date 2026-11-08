# General employee retrieval repair

Verified November 7, 2026 against the existing FastAPI service at `http://127.0.0.1:8000` and its active `backend/ace.db`. This supersedes the narrow query-language corrections in the earlier employee search reports.

## Root cause

Search used an SQL `HAVING` condition requiring a prefix match for **every** remaining query word, followed by an all-word root check in Python. Ordinary request framing such as “Could you explain the steps for …?” retained `explain` and `steps` as mandatory policy keywords. A passage about the requested subject was discarded unless it happened to contain those request words. Synonym support covered only start/begin/commence; ordinary equivalents such as buy/purchase and notify/inform were also disconnected. The prior huddle repair fixed one verb family without resolving the general problem.

Controlled local probes built from indexed topics demonstrate the failure across every document. For each of the seven documents, ten plain topic questions succeeded. Adding the same conversational framing made all ten return zero candidates. Thus **70/70 plain probes succeeded, and 0/70 conversational probes succeeded before the repair**. All conversational failures occurred before office checks, evidence selection, and quote verification. A representative pair from each document was also reproduced through the running authenticated HTTP endpoint: 7/7 plain succeeded, 0/7 conversational succeeded, with all responses matching the local search implementation.

These internally derived probes measure wording sensitivity, not answer accuracy or support for every possible employee question. A successful retrieval means `found` or `conflict`, both of which include verified source passages. The user's other failing question texts were not provided or captured; individual failures for those undisclosed questions cannot be established retrospectively. No private topic words, source contents, filenames, identifiers, credentials, or returned quotes were printed or copied into fixtures.

## Findings requested

| Check | Finding |
|---|---|
| Starter knowledge base preference | No filename, document-title, or format boost exists. All seven documents passed the plain baseline. The old short-passage ranking and five-result cap could let repeated quotations from one document occupy every display slot; the fix gives each eligible source one slot before taking additional quotations. |
| PDF and DOCX | The active snapshot has five PDFs with 632 passages and two DOCX files with 421 passages. Both use the same retrieval and verification path. All seven documents yielded results. Synthetic identical-language tests pass in both formats, with PDF page and DOCX heading citations preserved. |
| Matching, thresholds, quotes | Mandatory query-word coverage caused the demonstrated failures. There is no relevance-score cutoff to lower. All 1,053 stored passages pass exact-source quotation verification and have complete persisted term sets; quote validation was not the blanket cause. |
| Selected office | The shipped frontend reads the current selector on every submission. A new full-script JavaScript test changes it through all three offices and checks each outgoing request. Live backend requests with different office values enforce the corresponding scope. Changing a selector takes effect on the next search submission. |
| Company-wide access | 762 active passages are company-wide. A live company-wide probe remains retrievable in all three offices; a restricted probe is available only in its permitted offices. Synthetic authenticated tests cover this with conversational synonym queries and category selection. |
| Contradictory evidence | Every eligible verified candidate is checked before display truncation. Tests retrieve both PDF/DOCX policies even after six same-source candidates, and recognize equivalent wording with conflicting quantities or schedules. Different conditions and ineligible offices remain distinct. |
| Actual running service | Reload parent PID 74558, verified worker PID 80284, listening on port 8000. Its working database is this repository's `backend/ace.db`. Authenticated administrator metadata matches seven active documents, and the HTTP search revision `5aa95000a18cc1ad` matches both changed search modules. |

## Implemented improvement

Query framing is normalized before matching and intent checks. Shared language normalization handles common inflections, possessives, ordinary synonym families, and the phrase “time off.” The existing inverted index is searched with spelling variants, then exact canonical topic coverage is checked. Unknown substantive terms, policy qualifiers, actors, and opposing actions remain mandatory; partial topic overlap does not force a result. Manager/supervisor and different leave types are deliberately kept distinct.

Result selection preserves relevance ordering while allocating one display slot per eligible source before taking additional quotations from a source. Conflict comparison uses the same normalized word families, retaining conditions, amounts, weekdays and polarity. No example-question branches or embedded policy answers were added. The diagnostic script derives its questions locally rather than storing Buildathon questions.

The quotation verifier, source text, 80-word quote limit, six-word windows, active-generation boundary, category/office eligibility, authentication, CSRF, origin enforcement, and deadlines are unchanged. No remote model or embedding service receives source contents. This remains deterministic lexical retrieval with bounded language equivalences; arbitrary paraphrases and semantic contradictions remain limitations.

## Verification and data handling

After repair, **70/70 plain and 70/70 conversational probes succeeded** across all seven documents. The same fourteen representative live HTTP requests all succeeded and matched local results. Both employee and administrator authenticated requests were checked. Served employee JavaScript bytes match the workspace. Live office probes passed for company-wide and restricted evidence across all three offices.

The browser automation host was unavailable. The office-selector conclusion combines execution of the shipped JavaScript with live backend HTTP checks; it does not claim observation of the user's existing tab.

Two temporary probe sessions were inserted for existing active accounts and removed in `finally`; no existing account, session, source/index row, OAuth configuration, or saved setting was edited. No synchronization, reseeding, database migration, or index replacement was requested. Final live-probe before/after comparison hashes matched for **every database table**. One initial probe observed a concurrent database change; a repeat before code changes and the final post-change probe both matched all tables. The initial diagnostic did not retain table-level differences, so the concurrent change cannot be attributed more precisely. Probe code writes only its own new session rows and deletes those exact rows during cleanup.

**215 Python tests and 15 JavaScript tests passed**, including 33 additional Python cases for conversational phrasing, synonyms, both formats, preserved qualifiers, tampered quotes, source diversity, conflict retrieval, and authenticated filtering. Python reported six existing dependency deprecation warnings. JavaScript syntax and `git diff --check` passed.

```sh
.venv/bin/python -m pytest -q
node --test tests/test_auth_client.cjs tests/test_employee_search_ui.cjs
.venv/bin/python -m scripts.check_live_retrieval
```

The optional live diagnostic prints aggregate counts and flags only. It uses the current real database and temporarily creates probe sessions, so run it only for authorized local troubleshooting. It never prints private data or runs synchronization.

## Files changed for this repair

- `backend/search_language.py`: shared query framing, morphology, synonym and phrase normalization.
- `backend/search.py`: indexed spelling expansion, consistent evidence/topic matching, source-diverse selection, normalized conflict comparison, combined runtime fingerprint.
- `tests/test_ingestion.py`: synthetic PDF/DOCX retrieval, negative and scope cases, conflict and quote regressions.
- `tests/test_employee_search_ui.cjs`: current office/category request values.
- `scripts/check_live_retrieval.py`: privacy-preserving active-index and authenticated HTTP diagnostic.
- `docs/ingestion.md`: current retrieval behavior and report link.
- `docs/general-retrieval-fix.md`: this report.

Pre-existing workspace edits were preserved.

## Restart

**No manual FastAPI restart is needed.** The existing reload worker has loaded the fix and its HTTP fingerprint matches the updated modules. No resynchronization or reindexing is needed. Refresh the employee page to clear any previously displayed result, then submit the question with the desired filters.

# Newly synchronized document retrieval

Verified November 7, 2026 against the active local database and authenticated FastAPI service.

## Root cause and correction

The new document was correctly synchronized. A direct permission question retrieved it, but “Can I bring a giraffe to the office?” returned `not_found`. Search required `bring` to appear in the source even though the source expresses permission for an object's presence. This failed before office filtering, ranking, and quotation verification. The exact wording of the user's failed search was not supplied; this is a reproduced wording defect rather than a diagnosis of every paraphrase.

`backend/search_language.py` now recognizes a bounded office-entry permission relation: can/may/could I/we bring an object to/into/in an office can match an explicit source rule allowing or prohibiting that object's presence. `backend/search.py` requires the rule's actual subject to cover the requested object and its qualifiers. Purchase, storage, use, inspection, unrelated entities, and heading-only context cannot supply this relationship. Returned quotations retain their original text and negation.

No test filename, animal, answer, or question-specific branch appears in application code. New fixtures use fictional rockets, otters, balloons, kites, and observatory policies. Existing persisted terms remain compatible; reindexing is unnecessary. The rule is deliberately bounded and does not provide arbitrary semantic paraphrase support.

## Requested checks

| Check | Result |
|---|---|
| Active passages and extraction | The active index has eight documents and 1,210 passages. `TEST Giraffe Policy.docx` has one searchable passage, complete persisted terms, no extraction error, and the exact user-provided sentence in its stored source and passage. Its source contains seven words. All 1,210 stored quotations validate. |
| Immediate publication | Sync atomically publishes a generation with its documents, passages, and terms. Search resolves the active generation in its retrieval statement on every request. HTTP 202 means accepted; new content becomes searchable when synchronization successfully publishes. No additional cache rebuild is needed. |
| Short-document ranking | There is no minimum document length or relevance-score threshold. Ranking favors complete body evidence and focused passages, with source-diverse display selection. Mandatory keyword coverage caused the reproduced failure; document length and ranking did not. |
| Filters | The document and passage are company-wide, and its category is `All Categories`: it is eligible in every office/category. Live checks passed all three offices with multiple categories. Synthetic requests passed all 27 official office/category combinations; restricted-office and category exclusions also pass. |
| Quotes below six words | The existing validator already accepts complete source sentences shorter than six words. Added tests accept one-through-five-word sentences and reject incomplete or altered excerpts. Five-word policies are also extracted, indexed, and retrieved in both PDF and DOCX. The user's sentence is seven words. |
| No restart after sync | A single FastAPI app and the same authenticated clients search before addition, after addition sync, and after deletion sync. Availability changes immediately after publication. The real development server automatically loaded the code fix; its HTTP fingerprint matches current source. No manual restart or real-document synchronization was performed. |
| Deletion | Removing a synthetic DOCX from a mocked Drive inventory and re-syncing changes employee search from found to not-found. Its document, passage, and term rows are gone; remaining passages/terms belong to the active generation. The real Drive adapter, extraction, indexing, publication, cleanup, authenticated APIs, and search run; only Google's transport is mocked. No real Drive document was deleted. |

## Tests and regression scope

**274 Python tests and 15 JavaScript tests pass**, including 30 added Python cases. Python reports six existing dependency deprecation warnings. `git diff --check` passes.

Six synthetic control searches retain identical full responses before addition, after addition sync, and after deletion sync. They cover timing, procedures, location, person, amount, and conflicting evidence. The existing regression suite also remains green. The exact original six questions were requested but not supplied, so an exact replay of that particular set remains unverified.

A broader diagnostic loaded before the edit found 71/71 plain and 71/71 conversational topic probes across all eight documents. After reload, 16 representative HTTP responses agreed exactly with that pre-change local implementation. Its old fingerprint differed from the new server as expected; the final targeted check below independently verifies current loaded code. These derived probes measure retrieval continuity, not semantic accuracy or the original six-question benchmark.

The final targeted check made eight employee/admin HTTP searches covering the reproduced permission wording across all three offices and direct permission wording. All returned HTTP 200 / `found`, one verified quotation, matching local results, and matching rendered quotation/citation fields. Administrator traces showed one accepted passage and zero rejection counts. Live metadata matched the active local index; served frontend assets matched workspace files. Unsupported questions still returned not-found, and unauthenticated/missing-CSRF requests returned HTTP 401/403.

Diagnostics printed only aggregate counts and flags. Their temporary probe sessions were removed in `finally`. A first targeted database comparison overlapped another diagnostic's temporary sessions; the final isolated repeat confirmed every database table unchanged. The broader diagnostic also finished with every table unchanged. No confidential contents were emitted or sent to a model, and no existing knowledge row, session, account, credential, OAuth setting, or Drive source was edited.

```sh
.venv/bin/python -m pytest -q
node --test tests/test_auth_client.cjs tests/test_employee_search_ui.cjs
git diff --check
```

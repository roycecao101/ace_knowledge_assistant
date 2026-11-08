# Buildathon retrieval diagnosis

Verified November 7, 2026 against the running local FastAPI service. The three reported failures now return verified evidence through authenticated employee and administrator HTTP requests. The emergency-location case returns `found` with one quotation, the VA referral case returns `found` with two quotations, and the missed-appointment case returns `conflict` with both quotations. The morning-huddle control remains `found`.

The conflicting passages are in the same approved DOCX. The interface now says “approved passages disagree,” which also covers disagreements across different documents. No policy value or confidential quotation is reproduced in this report.

| Case | Confirmed root cause | Original loss point |
|---|---|---|
| Norcross emergency location | Relevant location wording and emergency context were split into different sentence passages under an office heading. The only full-query candidate contained no location expression. | Candidate granularity, followed by answer-eligibility rejection: retrieved=1, evidence_rejected=1, accepted=0. The quotation verifier was never reached. |
| VA referral PDFs | Relevant program, actor, scheduling, treatment, and referral context did not all occur in one sentence passage. The conjunctive candidate SQL required every normalized query term in that single passage/heading. | Candidate retrieval: retrieved=0. PDF extraction, office eligibility, and exact-source quotation validity were present for relevant evidence. Ranking and verification were never reached. |
| Missed-appointment policy | Conversational timing phrasing became mandatory search words. DOCX values also lost ancestor headings and table row/column conditions, hiding another applicable rule. Near-identical-sentence conflict comparison could not compare a terse labeled value with a differently phrased policy. | Original candidate retrieval: retrieved=0. Further isolation restored one result with vocabulary/context recovery; preserving DOCX ancestry and table labels restored the second verified policy and the conflict response. Ranking/display deduplication was not the original cause. |

The initial stage counts above came from local evaluation of the original active snapshot, before edits. They are not claimed as pre-change HTTP measurements. Final results below were measured through the actual authenticated service.

| Requested stage | Emergency location | VA PDFs | Missed-appointment conflict |
|---|---|---|---|
| 1. Relevant metadata | Exists | Exists for two relevant PDFs | Exists |
| 2. Searchable extraction | Exists; location/context fragmented | Exists; relevant context fragmented | Exists; heading/table relationships were incomplete |
| 3. Office/category eligibility | Norcross allowed | Allowed for matching filename offices/categories | Company-wide allowed |
| 4. Final eligible candidates | 4 retrieved, 1 accepted | 2 retrieved, 2 accepted | 2 retrieved and accepted before conflict return |
| 5. Ranking/display retention | 1 result | 2 results | Both conflict results retained before display truncation |
| 6. Exact quotation verification | Pass | Both pass | Both pass |
| 7. Live response and renderer | 1 quotation with citation | 2 quotations with citations | Conflict and both quotations with citations |

The implementation checks answer eligibility and exact quotations before final display ranking. The stage numbers describe the requested diagnostic checkpoints rather than asserting a different execution order. Three non-answer candidates in the final location search are still rejected. No quotation-verification rejection occurred in the successful live probes.

The general correction keeps complete query coverage for ordinary searches while retrieving bounded contiguous context from indexed source spans. A context quotation must be an exact source substring of at most 80 words. It cannot cross document, heading, PDF page, or office scope; excluded/unindexed text interrupts it. Repeated source spans with ambiguous offsets remain usable alone but are not joined. The existing six-word-window and complete-source quotation checks are unchanged.

DOCX citations retain the ancestor heading path. Table values retain applicable column and row labels, including office restrictions. Directed-instruction table headers cannot promote their values into approved evidence. A separate confirmed indexing gap dropped short unpunctuated paragraphs even when extraction marked them searchable. Complete short source lines now reach the existing verifier. One normal synchronization increased the active index from 1,053 to 1,209 passages without changing extracted source snapshots.

Language normalization handles written event forms, ordinal spellings, timing-question framing, and grammatical anaphora. A narrow counted-event timing comparison retains event qualifiers, occurrence counts, explicit possessors, duration units, and business/calendar distinctions. Overlapping ranges, differently bounded rules, and different conditions are not automatically declared contradictory. Terse values with different labels cannot become an unconditional conflict by discarding those labels. Conflict checks precede display ranking and source-diverse selection, preserving both verified quotations.

| Live check | Observed result |
|---|---|
| Loaded code | Import-time fingerprint matches all current retrieval, language, context, timing, parser, indexer, and taxonomy modules |
| Database | Running worker uses this repository and `backend/ace.db`; authenticated document metadata/content hashes/office/category labels match the local active index |
| Active index | 7 documents: 5 PDFs, 2 DOCX; 1,209 passages; 914 company-wide; 0 unreadable documents; 0 stored quotation failures |
| Emergency location across offices | Alpharetta: not_found; Norcross: found; Lilburn: not_found |
| VA query across offices | Alpharetta: found; Norcross: found; Lilburn: not_found; all PDF passage scopes match filename-derived labels |
| Missed-appointment query across offices | conflict in all three offices, with identical company-wide quotations |
| Morning-huddle control | found in all three offices, with identical company-wide quotations |
| Categories | 36 authenticated checks across all nine categories passed eligibility and local/live agreement checks; excluded evidence remains excluded |
| Frontend office/category submission | Shipped JavaScript test changes all three office selections and category selection; each request sends the current values accepted by FastAPI |
| Served assets | Employee HTML, shared authentication client, and search script match workspace bytes |
| Rendering | Actual live responses pass the shipped validator/renderer in an in-memory DOM; every returned quotation and citation is preserved |
| Unsupported fictional question | not_found for both roles |
| Authentication/CSRF | Unauthenticated search: HTTP 401; missing CSRF: HTTP 403 |
| Data preservation | Source snapshots unchanged after synchronization; every non-knowledge database table unchanged after synchronization/probe cleanup; every database table unchanged during final read-only probes |

The API office values are the full names `Alpharetta`, `Norcross`, and `Lilburn`. Filename prefixes use the separate ALP/NOR/LIL/ADC translation. DOCX office headings were already applying Norcross scope in the failing location case. Company-wide evidence remains accessible in every office; no office or category restriction was disabled.

**244 Python tests and 15 JavaScript tests passed.** The 29 added Python cases use fictional inspections, visitors, observatories, and permits. They cover contiguous DOCX/PDF evidence, possessive wording, office/category filtering, page/heading/scope/exclusion boundaries, ambiguous repeated spans, short source lines, ancestor/table context, company-wide visibility, synthetic conflicts beyond display limits, different conditions/possessors, numeric ranges/bounds, table office rows/columns, directed headers, and unsupported qualifiers. Existing quotation-tampering, atomic-publication, authentication, CSRF, Drive, unsupported-question, and UI tests pass. Python reports six dependency deprecation warnings. `git diff --check` passes.

Files changed for this repair:

- `backend/search.py`: context-aware candidate retrieval, evidence checks, conflict integration, complete runtime fingerprint.
- `backend/search_language.py`: query grammar and shared written event/ordinal forms, including persisted-vocabulary prefix compatibility.
- `backend/search_context.py`: bounded exact-source context recovery.
- `backend/timing_policy.py`: conservative counted-event duration comparison.
- `backend/document_parser.py`: ancestor headings, table label context, table office restrictions and directed-header exclusion.
- `backend/document_indexer.py`: verified complete short source lines.
- `frontend/script.js`: accurate conflict wording for passages within one document or across documents.
- `tests/test_ingestion.py`: 29 additional synthetic regression cases.
- `scripts/check_retrieval_stages.py`: ephemeral stdin probes, isolated in-memory preview, optional normal synchronization, authenticated HTTP/rendering checks, count/boolean output and session cleanup.
- `scripts/inspect_index_structure.py`: read-only approved Drive formatting/count diagnostics without source text or identifiers.
- `docs/ingestion.md` and this report: current behavior, verification, limits and operations.

Pre-existing workspace edits were preserved. No official question or expected policy answer was added to application code or regression fixtures. Diagnostic requests were supplied transiently on stdin. No employee history, credentials, tokens, confidential filenames, source contents, or quotations were printed. No external model or embedding service received document contents. Approved Drive documents, account records, existing sessions, OAuth configuration, database schema, and authentication behavior were not modified. Temporary diagnostic sessions were removed in `finally` blocks.

**No manual FastAPI restart or further synchronization is needed now.** The reload worker loaded the latest code, and the required normal Drive synchronization completed. Refresh the employee page once and submit with the intended office/category selections. Future installations of these parser/indexer changes need one normal synchronization to rebuild heading/table metadata and short passages.

Live verification used authenticated employee/admin HTTP requests and the real shipped renderer with live response bodies kept in local memory. The user's existing browser tab, session memory, and physical selector state were not inspected. This establishes the live backend and served rendering path, while leaving that specific tab's state unobserved.

Remaining limits: deterministic lexical/context matching is not general semantic entailment or arbitrary contradiction detection. Unstyled/ambiguous headings and complex tables can still require review. OCR, image-only PDF text, Word textboxes and embedded objects remain unsupported. Context recovery abstains across pages/scopes/headings, ambiguous repeated offsets, excluded gaps, or the 80-word quotation limit. Requests exceeding 2,000 scanned source passages or the 40-second server deadline return unavailable. The conflicting approved policy passages still require an authorized policy owner's decision; both remain visible and neither is silently selected as authoritative.

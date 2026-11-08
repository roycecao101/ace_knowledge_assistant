# Find & Fix Log

Find & Fix Log replaces the Policy Guardian placeholder. Administrators see one row per supported policy issue, its source-derived topic, Needs Review status, representative source filenames, and View details. The page reports raw supported candidate pairs versus distinct issues, the last successful scan, and the latest scan status. Details show exact quotations side by side, original filenames, headings or page numbers, and applicable offices. Previous/Next comparison reveals additional distinct evidence without adding duplicate alerts. Human review is required; the log does not determine which source is correct. The administrator overview links to the log when review is needed. Legacy `#guardian` and `#pulse` links open `#find-fix`.

## Employee/scanner inconsistency investigation

The active application had seven readable approved documents and 1,209 indexed passages. Its successful discrepancy scan referenced the active generation, but produced no pairs. Locally reproducing the employee comparison confirmed the conflict without returning private source contents to development tools.

The cause was comparison coverage, before deduplication: employee search combined its lexical comparison with `timing_policy.timing_conflict`, which understands a counted event and disjoint rescheduling durations. It also recovers bounded, adjacent source context and inherits table ancestor/row labels. The scanner used only `review_signature` and `difference_key` on individual passages. Those required nearly identical ordered wording, matching heading qualifiers and matching explicit modality. The live pair expresses its event through table headings and uses different instruction wording, including an explicit modal on one side and an imperative table instruction on the other. That pair never reached grouping.

Both paths read `knowledge_passages` and `knowledge_documents` from the active approved generation. Employee search restricts candidates to the question, selected office and category; the proactive scanner has no employee-question relevance threshold. The scanner's stricter proposition eligibility was the discrepancy. Same-document comparisons were already permitted. Office intersection was correct, categories did not exclude scanner candidates, and the successful sync had completed its atomic scan. Neither deduplication nor a missing sync hook caused the empty log.

The fix shares source timing extraction and duration comparison with employee search. The scanner discovers candidate counted events from approved prose and table headings, ranks equivalent source-derived descriptions by independent support, and validates each candidate with that shared extractor. Unknown/ambiguous interpretations can still be missed; a completed empty scan only means no supported discrepancies were found. Explicit conflicting modalities, different possessors, different counted conditions, non-overlapping offices, different units, overlapping ranges, bounds, and additional approval/eligibility clauses do not establish a timing conflict. An imperative policy instruction can be compared with a modal instruction. Existing scalar comparison additionally shares the employee vocabulary families for equivalents such as staff/employees and start/begin.

Contiguous context uses the existing employee context-recovery function. It cannot cross document, heading, page, office, excluded-text or ambiguous repeated-span boundaries. A citation stores a single passage ID or an ordered list of IDs; exact quotations are rebuilt from the current private source and verified again. No employee questions, generated probe questions, copied quotations or document contents populate the log.

## Upgrade and restart

Stop the existing server in its owning terminal. From the repository root, activate the existing environment and load the same private configuration used by the server:

```sh
source .venv/bin/activate
set -a
source .env
set +a
python -m backend.initialize_knowledge
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Preserve your existing `DATABASE_URL` and Drive authorization settings. The initializer creates missing knowledge/discrepancy tables with `checkfirst=True`, adds nullable `issue_id` and `evidence_pairs` columns to an existing discrepancy table, and adds a nullable scan `revision`. It is idempotent and does not reset or rewrite existing accounts, sessions, documents, credentials, or alert rows. Legacy pair-only alerts and scans produced by an earlier analyzer revision are withheld as awaiting analysis until a current scan succeeds. The additive migration has been applied to this workspace, and the existing `--reload` FastAPI server loaded the new code automatically. No new dependencies or OAuth authorization are required.

Reload the administrator page, open Find & Fix Log, and click **Re-sync now**. Existing snapshots show “Awaiting a successful synchronization” until a new sync runs. A failed Drive sync retains the previous index and its previous scan; inspect the separate synchronization status for that failure.

## Detection and publication

Analysis runs locally on the searchable passages produced by the approved-folder ingestion pipeline. It sends no documents, prompts or questions to an external AI service. There are no document-specific rules or expected answers.

The administrator matcher compares scalar policy statements with equivalent ordered wording and matching contextual headings. It checks for a single changed numerical value, weekday, schedule frequency, or opposing negation. For counted-event timing rules it uses the shared source extractor and disjoint-duration comparator described above. Number words, supported vocabulary equivalents and unambiguous numeric formatting are normalized for comparison only. Quotations are never reconstructed from normalized text. Additional conservative checks abstain on alternatives, examples, descriptive history, advice versus explicit obligations, and different permitted/prohibited quantities that can coexist. Employee retrieval, quotation verification and conflict behavior are preserved.

Pairs must apply to overlapping offices. Company-wide passages overlap specific offices; disjoint office scopes are excluded. Categories do not suppress comparisons. Different passages in the same document are eligible. Unrelated numbers cannot trigger an alert merely because the numbers differ.

Supported pairs are grouped by the normalized policy proposition, contextual qualifiers, and disputed field. Distinct issues in the same document or document pair stay separate. Different values of the same field share an issue. A duration disagreement and a fee disagreement remain separate even when their filenames match. Filenames never define an issue. Repeated evidence at the same source filename/identity, heading, page, office scope and exact text is shown once; its occurrences still contribute to the raw count. Different quotations and different source locations remain available in details.

The public issue ID is a deterministic SHA-256 of the versioned proposition/disputed-field key. It excludes generation, database row IDs, filenames and the disputed values. An unchanged issue retains its ID across identical synchronizations, reordered passage ingestion, renames, extra duplicate occurrences, and changes to the disputed value. Changing policy wording, heading qualifiers, or another fixed value can create a new identity. The row's internal integer ID is not exposed as the issue ID. Detail links also carry the current generation and expire after re-sync to avoid presenting an old comparison as current.

Each successful synchronization replaces the entire active issue set inside the same database transaction as the new search snapshot, including scheduled syncs. An issue stores its stable ID and current passage-pair references, with a deterministic representative comparison; it stores no copied quotations. Updating or deleting a source removes its obsolete evidence after the next successful sync. If other evidence still supports the issue, the same ID remains active. No quotation history or manual dismissal is stored, and the application never chooses or edits a policy. Detection does not depend on employee questions.

Every displayed pair passes the existing exact source-substring and six-word-window verifier. Detail requests verify all supporting quotations again, along with their policy comparison and office overlap. If any supporting evidence is invalid, that issue is withheld and the log reports incomplete analysis. List responses omit quotation fields and additional evidence. Review reads use a consistent database snapshot.

Analysis is bounded to 50,000 passages, 4,096 discovered event conditions, 200,000 comparisons, 200,000 supported candidate pairs, 5,000 distinct issues and 15 seconds of analysis checks. The raw candidate count means supported, office-overlapping conflicting passage pairs before grouping, not every attempted comparison. If a bound is exceeded, partial issues are discarded and status is **Analysis incomplete**. Other analysis errors report **Scan failed**. In both cases the new search snapshot still publishes. An absent, legacy or outdated analyzer revision reports **Awaiting analysis**. Completed scans distinguish **Completed with discrepancies** from **Completed with no supported discrepancies**. The dashboard displays **Unavailable** for the issue count in failed, incomplete or awaiting states, and omits a numerical candidate count. Raw exceptions are not returned or logged. The last successful scan time remains available. An empty log after failed analysis never claims agreement.

## Demonstrate with fictional Drive documents

Use an authorized test folder containing only fictional approved materials. Keep your existing Drive permissions. Create two Google Docs (or readable DOCX/PDF files), named **Fictional Inspection A** and **Fictional Inspection B**, with these complete sentences:

> Equipment inspection occurs every Monday before the fictional office opens.

> Equipment inspection occurs every Tuesday before the fictional office opens.

1. Synchronize through the existing administrator workflow. Wait for synchronization to complete.
2. Open the administrator Overview: its warning links to Find & Fix Log. Open the log and check the Needs Review pair.
3. Click View details. Both exact quotations appear with their original filenames, heading or PDF page, and applicable office.
4. As an employee, search “When does equipment inspection occur?” using an applicable office and All Categories. Both verified quotations appear with exactly: “These approved documents disagree. Please check with your manager which one applies.”
5. Have the appropriate manager confirm the fictional policy, edit B in Google Drive to agree with A, and click Re-sync now. The active pair and overview warning clear after successful synchronization and refresh.
6. Restore the difference, re-sync, then delete B from the approved test inventory and re-sync. Its active pair clears again.
7. To test a conflict within one document, place both sentences in separate paragraphs under the same heading in A and remove B.
8. To test office filtering, use readable DOCX/PDF filenames beginning `ALP - ` and `NOR - ` respectively. Different offices produce no alert. A company-wide passage paired with an overlapping office passage remains eligible. For Google Docs, explicit office headings provide scope.

Use this fictional demonstration in isolation from real approved materials so other genuine potential discrepancies do not affect the expected total.

## Security and employee behavior

The list and detail APIs require the existing administrator session; unauthenticated and employee requests receive 401/403. The administrator page remains protected. Re-sync reuses the existing CSRF-protected endpoint. There are no employee notifications, browser uploads, Drive permission changes, credential changes, or employee-linked question logs.

Employee retrieval keeps its existing conflict checks and adds the same local comparison for supported forms. It still verifies quotations and applies the selected office and category. Its warning is corrected to the exact required “approved documents” wording in both the backend and renderer.

## Limits

This is a conservative detector of potential discrepancies, not a semantic policy adjudicator. It can miss unsupported paraphrases, changed actors/actions, conflicting before/after relationships, cross-unit durations, complex tables, context beyond a verified 80-word window, and conflicts involving multiple changed values. Some differently worded descriptions of the same policy may remain separate or be missed. Scalar comparison abstains on numeric bounds, approximate values and ranges; counted-event comparison supports disjoint ranges but abstains on overlapping ranges and bounds. Additional timing conditions and qualifiers may require manager review directly in the source. Unreadable files and intentionally excluded passages are not analyzed. Different heading context or tied event interpretations can cause abstention. Matching policy propositions across offices share an issue only from supporting pairs with overlapping offices; individual comparisons retain their scopes. Very large or duplicate-heavy inventories can hit scan bounds. A successful empty scan is not proof that all policies agree. Human review remains required.

## Files and verification

- `backend/policy_conflicts.py`: general local matcher, shared with employee search.
- `backend/policy_issues.py`: administrator reliability checks, disputed-field grouping, stable identity and source-derived topic labels.
- `backend/proactive_policy.py`: source-derived event discovery, shared timing analysis eligibility, imperative/modal handling and timing issue keys.
- `backend/timing_policy.py`, `backend/search_context.py`: shared source timing extraction, duration comparison, verified contiguous context and citation reconstruction.
- `backend/discrepancies.py`: bounded scan, atomic alert replacement and verified review projections.
- `backend/knowledge_models.py`, `backend/initialize_knowledge.py`: additive discrepancy schema.
- `backend/sync_service.py`: scan integration for all successful sync paths, including scheduled runs.
- `backend/main.py`: protected list/detail APIs and schema startup diagnostic.
- `backend/search.py`, `frontend/script.js`: preserve employee conflict behavior and correct the required message.
- `frontend/admin.js`, `frontend/live-admin.js`, `frontend/admin.css`: navigation, overview notification, review page, source dialog and responsive styling.
- `tests/test_discrepancies.py`: synthetic duplicate/near-duplicate grouping, multiple issues in one document, cross-document comparisons, stable IDs, similar unrelated numbers, office scope, edits/deletions, all-evidence verification, DOCX headings/PDF pages, authorization, additive legacy upgrades, restart, concurrent publication and failure checks.
- `tests/test_ingestion.py`: Google Docs export/index integration also checks scan completion.
- `tests/test_admin_dashboard_ui.cjs`, `tests/test_employee_search_ui.cjs`: actual renderer/handler checks with synthetic DOM/API fixtures.
- `README.md`, this guide: operation, demonstration and limitations.

Run from the repository root:

```sh
.venv/bin/python -m pytest -q
node --test tests/test_auth_client.cjs tests/test_employee_search_ui.cjs tests/test_admin_dashboard_ui.cjs
git diff --check
```

Automated regression tests use mocked Google clients and fictional document bytes. Live validation uses the existing authorized local application's normal administrator login, CSRF-protected sync, log and detail APIs. Private contents stay in local memory; only counts and verification flags are emitted. Google Drive documents are read through the existing synchronization pipeline and are never modified. Existing accounts are compared before/after and preserved; the temporary validation login is logged out.

Representative fictional regression counts (independent fixtures):

| Scenario | Raw supported candidate pairs | Distinct displayed issues |
| --- | ---: | ---: |
| Repeated identical statements | 6 | 1 |
| Number-word/formatting variants | 6 | 1 |
| Two unrelated contradictions within one document | 2 | 2 |
| Three documents with three differing schedule values | 3 | 1 |
| Resolved by update or deletion (all evidence removed) | 0 | 0 |

These table counts come from independent fictional automated fixtures. Live validation separately found **one supported candidate pair grouped into one Needs Review issue** in the current seven-document, 1,209-passage index after a successful synchronization. Every detail quotation was locally reverified, required filenames/headings/pages/office fields were present, and its evidence matched the unchanged employee conflict response. The running code and served administrator script matched the workspace. Browser automation was unavailable, so live validation covered the actual API and served script; dashboard interaction is covered by renderer/handler tests.

Final validation: **434 Python tests passed**, **26 JavaScript tests passed**, `node --check frontend/live-admin.js` and `git diff --check` passed. Tests cover within-document and cross-document conflicts, inherited table labels, safe context boundaries, equivalent wording, imperative/modal instructions, duplicate grouping, office applicability, unrelated numbers, changed conditions/actors/units, bounds/ranges, updates/deletions, stale revisions, scan failures, authorization and CSRF. Python emits six existing dependency deprecation warnings. The final live sync also succeeded with one candidate pair and one issue, and the live scan revision matched the current analyzer.

Files changed for this comparison fix: `backend/discrepancies.py`, `backend/proactive_policy.py`, `backend/policy_issues.py`, `backend/timing_policy.py`, `backend/search_context.py`, `backend/knowledge_models.py`, `backend/initialize_knowledge.py`, `backend/main.py`, `frontend/live-admin.js`, `tests/test_discrepancies.py`, `tests/test_admin_dashboard_ui.cjs`, `README.md`, and this guide. Existing uncommitted Find & Fix implementation work was preserved.

For this running `--reload` instance, no manual FastAPI restart or additional synchronization is needed. Reload the administrator page to pick up the updated script. Deployments without automatic reload must migrate, restart FastAPI with their existing configuration, and run a successful synchronization.

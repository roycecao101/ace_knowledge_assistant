# Conversational retrieval update

Implemented November 7, 2026. Verification uses synthetic documents and temporary databases only. This report describes workspace tests, not a verification of the running production worker or confidential documents.

## Root cause

Indexing was not the cause of the reported wording sensitivity. Retrieval first uses a persisted keyword index to obtain candidate documents, then requires every remaining normalized query term to occur in a passage or its heading. Unicode tokenization, plural reduction, suffix stemming, and a small synonym vocabulary already existed. However, ordinary policy-question framing, multiword equivalents and alternative ways to ask permission were incompletely normalized. These words became mandatory source keywords and rejected relevant passages before ranking. The existing office-entry recognizer only handled a narrow can/may/could-I/we-bring form ending in “office.” Possessives were previously stripped after stopword filtering, so an organization possessive could also survive as an unwanted keyword.

The initial synthetic reproduction contained 28 supported searches across multiple objects, procedures and PDF/DOCX formats. Before this update, 24 failed and four succeeded; all 11 unsupported controls returned not-found. The supported set now succeeds in full. None of these tests uses the reported animal or an official example question.

## Retrieval changes

- Normalize complete request frames such as policy on/about/regarding/for, explanatory requests, and “I'm trying to find out.” Normalize possessives before lexical stopword filtering on both query and evidence text.
- Apply symmetric phrase equivalents: contact/reach out to/get in touch with, return/give back/hand back, and late/running late. Extend buy/purchase with procure/procurement. Phrase candidate expansion searches existing written spellings using a content anchor; the complete phrase must still validate in the local evidence stage.
- Recognize multiple grammatical forms of permission questions, direct permission questions, and bringing/taking an object to work, the office or the workplace. Match these to explicit presence rules, retaining the source quotation and its negation.
- Require the actual rule subject to match the requested object after canonical normalization. An incidental noun in a rule about cages, pictures or transport is insufficient. Only the attributive pet role can be covered by an otherwise identical blanket rule; unknown object modifiers remain mandatory. A pet-specific source rule is not generalized to all objects of that kind.

This is dependency-free lexical retrieval with bounded language and relation normalization. A local embedding model was considered unnecessary for this repair: it would add model distribution, resources and relevance calibration without proving that a similar passage supports a requested exception or fact. The existing index already supplies the object/topic anchors. The update improves recall at the query/evidence language layer while retaining strict evidence checks. Arbitrary paraphrases and complex semantic relationships can still return not-found.

## Ranking, scope and evidence

The existing ranking already favors complete evidence in the quotation body, then focused passages. It has no document-length penalty or minimum relevance-score threshold. It remains unchanged. A new regression puts a three-word policy ahead of six longer matching sources, each containing repeated policies. Existing source diversity and conflict checks remain in place; conflicts are checked before the five-result display limit.

Office and category filters, active-generation selection, bounded contiguous context, deadlines, exact substring quotation verification, six-word-window verification, short whole-sentence validation and the 80-word limit remain in place. Returned content is still extracted source text, with existing fixed not-found/conflict/unavailable messages. No policy answer is generated. Missing facts, qualifiers, actors and unrelated actions do not become inferred answers.

## Verification

The update adds 58 synthetic test cases, covering:

- Multiple questions retrieving the same exact supported passage in PDF and DOCX.
- Symmetric synonyms and multiword equivalents, conversational request context, possessives and singular/plural objects.
- Short policy ranking, including a complete three-word policy.
- Unknown objects, injured-object qualifiers, unrelated purchase/storage actions, unsupported fees, approval, timing, medical exemptions and additional conditions.
- Distinguishing an object from its cage, picture or transport, and refusing to broaden a pet-specific rule.
- Authenticated searches across all three offices and all nine categories, preserving each selected filter.
- Conflicting approved sources and tampered quotation rejection under the new question forms.
- Addition, office/category moves, renaming and removal through synchronization, searched on the same app and authenticated client. Removal deletes document, passage and term rows. Existing mocked-Drive lifecycle and response-equality controls also remain covered.

Commands:

```sh
.venv/bin/python -m pytest -q
node --test tests/test_auth_client.cjs tests/test_employee_search_ui.cjs
git diff --check
```

Results: **332 Python tests and 15 JavaScript tests passed**. Python reported six existing dependency deprecation warnings. `git diff --check` and Python compilation checks passed. The original 274 Python cases remain green alongside the 58 added cases.

No live database was queried, no real synchronization was run, and no source document content was sent to an AI service or included in prompts. All new fixtures contain fictional policies. Existing uncommitted changes were retained.

## Loading the update

Restart FastAPI if it is running without `--reload`. A development server using `--reload` should load the Python changes automatically. This task did not inspect or restart the user's running worker, so its loaded revision is not asserted here.

No re-sync, reindex, schema migration, package install, or model download is needed for an already indexed document. Existing persisted terms are supported by the query-time expansion. Future document changes still require a successful normal synchronization; no restart is needed after that publication.

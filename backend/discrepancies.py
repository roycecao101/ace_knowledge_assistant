"""Bounded local scans and administrator-only, reverified source projections."""
import time
import hashlib
from pathlib import Path
from collections import defaultdict
from sqlalchemy import select, delete
from .knowledge_models import KnowledgeState, Document, Passage, DiscrepancyScan, Discrepancy
from .document_indexer import verify_quote
from .policy_issues import identifier, topic
from .proactive_policy import discover_conditions, timing_signature, analysis_signature, issue_key
from .search_context import context_passages, indexed_window
from .search_language import passage_terms

MAX_PASSAGES = 50000
MAX_COMPARISONS = 200000
MAX_ALERTS = 5000
MAX_CANDIDATE_PAIRS = 200000
SCAN_SECONDS = 15
SCAN_ERROR = 'Discrepancy analysis could not complete. Re-sync to retry. The current search index remains available; an empty log does not establish that policies agree.'
REVISION = hashlib.sha256(b''.join(Path(__file__).with_name(name).read_bytes() for name in (
    'discrepancies.py', 'policy_issues.py', 'policy_conflicts.py', 'proactive_policy.py',
    'timing_policy.py', 'search_context.py', 'search_language.py', 'document_indexer.py'))).hexdigest()


class ScanIncomplete(Exception):
    pass


def detect(db, generation):
    deadline = time.monotonic() + SCAN_SECONDS
    documents = {d.id: d for d in db.scalars(select(Document).where(Document.generation == generation, Document.error == ''))}
    passages = db.scalars(select(Passage).where(Passage.generation == generation).order_by(Passage.id).limit(MAX_PASSAGES + 1)).all()
    if len(passages) > MAX_PASSAGES:
        raise ScanIncomplete('Scan limit')
    by_id = {p.id: p for p in passages}
    groups, issues, comparisons, raw_count = defaultdict(list), {}, 0, 0
    def source_key(reference):
        passage = by_id[reference if isinstance(reference, int) else reference[0]]
        document = documents[passage.document_id]
        return (document.file_id, passage.heading, passage.page or 0, passage.text, passage.id, str(reference))
    def deadline_ok():
        if time.monotonic() > deadline:
            raise ScanIncomplete('Scan limit')
        return True
    try:
        conditions = discover_conditions(passages, deadline_ok)
    except ValueError:
        raise ScanIncomplete('Scan limit') from None
    for passage in passages:
        document = documents.get(passage.document_id)
        if not document:
            raise ValueError('Missing readable source')
        if time.monotonic() > deadline:
            raise ScanIncomplete('Scan limit')
        if not verify_quote(passage.text, document.source_text):
            raise ValueError('Unverified indexed passage')
    rows = [(p, documents[p.document_id]) for p in passages]
    for passage, document in context_passages(rows, set(), passage_terms,
            lambda text, heading: timing_signature(text, heading, conditions) is not None, deadline_ok):
        deadline_ok()
        ids = getattr(passage, 'passage_ids', (passage.id,))
        reference = ids[0] if len(ids) == 1 else list(ids)
        fact = analysis_signature(passage.text, passage.heading, conditions, context=len(ids) > 1)
        if not fact:
            continue
        for other, previous, other_ref in groups[fact[0]]:
            comparisons += 1
            if comparisons > MAX_COMPARISONS or time.monotonic() > deadline:
                raise ScanIncomplete('Scan limit')
            if passage.offices and other.offices and not set(passage.offices).intersection(other.offices):
                continue
            key = issue_key(previous, fact)
            if key:
                raw_count += 1
                if raw_count > MAX_CANDIDATE_PAIRS:
                    raise ScanIncomplete('Scan limit')
                issue_id = identifier(key)
                issues.setdefault(issue_id, []).append(tuple(sorted((other_ref, reference), key=source_key)))
                if len(issues) > MAX_ALERTS:
                    raise ScanIncomplete('Scan limit')
        groups[fact[0]].append((passage, fact, reference))
    return [dict(issue_id=issue_id, evidence_pairs=sorted(pairs, key=lambda pair: (
                by_id[pair[0] if isinstance(pair[0], int) else pair[0][0]].document_id == by_id[pair[1] if isinstance(pair[1], int) else pair[1][0]].document_id,
                source_key(pair[0]), source_key(pair[1]))))
            for issue_id, pairs in sorted(issues.items())]


def publish_scan(db, generation):
    """Part of snapshot publication. Failure publishes explicit incomplete state.

    Savepoints discard partial scan writes without discarding the search index.
    No exception text, confidential text, or previous quotations are retained.
    """
    now = time.time()
    status = 'succeeded'
    db.execute(delete(Discrepancy))
    try:
        with db.begin_nested():
            issues = detect(db, generation)
            def first_id(ref):
                return ref if isinstance(ref, int) else ref[0]
            db.add_all(Discrepancy(generation=generation, passage_a=first_id(issue['evidence_pairs'][0][0]),
                                  passage_b=first_id(issue['evidence_pairs'][0][1]), **issue) for issue in issues)
            db.flush()
    except ScanIncomplete:
        status = 'incomplete'
    except Exception:
        status = 'failed'
    scan = db.get(DiscrepancyScan, 1)
    if not scan:
        scan = DiscrepancyScan(id=1)
        db.add(scan)
    scan.generation, scan.status, scan.last_attempt = generation, status, now
    scan.revision = REVISION
    if status == 'succeeded':
        scan.last_success = time.time()


def source(passage, document):
    return dict(quote=passage.text, filename=document.filename, file_id=document.file_id,
                heading=passage.heading, page=passage.page,
                office=' and '.join(passage.offices) + ' only' if passage.offices else 'Company-wide')


def review_log(factory, *, include_evidence=True):
    # Explicit repeatable read: status, references and sources must come from
    # one snapshot even if synchronization publishes/deletes between statements.
    # Load each source once; a join per pair can multiply a large source thousands
    # of times in memory. SQLite's legacy mode needs an explicit read BEGIN.
    with factory() as db:
        if db.get_bind().dialect.name == 'sqlite':
            db.connection().exec_driver_sql('BEGIN')
        else:
            db.connection(execution_options={'isolation_level': 'REPEATABLE READ'})
        state = db.get(KnowledgeState, 1)
        scan = db.get(DiscrepancyScan, 1)
        current = bool(state and scan and scan.generation == state.active_generation and scan.revision == REVISION)
        status = scan.status if current else 'not_scanned'
        items, invalid, raw_count = [], False, 0
        if status == 'succeeded':
            alerts = db.scalars(select(Discrepancy).where(Discrepancy.generation == state.active_generation)
                                .order_by(Discrepancy.id).limit(MAX_ALERTS + 1)).all()
            if len(alerts) > MAX_ALERTS:
                alerts, invalid = [], True
            # Legacy rows have no grouping metadata. Re-sync computes the new
            # identity instead of serving pair rows as if they were issues.
            if any(not alert.issue_id or not alert.evidence_pairs for alert in alerts):
                alerts, status = [], 'not_scanned'
            pair_count = sum(len(alert.evidence_pairs) for alert in alerts)
            if pair_count > MAX_CANDIDATE_PAIRS:
                alerts, invalid = [], True
            ids = {pid for alert in alerts for pair in alert.evidence_pairs for ref in pair
                   for pid in ([ref] if isinstance(ref, int) else ref)}
            def current_records(model, identifiers):
                # Stay below database bind-parameter limits for large scans.
                records, ordered = {}, sorted(identifiers)
                for start in range(0, len(ordered), 500):
                    records.update((row.id, row) for row in db.scalars(select(model).where(
                        model.id.in_(ordered[start:start + 500]), model.generation == state.active_generation)))
                return records
            passages = current_records(Passage, ids)
            doc_ids = {p.document_id for p in passages.values()}
            documents = current_records(Document, doc_ids)
            # Discovery uses the complete active index, just as publication did;
            # a terse table label may inherit its event from another source.
            all_passages = db.scalars(select(Passage).where(Passage.generation == state.active_generation)
                                     .order_by(Passage.id).limit(MAX_PASSAGES + 1)).all()
            if len(all_passages) > MAX_PASSAGES:
                alerts, invalid = [], True
                conditions = []
            else:
                try:
                    review_deadline = time.monotonic() + SCAN_SECONDS
                    def review_deadline_ok():
                        if time.monotonic() > review_deadline:
                            raise ScanIncomplete('Scan limit')
                        return True
                    conditions = discover_conditions(all_passages, review_deadline_ok)
                except (ScanIncomplete, ValueError):
                    alerts, invalid, conditions = [], True, []
            verified, facts = {}, {}
            def valid(passage, document):
                if not passage or not document or document.error:
                    return False
                cache_key = (passage.id, passage.text)
                if cache_key not in verified:
                    verified[cache_key] = verify_quote(passage.text, document.source_text)
                    facts[cache_key] = analysis_signature(passage.text, passage.heading, conditions)
                return verified[cache_key]
            for alert in alerts:
                leading = tuple(ref if isinstance(ref, int) else ref[0] for ref in alert.evidence_pairs[0])
                if (alert.passage_a, alert.passage_b) != leading:
                    invalid = True
                    continue
                evidence, seen, bad = [], set(), False
                for a, b in alert.evidence_pairs:
                    first, doc_a = indexed_window(a, passages, documents)
                    second, doc_b = indexed_window(b, passages, documents)
                    if (not valid(first, doc_a) or not valid(second, doc_b)
                            or (first.offices and second.offices and not set(first.offices).intersection(second.offices))):
                        bad = True
                        break
                    # Recheck the proposition as well as quotation and scope.
                    key = issue_key(facts[(first.id, first.text)], facts[(second.id, second.text)])
                    if not key or identifier(key) != alert.issue_id:
                        bad = True
                        break
                    # Repeated occurrences remain counted, but identical
                    # evidence locations need only one side-by-side display.
                    location = tuple((doc.file_id, p.heading, p.page, tuple(p.offices), p.text)
                                     for p, doc in ((first, doc_a), (second, doc_b)))
                    if location not in seen:
                        evidence.append(dict(document_a=source(first, doc_a), document_b=source(second, doc_b)))
                        seen.add(location)
                if bad or not evidence:
                    invalid = True
                    continue
                raw_count += len(alert.evidence_pairs)
                first_pair = evidence[0]
                item = dict(id=alert.issue_id, generation=alert.generation, status='Needs Review',
                            topic=topic(indexed_window(alert.evidence_pairs[0][0], passages, documents)[0], key[-1]), pair_count=len(alert.evidence_pairs),
                            evidence_count=len(evidence), **first_pair)
                if include_evidence:
                    item['evidence'] = evidence
                else:
                    for name in ('document_a', 'document_b'):
                        item[name].pop('quote')
                items.append(item)
        if invalid:
            status = 'failed'
        return dict(active_count=len(items), raw_candidate_count=raw_count if status == 'succeeded' else None,
                    scan_status=status, last_success=scan.last_success if scan else None,
                    last_attempt=scan.last_attempt if current else None,
                    error=SCAN_ERROR if status in {'failed', 'incomplete'} else '', discrepancies=items)

"""Local-only aggregate diagnostic. Never print private sources or identifiers.

Uses two short-lived probe sessions; never changes existing rows, synchronizes,
or writes questions/results. Run from the repository with python -m scripts.check_live_retrieval.
"""
import hashlib
import json
import secrets
import sqlite3
import time
from collections import Counter
from pathlib import Path

import httpx
from sqlalchemy import select

from backend.auth import digest
from backend.database import database
from backend.document_indexer import terms, verify_quote
from backend.knowledge_models import Document, KnowledgeState, Passage, PassageTerm
from backend.models import Administrator, AuthSession, Employee
from backend.search import REVISION, search
from backend.taxonomy import OFFICES


def fingerprints():
    with sqlite3.connect('file:backend/ace.db?mode=ro', uri=True) as db:
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {name: hashlib.sha256(repr(sorted(db.execute('SELECT * FROM "' + name + '"').fetchall(), key=repr)).encode()).digest()
                for name in tables}


def main():
    before = fingerprints()
    engine, factory = database()
    tokens = []
    report = {}
    try:
        with factory() as db:
            state = db.get(KnowledgeState, 1)
            generation = state.active_generation
            docs = db.scalars(select(Document).where(Document.generation == generation).order_by(Document.id)).all()
            rows = db.scalars(select(Passage).where(Passage.generation == generation).order_by(Passage.id)).all()
            stored = {}
            for row in db.scalars(select(PassageTerm).where(PassageTerm.generation == generation)):
                stored.setdefault(row.passage_id, set()).add(row.term)
            by_id = {doc.id: doc for doc in docs}
            report['index'] = dict(documents=len(docs), passages=len(rows),
                formats=dict(Counter('pdf' if doc.mime_type == 'application/pdf' else 'docx' for doc in docs)),
                quote_failures=sum(not verify_quote(p.text, by_id[p.document_id].source_text) for p in rows),
                term_failures=sum(stored.get(p.id, set()) != terms(p.text + ' ' + p.heading) for p in rows),
                company_wide=sum(not p.offices for p in rows))
            # Controlled wording pairs from indexed topics. These are coverage
            # probes, not actual employee questions or an accuracy benchmark.
            probes = []
            for ordinal, doc in enumerate(docs, 1):
                passages = [p for p in rows if p.document_id == doc.id]
                topics = []
                for p in passages:
                    topic = sorted(t for t in terms(p.text) if t.isalpha() and len(t) > 4)[:3]
                    if len(topic) == 3 and topic not in [t for _, t in topics]:
                        topics.append((p, topic))
                    if len(topics) == 10:
                        break
                counts = Counter()
                for p, topic in topics:
                    question = 'What do I need to know about ' + ' '.join(topic) + '?'
                    conversational = 'Could you explain the steps for ' + ' '.join(topic) + '?'
                    office = p.offices[0] if p.offices else OFFICES[0]
                    counts['plain_found'] += search(factory, question, office, 'All Categories')['status'] in ('found', 'conflict')
                    trace = {}
                    result = search(factory, conversational, office, 'All Categories', diagnostics=trace)
                    counts['conversational_found'] += result['status'] in ('found', 'conflict')
                    counts['zero_candidates'] += trace['retrieved'] == 0
                    counts['quote_rejected'] += trace['quote_rejected']
                    if len(probes) < ordinal:
                        probes.append((question, conversational, office))
                report.setdefault('documents', []).append(dict(ordinal=ordinal,
                    starter='starter knowledge' in doc.filename.casefold(),
                    format='pdf' if doc.mime_type == 'application/pdf' else 'docx',
                    passages=len(passages), probes=len(topics), **counts))
            accounts = [(role, db.scalar(select(model).where(model.active.is_(True))))
                        for role, model in [('admin', Administrator), ('employee', Employee)]]
        clients = {}
        for role, account in accounts:
            if account is None:
                continue
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            with factory.begin() as db:
                db.add(AuthSession(token_hash=digest(token), role=role, account_id=account.id,
                    version=account.version, csrf=csrf, expires=time.time() + 300))
            tokens.append(digest(token))
            clients[role] = httpx.Client(base_url='http://127.0.0.1:8000',
                cookies={'ace_session': token}, headers={'X-CSRF-Token': csrf,
                    'Origin': 'http://127.0.0.1:8000', 'X-Ace-Search-Diagnostics': 'counts'}, timeout=45)
        client = clients.get('admin') or clients['employee']
        live = Counter()
        revisions = set()
        for plain, conversational, office in probes:
            for label, question in [('plain', plain), ('conversational', conversational)]:
                response = client.post('/api/search', json=dict(question=question, office=office, category='All Categories'))
                revisions.add(response.headers.get('X-Ace-Search-Revision'))
                data = response.json()
                live[label + '_found'] += data.get('status') in ('found', 'conflict')
                live['http_200'] += response.status_code == 200
                live['local_agreement'] += data == search(factory, question, office, 'All Categories')
        report['live'] = dict(live, source_matches=revisions == {REVISION}, revision=sorted(revisions))
        scope_checks = {}
        # Derive short local probes without exposing their words or responses.
        for label, scoped in [('company', False), ('restricted', True)]:
            tested = 0
            for passage in rows:
                if bool(passage.offices) != scoped or len(terms(passage.text)) > 15:
                    continue
                question = 'What do I need to know about ' + passage.text
                expected = search(factory, question, passage.offices[0] if scoped else OFFICES[0], 'All Categories')
                if expected['status'] not in ('found', 'conflict'):
                    continue
                if not any(r['quote'] == passage.text for r in expected['results']):
                    continue
                valid = True
                for office in OFFICES:
                    data = client.post('/api/search', json=dict(question=question,
                        office=office, category='All Categories')).json()
                    quotes = data.get('results', [])
                    present = any(r['quote'] == passage.text for r in quotes)
                    valid &= present == (not scoped or office in passage.offices)
                    valid &= all(any(p.text == r['quote'] and by_id[p.document_id].file_id == r['file_id']
                        and (not p.offices or office in p.offices) for p in rows) for r in quotes)
                tested += 1
                scope_checks[label + '_all_offices_pass'] = bool(valid)
                break
            scope_checks[label + '_probes'] = tested
        report['live_office_checks'] = scope_checks
        for role, c in clients.items():
            _, question, office = probes[0]
            response = c.post('/api/search', json=dict(question=question,
                office=office, category='All Categories'))
            report[role + '_conversational_probe'] = dict(http=response.status_code, status=response.json().get('status'))
        metadata = client.get('/api/admin/knowledge').json()
        report['live_metadata_matches'] = metadata.get('indexed_count') == len(docs) if 'indexed_count' in metadata else (
            len(metadata.get('documents', [])) == len(docs))
        report['served_script_matches'] = client.get('/script.js').content == Path('frontend/script.js').read_bytes()
    finally:
        for token_hash in tokens:
            with factory.begin() as db:
                session = db.get(AuthSession, token_hash)
                if session:
                    db.delete(session)
        for client in locals().get('clients', {}).values():
            client.close()
        engine.dispose()
        after = fingerprints()
        report['all_database_tables_unchanged'] = before == after
        report['changed_tables'] = [name for name in before if before[name] != after.get(name)]
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    # Third-party exceptions can embed private SQL parameters or source values.
    try:
        main()
    except Exception as exc:
        print(json.dumps({'diagnostic_failed': type(exc).__name__}))
        raise SystemExit(1) from None

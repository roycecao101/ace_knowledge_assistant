"""Local diagnostics. Read ephemeral probe JSON on stdin; output counts/flags only.

--preview rebuilds an isolated in-memory index from approved Drive sources.
Otherwise checks the actual authenticated HTTP service using temporary sessions.
Never persist probes, print response/source text, or change existing sessions.
"""
import argparse
import hashlib
import json
import secrets
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import httpx
from sqlalchemy import inspect, select

from backend.auth import digest
from backend.database import Base, database
from backend.document_indexer import index_document, verify_quote
from backend.document_parser import parse
from backend.knowledge_models import Document, KnowledgeState, Passage
from backend.models import Administrator, AuthSession, Employee
from backend.search import REVISION, search
from backend.sync_service import SyncService
from backend.taxonomy import OFFICES


def snapshot(engine):
    with engine.connect() as connection:
        return {table: hashlib.sha256(repr(sorted(connection.exec_driver_sql(
            'SELECT * FROM "' + table + '"').all(), key=repr)).encode()).digest()
            for table in inspect(engine).get_table_names()}


def index_rows(factory):
    with factory() as db:
        state = db.get(KnowledgeState, 1)
        documents = db.scalars(select(Document).where(Document.generation == state.active_generation).order_by(Document.id)).all()
        passages = db.scalars(select(Passage).where(Passage.generation == state.active_generation)).all()
        return state, documents, passages


def summary(factory):
    _, documents, passages = index_rows(factory)
    by_id = {d.id: d for d in documents}
    return dict(documents=len(documents), passages=len(passages),
        formats=dict(Counter(d.mime_type for d in documents)),
        unreadable=sum(bool(d.error) for d in documents),
        company_wide=sum(not p.offices for p in passages),
        quotation_failures=sum(not verify_quote(p.text, by_id[p.document_id].source_text) for p in passages))


def preview(factory, probes):
    state, documents, _ = index_rows(factory)
    source = SyncService.default_source()
    files = {f.id: f for f in source.inventory(state.folder_id)}
    engine, temporary = database('sqlite://')
    try:
        Base.metadata.create_all(engine)
        with temporary.begin() as db:
            db.add(KnowledgeState(id=1, active_generation='preview'))
            unchanged = True
            for original in documents:
                file = files[original.file_id]
                data = source.read(file)
                parsed = parse(data, file.mime, file.name)
                unchanged &= parsed.source == original.source_text
                document = Document(generation='preview', file_id=file.id, filename=file.name,
                    mime_type=file.mime, category=file.category, offices=original.offices,
                    modified=file.modified, content_hash=hashlib.sha256(data).hexdigest(),
                    source_text=parsed.source, error='')
                db.add(document)
                db.flush()
                index_document(db, document, parsed)
        report = dict(source_snapshots_unchanged=bool(unchanged), index=summary(temporary), probes=[])
        for ordinal, probe in enumerate(probes, 1):
            trace = {}
            result = search(temporary, **probe, diagnostics=trace)
            report['probes'].append(dict(ordinal=ordinal, status=result['status'],
                quotations=len(result.get('results', [])), stages=trace))
        return report
    finally:
        engine.dispose()


def live(factory, probes, base_url, synchronize=False):
    _, documents, passages = index_rows(factory)
    by_file = {d.file_id: d for d in documents}
    tokens, clients = [], {}
    report = dict(index=summary(factory), probes=[])
    try:
        with factory() as db:
            accounts = [(role, db.scalar(select(model).where(model.active.is_(True))))
                for role, model in [('admin', Administrator), ('employee', Employee)]]
        for role, account in accounts:
            if account is None:
                continue
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            with factory.begin() as db:
                db.add(AuthSession(token_hash=digest(token), role=role, account_id=account.id,
                    version=account.version, csrf=csrf, expires=time.time() + 300))
            tokens.append(digest(token))
            clients[role] = httpx.Client(base_url=base_url, cookies={'ace_session': token},
                headers={'X-CSRF-Token': csrf, 'Origin': base_url,
                    'X-Ace-Search-Diagnostics': 'counts'}, timeout=45)
        if synchronize:
            admin = clients['admin']
            check = admin.post('/api/search', json=dict(question='What is the fictional underwater telescope fuel allowance?',
                office=OFFICES[0], category='All Categories'))
            if check.headers.get('X-Ace-Search-Revision') != REVISION:
                raise RuntimeError('Live code has not reloaded')
            original_sources = {d.file_id: d.source_text for d in documents}
            if admin.post('/api/admin/sync', timeout=180).status_code != 202:
                raise RuntimeError('Synchronization was not accepted')
            limit = time.monotonic() + 180
            while time.monotonic() < limit:
                metadata = admin.get('/api/admin/knowledge').json()
                if not metadata.get('running'):
                    break
                time.sleep(1)
            if metadata.get('sync_status') != 'succeeded':
                raise RuntimeError('Synchronization did not succeed')
            _, documents, passages = index_rows(factory)
            by_file = {d.file_id: d for d in documents}
            report['synchronization_succeeded'] = True
            report['source_snapshots_unchanged'] = original_sources == {d.file_id: d.source_text for d in documents}
            report['index'] = summary(factory)
        for ordinal, probe in enumerate(probes, 1):
            for role, client in clients.items():
                response = client.post('/api/search', json=probe)
                data = response.json()
                results = data.get('results', [])
                verified = all(r['file_id'] in by_file and verify_quote(r['quote'], by_file[r['file_id']].source_text)
                    and any(p.document_id == by_file[r['file_id']].id
                        and p.heading == r['heading'] and p.page == r['page']
                        and (not p.offices or probe['office'] in p.offices) for p in passages)
                    and (probe['category'] == 'All Categories' or by_file[r['file_id']].category in
                        [probe['category'], 'All Categories']) for r in results)
                rendered = subprocess.run(['node', '-e',
                    "let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>{try{process.stdout.write(JSON.stringify(require('./tests/employee_renderer.cjs').inspectRender(JSON.parse(s))))}catch{process.stdout.write('{}')}})"],
                    input=json.dumps(data), text=True, capture_output=True)
                flags = json.loads(rendered.stdout or '{}')
                trace = {key: int(value) for key, value in (part.split('=') for part in
                    response.headers.get('X-Ace-Search-Trace', '').split(',') if part)}
                report['probes'].append(dict(ordinal=ordinal, role=role, http=response.status_code,
                    status=data.get('status'), quotations=len(results), all_verified=verified,
                    loaded_source_matches=response.headers.get('X-Ace-Search-Revision') == REVISION,
                    local_result_matches=data == search(factory, **probe), stages=trace,
                    rendered_quotes=flags.get('rendered_quotes'),
                    rendered_citations_match=flags.get('source_fields_match'),
                    not_found_visible=flags.get('not_found_visible')))
        admin = clients.get('admin')
        if admin:
            metadata = admin.get('/api/admin/knowledge').json()
            remote = {d['file_id']: (d['content_hash'], d['category'], d['offices']) for d in metadata.get('documents', [])}
            report['live_index_matches'] = remote == {d.file_id: (d.content_hash, d.category, d.offices) for d in documents}
        client = clients.get('employee') or admin
        report['served_assets_match'] = all(client.get('/' + filename).content == Path('frontend', filename).read_bytes()
            for filename in ['index.html', 'script.js', 'auth-client.js'])
        negative = dict(question='What is the fictional underwater telescope fuel allowance?', office=OFFICES[0], category='All Categories')
        report['unsupported_not_found'] = all(c.post('/api/search', json=negative).json().get('status') == 'not_found' for c in clients.values())
        report['unauthenticated_rejected'] = httpx.post(base_url + '/api/search', json=negative, timeout=10).status_code == 401
        report['missing_csrf_rejected'] = client.post('/api/search', json=negative, headers={'X-CSRF-Token': ''}).status_code == 403
        report['roles_tested'] = sorted(clients)
        return report
    finally:
        for token_hash in tokens:
            with factory.begin() as db:
                session = db.get(AuthSession, token_hash)
                if session:
                    db.delete(session)
        for client in clients.values():
            client.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--synchronize', action='store_true', help='Publish one normal authorized Drive synchronization before live checks')
    args = parser.parse_args()
    probes = json.load(sys.stdin)
    engine, factory = database()
    before = snapshot(engine)
    try:
        report = preview(factory, probes) if args.preview else live(factory, probes, args.base_url, args.synchronize)
        after = snapshot(engine)
        report['all_database_tables_unchanged'] = before == after
        report['nonknowledge_database_tables_unchanged'] = all(value == after.get(table)
            for table, value in before.items() if not table.startswith('knowledge_'))
        print(json.dumps(report, sort_keys=True))
    finally:
        engine.dispose()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Exceptions from SQL/HTTP/parsers can embed private parameters.
        print(json.dumps({'diagnostic_failed': type(exc).__name__}))
        raise SystemExit(1) from None

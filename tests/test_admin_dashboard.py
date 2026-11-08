"""Dashboard regression checks use isolated databases and fictional documents only."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pytest
from docx import Document as Word
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.main import create_app
from backend.models import Employee, Administrator, AuthSession, Office
from backend.offices import initialize as initialize_offices
from backend.seed_test_accounts import initialize, seed
from backend.sync_service import SyncService
from backend.drive_client import SourceFile, DOCX


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('KNOWLEDGE_SOURCE', 'local')
    instance = create_app(f'sqlite:///{tmp_path}/offices.db')
    initialize(instance.state.engine)
    seed(instance.state.factory)
    yield instance
    instance.state.engine.dispose()


def client(app, role='admin'):
    c = TestClient(app)
    credentials = ({'identifier':'morgan', 'credential':'Ace-Admin-Test-2026'} if role == 'admin'
                   else {'identifier':'ALP-01', 'credential':'24681357'})
    r = c.post(f'/api/auth/{role}/login', json=credentials)
    assert r.status_code == 200
    c.headers['X-CSRF-Token'] = r.json()['csrf_token']
    return c


def add(c, name='Duluth', code='DUL'):
    return c.post('/api/admin/offices', json={'name':name, 'code':code})


def test_catalog_and_idempotent_additive_migration(app):
    c = client(app)
    with app.state.factory() as db:
        before = [(e.id, e.office, e.credential_hash, e.version, e.active) for e in db.scalars(select(Employee))]
        admin_before = [(a.id, a.credential_hash) for a in db.scalars(select(Administrator))]
        sessions = [(s.token_hash, s.csrf) for s in db.scalars(select(AuthSession))]
    assert add(c).status_code == 201
    initialize_offices(app.state.engine)
    initialize_offices(app.state.engine)
    assert c.get('/api/admin/offices').json() == [
        {'name':'Alpharetta', 'code':'ALP', 'aliases':[]},
        {'name':'Duluth', 'code':'DUL', 'aliases':[]},
        {'name':'Lilburn', 'code':'LIL', 'aliases':['ADC']},
        {'name':'Norcross', 'code':'NOR', 'aliases':[]},
    ]
    with app.state.factory() as db:
        assert before == [(e.id, e.office, e.credential_hash, e.version, e.active) for e in db.scalars(select(Employee))]
        assert admin_before == [(a.id, a.credential_hash) for a in db.scalars(select(Administrator))]
        assert sessions == [(s.token_hash, s.csrf) for s in db.scalars(select(AuthSession))]


def test_restart_employee_create_edit_and_selector(app):
    c = client(app)
    assert add(c, '  Duluth  ', 'dul').json()['code'] == 'DUL'
    employee = client(app, 'employee')
    assert any(o['code'] == 'DUL' for o in employee.get('/api/offices').json())
    r = c.post('/api/admin/employees', json={'id':'NEW-01', 'name':'Synthetic New', 'office':'Duluth'})
    assert r.status_code == 200
    new = TestClient(app)
    login = new.post('/api/auth/employee/login', json={'identifier':'NEW-01', 'credential':r.json()['pin']})
    assert login.json()['user']['home_office'] == 'Duluth'
    assert c.patch('/api/admin/employees/NEW-01/details', json={'name':'Synthetic Edited', 'office':'Lilburn'}).status_code == 200
    assert new.get('/api/auth/me').status_code == 401  # Refresh changed account context.
    assert c.patch('/api/admin/employees/NEW-01/details', json={'name':'Synthetic', 'office':'Unknown'}).status_code == 422
    assert c.get('/api/admin/employees').json()[0]['office'] == 'Alpharetta'
    app.state.engine.dispose()
    restarted = create_app(str(app.state.engine.url))
    try:
        other = TestClient(restarted)
        other.cookies.update(c.cookies)
        assert any(o['name'] == 'Duluth' for o in other.get('/api/admin/offices').json())
        assert {e['id']:e['office'] for e in other.get('/api/admin/employees').json()}['NEW-01'] == 'Lilburn'
    finally:
        restarted.state.engine.dispose()


@pytest.mark.parametrize('name,code', [('Other','alp'), ('Other','ADC'), ('ALPHARETTA','OTH'), ('Other','LIL'), ('ALP','OTH'), ('Other','NOR')])
def test_duplicate_names_codes_and_aliases(app, name, code):
    assert add(client(app), name, code).status_code == 409


@pytest.mark.parametrize('name,code', [('', 'NEW'), ('  ', 'NEW'), ('<script>', 'NEW'), ('All offices','NEW'), ('Company-wide','NEW'), ('New','A'), ('New','1ABC'), ('New','A B'), ('New','A/B'), ('New','ABCDEFGHIJK'), ('New','a-b')])
def test_invalid_office(app, name, code):
    assert add(client(app), name, code).status_code == 422


def test_duplicate_concurrent_office(app):
    a, b = client(app), client(app)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(add, [a, b]))
    assert sorted(r.status_code for r in results) == [201, 409]
    assert len([o for o in a.get('/api/admin/offices').json() if o['code'] == 'DUL']) == 1


def test_admin_only_and_csrf(app):
    for c, expected in [(TestClient(app),401), (client(app,'employee'),403)]:
        assert c.get('/api/admin/offices').status_code == expected
        assert add(c).status_code == expected
        assert c.patch('/api/admin/employees/ALP-01/details',json={'name':'Synthetic','office':'Norcross'}).status_code == expected
    assert TestClient(app).get('/api/offices').status_code == 401
    c = client(app)
    c.headers.pop('X-CSRF-Token')
    assert add(c).status_code == 403
    assert c.patch('/api/admin/employees/ALP-01/details',json={'name':'Synthetic','office':'Norcross'}).status_code == 403
    c.headers['X-CSRF-Token'] = 'invalid'
    assert add(c).status_code == 403
    assert not any(o['code'] == 'DUL' for o in c.get('/api/admin/offices').json())


class Source:
    def __init__(self):
        self.files = []

    def add(self, name, paragraphs, category='All Categories'):
        doc = Word()
        for text, heading in paragraphs:
            doc.add_heading(text, 1) if heading else doc.add_paragraph(text)
        stream = BytesIO()
        doc.save(stream)
        self.files.append((SourceFile(str(len(self.files)),name,DOCX,'2026-11-07T12:00:00Z',category), stream.getvalue()))

    def inventory(self, folder):
        return [f for f, _ in self.files]

    def read(self, file):
        return next(data for f, data in self.files if f.id == file.id)


def test_sync_dynamic_office_scopes_categories_and_existing_search(app):
    c = client(app)
    assert add(c).status_code == 201
    source = Source()
    source.add('DUL - Fictional.docx', [('Telescope calibration occurs every Thursday before the office opens.',False)], 'Front Office')
    source.add('Fictional headings.docx', [('Duluth inspection',True), ('Equipment inspection occurs every Tuesday before opening.',False)])
    source.add('Company Fictional.docx', [('Company orientation occurs every Monday before opening.',False)])
    source.add('ADC - Fictional.docx', [('Supply counting occurs every Friday before opening.',False)])
    app.state.sync = SyncService(app.state.factory, lambda:source)
    assert c.patch('/api/admin/settings',json={'folder_id':'synthetic'}).status_code == 200
    assert c.post('/api/admin/sync').status_code == 202
    state = c.get('/api/admin/knowledge').json()
    assert state['sync_status'] == 'succeeded' and state['last_success'] and state['indexed_count'] == 4
    assert c.get('/api/admin/documents').json() == state
    assert all('source_text' not in d and 'quote' not in d for d in state['documents'])
    employee = client(app,'employee')
    def ask(question, office, category='All Categories'):
        r = employee.post('/api/search',json={'question':question,'office':office,'category':category})
        assert r.status_code == 200
        return r.json()
    assert ask('When does telescope calibration occur?', 'Duluth')['status'] == 'found'
    for office in ['Alpharetta','Norcross','Lilburn']:
        assert ask('When does telescope calibration occur?',office)['status'] == 'not_found'
    assert ask('When does telescope calibration occur?', 'Duluth','OSHA & Safety')['status'] == 'not_found'
    assert ask('When does equipment inspection occur?', 'Duluth')['status'] == 'found'
    assert ask('When does equipment inspection occur?', 'Norcross')['status'] == 'not_found'
    assert ask('When does supply counting occur?', 'Lilburn')['status'] == 'found'
    assert ask('When does supply counting occur?', 'Duluth')['status'] == 'not_found'
    for office in ['Alpharetta','Norcross','Lilburn','Duluth']:
        assert ask('When does company orientation occur?',office)['status'] == 'found'
    assert employee.post('/api/search',json={'question':'Synthetic','office':'Invalid','category':'All Categories'}).status_code == 422


def test_legacy_schema_migration_does_not_rewrite_existing_records(app):
    with app.state.factory() as db:
        before = [(e.id, e.office, e.credential_hash) for e in db.scalars(select(Employee))]
    Office.__table__.drop(app.state.engine)  # Isolated legacy-schema fixture.
    initialize_offices(app.state.engine)
    with app.state.factory() as db:
        assert len(list(db.scalars(select(Office)))) == 3
        assert before == [(e.id, e.office, e.credential_hash) for e in db.scalars(select(Employee))]


def test_unreadable_diagnostics_are_fixed_and_metadata_only(app, monkeypatch):
    from backend.document_parser import Unreadable
    from backend.knowledge_models import Document, KnowledgeState
    import backend.sync_service as service
    source = Source()
    source.add('Synthetic unreadable.docx', [('Synthetic text for extraction.',False)])
    app.state.sync = SyncService(app.state.factory, lambda:source)
    app.state.sync.configure('synthetic')
    def fail(*args):
        raise Unreadable('private token and confidential document text')
    monkeypatch.setattr(service, 'parse', fail)
    assert app.state.sync.run()
    c = client(app)
    state = c.get('/api/admin/knowledge').json()
    assert state['unreadable_count'] == 1
    assert state['documents'][0]['error'] == 'File extraction failed. Provide an approved readable version in Drive, then re-sync.'
    assert 'private token' not in str(state)
    with app.state.factory.begin() as db:
        document = db.scalar(select(Document))
        assert document.source_text == '' and 'private token' not in document.error
        document.error = 'private token from a legacy failure'
    assert 'private token' not in c.get('/api/admin/knowledge').text

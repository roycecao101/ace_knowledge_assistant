import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.main import create_app
from backend.seed_test_accounts import initialize, seed
from backend.models import LoginAttempt, Administrator, AuthSession

@pytest.fixture
def app(tmp_path):
    app = create_app(f"sqlite:///{tmp_path}/test.db")
    initialize(app.state.engine)
    seed(app.state.factory)
    yield app
    app.state.engine.dispose()

def login(client, role="employee", identifier="ALP-01", credential="24681357"):
    response = client.post(f"/api/auth/{role}/login", json={"identifier":identifier,"credential":credential})
    if response.status_code == 200:
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response

def admin(app, identifier="morgan"):
    client = TestClient(app)
    assert login(client, "admin", identifier, "Ace-Admin-Test-2026").status_code == 200
    return client

def search(client):
    return client.post("/api/search",json={"question":"Fictional training question", "office":"Norcross", "category":"All Categories"})

@pytest.mark.parametrize("identifier,pin,office",[("ALP-01","24681357","Alpharetta"),("NOR-01","13572468","Norcross")])
def test_employee_login(app, identifier, pin, office):
    c=TestClient(app)
    r=login(c, identifier=identifier, credential=pin)
    assert r.status_code == 200
    assert r.json()["user"]["home_office"] == office
    assert c.get("/api/auth/me").json()["user"]["home_office"] == office
    assert search(c).status_code == 200
    assert "HttpOnly" in r.headers["set-cookie"]
    assert "SameSite=strict" in r.headers["set-cookie"]
    assert "credential_hash" not in r.text

def test_lockout(app):
    c=TestClient(app)
    for _ in range(5):
        assert login(c, credential="00000000").status_code == 401
    assert login(c).status_code == 401
    with app.state.factory() as db:
        attempt=db.scalar(select(LoginAttempt))
        assert 895 < attempt.locked_until-time.time() <= 900
        attempt.locked_until=time.time()-1; attempt.window=time.time()-901
        db.commit()
    assert login(c).status_code == 200

def test_generic_failures(app):
    c=TestClient(app)
    first=login(c, credential="00000000")
    second=login(c, identifier="UNKNOWN")
    assert first.json() == second.json()
    a=admin(app)
    a.patch("/api/admin/employees/ALP-01",json={"active":False})
    assert login(c).json() == first.json()

def test_deactivation(app, monkeypatch):
    calls = []
    def synthetic_search(*args, **kwargs):
        calls.append(True)
        return {'status': 'not_found'}
    monkeypatch.setattr('backend.main.knowledge_search.search', synthetic_search)
    c=TestClient(app); other=TestClient(app)
    assert login(c).status_code == 200
    assert login(other).status_code == 200
    assert search(c).json() == {'status': 'not_found'}
    assert search(other).status_code == 200
    calls.clear()
    anonymous = TestClient(app)
    generic_error = search(anonymous).json()
    a=admin(app)
    assert a.patch("/api/admin/employees/ALP-01",json={"active":False}).status_code==200
    for client in (c, other):
        for _ in range(2):  # The next question and follow-up questions all fail.
            response = search(client)
            assert response.status_code == 401
            assert response.json() == generic_error
        assert client.get('/api/auth/me').status_code == 401
        page = client.get('/index.html', follow_redirects=False)
        assert page.status_code == 303 and page.headers['location'] == '/login.html'
    assert calls == []  # Rejection happens before the search service runs.
    failure = login(TestClient(app), identifier='UNKNOWN')
    for client in (c, TestClient(app)):
        response = login(client)
        assert response.status_code == 401
        assert response.json() == failure.json()
        assert 'set-cookie' not in response.headers

    assert a.patch('/api/admin/employees/ALP-01', json={'active': True}).status_code == 200
    for client in (c, other):
        assert search(client).status_code == 401
        assert client.get('/api/auth/me').status_code == 401
    assert calls == []  # Reactivation cannot restore either old session.
    assert login(c).status_code == 200
    assert search(c).status_code == 200
    assert len(calls) == 1


def test_search_rechecks_active_status_independently_of_session_version(app, monkeypatch):
    from backend.models import Employee
    from sqlalchemy import update
    c = TestClient(app)
    assert login(c).status_code == 200
    # Verify the active-account check itself, independent of version revocation.
    with app.state.factory() as db:
        db.execute(update(Employee).where(Employee.id == 'ALP-01').values(active=False))
        db.commit()
    def unexpected_search(*args, **kwargs):
        pytest.fail('Inactive employee reached the search service')
    monkeypatch.setattr('backend.main.knowledge_search.search', unexpected_search)
    c.headers.pop('X-CSRF-Token')
    response = search(c)
    assert response.status_code == 401
    assert response.json() == {'detail': 'Please sign in again.'}
    assert 'X-CSRF-Error' not in response.headers

def test_pin_replacement(app):
    c=TestClient(app); login(c); a=admin(app)
    r=a.post("/api/admin/employees/ALP-01/pin")
    pin=r.json()["pin"]
    assert len(pin)==8 and pin.isdigit()
    assert search(c).status_code==401
    assert login(c).status_code==401
    assert login(c,credential=pin).status_code==200
    assert "no-store" in r.headers["cache-control"]

@pytest.mark.parametrize("identifier",["morgan","avery"])
def test_admin_login(app,identifier):
    a=admin(app,identifier)
    assert a.get("/admin.html").status_code==200
    assert a.get("/api/admin/employees").status_code==200
    assert search(a).status_code==200
    assert a.get("/api/auth/me").json()["user"]["role"]=="admin"

def test_employee_admin_denial(app):
    c=TestClient(app); login(c)
    for method,path,data in [("GET","/api/admin/employees",None),("POST","/api/admin/employees/ALP-01/pin",None),("PATCH","/api/admin/admins/morgan",{"active":False}),("POST","/api/admin/sync",None),("PATCH","/api/admin/settings",{})]:
        assert c.request(method,path,json=data).status_code==403
    assert c.get("/admin.html",follow_redirects=False).status_code==303

def test_admin_minimum(app):
    a=admin(app)
    assert a.patch("/api/admin/admins/avery",json={"active":False}).status_code==409
    assert a.delete("/api/admin/admins/morgan").status_code==409
    assert a.post("/api/admin/admins",json={"id":"third","name":"Third Test","password":"Long-Test-Password"}).status_code==200
    assert a.patch("/api/admin/admins/third",json={"active":False}).status_code==200
    assert a.delete("/api/admin/admins/avery").status_code==409
    assert a.post("/api/admin/admins",json={"id":"short","name":"Test","password":"short"}).status_code==422

def test_logout(app):
    c=TestClient(app); login(c)
    old=c.cookies.get("ace_session")
    assert c.post("/api/auth/logout").status_code==200
    c.cookies.set("ace_session",old)
    assert search(c).status_code==401

def test_unauthenticated_and_preview(app):
    c=TestClient(app)
    assert search(c).status_code==401
    assert c.get("/api/admin/employees").status_code==401
    assert c.get("/admin.html?preview=1",follow_redirects=False).status_code==303
    assert c.get("/index.html?preview=1",follow_redirects=False).status_code==303
    assert c.get("/README.md").status_code==404

def test_csrf(app):
    c=TestClient(app); login(c)
    c.headers.pop("X-CSRF-Token")
    assert search(c).status_code==403
    assert c.post("/api/auth/logout").status_code==403
    assert c.post("/api/auth/employee/login",headers={"Origin":"https://evil.example"},json={"identifier":"ALP-01","credential":"24681357"}).status_code==403

def test_create_employee_and_password_invalidation(app):
    a=admin(app)
    r=a.post("/api/admin/employees",json={"id":"TEST","name":"Test Employee","office":"Norcross"})
    c=TestClient(app)
    assert login(c,identifier="TEST",credential=r.json()["pin"]).status_code==200
    b=admin(app,"avery")
    assert a.post("/api/admin/admins/avery/password",json={"password":"Replacement-Test-Password"}).status_code==200
    assert b.get("/api/auth/me").status_code==401

def test_expiration_and_seed_preservation(app):
    c=TestClient(app); login(c)
    with app.state.factory() as db:
        session=db.scalar(select(AuthSession)); session.expires=time.time()-1
        original=db.get(Administrator,"morgan").credential_hash
        db.commit()
    seed(app.state.factory)
    with app.state.factory() as db:
        assert db.get(Administrator,"morgan").credential_hash==original
    assert search(c).status_code==401


def test_concurrent_admin_minimum(app):
    from concurrent.futures import ThreadPoolExecutor
    a=admin(app)
    a.post('/api/admin/admins',json={'id':'third','name':'Third Test','password':'Long-Test-Password'})
    b=admin(app,'avery')
    def deactivate(client, identifier):
        return client.patch(f'/api/admin/admins/{identifier}',json={'active':False}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(deactivate,a,'third'),pool.submit(deactivate,b,'morgan')]
        statuses=[f.result() for f in futures]
    assert sorted(statuses)==[200,409]
    with app.state.factory() as db:
        assert len([a for a in db.scalars(select(Administrator)) if a.active])==2

def test_production_configuration(tmp_path,monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('APP_ORIGIN','http://example.test')
    with pytest.raises(RuntimeError):
        create_app(f'sqlite:///{tmp_path}/bad.db')
    monkeypatch.setenv('APP_ORIGIN','https://example.test')
    app=create_app(f'sqlite:///{tmp_path}/secure.db')
    initialize(app.state.engine)
    seed(app.state.factory)  # isolated test fixtures; CLI rejects production seeding
    c=TestClient(app,base_url='https://example.test')
    r=login(c)
    assert 'Secure' in r.headers['set-cookie']
    assert '__Host-ace_session=' in r.headers['set-cookie']
    assert c.get('/api/auth/me').status_code==200
    assert 'Strict-Transport-Security' in r.headers
    assert b'ACE_SYNTHETIC_PREVIEW = true' not in c.get('/auth-client.js').content
    app.state.engine.dispose()

@pytest.mark.parametrize('host', ['127.0.0.1', 'localhost'])
def test_development_same_origin_admin_session(app, host):
    origin = f'http://{host}:8000'
    c = TestClient(app, base_url=origin, headers={'Origin': origin})
    r = login(c, 'admin', 'morgan', 'Ace-Admin-Test-2026')
    assert r.status_code == 200
    assert 'HttpOnly' in r.headers['set-cookie']
    assert 'SameSite=strict' in r.headers['set-cookie']
    assert 'Secure' not in r.headers['set-cookie']
    assert c.get('/api/auth/me').json()['user']['id'] == 'morgan'
    assert c.get('/admin.html').status_code == 200
    assert c.get('/api/admin/admins').status_code == 200
    assert c.post('/api/auth/logout').status_code == 200
    assert c.get('/api/admin/admins').status_code == 401

@pytest.mark.parametrize('origin', ['http://localhost:5500', 'http://127.0.0.1:5500', 'https://evil.example'])
def test_development_rejects_other_origins(app, origin):
    c = TestClient(app, base_url='http://localhost:8000', headers={'Origin': origin})
    assert login(c, 'admin', 'morgan', 'Ace-Admin-Test-2026').status_code == 403

@pytest.mark.parametrize('identifier', ['morgan', 'avery'])
def test_invalid_admin_credentials(app, identifier):
    c = TestClient(app)
    r = login(c, 'admin', identifier, 'invalid-password')
    assert r.status_code == 401
    assert 'set-cookie' not in r.headers
    assert c.get('/api/auth/me').status_code == 401
    assert c.get('/api/admin/admins').status_code == 401


def test_admin_csrf_tracks_session_rotation_and_refresh(app):
    c = admin(app)
    old_cookie = c.cookies.get('ace_session')
    old_csrf = c.headers['X-CSRF-Token']
    assert login(c, 'admin', 'morgan', 'Ace-Admin-Test-2026').status_code == 200
    assert c.cookies.get('ace_session') != old_cookie
    assert c.headers['X-CSRF-Token'] != old_csrf
    c.headers['X-CSRF-Token'] = old_csrf  # An already open tab's page memory.
    response = c.patch('/api/admin/settings', json={'folder_id': 'approved-root'})
    assert response.status_code == 403
    assert response.headers['X-CSRF-Error'] == 'invalid'
    with app.state.factory() as db:
        from backend.knowledge_models import KnowledgeState
        assert db.get(KnowledgeState, 1) is None
    me = c.get('/api/auth/me')
    assert me.status_code == 200 and me.headers['Cache-Control'] == 'no-store'
    c.headers['X-CSRF-Token'] = me.json()['csrf_token']
    assert c.patch('/api/admin/settings', json={'folder_id': 'approved-root'}).status_code == 200
    assert c.post('/api/auth/logout').status_code == 200
    c.cookies.set('ace_session', old_cookie)
    assert c.get('/api/auth/me').status_code == 401


def test_admin_session_and_csrf_survive_backend_recreation(app):
    c = admin(app)
    csrf = c.headers['X-CSRF-Token']
    restarted = create_app(str(app.state.engine.url))
    try:
        other = TestClient(restarted)
        other.cookies.update(c.cookies)
        refreshed = other.get('/api/auth/me')
        assert refreshed.status_code == 200 and refreshed.json()['csrf_token'] == csrf
        assert other.patch('/api/admin/settings', json={'folder_id': 'approved-root'}).status_code == 403
        other.headers['X-CSRF-Token'] = csrf
        assert other.patch('/api/admin/settings', json={'folder_id': 'approved-root'}).status_code == 200
    finally:
        restarted.state.engine.dispose()


@pytest.mark.parametrize('token', [b'', b'wrong-token', b'\xff'])
def test_invalid_csrf_is_rejected_even_for_malformed_header(app, token):
    c = admin(app)
    c.headers.pop('X-CSRF-Token')
    response = c.patch('/api/admin/settings', json={'folder_id': 'approved-root'},
                       headers=[(b'X-CSRF-Token', token)])
    assert response.status_code == 403
    assert response.headers['X-CSRF-Error'] == 'invalid'

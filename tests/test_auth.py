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

def test_deactivation(app):
    c=TestClient(app); other=TestClient(app)
    login(c); login(other)
    a=admin(app)
    assert a.patch("/api/admin/employees/ALP-01",json={"active":False}).status_code==200
    assert search(c).status_code==401
    assert search(other).status_code==401

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

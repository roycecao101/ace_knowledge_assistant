"""Hosted security and durability checks; fictional grants and empty inventories only."""
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch
import time

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from backend.main import create_app
from backend.migrate import migrate, ready
from backend.models import Administrator, AuthSession
from backend.hosting_models import DriveConsent, DriveGrant, SyncRequest
from backend.seed_test_accounts import seed
from backend.drive_auth import DRIVE_SCOPES, DriveAuthError
from backend import drive_web_oauth as web, sync
from backend.job_dispatch import dispatch_sync
from backend.runtime import validate_environment, development_only
from backend.sync_service import SyncService


@pytest.fixture
def hosted(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.delenv('RENDER', raising=False)
    monkeypatch.setenv('APP_ORIGIN', 'https://testserver')
    monkeypatch.setenv('KNOWLEDGE_SOURCE', 'drive')
    monkeypatch.setenv('DRIVE_AUTH_MODE', 'oauth_web')
    monkeypatch.setenv('DRIVE_AUTHORIZED_EMAIL', 'team@example.test')
    monkeypatch.setenv('DRIVE_KNOWLEDGE_FOLDER_ID', 'approved-root')
    monkeypatch.setenv('DRIVE_WEB_CLIENT_ID', 'fictional.apps.googleusercontent.com')
    monkeypatch.setenv('DRIVE_WEB_CLIENT_SECRET', 'fictional-client-secret')
    monkeypatch.setenv('DRIVE_TOKEN_ENCRYPTION_KEY', Fernet.generate_key().decode())
    monkeypatch.setenv('SYNC_EXECUTOR', 'database')
    app = create_app(f'sqlite:///{tmp_path}/hosted.db')
    migrate(app.state.engine)
    seed(app.state.factory)
    yield app
    app.state.engine.dispose()


def login(app, role='admin'):
    client = TestClient(app, base_url='https://testserver')
    body = {'identifier': 'morgan', 'credential': 'Ace-Admin-Test-2026'} if role == 'admin' else {
        'identifier': 'ALP-01', 'credential': '24681357'}
    result = client.post(f'/api/auth/{role}/login', json=body)
    assert result.status_code == 200
    client.headers['X-CSRF-Token'] = result.json()['csrf_token']
    return client


def consent(client):
    result = client.post('/api/admin/drive/connect')
    assert result.status_code == 200
    return parse_qs(urlsplit(result.json()['authorization_url']).query)['state'][0]


def provider(email='team@example.test', refresh='fictional-refresh-token', scopes=None):
    flow = Mock()
    flow.credentials = SimpleNamespace(refresh_token=refresh, granted_scopes=scopes or DRIVE_SCOPES)
    service = Mock()
    service.about.return_value.get.return_value.execute.return_value = {'user': {'emailAddress': email}}
    return flow, service


def callback(client, state, flow, service):
    with patch.object(web, 'new_flow', return_value=flow), patch.object(web, 'build_service', return_value=service), \
            patch('backend.drive_client.DriveClient.inventory', return_value=[]) as inventory:
        response = client.get(web.CALLBACK, params={'state': state, 'code': 'fictional-code'}, follow_redirects=False)
    return response, inventory


def test_connect_requires_admin_session_csrf_and_origin(hosted):
    assert TestClient(hosted).post('/api/admin/drive/connect').status_code == 401
    employee = login(hosted, 'employee')
    assert employee.post('/api/admin/drive/connect').status_code == 403
    admin = login(hosted)
    assert admin.post('/api/admin/drive/connect', headers={'origin': 'https://attacker.test'}).status_code == 403
    admin.headers.pop('X-CSRF-Token')
    assert admin.post('/api/admin/drive/connect').status_code == 403


def test_consent_uses_pkce_state_offline_readonly_and_secure_nonce(hosted):
    client = login(hosted)
    result = client.post('/api/admin/drive/connect')
    query = parse_qs(urlsplit(result.json()['authorization_url']).query)
    assert query['redirect_uri'] == ['https://testserver' + web.CALLBACK]
    assert query['scope'] == DRIVE_SCOPES
    assert query['access_type'] == ['offline']
    assert query['code_challenge_method'] == ['S256']
    assert query['code_challenge']
    cookie = result.headers['set-cookie']
    assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=lax' in cookie
    with hosted.state.factory() as db:
        row = db.scalar(select(DriveConsent))
        assert query['state'][0] != row.state_hash
        assert web.configuration()[1].decrypt(row.encrypted_verifier.encode())
        assert row.encrypted_verifier not in result.text


def test_callback_is_one_use_bound_to_browser_and_live_admin(hosted):
    client = login(hosted)
    state = consent(client)
    flow, service = provider()
    alien = TestClient(hosted, base_url='https://testserver')
    response, _ = callback(alien, state, flow, service)
    assert 'drive=failed' in response.text
    flow.fetch_token.assert_not_called()
    # Simulate Google's cross-site GET: the Strict app cookie is absent.
    client.cookies.delete('ace_session')
    response, inventory = callback(client, state, flow, service)
    assert 'drive=connected' in response.text
    inventory.assert_called_once_with('approved-root')
    assert flow.fetch_token.call_args.kwargs == {'code': 'fictional-code', 'timeout': 30}
    with hosted.state.factory() as db:
        grant = db.get(DriveGrant, 1)
        assert 'fictional-refresh-token' not in grant.encrypted_refresh
        assert web.configuration()[1].decrypt(grant.encrypted_refresh.encode()) == b'fictional-refresh-token'
        assert not db.scalar(select(DriveConsent))
    response, _ = callback(client, state, flow, service)
    assert 'drive=failed' in response.text
    assert flow.fetch_token.call_count == 1


@pytest.mark.parametrize('failure', ['expired', 'deactivated', 'logout', 'wrong-account', 'no-refresh', 'extra-scope', 'provider-error'])
def test_callback_failures_do_not_store_grants_or_leak_details(hosted, failure, caplog):
    client = login(hosted)
    state = consent(client)
    flow, service = provider(email='wrong@example.test' if failure == 'wrong-account' else 'team@example.test',
                             refresh='' if failure == 'no-refresh' else 'fictional-refresh-token',
                             scopes=DRIVE_SCOPES + ['openid'] if failure == 'extra-scope' else DRIVE_SCOPES)
    with hosted.state.factory.begin() as db:
        if failure == 'expired':
            db.execute(update(DriveConsent).values(expires=time.time() - 1))
        if failure == 'deactivated':
            db.get(Administrator, 'morgan').active = False
        if failure == 'logout':
            db.delete(db.scalar(select(AuthSession)))
    if failure == 'provider-error':
        flow.fetch_token.side_effect = RuntimeError('fictional-secret-provider-response')
    response, _ = callback(client, state, flow, service)
    assert 'drive=failed' in response.text
    assert 'fictional-secret-provider-response' not in response.text + str(response.headers) + caplog.text
    with hosted.state.factory() as db:
        assert db.get(DriveGrant, 1) is None


def test_refreshed_service_rechecks_identity_and_config_binding(hosted, monkeypatch):
    config, cipher, binding = web.configuration()
    with hosted.state.factory.begin() as db:
        db.add(DriveGrant(id=1, binding=binding, encrypted_refresh=cipher.encrypt(b'fictional-refresh-token').decode()))
    _, service = provider()
    credentials = Mock(refresh_token='rotated-fictional-refresh')
    with patch('backend.database.database', return_value=(hosted.state.engine, hosted.state.factory)), \
            patch('google.oauth2.credentials.Credentials', return_value=credentials), \
            patch.object(web, 'build_service', return_value=service):
        assert web.load_service() is service
        credentials.refresh.assert_called_once()
    with hosted.state.factory() as db:
        assert cipher.decrypt(db.get(DriveGrant, 1).encrypted_refresh.encode()) == b'rotated-fictional-refresh'
    monkeypatch.setenv('DRIVE_KNOWLEDGE_FOLDER_ID', 'different-root')
    with patch('backend.database.database', return_value=(hosted.state.engine, hosted.state.factory)), \
            pytest.raises(DriveAuthError, match='connect'):
        web.load_service()


class EmptySource:
    def inventory(self, folder):
        assert folder == 'approved-root'
        return []


def test_durable_queue_daily_schedule_and_restart(hosted):
    factory = hosted.state.factory
    service = SyncService(factory, source_factory=EmptySource)
    service.configure('approved-root')
    dispatch_sync(factory)
    hosted.state.engine.dispose()  # Work and account state survive reconnection.
    with patch.object(sync, 'database', return_value=(hosted.state.engine, factory)), \
            patch.object(sync, 'SyncService', return_value=service), patch('sys.argv', ['sync', '--if-due']):
        assert sync.main() == 0
        with factory() as db:
            row = db.get(SyncRequest, 1)
            assert row.requested == row.completed == 1
        with patch.object(service, 'run') as run:
            assert sync.main() == 0
            run.assert_not_called()
        with factory.begin() as db:
            from backend.knowledge_models import KnowledgeState
            db.get(KnowledgeState, 1).last_success = time.time() - 24 * 3600
        assert sync.main() == 0
        assert time.time() - service.status()['last_success'] < 5


def test_failed_work_retries_and_requests_during_run_are_retained(hosted):
    factory = hosted.state.factory
    service = SyncService(factory, source_factory=EmptySource)
    service.configure('approved-root')
    dispatch_sync(factory)
    with patch.object(sync, 'database', return_value=(hosted.state.engine, factory)), \
            patch.object(sync, 'SyncService', return_value=service), patch('sys.argv', ['sync', '--if-due']):
        with patch.object(service, 'run', return_value=False):
            assert sync.main() == 1
        with factory() as db:
            assert db.get(SyncRequest, 1).completed == 0
        def run():
            dispatch_sync(factory)
            return True
        with patch.object(service, 'run', side_effect=run):
            assert sync.main() == 0
        with factory() as db:
            row = db.get(SyncRequest, 1)
            assert row.requested == 2 and row.completed == 1


def test_migration_is_additive_and_idempotent(hosted):
    with hosted.state.factory() as db:
        old = db.get(Administrator, 'morgan').credential_hash
    migrate(hosted.state.engine)
    assert ready(hosted.state.engine)
    with hosted.state.factory() as db:
        assert db.get(Administrator, 'morgan').credential_hash == old


def test_render_fails_closed_without_production_and_desktop_credentials(hosted, monkeypatch):
    monkeypatch.setenv('RENDER', 'true')
    with pytest.raises(RuntimeError, match='production'):
        validate_environment()
    with pytest.raises(RuntimeError, match='local development'):
        development_only()
    monkeypatch.setenv('APP_ENV', 'production')
    validate_environment(web=True)
    monkeypatch.setenv('DRIVE_OAUTH_TOKEN_FILE', '/private/local-token.json')
    with pytest.raises(RuntimeError, match='local credential'):
        validate_environment()


def test_production_database_rejects_sqlite_and_requires_render_tls(hosted, monkeypatch):
    from backend.database import database
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('RENDER', 'true')
    with pytest.raises(RuntimeError, match='PostgreSQL'):
        database('sqlite:///:memory:')
    with pytest.raises(RuntimeError, match='TLS'):
        database('postgresql://fictional:fictional@private.test/ace?sslmode=disable')
    with patch('backend.database.create_engine') as create:
        database('postgres://fictional:fictional@private.test/ace')
        url = create.call_args.args[0]
        assert url.drivername == 'postgresql+psycopg' and url.query['sslmode'] == 'require'
        assert create.call_args.kwargs['hide_parameters'] is True


def test_production_lifespan_cookie_and_queue_endpoint(hosted, monkeypatch):
    # Only substitute the DB connection for HTTP behavior tests, never validation.
    SyncService(hosted.state.factory).configure('approved-root')
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('RENDER', 'true')
    with patch('backend.main.database', return_value=(hosted.state.engine, hosted.state.factory)):
        production = create_app()
    with TestClient(production, base_url='https://testserver') as client:
        assert client.get('/readyz').status_code == 200
        assert client.get('/docs').status_code == 404
        assert client.get('/index.html?preview=1').status_code == 404
        response = client.post('/api/auth/admin/login', json={'identifier': 'morgan', 'credential': 'Ace-Admin-Test-2026'})
        assert '__Host-ace_session=' in response.headers['set-cookie']
        assert 'Secure' in response.headers['set-cookie'] and 'SameSite=strict' in response.headers['set-cookie']
        assert client.post('/api/admin/sync').status_code == 403
        client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        assert client.post('/api/admin/sync').status_code == 202
        with hosted.state.factory() as db:
            assert db.get(SyncRequest, 1).requested == 1
        assert client.post('/api/admin/drive/connect').status_code == 200


def test_release_explicit_real_bootstrap_never_overwrites_credentials(tmp_path, monkeypatch, capsys):
    import json
    from backend.database import database
    from backend import release
    monkeypatch.setenv('APP_ENV', 'development')
    engine, factory = database(f'sqlite:///{tmp_path}/release.db')
    entries = [{'id': 'real-1', 'name': 'Fictional operator one', 'password': 'Fictional-Strong-One-2026'},
               {'id': 'real-2', 'name': 'Fictional operator two', 'password': 'Fictional-Strong-Two-2026'}]
    with patch.object(release, 'database', return_value=(engine, factory)):
        assert release.main() == 1  # No silent test accounts.
        monkeypatch.setenv('BOOTSTRAP_ADMINS', json.dumps(entries))
        assert release.main() == 0
        with factory() as db:
            before = db.get(Administrator, 'real-1').credential_hash
            assert {a.id for a in db.scalars(select(Administrator))} == {'real-1', 'real-2'}
        entries[0]['password'] = 'Changed-Fictional-Value-2026'
        monkeypatch.setenv('BOOTSTRAP_ADMINS', json.dumps(entries))
        assert release.main() == 0
        with factory() as db:
            assert db.get(Administrator, 'real-1').credential_hash == before
    assert 'Fictional-Strong-One-2026' not in capsys.readouterr().out
    engine.dispose()


def test_concurrent_publish_lease_and_reconnect_preserve_prior_index(hosted):
    from backend.sync_service import SyncBusy
    service = SyncService(hosted.state.factory, source_factory=EmptySource)
    service.configure('approved-root')
    assert service.run()
    previous = service.status()['last_success']
    reservation = service.reserve()
    hosted.state.engine.dispose()
    with pytest.raises(SyncBusy):
        service.reserve()
    def failing_source():
        raise RuntimeError('fictional-provider-private-detail')
    failed = SyncService(hosted.state.factory, source_factory=failing_source)
    assert not failed.run(reservation)
    state = failed.status()
    assert state['last_success'] == previous and not state['running']
    assert 'fictional-provider-private-detail' not in state['error']


def test_production_startup_rejects_stale_approved_folder(hosted, monkeypatch):
    SyncService(hosted.state.factory).configure('approved-root')
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('RENDER', 'true')
    monkeypatch.setenv('DRIVE_KNOWLEDGE_FOLDER_ID', 'new-approved-root')
    with patch('backend.main.database', return_value=(hosted.state.engine, hosted.state.factory)):
        production = create_app()
    with pytest.raises(RuntimeError, match='execute the release command'):
        with TestClient(production):
            pass

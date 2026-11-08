"""Credential and folder boundaries, using fictional credentials and mocked Google APIs."""
import json
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from google.oauth2.credentials import Credentials

from backend import drive_auth, drive_oauth
from backend.drive_auth import DRIVE_SCOPES, DriveAuthError, OAuthStore
from backend.drive_client import DriveClient, SourceFile, PDF, FOLDER
from backend.main import create_app
from backend.seed_test_accounts import initialize, seed


@pytest.fixture
def oauth(tmp_path, monkeypatch):
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    client_path, token_path = private / 'client.json', private / 'token.json'
    client_path.write_text(json.dumps({'installed': {
        'client_id': 'fictional-client', 'client_secret': 'fictional-client-secret',
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        'token_uri': 'https://oauth2.googleapis.com/token', 'redirect_uris': ['http://localhost']}}))
    client_path.chmod(0o600)
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('KNOWLEDGE_SOURCE', 'drive')
    monkeypatch.setenv('DRIVE_AUTH_MODE', 'oauth_local')
    monkeypatch.setenv('DRIVE_AUTHORIZED_EMAIL', 'team@example.test')
    monkeypatch.setenv('DRIVE_KNOWLEDGE_FOLDER_ID', 'approved-root')
    monkeypatch.setenv('DRIVE_OAUTH_CLIENT_FILE', str(client_path))
    monkeypatch.setenv('DRIVE_OAUTH_TOKEN_FILE', str(token_path))
    return OAuthStore.configured()


def credentials():
    return Credentials('fictional-access-token', refresh_token='fictional-refresh-token',
        token_uri='https://oauth2.googleapis.com/token', client_id='fictional-client',
        client_secret='fictional-client-secret', scopes=DRIVE_SCOPES)


def google_service(email='team@example.test'):
    service = Mock()
    service.about.return_value.get.return_value.execute.return_value = {'user': {'emailAddress': email}}
    service.files.return_value.get.return_value.execute.return_value = {'id': 'approved-root', 'mimeType': FOLDER}
    service.files.return_value.list.return_value.execute.return_value = {'files': [
        {'id': 'permitted', 'name': 'Fictional Policy.pdf', 'mimeType': PDF}]}
    return service


def test_installed_login_uses_loopback_pkce_and_only_readonly_scope(oauth):
    creds = credentials()
    flow = Mock()
    flow.run_local_server.return_value = creds
    with patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_config', return_value=flow) as build, \
            patch('backend.drive_oauth.build_service', return_value=google_service()):
        drive_oauth.login(oauth)
    assert build.call_args.kwargs == {'scopes': DRIVE_SCOPES, 'autogenerate_code_verifier': True}
    options = flow.run_local_server.call_args.kwargs
    assert options['host'] == '127.0.0.1' and options['port'] == 0 and options['open_browser']
    assert options['access_type'] == 'offline' and options['prompt'] == 'consent'
    assert options['login_hint'] == oauth.email and options['include_granted_scopes'] == 'false'
    assert options['authorization_prompt_message'] == ''
    data = json.loads(oauth.token_path.read_text())
    assert not data['metadata_verified'] and 'token' not in data and 'id_token' not in data
    assert data['refresh_token'] == creds.refresh_token
    assert oauth.token_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('change', ['wrong_account', 'extra_scope', 'no_refresh'])
def test_login_rejects_wrong_identity_or_consent(oauth, change):
    creds = credentials()
    if change == 'extra_scope':
        creds._granted_scopes = DRIVE_SCOPES + ['https://www.googleapis.com/auth/drive']
    if change == 'no_refresh':
        creds._refresh_token = None
    flow = Mock(run_local_server=Mock(return_value=creds))
    with patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_config', return_value=flow), \
            patch('backend.drive_oauth.build_service', return_value=google_service(
                'someone@example.test' if change == 'wrong_account' else oauth.email)):
        with pytest.raises(DriveAuthError):
            drive_oauth.login(oauth)
    assert not oauth.token_path.exists()


def test_verification_lists_metadata_only_and_unlocks_sync(oauth, capsys):
    oauth.save(credentials())
    with pytest.raises(DriveAuthError, match='verify'):
        oauth.load()
    service = google_service()
    with patch.object(Credentials, 'refresh') as refresh, \
            patch('backend.drive_oauth.build_service', return_value=service):
        assert drive_oauth.main(['verify']) == 0
    refresh.assert_called_once()
    output = capsys.readouterr().out
    assert 'Fictional Policy.pdf' in output and 'No documents were downloaded' in output
    assert 'fictional-access-token' not in output and 'fictional-refresh-token' not in output
    service.files.return_value.get_media.assert_not_called()
    service.files.return_value.export_media.assert_not_called()
    assert json.loads(oauth.token_path.read_text())['metadata_verified']
    with patch.object(Credentials, 'refresh') as refresh:
        oauth.load()
        refresh.assert_called_once()


def test_failed_inventory_cannot_mark_verified(oauth, capsys):
    oauth.save(credentials())
    service = google_service()
    service.files.return_value.list.return_value.execute.side_effect = RuntimeError('fictional-refresh-token')
    with patch.object(Credentials, 'refresh'), patch('backend.drive_oauth.build_service', return_value=service):
        assert drive_oauth.main(['verify']) == 1
    assert not json.loads(oauth.token_path.read_text())['metadata_verified']
    assert 'fictional-refresh-token' not in capsys.readouterr().out


@pytest.mark.parametrize('field,value', [('approved_email', 'wrong@example.test'),
    ('approved_folder_id', 'other-root'), ('client_id', 'other-client'),
    ('token_uri', 'https://attacker.example/token'), ('scopes', DRIVE_SCOPES + ['openid'])])
def test_token_binding_rejects_changed_configuration(oauth, field, value):
    oauth.save(credentials(), verified=True)
    data = json.loads(oauth.token_path.read_text())
    data[field] = value
    oauth.token_path.write_text(json.dumps(data))
    with patch.object(Credentials, 'refresh') as refresh, pytest.raises(DriveAuthError):
        oauth.load()
    refresh.assert_not_called()


@pytest.mark.parametrize('target,mode', [('directory', 0o755), ('client', 0o644), ('token', 0o644)])
def test_private_permissions_required(oauth, target, mode):
    oauth.save(credentials())
    path = {'directory': oauth.client_path.parent, 'client': oauth.client_path, 'token': oauth.token_path}[target]
    path.chmod(mode)
    with pytest.raises(DriveAuthError):
        OAuthStore.configured()


def test_symlink_and_git_paths_rejected(oauth, monkeypatch):
    link = oauth.client_path.parent / 'link.json'
    link.symlink_to(oauth.client_path)
    monkeypatch.setenv('DRIVE_OAUTH_CLIENT_FILE', str(link))
    with pytest.raises(DriveAuthError):
        OAuthStore.configured()
    monkeypatch.setenv('DRIVE_OAUTH_CLIENT_FILE', str(drive_auth.REPOSITORY / 'oauth-client.json'))
    with pytest.raises(DriveAuthError, match='outside'):
        OAuthStore.configured()
    monkeypatch.setenv('DRIVE_OAUTH_CLIENT_FILE', str(oauth.client_path))
    (oauth.client_path.parent / '.git').mkdir()
    with pytest.raises(DriveAuthError, match='outside'):
        OAuthStore.configured()


def test_web_oauth_client_rejected(oauth):
    config = json.loads(oauth.client_path.read_text())
    config['web'] = config.pop('installed')
    oauth.client_path.write_text(json.dumps(config))
    with pytest.raises(DriveAuthError, match='Desktop'):
        oauth.client_config()


def test_production_rejects_desktop_oauth_at_startup(oauth, tmp_path, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    with pytest.raises(DriveAuthError, match='development'):
        create_app(f'sqlite:///{tmp_path}/unused.db')
    with pytest.raises(DriveAuthError):
        OAuthStore.configured()


def test_account_rechecked_when_backend_builds_service(oauth):
    oauth.save(credentials(), verified=True)
    with patch.object(Credentials, 'refresh'), patch('backend.drive_auth.build_service', return_value=google_service('wrong@example.test')):
        with pytest.raises(DriveAuthError, match='account'):
            DriveClient()


def test_folder_pin_and_api_authorization(oauth, tmp_path):
    app = create_app(f'sqlite:///{tmp_path}/accounts.db')
    initialize(app.state.engine)
    seed(app.state.factory)
    try:
        for role, identifier, credential, expected in [
            ('employee', 'ALP-01', '24681357', 403),
            ('admin', 'morgan', 'Ace-Admin-Test-2026', 422)]:
            client = TestClient(app)
            response = client.post(f'/api/auth/{role}/login', json={'identifier': identifier, 'credential': credential})
            client.headers['X-CSRF-Token'] = response.json()['csrf_token']
            assert client.patch('/api/admin/settings', json={'folder_id': 'unapproved-root'}).status_code == expected
        assert client.patch('/api/admin/settings', json={'folder_id': oauth.folder}).status_code == 200
        # Accepted jobs fail safely before any Drive request when login/verification is absent.
        with patch('backend.drive_auth.build_service') as build:
            assert client.post('/api/admin/sync').status_code == 202
            build.assert_not_called()
        status = client.get('/api/admin/knowledge').json()
        assert status['sync_status'] == 'failed' and not status['connection_verified']
        assert 'backend.drive_oauth login' in status['error']
        client.headers.pop('X-CSRF-Token')
        assert client.post('/api/admin/sync').status_code == 403
    finally:
        app.state.engine.dispose()


def test_arbitrary_read_and_moved_file_blocked(oauth):
    service = google_service()
    client = DriveClient(service)
    file = SourceFile('outsider', 'Unapproved.pdf', PDF, '')
    with pytest.raises(ValueError, match='inventory'):
        client.read(file)
    with pytest.raises(DriveAuthError):
        client.inventory('wrong-root')
    inventory = client.inventory(oauth.folder)
    service.files.return_value.get.return_value.execute.return_value = {'id': 'permitted', 'mimeType': PDF, 'parents': ['outside-root']}
    with pytest.raises(ValueError, match='moved'):
        client.read(inventory[0])
    service.files.return_value.get_media.assert_not_called()


def test_moved_category_ancestor_blocks_download(oauth):
    service = google_service()
    files = service.files.return_value
    files.list.return_value.execute.side_effect = [
        {'files': [{'id': 'hr', 'name': 'HR & Employee Policies', 'mimeType': FOLDER}]},
        {'files': [{'id': 'permitted', 'name': 'Fictional Policy.pdf', 'mimeType': PDF}]}]
    client = DriveClient(service)
    inventory = client.inventory(oauth.folder)
    files.get.side_effect = lambda **kwargs: Mock(execute=Mock(return_value=(
        {'mimeType': PDF, 'parents': ['hr']} if kwargs['fileId'] == 'permitted'
        else {'mimeType': FOLDER, 'parents': ['outside-root']})))
    with pytest.raises(ValueError, match='moved'):
        client.read(inventory[0])
    files.get_media.assert_not_called()


def test_failed_inventory_discards_previous_allowlist(oauth):
    service = google_service()
    client = DriveClient(service)
    inventory = client.inventory(oauth.folder)
    service.files.return_value.list.return_value.execute.return_value = {'incompleteSearch': True}
    with pytest.raises(RuntimeError, match='Incomplete'):
        client.inventory(oauth.folder)
    with pytest.raises(ValueError, match='inventory'):
        client.read(inventory[0])


def test_cli_failure_never_logs_raw_refresh_errors(oauth, caplog, capsys):
    oauth.save(credentials(), verified=True)
    with patch.object(Credentials, 'refresh', side_effect=RuntimeError('fictional-refresh-token')):
        assert drive_oauth.main(['verify']) == 1
    assert 'fictional-refresh-token' not in caplog.text + capsys.readouterr().out


def test_default_adc_path_is_preserved(monkeypatch):
    from google.auth.compute_engine import Credentials as AttachedCredentials
    monkeypatch.delenv('DRIVE_AUTH_MODE', raising=False)
    attached = AttachedCredentials(scopes=DRIVE_SCOPES)
    with patch('google.auth.default', return_value=(attached, 'fictional-project')), \
            patch('backend.drive_auth.build_service') as build:
        drive_auth.drive_service()
    build.assert_called_once_with(attached)


def test_sync_requires_receipt_even_when_refresh_credentials_exist(oauth, tmp_path):
    from backend.sync_service import SyncService
    oauth.save(credentials(), verified=False)
    app = create_app(f'sqlite:///{tmp_path}/unverified.db')
    initialize(app.state.engine)
    try:
        sync = SyncService(app.state.factory)
        sync.configure(oauth.folder)
        with patch('backend.drive_auth.build_service') as build, patch.object(Credentials, 'refresh') as refresh:
            assert not sync.run()
        build.assert_not_called()
        refresh.assert_not_called()
        state = sync.status()
        assert state['sync_status'] == 'failed' and state['last_success'] is None
        assert 'verify before importing' in state['error']
    finally:
        app.state.engine.dispose()


def test_existing_saved_folder_must_still_match_runtime_pin(oauth, tmp_path):
    from backend.knowledge_models import KnowledgeState
    app = create_app(f'sqlite:///{tmp_path}/mismatch.db')
    initialize(app.state.engine)
    try:
        with app.state.factory.begin() as db:
            db.add(KnowledgeState(id=1, folder_id='old-unapproved-root'))
        with patch('backend.drive_auth.drive_service') as build:
            assert not app.state.sync.run()
        build.assert_not_called()
        state = app.state.sync.status()
        assert 'source configuration' in state['error'] and 'approved' in state['error']
    finally:
        app.state.engine.dispose()


def test_unknown_knowledge_source_is_rejected(monkeypatch):
    from backend.sync_service import SyncService
    monkeypatch.setenv('KNOWLEDGE_SOURCE', 'typo')
    with pytest.raises(DriveAuthError, match='KNOWLEDGE_SOURCE'):
        SyncService.default_source()

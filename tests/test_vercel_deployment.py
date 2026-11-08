"""Vercel adapter regression checks. No cloud resources or credentials used."""
import ast
import json
import tomllib
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from test_render_deployment import hosted  # shared isolated database fixture
from backend.database import database
from backend.drive_auth import auth_mode, DriveAuthError
from backend.runtime import validate_environment, development_only
from backend.main import create_app
from backend.sync_service import SyncService
from backend.hosting_models import SyncRequest


def test_fresh_vercel_import_and_safe_missing_settings():
    # A fresh interpreter exercises imports rather than reusing backend.main.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('APP_', 'DRIVE_', 'VERCEL', 'CLOUD_', 'DB_'))
           and key not in {'DATABASE_URL', 'KNOWLEDGE_SOURCE', 'SYNC_EXECUTOR',
                           'RENDER', 'K_SERVICE', 'GOOGLE_APPLICATION_CREDENTIALS',
                           'SYNTHETIC_DOCUMENT_DIR'}}
    env.update(VERCEL='1', VERCEL_ENV='production')
    root = Path(__file__).resolve().parents[1]
    failed = subprocess.run([sys.executable, '-c', 'import backend.main'], cwd=root,
                            env=env, capture_output=True, text=True)
    assert failed.returncode != 0
    assert 'Missing required settings: APP_ENV, APP_ORIGIN, DATABASE_URL' in failed.stderr
    env.update(APP_ENV='production', APP_ORIGIN='https://example.test',
               DATABASE_URL='postgresql://fictional:private-password@db.render.com/ace',
               KNOWLEDGE_SOURCE='drive', DRIVE_AUTH_MODE='oauth_web',
               SYNC_EXECUTOR='database', DRIVE_AUTHORIZED_EMAIL='team@example.test',
               DRIVE_KNOWLEDGE_FOLDER_ID='approved-root',
               DRIVE_WEB_CLIENT_ID='fictional.apps.googleusercontent.com',
               DRIVE_WEB_CLIENT_SECRET='private-client-secret',
               DRIVE_TOKEN_ENCRYPTION_KEY='invalid-private-key')
    failed = subprocess.run([sys.executable, '-c', 'import backend.main'], cwd=root,
                            env=env, capture_output=True, text=True)
    assert failed.returncode != 0
    assert 'Startup failed (DriveAuthError)' in failed.stderr
    for value in ('private-password', 'private-client-secret', 'invalid-private-key'):
        assert value not in failed.stderr
    from cryptography.fernet import Fernet
    env['DRIVE_TOKEN_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
    env['BOOTSTRAP_ADMINS'] = 'must-never-be-consumed-by-web'
    imported = subprocess.run(
        [sys.executable, '-c', 'from backend.main import app; from fastapi import FastAPI; import os; assert isinstance(app, FastAPI); assert "BOOTSTRAP_ADMINS" not in os.environ; from main import app as compatibility; assert compatibility is app'],
        cwd=root, env=env, capture_output=True, text=True)
    assert imported.returncode == 0, imported.stderr


def test_vercel_rejects_development_utilities_and_preview(hosted, monkeypatch):
    monkeypatch.setenv('VERCEL', '1')
    with pytest.raises(RuntimeError, match='production'):
        validate_environment()
    with pytest.raises(RuntimeError, match='local development'):
        development_only()
    monkeypatch.setenv('DRIVE_AUTH_MODE', 'oauth_local')
    with pytest.raises(DriveAuthError, match='local development'):
        auth_mode()
    monkeypatch.setenv('DRIVE_AUTH_MODE', 'oauth_web')
    monkeypatch.setenv('APP_ENV', 'production')
    validate_environment(web=True)
    monkeypatch.setenv('SYNC_EXECUTOR', 'cloud_run')
    with pytest.raises(RuntimeError, match='Vercel requires'):
        validate_environment(web=True)
    monkeypatch.setenv('SYNC_EXECUTOR', 'database')
    monkeypatch.setenv('VERCEL_ENV', 'preview')
    with pytest.raises(RuntimeError, match='preview'):
        validate_environment()


@pytest.mark.parametrize('url', [
    'sqlite:///:memory:',
    'postgresql://user:private@dpg-internal/ace',
    'postgresql://user:private@db.render.com/ace?sslmode=disable',
    'postgresql://user:private@db.render.com/ace?sslmode=require',
    'postgresql://user:private@db.render.com/ace?host=dpg-internal',
    'postgresql://user:private@db.render.com/ace?hostaddr=127.0.0.1',
])
def test_vercel_database_fails_before_connecting(hosted, monkeypatch, url):
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('APP_ENV', 'production')
    with patch('backend.database.create_engine') as create:
        with pytest.raises(RuntimeError):
            database(url)
        create.assert_not_called()


def test_external_database_verifies_certificates_and_bounds_pool(hosted, monkeypatch):
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('APP_ENV', 'production')
    with patch('backend.database.create_engine') as create:
        database('postgres://user:private@db.render.com/ace')
        url = create.call_args.args[0]
        assert url.drivername == 'postgresql+psycopg'
        assert url.query['sslmode'] == 'verify-full'
        assert url.query['sslrootcert'] == 'system'
        assert create.call_args.kwargs['pool_size'] == 1
        assert create.call_args.kwargs['max_overflow'] == 1
        assert create.call_args.kwargs['hide_parameters'] is True


def test_vercel_entrypoint_routes_roles_csrf_and_durable_sync(hosted, monkeypatch):
    SyncService(hosted.state.factory).configure('approved-root')
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('VERCEL_ENV', 'production')
    with patch('backend.main.database', return_value=(hosted.state.engine, hosted.state.factory)):
        production = create_app()
    with TestClient(production, base_url='https://testserver') as client:
        for path in ('/login.html', '/admin-login.html', '/login.js', '/style.css', '/assets/ace-logo.webp'):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers['cache-control'] == 'no-store'
        for path, target in (('/index.html', '/login.html'), ('/admin.html', '/admin-login.html')):
            assert client.get(path, follow_redirects=False).headers['location'] == target
        assert client.get('/api/admin/documents').status_code == 401
        assert client.get('/docs').status_code == 404
        assert client.get('/backend/ace.db').status_code == 404
        assert client.get('/login.html', headers={'host': 'evil.test'}).status_code == 400
        response = client.post('/api/auth/employee/login', json={
            'identifier': 'ALP-01', 'credential': '24681357'})
        assert response.status_code == 200
        client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        assert client.get('/index.html').status_code == 200
        assert client.get('/api/admin/documents').status_code == 403
        assert client.post('/api/admin/sync').status_code == 403
        assert client.post('/api/admin/drive/connect').status_code == 403
        response = client.post('/api/auth/admin/login', json={
            'identifier': 'morgan', 'credential': 'Ace-Admin-Test-2026'})
        assert response.status_code == 200
        assert 'Secure' in response.headers['set-cookie']
        client.headers.pop('X-CSRF-Token')
        assert client.post('/api/admin/sync').status_code == 403
        client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        assert client.get('/admin.html').status_code == 200
        with patch.object(production.state.sync, 'run') as run:
            assert client.post('/api/admin/sync').status_code == 202
            run.assert_not_called()
        with hosted.state.factory() as db:
            assert db.scalar(select(SyncRequest.requested)) == 1
        assert client.post('/api/admin/sync', headers={'origin': 'https://evil.test'}).status_code == 403
        assert client.post('/api/admin/drive/connect').status_code == 200


def test_vercel_configuration_selects_backend_without_routing_overrides():
    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / 'pyproject.toml').read_text())
    assert config['tool']['vercel']['entrypoint'] == 'backend.main:app'
    deployment = json.loads((root / 'vercel.json').read_text())
    assert deployment['framework'] == 'fastapi'
    assert not {'builds', 'routes', 'rewrites', 'redirects', 'outputDirectory'} & deployment.keys()
    assert set(deployment['functions']) == {'backend/main.py'}
    assert deployment['functions']['backend/main.py']['includeFiles'] == 'frontend/**'
    module = ast.parse((root / 'backend/main.py').read_text())
    # Vercel must see the app assignment directly at module scope.
    assignments = [node for node in module.body if isinstance(node, ast.Assign)]
    assert any(any(isinstance(target, ast.Name) and target.id == 'app'
                   for target in node.targets)
               and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
               and node.value.func.id == '_startup_app' for node in assignments)

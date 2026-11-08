"""Admin-initiated Web OAuth, state/PKCE, and encrypted offline Drive grants.

No Desktop client, service-account key, token file, or browser token storage.
Only the OAuth nonce cookie is Lax; application sessions remain Strict.
"""
import hashlib
import json
import os
import secrets
import time
from functools import partial
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from google_auth_oauthlib.flow import Flow
from sqlalchemy import delete, update
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse

from .auth import digest, lock_admin_changes
from .drive_auth import (DRIVE_SCOPES, DriveAuthError, approved_identity,
                         build_service, check_account, quiet_google_logging)
from .hosting_models import DriveGrant, DriveConsent
from .models import AuthSession, Administrator

COOKIE = '__Host-ace_drive_consent'
CALLBACK = '/api/drive/oauth/callback'


def configuration():
    email, folder = approved_identity()
    origin = os.getenv('APP_ORIGIN', '')
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment or parsed.port not in (None, 443)):
        raise DriveAuthError('Web OAuth requires an exact HTTPS APP_ORIGIN without a path.')
    client = os.getenv('DRIVE_WEB_CLIENT_ID', '')
    secret = os.getenv('DRIVE_WEB_CLIENT_SECRET', '')
    if not client.endswith('.apps.googleusercontent.com') or not secret:
        raise DriveAuthError('Configure a dedicated Google Web application OAuth client.')
    try:
        cipher = Fernet(os.environ['DRIVE_TOKEN_ENCRYPTION_KEY'].encode('ascii'))
    except Exception:
        raise DriveAuthError('Configure a valid, privately generated DRIVE_TOKEN_ENCRYPTION_KEY.') from None
    config = {'web': {'client_id': client, 'client_secret': secret,
                     'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                     'token_uri': 'https://oauth2.googleapis.com/token',
                     'redirect_uris': [origin + CALLBACK]}}
    binding = hashlib.sha256(json.dumps([client, secret, origin, email, folder, DRIVE_SCOPES]).encode()).hexdigest()
    return config, cipher, binding


def new_flow(*, state, verifier):
    config, _, _ = configuration()
    return Flow.from_client_config(config, scopes=DRIVE_SCOPES, state=state,
                                   code_verifier=verifier,
                                   redirect_uri=config['web']['redirect_uris'][0])


def active_administrator(db, session_hash):
    session = db.get(AuthSession, session_hash)
    account = db.get(Administrator, session.account_id) if session and session.role == 'admin' else None
    if (not session or session.expires <= time.time() or not account or not account.active
            or account.version != session.version):
        raise DriveAuthError('Administrator session expired. Sign in and reconnect Google Drive.')


def load_service():
    """Refresh on the backend and verify the approved account every sync."""
    from .database import database
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    config, cipher, binding = configuration()
    engine, factory = database()
    try:
        with factory() as db:
            grant = db.get(DriveGrant, 1)
            if not grant or grant.binding != binding:
                raise DriveAuthError('An administrator must connect the approved Google Drive account in Knowledge Management.')
            encrypted = grant.encrypted_refresh
        try:
            refresh = cipher.decrypt(encrypted.encode()).decode()
        except Exception:
            raise DriveAuthError('Drive authorization could not be decrypted. Restore the encryption key or reconnect.') from None
        client = config['web']
        credentials = Credentials(None, refresh_token=refresh, token_uri=client['token_uri'],
                                  client_id=client['client_id'], client_secret=client['client_secret'],
                                  scopes=DRIVE_SCOPES)
        credentials.refresh(partial(GoogleRequest(), timeout=30))
        service = build_service(credentials)
        check_account(service, approved_identity()[0])
        if credentials.refresh_token != refresh:
            with factory.begin() as db:
                db.execute(update(DriveGrant).where(DriveGrant.id == 1, DriveGrant.binding == binding,
                    DriveGrant.encrypted_refresh == encrypted).values(
                    encrypted_refresh=cipher.encrypt(credentials.refresh_token.encode()).decode()))
        return service
    finally:
        engine.dispose()


def install_routes(app, admin):
    @app.post('/api/admin/drive/connect')
    def connect(identity=Depends(admin)):
        if os.getenv('DRIVE_AUTH_MODE') != 'oauth_web':
            raise HTTPException(404)
        quiet_google_logging()
        _, cipher, binding = configuration()
        state, browser, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)
        flow = new_flow(state=state, verifier=verifier)
        url, _ = flow.authorization_url(access_type='offline', prompt='consent',
                                        login_hint=approved_identity()[0], include_granted_scopes='false')
        with app.state.factory.begin() as db:
            db.execute(delete(DriveConsent).where(DriveConsent.expires <= time.time()))
            db.execute(delete(DriveConsent).where(DriveConsent.session_hash == identity[0].token_hash))
            db.add(DriveConsent(state_hash=digest(state), browser_hash=digest(browser),
                session_hash=identity[0].token_hash, binding=binding, expires=time.time() + 600,
                encrypted_verifier=cipher.encrypt(verifier.encode()).decode()))
        response = JSONResponse({'authorization_url': url})
        response.set_cookie(COOKIE, browser, max_age=600, secure=True, httponly=True, samesite='lax', path='/')
        return response

    @app.get(CALLBACK, include_in_schema=False)
    def callback(request: Request):
        # The Strict application cookie is intentionally absent on Google's redirect.
        # A one-use state and Lax browser nonce bind this to the initiating admin session.
        if os.getenv('DRIVE_AUTH_MODE') != 'oauth_web':
            raise HTTPException(404)
        quiet_google_logging()
        succeeded = False
        try:
            _, cipher, binding = configuration()
            state = request.query_params.get('state', '')
            browser = request.cookies.get(COOKIE, '')
            if not 20 <= len(state) <= 200 or not 20 <= len(browser) <= 200:
                raise DriveAuthError('Invalid consent state.')
            with app.state.factory.begin() as db:
                consent = db.get(DriveConsent, digest(state))
                if (not consent or consent.expires <= time.time() or consent.binding != binding
                        or not secrets.compare_digest(consent.browser_hash, digest(browser))):
                    raise DriveAuthError('Invalid consent state.')
                active_administrator(db, consent.session_hash)
                claimed = db.execute(delete(DriveConsent).where(DriveConsent.state_hash == digest(state)))
                if claimed.rowcount != 1:
                    raise DriveAuthError('Consent was already consumed.')
                verifier = cipher.decrypt(consent.encrypted_verifier.encode()).decode()
                session_hash = consent.session_hash
            code = request.query_params.get('code', '')
            if request.query_params.get('error') or not code or len(code) > 4096:
                raise DriveAuthError('Consent was not granted.')
            flow = new_flow(state=state, verifier=verifier)
            flow.fetch_token(code=code, timeout=30)
            credentials = flow.credentials
            if not credentials.refresh_token or (credentials.granted_scopes is not None
                    and set(credentials.granted_scopes) != set(DRIVE_SCOPES)):
                raise DriveAuthError('Read-only offline authorization is required.')
            service = build_service(credentials)
            check_account(service, approved_identity()[0])
            # Metadata only; do not download or publish documents during consent.
            from .drive_client import DriveClient
            DriveClient(service).inventory(approved_identity()[1])
            with app.state.factory.begin() as db:
                lock_admin_changes(db)
                active_administrator(db, session_hash)
                grant = db.get(DriveGrant, 1)
                encrypted = cipher.encrypt(credentials.refresh_token.encode()).decode()
                if grant:
                    grant.binding, grant.encrypted_refresh = binding, encrypted
                else:
                    db.add(DriveGrant(id=1, binding=binding, encrypted_refresh=encrypted))
            succeeded = True
        except Exception:
            # Never log query strings, raw provider responses, code, or credentials.
            pass
        # A same-origin landing page and explicit navigation restore the Strict app
        # cookie after Google's cross-site redirect, without relaxing that cookie.
        outcome = 'connected' if succeeded else 'failed'
        title = 'Google Drive connected' if succeeded else 'Google Drive authorization failed'
        message = ('Authorization and folder access verified. Return to Knowledge Management and use Re-sync now.'
                   if succeeded else 'Return to Knowledge Management, sign in again if needed, and reconnect using the approved Google account. Ask the technical owner to check configuration if this persists.')
        response = HTMLResponse('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Google Drive · Ace</title><link rel="stylesheet" href="/style.css">'
            '<link rel="stylesheet" href="/login.css"></head><body><main class="login-workspace">'
            '<section class="login-card"><img class="ace-logo login-logo" src="/assets/ace-logo.webp" '
            'alt="Ace Family Dental" width="281" height="140"><h1>' + title + '</h1><p>' + message + '</p>'
            '<a href="/admin.html?drive=' + outcome + '#knowledge">Return to Knowledge Management</a>'
            '</section></main></body></html>')
        response.delete_cookie(COOKIE, path='/', secure=True, httponly=True, samesite='lax')
        return response

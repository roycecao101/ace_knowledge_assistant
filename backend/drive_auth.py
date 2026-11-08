"""Backend-only credentials. Interactive consent is available only in the operator CLI."""
import json
import logging
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from .runtime import production, validate_environment

DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
REPOSITORY = Path(__file__).resolve().parents[1]


class DriveAuthError(RuntimeError):
    """Only fixed, operator-safe messages may be used with this exception."""


def quiet_google_logging():
    # OAuth/HTTP debug output can include authorization headers and token bodies.
    for name in ('google', 'googleapiclient', 'google_auth_httplib2', 'google_auth_oauthlib',
                 'oauthlib', 'requests_oauthlib', 'requests', 'urllib3', 'httplib2'):
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL + 1)
        logger.handlers = [logging.NullHandler()]
        logger.propagate = False
    import httplib2
    httplib2.debuglevel = 0


def auth_mode():
    mode = os.getenv('DRIVE_AUTH_MODE', 'adc')
    if mode not in ('adc', 'oauth_local', 'oauth_web'):
        raise DriveAuthError('Set DRIVE_AUTH_MODE to adc, oauth_local, or oauth_web.')
    if mode == 'oauth_local' and (os.getenv('APP_ENV', 'development') != 'development'
            or os.getenv('RENDER') or os.getenv('K_SERVICE') or os.getenv('CLOUD_RUN_JOB')):
        raise DriveAuthError('Local desktop OAuth is allowed only in local development with APP_ENV=development.')
    return mode


def approved_identity():
    email = os.getenv('DRIVE_AUTHORIZED_EMAIL', '').strip().casefold()
    folder = os.getenv('DRIVE_KNOWLEDGE_FOLDER_ID', '')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise DriveAuthError('Set DRIVE_AUTHORIZED_EMAIL to the approved team Google account.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', folder):
        raise DriveAuthError('Set DRIVE_KNOWLEDGE_FOLDER_ID to the approved knowledge folder ID.')
    return email, folder


def validate_folder(folder):
    if production():
        approved = os.getenv('DRIVE_KNOWLEDGE_FOLDER_ID', '')
        if not approved or folder != approved:
            raise DriveAuthError('The folder must match the production-approved DRIVE_KNOWLEDGE_FOLDER_ID.')
    if auth_mode() in ('oauth_local', 'oauth_web') and folder != approved_identity()[1]:
        raise DriveAuthError('The folder must match DRIVE_KNOWLEDGE_FOLDER_ID approved by the technical owner.')


def _private_path(path, *, exists=True):
    path = Path(path).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise DriveAuthError('Credential paths must be absolute and must not be symbolic links.')
    resolved = path.resolve()
    if resolved == REPOSITORY or REPOSITORY in resolved.parents or any(
            (parent / '.git').exists() for parent in resolved.parents):
        raise DriveAuthError('Store OAuth files outside all Git repositories.')
    parent = path.parent
    if not parent.is_dir() or parent.resolve() != parent:
        raise DriveAuthError('Create a private credential directory without symbolic links first.')
    info = parent.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise DriveAuthError('The OAuth directory must be owned by this user with permissions 0700.')
    if exists or path.exists():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise DriveAuthError('OAuth files must be regular files owned by this user with permissions 0600.')
    return path


def _read_json(path):
    # O_NOFOLLOW also protects against replacing the file with a symlink after validation.
    fd = os.open(_private_path(path), os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        return json.load(stream)


@dataclass(frozen=True)
class OAuthStore:
    client_path: Path
    token_path: Path
    email: str
    folder: str

    @classmethod
    def configured(cls):
        if auth_mode() != 'oauth_local':
            raise DriveAuthError('Set DRIVE_AUTH_MODE=oauth_local for local user OAuth.')
        email, folder = approved_identity()
        base = Path.home() / '.config' / 'ace-knowledge-assistant'
        client = _private_path(os.getenv('DRIVE_OAUTH_CLIENT_FILE', str(base / 'oauth-client.json')))
        token = _private_path(os.getenv('DRIVE_OAUTH_TOKEN_FILE', str(base / 'oauth-token.json')), exists=False)
        if client == token:
            raise DriveAuthError('Use separate OAuth client and token files.')
        return cls(client, token, email, folder)

    def client_config(self):
        config = _read_json(self.client_path)
        client = config.get('installed', {})
        if (not client.get('client_id') or not client.get('client_secret')
                or client.get('auth_uri') != 'https://accounts.google.com/o/oauth2/auth'
                or client.get('token_uri') != 'https://oauth2.googleapis.com/token'):
            raise DriveAuthError('Use an unmodified Google Desktop app OAuth client download.')
        return {'installed': client}

    def save(self, credentials, *, verified=False):
        path = _private_path(self.token_path, exists=False)
        # Persist refresh credentials only; access tokens remain in process memory.
        data = json.loads(credentials.to_json(strip=['token', 'id_token']))
        data['approved_email'] = self.email
        data['approved_folder_id'] = self.folder
        data['metadata_verified'] = verified
        fd, temporary = tempfile.mkstemp(prefix='.oauth-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump(data, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def load(self, *, require_verified=True):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        config = self.client_config()['installed']
        if not self.token_path.exists():
            raise DriveAuthError('Run python -m backend.drive_oauth login, then verify, on this local machine.')
        data = _read_json(self.token_path)
        if (data.get('approved_email') != self.email or data.get('approved_folder_id') != self.folder
                or data.get('client_id') != config['client_id']
                or data.get('client_secret') != config['client_secret']
                or data.get('token_uri') != config['token_uri']
                or set(data.get('scopes', [])) != set(DRIVE_SCOPES) or not data.get('refresh_token')):
            raise DriveAuthError('OAuth configuration changed. Repeat local login and metadata verification.')
        verified = data.get('metadata_verified') is True
        if require_verified and not verified:
            raise DriveAuthError('Run python -m backend.drive_oauth verify before importing documents.')
        credentials = Credentials.from_authorized_user_info(data, scopes=DRIVE_SCOPES)
        credentials.refresh(partial(Request(), timeout=30))
        self.save(credentials, verified=verified)
        return credentials


def build_service(credentials):
    from googleapiclient.discovery import build
    import google_auth_httplib2
    import httplib2
    return build('drive', 'v3', http=google_auth_httplib2.AuthorizedHttp(
        credentials, http=httplib2.Http(timeout=30)), cache_discovery=False)


def check_account(service, email):
    actual = service.about().get(fields='user(emailAddress)').execute().get('user', {}).get('emailAddress', '')
    if actual.casefold() != email:
        raise DriveAuthError('The signed-in Google account does not match DRIVE_AUTHORIZED_EMAIL. Reconnect with the approved account.')


def drive_service(*, require_verified=True):
    validate_environment()
    quiet_google_logging()
    if auth_mode() == 'oauth_web':
        from .drive_web_oauth import load_service
        return load_service()
    if auth_mode() == 'oauth_local':
        store = OAuthStore.configured()
        service = build_service(store.load(require_verified=require_verified))
        check_account(service, store.email)
        return service
    import google.auth
    from google.oauth2.service_account import Credentials as ServiceCredentials
    from google.auth.compute_engine import Credentials as AttachedCredentials
    credentials, _ = google.auth.default(scopes=DRIVE_SCOPES)
    if production() and not isinstance(credentials, AttachedCredentials):
        raise DriveAuthError('Production Drive access requires an attached service account through ADC.')
    if not isinstance(credentials, (ServiceCredentials, AttachedCredentials)) or getattr(credentials, '_subject', None):
        raise DriveAuthError('ADC requires a dedicated service identity without user delegation. Use oauth_local for development.')
    return build_service(credentials)

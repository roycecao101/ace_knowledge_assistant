"""Fail closed for hosted processes; development keeps its existing defaults."""
import os
import re
from urllib.parse import urlsplit


def production():
    return os.getenv('APP_ENV', 'development') == 'production'


def validate_environment(*, web=False):
    if (os.getenv('VERCEL') or os.getenv('RENDER') or os.getenv('K_SERVICE') or os.getenv('CLOUD_RUN_JOB')) and not production():
        raise RuntimeError('Hosted services require APP_ENV=production.')
    if not production():
        return
    if os.getenv('VERCEL_ENV') == 'preview':
        raise RuntimeError('Production data must not be used in Vercel preview deployments.')
    from .drive_auth import auth_mode
    mode = auth_mode()
    if mode not in ('adc', 'oauth_web') or os.getenv('KNOWLEDGE_SOURCE') != 'drive':
        raise RuntimeError('Production requires hosted Drive authorization and KNOWLEDGE_SOURCE=drive.')
    if os.getenv('RENDER') and (mode != 'oauth_web' or os.getenv('SYNC_EXECUTOR') != 'database'):
        raise RuntimeError('Render requires DRIVE_AUTH_MODE=oauth_web and SYNC_EXECUTOR=database.')
    if os.getenv('VERCEL') and (mode != 'oauth_web' or os.getenv('SYNC_EXECUTOR') != 'database'):
        raise RuntimeError('Vercel requires DRIVE_AUTH_MODE=oauth_web and SYNC_EXECUTOR=database.')
    if any(os.getenv(key) for key in (
        'GOOGLE_APPLICATION_CREDENTIALS', 'DRIVE_OAUTH_CLIENT_FILE',
        'DRIVE_OAUTH_TOKEN_FILE', 'SYNTHETIC_DOCUMENT_DIR',
    )):
        raise RuntimeError('Production must not use local credential or document paths.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', os.getenv('DRIVE_KNOWLEDGE_FOLDER_ID', '')):
        raise RuntimeError('Production requires the approved DRIVE_KNOWLEDGE_FOLDER_ID.')
    if mode == 'oauth_web':
        from .drive_web_oauth import configuration
        configuration()
    if web:
        origin = os.getenv('APP_ORIGIN', '')
        parsed = urlsplit(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment or parsed.port not in (None, 443)):
            raise RuntimeError('Production requires an HTTPS APP_ORIGIN without a path or credentials.')
        executor = os.getenv('SYNC_EXECUTOR', 'cloud_run')
        if executor not in ('database', 'cloud_run'):
            raise RuntimeError('Unknown production synchronization executor.')
        if executor == 'cloud_run' and not re.fullmatch(
                r'projects/[a-z][a-z0-9-]+/locations/[a-z0-9-]+/jobs/[a-z][a-z0-9-]+',
                os.getenv('SYNC_JOB_RESOURCE', '')):
            raise RuntimeError('Cloud Run synchronization requires SYNC_JOB_RESOURCE.')


def development_only():
    if (os.getenv('APP_ENV', 'development') != 'development' or os.getenv('RENDER')
            or os.getenv('VERCEL') or os.getenv('K_SERVICE') or os.getenv('CLOUD_RUN_JOB')):
        raise RuntimeError('This utility is restricted to local development.')

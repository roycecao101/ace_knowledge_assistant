"""Vercel ASGI entrypoint; all routing and authorization stay in the existing app."""
import os

# Bootstrap is an operator release task, never an HTTP startup task.
os.environ.pop('BOOTSTRAP_ADMINS', None)
try:
    from backend.main import app
except Exception as exc:
    # Only fixed setting names and the exception class are safe to expose.
    # Exception text can contain database URLs, credentials, or source data.
    required = (
        'APP_ENV', 'APP_ORIGIN', 'DATABASE_URL', 'KNOWLEDGE_SOURCE',
        'DRIVE_AUTH_MODE', 'SYNC_EXECUTOR', 'DRIVE_AUTHORIZED_EMAIL',
        'DRIVE_KNOWLEDGE_FOLDER_ID', 'DRIVE_WEB_CLIENT_ID',
        'DRIVE_WEB_CLIENT_SECRET', 'DRIVE_TOKEN_ENCRYPTION_KEY',
    )
    missing = [key for key in required if not os.getenv(key)]
    detail = (' Missing required settings: ' + ', '.join(missing) + '.') if os.getenv('VERCEL') and missing else ''
    raise RuntimeError(
        f'Startup failed ({type(exc).__name__}).{detail} '
        'Check production configuration and release prerequisites; private details suppressed.'
    ) from None

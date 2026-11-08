"""Vercel ASGI entrypoint; all routing and authorization stay in the existing app."""
import os

# Bootstrap is an operator release task, never an HTTP startup task.
os.environ.pop('BOOTSTRAP_ADMINS', None)
try:
    from backend.main import app
except Exception:
    raise RuntimeError('Startup failed. Check production configuration and release prerequisites; private details suppressed.') from None

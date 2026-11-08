"""Hosted entrypoint. No reload, access logs, schema changes, or seeding."""
import os
import uvicorn


if __name__ == '__main__':
    # Bootstrap is consumed only by the explicit release process.
    os.environ.pop('BOOTSTRAP_ADMINS', None)
    try:
        from .main import app
        port = int(os.getenv('PORT', '8080'))
        if not 1 <= port <= 65535:
            raise ValueError('Invalid port')
    except Exception:
        raise SystemExit('Startup configuration failed. Check production environment and database; private details suppressed.') from None
    uvicorn.run(app, host='0.0.0.0', port=port, workers=1, access_log=False,
                proxy_headers=False, log_level='warning')

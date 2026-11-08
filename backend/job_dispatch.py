"""Durable database sync queue for Render; attached-ADC dispatch for Cloud Run."""
import os


def dispatch_sync(factory=None):
    if os.getenv('SYNC_EXECUTOR') == 'database':
        from sqlalchemy import update
        from .hosting_models import SyncRequest
        with factory.begin() as db:
            result = db.execute(update(SyncRequest).where(SyncRequest.id == 1).values(
                requested=SyncRequest.requested + 1))
            if result.rowcount != 1:
                raise RuntimeError('Synchronization queue is not initialized.')
        return
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    resource = os.environ['SYNC_JOB_RESOURCE']
    with AuthorizedSession(credentials) as session:
        response = session.post(f'https://run.googleapis.com/v2/{resource}:run', json={}, timeout=30)
        if not response.ok:
            raise RuntimeError('Synchronization job could not be started.')

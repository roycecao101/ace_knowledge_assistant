"""Operator CLI; Miriam uses the authenticated dashboard instead."""
import argparse
from .database import database
from .sync_service import SyncService, SyncBusy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder-id', help='Set the approved knowledge folder ID before sync')
    parser.add_argument('--if-due', action='store_true', help='Process durable requests or the daily scheduled sync')
    args = parser.parse_args()
    engine = None
    try:
        engine, factory = database()
        from .runtime import production
        from .migrate import ready
        if production() and not ready(engine):
            raise RuntimeError('Run database migration first.')
        service = SyncService(factory)
        if args.folder_id:
            import re
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', args.folder_id):
                parser.error('Invalid folder ID')
            service.configure(args.folder_id)
        # Production jobs can initialize the approved setting without a UI request.
        if production():
            import os
            approved = os.environ['DRIVE_KNOWLEDGE_FOLDER_ID']
            current = service.status()['folder_id']
            if not current:
                service.configure(approved)
        request_number = 0
        if args.if_due:
            import time
            from .hosting_models import SyncRequest
            with factory() as db:
                queued = db.get(SyncRequest, 1)
                if not queued:
                    raise RuntimeError('Synchronization queue is not initialized.')
                request_number = queued.requested
                pending = queued.requested > queued.completed
            status = service.status()
            if not pending and status['last_success'] and time.time() - status['last_success'] < 23 * 3600:
                print('Synchronization is current; no pending requests.')
                return 0
        success = service.run()
        if success and args.if_due:
            from sqlalchemy import update
            with factory.begin() as db:
                db.execute(update(SyncRequest).where(SyncRequest.id == 1,
                    SyncRequest.completed < request_number).values(completed=request_number))
        print('Synchronization succeeded.' if success else service.status()['error'])
        return 0 if success else 1
    except SyncBusy:
        print('Synchronization already in progress; overlapping execution skipped.')
        return 0
    except Exception:
        print('Synchronization could not start. Check production configuration, schema, and database availability.')
        return 1
    finally:
        if engine is not None:
            engine.dispose()

if __name__ == '__main__':
    raise SystemExit(main())

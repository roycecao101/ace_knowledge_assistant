"""Operator CLI; Miriam uses the authenticated dashboard instead."""
import argparse
from .database import database
from .sync_service import SyncService

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder-id', help='Set knowledge folder ID before sync')
    args = parser.parse_args()
    engine, factory = database()
    service = SyncService(factory)
    if args.folder_id:
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', args.folder_id):
            parser.error('Invalid folder ID')
        service.configure(args.folder_id)
    success = service.run()
    print('Synchronization succeeded.' if success else service.status()['error'])
    engine.dispose()
    raise SystemExit(0 if success else 1)

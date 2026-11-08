"""One-time real administrator setup from a runtime-only secret value."""
import json
import os
import re
from sqlalchemy import select, func
from .auth import hasher, lock_admin_changes
from .database import database
from .migrate import ready
from .models import Administrator


def bootstrap(factory, raw):
    entries = json.loads(raw)
    if not isinstance(entries, list) or len(entries) != 2:
        raise ValueError('Supply exactly two administrators.')
    for item in entries:
        if (not isinstance(item, dict) or set(item) != {'id', 'name', 'password'}
                or not all(isinstance(item[k], str) for k in item)
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', item['id'])
                or not 1 <= len(item['name'].strip()) <= 120
                or not 16 <= len(item['password']) <= 256):
            raise ValueError('Invalid administrator setup.')
    if entries[0]['id'] == entries[1]['id'] or entries[0]['password'] == entries[1]['password']:
        raise ValueError('Use distinct administrator identities and passwords.')
    with factory.begin() as db:
        lock_admin_changes(db)
        if db.scalar(select(func.count()).select_from(Administrator)):
            raise ValueError('Bootstrap requires an empty administrator table; use the dashboard for existing accounts.')
        for item in entries:
            db.add(Administrator(id=item['id'], name=item['name'].strip(), credential_hash=hasher.hash(item['password'])))


def main():
    engine = None
    try:
        engine, factory = database()
        if not ready(engine):
            raise ValueError('Run migrations first.')
        bootstrap(factory, os.environ.pop('BOOTSTRAP_ADMINS'))
        print('Two administrators initialized. Remove the bootstrap secret binding before serving traffic.')
        return 0
    except Exception:
        print('Administrator setup failed. Check schema, empty administrator table, and secret format; no credentials logged.')
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())

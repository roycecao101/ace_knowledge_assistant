"""Explicit Render pre-deploy command; optional one-time real admin bootstrap."""
import os
from sqlalchemy import select, func
from .database import database
from .migrate import migrate
from .bootstrap_admins import bootstrap
from .models import Administrator


def main():
    engine = None
    try:
        engine, factory = database()
        migrate(engine)
        from .runtime import production
        if production():
            from .sync_service import SyncService
            SyncService(factory).configure(os.environ['DRIVE_KNOWLEDGE_FOLDER_ID'])
        raw = os.environ.pop('BOOTSTRAP_ADMINS', None)
        with factory() as db:
            count = db.scalar(select(func.count()).select_from(Administrator))
        if raw and count == 0:
            bootstrap(factory, raw)
        with factory() as db:
            if db.scalar(select(func.count()).select_from(Administrator).where(Administrator.active.is_(True))) < 2:
                raise RuntimeError('Provision at least two active real administrators.')
        print('Production schema and administrator prerequisites verified.')
        return 0
    except Exception:
        print('Release failed. Check production configuration, database, and administrator bootstrap; private details suppressed.')
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())

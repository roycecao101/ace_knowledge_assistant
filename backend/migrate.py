"""Versioned, explicit schema upgrade. Never run as a web startup side effect."""
from sqlalchemy import Integer, inspect, text
from sqlalchemy.orm import Mapped, mapped_column, Session
from .database import Base, database
from . import models, knowledge_models  # register the complete schema
from .models import AdminGuard
from .hosting_models import SyncRequest
from .initialize_knowledge import initialize as upgrade_knowledge
from .offices import initialize as initialize_offices

REVISION = 2


class SchemaRevision(Base):
    __tablename__ = 'schema_revision'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)


def ready(engine):
    """Inspect schema metadata and singleton state, never source documents."""
    inspector = inspect(engine)
    if not set(Base.metadata.tables).issubset(inspector.get_table_names()):
        return False
    for table in Base.metadata.sorted_tables:
        if not set(table.columns.keys()).issubset(c['name'] for c in inspector.get_columns(table.name)):
            return False
    with Session(engine) as db:
        version = db.get(SchemaRevision, 1)
        return bool(version and version.revision == REVISION and db.get(AdminGuard, 1) and db.get(SyncRequest, 1))


def migrate(engine):
    # PostgreSQL serializes explicit migration jobs across deployments.
    with engine.connect() as lock:
        postgres = engine.dialect.name == 'postgresql'
        if postgres:
            lock.execute(text('SELECT pg_advisory_lock(714602911)'))
            lock.commit()
        try:
            if 'schema_revision' in inspect(engine).get_table_names():
                with Session(engine) as db:
                    current = db.get(SchemaRevision, 1)
                    if current and current.revision > REVISION:
                        raise RuntimeError('Database schema is newer than this application.')
            # Revision 1 adopts the legacy schema and nullable additive upgrades.
            # Revision 2 adds DriveGrant, DriveConsent and SyncRequest (new tables
            # only), plus the queue singleton. Repeating either upgrade is safe.
            Base.metadata.create_all(engine)
            upgrade_knowledge(engine)
            initialize_offices(engine)
            with Session(engine) as db:
                if not db.get(AdminGuard, 1):
                    db.add(AdminGuard(id=1, revision=0))
                if not db.get(SyncRequest, 1):
                    db.add(SyncRequest(id=1, requested=0, completed=0))
                version = db.get(SchemaRevision, 1)
                if version:
                    version.revision = REVISION
                else:
                    db.add(SchemaRevision(id=1, revision=REVISION))
                db.commit()
            if not ready(engine):
                raise RuntimeError('Schema verification failed.')
        finally:
            if postgres:
                lock.execute(text('SELECT pg_advisory_unlock(714602911)'))
                lock.commit()


def main():
    engine = None
    try:
        engine, _ = database()
        migrate(engine)
        print('Database migration completed and schema verified.')
        return 0
    except Exception:
        print('Database migration failed. Check database connectivity and schema compatibility; no private error details logged.')
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())

"""Explicit, idempotent local fixture setup. Never run on production data."""
import argparse
import os
from .database import Base, database
from .models import Employee, Administrator, AdminGuard
from .auth import hasher

def initialize(engine):
    Base.metadata.create_all(engine)
    from .offices import initialize as initialize_offices
    initialize_offices(engine)
    if engine.dialect.name == 'sqlite' and engine.url.database not in (None, ':memory:'):
        from pathlib import Path
        Path(engine.url.database).chmod(0o600)
    from sqlalchemy.orm import Session
    with Session(engine) as db:
        if not db.get(AdminGuard, 1):
            db.add(AdminGuard(id=1, revision=0))
        db.commit()

def seed(factory):
    with factory() as db:
        for identifier, name, pin, office in [('ALP-01', 'Jordan Test', '24681357', 'Alpharetta'), ('NOR-01', 'Riley Test', '13572468', 'Norcross')]:
            if not db.get(Employee, identifier):
                db.add(Employee(id=identifier, name=name, credential_hash=hasher.hash(pin), office=office))
        for identifier, name in [('morgan', 'Morgan Test'), ('avery', 'Avery Test')]:
            if not db.get(Administrator, identifier):
                db.add(Administrator(id=identifier, name=name, credential_hash=hasher.hash('Ace-Admin-Test-2026')))
        db.commit()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed-test-accounts', action='store_true')
    args = parser.parse_args()
    if os.getenv('APP_ENV', 'development') != 'development' or not os.getenv('DATABASE_URL', 'sqlite:///./backend/ace.db').startswith('sqlite:'):
        parser.error('This initializer is restricted to local development SQLite databases.')
    engine, factory = database()
    initialize(engine)
    if args.seed_test_accounts:
        seed(factory)
    print('Local database initialized. Existing credentials were preserved.')

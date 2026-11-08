"""Persistent office catalog. Names remain the existing employee/index scope keys."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Office
from .taxonomy import CODES

DEFAULTS = [('ALP', 'Alpharetta'), ('NOR', 'Norcross'), ('LIL', 'Lilburn')]

def initialize(engine):
    """Add only the office table and required offices; never rewrite account records."""
    Office.__table__.create(engine, checkfirst=True)
    with Session(engine) as db:
        for code, name in DEFAULTS:
            if not db.get(Office, code):
                db.add(Office(code=code, name=name, name_key=name.casefold()))
        db.commit()

def catalog(db):
    return [dict(name=o.name, code=o.code, aliases=['ADC'] if o.code == 'LIL' else [])
            for o in db.scalars(select(Office).order_by(Office.name))]

def scope_codes(db):
    return dict(CODES, **{o.code: o.name for o in db.scalars(select(Office))})

if __name__ == '__main__':
    from .database import database
    engine, _ = database()
    initialize(engine)
    engine.dispose()
    print('Office catalog initialized; existing accounts and knowledge records preserved.')

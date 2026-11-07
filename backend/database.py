import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

class Base(DeclarativeBase):
    pass

def database(url=None):
    engine = create_engine(url or os.getenv('DATABASE_URL', 'sqlite:///./backend/ace.db'))
    if engine.dialect.name == 'sqlite':
        @event.listens_for(engine, 'connect')
        def configure(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA busy_timeout=10000')
    return engine, sessionmaker(engine, expire_on_commit=False)

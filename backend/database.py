import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.engine import URL, make_url
from .runtime import production, validate_environment

class Base(DeclarativeBase):
    pass

def database(url=None):
    validate_environment()
    configured = url or os.getenv('DATABASE_URL')
    if not configured and os.getenv('CLOUD_SQL_CONNECTION_NAME'):
        configured = URL.create('postgresql+psycopg', username=os.environ['DB_USER'],
            password=os.environ['DB_PASSWORD'], database=os.environ['DB_NAME'],
            query={'host': '/cloudsql/' + os.environ['CLOUD_SQL_CONNECTION_NAME']})
    parsed = make_url(configured or 'sqlite:///./backend/ace.db')
    if parsed.drivername in ('postgres', 'postgresql'):
        parsed = parsed.set(drivername='postgresql+psycopg')
    if production() and parsed.drivername != 'postgresql+psycopg':
        raise RuntimeError('Production requires persistent PostgreSQL; SQLite is for local development.')
    if production() and not configured:
        raise RuntimeError('Production requires an explicit persistent database.')
    if os.getenv('VERCEL'):
        host = parsed.host or ''
        if (not host.endswith('.render.com') or parsed.query.get('host')
                or parsed.query.get('hostaddr') or parsed.query.get('service')):
            raise RuntimeError('Vercel requires the full external Render PostgreSQL hostname.')
        if parsed.query.get('sslmode', 'verify-full') != 'verify-full':
            raise RuntimeError('Vercel database connections must verify TLS certificates (verify-full).')
        parsed = parsed.update_query_dict({'sslmode': 'verify-full',
                                          'sslrootcert': parsed.query.get('sslrootcert', 'system')})
    if production() and os.getenv('RENDER'):
        if parsed.query.get('sslmode', 'require') != 'require':
            raise RuntimeError('Render database connections must require TLS.')
        parsed = parsed.update_query_dict({'sslmode': 'require'})
    options = dict(pool_pre_ping=True, hide_parameters=True)
    if parsed.get_backend_name() == 'postgresql':
        options.update(pool_size=3, max_overflow=2, pool_timeout=10,
                       connect_args={'connect_timeout': 10, 'options': '-c statement_timeout=120000'})
        if os.getenv('VERCEL'):
            options.update(pool_size=1, max_overflow=1, pool_recycle=60)
    engine = create_engine(parsed, **options)
    if engine.dialect.name == 'sqlite':
        @event.listens_for(engine, 'connect')
        def configure(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA busy_timeout=10000')
    return engine, sessionmaker(engine, expire_on_commit=False)

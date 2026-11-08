import os
import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks
from .sync_service import SyncService, SyncBusy
from .drive_auth import DriveAuthError, auth_mode
from . import search as knowledge_search
from .discrepancies import review_log
import re
import secrets
import time
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func, update, inspect
from sqlalchemy.exc import IntegrityError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .database import database
from .models import Employee, Administrator, AuthSession, LoginAttempt, Office
from .offices import catalog
from .auth import hasher, DUMMY, verify, digest, resolve, serialize, lock_admin_changes
from .runtime import validate_environment
from .migrate import ready as schema_ready
from .job_dispatch import dispatch_sync


class HealthTrustedHostMiddleware(TrustedHostMiddleware):
    async def __call__(self, scope, receive, send):
        # Hosted HTTP probes may use an instance-IP Host header. These two
        # fixed, read-only endpoints never inspect accounts or documents.
        if scope['type'] == 'http' and scope['method'] == 'GET' and scope['path'] in ('/healthz', '/readyz'):
            return await self.app(scope, receive, send)
        return await super().__call__(scope, receive, send)

FRONTEND = Path(__file__).resolve().parent.parent / 'frontend'
CATEGORIES = ['All Categories', 'HR & Employee Policies', 'OSHA & Safety', 'Front Office', 'Back Office / Clinical Operations', 'Insurance & Documentation (non-PHI)', 'Management & Operations', 'Training & Onboarding', 'Scripts & Communication']
logger = logging.getLogger('uvicorn.error')

class Login(BaseModel):
    identifier: str = Field(min_length=1, max_length=80)
    credential: str = Field(min_length=1, max_length=256)

class NewEmployee(BaseModel):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    name: str = Field(min_length=1, max_length=120)
    office: str

class EmployeeDetails(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    office: str

class NewOffice(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=2, max_length=10)

    @field_validator('name')
    @classmethod
    def valid_name(cls, value):
        value = ' '.join(value.split())
        if not re.fullmatch(r"[\w][\w .&'()’-]{0,119}", value) or not any(c.isalpha() for c in value):
            raise ValueError('Use a readable office name with letters and optional numbers.')
        if value.casefold() in {'company-wide', 'all offices', 'all', 'company wide'}:
            raise ValueError('Choose a specific office name.')
        return value

    @field_validator('code')
    @classmethod
    def valid_code(cls, value):
        value = value.strip().upper()
        if not re.fullmatch(r'[A-Z][A-Z0-9]{1,9}', value):
            raise ValueError('Use 2–10 letters or digits, starting with a letter.')
        return value

class NewAdmin(BaseModel):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=256)

class Status(BaseModel):
    active: bool

class Password(BaseModel):
    password: str = Field(min_length=12, max_length=256)

class Search(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    office: str
    category: str

def create_app(url=None, *, defer_initialization=False):
    engine = factory = None

    def initialize():
        nonlocal engine, factory
        validate_environment(web=True)
        auth_mode()  # Reject local OAuth before any request can be served.
        engine, factory = database(url)
        app.state.engine, app.state.factory = engine, factory
        app.state.sync = SyncService(factory)

    @asynccontextmanager
    async def lifespan(app):
        if defer_initialization:
            _checked_startup(initialize)
        if production:
            try:
                if not schema_ready(app.state.engine):
                    raise RuntimeError('Schema not ready')
                with factory() as db:
                    if db.scalar(select(func.count()).select_from(Administrator).where(Administrator.active.is_(True))) < 2:
                        raise RuntimeError('Administrator setup incomplete')
                    from .knowledge_models import KnowledgeState
                    state = db.get(KnowledgeState, 1)
                    if not state or state.folder_id != os.environ['DRIVE_KNOWLEDGE_FOLDER_ID']:
                        raise RuntimeError('Approved folder changed; execute the release command')
            except Exception:
                engine.dispose()
                raise RuntimeError('Production is not ready. Check database connectivity and execute the release command.') from None
        logger.info('Knowledge APIs registered: GET /api/admin/knowledge, GET /api/admin/documents, POST /api/admin/sync, PATCH /api/admin/settings')
        logger.info('Knowledge runtime: source=%s, auth=%s, environment=%s, project_venv=%s',
                    os.getenv('KNOWLEDGE_SOURCE', 'drive'), auth_mode(),
                    os.getenv('APP_ENV', 'development'), sys.prefix != sys.base_prefix)
        if (os.getenv('KNOWLEDGE_SOURCE', 'drive') == 'drive' and auth_mode() == 'adc'
                and 'DRIVE_AUTH_MODE' not in os.environ):
            logger.warning('DRIVE_AUTH_MODE is unset; this process uses ADC. Local OAuth requires restarting with DRIVE_AUTH_MODE=oauth_local and the approved account/folder environment.')
        if not production:
            required = {'knowledge_state', 'knowledge_documents', 'knowledge_passages', 'knowledge_terms', 'discrepancy_scan', 'discrepancies'}
            if not required.issubset(inspect(app.state.engine).get_table_names()):
                logger.error('Knowledge schema is incomplete. Run python -m backend.initialize_knowledge with the server database configuration.')
            elif not {'issue_id', 'evidence_pairs'}.issubset({c['name'] for c in inspect(app.state.engine).get_columns('discrepancies')}):
                logger.error('Discrepancy grouping schema is incomplete. Run python -m backend.initialize_knowledge with the server database configuration.')
            elif 'revision' not in {c['name'] for c in inspect(app.state.engine).get_columns('discrepancy_scan')}:
                logger.error('Discrepancy scan revision schema is incomplete. Run python -m backend.initialize_knowledge with the server database configuration.')
            if 'offices' not in inspect(app.state.engine).get_table_names():
                logger.error('Office catalog is missing. Run python -m backend.offices with the server database configuration before serving requests.')
        async def schedule():
            while True:
                try:
                    await asyncio.to_thread(app.state.sync.run_if_due)
                except Exception as exc:
                    # Exception messages/tracebacks can contain private source data.
                    logger.warning('Knowledge scheduler check failed (%s). Check schema initialization and database availability.', type(exc).__name__)
                await asyncio.sleep(300)
        worker = None if production else asyncio.create_task(schedule())
        try:
            yield
        finally:
            if worker:
                worker.cancel()
                try:
                    await worker
                except asyncio.CancelledError:
                    pass
            engine.dispose()
    production = os.getenv('APP_ENV', 'development') == 'production'
    app = FastAPI(lifespan=lifespan, docs_url=None if production else '/docs',
                  redoc_url=None if production else '/redoc', openapi_url=None if production else '/openapi.json')
    if not defer_initialization:
        initialize()
    production = os.getenv('APP_ENV', 'development') == 'production'
    origin = os.getenv('APP_ORIGIN', 'http://127.0.0.1:8000').rstrip('/')
    cookie = '__Host-ace_session' if production else 'ace_session'
    from urllib.parse import urlsplit
    app.add_middleware(HealthTrustedHostMiddleware, allowed_hosts=[urlsplit(origin).hostname] if production else ['127.0.0.1', 'localhost', 'testserver'])

    @app.middleware('http')
    async def security(request, call_next):
        if production and ('preview' in request.query_params or request.url.path.startswith('/preview')):
            return JSONResponse({'detail': 'Not found.'}, 404)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            supplied = request.headers.get('origin')
            # Both loopback names work in development, but only on the origin
            # serving this request. Do not permit a separate static-server port.
            local_origin = (not production and request.url.hostname in ('localhost', '127.0.0.1')
                            and supplied == str(request.base_url).rstrip('/'))
            if supplied and supplied != origin and not local_origin:
                return JSONResponse({'detail': 'Invalid request origin.'}, 403)
            if request.headers.get('sec-fetch-site') == 'cross-site':
                return JSONResponse({'detail': 'Cross-site request rejected.'}, 403)
        try:
            response = await call_next(request)
        except Exception as exc:
            if not production:
                raise
            # Do not send tracebacks, SQL, query text, or source data to cloud logs.
            logger.warning('Request failed (%s).', type(exc).__name__)
            response = JSONResponse({'detail': 'Service temporarily unavailable.'}, 503)
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'Content-Security-Policy': "default-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})
        if production:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    def db_session():
        with factory() as db:
            yield db

    def authenticated(request: Request, db=Depends(db_session)):
        session, account = resolve(db, request.cookies.get(cookie))
        if request.method not in ('GET', 'HEAD') and not secrets.compare_digest(
                request.headers.get('x-csrf-token', '').encode('utf-8'), session.csrf.encode('utf-8')):
            raise HTTPException(403, 'Invalid CSRF token.', headers={'X-CSRF-Error': 'invalid'})
        return session, account

    def admin(identity=Depends(authenticated)):
        if identity[0].role != 'admin':
            raise HTTPException(403, 'Administrator access required.')
        return identity

    from .drive_web_oauth import install_routes
    install_routes(app, admin)

    @app.get('/healthz', include_in_schema=False)
    def health():
        return {'status': 'ok'}

    @app.get('/readyz', include_in_schema=False)
    def readiness():
        try:
            if schema_ready(engine):
                return {'status': 'ok'}
        except Exception:
            pass
        return JSONResponse({'status': 'unavailable'}, 503)

    @app.exception_handler(IntegrityError)
    async def duplicate(request, exc):
        return JSONResponse({'detail': 'Account identifier already exists.'}, 409)

    @app.post('/api/auth/{role}/login')
    def login(role: str, body: Login, request: Request, db=Depends(db_session)):
        if role not in ('employee', 'admin'):
            raise HTTPException(404)
        identifier = body.identifier.strip()
        key = digest(role + ':' + identifier)
        # Serialize lockout counters, including concurrent requests for unknown IDs.
        lock_admin_changes(db)
        attempt = db.get(LoginAttempt, key)
        now = time.time()
        if not attempt:
            attempt = LoginAttempt(key=key, failures=0, window=now, locked_until=0)
            db.add(attempt)
        model = Employee if role == 'employee' else Administrator
        account = db.get(model, identifier)
        valid = verify(account.credential_hash if account else DUMMY, body.credential)
        valid = valid and (role != 'employee' or bool(re.fullmatch(r'[0-9]{8}', body.credential)))
        if attempt.locked_until > now:
            db.commit()
            raise HTTPException(401, 'Invalid account or credentials. Try again later.')
        if not valid or not account or not account.active:
            if now - attempt.window >= 900:
                attempt.window, attempt.failures = now, 0
            attempt.failures += 1
            if attempt.failures >= 5:
                attempt.locked_until = now + 900
            db.commit()
            raise HTTPException(401, 'Invalid account or credentials. Try again later.')
        attempt.failures, attempt.locked_until = 0, 0
        old = db.get(AuthSession, digest(request.cookies.get(cookie, '')))
        if old:
            db.delete(old)
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        db.add(AuthSession(token_hash=digest(token), role=role, account_id=account.id, version=account.version, csrf=csrf, expires=now + 28800))
        db.commit()
        response = JSONResponse({'user': serialize(account, role), 'csrf_token': csrf})
        response.set_cookie(cookie, token, httponly=True, secure=production, samesite='strict', max_age=28800, path='/')
        return response

    @app.get('/api/auth/me')
    def me(identity=Depends(authenticated)):
        session, account = identity
        return {'user': serialize(account, session.role), 'csrf_token': session.csrf}

    @app.post('/api/auth/logout')
    def logout(identity=Depends(authenticated), db=Depends(db_session)):
        db.delete(identity[0]); db.commit()
        response = JSONResponse({'ok': True})
        response.delete_cookie(cookie, path='/', secure=production, httponly=True, samesite='strict')
        return response

    @app.post('/api/search')
    async def search(body: Search, request: Request, identity=Depends(authenticated), db=Depends(db_session)):
        if not db.scalar(select(Office).where(Office.name == body.office)) or body.category not in CATEGORIES:
            raise HTTPException(422, 'Invalid search filters.')
        # No contents or employee-query associations are persisted or logged.
        # Explicit development/admin diagnostics return only fixed stage counts.
        # No logging, storage, employee identity, questions, or source text.
        trace = {} if (not production and identity[0].role == 'admin'
                       and request.headers.get('x-ace-search-diagnostics') == 'counts') else None
        try:
            result = await asyncio.wait_for(asyncio.to_thread(knowledge_search.search, factory,
                body.question, body.office, body.category, diagnostics=trace), timeout=40)
        except Exception:
            # The worker may still be unwinding; do not read a partial trace.
            result = knowledge_search.unavailable()
            trace = None
        headers = {'X-Ace-Search-Revision': knowledge_search.REVISION}
        if trace is not None:
            headers['X-Ace-Search-Trace'] = ','.join(f'{key}={value}' for key, value in trace.items())
        return JSONResponse(result, headers=headers)

    @app.get('/api/offices', dependencies=[Depends(authenticated)])
    @app.get('/api/admin/offices', dependencies=[Depends(admin)])
    def offices(db=Depends(db_session)):
        return catalog(db)

    @app.post('/api/admin/offices', status_code=201, dependencies=[Depends(admin)])
    def create_office(body: NewOffice, db=Depends(db_session)):
        # Serialize catalog writes and keep aliases in the same code namespace.
        lock_admin_changes(db)
        existing = catalog(db)
        codes = {c for o in existing for c in [o['code'], *o['aliases']]}
        names = {o['name'].casefold() for o in existing}
        if (body.code in codes or body.name.casefold() in names
                or body.name.upper() in codes or body.code.casefold() in names):
            raise HTTPException(409, 'Office name or code already exists, including office aliases.')
        db.add(Office(code=body.code, name=body.name, name_key=body.name.casefold()))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Office name or code already exists.') from None
        return {'name': body.name, 'code': body.code, 'aliases': []}

    @app.get('/api/admin/employees', dependencies=[Depends(admin)])
    def employees(db=Depends(db_session)):
        return [dict(serialize(a, 'employee'), active=a.active, office=a.office) for a in db.scalars(select(Employee))]

    @app.post('/api/admin/employees', dependencies=[Depends(admin)])
    def create_employee(body: NewEmployee, db=Depends(db_session)):
        if not db.scalar(select(Office).where(Office.name == body.office)):
            raise HTTPException(422, 'Invalid office.')
        pin = f'{secrets.randbelow(100000000):08d}'
        db.add(Employee(id=body.id, name=body.name, office=body.office, credential_hash=hasher.hash(pin)))
        db.commit()
        return {'pin': pin}

    @app.patch('/api/admin/employees/{identifier}/details', dependencies=[Depends(admin)])
    def employee_details(identifier: str, body: EmployeeDetails, db=Depends(db_session)):
        if not body.name.strip() or not db.scalar(select(Office).where(Office.name == body.office)):
            raise HTTPException(422, 'Invalid employee name or office.')
        result = db.execute(update(Employee).where(Employee.id == identifier).values(
            name=body.name.strip(), office=body.office, version=Employee.version + 1))
        if not result.rowcount:
            raise HTTPException(404, 'Employee not found.')
        db.commit()
        return {'ok': True}

    @app.patch('/api/admin/employees/{identifier}', dependencies=[Depends(admin)])
    def employee_status(identifier: str, body: Status, db=Depends(db_session)):
        # Atomic update prevents racing a PIN replacement.
        result = db.execute(update(Employee).where(Employee.id == identifier).values(active=body.active, version=Employee.version + 1))
        if not result.rowcount:
            raise HTTPException(404, 'Employee not found.')
        db.commit(); return {'ok': True}

    @app.post('/api/admin/employees/{identifier}/pin', dependencies=[Depends(admin)])
    def replace_pin(identifier: str, db=Depends(db_session)):
        pin = f'{secrets.randbelow(100000000):08d}'
        result = db.execute(update(Employee).where(Employee.id == identifier).values(credential_hash=hasher.hash(pin), version=Employee.version + 1))
        if not result.rowcount:
            raise HTTPException(404, 'Employee not found.')
        db.commit(); return {'pin': pin}

    @app.get('/api/admin/admins', dependencies=[Depends(admin)])
    def admins(db=Depends(db_session)):
        return [dict(serialize(a, 'admin'), active=a.active) for a in db.scalars(select(Administrator))]

    @app.post('/api/admin/admins', dependencies=[Depends(admin)])
    def create_admin(body: NewAdmin, db=Depends(db_session)):
        lock_admin_changes(db)
        db.add(Administrator(id=body.id, name=body.name, credential_hash=hasher.hash(body.password)))
        db.commit(); return {'ok': True}

    @app.patch('/api/admin/admins/{identifier}', dependencies=[Depends(admin)])
    def admin_status(identifier: str, body: Status, db=Depends(db_session)):
        lock_admin_changes(db)
        account = db.get(Administrator, identifier)
        if not account:
            raise HTTPException(404)
        count = db.scalar(select(func.count()).select_from(Administrator).where(Administrator.active.is_(True)))
        if account.active and not body.active and count <= 2:
            raise HTTPException(409, 'At least two active administrators must remain.')
        account.active = body.active; account.version += 1
        db.commit(); return {'ok': True}

    @app.delete('/api/admin/admins/{identifier}', dependencies=[Depends(admin)])
    def delete_admin(identifier: str, db=Depends(db_session)):
        lock_admin_changes(db)
        account = db.get(Administrator, identifier)
        if not account:
            raise HTTPException(404)
        count = db.scalar(select(func.count()).select_from(Administrator).where(Administrator.active.is_(True)))
        if account.active and count <= 2:
            raise HTTPException(409, 'At least two active administrators must remain.')
        db.delete(account); db.commit(); return {'ok': True}

    @app.post('/api/admin/admins/{identifier}/password', dependencies=[Depends(admin)])
    def password(identifier: str, body: Password, db=Depends(db_session)):
        lock_admin_changes(db)
        result = db.execute(update(Administrator).where(Administrator.id == identifier).values(credential_hash=hasher.hash(body.password), version=Administrator.version + 1))
        if not result.rowcount:
            raise HTTPException(404)
        db.commit(); return {'ok': True}

    class FolderSettings(BaseModel):
        folder_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,200}$')

    @app.get('/api/admin/discrepancies', dependencies=[Depends(admin)])
    def discrepancies():
        return review_log(factory, include_evidence=False)

    @app.get('/api/admin/discrepancies/{generation}/{identifier}', dependencies=[Depends(admin)])
    def discrepancy_details(generation: str, identifier: str):
        # Reverify all evidence on each request. The stable issue ID survives
        # re-syncs; the generation prevents showing a stale source comparison.
        for item in review_log(factory)['discrepancies']:
            if item['generation'] == generation and item['id'] == identifier:
                return item
        raise HTTPException(404, 'This discrepancy is no longer available. Refresh the Find & Fix Log.')

    @app.get('/api/admin/knowledge', dependencies=[Depends(admin)])
    @app.get('/api/admin/documents', dependencies=[Depends(admin)])
    def knowledge_status():
        status = app.state.sync.status()
        status['authorization_mode'] = auth_mode()
        return status

    @app.patch('/api/admin/settings', dependencies=[Depends(admin)])
    def knowledge_settings(body: FolderSettings):
        try:
            app.state.sync.configure(body.folder_id)
        except SyncBusy:
            raise HTTPException(409, 'Wait for the current synchronization to finish.')
        except DriveAuthError as exc:
            raise HTTPException(422, str(exc)) from None
        return {'ok': True}

    @app.post('/api/admin/sync', status_code=202, dependencies=[Depends(admin)])
    def synchronize(background: BackgroundTasks):
        status = app.state.sync.status()
        if not status['folder_id']:
            raise HTTPException(409, 'Configure the Google Drive folder ID first.')
        if status['running']:
            raise HTTPException(409, 'Synchronization is already running.')
        if production:
            try:
                dispatch_sync(factory)
            except Exception:
                raise HTTPException(503, 'Synchronization could not be scheduled. Please retry.') from None
            return {'status': 'scheduled'}
        try:
            reservation = app.state.sync.reserve()
        except SyncBusy:
            raise HTTPException(409, 'Synchronization is already running.')
        def run():
            try:
                app.state.sync.run(reservation)
            except SyncBusy:
                pass
        background.add_task(run)
        return {'status': 'scheduled'}

    @app.api_route('/api/admin/{service:path}', methods=['GET', 'POST', 'PATCH', 'DELETE'], dependencies=[Depends(admin)], include_in_schema=False)
    def unconnected(service: str):
        raise HTTPException(503, 'This service is not connected.')

    @app.get('/')
    @app.get('/index.html')
    @app.get('/admin.html')
    def dashboard(request: Request, db=Depends(db_session)):
        is_admin = request.url.path == '/admin.html'
        try:
            session, _ = resolve(db, request.cookies.get(cookie))
            if is_admin and session.role != 'admin':
                return RedirectResponse('/admin-login.html', 303)
        except HTTPException:
            return RedirectResponse('/admin-login.html' if is_admin else '/login.html', 303)
        return FileResponse(FRONTEND / ('admin.html' if is_admin else 'index.html'))

    @app.get('/assets/ace-logo.webp', include_in_schema=False)
    def brand_logo():
        return FileResponse(FRONTEND / 'assets' / 'ace-logo.webp', media_type='image/webp')

    @app.get('/{filename}')
    def asset(filename: str):
        if filename not in {'login.html', 'admin-login.html', 'login.js', 'auth-client.js', 'live-admin.js', 'login.css', 'style.css', 'admin.css', 'ui.css', 'script.js', 'admin.js'}:
            raise HTTPException(404)
        return FileResponse(FRONTEND / filename)
    return app

def _checked_startup(initialize):
    # Bootstrap is an operator release task, never an HTTP startup task.
    os.environ.pop("BOOTSTRAP_ADMINS", None)
    try:
        return initialize()
    except Exception as exc:
        # Only fixed setting names and the exception class are safe to expose.
        # Exception text can contain database URLs, credentials, or source data.
        required = (
            'APP_ENV', 'APP_ORIGIN', 'DATABASE_URL', 'KNOWLEDGE_SOURCE',
            'DRIVE_AUTH_MODE', 'SYNC_EXECUTOR', 'DRIVE_AUTHORIZED_EMAIL',
            'DRIVE_KNOWLEDGE_FOLDER_ID', 'DRIVE_WEB_CLIENT_ID',
            'DRIVE_WEB_CLIENT_SECRET', 'DRIVE_TOKEN_ENCRYPTION_KEY',
        )
        missing = [key for key in required if not os.getenv(key)]
        detail = (' Missing required settings: ' + ', '.join(missing) + '.') if os.getenv('VERCEL') and missing else ''
        raise RuntimeError(
            f'Startup failed ({type(exc).__name__}).{detail} '
            'Check production configuration and release prerequisites; private details suppressed.'
        ) from None


def _startup_app():
    # Build discovery imports this module without production credentials.
    # Lifespan performs the same strict checks before runtime serves requests.
    os.environ.pop("BOOTSTRAP_ADMINS", None)
    return _checked_startup(lambda: create_app(defer_initialization=True))


app = _startup_app()

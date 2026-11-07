import hashlib
import secrets
import time
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import HTTPException
from sqlalchemy import select, update
from .models import Employee, Administrator, AuthSession, AdminGuard

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY = hasher.hash(secrets.token_urlsafe(32))

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def verify(stored, value):
    try:
        return hasher.verify(stored, value)
    except (VerificationError, InvalidHashError):
        return False

def serialize(account, role):
    return {'id': account.id, 'name': account.name, 'role': role,
            'home_office': getattr(account, 'office', 'Alpharetta')}

def resolve(db, token):
    session = db.get(AuthSession, digest(token or ''))
    if not session or session.expires <= time.time():
        raise HTTPException(401, 'Please sign in again.')
    model = Administrator if session.role == 'admin' else Employee
    account = db.get(model, session.account_id)
    if not account or not account.active or account.version != session.version:
        raise HTTPException(401, 'Please sign in again.')
    return session, account

def lock_admin_changes(db):
    # A shared row serializes mutations in both SQLite and PostgreSQL.
    db.execute(update(AdminGuard).where(AdminGuard.id == 1).values(revision=AdminGuard.revision + 1))

from sqlalchemy import String, Integer, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class Account:
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    credential_hash: Mapped[str] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

class Employee(Account, Base):
    __tablename__ = 'employees'
    office: Mapped[str] = mapped_column(String(120))

class Administrator(Account, Base):
    __tablename__ = 'administrators'

class AuthSession(Base):
    __tablename__ = 'authentication_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[str] = mapped_column(String(12))
    account_id: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer)
    csrf: Mapped[str] = mapped_column(String(80))
    expires: Mapped[float] = mapped_column(Float)

class LoginAttempt(Base):
    __tablename__ = 'login_attempts'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    window: Mapped[float] = mapped_column(Float, default=0)
    locked_until: Mapped[float] = mapped_column(Float, default=0)

class AdminGuard(Base):
    __tablename__ = 'admin_guard'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)

from .knowledge_models import KnowledgeState, Document, Passage  # noqa: F401

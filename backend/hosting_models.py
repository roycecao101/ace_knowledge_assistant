"""Hosted credentials and work requests. Never contains questions or answers."""
from sqlalchemy import String, Text, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class DriveGrant(Base):
    __tablename__ = 'drive_grant'
    id: Mapped[int] = mapped_column(primary_key=True)
    binding: Mapped[str] = mapped_column(String(64))
    encrypted_refresh: Mapped[str] = mapped_column(Text)


class DriveConsent(Base):
    __tablename__ = 'drive_consent'
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_hash: Mapped[str] = mapped_column(String(64))
    browser_hash: Mapped[str] = mapped_column(String(64))
    encrypted_verifier: Mapped[str] = mapped_column(Text)
    binding: Mapped[str] = mapped_column(String(64))
    expires: Mapped[float] = mapped_column(Float)


class SyncRequest(Base):
    __tablename__ = 'sync_request'
    id: Mapped[int] = mapped_column(primary_key=True)
    requested: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[int] = mapped_column(Integer, default=0)

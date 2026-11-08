"""Private source snapshots; no employee questions or answers are persisted."""
from sqlalchemy import String, Text, Float, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class KnowledgeState(Base):
    __tablename__ = 'knowledge_state'
    id: Mapped[int] = mapped_column(primary_key=True)
    folder_id: Mapped[str] = mapped_column(String(200), default='')
    active_generation: Mapped[str] = mapped_column(String(40), default='')
    last_success: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_attempt: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str] = mapped_column(Text, default='')
    lease_until: Mapped[float] = mapped_column(Float, default=0)
    lease_token: Mapped[str] = mapped_column(String(40), default='')

class Document(Base):
    __tablename__ = 'knowledge_documents'
    id: Mapped[int] = mapped_column(primary_key=True)
    generation: Mapped[str] = mapped_column(String(40), index=True)
    file_id: Mapped[str] = mapped_column(String(512))
    filename: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(Text)
    offices: Mapped[list] = mapped_column(JSON)
    modified: Mapped[str] = mapped_column(String(80))
    content_hash: Mapped[str] = mapped_column(String(64))
    source_text: Mapped[str] = mapped_column(Text)
    error: Mapped[str] = mapped_column(Text, default='')

class Passage(Base):
    __tablename__ = 'knowledge_passages'
    id: Mapped[int] = mapped_column(primary_key=True)
    generation: Mapped[str] = mapped_column(String(40), index=True)
    document_id: Mapped[int] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(Text)
    normalized: Mapped[str] = mapped_column(Text)
    heading: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offices: Mapped[list] = mapped_column(JSON)

class PassageTerm(Base):
    __tablename__ = 'knowledge_terms'
    passage_id: Mapped[int] = mapped_column(primary_key=True)
    term: Mapped[str] = mapped_column(String(150), primary_key=True, index=True)
    generation: Mapped[str] = mapped_column(String(40), index=True)

class DiscrepancyScan(Base):
    __tablename__ = 'discrepancy_scan'
    id: Mapped[int] = mapped_column(primary_key=True)
    generation: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    last_attempt: Mapped[float] = mapped_column(Float)
    last_success: Mapped[float | None] = mapped_column(Float, nullable=True)
    revision: Mapped[str | None] = mapped_column(String(64), nullable=True)

class Discrepancy(Base):
    """References only: quotations stay in the private, current source snapshot."""
    __tablename__ = 'discrepancies'
    id: Mapped[int] = mapped_column(primary_key=True)
    generation: Mapped[str] = mapped_column(String(40), index=True)
    passage_a: Mapped[int] = mapped_column(Integer)
    passage_b: Mapped[int] = mapped_column(Integer)
    # Nullable for additive upgrades. Legacy pair rows await a new scan.
    issue_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Each side is one passage ID, or an ordered list of IDs for an exact,
    # contiguous source window. Quotations are reconstructed and reverified.
    evidence_pairs: Mapped[list | None] = mapped_column(JSON, nullable=True)

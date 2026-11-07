"""Full inventory reconciliation with a database lease and atomic publication."""
import hashlib
import os
import time
import uuid
from sqlalchemy import select, update, delete
from .knowledge_models import KnowledgeState, Document, Passage, PassageTerm
from .document_parser import parse, Unreadable
from .document_indexer import index_document
from .taxonomy import filename_offices

class SyncBusy(Exception):
    pass

class SyncService:
    def __init__(self, factory, source_factory=None):
        self.factory = factory
        self.source_factory = source_factory or self.default_source

    @staticmethod
    def default_source():
        if os.getenv('KNOWLEDGE_SOURCE', 'drive') == 'local':
            from .local_source import LocalSource
            return LocalSource(os.environ['SYNTHETIC_DOCUMENT_DIR'])
        from .drive_client import DriveClient
        return DriveClient()

    def status(self):
        with self.factory() as db:
            state = db.get(KnowledgeState, 1)
            if not state:
                return dict(folder_id='', last_success=None, last_attempt=None, error='', running=False, documents=[])
            documents = db.scalars(select(Document).where(Document.generation == state.active_generation)).all()
            return dict(folder_id=state.folder_id, last_success=state.last_success, last_attempt=state.last_attempt,
                error=state.error, running=state.lease_until > time.time(), documents=[dict(file_id=d.file_id, filename=d.filename,
                category=d.category, offices=d.offices, modified=d.modified, content_hash=d.content_hash,
                status='unreadable' if d.error else 'indexed', error=d.error) for d in documents])

    def configure(self, folder_id):
        with self.factory.begin() as db:
            state = db.get(KnowledgeState, 1)
            if not state:
                db.add(KnowledgeState(id=1, folder_id=folder_id))
            else:
                changed = db.execute(update(KnowledgeState).where(KnowledgeState.id == 1,
                    KnowledgeState.lease_until <= time.time()).values(folder_id=folder_id,
                    active_generation=state.active_generation if folder_id == state.folder_id else '',
                    last_success=state.last_success if folder_id == state.folder_id else None,
                    error=''))
                if not changed.rowcount:
                    raise SyncBusy()

    def run(self):
        token, now = uuid.uuid4().hex, time.time()
        # Configure creates the singleton before first run; no startup schema mutation.
        with self.factory.begin() as db:
            state = db.get(KnowledgeState, 1)
            if not state:
                raise ValueError('Configure the knowledge folder first')
            folder = state.folder_id
            claimed = db.execute(update(KnowledgeState).where(KnowledgeState.id == 1, KnowledgeState.lease_until <= now, KnowledgeState.folder_id == folder).values(lease_until=now+600, lease_token=token, last_attempt=now, error=''))
            if not claimed.rowcount:
                raise SyncBusy()
        generation = uuid.uuid4().hex
        try:
            source = self.source_factory()
            inventory = source.inventory(folder)
            seen, staged, total_bytes = set(), [], 0
            if len(inventory) > 1000:
                raise ValueError('Knowledge folder exceeds 1000-file limit')
            # Download and extract before taking a write transaction, so authentication
            # writes and current search remain available while Drive is slow.
            for file in inventory:
                if file.id in seen:
                    raise ValueError('Duplicate source file')
                seen.add(file.id)
                data = source.read(file)
                total_bytes += len(data)
                if total_bytes > 100 * 1024 * 1024:
                    raise ValueError('Knowledge folder exceeds 100 MB snapshot limit')
                parsed, error = None, ''
                try:
                    parsed = parse(data, file.mime, file.name)
                except Unreadable as exc:
                    error = str(exc)
                staged.append((file, hashlib.sha256(data).hexdigest(), parsed, error))
                if time.time() >= now+540:
                    raise TimeoutError('Sync exceeded its time limit')
            with self.factory.begin() as db:
                for file, content_hash, parsed, error in staged:
                    doc = Document(generation=generation, file_id=file.id, filename=file.name, mime_type=file.mime,
                        category=file.category, offices=filename_offices(file.name), modified=file.modified,
                        content_hash=content_hash, source_text=parsed.source if parsed else '', error=error)
                    db.add(doc); db.flush()
                    if parsed:
                        index_document(db, doc, parsed)
                # Re-read active state under the publication lock and invalidate stale
                # leases before publishing; a crashed worker cannot replace a newer run.
                published = db.execute(update(KnowledgeState).where(KnowledgeState.id == 1,
                    KnowledgeState.lease_token == token, KnowledgeState.lease_until > time.time(),
                    KnowledgeState.folder_id == folder).values(active_generation=generation,
                    last_success=time.time(), error='', lease_until=0, lease_token=''))
                if not published.rowcount:
                    raise RuntimeError('Sync lease expired')
                # Old snapshots are no longer needed; deletion is in the same transaction.
                db.execute(delete(PassageTerm).where(PassageTerm.generation != generation))
                db.execute(delete(Passage).where(Passage.generation != generation))
                db.execute(delete(Document).where(Document.generation != generation))
            return True
        except Exception:
            with self.factory.begin() as db:
                db.execute(update(KnowledgeState).where(KnowledgeState.id == 1, KnowledgeState.lease_token == token).values(
                    lease_until=0, lease_token='', error='Synchronization failed. Check folder access, credentials, file limits, and service availability; the previous index was retained.'))
            return False

    def run_if_due(self):
        status = self.status()
        if status['folder_id'] and not status['running'] and (not status['last_success'] or time.time()-status['last_success'] >= 23*3600):
            try:
                self.run()
            except SyncBusy:
                pass

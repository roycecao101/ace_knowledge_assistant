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
from .offices import scope_codes
from .drive_client import FileUnreadable
from .drive_auth import DriveAuthError, validate_folder
from .discrepancies import publish_scan

class SyncBusy(Exception):
    pass

def safe_extraction_error(message):
    """Only fixed diagnostics may leave the extractor, including legacy rows."""
    allowed = {
        'Password-protected PDF', 'PDF has a page without extractable text; OCR is not enabled',
        'Empty PDF', 'PDF extraction failed', 'Word archive exceeds extraction limit',
        'Word document contains no extractable text', 'Word extraction failed',
        'Unsupported format; use a text PDF, .docx, or Google Doc',
        'Google Drive does not permit download/export of this file',
        'Legacy Word .doc is unsupported; convert to .docx or Google Docs in Drive',
    }
    return message if not message or message in allowed else 'File extraction failed. Provide an approved readable version in Drive, then re-sync.'

class SyncService:
    def __init__(self, factory, source_factory=None):
        self.factory = factory
        self.source_factory = source_factory or self.default_source

    @staticmethod
    def default_source():
        source = os.getenv('KNOWLEDGE_SOURCE', 'drive')
        if source == 'local':
            from .local_source import LocalSource
            return LocalSource(os.environ['SYNTHETIC_DOCUMENT_DIR'])
        if source != 'drive':
            raise DriveAuthError('Set KNOWLEDGE_SOURCE to drive or local.')
        from .drive_client import DriveClient
        return DriveClient()

    def status(self):
        with self.factory() as db:
            state = db.get(KnowledgeState, 1)
            if not state:
                return dict(folder_id='', configured=False, connection_verified=False, sync_status='not_configured',
                    source_type=os.getenv('KNOWLEDGE_SOURCE', 'drive'),
                    indexed_count=0, unreadable_count=0, last_success=None, last_attempt=None, error='', running=False, documents=[])
            documents = db.scalars(select(Document).where(Document.generation == state.active_generation).order_by(Document.filename)).all()
            running = state.lease_until > time.time()
            error = state.error or ('Synchronization stopped before completing. Please retry.' if state.lease_token and not running else '')
            status = ('running' if running else 'failed' if error else 'succeeded' if state.last_success
                      else 'pending' if state.folder_id else 'not_configured')
            return dict(folder_id=state.folder_id, configured=bool(state.folder_id), connection_verified=bool(state.last_success),
                source_type=os.getenv('KNOWLEDGE_SOURCE', 'drive'),
                sync_status=status, indexed_count=sum(not d.error for d in documents), unreadable_count=sum(bool(d.error) for d in documents),
                last_success=state.last_success, last_attempt=state.last_attempt,
                error=error, running=running, documents=[dict(file_id=d.file_id, filename=d.filename,
                category=d.category, offices=d.offices, modified=d.modified, content_hash=d.content_hash,
                status='unreadable' if d.error else 'indexed', error=safe_extraction_error(d.error)) for d in documents])

    def configure(self, folder_id):
        if os.getenv('KNOWLEDGE_SOURCE', 'drive') == 'drive':
            validate_folder(folder_id)
        with self.factory.begin() as db:
            state = db.get(KnowledgeState, 1)
            if not state:
                db.add(KnowledgeState(id=1, folder_id=folder_id))
            else:
                changed = db.execute(update(KnowledgeState).where(KnowledgeState.id == 1,
                    KnowledgeState.lease_until <= time.time()).values(folder_id=folder_id,
                    active_generation=state.active_generation if folder_id == state.folder_id else '',
                    last_success=state.last_success if folder_id == state.folder_id else None,
                    last_attempt=state.last_attempt if folder_id == state.folder_id else None,
                    error=state.error if folder_id == state.folder_id else ''))
                if not changed.rowcount:
                    raise SyncBusy()

    def reserve(self):
        """Claim before returning HTTP 202, so concurrent clicks get HTTP 409."""
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
        return token, now, folder

    def run(self, reservation=None):
        token, now, folder = reservation or self.reserve()
        generation = uuid.uuid4().hex
        stage = 'source configuration'
        try:
            if os.getenv('KNOWLEDGE_SOURCE', 'drive') == 'drive':
                validate_folder(folder)
            stage = 'Google authorization' if os.getenv('KNOWLEDGE_SOURCE', 'drive') == 'drive' else 'local source setup'
            source = self.source_factory()
            stage = 'folder inventory'
            inventory = source.inventory(folder)
            with self.factory() as db:
                codes = scope_codes(db)
            seen, staged, total_bytes = set(), [], 0
            if len(inventory) > 1000:
                raise ValueError('Knowledge folder exceeds 1000-file limit')
            # Download and extract before taking a write transaction, so authentication
            # writes and current search remain available while Drive is slow.
            for file in inventory:
                if file.id in seen:
                    raise ValueError('Duplicate source file')
                seen.add(file.id)
                parsed, error, data = None, '', b''
                try:
                    stage = 'file download/export'
                    data = source.read(file)
                    total_bytes += len(data)
                    if total_bytes > 100 * 1024 * 1024:
                        raise ValueError('Knowledge folder exceeds 100 MB snapshot limit')
                    stage = 'text extraction'
                    parsed = parse(data, file.mime, file.name, codes)
                except (Unreadable, FileUnreadable) as exc:
                    error = safe_extraction_error(str(exc))
                staged.append((file, hashlib.sha256(data).hexdigest(), parsed, error))
                if time.time() >= now+540:
                    raise TimeoutError('Sync exceeded its time limit')
            stage = 'document indexing/database update'
            with self.factory.begin() as db:
                for file, content_hash, parsed, error in staged:
                    scopes = [s.offices for s in parsed.sections if s.searchable] if parsed else []
                    offices = (sorted({o for scope in scopes for o in scope}) if scopes and all(scopes)
                               else [] if scopes else filename_offices(file.name, codes))
                    doc = Document(generation=generation, file_id=file.id, filename=file.name, mime_type=file.mime,
                        category=file.category, offices=offices, modified=file.modified,
                        content_hash=content_hash, source_text=parsed.source if parsed else '', error=error)
                    db.add(doc); db.flush()
                    if parsed:
                        index_document(db, doc, parsed)
                # Re-read active state under the publication lock and invalidate stale
                # leases before publishing; a crashed worker cannot replace a newer run.
                stage = 'snapshot publication'
                published = db.execute(update(KnowledgeState).where(KnowledgeState.id == 1,
                    KnowledgeState.lease_token == token, KnowledgeState.lease_until > time.time(),
                    KnowledgeState.folder_id == folder).values(active_generation=generation,
                    last_success=time.time(), error='', lease_until=0, lease_token=''))
                if not published.rowcount:
                    raise RuntimeError('Sync lease expired')
                publish_scan(db, generation)
                # Old snapshots are no longer needed; deletion is in the same transaction.
                stage = 'old snapshot cleanup'
                db.execute(delete(PassageTerm).where(PassageTerm.generation != generation))
                db.execute(delete(Passage).where(Passage.generation != generation))
                db.execute(delete(Document).where(Document.generation != generation))
            return True
        except Exception as exc:
            # Classify without returning raw Google errors (which can contain
            # private URLs, identifiers, access tokens, or response content).
            from google.auth.exceptions import DefaultCredentialsError, RefreshError
            from googleapiclient.errors import HttpError
            reason = 'Check folder access, credentials, file limits, and service availability.'
            if isinstance(exc, DriveAuthError):
                reason = str(exc)
            elif isinstance(exc, (DefaultCredentialsError, RefreshError)):
                reason = 'Backend Google credentials are missing or expired. Ask the technical owner to restore them.'
                if os.getenv('KNOWLEDGE_SOURCE', 'drive') == 'drive' and os.getenv('DRIVE_AUTH_MODE', 'adc') == 'adc':
                    reason += ' This server uses DRIVE_AUTH_MODE=adc; local OAuth verification requires restarting FastAPI with DRIVE_AUTH_MODE=oauth_local and the same approved account/folder settings.'
            elif isinstance(exc, HttpError):
                reason = {401: 'Google authorization failed. Ask the technical owner to restore backend authorization.',
                          403: 'Google denied access. Check the authorized Google identity Viewer permission and export restrictions.',
                          404: 'Google could not find the folder or a listed file. Verify the folder ID and retry.',
                          429: 'Google rate limit reached. Wait a few minutes and retry.'}.get(exc.resp.status,
                          'Google Drive is unavailable. Please retry later.')
            elif isinstance(exc, TimeoutError):
                reason = 'Synchronization exceeded its time limit. Retry or reduce the approved folder size.'
            with self.factory.begin() as db:
                db.execute(update(KnowledgeState).where(KnowledgeState.id == 1, KnowledgeState.lease_token == token).values(
                    lease_until=0, lease_token='', error='Synchronization failed during ' + stage + '. ' + reason + ' The previous index was retained.'))
            return False

    def run_if_due(self):
        status = self.status()
        if status['folder_id'] and not status['running'] and (not status['last_success'] or time.time()-status['last_success'] >= 23*3600):
            try:
                self.run()
            except SyncBusy:
                pass

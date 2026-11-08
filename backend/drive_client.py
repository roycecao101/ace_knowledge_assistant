"""Folder-scoped read-only Google Drive adapter. Never follows shortcuts."""
import re
from dataclasses import dataclass
from .taxonomy import CATEGORIES
from .drive_auth import drive_service, validate_folder

PDF = 'application/pdf'
DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
GDOC = 'application/vnd.google-apps.document'
FOLDER = 'application/vnd.google-apps.folder'
LEGACY_WORD = 'application/msword'
SUPPORTED = {PDF, DOCX, GDOC, LEGACY_WORD}
MAX_BYTES = 25 * 1024 * 1024

@dataclass
class SourceFile:
    id: str
    name: str
    mime: str
    modified: str
    category: str = 'All Categories'
    downloadable: bool = True

class FileUnreadable(ValueError):
    """A safe per-file error; transport and inventory failures still abort sync."""

class DriveClient:
    def __init__(self, service=None):
        self.service = service if service is not None else drive_service()
        self._permitted = {}
        self._parents = {}
        self._root = None

    def inventory(self, folder_id):
        self._permitted, self._parents, self._root = {}, {}, None
        validate_folder(folder_id)
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', folder_id):
            raise ValueError('Invalid knowledge folder ID')
        root = self.service.files().get(fileId=folder_id, fields='id,mimeType,trashed', supportsAllDrives=True).execute()
        if root.get('trashed') or root['mimeType'] != FOLDER:
            raise ValueError('Knowledge source is not an accessible folder')
        result, seen, parents = [], set(), {}
        def visit(parent, category):
            if parent in seen:
                raise ValueError('Duplicate folder traversal')
            seen.add(parent)
            if len(seen) > 1000:
                raise ValueError('Knowledge folder exceeds folder limit')
            token = None
            tokens = set()
            while True:
                response = self.service.files().list(q=f"'{parent}' in parents and trashed = false", fields='nextPageToken,incompleteSearch,files(id,name,mimeType,modifiedTime,size,capabilities(canDownload))', pageToken=token, pageSize=100, supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
                if response.get('incompleteSearch'):
                    raise RuntimeError('Incomplete Drive inventory')
                for f in response.get('files', []):
                    if f['mimeType'] == FOLDER:
                        # Unknown subfolders are deliberately outside the approved taxonomy.
                        if category != 'All Categories' or f['name'] in CATEGORIES[1:]:
                            parents[f['id']] = parent
                            visit(f['id'], f['name'] if category == 'All Categories' else category)
                    elif f['mimeType'] in SUPPORTED:
                        parents[f['id']] = parent
                        result.append(SourceFile(f['id'], f['name'], f['mimeType'], f.get('modifiedTime', ''), category,
                            f.get('capabilities', {}).get('canDownload', True)))
                        if len(result) > 1000:
                            raise ValueError('Knowledge folder exceeds file limit')
                token = response.get('nextPageToken')
                if not token:
                    break
                if token in tokens:
                    raise RuntimeError('Repeated Drive page token')
                tokens.add(token)
        visit(folder_id, 'All Categories')
        # Publish the allowlist only after a complete, successful inventory.
        self._permitted = {f.id: f for f in result}
        self._parents, self._root = parents, folder_id
        return result

    def read(self, file):
        if not file.downloadable:
            raise FileUnreadable('Google Drive does not permit download/export of this file')
        if file.mime == LEGACY_WORD:
            raise FileUnreadable('Legacy Word .doc is unsupported; convert to .docx or Google Docs in Drive')
        if self._permitted.get(file.id) != file:
            raise ValueError('File is outside the completed approved inventory')
        # Fail the snapshot if a file or ancestor moved out of its inventoried
        # category path before download. Never follow shortcuts or arbitrary IDs.
        current = file.id
        while True:
            metadata = self.service.files().get(fileId=current,
                fields='id,mimeType,trashed,parents,capabilities(canDownload)', supportsAllDrives=True).execute()
            expected_mime = file.mime if current == file.id else FOLDER
            if metadata.get('trashed') or metadata.get('mimeType') != expected_mime:
                raise ValueError('Approved source changed during synchronization')
            if current == file.id and not metadata.get('capabilities', {}).get('canDownload', True):
                raise FileUnreadable('Google Drive does not permit download/export of this file')
            if current == self._root:
                break
            parent = self._parents[current]
            if parent not in metadata.get('parents', []):
                raise ValueError('Approved source moved during synchronization')
            current = parent
        from googleapiclient.http import MediaIoBaseDownload
        import io
        request = (self.service.files().export_media(fileId=file.id, mimeType=DOCX) if file.mime == GDOC else self.service.files().get_media(fileId=file.id, supportsAllDrives=True))
        stream = io.BytesIO()
        downloader = MediaIoBaseDownload(stream, request, chunksize=1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk(num_retries=2)
            if stream.tell() > MAX_BYTES:
                raise ValueError('Document exceeds 25 MB limit')
        return stream.getvalue()

"""Folder-scoped read-only Google Drive adapter. Never follows shortcuts."""
import os
import re
from dataclasses import dataclass
from .taxonomy import CATEGORIES

PDF = 'application/pdf'
DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
GDOC = 'application/vnd.google-apps.document'
FOLDER = 'application/vnd.google-apps.folder'
SUPPORTED = {PDF, DOCX, GDOC}
MAX_BYTES = 25 * 1024 * 1024

@dataclass
class SourceFile:
    id: str
    name: str
    mime: str
    modified: str
    category: str = 'All Categories'

class DriveClient:
    def __init__(self, service=None):
        if service is None:
            import google.auth
            from googleapiclient.discovery import build
            import google_auth_httplib2
            import httplib2
            credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/drive.readonly'])
            from google.oauth2.service_account import Credentials as ServiceCredentials
            from google.auth.compute_engine import Credentials as AttachedCredentials
            if not isinstance(credentials, (ServiceCredentials, AttachedCredentials)):
                raise RuntimeError('Use a dedicated service account, not personal user credentials')
            # Do not use domain-wide delegation or user impersonation.
            if getattr(credentials, '_subject', None):
                raise RuntimeError('Delegated credentials are not allowed')
            service = build('drive', 'v3', http=google_auth_httplib2.AuthorizedHttp(credentials, http=httplib2.Http(timeout=30)), cache_discovery=False)
        self.service = service

    def inventory(self, folder_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', folder_id):
            raise ValueError('Invalid knowledge folder ID')
        root = self.service.files().get(fileId=folder_id, fields='id,mimeType,trashed', supportsAllDrives=True).execute()
        if root.get('trashed') or root['mimeType'] != FOLDER:
            raise ValueError('Knowledge source is not an accessible folder')
        result, seen = [], set()
        def visit(parent, category):
            if parent in seen:
                raise ValueError('Duplicate folder traversal')
            seen.add(parent)
            token = None
            while True:
                response = self.service.files().list(q=f"'{parent}' in parents and trashed = false", fields='nextPageToken,incompleteSearch,files(id,name,mimeType,modifiedTime,size)', pageToken=token, pageSize=100, supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
                if response.get('incompleteSearch'):
                    raise RuntimeError('Incomplete Drive inventory')
                for f in response.get('files', []):
                    if f['mimeType'] == FOLDER:
                        # Unknown subfolders are deliberately outside the approved taxonomy.
                        if category != 'All Categories' or f['name'] in CATEGORIES[1:]:
                            visit(f['id'], f['name'] if category == 'All Categories' else category)
                    elif f['mimeType'] in SUPPORTED:
                        result.append(SourceFile(f['id'], f['name'], f['mimeType'], f.get('modifiedTime', ''), category))
                token = response.get('nextPageToken')
                if not token:
                    break
        visit(folder_id, 'All Categories')
        return result

    def read(self, file):
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

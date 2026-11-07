"""Explicit development-only synthetic fixture adapter, never a production source."""
import os
from pathlib import Path
from .drive_client import SourceFile, PDF, DOCX, MAX_BYTES
from .taxonomy import CATEGORIES

class LocalSource:
    def __init__(self, root):
        if os.getenv('APP_ENV', 'development') != 'development':
            raise RuntimeError('Local ingestion is restricted to development')
        self.root = Path(root).resolve()
        if not (self.root / '.synthetic-only').is_file():
            raise ValueError('Synthetic fixture marker is required')
    def inventory(self, folder_id):
        files = []
        for path in sorted(self.root.rglob('*')):
            if path.is_symlink() or not path.is_file() or self.root not in path.resolve().parents:
                continue
            mime = {'.pdf':PDF, '.docx':DOCX}.get(path.suffix.lower())
            if mime:
                relative = path.relative_to(self.root)
                category = relative.parts[0] if len(relative.parts)>1 else 'All Categories'
                # Slash-containing category names use the folder name from fixture generator.
                category = category.replace('Back Office - Clinical Operations', 'Back Office / Clinical Operations')
                if category in CATEGORIES:
                    files.append(SourceFile(relative.as_posix(), path.name, mime, str(path.stat().st_mtime_ns), category))
        return files
    def read(self, file):
        path = (self.root / file.id).resolve()
        if self.root not in path.parents or path.stat().st_size > MAX_BYTES:
            raise ValueError('Invalid fixture path or size')
        return path.read_bytes()

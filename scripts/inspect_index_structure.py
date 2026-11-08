"""Authorized local structural inspection; never output source text or IDs."""
import io
import json
import re

from docx import Document as Word
from sqlalchemy import select

from backend.database import database
from backend.document_parser import parse
from backend.knowledge_models import Document, KnowledgeState, Passage
from backend.sync_service import SyncService
from backend.search_language import passage_terms


def main():
    engine, factory = database()
    try:
        with factory() as db:
            state = db.get(KnowledgeState, 1)
            docs = db.scalars(select(Document).where(Document.generation == state.active_generation).order_by(Document.id)).all()
            passages = db.scalars(select(Passage).where(Passage.generation == state.active_generation)).all()
        source = SyncService.default_source()
        inventory = {file.id: file for file in source.inventory(state.folder_id)}
        for ordinal, document in enumerate(docs, 1):
            if not document.mime_type.endswith('wordprocessingml.document'):
                continue
            data = source.read(inventory[document.file_id])
            word = Word(io.BytesIO(data))
            parsed = parse(data, document.mime_type, document.filename)
            short = [p for p in word.paragraphs if 0 < len(p.text.split()) < 6]
            missing = [p for p in short if not any(p.text.strip() in row.text or row.text in p.text
                for row in passages if row.document_id == document.id)]
            counted = []
            for i, p in enumerate(word.paragraphs):
                if len(p.text.split()) > 6 or not re.search(r'(?i)\b(?:\d+(?:st|nd|rd|th)|first|second|third)\b', p.text):
                    continue
                counted.append([dict(offset=k, words=len(other.text.split()),
                    styled_heading=bool(re.match('Heading', other.style.name)),
                    all_bold=bool(other.runs) and all(run.bold for run in other.runs if run.text.strip()),
                    searchable=any(s.text == other.text and s.searchable for s in parsed.sections))
                    for k in range(-3, 2) if 0 <= i + k < len(word.paragraphs)
                    for other in [word.paragraphs[i + k]]])
            tables = []
            event = passage_terms('missed appointment')
            for table in word.tables:
                if not any(re.search(r'(?i)\b(?:2nd|second|no[\s\-\u2010-\u2015]?shows?)\b', c.text)
                        for row in table.rows for c in row.cells):
                    continue
                tables.append([[dict(words=len(c.text.split()),
                    event_terms=len(event & passage_terms(c.text)),
                    ordinal=bool(re.search(r'(?i)\b(?:2nd|second)\b', c.text)),
                    duration=bool(re.search(r'(?i)\b\d+[\s-]*(?:weeks?|days?|months?)\b', c.text)),
                    heading_event_terms=max((len(event & passage_terms(s.heading)) for s in parsed.sections if s.text == c.text), default=0))
                    for c in row.cells] for row in table.rows])
            print(json.dumps(dict(document_ordinal=ordinal, source_matches=parsed.source == document.source_text,
                short_paragraphs=len(short), short_not_indexed=len(missing),
                missing_searchable=sum(any(s.text == p.text and s.searchable for s in parsed.sections) for p in missing),
                missing_styled_headings=sum(bool(re.match('Heading', p.style.name)) for p in missing),
                missing_bold=sum(bool(p.runs) and all(run.bold for run in p.runs if run.text.strip()) for p in missing),
                counted_label_neighborhoods=counted, policy_table_structure=tables)))
    finally:
        engine.dispose()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'error_type': type(exc).__name__}))
        raise SystemExit(1) from None

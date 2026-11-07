"""Deterministic extraction. Source text is retained unchanged; OCR is optional future work."""
from dataclasses import dataclass
from io import BytesIO
import re
import zipfile
from .drive_client import PDF, DOCX, GDOC
from .taxonomy import filename_offices, heading_offices

class Unreadable(ValueError):
    pass

@dataclass
class Section:
    text: str
    heading: str
    page: int | None
    offices: list
    searchable: bool = True
    table_cell: bool = False

@dataclass
class Parsed:
    source: str
    sections: list[Section]

def parse_pdf(data, filename):
    import pymupdf
    try:
        with pymupdf.open(stream=data, filetype='pdf') as pdf:
            if pdf.needs_pass:
                raise Unreadable('Password-protected PDF')
            sections, pages = [], []
            blocked = False
            from .document_indexer import assistant_heading
            for number, page in enumerate(pdf, 1):
                text = page.get_text(sort=False)
                if not text.strip():
                    # Do not silently index only the readable pages of a mixed scan.
                    raise Unreadable('PDF has a page without extractable text; OCR is not enabled')
                pages.append(text)
                blocks = page.get_text('dict')['blocks']
                sizes = [span['size'] for block in blocks if 'lines' in block for line in block['lines'] for span in line['spans']]
                body_size = sorted(sizes)[len(sizes)//2] if sizes else 12
                for block in blocks:
                    if 'lines' not in block:
                        continue
                    block_text = ''.join(''.join(span['text'] for span in line['spans'])+'\n' for line in block['lines'])
                    max_size = max((span['size'] for line in block['lines'] for span in line['spans']), default=body_size)
                    styled_heading = len(block_text.split()) <= 30 and max_size > body_size+1
                    if styled_heading:
                        blocked = assistant_heading(block_text)
                    elif assistant_heading(block_text) and len(block_text.split()) <= 30:
                        # Ambiguous assistant-directed headings fail closed until a styled heading.
                        blocked = True
                    sections.append(Section(block_text, '', number, filename_offices(filename), not blocked))
            if not sections:
                raise Unreadable('Empty PDF')
            return Parsed('\n'.join(pages), sections)
    except Unreadable:
        raise
    except Exception:
        raise Unreadable('PDF extraction failed') from None

def parse_docx(data, filename):
    from docx import Document
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            if sum(i.file_size for i in archive.infolist()) > 100 * 1024 * 1024:
                raise Unreadable('Word archive exceeds extraction limit')
        doc = Document(BytesIO(data))
        baseline = filename_offices(filename)
        scopes, sections, source = [], [], []
        heading = 'Document body'
        blocked = []
        from .document_indexer import assistant_heading
        for block in doc.iter_inner_content():
            if isinstance(block, Paragraph):
                text = block.text
                match = re.match(r'Heading (\d+)', block.style.name)
                outline = block._p.xpath('./w:pPr/w:outlineLvl')
                level = int(match[1]) if match else (int(outline[0].get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val'))+1 if outline else None)
                if level:
                    while scopes and scopes[-1][0] >= level:
                        scopes.pop()
                    while blocked and blocked[-1][0] >= level:
                        blocked.pop()
                    blocked.append((level, assistant_heading(text) or (blocked[-1][1] if blocked else False)))
                    scoped = heading_offices(text)
                    # Explicit headings reset the same-level scope; child headings inherit.
                    offices = scoped or (scopes[-1][1] if scopes else baseline)
                    scopes.append((level, offices))
                    heading = text or 'Document body'
                offices = scopes[-1][1] if scopes else baseline
                source.append(text)
                if text.strip():
                    sections.append(Section(text, heading, None, offices, not level and not (blocked and blocked[-1][1])))
            elif isinstance(block, Table):
                for row in block.rows:
                    for cell in row.cells:
                        text = cell.text
                        source.append(text)
                        if text.strip():
                            sections.append(Section(text, heading, None, scopes[-1][1] if scopes else baseline, not (blocked and blocked[-1][1]), True))
        if not sections:
            raise Unreadable('Word document contains no extractable text')
        return Parsed('\n'.join(source), sections)
    except Unreadable:
        raise
    except Exception:
        raise Unreadable('Word extraction failed') from None

def parse(data, mime, filename):
    if mime == PDF:
        return parse_pdf(data, filename)
    if mime in (DOCX, GDOC):
        return parse_docx(data, filename)
    raise Unreadable('Unsupported format')

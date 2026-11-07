"""Generate fictional fixtures only. No Ace policy content belongs here."""
from pathlib import Path
import argparse
import pymupdf
from docx import Document

def generate(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / '.synthetic-only').write_text('FICTIONAL DEVELOPMENT DOCUMENTS ONLY\n')
    doc = Document()
    doc.add_heading('Fictional equipment checkout', 1)
    doc.add_paragraph('Employees return borrowed telescopes to the equipment cabinet before closing.')
    doc.add_heading('Norcross Emergency Action', 1)
    doc.add_paragraph('The fictional evacuation assembly point is beside the purple observatory gate.')
    doc.add_heading('General training', 1)
    doc.add_paragraph('All employees complete telescope orientation during their first working week.')
    doc.save(root / 'Fictional Training.docx')
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72,72), 'The fictional equipment inspection occurs every Thursday before opening.')
    pdf.save(root / 'ALP NOR - Fictional Equipment.pdf')
    pdf.close()
    pdf = pymupdf.open(); pdf.new_page()
    pdf.save(root / 'Fictional Unreadable Scan.pdf'); pdf.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', nargs='?', default='backend/data/synthetic')
    generate(parser.parse_args().directory)

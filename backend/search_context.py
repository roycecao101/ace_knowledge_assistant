"""Recover bounded contiguous context from the existing verified index locally."""
from types import SimpleNamespace

from .document_indexer import verify_quote


def context_passages(rows, wanted, vocabulary, supplies_answer, deadline_ok, conditioned=lambda text, heading: False):
    """Join adjacent indexed spans only; never cross scope, heading or page.

    The exact substring between source offsets is the quotation. Missing or
    excluded source clauses and headings interrupt a window. A minimal window
    supplies topic and answer together, without joining unrelated policies just
    to improve term coverage. Original single passages still reach validation.
    """
    positioned = []
    for passage, document in rows:
        if not deadline_ok():
            return
        # Old generations do not retain offsets. An ambiguous repeated span
        # remains valid alone, but cannot establish a safe context boundary.
        start = document.source_text.find(passage.text)
        if document.source_text.find(passage.text, start + 1) >= 0:
            start = -1
        if start < 0:
            positioned.append((passage, document, -1, -1))
            continue
        end = start + len(passage.text)
        positioned.append((passage, document, start, end))

    def sufficient(text, heading):
        return (wanted.issubset(vocabulary(text + ' ' + heading)) or conditioned(text, heading)) and supplies_answer(text, heading)

    for i, (passage, document, start, end) in enumerate(positioned):
        if not deadline_ok():
            return
        yield passage, document
        if start < 0 or sufficient(passage.text, passage.heading):
            continue
        previous_end = end
        for j in range(i + 1, len(positioned)):
            following, other, next_start, next_end = positioned[j]
            if not deadline_ok():
                return
            if (other.id != document.id or following.heading != passage.heading
                    or following.offices != passage.offices or following.page != passage.page
                    or next_start < previous_end
                    or document.source_text[previous_end:next_start].strip()):
                break
            text = document.source_text[start:next_end]
            if len(text.split()) > 80:
                break
            previous_end = next_end
            # A later, narrower window will be considered at its own start.
            if any(sufficient(document.source_text[positioned[k][2]:next_end], passage.heading)
                   for k in range(i + 1, j + 1)):
                break
            if sufficient(text, passage.heading) and verify_quote(text, document.source_text):
                yield SimpleNamespace(id=passage.id, text=text, heading=passage.heading,
                    offices=passage.offices, page=passage.page), document
                break

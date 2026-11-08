import re
import unicodedata
from .knowledge_models import Passage, PassageTerm

def words(text):
    return re.findall(r"\w+(?:['’]\w+)?", unicodedata.normalize('NFKC', text).casefold())

def normalize(text):
    return ' '.join(words(text))

def spans(text):
    # Sentence spans are sliced directly from the extracted source, never rebuilt.
    for match in re.finditer(r'.+?(?:[.!?]+(?=\s|$)|$)', text, re.S):
        sentence = match.group().strip()
        if not sentence:
            continue
        tokens = list(re.finditer(r'\S+', sentence))
        for start in range(0, len(tokens), 80):
            end = min(start+80, len(tokens))
            if end-start < 6 and len(tokens)>80:
                continue
            yield sentence[tokens[start].start():tokens[end-1].end()]

def verify_quote(quote, source):
    q, s = words(quote), words(source)
    if not q or len(q) > 80 or len(quote.split()) > 80:
        return False
    # Require the complete source span as well as every six-word window.
    if quote not in source:
        return False
    if len(quote.split()) < 6:
        # A short quote must occupy a complete source line (e.g. a table cell)
        # or a whole sentence, rather than an arbitrary fragment of a policy.
        whole = any(line.strip() == quote.strip() for line in source.splitlines())
        whole = whole or any(span == quote for span in spans(source) if re.search(r'[.!?]$', span))
        if not whole:
            return False
    normalized_source = ' ' + ' '.join(s) + ' '
    return all(' ' + ' '.join(q[i:i+6]) + ' ' in normalized_source for i in range(max(1, len(q)-5)))

def index_document(db, document, parsed):
    for section in parsed.sections:
        if not section.searchable:
            continue
        for clause in safe_text(section.text):
            for quote in spans(clause):
                if len(quote.split()) < 6 and not (quote.strip() == section.text.strip() or re.search(r'[.!?]$', quote)):
                    continue
                if verify_quote(quote, parsed.source):
                    passage = Passage(generation=document.generation, document_id=document.id, text=quote,
                        normalized=normalize(quote), heading=section.heading, page=section.page, offices=section.offices)
                    db.add(passage); db.flush()
                    for token in terms(quote+' '+section.heading):
                        db.add(PassageTerm(passage_id=passage.id, term=token, generation=document.generation))

STOP = set('a an the is are was were be been being do does did can could should would will shall must may might i we you they it its our your their to of for in on at by with from and or but as if then than that this these those what which who how when where why please tell me about policy policies procedure procedures company ace office offices'.split())
def term(word):
    if len(word) > 4 and word.endswith('ies'):
        return word[:-3]+'y'
    if len(word) > 4 and word.endswith('s') and not word.endswith('ss'):
        return word[:-1]
    return word

def terms(text):
    return {term(w) for w in words(text) if w not in STOP and len(w) < 150}


def assistant_heading(text):
    return bool(re.search(r"(?i)(?<!dental )\b(?:assistant|AI|chatgpt|language model)\b.{0,100}\b(?:must|should|shall|instructions?|ignore|invent|never|do not)\b|\b(?:system prompt|instructions? (?:for|to) (?:the )?(?:assistant|AI))\b", text))

def safe_text(text):
    # The brief excludes text addressed to the assistant, not ordinary policy prose.
    # Cut a directed clause at its punctuation boundary, preserving other source spans.
    kept = []
    initial = re.split(r'(?<=[;.!?])\s+', text)
    clauses = [part for clause in initial for part in (re.split(r',\s+(?:but\s+|and\s+)?', clause) if assistant_heading(clause) else [clause])]
    for clause in clauses:
        if assistant_heading(clause) or re.search(r"(?i)ignore (?:your |all |previous )?(?:rules|instructions)|fabricate|invent (?:answers|quotes|responses)", clause):
            continue
        if re.search(r"_{2,}|\[[^\]]+\]|\{[^}]+\}|\b(?:TBD|TODO|TBC|placeholder)\b|<[^>]+>|\b(?:X{2,}|N/?A)\b", clause, re.I):
            continue
        # Questions and explicit gaps in a template are not approved answers.
        if '?' in clause or re.search(r"(?i)\b(?:not (?:yet )?(?:specified|defined|determined|provided|established)|to be (?:determined|confirmed|completed)|fill (?:in|out)|insert (?:amount|value|date|text))\b", clause):
            continue
        kept.append(clause)
    # Newlines prevent joining across removed instructions into a fabricated sentence.
    return kept

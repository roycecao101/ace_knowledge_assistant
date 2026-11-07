"""Conservative lexical retrieval. No generative model, question history, or logging."""
import re
import time
from sqlalchemy import select, func
from .knowledge_models import KnowledgeState, Document, Passage, PassageTerm
from .document_indexer import terms, verify_quote, normalize
from .taxonomy import OFFICES

NOT_FOUND = "I could not find this in Ace's approved materials."
CONFLICT = 'These approved documents disagree. Please check with your manager which one applies.'
UNAVAILABLE = 'The assistant is unavailable right now. Please check the documents directly or ask your manager.'

def unavailable():
    return {'status':'unavailable', 'message':UNAVAILABLE}

def contradictory(first, second):
    # Only assert a conflict for near-identical propositions with differing quantities
    # or polarity. Arbitrary semantic conflicts require future review/model support.
    def skeleton(text):
        text = normalize(text)
        numbers = re.findall(r'\b\d+\b', text)
        negative = bool(re.search(r'\b(?:not|never|prohibited)\b', text))
        base = re.sub(r'\b(?:not|never)\b', '', re.sub(r'\b\d+\b', '#', text))
        return ' '.join(base.split()), numbers, negative
    a, an, ap = skeleton(first)
    b, bn, bp = skeleton(second)
    return a == b and (an != bn or ap != bp)

def search(factory, question, office, category, deadline=None):
    deadline = deadline or time.monotonic()+40
    if re.search(r'(?i)\b(?:your|system) (?:instructions|prompt)|\b(?:invent|create|write|make up)\b.{0,30}\bpolicy\b', question):
        return {'status':'not_found', 'message':NOT_FOUND}
    wanted = terms(question) - {o.casefold() for o in OFFICES}
    if not wanted or len(wanted)>25:
        return {'status':'not_found', 'message':NOT_FOUND}
    with factory() as db:
        state = db.get(KnowledgeState, 1)
        if not state or not state.active_generation:
            return unavailable()
        # Inverted term index requires every substantive query term. Conservative
        # matching may abstain on paraphrases; it cannot invent missing policy facts.
        active = select(KnowledgeState.active_generation).where(KnowledgeState.id==1).scalar_subquery()
        candidates = select(PassageTerm.passage_id).where(PassageTerm.generation==active,
            PassageTerm.term.in_(wanted)).group_by(PassageTerm.passage_id).having(func.count()==len(wanted))
        query = select(Passage, Document).join(Document, Passage.document_id==Document.id).where(
            Passage.id.in_(candidates), Passage.generation==active)
        if category != 'All Categories':
            query = query.where(Document.category.in_([category, 'All Categories']))
        results = []
        for passage, document in db.execute(query.order_by(Passage.id).limit(500)):
            if time.monotonic()>deadline:
                return unavailable()
            if passage.offices and office not in passage.offices:
                continue
            if re.search(r'(?i)\bhow (?:much|many)\b|\b(?:amount|number)\b', question) and not re.search(r'\d|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|no|none)\b', passage.text, re.I):
                continue
            if not verify_quote(passage.text, document.source_text):
                continue
            results.append(dict(quote=passage.text, filename=document.filename, heading=passage.heading,
                page=passage.page, office=(' and '.join(passage.offices)+' only') if passage.offices else 'Company-wide'))
        for i, first in enumerate(results):
            for second in results[i+1:]:
                if contradictory(first['quote'], second['quote']):
                    return {'status':'conflict', 'message':CONFLICT, 'results':[first, second]}
        if not results:
            return {'status':'not_found', 'message':NOT_FOUND}
        return {'status':'found', 'results':results[:5]}

"""Conservative lexical retrieval. No generative model, history, or logging."""
import re
import time
import hashlib
from pathlib import Path
from sqlalchemy import select, or_
from .knowledge_models import KnowledgeState, Document, Passage, PassageTerm
from .document_indexer import term, verify_quote, normalize
from .search_language import (query_text, question_terms, root, roots, prefixes as word_prefixes,
                              passage_terms, office_entry_matches)
from .search_context import context_passages
from .timing_policy import timing_fact, timing_conflict

NOT_FOUND = "I could not find this in Ace's approved materials."
CONFLICT = 'These approved passages disagree. Please check with your manager which one applies.'
UNAVAILABLE = 'The assistant is unavailable right now. Please check the documents directly or ask your manager.'
DAYS = 'monday tuesday wednesday thursday friday saturday sunday'.split()
NUMBERS = dict(zip('zero one two three four five six seven eight nine ten eleven twelve'.split(), map(str, range(13))))
TIME = r'\b(?:' + '|'.join(DAYS) + r'|daily|weekly|monthly|annually|morning|afternoon|evening|noon|midnight|before|after|during|until|within|immediately|first|last|every|each|hours?|minutes?|days?|weeks?|months?|years?|january|february|march|april|may|june|july|august|september|october|november|december)\b|\b\d{1,2}:\d{2}\b'
# Captured at import, so a live response identifies the loaded search source,
# rather than whichever file happens to be on disk when a request arrives.
REVISION = hashlib.sha256(b''.join(Path(__file__).with_name(name).read_bytes() for name in (
    'search.py', 'search_language.py', 'search_context.py', 'timing_policy.py',
    'document_indexer.py', 'document_parser.py', 'taxonomy.py'))).hexdigest()[:16]


def unavailable():
    return {'status': 'unavailable', 'message': UNAVAILABLE}


def not_found():
    return {'status': 'not_found', 'message': NOT_FOUND}


def answers(question, text, heading=''):
    """Reject common topical matches which do not supply the requested fact.

    These deterministic checks deliberately abstain on unsupported phrasing;
    they are not a general semantic entailment engine.
    """
    q = normalize(query_text(question))
    t = normalize(text)
    if not office_entry_matches(query_text(question), text):
        return False
    if re.search(r'(?i)\bhow far out\b', question) and not re.search(
            r'\b(?:\d+(?:\s*[-–—]\s*\d+)?|' + '|'.join(NUMBERS) + r')[\s-]+(?:hours?|days?|weeks?|months?|years?)\b', text, re.I):
        return False
    if re.match(r'(?i)^\s*after\b[^,]+,', query_text(question)) and re.search(r'\bbefore\b', t):
        return False
    topic = question_terms(question) - {
        'much', 'many', 'often', 'amount', 'number', 'time', 'day', 'date', 'occur', 'happen',
        'handle', 'receive', 'get', 'have', 'take', 'need', 'start', 'end', 'located', 'recorded',
        'kept', 'stored', 'pay', 'cost', 'schedule'}
    # A heading may provide context for a short direct value, but must not turn
    # an unrelated sentence underneath it into policy evidence for this topic.
    body_topic = roots(topic) & passage_terms(text)
    if topic and not body_topic:
        direct = bool(re.fullmatch(r'\s*[$€£]?\d+(?:[.,]\d+)*(?:\s+(?:dollars?|days?|hours?|minutes?|weeks?|months?|years?))?[.!]?\s*', text, re.I))
        direct = direct or bool(re.fullmatch(r'\s*(?:every |each )?(?:' + '|'.join(DAYS) + r'|daily|weekly|monthly)[.!]?\s*', text, re.I))
        if not direct or not roots(topic).issubset(passage_terms(heading)):
            return False
    if '?' in text or re.search(r'\b(?:discuss|discusses|discussed|discussing|mention|mentions|mentioned)\b', t):
        return False
    # A source instruction to contact someone is itself valid procedural
    # evidence. Fact-specific checks below still require the requested value.
    if re.search(r'\b(?:how (?:much|many)|amount|number)\b', q):
        # Units/amount evidence must appear in the quote, not only its heading.
        if not re.search(r'\d|\b(?:' + '|'.join(NUMBERS) + r'|none)\b', t):
            return False
    if re.search(r'\b(?:when|how often|what (?:time|day|date))\b', q):
        if not re.search(TIME, text, re.I):
            return False
        # "Every employee ..." is not a schedule.
        if not re.search(TIME.replace('|every|each', ''), text, re.I) and not re.search(r'\b(?:every|each)\s+\d', t):
            return False
    if re.search(r'\bwhere\b', q) and not re.search(r'\b(?:at|in|inside|outside|beside|behind|near|under|above|below|next to|located|stored|kept|portal|website)\b', t):
        return False
    if re.search(r'\b(?:who|whom)\b', q) and not re.search(r'\b(?:manager|supervisor|coordinator|administrator|director|employee|staff|assistant|team|officer|lead|receptionist|dentist)\b', t):
        return False
    return True


def contradictory(first, second, first_heading='', second_heading=''):
    # Compare the same proposition and conditions with different values or
    # polarity. Different wording/conditions must not create a false conflict.
    # A terse table value depends on its labels. Different labels cannot be
    # discarded to make two values look like the same unconditional rule.
    if (min(len(first.split()), len(second.split())) < 6
            and passage_terms(first_heading) != passage_terms(second_heading)):
        return False
    def skeleton(text):
        text = normalize(text)
        for word, value in NUMBERS.items():
            text = re.sub(r'\b' + word + r'\b', value, text)
        text = re.sub(r'\b(?:must|shall|should)\b', 'must', text)
        text = re.sub(r'\b(?:prohibited|forbidden|disallowed)\b', 'not allowed', text)
        text = re.sub(r'\bpermitted\b', 'allowed', text)
        negative = bool(re.search(r'\b(?:not|never|cannot)\b|\b\w+[’\']t\b', text))
        text = re.sub(r'\bcannot\b', 'can not', text)
        text = re.sub(r'\b(can|must|should)n[’\']t\b', r'\1 not', text)
        text = re.sub(r'\b(?:not|never)\b', '', text)
        values = re.findall(r'\b\d+(?: \d+)?\b|\b(?:' + '|'.join(DAYS) + r')\b', text)
        base = re.sub(r'\b\d+(?: \d+)?\b|\b(?:' + '|'.join(DAYS) + r')\b', '#', text)
        return ' '.join(root(term(word)) for word in base.split()), values, negative
    a, av, ap = skeleton(first)
    b, bv, bp = skeleton(second)
    return a == b and (av != bv or ap != bp)


def search(factory, question, office, category, deadline=None, diagnostics=None):
    # Optional, in-memory stage counts only. Never retain source/query values,
    # account/session identifiers, query hashes, or timing fingerprints.
    counts = dict(retrieved=0, office_rejected=0, topic_rejected=0,
                  evidence_rejected=0, quote_rejected=0, accepted=0)
    if diagnostics is not None:
        diagnostics.update(counts)
        counts = diagnostics
    deadline = deadline if deadline is not None else time.monotonic() + 40
    if time.monotonic() > deadline:
        return unavailable()
    if re.search(r'(?i)\b(?:your|system) (?:instructions|prompt)|\b(?:invent|create|write|make up)\b.{0,30}\bpolicy\b', question):
        return not_found()
    wanted = roots(question_terms(question))
    if not wanted or len(wanted) > 25:
        return not_found()
    with factory() as db:
        state = db.get(KnowledgeState, 1)
        if not state or not state.active_generation:
            return unavailable()
        # Resolve the generation in the retrieval statement itself, so an atomic
        # publication between the state read and retrieval cannot mix snapshots.
        active = select(KnowledgeState.active_generation).where(KnowledgeState.id == 1).scalar_subquery()
        # Root prefixes include the original persisted spelling and its common
        # inflections. The exact root check below discards prefix lookalikes.
        # Keep this in ONE retrieval statement: publication may replace/delete
        # a generation between SQL statements during concurrent synchronization.
        prefixes = [or_(*(PassageTerm.term.startswith(variant, autoescape=True)
                         for variant in word_prefixes(value)))
                    for value in sorted(wanted)]
        candidates = select(Passage.document_id).join(PassageTerm,
            PassageTerm.passage_id == Passage.id).where(Passage.generation == active,
            PassageTerm.generation == active, or_(*prefixes))
        query = select(Passage, Document).join(Document, Passage.document_id == Document.id).where(
            Passage.document_id.in_(candidates), Passage.generation == active, Document.generation == active)
        if category != 'All Categories':
            query = query.where(Document.category.in_([category, 'All Categories']))
        results = []
        # Never silently truncate candidates and miss a contradiction.
        rows = db.execute(query.order_by(Passage.id).limit(2001)).all()
        if len(rows) > 2000:
            return unavailable()
        for passage, document in context_passages(rows, wanted, passage_terms,
                lambda text, heading: answers(question, text, heading),
                lambda: time.monotonic() <= deadline,
                lambda text, heading: timing_fact(question, text, heading) is not None):
            if time.monotonic() > deadline:
                return unavailable()
            conditioned = timing_fact(question, passage.text, passage.heading) is not None
            if not wanted.issubset(passage_terms(passage.text + ' ' + passage.heading)) and not conditioned:
                continue
            counts['retrieved'] += 1
            if passage.offices and office not in passage.offices:
                counts['office_rejected'] += 1
                continue
            body_terms = passage_terms(passage.text)
            # Retrieval accepts word variants and ignores request scaffolding,
            # but must still cover the entire topic. Mere partial overlap must
            # not manufacture support for an absent qualifier or policy.
            if not wanted.issubset(body_terms | passage_terms(passage.heading)) and not conditioned:
                counts['topic_rejected'] += 1
                continue
            if not answers(question, passage.text, passage.heading):
                counts['evidence_rejected'] += 1
                continue
            if not verify_quote(passage.text, document.source_text):
                counts['quote_rejected'] += 1
                continue
            counts['accepted'] += 1
            result = dict(quote=passage.text, filename=document.filename, file_id=document.file_id,
                heading=passage.heading, page=passage.page,
                office=(' and '.join(passage.offices) + ' only') if passage.offices else 'Company-wide')
            for _, previous in results:
                if time.monotonic() > deadline:
                    return unavailable()
                if (contradictory(previous['quote'], result['quote'], previous['heading'], result['heading'])
                        or timing_conflict(question, previous['quote'], result['quote'], previous['heading'], result['heading'])):
                    return {'status': 'conflict', 'message': CONFLICT, 'results': [previous, result]}
            # Prefer evidence in the quotation over heading-only context, then
            # focused passages. IDs are only a deterministic tie-breaker.
            rank = (-len(wanted & body_terms), len(body_terms), passage.id)
            results.append((rank, result))
        if time.monotonic() > deadline:
            return unavailable()
        results.sort(key=lambda item: item[0])
        # Give each eligible source a display slot before taking more quotes
        # from one document. Conflicts were checked across ALL accepted rows.
        # Neither filename nor MIME type contributes to the ranking.
        diverse, remaining, seen = [], [], set()
        for _, result in results:
            if result['file_id'] not in seen:
                diverse.append(result)
                seen.add(result['file_id'])
            else:
                remaining.append(result)
        return {'status': 'found', 'results': (diverse + remaining)[:5]} if results else not_found()

"""Local, bounded comparison of durations after a counted event.

This recognizes a narrow grammatical policy form, not arbitrary entailment.
Event qualifiers stay mandatory. The returned facts are never persisted.
"""
import re

from .document_indexer import words, term
from .search_language import lexical_text, passage_terms, root

CARDINAL = dict(zip('one two three four five six seven eight nine ten eleven twelve'.split(), range(1, 13)))
ORDINAL = dict(zip('first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth'.split(), range(1, 13)))


def number(word):
    if word in CARDINAL or word in ORDINAL:
        return CARDINAL.get(word, ORDINAL.get(word))
    match = re.fullmatch(r'(\d+)(?:st|nd|rd|th)?', word)
    return int(match[1]) if match else None


def request_condition(question):
    match = re.match(r"(?i)^\s*after\s+(?:(?:a|an|the)\s+)?(?:(\w+)[’']s\s+)?(?:the\s+)?"
        r'(\w+)\s+([^,?]+),\s*(?:how far out|when|how long)\b(.*)', question)
    if not match or match[2].casefold() not in ORDINAL and not re.fullmatch(r'\d+(?:st|nd|rd|th)', match[2], re.I):
        return None
    actions = {root(w) for w in ('schedule', 'reschedule', 'book', 'rebook', 'wait', 'return')}
    action_terms = passage_terms(match[4])
    if not action_terms & actions or action_terms - actions - {'them', 'us'}:
        return None
    event = passage_terms(match[3])
    if not event or len(event) > 8:
        return None
    return number(match[2].casefold()), event, root(match[1].casefold()) if match[1] else None


def timing_fact(question, text, heading=''):
    condition = request_condition(question)
    if condition is None:
        return None
    occurrence, event, actor = condition
    # An unqualified event rule can apply to the question's generic possessor.
    # An explicitly different possessor cannot supply that evidence.
    possessors = {root(value) for value in re.findall(r"(?i)\b(\w+)[’']s\b", text + ' ' + heading)}
    if actor and possessors and actor not in possessors:
        return None
    if re.search(r'(?i)\bbefore\b', text):
        return None
    tokens = words(lexical_text(heading + '\n' + text))
    heading_event = event & passage_terms(heading)
    found = set()
    for i, token in enumerate(tokens):
        count = number(token)
        if count is None:
            continue
        for end in range(i + 2, min(i + 11, len(tokens) + 1)):
            following = tokens[i + 1:end]
            if set(following) & {'hour', 'hours', 'day', 'days', 'week', 'weeks', 'month', 'months', 'year', 'years'}:
                break
            following_event = {root(term(w)) for w in following}
            # An ordinal row label can inherit the event name from its table
            # header. Cardinal durations cannot become occurrence counts.
            inherited = heading_event if token in ORDINAL or re.fullmatch(r'\d+(?:st|nd|rd|th)', token) else set()
            if event.issubset(following_event | inherited):
                found.add(count)
                break
    if found != {occurrence}:
        return None
    if not passage_terms(text) & {root(w) for w in ('schedule', 'reschedule', 'book', 'rebook', 'wait', 'delay', 'postpone', 'next', 'out', 'push', 'move', 'return')}:
        return None
    numeric = text.casefold()
    for word, value in CARDINAL.items():
        numeric = re.sub(r'\b' + word + r'\b', str(value), numeric)
    durations = set()
    for match in re.finditer(r'\b(\d+)(?:\s*[-–—]\s*(\d+))?[\s-]*(business |working |calendar )?(hours?|days?|weeks?|months?|years?)\b', numeric):
        low, high = int(match[1]), int(match[2] or match[1])
        unit = match[4].rstrip('s')
        kind = (match[3] or '').strip()
        # Preserve business/calendar distinctions; compare only equal units.
        durations.add((low, high, unit, kind))
    if len(durations) != 1:
        return None
    duration = durations.pop()
    bounded = bool(re.search(r'(?i)\b(?:at least|at most|within|minimum|maximum|up to|no sooner|no later)\b', text))
    return occurrence, frozenset(event), duration, bounded


def timing_conflict(question, first, second, first_heading='', second_heading=''):
    a, b = timing_fact(question, first, first_heading), timing_fact(question, second, second_heading)
    if not a or not b or a[:2] != b[:2] or a[3] or b[3]:
        return False
    low_a, high_a, unit_a, kind_a = a[2]
    low_b, high_b, unit_b, kind_b = b[2]
    return (unit_a, kind_a) == (unit_b, kind_b) and (high_a < low_b or high_b < low_a)

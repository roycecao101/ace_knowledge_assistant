"""Deterministic query vocabulary; no source text, models, or remote services.

Equivalences describe language, never policies or answers. Keep conditions,
negation, actors and opposing actions distinct. Unknown words remain mandatory.
"""
import re

from .document_indexer import terms
from .taxonomy import OFFICES, CODES


def stem(value):
    value = re.sub(r"[’']s$", '', value)
    value = value.rstrip("'’")
    value = re.sub(r'(?<=\w{3})(?:ation|ion|ing|ed|ment)$', '', value)
    if len(value) > 4 and value.endswith('e'):
        value = value[:-1]
    # Silent-e verbs: calibrate/calibrating/calibration, operate/operation.
    if len(value) > 5 and value.endswith('at'):
        value = value[:-2]
    if len(value) > 4 and value[-2:] in {'nn', 'tt', 'pp'}:
        value = value[:-1]
    return value


# No roles or leave types are merged: a supervisor need not be a manager,
# and sick, unpaid and annual leave have different eligibility conditions.
FAMILIES = (
    ('start', 'begin', 'began', 'begun', 'commence'),
    ('finish', 'end', 'conclude'),
    ('employee', 'staff', 'personnel'),
    ('buy', 'bought', 'purchase'),
    ('notify', 'notified', 'notification', 'inform'),
    ('allow', 'permit', 'permission'),
    ('prohibit', 'forbid', 'forbidden', 'ban'),
    ('require', 'mandatory', 'compulsory'),
    ('reimburse', 'reimbursement', 'repay', 'repayment'),
    ('late', 'tardy', 'tardiness'),
    ('absent', 'absence'),
)
ALIASES = {stem(word): stem(family[0]) for family in FAMILIES for word in family}


def root(value):
    value = stem(value)
    return ALIASES.get(value, value)


def roots(values):
    return {root(value) for value in values}


def prefixes(value):
    # Existing persisted terms retain their original spelling. Prefix retrieval
    # is only an overinclusive candidate operation; root equality is mandatory.
    variants = {value} | {alias for alias, canonical in ALIASES.items() if canonical == value}
    if value == root('leave'):
        variants.add('time')  # persisted "time off"; checked as a phrase later
    if value == root('missed'):
        variants.add('no')
    if value == root('appointment'):
        variants.update({'appt', 'show'})
    for spelling, written in [('1st', 'first'), ('2nd', 'second'), ('3rd', 'third')]:
        if value == root(written):
            variants.add(spelling)
    return sorted(variants)


def query_text(question):
    # Remove request framing as phrases before tokenization. Do not discard
    # arbitrary unmatched terms to force a result, or remove policy qualifiers.
    question = re.sub(r"(?i)\b(what|where|when|who)[’']s\b", r'\1 is', question)
    question = re.sub(r"(?i)\b(?:i(?:[’']d| would) like to know|i want to know|i(?:[’']m| am| was) wondering|help me understand)\b", '', question)
    question = re.sub(r"(?i)\b(?:i(?:'m| am)|we(?:'re| are)) supposed to\b", '', question)
    question = re.sub(r'(?i)\b(?:am i|are we) supposed to\b', '', question)
    question = re.sub(r'(?i)\b(?:could|can|would) you (?:please )?(?:explain|show|tell)(?: me| us)?\b', '', question)
    question = re.sub(r'(?i)\b(?:please )?(?:explain|describe|show)(?: me| us)?\b', '', question)
    question = re.sub(r'(?i)\b(?:find out|steps (?:for|to)|process for|rules for|guidelines for|way to|go about)\b', '', question)
    question = re.sub(r'(?i)\btime[ -]+off\b', 'leave', question)
    question = re.sub(r'(?i)\bhow far out\b', 'when', question)
    return question


def lexical_text(text):
    """Common written forms, applied equally to queries and source evidence."""
    text = re.sub(r'(?i)\bno[\s\-\u2010-\u2015]?shows?\b', 'missed appointment', text)
    text = re.sub(r'(?i)\bappts?\b', 'appointment', text)
    for ordinal, name in [('1st', 'first'), ('2nd', 'second'), ('3rd', 'third')]:
        text = re.sub(r'(?i)\b' + ordinal + r'\b', name, text)
    return text


def question_terms(question):
    question = query_text(question)
    # Event labels ("Third failed inspection: ...") express the condition
    # without an explicit "after". Keep every word describing that event.
    if re.match(r'(?i)^\s*after\b[^,]+,\s*(?:when|how|what)\b', question):
        question = re.sub(r'(?i)^\s*after\b', '', question)
    wanted = terms(lexical_text(question)) - {o.casefold() for o in OFFICES} - {c.casefold() for c in CODES} - {
        'much', 'many', 'often', 'know', 'need', 'get', 'have', 'occur', 'happen',
        'handle', 'receive', 'take', 'located', 'recorded', 'kept', 'stored', 'them'}
    if re.search(r'(?i)\bwhat (?:time|day|date)\b', question):
        wanted -= {'time', 'day', 'date'}
    return wanted


def passage_terms(text):
    return roots(terms(lexical_text(re.sub(r'(?i)\btime[ -]+off\b', 'leave', text))))

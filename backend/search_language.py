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
    ('buy', 'bought', 'purchase', 'procure', 'procurement'),
    ('notify', 'notified', 'notification', 'inform'),
    ('allow', 'permit', 'permission'),
    ('prohibit', 'forbid', 'forbidden', 'ban'),
    ('require', 'mandatory', 'compulsory'),
    ('reimburse', 'reimbursement', 'repay', 'repayment'),
    ('late', 'tardy', 'tardiness'),
    ('absent', 'absence'),
)
ALIASES = {stem(word): stem(family[0]) for family in FAMILIES for word in family}


# Phrase equivalences are symmetric. These are language relationships, not
# corpus-derived expansions. Candidate lookup also includes their persisted
# spellings, so existing generations need no rebuild.
PHRASES = (
    ('contact', ('reach out to', 'get in touch with')),
    ('return', ('give back', 'gives back', 'giving back', 'gave back', 'hand back')),
    ('late', ('running late',)),
)


# Bringing an object into an office is a permission question about its presence.
# Keep this relation narrow: purchasing, using, storing, and other actions are
# not equivalent. Objects/qualifiers stay mandatory; no document-specific nouns.
_OFFICE = r'(?:(?:the|an?|either|any|our|your|both|all)\s+)?offices?'
_WORKPLACE = rf'(?:{_OFFICE}|work|(?:(?:the|our|your)\s+)?workplace)'
_ENTRY_QUESTIONS = [re.compile(
    rf'{prefix}\s+([^.!?;\n]+?)\s+(?:to|into|in)\s+{_WORKPLACE}', re.I)
    for prefix in (
        r'(?:can|may|could)\s+(?:I|we|employees|staff)\s+(?:bring|take)',
        r'(?:I|we|employees|staff)\s+(?:can|may|could)\s+(?:bring|take)',
        r'(?:am I|are we|are employees|are staff)\s+(?:allowed|permitted)\s+to\s+(?:bring|take)',
        r'(?:is it|would it be)\s+(?:OK|okay|allowed|permitted)\s+(?:(?:for me|for us|for employees)\s+)?to\s+(?:bring|take)',
        r'(?:bringing|taking|bring|take)',
    )]
_ENTRY_QUESTIONS.append(re.compile(
    rf'(?:is|are)\s+([^.!?;\n]+?)\s+(?:allowed|permitted|prohibited|forbidden|banned)'
    rf'(?:\s+(?:in|inside|within|at)\s+{_WORKPLACE})?', re.I))
_ENTRY_RULES = [re.compile(pattern, re.I) for pattern in (
    rf'(?:^|(?<=[.!?\n]))\s*([^.!?\n]+?)\s+(?:is|are)\s+(?:(?:not|never)\s+)?(?:allowed|permitted|prohibited|forbidden|banned)(?:\s+(?:in|inside|within|at)\s+{_WORKPLACE})?(?=[.!?;\n]|$)',
    rf'(?:^|(?<=[.!?\n]))\s*(?:employees|staff)\s+(?:may(?: not)?|can(?: not)?|cannot|must not|are (?:not )?(?:allowed|permitted) to)\s+(?:bring|take)\s+([^.!?\n]+?)\s+(?:to|into|in)\s+{_WORKPLACE}(?=[.!?;\n]|$)',
)]


def office_entry_subject(question, *, keep_role=False):
    question = question.strip().rstrip('?.!').strip()
    # "Tell me if I can ..." is request framing; an arbitrary conditional
    # clause or a trailing exception must never be removed to make it match.
    question = re.sub(r'(?i)^(?:whether|if)\s+', '', question)
    for pattern in _ENTRY_QUESTIONS:
        match = pattern.fullmatch(question)
        if match:
            subject = re.sub(r'(?i)^(?:(?:a|an|the|my|our|your)\s+)+', '', match[1])
            # "Pet X" still asks about X's presence. Only this attributive
            # role is optional, never a standalone "pet" or an unknown modifier
            # such as "injured". This does not assert what species are pets.
            if not keep_role:
                subject = re.sub(r'(?i)^pet\s+(?=\w)', '', subject)
            return subject if terms(subject) else None
    return None


def office_entry_subjects(text):
    return [match[1] for pattern in _ENTRY_RULES for match in pattern.finditer(text)]


def office_entry_matches(question, text):
    """Require the object of a presence rule, not an incidental noun match.

    A rule about an object's accessories, transport or pictures does not supply
    permission for the object. A blanket rule for X can answer "pet X"; a rule
    specifically for pet X cannot be generalized to all X.
    """
    subject = office_entry_subject(question, keep_role=True)
    if subject is None:
        return True
    variants = [roots(terms(lexical_text(subject)))]
    if re.match(r'(?i)^pet\s+\w', subject):
        variants.append(roots(terms(lexical_text(re.sub(r'(?i)^pet\s+', '', subject)))))
    return any(roots(terms(lexical_text(source))) in variants
               for source in office_entry_subjects(text))


def root(value):
    value = stem(value)
    return ALIASES.get(value, value)


def roots(values):
    return {root(value) for value in values}


def prefixes(value):
    # Existing persisted terms retain their original spelling. Prefix retrieval
    # is only an overinclusive candidate operation; root equality is mandatory.
    variants = {value} | {alias for alias, canonical in ALIASES.items() if canonical == value}
    for canonical, phrases in PHRASES:
        if value == root(canonical):
            # One content anchor per written phrase is enough to retrieve its
            # document. Avoid broad prefixes such as "get" and "out"; the
            # complete phrase is still checked during evidence validation.
            variants.update(max(terms(phrase), key=lambda word: (len(word), word))
                            for phrase in phrases)
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
    question = re.sub(r"(?i)\b(?:i(?:[’']d| would) like to know|i want to know|i(?:[’']m| am) trying to find out|i(?:[’']m| am| was) wondering|help me understand)\b", '', question)
    question = re.sub(r"(?i)\b(?:i(?:'m| am)|we(?:'re| are)) supposed to\b", '', question)
    question = re.sub(r'(?i)\b(?:am i|are we) supposed to\b', '', question)
    question = re.sub(r'(?i)\b(?:could|can|would) you (?:please )?(?:explain|show|tell)(?: me| us)?\b', '', question)
    question = re.sub(r'(?i)\b(?:please )?(?:explain|describe|show)(?: me| us)?\b', '', question)
    # Remove only a complete request frame. Brand possessives and ordinary
    # "policy on/regarding" wording must not become mandatory subject words.
    question = re.sub(r"(?i)^\s*what\s+(?:is|are)\s+(?:(?:the|our|company|Ace[’']s)\s+)*(?:policy|policies|rules|guidelines)\s+(?:on|about|regarding|for)\s+", '', question)
    question = re.sub(r'(?i)\b(?:find out|steps (?:for|to)|process for|rules for|guidelines for|way to|go about)\b', '', question)
    question = re.sub(r'(?i)\btime[ -]+off\b', 'leave', question)
    question = re.sub(r'(?i)\bhow far out\b', 'when', question)
    return question


def lexical_text(text):
    """Common written forms, applied equally to queries and source evidence."""
    text = re.sub(r"(?i)\b(\w+)[’']s\b", r'\1', text)
    for canonical, phrases in PHRASES:
        for phrase in phrases:
            text = re.sub(r'(?i)\b' + re.escape(phrase) + r'\b', canonical, text)
    text = re.sub(r'(?i)\bno[\s\-\u2010-\u2015]?shows?\b', 'missed appointment', text)
    text = re.sub(r'(?i)\bappts?\b', 'appointment', text)
    for ordinal, name in [('1st', 'first'), ('2nd', 'second'), ('3rd', 'third')]:
        text = re.sub(r'(?i)\b' + ordinal + r'\b', name, text)
    return text


def question_terms(question):
    question = query_text(question)
    entry = office_entry_subject(question)
    if entry is not None:
        question = entry + ' allowed'
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
    values = roots(terms(lexical_text(re.sub(r'(?i)\btime[ -]+off\b', 'leave', text))))
    if office_entry_subjects(text):
        # A prohibition also answers a yes/no permission question. Preserve its
        # negation in the exact quotation and in contradiction comparison.
        values.add(root('allow'))
    return values

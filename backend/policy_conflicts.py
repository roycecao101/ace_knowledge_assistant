"""Conservative local proposition matching; no models, prompts, or corpus rules.

Preserve word order, units, actors and conditions. Match a changed value or
negation only in otherwise equivalent statements. This deliberately abstains
on paraphrases, overlapping ranges and bounds rather than asserting entailment.
"""
import re
import unicodedata
from decimal import Decimal
from .document_indexer import term
from .search_language import root, passage_terms

DAYS = set('monday tuesday wednesday thursday friday saturday sunday'.split())
FREQUENCIES = set('daily weekly monthly quarterly annually'.split())
NUMBERS = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split(), map(str, range(21))))
BOUNDS = re.compile(r'\b(?:at least|at most|within|minimum|maximum|up to|no sooner|no later|between|more than|less than|about|approximately|roughly)\b|\d\s*[-–—]\s*\d|\b\d+(?:\.\d+)?\s+(?:to|through|or)\s+\d+', re.I)


def value_key(token):
    if not token[0].isdigit():
        return token
    if ':' in token:
        return ':'.join(str(int(part)) for part in token.split(':'))
    percent = token.endswith('%')
    numeric = token.rstrip('%')
    if ',' in numeric:
        # Only unambiguous thousands grouping; other locale formats abstain.
        if not re.fullmatch(r'\d{1,3}(?:,\d{3})+(?:\.\d+)?', numeric):
            return None
        numeric = numeric.replace(',', '')
    return str(Decimal(numeric).normalize()) + ('%' if percent else '')


def signature(text, heading=''):
    text = unicodedata.normalize('NFKC', text).casefold()
    # Avoid treating a conditional value as the policy's output value.
    # Punctuation is retained until these clause boundaries have been read.
    text = re.sub(r"\b(can|must|should)n[’']t\b", r'\1 not', text)
    text = re.sub(r'\bcannot\b', 'can not', text)
    text = re.sub(r'\b(?:prohibited|forbidden|disallowed|banned)\b', 'not allowed', text)
    text = re.sub(r'\bpermitted\b', 'allowed', text)
    text = re.sub(r'\b(?:shall|should)\b', 'must', text)
    text = re.sub(r'\bmay\b(?!\s+\d)', 'can', text)
    text = re.sub(r'\byearly\b', 'annually', text)
    for word, number in NUMBERS.items():
        text = re.sub(r'\b' + word + r'\b', number, text)
    bounded = bool(BOUNDS.search(text))
    tokens = re.findall(r"[$€£]|\d+(?:[.,:]\d+)*(?:st|nd|rd|th|%)?|\w+(?:['’]\w+)?|[,;:.!?]", text)
    # A leading row/event label is a condition, including cardinal counts.
    conditional = ':' in tokens or bool(re.match(r'^\s*(?:\d+|' + '|'.join(NUMBERS) + r')\b[^,]+,', text))
    base, values, negatives = [], [], 0
    for token in tokens:
        if token in ',;:.!?':
            # An initial 'if/after/when ...,' clause ends here.
            conditional = False
            continue
        if token in {'if', 'unless', 'when', 'after', 'before', 'except', 'until'}:
            conditional = True
        if token in {'not', 'never'} and not conditional:
            negatives += 1
            continue
        token = NUMBERS.get(token, token)
        if not conditional and (re.fullmatch(r'\d+(?:[.,:]\d+)*%?', token) or token in DAYS | FREQUENCIES):
            base.append('#')
            value = value_key(token)
            if value is None:
                return None
            values.append(value)
        else:
            base.append(root(term(token)))
    # Short table cells need all of their context. Longer sentences still keep
    # heading qualifiers that are not expressed in the body (e.g. worker type).
    context = passage_terms(heading) - passage_terms('Document body')
    if len(text.split()) >= 6:
        context -= passage_terms(text)
    anchors = (passage_terms(text) | context) - passage_terms(' '.join(values)) - {'not', 'never'}
    if len(anchors) < 2 or negatives > 1 or not (values or negatives or re.search(r'\b(?:must|can|allowed|required)\b', text)):
        return None
    return (tuple(base), frozenset(context)), tuple(values), bool(negatives), bounded


def supported_difference(a, b):
    if not a or not b or a[0] != b[0]:
        return False
    if a[2] != b[2]:
        return a[1] == b[1]
    if a[3] or b[3] or len(a[1]) != len(b[1]):
        return False
    return sum(x != y for x, y in zip(a[1], b[1])) == 1


def potential_conflict(first, second, first_heading='', second_heading=''):
    return supported_difference(signature(first, first_heading), signature(second, second_heading))

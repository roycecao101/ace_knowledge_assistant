"""Administrator-only, conservative issue keys. No source leaves this process.

Employee retrieval deliberately keeps its existing matcher. Issue identity is
the ordered policy proposition plus the disputed field, never the filenames,
passage IDs, disputed values, or synchronization generation.
"""
import hashlib
import json
import re
import unicodedata

from .policy_conflicts import DAYS, FREQUENCIES, NUMBERS, signature, supported_difference
from .document_indexer import words, term
from .search_language import root, FAMILIES

VALUE_WORDS = '|'.join(sorted(set(NUMBERS) | DAYS | FREQUENCIES))
EQUIVALENT_WORDS = {word: family[0] for family in FAMILIES for word in family}


def review_signature(text, heading=''):
    normalized = unicodedata.normalize('NFKC', text).casefold()
    normalized = re.sub(r"\bcan[’']t\b", 'can not', normalized)
    normalized = re.sub(r"\b(must|should)n[’']t\b", r'\1 not', normalized)
    # Alternatives, examples and descriptive history do not establish opposing
    # requirements. Abstain rather than infer their intended applicability.
    if re.search(r'\b(?:or|either|alternatively|formerly|previously|historical|example|observed|reported)\b|\b(?:used to|last year)\b', normalized + ' ' + heading.casefold()):
        return None
    if not re.search(r'\b(?:must|shall|should|required|allowed|permitted|prohibited|forbidden|banned|cannot|can|may|receive|receives|entitled|fee|deadline|occurs|every|daily|weekly|monthly|quarterly|annually)\b', normalized):
        # A short table cell needs an explicit policy/schedule heading.
        if len(normalized.split()) >= 6 or not re.search(r'\b(?:policy|schedule|inspection|fee|leave|deadline)\b', heading, re.I):
            return None
    fact = signature(normalized, heading)
    if not fact:
        return None
    # "Should" is advice; "must" is an obligation. The employee matcher has
    # broader equivalences that must not turn advice into an admin alert.
    expanded = normalized.replace('cannot', 'can not')
    modals = tuple(re.findall(r'\b(?:should|must|shall|can|may)\b', expanded))
    modals = tuple('must' if value == 'shall' else value for value in modals)
    # Retain literal lexical qualifiers too. Stemming alone can conflate roles
    # and actions; only normalize the supported written value forms here.
    guard = expanded
    guard = re.sub(r'\b(?:prohibited|forbidden|disallowed|banned)\b', 'not allowed', guard)
    guard = re.sub(r'\bpermitted\b', 'allowed', guard)
    guard = re.sub(r'\bshall\b', 'must', guard)
    guard = re.sub(r'\byearly\b', 'annually', guard)
    guard = re.sub(r'\b(?:' + VALUE_WORDS + r')\b|\d+(?:[.,:]\d+)*%?', '#', guard)
    guard = re.sub(r'\b(?:not|never)\b', '', guard)
    # Contextual headings also retain their order (e.g. who notifies whom).
    heading_guard = tuple(word for word in words(heading) if root(term(word)) in fact[0][1])
    guard = (tuple(EQUIVALENT_WORDS.get(word, EQUIVALENT_WORDS.get(term(word), word))
                   for word in re.findall(r'[#\w]+|[$€£]', guard)), heading_guard)
    return ((fact[0], guard, modals), *fact[1:])


def difference_key(first, second):
    """Keep distinct disputed fields (e.g. duration and fee) separate."""
    if not supported_difference(first, second):
        return None
    template, guard, modals = first[0]
    base, context = template
    if first[2] != second[2]:
        aspect = ('negation', first[1])
    else:
        # Permissions/prohibitions at two quantities can both hold. A direct
        # permission versus prohibition at the *same* quantity remains eligible.
        if first[2] or 'allowed' in guard[0] or any(value in {'can', 'may'} for value in modals):
            return None
        index = next(i for i, (a, b) in enumerate(zip(first[1], second[1])) if a != b)
        aspect = ('value', index, first[2], first[1][:index] + first[1][index + 1:])
    return (base, tuple(sorted(context)), guard, modals, aspect)


def identifier(key):
    encoded = json.dumps(['policy-issue-v1', key], ensure_ascii=True, separators=(',', ':'))
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def topic(passage, aspect):
    """Mask only the disputed field, retaining fixed values and conditions.

    This is a display label, never a quotation. Evidence always uses the
    untouched, independently verified source span.
    """
    label = passage.text
    if aspect[0] == 'duration':
        from .proactive_policy import DURATION
        label = DURATION.sub('[duration]', label)
    elif aspect[0] == 'value':
        # Follow the comparison's conditional boundaries when locating values.
        # Do not hide a fixed trigger count or another field in the topic.
        tokens = list(re.finditer(r"\d+(?:[.,:]\d+)*(?:st|nd|rd|th|%)?|\w+(?:['’]\w+)?|[,;:.!?]", label))
        conditional = any(t.group() == ':' for t in tokens) or bool(re.match(
            r'^\s*(?:\d+|' + '|'.join(NUMBERS) + r')\b[^,]+,', label, re.I))
        spans = []
        for match in tokens:
            token = match.group().casefold()
            if token in ',;:.!?':
                conditional = False
            elif token in {'if', 'unless', 'when', 'after', 'before', 'except', 'until'}:
                conditional = True
            elif not conditional and (token in set(NUMBERS) | DAYS | FREQUENCIES | {'yearly'}
                                     or re.fullmatch(r'\d+(?:[.,:]\d+)*%?', token)):
                spans.append(match.span())
        if aspect[1] < len(spans):
            start, end = spans[aspect[1]]
            label = label[:start] + '[value]' + label[end:]
    else:
        label = re.sub(r"\bcan[’']t\b", '[permission]', label, flags=re.I)
        label = re.sub(r"\b(?:must|shall|should|can|may|cannot|not|never|allowed|permitted|prohibited|forbidden|banned)(?:n[’']t)?\b", '[permission]', label, flags=re.I)
        label = re.sub(r'(?:\[permission\]\s*)+', '[permission] ', label).strip()
    heading = passage.heading if passage.heading != 'Document body' else ''
    return (f'{heading}: ' if heading else '') + label

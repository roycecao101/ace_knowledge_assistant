"""Discover counted-event rules locally, using the employee timing comparator.

Conditions come exclusively from approved passages/labels. No questions are
generated, read, or retained. Explicit event qualifiers and actors are retained.
"""
import re
from collections import defaultdict

from .document_indexer import words, term
from .search_language import lexical_text, passage_terms, root
from .timing_policy import CARDINAL, ORDINAL, number, fact_for_condition, facts_disagree
from .policy_issues import review_signature, difference_key

COUNT = r'(?:\d+(?:st|nd|rd|th)?|' + '|'.join(sorted(set(CARDINAL) | set(ORDINAL))) + r')'
ACTIONS = r'(?:reschedule|schedule|rebook|book|wait|delay|postpone|push|move|return)'
LABEL = re.compile(r'^\s*(?:after\s+)?(?:(?:a|an|the)\s+)?'
                   r"(?:(\w+)[’']s\s+)?(?:the\s+)?(" + COUNT + r')\s+(.+)', re.I)
UNSAFE = re.compile(r'\b(?:not|never|cannot|unless|except|if|or|either|alternatively|formerly|previously|historical|example|observed|reported|approximately|about|roughly)\b', re.I)
DURATION = re.compile(r'\b(?:\d+|' + '|'.join(CARDINAL) + r')(?:\s*[-–—]\s*\d+)?[\s-]*(?:(?:business|working|calendar) )?(?:hours?|days?|weeks?|months?|years?)\b', re.I)
MAX_CONDITIONS = 4096
HEADING_SCAFFOLDING = passage_terms('schedule reschedule rebook book wait delay postpone push move return '
                                   'reference quick guide guideline handbook manual action response event occurrence')


class ConditionCatalog(list):
    """Ephemeral source-derived events and their independent source support."""


def labels(text):
    """Retain every event qualifier, order, and explicit possessor."""
    for segment in re.split(r'[/\n]', text):
        match = LABEL.match(segment)
        if not match:
            continue
        tail = re.split(r'[,.:;!?]|\b' + ACTIONS + r'\b', match[3], maxsplit=1, flags=re.I)[0]
        # A numeric duration is an output, never an event occurrence.
        if re.search(r'\b(?:hours?|days?|weeks?|months?|years?)\b', tail, re.I):
            continue
        event = tuple(root(term(w)) for w in words(lexical_text(tail)) if w not in {'the', 'a', 'an'})
        if event and len(event) <= 8 and not UNSAFE.search(tail):
            yield number(match[2].casefold()), event, root(match[1].casefold()) if match[1] else None


def discover_conditions(passages, deadline_ok=lambda: True):
    # Single-adjective row labels can inherit their noun from a complete rule
    # elsewhere in the approved index; they cannot define an event by themselves.
    conditions = set()
    descriptions = defaultdict(set)
    for p in passages:
        deadline_ok()
        source_labels = list(labels(p.text + '\n' + p.heading))
        conditions.update((count, tuple(sorted(event))) for count, event, _ in source_labels if len(event) >= 2)
        # Table ancestors supply a topic while row labels supply occurrence.
        # Candidate phrases still need independent timing/source verification.
        for segment in p.heading.split('/'):
            if LABEL.match(segment):
                continue
            vocabulary = passage_terms(segment) - HEADING_SCAFFOLDING
            event = tuple(root(term(w)) for w in words(lexical_text(segment))
                          if root(term(w)) in vocabulary)
            if 2 <= len(event) <= 16 and not UNSAFE.search(segment):
                for count, _, _ in source_labels:
                    for start in range(len(event)):
                        for end in range(start + 2, min(start + 9, len(event) + 1)):
                            descriptions[count, tuple(sorted(event[start:end]))].add(tuple(sorted(event)))
        if len(conditions) > MAX_CONDITIONS or len(descriptions) > MAX_CONDITIONS:
            raise ValueError('Condition limit')
    # A topic can repeat in a different order across document titles. Match
    # the same event vocabulary used by the shared employee timing analyzer.
    whole = defaultdict(set)
    for (count, _), sources in descriptions.items():
        whole[count].update(sources)
    for count, sources in whole.items():
        ordered = sorted(sources)
        for i, first in enumerate(ordered):
            deadline_ok()
            for second in ordered[i + 1:]:
                deadline_ok()
                common = tuple(sorted(set(first) & set(second)))
                if len(common) >= 2:
                    descriptions[count, common].update((first, second))
                    if len(descriptions) > MAX_CONDITIONS:
                        raise ValueError('Condition limit')
    conditions.update(descriptions)
    result = ConditionCatalog(sorted(conditions))
    if len(result) > MAX_CONDITIONS:
        raise ValueError('Condition limit')
    support = defaultdict(set)
    for p in passages:
        deadline_ok()
        vocabulary = passage_terms(p.text + ' ' + p.heading)
        own = list(labels(p.text))
        row = list(labels(p.heading))
        for count, event in result:
            if not set(event).issubset(vocabulary):
                continue
            if not any(label[0] == count and (set(label[1]) == set(event) if own
                       else bool(set(label[1]) & set(event))) for label in own or row):
                continue
            if fact_for_condition((count, frozenset(event), None), p.text, p.heading):
                support[count, event].add((p.text, p.heading))
    result.support = {key: len(sources) for key, sources in support.items()}
    return result


def timing_signature(text, heading, conditions):
    if UNSAFE.search(text) or UNSAFE.search(heading):
        return None
    own = list(labels(text))
    row = list(labels(heading))
    # Narrative rules keep their complete condition. Terse output cells may
    # inherit labels from their indexed table headings.
    applicable = own or row
    if not applicable:
        return None
    choices = []
    for count, event in conditions:
        matching = [label for label in applicable if label[0] == count and (
            set(label[1]) == set(event) if own else bool(set(label[1]) & set(event)))]
        if not matching:
            continue
        fact = fact_for_condition((count, frozenset(event), None), text, heading)
        if not fact:
            continue
        actors = {actor for _, _, actor in matching if actor}
        actors |= {root(value.casefold()) for value in re.findall(r"(?i)\b(\w+)[’']s\b", text + ' ' + heading)}
        if len(actors) > 1:
            continue
        # Approval and eligibility clauses need more than a duration comparison.
        if re.search(r'\b(?:approval|permission|urgent|emergency|eligible|eligibility|without|only|provided)\b', text, re.I):
            continue
        modality = tuple(re.findall(r'\b(?:should|must|shall|can|may)\b', text.casefold()))
        if any(value in {'can', 'may'} for value in modality):
            continue
        modality = tuple('must' if value == 'shall' else value for value in modality)
        choices.append((('timing', count, event), fact, tuple(sorted(actors)), modality))
    # More than one complete event interpretation is ambiguous.
    # Equivalent ancestor/row descriptions may differ in how much context they
    # repeat. Prefer the complete event over a partial row label.
    if choices:
        support = getattr(conditions, 'support', {})
        def rank(choice):
            return support.get((choice[0][1], choice[0][2]), 0), len(choice[0][2])
        best = max(map(rank, choices))
        choices = [choice for choice in choices if rank(choice) == best]
    return choices[0] if len(choices) == 1 else None


def analysis_signature(text, heading, conditions, *, context=False):
    timed = timing_signature(text, heading, conditions)
    if timed:
        return timed
    if context:
        return None
    scalar = review_signature(text, heading)
    return (('scalar', scalar[0]), scalar) if scalar else None


def issue_key(first, second):
    if not first or not second or first[0] != second[0]:
        return None
    if first[0][0] == 'scalar':
        return difference_key(first[1], second[1])
    if ((first[3] and second[3] and first[3] != second[3])
            or (first[2] and second[2] and first[2] != second[2])):
        return None
    if not facts_disagree(first[1], second[1]):
        return None
    _, count, event = first[0]
    return ('counted-duration-v1', count, event, first[2] or second[2],
            first[1][2][2:], ('duration',))

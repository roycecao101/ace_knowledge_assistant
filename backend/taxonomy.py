import re
OFFICES = ['Alpharetta', 'Norcross', 'Lilburn']
CATEGORIES = ['All Categories', 'HR & Employee Policies', 'OSHA & Safety', 'Front Office', 'Back Office / Clinical Operations', 'Insurance & Documentation (non-PHI)', 'Management & Operations', 'Training & Onboarding', 'Scripts & Communication']
CODES = {'ALP':'Alpharetta', 'NOR':'Norcross', 'LIL':'Lilburn', 'ADC':'Lilburn'}
def filename_offices(name, codes=None):
    # Only leading office codes count, never incidental body/name mentions.
    codes = CODES if codes is None else codes
    alternatives = '|'.join(re.escape(code) for code in sorted(codes, key=len, reverse=True))
    label = rf'(?:{alternatives})\b'
    match = re.match(rf'^({label}(?:[\s,/&+-]+{label})*)', name, re.I)
    return sorted({codes[c.upper()] for c in re.findall(label, match[1], re.I)}) if match else []


def heading_offices(text, codes=None):
    # Scope must be a heading label/prefix, never an incidental prose mention.
    codes = CODES if codes is None else codes
    labels = {**{name.casefold(): name for name in codes.values()},
              **{code.casefold(): name for code, name in codes.items()}}
    alternatives = '|'.join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
    label = rf'(?:{alternatives})\b'
    match = re.match(rf'^\s*(?:Offices?\s*[:–—-]\s*)?({label}(?:(?:\s*(?:[,/&+]|and)\s*|\s+){label})*)', text, re.I)
    if not match:
        return []
    return sorted({labels[value.casefold()] for value in re.findall(label, match[1], re.I)})

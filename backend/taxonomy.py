import re
OFFICES = ['Alpharetta', 'Norcross', 'Lilburn']
CATEGORIES = ['All Categories', 'HR & Employee Policies', 'OSHA & Safety', 'Front Office', 'Back Office / Clinical Operations', 'Insurance & Documentation (non-PHI)', 'Management & Operations', 'Training & Onboarding', 'Scripts & Communication']
CODES = {'ALP':'Alpharetta', 'NOR':'Norcross', 'LIL':'Lilburn', 'ADC':'Lilburn'}
def filename_offices(name):
    # Only leading office codes count, never incidental body/name mentions.
    match = re.match(r'^((?:ALP|NOR|LIL|ADC)\b(?:[\s,/&+-]+(?:ALP|NOR|LIL|ADC)\b)*)', name, re.I)
    return sorted({CODES[c.upper()] for c in re.findall(r'ALP|NOR|LIL|ADC', match[1], re.I)}) if match else []

def heading_offices(text):
    # Scope must be a heading label/prefix, never an incidental mention such as
    # "Travel to Norcross". Codes and full names are both accepted.
    label = r'(?:Alpharetta|Norcross|Lilburn|ALP|NOR|LIL|ADC)\b'
    match = re.match(rf'^\s*(?:Offices?\s*[:–—-]\s*)?({label}(?:(?:\s*(?:[,/&+]|and)\s*|\s+){label})*)', text, re.I)
    if not match:
        return []
    labels = re.findall(label, match[1], re.I)
    return sorted({CODES.get(value.upper(), value.title()) for value in labels})

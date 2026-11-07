import re
OFFICES = ['Alpharetta', 'Norcross', 'Lilburn']
CATEGORIES = ['All Categories', 'HR & Employee Policies', 'OSHA & Safety', 'Front Office', 'Back Office / Clinical Operations', 'Insurance & Documentation (non-PHI)', 'Management & Operations', 'Training & Onboarding', 'Scripts & Communication']
CODES = {'ALP':'Alpharetta', 'NOR':'Norcross', 'LIL':'Lilburn', 'ADC':'Lilburn'}
def filename_offices(name):
    # Only leading office codes count, never incidental body/name mentions.
    match = re.match(r'^((?:ALP|NOR|LIL|ADC)(?:\s+(?:ALP|NOR|LIL|ADC))*)\s*[-–—]', name, re.I)
    return sorted({CODES[c.upper()] for c in re.findall(r'ALP|NOR|LIL|ADC', match[1], re.I)}) if match else []

def heading_offices(text):
    return [office for office in OFFICES if re.search(r'\b' + office + r'\b', text, re.I)]

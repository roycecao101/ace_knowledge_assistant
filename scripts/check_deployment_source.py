"""Print only file/category findings; never emit file contents or secret values."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_SUFFIXES = {'.db', '.sqlite', '.sqlite3', '.pdf', '.doc', '.docx', '.xlsx', '.pem', '.key', '.p12', '.dump', '.sql'}
PATTERNS = {
    'private key material': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'Google OAuth secret': re.compile(rb'GOCSPX-[A-Za-z0-9_-]{12,}'),
    'Google API key': re.compile(rb'AIza[A-Za-z0-9_-]{30,}'),
    'GitHub credential': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})'),
    'Google refresh token': re.compile(rb'1//[A-Za-z0-9_-]{30,}'),
}


def main():
    result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                            cwd=ROOT, check=True, capture_output=True)
    findings = []
    for name in sorted(set(result.stdout.decode().split('\0')) - {''}):
        path = ROOT / name
        if (path.suffix.lower() in PRIVATE_SUFFIXES or path.name == '.env' or path.name.startswith('.env.')
                or any(part in {'.aws', 'secrets', 'private', 'backups', 'data', '.venv'} for part in path.parts)
                or re.search(r'(?:credentials|token|client_secret|oauth-client|oauth-token).*\.json$', path.name)):
            findings.append((name, 'private artifact must not be committed'))
            continue
        if path.is_symlink():
            findings.append((name, 'review symlink before deployment'))
            continue
        if not path.is_file():
            continue
        data = path.read_bytes()
        for label, pattern in PATTERNS.items():
            if pattern.search(data):
                findings.append((name, label))
    for name, label in findings:
        print(f'{name}: {label}')
    if findings:
        print('Source audit failed. Review privately and rotate any exposed credentials before pushing.')
        return 1
    print('Current-source audit passed. Git history and manual privacy review are still required.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

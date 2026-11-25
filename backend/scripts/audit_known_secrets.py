"""Read-only known-local-secret scan; prints labels and paths, never values.

Run from the project root. This is evidence for known values, not a guarantee
against unknown credentials. Git blobs are read without modifying the index.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
GIT = ['git', '-c', f'safe.directory={ROOT.as_posix()}']


def known_secrets():
    secrets = {}
    for path in (ROOT / 'backend/.env', ROOT / '.env'):
        if not path.exists():
            continue
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if '=' not in line or line.lstrip().startswith('#'):
                continue
            key, value = line.split('=', 1)
            key, value = key.strip(), value.strip().strip('\"\'')
            if (value and 'EXPIRE' not in key.upper()
                  and key.upper() != 'GROQ_MAX_OUTPUT_TOKENS'
                  and any(word in key.upper() for word in ('PASSWORD', 'SECRET', 'TOKEN', 'API_KEY'))):
             secrets[key] = value.encode()
    return secrets


def matches(data, secrets):
    # Short strings are too ambiguous as arbitrary substrings. Match literals
    # or dotenv assignments instead; disclose this limit in the report.
    return [key for key, value in secrets.items() if (
        value in data if len(value) >= 8 else any(pattern in data for pattern in (
            b'"' + value + b'"', b"'" + value + b"'", key.encode() + b'=' + value + b'\n')))]


def main():
    secrets = known_secrets()
    paths = subprocess.check_output(GIT + ['ls-files', '--cached', '--others', '--exclude-standard'],
                                    cwd=ROOT).decode().splitlines()
    assets = list((ROOT / 'frontend/dist').rglob('*'))
    findings, inspected = [], 0
    for path in sorted(set(ROOT / name for name in paths) | set(assets)):
        if path.is_file() and path.suffix.lower() not in {'.png', '.jpg', '.ico', '.pdf'}:
            inspected += 1
            for key in matches(path.read_bytes(), secrets):
                findings.append(('working tree / bundle', str(path.relative_to(ROOT)), key))
    objects = subprocess.check_output(GIT + ['rev-list', '--objects', '--all'], cwd=ROOT).splitlines()
    blobs = 0
    # One batch process avoids putting any secret values in command arguments.
    batch = subprocess.Popen(GIT + ['cat-file', '--batch'], cwd=ROOT,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        for entry in objects:
            oid, _, name = entry.partition(b' ')
            if not name or Path(name.decode(errors='replace')).suffix.lower() in {'.png', '.jpg', '.ico', '.pdf'}:
                continue
            batch.stdin.write(oid + b'\n')
            batch.stdin.flush()
            header = batch.stdout.readline().split()
            if len(header) != 3:
                continue
            data = batch.stdout.read(int(header[2]))
            batch.stdout.read(1)
            if header[1] != b'blob':
                continue
            blobs += 1
            for key in matches(data, secrets):
                findings.append(('Git history', name.decode(errors='replace'), key))
    finally:
        batch.stdin.close()
        batch.wait()
    print(f'Inspected {inspected} current files/assets and {blobs} historical text blobs; '
          f'{len(secrets)} known local secret labels; short values use literal matching.')
    for scope, path, key in sorted(set(findings)):
        print(f'MATCH: {scope}: {path}: {key}')
    print(f'Known-secret findings: {len(set(findings))}')
    return bool(findings)


if __name__ == '__main__':
    sys.exit(main())

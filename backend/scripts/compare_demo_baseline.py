"""Compare a new read-only demo snapshot with the pinned private backup baseline."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = (ROOT / '.server-logs' / 'private-demo-backups').resolve()
MANIFEST = 'lankapex_demo_db_20261109T175450Z_a7ace782.backup.json'
DUMP = 'lankapex_demo_db_20261109T175450Z_a7ace782.sql'
SHA256 = 'ede32b514a47efb4b3b06a206596ff8d23a03f9779cafc39e32099b5a654e685'
FIELDS = ('row_counts', 'table_fingerprints',
          'financial_relationship_fingerprints', 'foreign_key_orphans')
DATABASE = 'lankapex_demo_db'
ACCOUNT = 'lankapex_demo_migrator@localhost'
REVISION = '14c0d3e2f782'


def stop(condition, reason):
    if not condition:
        raise ValueError(reason)


def validate(baseline):
    stop(isinstance(baseline, dict), 'invalid manifest format')
    stop(baseline.get('database') == DATABASE and baseline.get('account') == ACCOUNT
         and baseline.get('revision') == REVISION, 'database/account/revision mismatch')
    stop(isinstance(baseline.get('captured_utc'), str) and baseline['captured_utc'],
         'missing capture timestamp')
    for field in FIELDS:
        stop(isinstance(baseline.get(field), dict), 'missing or invalid ' + field)
    counts = baseline['row_counts']
    hashes = baseline['table_fingerprints']
    financial = baseline['financial_relationship_fingerprints']
    orphans = baseline['foreign_key_orphans']
    stop(len(counts) == 26 and counts.keys() == hashes.keys(), 'invalid table inventory')
    stop(len(financial) == 4 and len(orphans) == 53, 'invalid relationship inventory')
    stop(all(isinstance(k, str) and k and type(v) is int and v >= 0
             for k, v in counts.items()), 'invalid row count')
    stop(all(isinstance(k, str) and k and isinstance(v, str)
             and re.fullmatch(r'[0-9a-f]{64}', v) for group in (hashes, financial)
             for k, v in group.items()), 'invalid fingerprint')
    stop(all(isinstance(k, str) and k and type(v) is int and v >= 0
             for k, v in orphans.items()), 'invalid foreign-key count')


def compare(expected, current):
    validate(expected)
    validate(current)
    for field in FIELDS:
        stop(expected[field] == current[field], 'current ' + field + ' differs')


def private_json(path):
    path = Path(path).resolve()
    stop(path.parent == PRIVATE and path.suffix == '.json' and path.is_file(),
         'manifest must be an existing private JSON file')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError('invalid private JSON') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', required=True)
    args = parser.parse_args()
    pinned = private_json(PRIVATE / MANIFEST)
    stop(pinned.get('database') == DATABASE and pinned.get('revision') == REVISION
         and pinned.get('dump_filename') == DUMP and pinned.get('sha256') == SHA256
         and isinstance(pinned.get('before_manifest'), str),
         'pinned backup identity differs')
    before = PRIVATE / pinned['before_manifest']
    stop(before.resolve().parent == PRIVATE and before.name.endswith('.before.json'),
         'pinned baseline path differs')
    dump = PRIVATE / DUMP
    stop(dump.is_file() and dump.stat().st_size == pinned.get('size_bytes'),
         'pinned backup size differs')
    with dump.open('rb') as source:
        stop(hashlib.file_digest(source, 'sha256').hexdigest() == SHA256,
             'pinned backup checksum differs')
    current = Path(args.current).resolve()
    stop(current.parent == PRIVATE and current.name not in
         {MANIFEST, pinned['before_manifest'], pinned.get('after_manifest')},
         'current manifest path must be distinct and private')
    compare(private_json(before), private_json(current))
    print('PASS: exact demo identity/revision and all 26 table counts/fingerprints, '
          'four financial relationships and 53 foreign-key checks match pinned backup')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('STOP: demo baseline comparison failed ('
              + (str(exc) if isinstance(exc, ValueError) else type(exc).__name__) + ')',
              file=sys.stderr)
        sys.exit(1)

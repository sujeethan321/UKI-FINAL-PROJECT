"""Private logical backup of the exact populated demo schema; no database writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / '.server-logs' / 'private-demo-backups'
MYSQLDUMP = Path(r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe')
TARGET = 'lankapex_demo_db'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def option(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, choices=[TARGET])
    args = parser.parse_args()
    require(os.environ.get('APP_ENV') == 'development'
            and os.environ.get('MYSQL_DATABASE') == TARGET
            and os.environ.get('MYSQL_USER') == 'lankapex_demo_migrator'
            and os.environ.get('MYSQL_HOST') in ('localhost', '127.0.0.1', '::1')
            and os.environ.get('MYSQL_PASSWORD'), 'Exact private demo migrator environment required')
    require(PRIVATE.is_dir() and MYSQLDUMP.is_file(), 'Private directory or mysqldump missing')
    sys.path.insert(0, str(ROOT / 'backend'))
    from app.core.config import settings
    from app.core.database import engine
    require(settings.APP_ENV == 'development' and settings.MYSQL_DATABASE == TARGET
            and settings.MYSQL_USER == 'lankapex_demo_migrator', 'Effective demo settings differ')
    with engine.connect() as conn:
        require(conn.exec_driver_sql('SELECT DATABASE()').scalar_one() == TARGET
                and conn.exec_driver_sql('SELECT CURRENT_USER()').scalar_one()
                == 'lankapex_demo_migrator@localhost', 'Actual dump target/account differs')
        objects = conn.exec_driver_sql(
            'SELECT '
            '(SELECT COUNT(*) FROM information_schema.VIEWS WHERE TABLE_SCHEMA=%s),'
            '(SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s),'
            '(SELECT COUNT(*) FROM information_schema.EVENTS WHERE EVENT_SCHEMA=%s),'
            '(SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s)',
            (TARGET, TARGET, TARGET, TARGET)).one()
        require(tuple(objects) == (0, 0, 0, 0),
                'Demo has stored objects requiring separate privilege/backup review')
    engine.dispose()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stem = 'lankapex_demo_db_' + stamp + '_' + os.urandom(4).hex()
    dump = PRIVATE / (stem + '.sql')
    before = PRIVATE / (stem + '.before.json')
    after = PRIVATE / (stem + '.after.json')
    manifest = PRIVATE / (stem + '.backup.json')
    option_file = PRIVATE / (stem + '.client.cnf')
    require(not any(path.exists() for path in (dump, before, after, manifest, option_file)),
            'Private backup filename collision')
    baseline = [sys.executable, str(ROOT / 'backend/scripts/capture_demo_baseline.py'),
                '--database', TARGET]
    subprocess.run(baseline + ['--output', str(before)], check=True)
    try:
        with option_file.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write('[client]\n')
            for key, value in (('host', settings.MYSQL_HOST), ('port', settings.MYSQL_PORT),
                               ('user', settings.MYSQL_USER), ('password', settings.MYSQL_PASSWORD)):
                handle.write(key + '=' + option(value) + '\n')
        cmd = [str(MYSQLDUMP), '--defaults-extra-file=' + str(option_file),
               '--single-transaction', '--quick', '--comments', '--skip-extended-insert',
               '--set-gtid-purged=OFF', '--no-tablespaces', '--skip-add-drop-table',
               '--result-file=' + str(dump), TARGET]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            match = re.search(r'(?i)(?:error|errno)\s*:?\s*(\d{3,5})', result.stderr)
            raise RuntimeError('mysqldump failed (exit=' + str(result.returncode)
                               + ', MySQL code=' + (match.group(1) if match else 'unavailable') + ')')
    finally:
        option_file.unlink(missing_ok=True)
    require(dump.is_file() and dump.stat().st_size > 0, 'Backup missing or empty')
    sql = dump.read_text(encoding='utf-8')
    require(len(re.findall(r'(?m)^CREATE TABLE `[^`]+` \(', sql)) == 26,
            'Expected 26 table definitions missing')
    require('14c0d3e2f782' in sql and 'lankapex_demo_db' in sql,
            'Source revision/database marker missing from dump')
    require(not re.search(r'(?im)^\s*(?:CREATE|ALTER|DROP)\s+DATABASE\b|^\s*USE\s+|'
                          r'\bDEFINER\s*=|\b(?:lankapex_db|lankapex_test_db)\s*\.', sql),
            'Dump contains redirection or unreviewed object definition')
    first = json.loads(before.read_text(encoding='utf-8'))
    for table, expected_count in first['row_counts'].items():
        actual_count = len(re.findall(r'(?m)^INSERT INTO `' + re.escape(table) + r'` ', sql))
        require(actual_count == expected_count, 'Dump row count differs for ' + table)
    subprocess.run(baseline + ['--output', str(after)], check=True)
    second = json.loads(after.read_text(encoding='utf-8'))
    for key in ('database', 'account', 'revision', 'row_counts', 'table_fingerprints',
                'financial_relationship_fingerprints', 'foreign_key_orphans'):
        require(first[key] == second[key], 'Source changed across backup: ' + key)
    with dump.open('rb') as handle:
        checksum = hashlib.file_digest(handle, 'sha256').hexdigest()
    evidence = {'database': TARGET, 'revision': first['revision'], 'created_utc': stamp,
                'dump_filename': dump.name, 'size_bytes': dump.stat().st_size,
                'sha256': checksum, 'before_manifest': before.name, 'after_manifest': after.name,
                'restored_and_compared': False}
    with manifest.open('x', encoding='utf-8') as handle:
        json.dump(evidence, handle, indent=2, sort_keys=True)
        handle.write('\n')
    print('PASS: exact demo dump completed; checksum, 26 tables and revision verified')
    print('PASS: source counts, fingerprints and relationships unchanged across dump')
    print('PRIVATE_BACKUP=' + str(dump))
    print('PRIVATE_MANIFEST=' + str(manifest))
    print('SHA256=' + checksum)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            print('STOP: ' + str(exc), file=sys.stderr)
        else:
            print('STOP: demo backup validation failed (' + type(exc).__name__ + ')', file=sys.stderr)
        sys.exit(1)

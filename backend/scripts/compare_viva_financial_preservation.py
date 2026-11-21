"""Step 363 operator-only, read-only comparison with existing private evidence.

No reports written, Stripe access, app startup, environment edits or retries.
File timestamps are corroborative only; they do not prove baseline chronology.
"""
import argparse
from datetime import datetime, timezone
import getpass
import importlib.util
import json
import logging
from pathlib import Path
import re
import sys
import warnings

import pymysql

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'lankapex_viva_db'
PRIVATE = Path(r'C:\Users\admin\AppData\Local\LankaPex\VivaCheckpoints\step339')
TABLES = ('ledger_entries', 'credit_accounts', 'orders', 'order_items',
          'payment_reminders', 'delivery_requests', 'delivery_assignments', 'delivery_status_events')


def require(value):
    if not value:
        raise RuntimeError('Evidence gate failed')


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def baseline_tables(evidence):
    require(evidence.get('target') == TARGET)
    if 'before' in evidence:
        require(evidence.get('old') == '8c0f5e3d9b26' and evidence.get('new') == '9d1a6f4e0c37')
        tables = evidence['before']
    else:
        require(evidence.get('format') == 1)
        tables = evidence['tables']
    for table in TABLES:
        item = tables[table]
        require(type(item['count']) is int and item['count'] >= 0
            and re.fullmatch(r'[0-9a-f]{64}', item['sha256'])
            and re.fullmatch(r'[0-9a-f]{64}', item['ddl_sha256']))
    return tables


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read-only', action='store_true', required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    status, results, timestamp = 'BLOCKED', {}, 'UNVERIFIED'
    identity = 'UNVERIFIED'
    try:
        require(sys.stdin.isatty())
        path = args.baseline.resolve(strict=True)
        require(path.parent == PRIVATE.resolve(strict=True) and path.suffix == '.json')
        before_bytes = path.read_bytes()
        expected = baseline_tables(json.loads(before_bytes))
        identity = TARGET
        timestamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat() + '; FILE_MTIME_ONLY_NOT_CAPTURE_TIME'
        guards = load('step363_guards', 'output/step322/guarded_viva_setup.py')
        checkpoint = load('step363_digest', 'output/step336/checkpoint_viva.py')
        warnings.simplefilter('error', getpass.GetPassWarning)
        password = getpass.getpass('Existing viva runtime password (hidden): ')
        require(bool(password))
        connection = pymysql.connect(host='127.0.0.1', port=3306, database=TARGET, user=guards.RUNTIME,
            password=password, ssl=guards.tls_context(), autocommit=False,
            connect_timeout=5, read_timeout=30, write_timeout=15)
        try:
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                cursor.execute('SET TRANSACTION READ ONLY')
            guards.identity(connection, guards.RUNTIME, TARGET)
            require(guards.rows(connection, 'SELECT version_num FROM alembic_version') == (('9d1a6f4e0c37',),))
            guards.target_grants(connection, guards.RUNTIME, guards.RUNTIME_RIGHTS,
                guards.scalar(connection, 'SELECT @@GLOBAL.partial_revokes'))
            for table in TABLES:
                keys = guards.rows(connection, "SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND CONSTRAINT_NAME='PRIMARY' ORDER BY ORDINAL_POSITION", (TARGET, table))
                require(keys and all(re.fullmatch(r'[a-z_][a-z0-9_]*', row[0]) for row in keys))
                order = ','.join('`' + row[0] + '`' for row in keys)
                with connection.cursor() as cursor:
                    cursor.execute('SELECT * FROM `' + table + '` ORDER BY ' + order)
                    actual = checkpoint.digest_rows(cursor)
                match = actual == {key: expected[table][key] for key in ('count', 'sha256')}
                results[table] = 'EXACT_ROWS_MATCH; CHRONOLOGY_UNVERIFIED' if match else 'DIFFERENT; CAUSE_UNVERIFIED'
                if not match:
                    raise RuntimeError('Mismatch; stop without retry')
        finally:
            connection.close()
        require(path.read_bytes() == before_bytes)
        status = 'PARTIAL'  # No embedded timestamp/anchor; never infer historical PASS.
    except (Exception, KeyboardInterrupt):
        pass
    print('STEP363_STATUS=' + status)
    print('HISTORICAL_BASELINE=EXISTING_FILE; TIMING_REQUIRES_INDEPENDENT_CORROBORATION')
    print('BASELINE_DATABASE=' + identity)
    print('BASELINE_TIMESTAMP=' + timestamp)
    for table in TABLES:
        print('TABLE_' + table.upper() + '=' + results.get(table, 'UNVERIFIED'))
    print('FINANCIAL_DATA_PRESERVATION=UNVERIFIED_HISTORICALLY; CURRENT_COUNTS_ALONE_ARE_NOT_PROOF')
    print('NEXT_ACTION=' + ('Corroborate baseline creation before first Checkout using prior operator evidence'
        if status == 'PARTIAL' else 'STOP; missing, inaccessible or mismatched evidence; no retry or cleanup'))
    return 0 if status == 'PARTIAL' else 1


if __name__ == '__main__':
    sys.exit(main())

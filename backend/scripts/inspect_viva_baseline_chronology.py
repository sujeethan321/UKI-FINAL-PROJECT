"""Step 364: existing private evidence and first business-1 Checkout only.

No file writes, environment changes, application startup, retries or mutations.
Missing capture timestamps cannot be reconstructed from file modification time.
"""
import argparse
from datetime import datetime, timezone
import getpass
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import sys
import warnings

import httpx
import pymysql

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = Path(r'C:\Users\admin\AppData\Local\LankaPex\VivaCheckpoints\step339')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require(value):
    if not value:
        raise RuntimeError('Chronology gate failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read-only', required=True, action='store_true')
    parser.parse_args()
    logging.disable(logging.CRITICAL)
    result = dict(STEP364_STATUS='BLOCKED', BASELINE_CHRONOLOGY='UNVERIFIED',
        BASELINE_EVIDENCE='UNVERIFIED', FIRST_CHECKOUT_TIME='UNVERIFIED',
        CHRONOLOGY_COMPARISON='UNVERIFIED',
        FINANCIAL_DATA_PRESERVATION='STEP363_EXACT_MATCHES_OPERATOR_REPORTED; HISTORICAL_CHRONOLOGY_UNVERIFIED',
        NEXT_ACTION='STOP; preserve evidence; no retry')
    try:
        require(sys.stdin.isatty())
        comparison = load('step364_manifest', 'backend/scripts/compare_viva_financial_preservation.py')
        manifest = PRIVATE / 'step347-checkout-application.json'
        original = manifest.read_bytes()
        evidence = json.loads(original)
        comparison.baseline_tables(evidence)
        # This field is a pre-migration marker, not an outcome or a timestamp.
        require(evidence.get('phase') == 'APPLY_MAY_HAVE_STARTED')
        result['BASELINE_EVIDENCE'] = 'STEP347_TARGET_AND_REVISION_CHAIN_MATCH; PRE_MIGRATION_MARKER; NO_GENERATED_CAPTURE_TIMESTAMP'
        mtime = datetime.fromtimestamp(manifest.stat().st_mtime, timezone.utc)
        print('BASELINE_FILE_MTIME_UTC=' + mtime.isoformat() + '; FILESYSTEM_METADATA_ONLY')
        prior = PRIVATE / 'step343-result.json'
        if prior.is_file():
            old = json.loads(prior.read_bytes())
            require(old.get('DATABASE') == 'lankapex_viva_db')
            print('STEP343_PRIOR_REPORT=' + ('PASS_REPORTED_NO_CAPTURE_TIMESTAMP'
                if old.get('STEP343_STATUS') == 'PASS' else 'NOT_PASS_OR_INCOMPLETE'))
        else:
            print('STEP343_PRIOR_REPORT=MISSING')
        guards = load('step364_guards', 'output/step322/guarded_viva_setup.py')
        warnings.simplefilter('error', getpass.GetPassWarning)
        password = getpass.getpass('Existing viva runtime password (hidden): ')
        require(bool(password))
        connection = pymysql.connect(host='127.0.0.1', port=3306, database='lankapex_viva_db',
            user=guards.RUNTIME, password=password, ssl=guards.tls_context(), autocommit=False,
            connect_timeout=5, read_timeout=15, write_timeout=15)
        try:
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
            guards.identity(connection, guards.RUNTIME, 'lankapex_viva_db')
            require(guards.rows(connection, 'SELECT version_num FROM alembic_version') == (('9d1a6f4e0c37',),))
            rows = guards.rows(connection, 'SELECT created_at, stripe_session_id, attempt_id FROM subscription_checkout_attempts WHERE business_id=1 ORDER BY created_at, attempt_id LIMIT 1')
            require(len(rows) == 1)
            created, session_id, attempt_id = rows[0]
        finally:
            connection.close()
        result['FIRST_CHECKOUT_TIME'] = created.replace(tzinfo=timezone.utc).isoformat() + '; APP_GENERATED_UTC_STORED_IN_DATABASE'
        print('FILE_MTIME_BEFORE_FIRST_ATTEMPT=' + str(mtime < created.replace(tzinfo=timezone.utc))
            + '; CORROBORATIVE_ONLY')
        secret = os.environ.get('STRIPE_TEST_SECRET_KEY', '')
        if re.fullmatch(r'sk_test_[A-Za-z0-9]+', secret) and session_id:
            provider_module = load('step364_provider', 'backend/scripts/verify_existing_viva_subscription.py')
            with httpx.Client(base_url='https://api.stripe.com/v1/', timeout=12, trust_env=False,
                follow_redirects=False, transport=httpx.HTTPTransport(retries=0),
                headers={'Authorization': 'Bearer ' + secret, 'Stripe-Version': '2026-10-28.endive'}) as client:
                session = provider_module.Reader(client).get('checkout/sessions/' + session_id)
            require(session.get('id') == session_id and session.get('livemode') is False
                and session.get('client_reference_id') == '1'
                and session.get('metadata', {}).get('attempt_id') == attempt_id
                and type(session.get('created')) is int)
            print('EARLIEST_ATTEMPT_LINKED_SESSION_TIME_UTC=' + datetime.fromtimestamp(session['created'], timezone.utc).isoformat()
                + '; STRIPE_PROVIDER_GENERATED; DOES_NOT_PROVE_BASELINE_CAPTURE_TIME')
        else:
            print('EARLIEST_ATTEMPT_LINKED_SESSION_TIME_UTC=UNVERIFIED; TEST_KEY_OR_SESSION_UNAVAILABLE')
        require(manifest.read_bytes() == original)
        result.update(STEP364_STATUS='PARTIAL',
            CHRONOLOGY_COMPARISON='NO_TIMESTAMPED_BASELINE_ANCHOR; SCRIPT_ORDER_SUPPORTS_PRE_MIGRATION_CAPTURE_BUT_IS_NOT_AN_INDEPENDENT_EXECUTION_LOG',
            NEXT_ACTION='Corroborate with an existing trustworthy dated execution transcript or independent baseline hash anchor; do not recreate history or purchase again')
    except (Exception, KeyboardInterrupt):
        pass
    for key, value in result.items():
        print(key + '=' + value)
    return 0 if result['STEP364_STATUS'] == 'PARTIAL' else 1


if __name__ == '__main__':
    sys.exit(main())

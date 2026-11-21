"""Step 362: existing business 1 only; SELECTs and Stripe GETs, never reconciliation.

Run in the configured operator terminal. No dotenv, application startup, report
files, secret output, mutation endpoints, or automatic retries.
"""
import argparse
import ast
from datetime import datetime, timezone
import getpass
import importlib.util
import logging
import math
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import warnings

import httpx
import pymysql

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'lankapex_viva_db'
FIELDS = ('CHECKOUT_ATTEMPT', 'STRIPE_CHECKOUT_SESSION', 'STRIPE_PAYMENT_STATUS',
          'STRIPE_SUBSCRIPTION', 'LATEST_INVOICE', 'WEBHOOK_RECEIPTS',
          'MYSQL_SUBSCRIPTION', 'EFFECTIVE_PLAN', 'DUPLICATE_SUBSCRIPTIONS')


class Stop(Exception):
    pass


def require(condition):
    if not condition:
        raise Stop()


def evaluator():
    # Execute only the application's pure entitlement functions, without loading
    # its settings, database engine, app startup, or mutation services.
    source = ROOT / 'backend/app/services/subscription_service.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    names = {'utc_now', 'utc', 'evaluate'}
    tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    require({node.name for node in tree.body} == names)
    namespace = dict(datetime=datetime, timezone=timezone, math=math, FEATURES=())
    exec(compile(tree, str(source), 'exec'), namespace)
    return namespace['evaluate']


class Reader:
    def __init__(self, client):
        self.client = client

    def get(self, path, params=None):
        require(re.fullmatch(r'(checkout/sessions/cs_test_[A-Za-z0-9]+|subscriptions|'
            r'subscriptions/sub_[A-Za-z0-9]+|invoices/in_[A-Za-z0-9]+|'
            r'customers/cus_[A-Za-z0-9]+|prices/price_[A-Za-z0-9]+|events/evt_[A-Za-z0-9]+)', path))
        response = self.client.get(path, params=params)
        require(response.status_code == 200)
        obj = response.json()
        require(isinstance(obj, dict) and obj.get('livemode') is not True)
        return obj

    def subscriptions(self, customer):
        result = []
        after = None
        for _ in range(20):
            page = self.get('subscriptions', dict(customer=customer, status='all', limit=100,
                **({'starting_after': after} if after else {})))
            require(isinstance(page.get('data'), list))
            result.extend(page['data'])
            if page.get('has_more') is False:
                return result
            require(bool(page['data']))
            after = page['data'][-1]['id']
        raise Stop()


def inspect(rows, provider, price, result, evaluate):
    sub, attempts, receipts, grant = rows
    require(sub and sub['business_id'] == 1 and sub['provider_mode'] == 'sandbox')
    # Ambiguous/historical duplicate attempts require manual review, never choose
    # one silently. All existing attempts are read, not just the latest one.
    require(len(attempts) == 1)
    attempt = attempts[0]
    require(attempt['business_id'] == 1 and attempt['plan'] == 'PRO'
            and attempt['billing_interval'] == 'month' and attempt['price_id'] == price)
    result['CHECKOUT_ATTEMPT'] = attempt['status']
    require(attempt['status'] == 'COMPLETE' and attempt['active_business_id'] is None)
    customer_id, subscription_id = sub['stripe_customer_id'], sub['stripe_subscription_id']
    require(customer_id and subscription_id and attempt['stripe_customer_id'] == customer_id)
    session = provider.get('checkout/sessions/' + attempt['stripe_session_id'])
    require(session.get('id') == attempt['stripe_session_id'] and session.get('livemode') is False
        and session.get('mode') == 'subscription' and session.get('status') == 'complete'
        and session.get('customer') == customer_id and session.get('subscription') == subscription_id
        and session.get('client_reference_id') == '1'
        and session.get('metadata', {}).get('attempt_id') == attempt['attempt_id'])
    result['STRIPE_CHECKOUT_SESSION'] = 'VERIFIED_BUSINESS_BINDING'
    require(session.get('payment_status') == 'paid')
    result['STRIPE_PAYMENT_STATUS'] = 'paid'
    customer = provider.get('customers/' + customer_id)
    require(customer.get('id') == customer_id and customer.get('livemode') is False
        and not customer.get('deleted') and customer.get('metadata', {}).get('business_id') == '1')
    objects = provider.subscriptions(customer_id)
    require(all(obj.get('livemode') is False and obj.get('customer') == customer_id for obj in objects))
    active = [obj for obj in objects if obj.get('status') not in ('canceled', 'incomplete_expired')]
    require(len(active) == 1 and active[0]['id'] == subscription_id)
    result['DUPLICATE_SUBSCRIPTIONS'] = 'NONE; ONE_COMPLETED_ATTEMPT_AND_ONE_NONTERMINAL_SUBSCRIPTION'
    obj = provider.get('subscriptions/' + subscription_id)
    require(obj.get('id') == subscription_id and obj.get('livemode') is False
        and obj.get('customer') == customer_id and obj.get('status') == 'active'
        and obj.get('metadata', {}).get('business_id') == '1'
        and obj.get('metadata', {}).get('attempt_id') == attempt['attempt_id'])
    entries = obj.get('items', {})
    require(entries.get('has_more') is False and len(entries.get('data', [])) == 1)
    item = entries['data'][0]
    require(item.get('quantity') == 1 and item.get('price', {}).get('id') == price)
    configured = provider.get('prices/' + price)
    require(configured.get('id') == price and configured.get('livemode') is False
        and configured.get('currency') == 'lkr' and configured.get('unit_amount') == 49900
        and configured.get('type') == 'recurring' and configured.get('billing_scheme') == 'per_unit'
        and configured.get('recurring', {}).get('interval') == 'month'
        and configured['recurring'].get('interval_count') == 1)
    result['STRIPE_SUBSCRIPTION'] = 'ACTIVE; PRO_MONTHLY_LKR_499'
    invoice_id = obj.get('latest_invoice')
    if isinstance(invoice_id, dict):
        invoice_id = invoice_id.get('id')
    invoice = provider.get('invoices/' + invoice_id)
    linked = invoice.get('subscription') or (invoice.get('parent') or {}).get('subscription_details', {}).get('subscription')
    require(invoice.get('id') == invoice_id and invoice.get('livemode') is False
        and invoice.get('status') == 'paid' and invoice.get('customer') == customer_id
        and linked == subscription_id and invoice.get('currency') == 'lkr'
        and invoice.get('amount_paid') == 49900 and invoice.get('amount_remaining') == 0)
    result['LATEST_INVOICE'] = 'PAID; LKR_499; CORRECT_CUSTOMER_AND_SUBSCRIPTION'
    require(sub['plan'] == 'PRO' and sub['status'] == 'ACTIVE' and sub['billing_interval'] == 'month')
    start = datetime.fromtimestamp(item['current_period_start'], timezone.utc).replace(tzinfo=None)
    end = datetime.fromtimestamp(item['current_period_end'], timezone.utc).replace(tzinfo=None)
    require(sub['started_at'] == start and sub['paid_through'] == end)
    result['MYSQL_SUBSCRIPTION'] = 'ACTIVE_PRO_MONTHLY; PROVIDER_PERIOD_MATCH'
    state = evaluate(SimpleNamespace(**sub), SimpleNamespace(**grant) if grant else None)
    require(state['effective_plan'] == 'PRO' and state['status'] == 'ACTIVE' and not state['trial_active'])
    result['EFFECTIVE_PLAN'] = 'PRO; VERIFIED_PAID_ENTITLEMENT'
    require(bool(receipts) and len(receipts) <= 100)
    paid_receipt = False
    for receipt in receipts:
        require(receipt['business_id'] == 1 and receipt['provider_mode'] == 'sandbox')
        event = provider.get('events/' + receipt['event_id'])
        payload = event.get('data', {}).get('object', {})
        require(event.get('id') == receipt['event_id'] and event.get('livemode') is False
            and event.get('type') == receipt['event_type'] and payload.get('customer') == customer_id)
        if event['type'] == 'invoice.paid' and payload.get('id') == invoice_id:
            require(payload.get('amount_paid') == receipt['amount_minor'] == 49900 and receipt['currency'] == 'lkr')
            paid_receipt = True
    require(paid_receipt)
    result['WEBHOOK_RECEIPTS'] = 'COMMITTED_RECEIPTS_MATCH_PROVIDER; LATEST_PAID_INVOICE_RECEIPT_PRESENT; RAW_SIGNATURE_NOT_RETAINED'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read-only', required=True, action='store_true')
    parser.parse_args()
    result = {key: 'UNVERIFIED' for key in FIELDS}
    stage = 'LOCAL_CONFIGURATION'
    status = 'BLOCKED'
    logging.disable(logging.CRITICAL)
    try:
        require(sys.stdin.isatty())
        secret, price = os.environ.get('STRIPE_TEST_SECRET_KEY', ''), os.environ.get('STRIPE_PRO_MONTH_PRICE', '')
        require(re.fullmatch(r'sk_test_[A-Za-z0-9]+', secret) and re.fullmatch(r'price_[A-Za-z0-9]+', price))
        warnings.simplefilter('error', getpass.GetPassWarning)
        password = getpass.getpass('Existing viva runtime password (hidden): ')
        require(bool(password))
        spec = importlib.util.spec_from_file_location('step362_guards', ROOT/'output/step322/guarded_viva_setup.py')
        guards = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guards)
        stage = 'MYSQL_READ_ONLY'
        connection = pymysql.connect(host='127.0.0.1', port=3306, database=TARGET, user=guards.RUNTIME,
            password=password, ssl=guards.tls_context(), autocommit=False,
            connect_timeout=5, read_timeout=15, write_timeout=15)
        try:
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
            guards.identity(connection, guards.RUNTIME, TARGET)
            guards.target_grants(connection, guards.RUNTIME, guards.RUNTIME_RIGHTS,
                guards.scalar(connection, 'SELECT @@GLOBAL.partial_revokes'))
            require(guards.rows(connection, 'SELECT version_num FROM alembic_version') == (('9d1a6f4e0c37',),))
            tables = guards.rows(connection, 'SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE=\'BASE TABLE\'', (TARGET,))
            require(len(tables) == 33 and {r[0] for r in tables} == guards.TABLES | {'alembic_version',
                'business_subscriptions', 'subscription_trial_grants', 'subscription_payment_events', 'subscription_checkout_attempts'})
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute('SELECT * FROM business_subscriptions WHERE business_id=1')
                sub = cursor.fetchone()
                cursor.execute('SELECT * FROM subscription_checkout_attempts WHERE business_id=1 ORDER BY created_at LIMIT 1001')
                attempts = cursor.fetchall()
                cursor.execute('SELECT * FROM subscription_payment_events WHERE business_id=1 ORDER BY received_at LIMIT 101')
                receipts = cursor.fetchall()
                cursor.execute('SELECT * FROM subscription_trial_grants WHERE business_id=1')
                grant = cursor.fetchone()
        finally:
            connection.close()
        stage = 'EXISTING_PROVIDER_EVIDENCE'
        with httpx.Client(base_url='https://api.stripe.com/v1/', timeout=12, trust_env=False,
            follow_redirects=False, transport=httpx.HTTPTransport(retries=0),
            headers={'Authorization': 'Bearer ' + secret, 'Stripe-Version': '2026-10-28.endive'}) as client:
            inspect((sub, attempts, receipts, grant), Reader(client), price, result, evaluator())
        status = 'PARTIAL'  # Historical financial preservation requires a prior baseline.
        stage = 'BILLING_EVIDENCE_VERIFIED'
    except (Exception, KeyboardInterrupt):
        pass  # Never print exceptions, response bodies, identifiers or credentials.
    print('STEP362_STATUS=' + status)
    print('BUSINESS=VIVA-BUSINESS-1')
    for key in FIELDS:
        print(key + '=' + result[key])
    print('FINANCIAL_DATA_PRESERVATION=UNVERIFIED; NO_PRIOR_COMPARABLE_BASELINE_CHECKED; NO_LEDGER_QUERIES_OR_WRITES')
    print('NEXT_ACTION=' + ('Review historical preservation evidence; do not purchase again' if stage == 'BILLING_EVIDENCE_VERIFIED'
        else 'STOP; ' + stage + ' incomplete or mismatched; preserve state; no automatic retry'))
    return 0 if stage == 'BILLING_EVIDENCE_VERIFIED' else 1


if __name__ == '__main__':
    sys.exit(main())

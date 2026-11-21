"""Step 351: four read-only Price GETs from the operator's existing environment.

Uses the project's HTTPX Stripe transport pattern (no Stripe SDK is installed).
No dotenv/app imports, environment edits, account overrides, writes or retries.
"""
import logging
import os
import re
import ssl
import sys

import httpx

EXPECTED = (
    ('PRO_MONTHLY', 'STRIPE_PRO_MONTH_PRICE', 49900, 'month'),
    ('PRO_YEARLY', 'STRIPE_PRO_YEAR_PRICE', 499000, 'year'),
    ('BUSINESS_MONTHLY', 'STRIPE_BUSINESS_MONTH_PRICE', 129900, 'month'),
    ('BUSINESS_YEARLY', 'STRIPE_BUSINESS_YEAR_PRICE', 1299000, 'year'),
)


ERROR_CODES = frozenset('''INVALID_COMMAND MISSING_ENVIRONMENT INVALID_TEST_KEY_FORMAT
INVALID_PRICE_ID_FORMAT DUPLICATE_PRICE_IDS BILLING_MUST_REMAIN_DISABLED
AUTHENTICATION_FAILED PERMISSION_DENIED PRICE_NOT_FOUND_OR_ACCOUNT_MISMATCH
RATE_LIMITED STRIPE_SERVER_ERROR UNEXPECTED_HTTP_STATUS INVALID_RESPONSE
LIVE_MODE_RESOURCE INACTIVE_PRICE CURRENCY_MISMATCH AMOUNT_MISMATCH
RECURRING_INTERVAL_MISMATCH UNSUPPORTED_PRICE_CONFIGURATION
PRO_PRODUCT_MISMATCH BUSINESS_PRODUCT_MISMATCH PLAN_PRODUCTS_NOT_DISTINCT
TLS_FAILURE NETWORK_OR_TLS_FAILURE NETWORK_TIMEOUT UNEXPECTED_LOCAL_ERROR'''.split())
FIELDS = {name for _, name, _, _ in EXPECTED} | {'STRIPE_TEST_SECRET_KEY'}
STAGES = {label for label, _, _, _ in EXPECTED} | {'CONFIGURATION', 'PRODUCT_MAPPING', 'LOCAL'}


class Stop(Exception):
    def __init__(self, code='UNEXPECTED_LOCAL_ERROR', stage='LOCAL', status=None, missing=()):
        self.code = code if code in ERROR_CODES else 'UNEXPECTED_LOCAL_ERROR'
        self.stage = stage if stage in STAGES else 'LOCAL'
        self.status = status if type(status) is int and 100 <= status <= 599 else None
        self.missing = tuple(name for name in sorted(FIELDS) if name in missing)
        super().__init__(self.code)  # Never retain provider messages or identifiers.


def require(ok, code='INVALID_RESPONSE', stage='LOCAL'):
    if not ok:
        raise Stop(code, stage)


def validate(price, ident, amount, interval, stage='LOCAL'):
    require(isinstance(price, dict), stage=stage)
    require(price.get('id') == ident and price.get('object') == 'price', stage=stage)
    require(price.get('livemode') is False, 'LIVE_MODE_RESOURCE', stage)
    require(price.get('active') is True, 'INACTIVE_PRICE', stage)
    require(price.get('currency') == 'lkr', 'CURRENCY_MISMATCH', stage)
    require(type(price.get('unit_amount')) is int and price['unit_amount'] == amount, 'AMOUNT_MISMATCH', stage)
    recurring = price.get('recurring')
    require(isinstance(recurring, dict) and price.get('type') == 'recurring', 'RECURRING_INTERVAL_MISMATCH', stage)
    require(recurring.get('interval') == interval and type(recurring.get('interval_count')) is int
        and recurring['interval_count'] == 1, 'RECURRING_INTERVAL_MISMATCH', stage)
    require(price.get('billing_scheme') == 'per_unit' and price.get('transform_quantity') is None
        and recurring.get('usage_type') == 'licensed', 'UNSUPPORTED_PRICE_CONFIGURATION', stage)
    require(isinstance(price.get('product'), str) and price['product'].startswith('prod_'), stage=stage)
    return price['product']


def network_code(error):
    if isinstance(error, httpx.TimeoutException):
        return 'NETWORK_TIMEOUT'
    current, seen = error, set()
    for _ in range(10):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        if isinstance(current, ssl.SSLError):
            return 'TLS_FAILURE'
        current = current.__cause__ or current.__context__
    return 'NETWORK_OR_TLS_FAILURE'


def verify(environ, transport=None):
    # All four GETs share one exact key and no Stripe-Account header: one account
    # context. No account/customer endpoint is queried or printed.
    secret = environ.get('STRIPE_TEST_SECRET_KEY', '')
    missing = [name for name in FIELDS if not environ.get(name)]
    if missing:
        raise Stop('MISSING_ENVIRONMENT', 'CONFIGURATION', missing=missing)
    # Inspect only: never change the feature flag. Unset retains backend false.
    require(environ.get('STRIPE_SANDBOX_ENABLED', 'false').lower() in ('false', '0', 'no', 'off'),
        'BILLING_MUST_REMAIN_DISABLED', 'CONFIGURATION')
    require(re.fullmatch(r'sk_test_[A-Za-z0-9]+', secret) is not None, 'INVALID_TEST_KEY_FORMAT', 'CONFIGURATION')
    ids = [environ.get(name, '') for _, name, _, _ in EXPECTED]
    for (label, _, _, _), ident in zip(EXPECTED, ids):
        require(re.fullmatch(r'price_[A-Za-z0-9]+', ident), 'INVALID_PRICE_ID_FORMAT', label)
    require(len(set(ids)) == 4, 'DUPLICATE_PRICE_IDS', 'CONFIGURATION')
    products = []
    with httpx.Client(base_url='https://api.stripe.com/v1/', timeout=12,
            trust_env=False, follow_redirects=False,
            transport=transport if transport is not None else httpx.HTTPTransport(retries=0),
            headers={'Authorization': 'Bearer ' + secret, 'Stripe-Version': '2026-10-28.endive'}) as client:
        for (label, _, amount, interval), ident in zip(EXPECTED, ids):
            try:
                response = client.get('prices/' + ident)  # Exactly GET; one attempt.
            except httpx.RequestError as error:
                raise Stop(network_code(error), label) from None
            if response.status_code != 200:
                code = {401:'AUTHENTICATION_FAILED', 403:'PERMISSION_DENIED',
                    404:'PRICE_NOT_FOUND_OR_ACCOUNT_MISMATCH', 429:'RATE_LIMITED'}.get(response.status_code,
                    'STRIPE_SERVER_ERROR' if response.status_code >= 500 else 'UNEXPECTED_HTTP_STATUS')
                raise Stop(code, label, status=response.status_code)
            try:
                price = response.json()
            except ValueError:
                raise Stop('INVALID_RESPONSE', label) from None
            products.append(validate(price, ident, amount, interval, label))
    require(products[0] == products[1], 'PRO_PRODUCT_MISMATCH', 'PRODUCT_MAPPING')
    require(products[2] == products[3], 'BUSINESS_PRODUCT_MISMATCH', 'PRODUCT_MAPPING')
    require(products[0] != products[2], 'PLAN_PRODUCTS_NOT_DISTINCT', 'PRODUCT_MAPPING')


def main():
    logging.disable(logging.CRITICAL)  # Never log resource URLs or identifiers.
    try:
        require(sys.argv[1:] in (['--read-only'], ['--read-only', '--diagnostic']), 'INVALID_COMMAND', 'LOCAL')
        verify(os.environ)
    except Exception as error:
        # No exception bodies, responses, headers, IDs, keys or provider messages.
        print('STEP351_STATUS=BLOCKED')
        diagnostic = error if isinstance(error, Stop) else Stop()
        print('DIAGNOSTIC_CODE=' + diagnostic.code)
        print('DIAGNOSTIC_STAGE=' + diagnostic.stage)
        if diagnostic.status is not None:
            print('HTTP_STATUS=' + str(diagnostic.status))
        if diagnostic.missing:
            print('MISSING_VARIABLES=' + ','.join(diagnostic.missing))
        for name in ('STRIPE_ACCOUNT_MODE', 'PRO_MONTHLY', 'PRO_YEARLY', 'BUSINESS_MONTHLY', 'BUSINESS_YEARLY', 'PRODUCT_MAPPING'):
            print(name + '=NOT_FULLY_VERIFIED')
        print('NEXT_ACTION=STOP; privately check environment and Stripe Price configuration; no automatic retry')
        return 1
    print('STEP351_STATUS=PASS')
    print('STRIPE_ACCOUNT_MODE=TEST; SAME_CREDENTIAL_ACCOUNT_CONTEXT; ALL_LIVEMODE_FALSE')
    for label, _, amount, interval in EXPECTED:
        print(label + '=PASS; LKR ' + format(amount // 100, ',') + '; ' + interval + '; ACTIVE')
    print('PRODUCT_MAPPING=PASS; PRO_PAIR_SAME; BUSINESS_PAIR_SAME; TWO_DISTINCT_PRODUCTS')
    print('NEXT_ACTION=Price verification complete; billing activation and Checkout testing remain separately authorized')
    return 0


if __name__ == '__main__':
    sys.exit(main())

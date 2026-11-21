"""Prepared one-GET diagnostic; no dotenv, application/DB imports or env edits.

Success prints only amount/currency/interval fields. Failure exits nonzero with
no response, URL, exception, identifier or credential output. Never retries.
"""
import logging
import os
import re
import sys
from decimal import Decimal

import httpx
from verify_stripe_prices import EXPECTED, Stop, require


def diagnose(environ, transport=None):
    _, name, expected, _ = EXPECTED[0]
    secret, ident = environ.get('STRIPE_TEST_SECRET_KEY', ''), environ.get(name, '')
    require(environ.get('STRIPE_SANDBOX_ENABLED', 'false').lower() in ('false', '0', 'off', 'no'))
    require(re.fullmatch(r'sk_test_[A-Za-z0-9]+', secret) and re.fullmatch(r'price_[A-Za-z0-9]+', ident))
    with httpx.Client(timeout=12, trust_env=False, follow_redirects=False,
            transport=transport if transport is not None else httpx.HTTPTransport(retries=0),
            headers={'Authorization':'Bearer '+secret, 'Stripe-Version':'2026-10-28.endive'}) as client:
        response=client.get('https://api.stripe.com/v1/prices/'+ident)
        require(response.status_code==200)
        price=response.json()
    require(isinstance(price,dict) and price.get('object')=='price' and price.get('id')==ident
        and price.get('livemode') is False)
    currency=price.get('currency')
    recurring=price.get('recurring')
    require(currency in ('lkr','usd','eur','gbp','inr') or (isinstance(currency,str) and re.fullmatch('[a-z]{3}',currency)))
    interval=recurring.get('interval') if isinstance(recurring,dict) else None
    require(interval in ('day','week','month','year',None))
    amount=price.get('unit_amount')
    if type(amount) is int and amount >= 0:
        actual=str(amount)
    elif amount is None:
        # Fractional per-unit prices may use unit_amount_decimal. Preserve the
        # number exactly; never round or convert it to a misleading integer.
        decimal=price.get('unit_amount_decimal')
        if decimal is None:
            actual='UNAVAILABLE'  # e.g. tiered Price: no single unit amount.
        else:
            require(isinstance(decimal,str) and re.fullmatch(r'[0-9]{1,20}(?:\.[0-9]{1,12})?',decimal))
            value=Decimal(decimal)
            require(value.is_finite() and value>=0)
            actual=format(value,'f')
    else:
        raise Stop()
    return {'EXPECTED_UNIT_AMOUNT':str(expected),'ACTUAL_UNIT_AMOUNT':actual,
        'CURRENCY':currency,'INTERVAL':interval or 'NON_RECURRING'}


def main():
    logging.disable(logging.CRITICAL)
    try:
        require(sys.argv[1:]==['--read-only'])
        result=diagnose(os.environ)
    except Exception:
        return 1  # Never leak exception/provider contents, even on TLS failures.
    for name,value in result.items(): print(name+'='+value)
    return 0


if __name__=='__main__': sys.exit(main())

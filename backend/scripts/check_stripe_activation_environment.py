"""Local-only pre-activation check. No API/DB calls, env edits or server launch."""
import getpass
import hmac
import os
import re
import sys
import warnings

from verify_stripe_portal_readiness import PRICE_NAMES


def check(environ, listener_secret):
    prices=[environ.get(name,'') for name in PRICE_NAMES]
    return (environ.get('STRIPE_SANDBOX_ENABLED')=='false'
        and bool(re.fullmatch(r'sk_test_[A-Za-z0-9]+',environ.get('STRIPE_TEST_SECRET_KEY','')))
        and len(set(prices))==4 and all(re.fullmatch(r'price_[A-Za-z0-9]+',p) for p in prices)
        and bool(re.fullmatch(r'bpc_[A-Za-z0-9]+',environ.get('STRIPE_PORTAL_CONFIGURATION','')))
        and environ.get('STRIPE_RETURN_ORIGIN')=='http://127.0.0.1:5176'
        and bool(re.fullmatch(r'whsec_[A-Za-z0-9]+',listener_secret))
        and hmac.compare_digest(listener_secret,environ.get('STRIPE_WEBHOOK_SECRET','')))


def main():
    if sys.argv[1:]!=['--check-only'] or not sys.stdin.isatty():
        print('STEP356_LOCAL_CHECK=BLOCKED; PRIVATE_INTERACTIVE_TERMINAL_REQUIRED')
        return 1
    warnings.simplefilter('error',getpass.GetPassWarning)
    try:
        secret=getpass.getpass('Paste signing secret from the CURRENT running Stripe CLI listener (hidden): ')
        ok=check(os.environ,secret)
    except Exception:
        ok=False
    print('STEP356_LOCAL_CHECK='+('PASS' if ok else 'BLOCKED'))
    print('ENVIRONMENT_AND_LISTENER_SECRET='+('MATCH; BILLING_REMAINS_DISABLED' if ok else 'NOT_CONFIRMED; STOP'))
    return 0 if ok else 1


if __name__=='__main__': sys.exit(main())

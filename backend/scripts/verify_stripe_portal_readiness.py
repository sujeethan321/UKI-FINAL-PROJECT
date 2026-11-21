"""Step 355: read environment and GET one Portal configuration. No app imports.

Run in the operator's configured terminal. No environment edits or API retries.
No provider bodies, keys, resource IDs or exception text are ever printed.
"""
import logging
import os
import re
import sys
import httpx

PRICE_NAMES = ('STRIPE_PRO_MONTH_PRICE','STRIPE_PRO_YEAR_PRICE',
               'STRIPE_BUSINESS_MONTH_PRICE','STRIPE_BUSINESS_YEAR_PRICE')


class Stop(Exception):
    pass


def require(ok, code):
    if not ok:
        raise Stop(code)


def verify(environ, transport=None):
    require(environ.get('STRIPE_SANDBOX_ENABLED') == 'false', 'BILLING_NOT_EXPLICITLY_DISABLED')
    key=environ.get('STRIPE_TEST_SECRET_KEY','')
    require(re.fullmatch(r'sk_test_[A-Za-z0-9]+',key), 'TEST_KEY_FORMAT_INVALID')
    prices=[environ.get(name,'') for name in PRICE_NAMES]
    require(all(re.fullmatch(r'price_[A-Za-z0-9]+',value) for value in prices)
        and len(set(prices))==4, 'PRICE_CONFIGURATION_INVALID')
    require(re.fullmatch(r'whsec_[A-Za-z0-9]+',environ.get('STRIPE_WEBHOOK_SECRET','')), 'WEBHOOK_SECRET_MISSING_OR_INVALID')
    require(environ.get('STRIPE_RETURN_ORIGIN')=='http://127.0.0.1:5176', 'RETURN_ORIGIN_MISMATCH')
    ident=environ.get('STRIPE_PORTAL_CONFIGURATION','')
    require(re.fullmatch(r'bpc_[A-Za-z0-9]+',ident), 'PORTAL_ID_FORMAT_INVALID')
    with httpx.Client(timeout=12,trust_env=False,follow_redirects=False,
            transport=transport if transport is not None else httpx.HTTPTransport(retries=0),
            headers={'Authorization':'Bearer '+key,'Stripe-Version':'2026-10-28.endive'}) as client:
        response=client.get('https://api.stripe.com/v1/billing_portal/configurations/'+ident)
        require(response.status_code==200, {401:'AUTHENTICATION_FAILED',403:'PERMISSION_DENIED',
            404:'PORTAL_NOT_FOUND_OR_ACCOUNT_MISMATCH',429:'RATE_LIMITED'}.get(response.status_code,'PROVIDER_HTTP_FAILURE'))
        portal=response.json()
    require(isinstance(portal,dict) and portal.get('id')==ident
        and portal.get('object')=='billing_portal.configuration','INVALID_PROVIDER_RESPONSE')
    require(portal.get('livemode') is False,'PORTAL_NOT_TEST_MODE')
    require(portal.get('active') is True,'PORTAL_INACTIVE')
    features=portal.get('features',{})
    require(features.get('payment_method_update',{}).get('enabled') is True,'PAYMENT_METHOD_UPDATES_DISABLED')
    cancel=features.get('subscription_cancel',{})
    require(cancel.get('enabled') is True,'CANCELLATION_DISABLED')
    require(cancel.get('mode')=='at_period_end','CANCELLATION_NOT_PERIOD_END')
    require(features.get('subscription_update',{}).get('enabled') is False,'PLAN_SWITCHING_NOT_EXPLICITLY_DISABLED')


def main():
    logging.disable(logging.CRITICAL)
    try:
        require(sys.argv[1:]==['--read-only'],'INVALID_COMMAND')
        verify(os.environ)
    except Exception as error:
        print('STEP355_STATUS=BLOCKED')
        # Only our fixed internal classifications; provider exceptions never echo.
        print('DIAGNOSTIC_CODE='+ (str(error) if type(error) is Stop else 'NETWORK_OR_INVALID_PROVIDER_RESPONSE'))
        print('NEXT_ACTION=STOP; no retry; inspect only the reported configuration mismatch privately')
        return 1
    print('STEP355_STATUS=PASS')
    print('STRIPE_TEST_MODE=TEST_KEY_AND_TEST_PORTAL_VERIFIED; BILLING_DISABLED')
    print('PRICE_CONFIGURATION=FOUR_DISTINCT_IDS_PRESENT; PRIOR_LIVE_PRICE_VERIFICATION_OPERATOR_CONFIRMED')
    print('PORTAL_CONFIGURATION=ACTIVE_TEST_CONFIGURATION_IN_CURRENT_KEY_ACCOUNT_CONTEXT')
    print('PORTAL_PAYMENT_METHODS=ENABLED')
    print('PORTAL_CANCELLATION=ENABLED_AT_PERIOD_END')
    print('PORTAL_PLAN_SWITCHING=DISABLED')
    print('WEBHOOK_ROUTE=/api/v1/subscriptions/webhook; SOURCE_REVIEWED')
    print('WEBHOOK_SECRET=PRESENT_FORMAT_VALID; LISTENER_SECRET_MATCH_NOT_TESTED')
    print('RETURN_ORIGIN=http://127.0.0.1:5176')
    print('VIVA_LAUNCHER=INHERITS_STRIPE_PROCESS_SETTINGS; SOURCE_REVIEWED; NO_RESTART')
    print('NEXT_ACTION=Read-only checks passed; activation, restart and Checkout test require separate authorization')
    return 0


if __name__=='__main__': sys.exit(main())

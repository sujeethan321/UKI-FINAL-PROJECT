"""Mock-transport tests only. No real credentials, databases or Stripe requests."""
import importlib.util
import io
import ssl
from contextlib import redirect_stdout
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

import httpx

path = Path(__file__).resolve().parents[1] / 'scripts/verify_stripe_prices.py'
spec = importlib.util.spec_from_file_location('offline_price_verifier', path)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class PriceTests(TestCase):
    def setUp(self):
        self.env = {'STRIPE_TEST_SECRET_KEY': 'sk_test_OfflineOnly123'}
        self.prices = {}
        self.calls = []
        for n, (_, name, amount, interval) in enumerate(verifier.EXPECTED):
            ident = 'price_Offline' + str(n)
            self.env[name] = ident
            self.prices[ident] = dict(id=ident, object='price', livemode=False, active=True,
                currency='lkr', unit_amount=amount, type='recurring', billing_scheme='per_unit',
                product='prod_Pro' if n < 2 else 'prod_Business',
                recurring=dict(interval=interval, interval_count=1, usage_type='licensed'))

    def handler(self, request):
        self.calls.append(request)
        return httpx.Response(200, json=self.prices[request.url.path.split('/')[-1]])

    def test_four_gets_one_key_no_account_override_and_no_environment_edits(self):
        before = self.env.copy()
        verifier.verify(self.env, httpx.MockTransport(self.handler))
        self.assertEqual(self.env, before)
        self.assertEqual(len(self.calls), 4)
        for request in self.calls:
            self.assertEqual(request.method, 'GET')
            self.assertEqual(request.url.host, 'api.stripe.com')
            self.assertEqual(request.headers['authorization'], 'Bearer ' + self.env['STRIPE_TEST_SECRET_KEY'])
            self.assertNotIn('stripe-account', request.headers)

    def test_mismatched_modes_amounts_currency_interval_activity_and_products_stop(self):
        ident = self.env['STRIPE_PRO_MONTH_PRICE']
        for changes in [dict(livemode=True), dict(active=False), dict(unit_amount=499),
                dict(currency='usd'), dict(recurring=dict(interval='year', interval_count=1, usage_type='licensed')),
                dict(product='prod_Wrong'), dict(transform_quantity={'divide_by': 10})]:
            original = self.prices[ident].copy()
            self.prices[ident].update(changes)
            with self.assertRaises(verifier.Stop): verifier.verify(self.env, httpx.MockTransport(self.handler))
            self.prices[ident] = original

    def test_unexpected_http_failure_stops_after_first_request_without_retry(self):
        def fail(request):
            self.calls.append(request)
            return httpx.Response(429, json={'error': {'message': 'private provider text'}})
        with self.assertRaises(verifier.Stop): verifier.verify(self.env, httpx.MockTransport(fail))
        self.assertEqual(len(self.calls), 1)

    def test_incomplete_or_live_credentials_make_no_requests_and_output_is_sanitized(self):
        for env in [{}, {**self.env, 'STRIPE_TEST_SECRET_KEY': 'sk_live_FORBIDDEN'}]:
            with self.assertRaises(verifier.Stop): verifier.verify(env, httpx.MockTransport(self.handler))
        self.assertEqual(self.calls, [])
        output = io.StringIO()
        with patch.object(verifier.sys, 'argv', ['verify', '--read-only']), \
             patch.object(verifier, 'verify', side_effect=ValueError('sk_test_DO_NOT_PRINT price_DO_NOT_PRINT')), redirect_stdout(output):
            self.assertEqual(verifier.main(), 1)
        self.assertNotIn('DO_NOT_PRINT', output.getvalue())

    def test_configuration_failures_are_specific_and_make_no_requests(self):
        cases = [({}, 'MISSING_ENVIRONMENT'),
            ({**self.env, 'STRIPE_TEST_SECRET_KEY':'sk_live_PRIVATE'}, 'INVALID_TEST_KEY_FORMAT'),
            ({**self.env, 'STRIPE_PRO_MONTH_PRICE':'prod_PRIVATE'}, 'INVALID_PRICE_ID_FORMAT'),
            ({**self.env, 'STRIPE_PRO_MONTH_PRICE':self.env['STRIPE_PRO_YEAR_PRICE']}, 'DUPLICATE_PRICE_IDS'),
            ({**self.env, 'STRIPE_SANDBOX_ENABLED':'true'}, 'BILLING_MUST_REMAIN_DISABLED')]
        for env, code in cases:
            before = env.copy()
            with self.assertRaises(verifier.Stop) as err:
                verifier.verify(env,httpx.MockTransport(self.handler))
            self.assertEqual(err.exception.code,code)
            self.assertEqual(env,before)
        self.assertEqual(self.calls,[])

    def test_http_categories_do_not_read_or_print_sensitive_bodies_or_retry(self):
        for status,code in [(401,'AUTHENTICATION_FAILED'),(403,'PERMISSION_DENIED'),
                (404,'PRICE_NOT_FOUND_OR_ACCOUNT_MISMATCH'),(429,'RATE_LIMITED'),
                (500,'STRIPE_SERVER_ERROR'),(302,'UNEXPECTED_HTTP_STATUS')]:
            calls=[]
            def response(request):
                calls.append(request)
                return httpx.Response(status,text='sk_test_PRIVATE price_PRIVATE customer_PRIVATE')
            with self.assertRaises(verifier.Stop) as err:
                verifier.verify(self.env,httpx.MockTransport(response))
            self.assertEqual(err.exception.code,code)
            self.assertEqual(err.exception.stage,'PRO_MONTHLY')
            self.assertEqual(err.exception.status,status)
            self.assertEqual(len(calls),1)
            self.assertNotIn('PRIVATE',str(err.exception))

    def test_price_attribute_and_product_categories_are_specific(self):
        ident=self.env['STRIPE_PRO_MONTH_PRICE']
        cases=[({'livemode':True},'LIVE_MODE_RESOURCE'),({'active':False},'INACTIVE_PRICE'),
            ({'currency':'usd'},'CURRENCY_MISMATCH'),({'unit_amount':499},'AMOUNT_MISMATCH'),
            ({'recurring':{'interval':'year','interval_count':1}},'RECURRING_INTERVAL_MISMATCH'),
            ({'transform_quantity':{'divide_by':10}},'UNSUPPORTED_PRICE_CONFIGURATION'),
            ({'product':'prod_OTHER'},'PRO_PRODUCT_MISMATCH'),({'id':'price_WRONG'},'INVALID_RESPONSE')]
        for changes,code in cases:
            before=self.prices[ident].copy()
            self.prices[ident].update(changes)
            with self.assertRaises(verifier.Stop) as err:
                verifier.verify(self.env,httpx.MockTransport(self.handler))
            self.assertEqual(err.exception.code,code)
            self.prices[ident]=before
        self.prices[self.env['STRIPE_BUSINESS_MONTH_PRICE']]['product']='prod_WRONG'
        with self.assertRaises(verifier.Stop) as err:
            verifier.verify(self.env,httpx.MockTransport(self.handler))
        self.assertEqual(err.exception.code,'BUSINESS_PRODUCT_MISMATCH')
        for price in self.prices.values(): price['product']='prod_SAME'
        with self.assertRaises(verifier.Stop) as err:
            verifier.verify(self.env,httpx.MockTransport(self.handler))
        self.assertEqual(err.exception.code,'PLAN_PRODUCTS_NOT_DISTINCT')

    def test_timeout_tls_and_generic_connection_failure_are_sanitized(self):
        tls=httpx.ConnectError('private address and key')
        tls.__cause__=ssl.SSLCertVerificationError('private TLS details')
        for error,code in [(httpx.ReadTimeout('private'), 'NETWORK_TIMEOUT'),
                (tls,'TLS_FAILURE'),(httpx.ConnectError('private'), 'NETWORK_OR_TLS_FAILURE')]:
            calls=[]
            def fail(request):
                calls.append(request)
                raise error
            with self.assertRaises(verifier.Stop) as err:
                verifier.verify(self.env,httpx.MockTransport(fail))
            self.assertEqual(err.exception.code,code)
            self.assertEqual(len(calls),1)
            self.assertNotIn('private',str(err.exception))

    def test_invalid_json_and_nonobject_responses_are_classified(self):
        for body in [b'private-not-json',b'[]']:
            with self.assertRaises(verifier.Stop) as err:
                verifier.verify(self.env,httpx.MockTransport(lambda request:httpx.Response(200,content=body)))
            self.assertEqual(err.exception.code,'INVALID_RESPONSE')

    def test_diagnostic_command_prints_only_allowlisted_fields(self):
        error=verifier.Stop('AUTHENTICATION_FAILED','PRO_MONTHLY',status=401)
        output=io.StringIO()
        with patch.object(verifier.sys,'argv',['verify','--read-only','--diagnostic']), \
             patch.object(verifier,'verify',side_effect=error),redirect_stdout(output):
            self.assertEqual(verifier.main(),1)
        self.assertIn('DIAGNOSTIC_CODE=AUTHENTICATION_FAILED',output.getvalue())
        self.assertIn('DIAGNOSTIC_STAGE=PRO_MONTHLY',output.getvalue())
        self.assertIn('HTTP_STATUS=401',output.getvalue())
        for private in ['sk_test_','price_','prod_','cus_','Authorization','Traceback']:
            self.assertNotIn(private,output.getvalue())


if __name__ == '__main__': main(verbosity=2)

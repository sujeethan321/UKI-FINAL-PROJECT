"""Mock-only tests; never imports backend configuration or database modules."""
import sys
from pathlib import Path
from unittest import TestCase,main
import httpx

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import verify_stripe_portal_readiness as checker


class PortalTests(TestCase):
    def setUp(self):
        self.env={name:'price_Offline'+str(n) for n,name in enumerate(checker.PRICE_NAMES)}
        self.env.update(STRIPE_TEST_SECRET_KEY='sk_test_Offline',STRIPE_WEBHOOK_SECRET='whsec_Offline',
            STRIPE_PORTAL_CONFIGURATION='bpc_Offline',STRIPE_RETURN_ORIGIN='http://127.0.0.1:5176',STRIPE_SANDBOX_ENABLED='false')
        self.portal=dict(id='bpc_Offline',object='billing_portal.configuration',livemode=False,active=True,
            features=dict(payment_method_update=dict(enabled=True),subscription_cancel=dict(enabled=True,mode='at_period_end'),
                subscription_update=dict(enabled=False)))
        self.calls=[]
    def handler(self,request):
        self.calls.append(request)
        return httpx.Response(200,json=self.portal)
    def test_one_get_preserves_environment_and_uses_no_account_override(self):
        before=self.env.copy()
        checker.verify(self.env,httpx.MockTransport(self.handler))
        self.assertEqual(self.env,before)
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.calls[0].method,'GET')
        self.assertNotIn('stripe-account',self.calls[0].headers)
    def test_unsafe_local_configuration_blocks_before_network(self):
        for changes in [dict(STRIPE_TEST_SECRET_KEY='sk_live_Forbidden'),dict(STRIPE_SANDBOX_ENABLED='true'),
                dict(STRIPE_RETURN_ORIGIN='https://other.example'),dict(STRIPE_WEBHOOK_SECRET='')]:
            with self.assertRaises(checker.Stop): checker.verify({**self.env,**changes},httpx.MockTransport(self.handler))
        self.assertEqual(self.calls,[])
    def test_each_portal_mismatch_fails_closed(self):
        for field,value in [('livemode',True),('active',False)]:
            old=self.portal[field]; self.portal[field]=value
            with self.assertRaises(checker.Stop): checker.verify(self.env,httpx.MockTransport(self.handler))
            self.portal[field]=old
        for group,field,value in [('payment_method_update','enabled',False),('subscription_cancel','enabled',False),
                ('subscription_cancel','mode','immediately'),('subscription_update','enabled',True)]:
            old=self.portal['features'][group][field]; self.portal['features'][group][field]=value
            with self.assertRaises(checker.Stop): checker.verify(self.env,httpx.MockTransport(self.handler))
            self.portal['features'][group][field]=old
    def test_http_failure_is_not_retried_and_body_is_not_disclosed(self):
        def fail(request):
            self.calls.append(request)
            return httpx.Response(401,text='sk_test_PRIVATE bpc_PRIVATE')
        with self.assertRaises(checker.Stop) as error: checker.verify(self.env,httpx.MockTransport(fail))
        self.assertEqual(str(error.exception),'AUTHENTICATION_FAILED')
        self.assertEqual(len(self.calls),1)


if __name__=='__main__': main(verbosity=2)

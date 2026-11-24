"""Synthetic HTTPX MockTransport only; no Stripe or MySQL requests."""
import sys
from pathlib import Path
from unittest import TestCase, main
import httpx

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import diagnose_pro_monthly_amount as diagnostic


class AmountTests(TestCase):
    def setUp(self):
        self.env={'STRIPE_TEST_SECRET_KEY':'sk_test_OfflineOnly', 'STRIPE_PRO_MONTH_PRICE':'price_Offline'}
        self.price=dict(id='price_Offline',object='price',livemode=False,currency='lkr',
            unit_amount=49900,recurring=dict(interval='month'))
        self.calls=[]
    def handler(self,request):
        self.calls.append(request)
        return httpx.Response(200,json=self.price)
    def test_expected_conversion_and_one_get_without_env_edits_or_ids_in_output(self):
        before=self.env.copy()
        result=diagnostic.diagnose(self.env,httpx.MockTransport(self.handler))
        self.assertEqual(result,dict(EXPECTED_UNIT_AMOUNT='49900',ACTUAL_UNIT_AMOUNT='49900',CURRENCY='lkr',INTERVAL='month'))
        self.assertEqual(499*100,int(result['EXPECTED_UNIT_AMOUNT']))
        self.assertEqual(self.env,before)
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.calls[0].method,'GET')
        self.assertNotIn('Offline',str(result))
    def test_wrong_amount_is_reported_without_conversion_or_repair(self):
        self.price['unit_amount']=499
        self.assertEqual(diagnostic.diagnose(self.env,httpx.MockTransport(self.handler))['ACTUAL_UNIT_AMOUNT'],'499')
    def test_null_and_fractional_amounts_are_never_fabricated_or_rounded(self):
        self.price['unit_amount']=None
        self.assertEqual(diagnostic.diagnose(self.env,httpx.MockTransport(self.handler))['ACTUAL_UNIT_AMOUNT'],'UNAVAILABLE')
        self.price['unit_amount_decimal']='49900.125'
        self.assertEqual(diagnostic.diagnose(self.env,httpx.MockTransport(self.handler))['ACTUAL_UNIT_AMOUNT'],'49900.125')
    def test_live_mode_enabled_billing_and_failed_requests_stop_without_retry(self):
        with self.assertRaises(diagnostic.Stop):
            diagnostic.diagnose({**self.env,'STRIPE_SANDBOX_ENABLED':'true'},httpx.MockTransport(self.handler))
        self.assertEqual(self.calls,[])
        self.price['livemode']=True
        with self.assertRaises(diagnostic.Stop): diagnostic.diagnose(self.env,httpx.MockTransport(self.handler))
        self.assertEqual(len(self.calls),1)


if __name__=='__main__': main(verbosity=2)

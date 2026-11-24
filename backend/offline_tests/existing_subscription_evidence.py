"""Offline Step 362 evidence checks; fake provider, no database/app imports."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'scripts/verify_existing_viva_subscription.py'
spec = importlib.util.spec_from_file_location('existing_evidence', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
        start, end = now - timedelta(days=1), now + timedelta(days=29)
        self.sub = dict(business_id=1, provider_mode='sandbox', plan='PRO', status='ACTIVE',
            billing_interval='month', stripe_customer_id='cus_fake', stripe_subscription_id='sub_fake',
            started_at=start, paid_through=end)
        self.attempt = dict(business_id=1, plan='PRO', billing_interval='month', price_id='price_fake',
            status='COMPLETE', active_business_id=None, stripe_customer_id='cus_fake',
            stripe_session_id='cs_test_fake', attempt_id='fake')
        self.receipt = dict(event_id='evt_fake', business_id=1, provider_mode='sandbox',
            event_type='invoice.paid', amount_minor=49900, currency='lkr')
        invoice = dict(id='in_fake', livemode=False, status='paid', customer='cus_fake',
            parent=dict(subscription_details=dict(subscription='sub_fake')),
            currency='lkr', amount_paid=49900, amount_remaining=0)
        self.objects = {
            'checkout/sessions/cs_test_fake': dict(id='cs_test_fake', livemode=False, mode='subscription',
                status='complete', customer='cus_fake', subscription='sub_fake', client_reference_id='1',
                metadata=dict(attempt_id='fake'), payment_status='paid'),
            'customers/cus_fake': dict(id='cus_fake', livemode=False, metadata=dict(business_id='1')),
            'subscriptions/sub_fake': dict(id='sub_fake', livemode=False, customer='cus_fake', status='active',
                metadata=dict(business_id='1', attempt_id='fake'), latest_invoice='in_fake',
                items=dict(has_more=False, data=[dict(quantity=1, price=dict(id='price_fake'),
                    current_period_start=int(start.replace(tzinfo=timezone.utc).timestamp()),
                    current_period_end=int(end.replace(tzinfo=timezone.utc).timestamp()))])),
            'prices/price_fake': dict(id='price_fake', livemode=False, currency='lkr', unit_amount=49900,
                type='recurring', billing_scheme='per_unit', recurring=dict(interval='month', interval_count=1)),
            'invoices/in_fake': invoice,
            'events/evt_fake': dict(id='evt_fake', livemode=False, type='invoice.paid', data=dict(object=deepcopy(invoice))),
        }
        self.subscriptions = [self.objects['subscriptions/sub_fake']]
        self.provider = type('FakeReader', (), {})()
        self.provider.get = lambda path: self.objects[path]
        self.provider.subscriptions = lambda customer: self.subscriptions

    def inspect(self, attempts=None, receipts=None):
        result = {field: 'UNVERIFIED' for field in module.FIELDS}
        module.inspect((self.sub, attempts if attempts is not None else [self.attempt],
            receipts if receipts is not None else [self.receipt], None), self.provider,
            'price_fake', result, module.evaluator())
        return result

    def test_existing_paid_evidence_matches_application_entitlement(self):
        self.assertIn('VERIFIED_PAID', self.inspect()['EFFECTIVE_PLAN'])

    def test_unpaid_wrong_business_and_live_resources_stop(self):
        session = self.objects['checkout/sessions/cs_test_fake']
        for key, value in [('payment_status', 'unpaid'), ('client_reference_id', '2'), ('livemode', True)]:
            with patch.dict(session, {key: value}), self.assertRaises(module.Stop):
                self.inspect()

    def test_duplicate_attempts_and_provider_subscriptions_stop(self):
        with self.assertRaises(module.Stop):
            self.inspect(attempts=[self.attempt, deepcopy(self.attempt)])
        self.subscriptions.append({**self.subscriptions[0], 'id': 'sub_other'})
        with self.assertRaises(module.Stop):
            self.inspect()

    def test_unrelated_invoice_and_missing_receipt_stop(self):
        with patch.dict(self.objects['invoices/in_fake'], {'parent': {}, 'subscription': 'sub_other'}), self.assertRaises(module.Stop):
            self.inspect()
        with self.assertRaises(module.Stop):
            self.inspect(receipts=[])

    def test_stale_mysql_state_and_trial_only_do_not_pass(self):
        with patch.dict(self.sub, {'paid_through': datetime(2000, 1, 1)}), self.assertRaises(module.Stop):
            self.inspect()
        with patch.dict(self.sub, {'status': 'TRIALING'}), self.assertRaises(module.Stop):
            self.inspect()

    def test_reader_only_permits_get_on_existing_resource_paths(self):
        import httpx
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={'livemode': False})
        with httpx.Client(base_url='https://api.stripe.com/v1/', transport=httpx.MockTransport(respond)) as client:
            reader = module.Reader(client)
            reader.get('checkout/sessions/cs_test_fake')
            for path in ['checkout/sessions', 'billing_portal/sessions', 'subscriptions/sub_fake/cancel']:
                with self.assertRaises(module.Stop):
                    reader.get(path)
        self.assertEqual([request.method for request in requests], ['GET'])


if __name__ == '__main__':
    unittest.main(verbosity=2)

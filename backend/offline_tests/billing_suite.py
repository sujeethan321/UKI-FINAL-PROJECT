"""SQLite and mocked Stripe only; network interdiction inherited from base suite."""
import hashlib
import hmac
import json
import tempfile
import threading
import ast
import sys
from types import ModuleType
from datetime import timedelta, timezone
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

import subscription_suite as base
from pydantic import SecretStr
from fastapi import HTTPException, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, create_engine, func
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.subscription import SubscriptionCheckoutAttempt as Attempt, SubscriptionPaymentEvent, BusinessSubscription, SubscriptionTrialGrant
from app.services import subscription_billing as billing, stripe_sandbox as stripe
from app.schemas.subscription import CheckoutRequest
import httpx

base.TABLES.append(Attempt.__table__)
OPTIONS = dict(STRIPE_SANDBOX_ENABLED=True, STRIPE_TEST_SECRET_KEY=SecretStr('sk_test_offline_only'),
    STRIPE_WEBHOOK_SECRET=SecretStr('whsec_offline_only'), STRIPE_RETURN_ORIGIN='http://127.0.0.1:5176',
    STRIPE_PORTAL_CONFIGURATION='bpc_offline', STRIPE_PRO_MONTH_PRICE='price_pm', STRIPE_PRO_YEAR_PRICE='price_py',
    STRIPE_BUSINESS_MONTH_PRICE='price_bm', STRIPE_BUSINESS_YEAR_PRICE='price_by')


class Fake(stripe.Provider):
    def __init__(self):
        self.sessions, self.subscriptions, self.calls = [], [], []
        self.interrupt = False

    def call(self, method, path, data=None, key=None):
        self.calls.append((method, path, data, key))
        if path.startswith('/prices/'):
            choice = next(pair for pair, value in stripe.price_map().items() if path.endswith('/' + value))
            return dict(id=path.split('/')[-1], livemode=False, active=True, type='recurring', billing_scheme='per_unit', currency='lkr',
                unit_amount={('PRO','month'):49900,('PRO','year'):499000,('BUSINESS','month'):129900,('BUSINESS','year'):1299000}[choice],
                recurring=dict(interval=choice[1], interval_count=1, usage_type='licensed'))
        if path == '/customers':
            return dict(id='cus_offline', livemode=False)
        if path.startswith('/customers/'):
            return dict(id='cus_offline', livemode=False, metadata=dict(business_id='10'))
        if path == '/checkout/sessions' and method == 'POST':
            obj = dict(id='cs_test_offline', livemode=False, mode='subscription', status='open',
                customer='cus_offline', client_reference_id='10', metadata=dict(attempt_id=data['metadata[attempt_id]']),
                url='https://checkout.stripe.com/c/pay/cs_test_offline')
            self.sessions.append(obj)
            if self.interrupt:
                self.interrupt = False
                raise HTTPException(502, 'Simulated lost response')
            return obj
        if path.startswith('/checkout/sessions/'):
            return self.sessions[0]
        if path.startswith('/billing_portal/configurations/'):
            return dict(livemode=False, active=True, features=dict(subscription_update=dict(enabled=False),
                subscription_cancel=dict(enabled=True, mode='at_period_end'), payment_method_update=dict(enabled=True)))
        if path == '/billing_portal/sessions':
            return dict(url='https://billing.stripe.com/p/session/test_offline')
        raise AssertionError((method, path))

    def pages(self, path, params):
        if path == '/checkout/sessions': return self.sessions
        if path == '/subscriptions': return self.subscriptions
        raise AssertionError(path)


class BillingTests(TestCase):
    def setUp(self):
        self.options = patch.multiple(base.config.settings, create=True, **OPTIONS)
        self.options.start()
        self.engine = create_engine('sqlite://', poolclass=base.StaticPool, connect_args={'check_same_thread':False})
        base.create_tables(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        base.seed(self.db)
        self.user = self.db.get(base.User, 2)
        self.db.get(base.Business, 10).approval_status = 'approved'
        self.db.commit()
        self.provider = Fake()
        self.payload = CheckoutRequest(plan='PRO', billing_interval='month', request_id='offline_request_123456')

    def tearDown(self):
        self.db.close(); self.engine.dispose(); self.options.stop()

    def checkout(self, payload=None):
        return billing.checkout(self.db, self.user, 10, payload or self.payload, self.provider)

    def paid(self, status='active', invoice='paid'):
        now = billing.utc_now().replace(microsecond=0)
        self.provider.subscriptions = [dict(id='sub_offline', created=1, livemode=False, customer='cus_offline',
            metadata=dict(business_id='10'), status=status, cancel_at_period_end=False,
            items=dict(has_more=False, data=[dict(quantity=1, price=dict(id='price_pm'),
                current_period_start=int((now-timedelta(days=1)).replace(tzinfo=timezone.utc).timestamp()),
                current_period_end=int((now+timedelta(days=29)).replace(tzinfo=timezone.utc).timestamp()))]),
            latest_invoice=dict(id='in_offline', livemode=False, status=invoice, customer='cus_offline', currency='lkr'))]

    def event(self, ident='evt_offline', kind='invoice.paid'):
        return dict(id=ident, type=kind, livemode=False,
            data=dict(object=dict(customer='cus_offline', currency='lkr', amount_paid=49900)))

    def test_four_exact_price_mappings_and_reject_bad_provider_price(self):
        for (plan, interval), ident in stripe.price_map().items():
            self.assertEqual(self.provider.verify_price(ident, plan, interval)['id'], ident)
        with patch.object(self.provider, 'call', return_value={'livemode': True}), self.assertRaises(HTTPException):
            self.provider.verify_price('price_pm', 'PRO', 'month')

    def test_real_rest_adapter_is_pinned_sandbox_only_and_does_not_follow_or_retry(self):
        with patch.object(stripe.httpx, 'Client') as client:
            request=client.return_value.__enter__.return_value.request
            request.return_value=httpx.Response(200,json=dict(id='cus_offline',livemode=False))
            provider=stripe.Provider()
            self.assertEqual(provider.call('POST','/customers',{'metadata[business_id]':'10'},'offline-idempotency')['id'],'cus_offline')
            self.assertFalse(client.call_args.kwargs['trust_env'])
            self.assertFalse(client.call_args.kwargs['follow_redirects'])
            self.assertEqual(request.call_args.args,('POST','https://api.stripe.com/v1/customers'))
            self.assertEqual(request.call_args.kwargs['headers']['Stripe-Version'],'2026-10-28.endive')
            self.assertEqual(request.call_args.kwargs['headers']['Idempotency-Key'],'offline-idempotency')
            request.return_value=httpx.Response(500,json={'error':{'message':'DO_NOT_DISCLOSE'}})
            with self.assertRaises(HTTPException) as err: provider.call('POST','/customers')
            self.assertNotIn('DO_NOT_DISCLOSE',str(err.exception))
            self.assertEqual(request.call_count,2)
            request.return_value=httpx.Response(200,json=dict(id='cus_live',livemode=True))
            with self.assertRaises(HTTPException): provider.call('GET','/customers/cus_live')
            with patch.object(base.config.settings,'STRIPE_TEST_SECRET_KEY',SecretStr('sk_live_FORBIDDEN')):
                with self.assertRaises(HTTPException): provider.call('GET','/customers/cus_offline')

    def test_lost_customer_response_reuses_original_customer_key(self):
        original=self.provider.call
        failed=[False]
        def interrupt(method,path,data=None,key=None):
            result=original(method,path,data,key)
            if path=='/customers' and not failed[0]:
                failed[0]=True
                raise HTTPException(502,'Lost customer response')
            return result
        with patch.object(self.provider,'call',side_effect=interrupt):
            with self.assertRaises(HTTPException): self.checkout()
            self.assertEqual(billing.recover(self.db,self.user,10,self.provider)['status'],'OPEN')
        keys=[key for method,path,_,key in self.provider.calls if method=='POST' and path=='/customers']
        self.assertEqual(len(keys),2)
        self.assertEqual(keys[0],keys[1])

    def test_double_click_reuses_session_and_changed_key_conflicts(self):
        first = self.checkout()
        self.assertEqual(self.checkout(), first)
        self.assertEqual(sum(m == 'POST' and p == '/checkout/sessions' for m,p,_,_ in self.provider.calls), 1)
        with self.assertRaises(HTTPException) as error:
            self.checkout(self.payload.model_copy(update={'request_id':'different_request_123456'}))
        self.assertEqual(error.exception.status_code, 409)
        with self.assertRaises(HTTPException):
            self.checkout(self.payload.model_copy(update={'plan':'BUSINESS'}))

    def test_lost_response_recovers_existing_session_without_second_creation(self):
        self.provider.interrupt = True
        with self.assertRaises(HTTPException): self.checkout()
        row = self.db.scalar(select(Attempt))
        self.assertEqual(row.status, 'UNCERTAIN')
        self.assertIsNone(row.stripe_session_id)
        result = billing.recover(self.db, self.user, 10, self.provider)
        self.assertEqual(result['status'], 'OPEN')
        self.assertEqual(sum(m == 'POST' and p == '/checkout/sessions' for m,p,_,_ in self.provider.calls), 1)
        self.assertEqual(row.stripe_session_id, 'cs_test_offline')

    def test_failed_database_commit_is_not_retried_and_preserves_durable_intent(self):
        original=self.db.commit
        count=[0]
        def fail_second_commit():
            count[0]+=1
            if count[0]==2: raise RuntimeError('Simulated commit interruption')
            return original()
        with patch.object(self.db,'commit',side_effect=fail_second_commit), self.assertRaises(RuntimeError):
            self.checkout()
        self.assertEqual(count[0],2)
        self.db.rollback()
        row=self.db.scalar(select(Attempt))
        self.assertEqual(row.status,'CREATING')
        self.assertIsNone(row.stripe_session_id)
        self.assertEqual(len(self.provider.sessions),1)
        self.assertEqual(billing.recover(self.db,self.user,10,self.provider)['status'],'OPEN')
        self.assertEqual(len(self.provider.sessions),1)

    def test_old_uncertain_attempt_never_issues_new_session(self):
        self.checkout()
        row = self.db.scalar(select(Attempt)); row.stripe_session_id = None
        row.created_at -= timedelta(days=2); row.expires_at -= timedelta(days=2)
        row.status = 'UNCERTAIN'; self.db.commit(); self.provider.sessions.clear()
        count = len(self.provider.calls)
        with self.assertRaises(HTTPException): billing.recover(self.db, self.user, 10, self.provider)
        self.assertFalse(any(method == 'POST' for method,_,_,_ in self.provider.calls[count:]))
        self.assertEqual(row.active_business_id, 10)

    def test_cross_tenant_and_admin_management_denied_without_provider_calls(self):
        for ident in [1,3,4,5]:
            with self.assertRaises(HTTPException):
                billing.checkout(self.db, self.db.get(base.User, ident), 10, self.payload, self.provider)
            with self.assertRaises(HTTPException):
                billing.portal(self.db, self.db.get(base.User, ident), 10, self.provider)
            with self.assertRaises(HTTPException):
                billing.recover(self.db, self.db.get(base.User, ident), 10, self.provider)
        self.assertEqual(self.provider.calls, [])

    def test_confirmed_expired_session_releases_slot_but_old_key_is_not_reused(self):
        self.checkout()
        self.provider.sessions[0]['status']='expired'
        self.assertEqual(billing.recover(self.db,self.user,10,self.provider)['status'],'EXPIRED')
        self.assertIsNone(self.db.scalar(select(Attempt)).active_business_id)
        with self.assertRaises(HTTPException): self.checkout()
        self.assertEqual(len(self.provider.sessions),1)

    def test_checkout_completion_is_bound_and_still_requires_verified_paid_state(self):
        self.checkout()
        session=self.provider.sessions[0]; session['status']='complete'
        session['subscription']='sub_offline'
        event=self.event('evt_checkout','checkout.session.completed')
        event['data']['object']=session.copy()
        billing.webhook(self.db,event,self.provider)
        self.assertEqual(billing.subscription_state(self.db,10)['effective_plan'],'FREE')
        self.assertEqual(self.db.scalar(select(Attempt)).active_business_id,10)
        self.assertEqual(self.db.scalar(select(Attempt)).status,'VERIFYING')
        with self.assertRaises(HTTPException):
            self.checkout(self.payload.model_copy(update={'request_id':'conflicting_request_123456'}))
        self.paid()
        billing.webhook(self.db,self.event('evt_paid_after_checkout'),self.provider)
        self.assertEqual(billing.subscription_state(self.db,10)['effective_plan'],'PRO')
        self.assertIsNone(self.db.scalar(select(Attempt)).active_business_id)

    def test_signature_exact_bytes_bad_signature_replay_and_live_rejected(self):
        body = json.dumps(self.event()).encode()
        digest = hmac.new(b'whsec_offline_only', b'1000.'+body, hashlib.sha256).hexdigest()
        signature = 't=1000,v1=' + digest
        self.assertEqual(stripe.signed_event(body, signature, now=1001)['id'], 'evt_offline')
        for raw, sig, now in [(body+b' ',signature,1001),(body,'t=1000,v1=bad',1001),(body,signature,1301)]:
            with self.assertRaises(HTTPException): stripe.signed_event(raw,sig,now=now)
        live = json.dumps({**self.event(),'livemode':True}).encode()
        sig = hmac.new(b'whsec_offline_only',b'1000.'+live,hashlib.sha256).hexdigest()
        with self.assertRaises(HTTPException): stripe.signed_event(live,'t=1000,v1='+sig,now=1001)

    def test_cancel_return_and_unpaid_subscription_never_grant_paid_access(self):
        result = self.checkout()
        self.assertTrue(result['url'].startswith('https://checkout.stripe.com/'))
        self.assertEqual(billing.subscription_state(self.db, 10)['effective_plan'], 'FREE')
        # A browser cancel/success query has no server-side activation operation.
        # An open Session remains pending, rather than becoming a subscription.
        self.assertEqual(self.db.scalar(select(Attempt)).status, 'OPEN')
        self.paid(status='active', invoice='open')
        billing.webhook(self.db, self.event('evt_unpaid', 'customer.subscription.updated'), self.provider)
        self.assertEqual(self.db.get(BusinessSubscription, 10).status, 'PAST_DUE')
        self.assertEqual(billing.subscription_state(self.db, 10)['effective_plan'], 'FREE')
        self.assertIsNone(self.db.get(BusinessSubscription, 10).paid_through)

    def test_webhook_duplicate_and_out_of_order_fetch_current_state(self):
        self.checkout(); self.paid()
        billing.webhook(self.db, self.event(), self.provider)
        self.assertTrue(billing.webhook(self.db, self.event(), self.provider)['duplicate'])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(SubscriptionPaymentEvent)), 1)
        # Old failed event cannot override an authoritative paid renewal.
        billing.webhook(self.db,self.event('evt_old','invoice.payment_failed'),self.provider)
        self.assertEqual(billing.subscription_state(self.db,10)['effective_plan'],'PRO')
        self.paid('past_due','open')
        billing.webhook(self.db,self.event('evt_failure','invoice.payment_failed'),self.provider)
        self.assertEqual(billing.subscription_state(self.db,10)['effective_plan'],'FREE')

    def test_cancellation_period_end_renewal_and_portal(self):
        self.checkout(); self.paid()
        self.provider.subscriptions[0]['cancel_at_period_end'] = True
        billing.webhook(self.db,self.event(),self.provider)
        self.assertEqual(billing.subscription_state(self.db,10)['effective_plan'],'PRO')
        self.assertTrue(billing.portal(self.db,self.user,10,self.provider)['url'].startswith('https://billing.stripe.com/'))
        old = self.db.get(BusinessSubscription,10).paid_through
        self.provider.subscriptions[0]['items']['data'][0]['current_period_end'] += 86400*30
        billing.webhook(self.db,self.event('evt_renewal'),self.provider)
        self.assertGreater(self.db.get(BusinessSubscription,10).paid_through,old)
        self.paid('canceled')
        billing.webhook(self.db,self.event('evt_cancel','customer.subscription.deleted'),self.provider)
        self.assertEqual(billing.subscription_state(self.db,10)['effective_plan'],'FREE')

    def test_trial_blocks_checkout_then_paid_preserves_original_grant(self):
        now=billing.utc_now()
        grant=SubscriptionTrialGrant(business_id=10, grant_status='GRANTED', created_at=now,
            trial_started_at=now-timedelta(days=10),trial_ends_at=now+timedelta(days=20))
        self.db.add(grant); self.db.commit()
        with self.assertRaises(HTTPException): self.checkout()
        self.assertEqual(self.provider.calls,[])
        grant.trial_started_at=now-timedelta(days=40); grant.trial_ends_at=now-timedelta(days=10); self.db.commit()
        dates=(grant.trial_started_at,grant.trial_ends_at)
        self.checkout(); self.paid(); billing.webhook(self.db,self.event(),self.provider)
        self.assertEqual(billing.subscription_state(self.db,10)['effective_plan'],'PRO')
        self.assertEqual((grant.trial_started_at,grant.trial_ends_at), dates)

    def test_provider_customer_mismatch_and_multiple_subscriptions_fail_closed(self):
        self.checkout(); self.paid()
        self.provider.subscriptions.append({**self.provider.subscriptions[0], 'id':'sub_other'})
        with self.assertRaises(HTTPException): billing.webhook(self.db,self.event(),self.provider)
        self.db.rollback()
        self.assertIsNone(self.db.get(SubscriptionPaymentEvent,'evt_offline'))
        self.provider.subscriptions=self.provider.subscriptions[:1]
        self.provider.subscriptions[0]['metadata']['business_id']='20'
        with self.assertRaises(HTTPException): billing.webhook(self.db,self.event(),self.provider)

    def test_disabled_and_redirect_checks(self):
        with patch.object(base.config.settings,'STRIPE_SANDBOX_ENABLED',False), self.assertRaises(HTTPException) as err:
            self.checkout()
        self.assertEqual(err.exception.status_code,503)
        self.assertEqual(self.provider.calls,[])
        for url in ['http://checkout.stripe.com/x','https://checkout.stripe.com.evil/x','https://user@checkout.stripe.com/x']:
            with self.assertRaises(HTTPException): stripe.hosted_url(url)

    def test_http_signed_boundary_and_disabled_fallback(self):
        app=FastAPI(); app.include_router(base.subscriptions.router,prefix='/api/v1')
        app.dependency_overrides[base.get_db]=lambda:self.db
        with TestClient(app) as client:
            self.assertEqual(client.post('/api/v1/subscriptions/webhook',content=b'{}').status_code,400)
            with patch.object(base.config.settings,'STRIPE_SANDBOX_ENABLED',False):
                self.assertEqual(client.post('/api/v1/subscriptions/webhook',content=b'{}').status_code,503)

    def test_only_billing_tables_written_and_mysql_lock_compiles(self):
        statements=[]
        def capture(conn,cursor,sql,params,context,many):
            if sql.split()[0].upper() in {'INSERT','UPDATE','DELETE'}: statements.append(sql)
        base.event.listen(self.engine,'before_cursor_execute',capture)
        self.checkout(); self.paid(); billing.webhook(self.db,self.event(),self.provider)
        self.assertTrue(statements)
        for sql in statements:
            self.assertTrue(any(name in sql for name in ['business_subscriptions','subscription_checkout_attempts','subscription_payment_events']),sql)
        self.assertIn('FOR UPDATE',str(select(base.Business).with_for_update().compile(dialect=mysql.dialect())))


class ConcurrencyTests(TestCase):
    def test_two_connections_cannot_reserve_two_active_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            engine=create_engine('sqlite:///'+str(Path(directory)/'offline.db'),connect_args={'timeout':10})
            base.create_tables(engine)
            with Session(engine) as db: base.seed(db)
            barrier=threading.Barrier(2); results=[]
            def writer(n):
                with Session(engine) as db:
                    now=billing.utc_now()
                    db.add(Attempt(attempt_id=str(n),business_id=10,active_business_id=10,request_key='key_'+str(n),
                        plan='PRO',billing_interval='month',price_id='price_pm',return_origin='http://127.0.0.1:5176',status='CREATING',created_at=now,expires_at=now+timedelta(hours=1)))
                    barrier.wait()
                    try: db.commit(); results.append('reserved')
                    except IntegrityError: db.rollback(); results.append('blocked')
            threads=[threading.Thread(target=writer,args=(n,)) for n in [1,2]]
            for thread in threads: thread.start()
            for thread in threads: thread.join(15)
            self.assertEqual(sorted(results),['blocked','reserved'])
            engine.dispose()


class SourceContractTests(TestCase):
    def test_additive_migration_matches_model_without_running_alembic(self):
        root=Path(__file__).resolve().parents[1]
        tree=ast.parse((root/'alembic/versions/9d1a6f4e0c37_subscription_checkout_attempts.py').read_text())
        upgrade=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='upgrade')
        calls=[node.value for node in upgrade.body]
        self.assertEqual([node.func.attr for node in calls],['create_table','create_index'])
        self.assertEqual(ast.literal_eval(calls[0].args[0]),'subscription_checkout_attempts')
        columns=[arg for arg in calls[0].args if isinstance(arg,ast.Call) and arg.func.attr=='Column']
        self.assertEqual({ast.literal_eval(arg.args[0]) for arg in columns},set(Attempt.__table__.columns.keys()))
        checks=[arg for arg in calls[0].args if isinstance(arg,ast.Call) and arg.func.attr=='CheckConstraint']
        self.assertEqual({ast.literal_eval(arg.args[0]) for arg in checks},
            {str(c.sqltext) for c in Attempt.__table__.constraints if hasattr(c,'sqltext')})

    def test_real_configuration_rejects_live_keys_bad_origins_and_duplicate_prices(self):
        # Execute class definitions only; remove singleton creation, never dotenv/DB.
        path=Path(__file__).resolve().parents[1]/'app/core/config.py'
        tree=ast.parse(path.read_text())
        tree.body=[n for n in tree.body if not (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='settings' for t in n.targets))]
        module=ModuleType('offline_billing_config'); module.__file__=str(path)
        sys.modules[module.__name__]=module
        exec(compile(tree,str(path),'exec'),module.__dict__)
        args=dict(_env_file=None,APP_ENV='development',MYSQL_USER='offline',MYSQL_PASSWORD='offline',
            MYSQL_DATABASE='offline',JWT_SECRET_KEY='offline',MYSQL_SSL_CA=None,
            CORS_ALLOWED_ORIGINS=['http://127.0.0.1:5176'],**OPTIONS)
        self.assertTrue(module.Settings(**args).STRIPE_SANDBOX_ENABLED)
        for overrides in [dict(STRIPE_TEST_SECRET_KEY='sk_live_forbidden'),dict(STRIPE_RETURN_ORIGIN='https://evil.example'),
            dict(STRIPE_PRO_YEAR_PRICE='price_pm'),dict(STRIPE_RETURN_ORIGIN='http://127.0.0.1:5176/x'),
            dict(STRIPE_WEBHOOK_SECRET='bad')]:
            with self.assertRaises(ValueError): module.Settings(**{**args,**overrides})


if __name__=='__main__': main(verbosity=2)

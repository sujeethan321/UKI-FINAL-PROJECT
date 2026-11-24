"""Package policy on synthetic SQLite only. No MySQL or provider requests."""
from datetime import timedelta
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
import reports_suite as fixtures
from app.services import subscription_service as policy
from app.models import CustomerProfile, BusinessSubscription, SubscriptionTrialGrant
from app.schemas.customer import CustomerCreate
from app.services.shop_owner_customer_create_service import create_business_customer


class Packages(TestCase):
    setUp=fixtures.ReportsTests.setUp
    tearDown=fixtures.ReportsTests.tearDown

    def free(self,business_id=10):
        for model in (SubscriptionTrialGrant,BusinessSubscription):
            row=self.db.get(model,business_id)
            if row:self.db.delete(row)
        self.db.commit()

    def test_matrix_prices_trial_and_paid_expiry(self):
        now=policy.utc_now()
        self.assertEqual([(p['monthly_minor'],p['yearly_minor']) for p in policy.PLANS],[(0,0),(49900,499000),(129900,1299000)])
        for name in ('PRO','BUSINESS'):
            paid=SimpleNamespace(plan=name,status='ACTIVE',provider_mode='sandbox',stripe_customer_id='fixture',stripe_subscription_id='fixture',started_at=now-timedelta(days=1),paid_through=now+timedelta(days=1),billing_interval='month')
            state=policy.evaluate(paid,None,now)
            self.assertTrue(state['entitlements']['reports']);self.assertIsNone(state['customer_limit'])
            self.assertFalse(state['entitlements']['advanced_reports'])
            expired=policy.evaluate(paid,None,paid.paid_through)
            self.assertEqual(expired['effective_plan'],'FREE');self.assertFalse(expired['entitlements']['orders'])
        trial=self.db.get(SubscriptionTrialGrant,10)
        self.assertEqual(policy.subscription_state(self.db,10)['effective_plan'],'PRO')
        self.assertEqual(policy.evaluate(None,trial,trial.trial_ends_at)['effective_plan'],'FREE')

    def test_customer_cap_scope_and_current_mysql_locks(self):
        self.free();self.free(20)
        from sqlalchemy.dialects import mysql
        captured=[];scalar=self.db.scalar;scalars=self.db.scalars
        def capture(statement,method):
            captured.append(str(statement.compile(dialect=mysql.dialect())))
            return method(statement)
        for i in range(4,32):self.db.add(CustomerProfile(customer_id=i,business_id=10,customer_name='Synthetic'))
        self.db.commit()
        with patch.object(self.db,'scalar',side_effect=lambda s:capture(s,scalar)),patch.object(self.db,'scalars',side_effect=lambda s:capture(s,scalars)):
            with self.assertRaises(HTTPException):create_business_customer(self.db,10,CustomerCreate(customer_name='Blocked synthetic'))
        self.db.rollback()
        self.assertTrue(any('FROM businesses' in s and 'FOR UPDATE' in s for s in captured))
        self.assertTrue(any('FROM customer_profiles' in s and 'FOR UPDATE' in s for s in captured))
        create_business_customer(self.db,20,CustomerCreate(customer_name='Other synthetic'))
        self.assertEqual(len(list(self.db.scalars(select(CustomerProfile).where(CustomerProfile.business_id==10)))),30)

    def test_http_free_reports_and_direct_ai_denied_then_trial_unlocked(self):
        app=FastAPI();app.include_router(fixtures.shop_owner.router,prefix='/api/v1')
        app.dependency_overrides[fixtures.base.get_db]=lambda:self.db
        app.dependency_overrides[fixtures.base.get_current_user]=lambda:self.user
        from app.services.report_ai_service import get_report_ai_client
        app.dependency_overrides[get_report_ai_client]=lambda:None
        self.free()
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/v1/shop-owner/reports/financial?business_id=10').status_code,403)
            self.assertEqual(client.post('/api/v1/shop-owner/businesses/10/reports/ai-summary',json={'question_id':'credit_overview','language':'en','start_date':'2026-11-01','end_date':'2026-11-20'}).status_code,403)
            now=policy.utc_now();self.db.add(SubscriptionTrialGrant(business_id=10,grant_status='GRANTED',trial_started_at=now,trial_ends_at=policy.calendar_month_end(now),created_at=now));self.db.commit()
            self.assertEqual(client.get('/api/v1/shop-owner/reports/financial?business_id=10').status_code,200)
            self.assertIn(client.get('/api/v1/shop-owner/reports/financial?business_id=20').status_code,(403,404))


if __name__=='__main__':main(verbosity=2)

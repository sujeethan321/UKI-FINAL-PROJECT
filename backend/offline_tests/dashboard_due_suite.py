"""Synthetic SQLite and pure FIFO checks; no live database connections."""
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch
import reports_suite as fixtures
from app.services.dashboard_due_service import due_totals
from app.services.customer_dashboard_service import dashboard_summary
from app.models import CustomerProfile, LedgerEntry
from sqlalchemy import select, func

NOW = datetime(2026, 11, 20, 12)


def sale(ident, due, amount='100', account=1, kind='credit_sale', ref=None):
    return SimpleNamespace(entry_id=ident, credit_account_id=account, entry_type=kind,
        amount=Decimal(amount), recorded_at=NOW-timedelta(days=40-ident), due_at=due, reverses_entry_id=ref)


class TotalsTests(TestCase):
    def setUp(self):
        from app.services.dashboard_due_service import settings
        option=patch.object(settings,'MAX_READ_LEDGER_ENTRIES',1000,create=True)
        option.start();self.addCleanup(option.stop)

    def test_empty_and_due_boundaries(self):
        self.assertEqual(due_totals([], NOW, '0')['overdue_amount'], '0.00')
        for days, soon, overdue in [(-1,'0.00','100.00'),(0,'100.00','0.00'),
                                     (7,'100.00','0.00'),(8,'0.00','0.00')]:
            result=due_totals([sale(1,NOW+timedelta(days=days))],NOW,'100')
            self.assertEqual((result['due_soon_amount'],result['overdue_amount']),(soon,overdue))

    def test_partial_full_and_advances_stay_per_account(self):
        rows=[sale(1,NOW-timedelta(days=1)),sale(2,None,'40',kind='repayment')]
        self.assertEqual(due_totals(rows,NOW,'60')['overdue_amount'],'60.00')
        rows[1].amount=Decimal('100')
        self.assertEqual(due_totals(rows,NOW,'0')['overdue_amount'],'0.00')
        rows.append(sale(3,None,'900',account=2,kind='repayment'))
        rows[1].amount=Decimal('40')
        self.assertEqual(due_totals(rows,NOW,'60')['overdue_amount'],'60.00')

    def test_missing_invalid_future_and_mismatch_never_fake_zero(self):
        for rows, now, total in [([sale(1,None)],NOW,'100'),([sale(1,NOW)],None,'100'),
                ([sale(1,NOW)],NOW,'99'),([sale(1,NOW-timedelta(days=100))],NOW,'100')]:
            result=due_totals(rows,now,total)
            self.assertIsNone(result['due_soon_amount']);self.assertIsNone(result['overdue_amount'])
        fully_paid=[sale(1,None),sale(2,None,'100',kind='repayment')]
        self.assertEqual(due_totals(fully_paid,NOW,'0')['overdue_amount'],'0.00')
        row=sale(1,NOW);row.recorded_at=NOW+timedelta(seconds=1)
        self.assertIsNone(due_totals([row],NOW,'100')['overdue_amount'])

    def test_reversal_reallocates_full_original_not_marker_amount(self):
        rows=[sale(1,NOW-timedelta(days=1)),sale(2,None,'40',kind='repayment'),sale(3,None,'1',kind='reversal',ref=2)]
        self.assertEqual(due_totals(rows,NOW,'100')['overdue_amount'],'100.00')


class ScopedTests(TestCase):
    setUp=fixtures.ReportsTests.setUp
    tearDown=fixtures.ReportsTests.tearDown

    def test_business_and_customer_isolation_and_readonly(self):
        now=self.db.scalar(select(func.now()))
        for ident, account, amount in [(1,1,'100'),(2,3,'900')]:
            self.db.add(LedgerEntry(entry_id=ident,credit_account_id=account,created_by=2,
                entry_type='credit_sale',amount=Decimal(amount),recorded_at=now-timedelta(days=3),
                due_at=now-timedelta(days=1),idempotency_key='due-'+str(ident)))
        self.db.commit()
        self.db.get(CustomerProfile,1).user_id=4
        self.db.connection().connection.driver_connection.create_function('greatest',2,max)
        self.db.commit()
        self.assertEqual(dashboard_summary(self.db,4)['overdue_amount'],'100.00')
        self.assertFalse(self.db.dirty)

    def test_customer_dashboard_authorization_and_no_store(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.routers import customer
        app=FastAPI();app.include_router(customer.router,prefix='/api/v1')
        self.db.connection().connection.driver_connection.create_function('greatest',2,max)
        app.dependency_overrides[fixtures.base.get_db]=lambda:self.db
        app.dependency_overrides[fixtures.base.get_current_user]=lambda:self.db.get(fixtures.base.User,4)
        with TestClient(app) as client:
            result=client.get('/api/v1/customer/dashboard/summary')
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.headers['cache-control'],'no-store')
            self.assertEqual(result.json()['overdue_amount'],'0.00')
            app.dependency_overrides[fixtures.base.get_current_user]=lambda:self.user
            self.assertEqual(client.get('/api/v1/customer/dashboard/summary').status_code,403)


if __name__=='__main__': main(verbosity=2)

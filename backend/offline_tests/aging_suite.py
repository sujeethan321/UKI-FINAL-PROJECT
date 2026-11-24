"""SQLite and pure offline aging regressions; network blocked by base suite."""
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase, main
import reports_suite as base
from app.services.shop_owner_aging_service import aging, BUCKETS
from app.services.shop_owner_reports_csv import render_report_csv
from app.services.shop_owner_reports_pdf import render_report_pdf
from unittest.mock import patch
import pymupdf

NOW = datetime(2026, 11, 18, 12)


def e(i, kind='credit_sale', amount='100', account=1, due=None, ref=None, stamp=None):
    return SimpleNamespace(entry_id=i, credit_account_id=account, entry_type=kind,
        amount=Decimal(amount), recorded_at=stamp or NOW-timedelta(days=200),
        due_at=due, reverses_entry_id=ref)


class AgingTests(TestCase):
    def calc(self, rows):
        return aging(rows, NOW, 1000)

    def test_all_boundaries_and_due_today_end_of_day(self):
        for days, index in [(-1,0),(0,0),(1,1),(30,1),(31,2),(60,2),(61,3),(90,3),(91,4)]:
            due = (NOW-timedelta(days=days)).replace(hour=0)
            result = self.calc([e(1,due=due)])
            self.assertEqual(result['buckets'][BUCKETS[index]], '100.00')
            self.assertEqual(result['status'], 'complete')
            self.assertEqual(result['overdue_amount'], '0.00' if index==0 else '100.00')

    def test_fifo_ties_not_due_date_and_partial_full_payments(self):
        rows = [e(2,due=NOW-timedelta(days=60)),e(1,due=NOW),e(3,'repayment','120',stamp=NOW)]
        result = self.calc(rows)
        self.assertEqual(result['buckets']['current'], '0.00')
        self.assertEqual(result['buckets']['days_31_60'], '80.00')
        rows[-1].amount = Decimal('200')
        self.assertEqual(self.calc(rows)['overdue_amount'], '0.00')

    def test_advances_and_account_reconciliation(self):
        result = self.calc([e(1,'repayment','300'),e(2,account=2,due=NOW-timedelta(days=1))])
        self.assertEqual(result['overdue_amount'], '100.00')
        self.assertEqual(result['reconciliation'], 'matched')

    def test_repayment_and_sale_reversals_reallocate(self):
        rows=[e(1,due=NOW),e(2,'repayment','50',stamp=NOW-timedelta(days=2)),
              e(3,'reversal','1',ref=2,stamp=NOW)]
        self.assertEqual(self.calc(rows)['buckets']['current'], '100.00')
        rows=[e(1,due=NOW),e(2,due=NOW-timedelta(days=10)),
              e(3,'repayment','120',stamp=NOW-timedelta(days=1)),e(4,'reversal','1',ref=1,stamp=NOW)]
        self.assertEqual(self.calc(rows)['overdue_amount'], '0.00')

    def test_missing_invalid_due_and_future(self):
        for due in (None, NOW-timedelta(days=201)):
            result = self.calc([e(1,due=due)])
            self.assertEqual(result['status'], 'incomplete')
            self.assertEqual(result['unclassified'], '100.00')
            self.assertIsNone(result['overdue_amount'])
        result=self.calc([e(1,stamp=NOW+timedelta(seconds=1))])
        self.assertEqual(result['status'],'unavailable')
        self.assertIsNone(result['buckets'])

    def test_invalid_histories_bounds_and_empty(self):
        for rows in ([e(1,'reversal',ref=99)], [e(1), e(2,'reversal',ref=1,account=2,stamp=NOW)],
                     [e(1,stamp=NOW),e(2,'reversal',ref=1)],
                     [e(1),e(2,'reversal',ref=1,stamp=NOW),e(3,'reversal',ref=1,stamp=NOW)]):
            with self.assertRaises(base.HTTPException): self.calc(rows)
        with self.assertRaises(base.HTTPException): aging([e(1)],NOW,0)
        self.assertEqual(self.calc([])['overdue_amount'],'0.00')


class AgingIntegrationTests(base.ReportsTests):
    def test_incomplete_exports_do_not_claim_exact_overdue_and_mismatch_blocks(self):
        self.entry(1,'credit_sale','123.45','2026-01-01T00:00:00')
        data=base.reports.report(self.db,10)
        self.assertEqual(data['aging']['status'],'incomplete')
        self.assertIsNone(data['summary']['overdue_amount'])
        self.assertEqual(data['aging']['unclassified'],'123.45')
        csv=render_report_csv(data).decode('utf-8-sig')
        self.assertIn('Unavailable; incomplete or invalid coverage',csv)
        with pymupdf.open(stream=render_report_pdf(data,'en'),filetype='pdf') as pdf:
            text=''.join(p.get_text() for p in pdf)
            self.assertIn('Exact overdue amount is unavailable',text)
        with patch.object(base.reports,'get_dashboard_summary',return_value=dict(total_outstanding=Decimal('1.00'))):
            with self.assertRaises(base.HTTPException) as raised:
                base.reports.report(self.db,10)
            self.assertEqual(raised.exception.status_code,409)

    def test_aging_json_csv_pdf_consistency_and_isolation(self):
        self.entry(1,'credit_sale','123.45','2026-01-01T00:00:00')
        row=self.db.get(base.LedgerEntry,1); row.due_at=datetime(2026,1,31); self.db.commit()
        self.entry(2,'credit_sale','999.99','2026-01-01T00:00:00',account=3)
        data=base.reports.report(self.db,10)
        self.assertEqual(data['aging']['overdue_amount'],'123.45')
        self.assertEqual(data['summary']['overdue_amount'],'123.45')
        self.assertEqual(data['aging']['buckets']['days_91_plus'],'123.45')
        csv=render_report_csv(data).decode('utf-8-sig')
        self.assertIn('Reporting-only FIFO',csv); self.assertIn('123.45',csv); self.assertNotIn('999.99',csv)
        for language in ('en','ta','si'):
            with pymupdf.open(stream=render_report_pdf(data,language),filetype='pdf') as pdf:
                text=''.join(p.get_text() for p in pdf)
                self.assertIn('123.45',text)
                self.assertNotIn('999.99',text)
        self.assertEqual(base.reports.report(self.db,20)['aging']['status'],'incomplete')


if __name__ == '__main__': main(verbosity=2)

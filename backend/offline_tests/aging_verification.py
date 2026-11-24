"""Pure verifier checks; no MySQL, HTTP or Stripe requests."""
import copy
from datetime import datetime
from decimal import Decimal as D
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('verification',Path(__file__).resolve().parents[1]/'scripts/verify_viva_aging.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)


class VerificationTests(unittest.TestCase):
    def fixture(self):
        now=datetime(2026,11,18,12)
        data=dict(business_id=1,reporting_clock='database_wall_clock',database_today='2026-11-18',
            summary=dict(business_id=1,total_outstanding='75.00',overdue_amount='75.00'),
            aging=dict(as_of='2026-11-18',reconciliation='matched',status='complete',unclassified='0.00',overdue_amount='75.00',
                coverage=dict(effective_sales=1,missing_due_dates=0,invalid_due_dates=0,unpaid_debt_fully_classified=True),
                buckets=dict(zip(v.KEYS,('0.00','75.00','0.00','0.00','0.00')))))
        rows=[(1,D('100'),datetime(2026,10,1),datetime(2026,11,1),D('75'))]
        return data,rows,[(1,D('75')),(2,D('-100'))],now

    def test_exact_comparison_and_account_advances(self):
        data,rows,balances,now=self.fixture()
        self.assertEqual(v.compare(data,rows,balances,now)[2],D('75'))

    def test_mismatches_fail_closed(self):
        data,rows,balances,now=self.fixture()
        for change in ('bucket','business','balance','clock'):
            altered=copy.deepcopy(data)
            if change=='bucket': altered['aging']['buckets']['current']='1.00'
            elif change=='business': altered['business_id']=2
            elif change=='balance': altered['summary']['total_outstanding']='74.99'
            else: altered['database_today']='2026-11-17'
            with self.assertRaises(ValueError): v.compare(altered,rows,balances,now)

    def test_pdf_text_normalization(self):
        self.assertEqual(v.normalize('1–30\n days overdue\u00a0 1,000.00'),'1-30 days overdue 1,000.00')


if __name__=='__main__': unittest.main()

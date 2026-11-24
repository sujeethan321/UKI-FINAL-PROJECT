"""Step 372 comparison unit tests; no network or database connection."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import importlib.util
from pathlib import Path
from unittest import TestCase, main

path=Path(__file__).resolve().parents[1]/'scripts/verify_viva_reports.py'
spec=importlib.util.spec_from_file_location('report_verifier',path)
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class ComparisonTests(TestCase):
    def setUp(self):
        self.data=dict(start_date='2026-11-01',end_date='2026-11-03',
            summary=dict(total_outstanding='70.05',collected_today='-30.00',overdue_amount=None),
            totals=dict(credit_sales='100.10',repayments='0.00'),
            daily=[dict(date='2026-11-01',credit_sales='100.10',repayments='30.00'),
                   dict(date='2026-11-02',credit_sales='0.00',repayments='0.00'),
                   dict(date='2026-11-03',credit_sales='0.00',repayments='-30.00')])
        self.rows=[(date(2026,11,1),Decimal('100.10'),Decimal('30.00')),
                   (date(2026,11,3),Decimal(0),Decimal('-30.00'))]

    def compare(self,data=None):
        module.compare(data or self.data,Decimal('70.05'),Decimal('-30.00'),self.rows)

    def test_exact_decimals_signed_reversals_and_missing_sql_days_match(self):
        self.compare()

    def test_changed_totals_current_balances_and_daily_points_fail(self):
        for section,key in [('summary','total_outstanding'),('summary','collected_today'),('totals','credit_sales'),('totals','repayments')]:
            data=deepcopy(self.data); data[section][key]='999.00'
            with self.assertRaises(RuntimeError): self.compare(data)
        data=deepcopy(self.data); data['daily'][2]['repayments']='30.00'
        with self.assertRaises(RuntimeError): self.compare(data)

    def test_duplicate_or_out_of_order_days_fail(self):
        for points in [self.data['daily'][:-1],list(reversed(self.data['daily']))]:
            data=deepcopy(self.data); data['daily']=points
            with self.assertRaises(RuntimeError): self.compare(data)

    def test_unsupported_overdue_values_fail(self):
        data=deepcopy(self.data); data['summary']['overdue_amount']='1.00'
        with self.assertRaises(RuntimeError): self.compare(data)


if __name__=='__main__': main(verbosity=2)

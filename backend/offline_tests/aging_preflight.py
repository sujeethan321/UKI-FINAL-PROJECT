"""Step 378 pure diagnostic tests: no database imports or connections."""
import importlib.util
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
import unittest

spec = importlib.util.spec_from_file_location('preflight', Path(__file__).resolve().parents[1] / 'scripts/preflight_viva_aging.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NOW = datetime(2026, 11, 18, 12)


def entry(i, kind='credit_sale', amount='100', account=1, due=NOW, ref=None, recorded=None):
    return (i, account, kind, Decimal(amount), recorded or NOW-timedelta(days=100-i), due, ref)


class PreflightTests(unittest.TestCase):
    def test_partial_and_fifo_unknown_residual(self):
        result = module.assess([entry(1, due=None), entry(2), entry(3, 'repayment', '120')], NOW)
        self.assertTrue(result['reconciled'])
        self.assertTrue(result['bucket_reconciliation'])
        self.assertFalse(result['unclassified'])
        self.assertEqual(result['missing_due'], 1)

    def test_unclassified_and_invalid_due(self):
        result = module.assess([entry(1, due=None), entry(2, due=NOW-timedelta(days=200))], NOW)
        self.assertTrue(result['unclassified'])
        self.assertEqual(result['invalid_due'], 1)
        self.assertTrue(result['reconciled'])

    def test_advances_never_offset_other_account(self):
        result = module.assess([entry(1, 'repayment', '200'), entry(2, account=2)], NOW)
        self.assertTrue(result['bucket_reconciliation'])
        self.assertTrue(result['reconciled'])

    def test_reversals_full_original_not_descriptive_amount(self):
        result = module.assess([entry(1), entry(2, 'repayment', '40'), entry(3, 'reversal', '1', ref=2)], NOW)
        self.assertTrue(result['bucket_reconciliation'])
        self.assertEqual(result['invalid_reversals'], 0)

    def test_invalid_reference_account_chronology_and_duplicates(self):
        for rows in ([entry(2, 'reversal', ref=99)],
                     [entry(1), entry(2, 'reversal', account=2, ref=1)],
                     [entry(2), entry(1, 'reversal', ref=2)],
                     [entry(1), entry(2, 'reversal', ref=1), entry(3, 'reversal', ref=1)]):
            self.assertFalse(module.assess(rows, NOW)['reconciled'])

    def test_future_blocks_even_reversed_original(self):
        result = module.assess([entry(1, recorded=NOW+timedelta(seconds=1))], NOW)
        self.assertEqual(result['future'], 1)
        self.assertFalse(result['reconciled'])

    def test_empty_and_calendar_boundaries(self):
        self.assertTrue(module.assess([], NOW)['bucket_reconciliation'])
        for days in (-1, 0, 1, 30, 31, 60, 61, 90, 91):
            result = module.assess([entry(1, due=NOW-timedelta(days=days))], NOW)
            self.assertTrue(result['bucket_reconciliation'])
            self.assertFalse(result['unclassified'])


if __name__ == '__main__':
    unittest.main()

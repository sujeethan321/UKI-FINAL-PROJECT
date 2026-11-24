"""Database-free guard checks for the demo's private financial baseline comparison."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


comparator = module('compare_demo_baseline')
capture = module('capture_demo_baseline')


def fixture():
    return {
        'database': comparator.DATABASE, 'account': comparator.ACCOUNT,
        'revision': comparator.REVISION, 'captured_utc': '2026-11-10 00:00:00',
        'row_counts': {f'table_{n}': n for n in range(26)},
        'table_fingerprints': {f'table_{n}': f'{n:064x}' for n in range(26)},
        'financial_relationship_fingerprints': {f'group_{n}': f'{n:064x}' for n in range(4)},
        'foreign_key_orphans': {f'fk_{n}': 0 for n in range(53)},
    }


class DemoBaselineToolsTests(unittest.TestCase):
    def test_matching_snapshot_passes(self):
        comparator.compare(fixture(), copy.deepcopy(fixture()))

    def test_each_financial_or_row_difference_stops(self):
        for field in comparator.FIELDS:
            with self.subTest(field=field):
                current = fixture()
                key = next(iter(current[field]))
                current[field][key] = (1 if field in ('row_counts', 'foreign_key_orphans')
                                       else 'f' * 64)
                with self.assertRaisesRegex(ValueError, 'differs'):
                    comparator.compare(fixture(), current)

    def test_missing_field_or_wrong_identity_stops(self):
        for field in comparator.FIELDS:
            with self.subTest(field=field):
                current = fixture()
                del current[field]
                with self.assertRaises(ValueError):
                    comparator.compare(fixture(), current)
        current = fixture()
        current['database'] = 'lankapex_db'
        with self.assertRaisesRegex(ValueError, 'identity|database'):
            comparator.compare(fixture(), current)

    def test_invalid_formats_stop(self):
        current = fixture()
        current['row_counts']['table_0'] = -1
        with self.assertRaises(ValueError):
            comparator.compare(fixture(), current)
        current = fixture()
        current['table_fingerprints']['table_0'] = 'invalid'
        with self.assertRaises(ValueError):
            comparator.compare(fixture(), current)

    def test_existing_capture_file_refused_before_database_import(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            private = root / '.server-logs' / 'private-demo-backups'
            private.mkdir(parents=True)
            existing = private / 'existing.json'
            existing.write_text(json.dumps(fixture()), encoding='utf-8')
            with patch.object(capture, 'ROOT', root), patch.object(
                    sys, 'argv', ['capture', '--database', comparator.DATABASE,
                                  '--output', str(existing)]):
                with self.assertRaisesRegex(RuntimeError, 'new private JSON'):
                    capture.main()
            self.assertEqual(json.loads(existing.read_text(encoding='utf-8')),
                             fixture())


if __name__ == '__main__':
    unittest.main()

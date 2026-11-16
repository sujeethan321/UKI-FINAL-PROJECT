"""Synthetic, database-free checks for guarded demo integrity verification."""
import copy
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'verify_demo_post_migration.py'
spec = importlib.util.spec_from_file_location('demo_post', PATH)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def expected():
    return {
        'row_counts': {'alembic_version': 1, **{f'table_{n}': n for n in range(25)}},
        'table_fingerprints': {'alembic_version': 'a' * 64,
                               **{f'table_{n}': f'{n:064x}' for n in range(25)}},
        'financial_relationship_fingerprints': {f'group_{n}': f'{n:064x}' for n in range(4)},
        'foreign_key_orphans': {f'fk_{n}': 0 for n in range(53)},
    }


def actual(source):
    return {
        'database': verifier.TARGET, 'account': verifier.ACCOUNT,
        'revision': verifier.HEAD, 'table_count': 27, 'invitation_count': 0,
        'row_counts': {k: v for k, v in source['row_counts'].items() if k != 'alembic_version'},
        'table_fingerprints': {k: v for k, v in source['table_fingerprints'].items()
                               if k != 'alembic_version'},
        'financial_relationship_fingerprints': copy.deepcopy(source['financial_relationship_fingerprints']),
        'foreign_key_orphans': copy.deepcopy(source['foreign_key_orphans']),
    }


class DemoPostMigrationTests(unittest.TestCase):
    def test_correct_evidence_passes(self):
        baseline = expected()
        verifier.verify_snapshot(baseline, actual(baseline))

    def test_wrong_identity_revision_or_table_count_stops(self):
        baseline = expected()
        for key, value in [('database', 'lankapex_db'), ('account', 'other@localhost'),
                           ('revision', verifier.OLD), ('table_count', 26)]:
            with self.subTest(key=key):
                snapshot = actual(baseline)
                snapshot[key] = value
                with self.assertRaises(ValueError):
                    verifier.verify_snapshot(baseline, snapshot)

    def test_original_financial_and_fk_mismatches_stop(self):
        baseline = expected()
        for field, key, value in [
            ('row_counts', 'table_0', 1),
            ('table_fingerprints', 'table_0', 'f' * 64),
            ('financial_relationship_fingerprints', 'group_0', 'f' * 64),
            ('foreign_key_orphans', 'fk_0', 1),
        ]:
            with self.subTest(field=field):
                snapshot = actual(baseline)
                snapshot[field][key] = value
                with self.assertRaises(ValueError):
                    verifier.verify_snapshot(baseline, snapshot)

    def test_nonempty_invitations_or_missing_evidence_stops(self):
        baseline = expected()
        snapshot = actual(baseline)
        snapshot['invitation_count'] = 1
        with self.assertRaises(ValueError):
            verifier.verify_snapshot(baseline, snapshot)
        for field in verifier.FIELDS:
            with self.subTest(field=field):
                snapshot = actual(baseline)
                del snapshot[field]
                with self.assertRaises(ValueError):
                    verifier.verify_snapshot(baseline, snapshot)

    def test_pinned_evidence_identity_and_checksum(self):
        with TemporaryDirectory() as temporary:
            private = Path(temporary)
            dump = b'synthetic backup'
            (private / verifier.DUMP).write_bytes(dump)
            baseline = expected()
            before = {'database': verifier.TARGET,
                      'account': 'lankapex_demo_migrator@localhost',
                      'revision': verifier.OLD, **baseline}
            (private / 'test.before.json').write_text(json.dumps(before), encoding='utf-8')
            (private / 'test.after.json').write_text(json.dumps(before), encoding='utf-8')
            import hashlib
            digest = hashlib.sha256(dump).hexdigest()
            manifest = {'database': verifier.TARGET, 'revision': verifier.OLD,
                        'dump_filename': verifier.DUMP, 'sha256': digest,
                        'size_bytes': len(dump), 'before_manifest': 'test.before.json',
                        'after_manifest': 'test.after.json'}
            (private / verifier.MANIFEST).write_text(json.dumps(manifest), encoding='utf-8')
            with patch.object(verifier, 'PRIVATE', private), patch.object(verifier, 'SHA256', digest):
                self.assertEqual(verifier.pinned_baseline(), before)
                (private / verifier.DUMP).write_bytes(b'changed backup__')
                with self.assertRaises(ValueError):
                    verifier.pinned_baseline()

    def test_write_sql_refused(self):
        for sql in ('INSERT INTO users VALUES (1)', 'UPDATE credit_accounts SET x=1',
                    'DELETE FROM ledger_entries', 'CREATE TABLE bad (id INT)',
                    'SET FOREIGN_KEY_CHECKS=0', 'START TRANSACTION',
                    'SELECT * FROM lankapex_test_db.users'):
            with self.subTest(sql=sql):
                self.assertFalse(verifier.read_only_sql(sql))
        self.assertTrue(verifier.read_only_sql('SELECT COUNT(*) FROM users'))
        self.assertTrue(verifier.read_only_sql('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY'))


if __name__ == '__main__':
    unittest.main()

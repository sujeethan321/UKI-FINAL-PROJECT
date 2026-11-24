"""Existing restore policy/comparison tests. No credentials, DB or migrations."""
import copy
from contextlib import nullcontext, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend/scripts'))
import verify_existing_demo_restore as v
from test_demo_qr_recovery import snapshot, H


def fixtures():
    policy = v.RestorePolicy('synthetic_restore@localhost',frozenset({'SELECT'}))
    source = snapshot()
    source['inventory_fingerprints'] = {'synthetic':H}
    source['comparison_schema_sha256'] = H
    source['comparison_original_schema_sha256'] = H
    source['qr_structure_complete'] = False
    restored = copy.deepcopy(source)
    restored.update(database=v.RESTORE,account=policy.account,grant_scope=v.RESTORE,
                    privileges=sorted(policy.rights))
    return policy,source,restored


def after_fixture(before):
    after = copy.deepcopy(before)
    after['revision'] = v.END
    for table in v.recovery.QR_TABLES:
        after['tables'][table] = dict(rows=0,sha256=H,schema_sha256=H)
    after['tables']['alembic_version']['rows'] = 1
    after['comparison_schema_sha256'] = 'b'*64
    after['qr_structure_complete'] = True
    for table,name in (('business_join_links','fk_business_join_business'),
                       ('customer_join_requests','fk_customer_join_business'),
                       ('customer_join_requests','fk_customer_join_user'),
                       ('customer_join_requests','fk_customer_join_decider')):
        after['foreign_key_orphans'][table+':'+name] = 0
    return after


class ExistingRestoreTests(unittest.TestCase):
    def test_current_source_binding_is_available_without_network_or_app_settings(self):
        with patch('socket.socket',side_effect=AssertionError('network prohibited')):
            hashes=v.source_hashes()
        self.assertIn('backend/scripts/verify_existing_demo_restore.py',hashes)
        self.assertIn('backend/scripts/demo_qr_recovery.py',hashes)
        self.assertIn('backend/scripts/demo_qr_migration_guard.py',hashes)
        self.assertTrue(all(len(value)==64 for value in hashes.values()))

    def test_account_contract_rejects_unknown_wildcard_and_excessive_rights(self):
        for account in ('root@localhost','user@%','lankapex_demo_app@localhost',
                        'lankapex_demo_migrator@localhost','user@127.0.0.1','user@remote','x'*33+'@localhost'):
            with self.subTest(account=account), self.assertRaises(v.recovery.RecoveryStop):
                v.RestorePolicy(account,frozenset({'SELECT'}))
        for rights in ({'SELECT','DROP'},{'SELECT','LOCK TABLES'},{'SELECT','UPDATE'},{'ALL PRIVILEGES'}):
            with self.subTest(rights=rights), self.assertRaises(v.recovery.RecoveryStop):
                v.RestorePolicy('synthetic_restore@localhost',frozenset(rights))
        for rights in ({'SELECT'},v.MINIMUM,v.MINIMUM | {'DELETE'}):
            v.RestorePolicy('synthetic_restore@localhost',frozenset(rights))

    def test_exact_targets_and_original_recovery_contract_unchanged(self):
        policy,source,restored=fixtures()
        adapter=v.ExistingRestoreAdapter(policy,None,connector=Mock(side_effect=AssertionError('network')))
        self.assertEqual(adapter.capture_policy(v.RESTORE)[2:],(v.START,v.recovery.TABLES))
        for target in ('lankapex_db','lankapex_test_db',v.recovery.RESTORE,'other'):
            with self.subTest(target=target), self.assertRaises(v.recovery.RecoveryStop):
                adapter.capture_policy(target)
        with self.assertRaises(v.recovery.RecoveryStop):
            v.recovery.validate_snapshot(restored,v.RESTORE)
        v.recovery.validate_snapshot(source)

    def test_complete_comparison_and_all_mismatch_categories(self):
        policy,source,restored=fixtures()
        v.compare_existing(source,restored,policy)
        changes=[lambda s:s.update(database='lankapex_db'),
                 lambda s:s.update(account='wrong@localhost'),
                 lambda s:s.update(privileges=['SELECT','DELETE']),
                 lambda s:s.update(revision=v.END),
                 lambda s:s['tables'].pop('users'),
                 lambda s:s['tables']['users'].update(sha256='b'*64),
                 lambda s:s['tables']['orders'].update(schema_sha256='b'*64),
                 lambda s:s['financial_fingerprints'].update(signed_account_balances='b'*64),
                 lambda s:s['foreign_key_orphans'].update(synthetic_fk=1),
                 lambda s:s.update(comparison_schema_sha256='b'*64),
                 lambda s:s.update(duplicate_profiles=1),
                 lambda s:s.update(active_roles='role')]
        for index,mutate in enumerate(changes):
            bad=copy.deepcopy(restored);mutate(bad)
            with self.subTest(case=index), self.assertRaises(v.recovery.RecoveryStop):
                v.compare_existing(source,bad,policy)

    def test_default_and_invalid_target_cannot_access_adapter(self):
        self.assertEqual(v.verify(NS())['status'],'OFFLINE_PREPARATION')
        with patch.object(v.recovery,'WindowsPrivateStore',side_effect=AssertionError('private access')), redirect_stdout(StringIO()):
            self.assertEqual(v.main([]),0)
            self.assertEqual(v.main(['--execute','--confirm-source','lankapex_db']),1)
        with self.assertRaises(v.recovery.RecoveryStop):
            v.verify(NS(),execute=True,confirm_source=v.SOURCE,confirm_restore='other')

    def test_comparison_orchestration_rechecks_source_without_migration(self):
        policy,source,restored=fixtures()
        adapter=Mock(policy=policy)
        adapter.snapshot.side_effect=[source,restored,copy.deepcopy(source)]
        with patch.object(v,'source_hashes',return_value={'synthetic':H}), patch.object(v,'rehearse_once') as rehearse:
            report=v.verify(adapter,execute=True,confirm_source=v.SOURCE,confirm_restore=v.RESTORE,
                            writer_ddl_pause=True,target_administration_pause=True)
        self.assertFalse(report['migration_verified'])
        self.assertFalse(report['production_migration_evidence_compatible'])
        rehearse.assert_not_called()
        self.assertEqual([c.args[0] for c in adapter.snapshot.call_args_list],[v.SOURCE,v.RESTORE,v.SOURCE])

    def test_source_or_content_drift_never_migrates_or_issues_result(self):
        policy,source,restored=fixtures()
        bad=copy.deepcopy(restored);bad['tables']['ledger_entries']['sha256']='b'*64
        adapter=Mock(policy=policy);adapter.snapshot.side_effect=[source,bad]
        with patch.object(v,'source_hashes',return_value={'synthetic':H}), patch.object(v,'rehearse_once') as rehearse, self.assertRaises(v.recovery.RecoveryStop):
            v.verify(adapter,execute=True,confirm_source=v.SOURCE,confirm_restore=v.RESTORE,
                     writer_ddl_pause=True,target_administration_pause=True,rehearsal=True,
                     approved_rehearsal=True,confirm_revision=v.END)
        rehearse.assert_not_called()

    def test_rehearsal_preserves_every_old_row_and_only_expected_schema_changes(self):
        policy,_source,before=fixtures()
        after=after_fixture(before)
        v.compare_rehearsal(before,after,policy)
        for change in (lambda s:s['tables']['users'].update(sha256='b'*64),
                       lambda s:s['tables']['orders'].update(rows=9),
                       lambda s:s.update(comparison_original_schema_sha256='b'*64),
                       lambda s:s['tables']['business_join_links'].update(rows=1),
                       lambda s:s['foreign_key_orphans'].pop('customer_join_requests:fk_customer_join_decider'),
                       lambda s:s.update(qr_structure_complete=False)):
            bad=copy.deepcopy(after);change(bad)
            with self.assertRaises(v.recovery.RecoveryStop):
                v.compare_rehearsal(before,bad,policy)

    def test_readonly_identity_rejects_other_scopes_and_wrong_account(self):
        policy,_source,_restored=fixtures()
        adapter=v.ExistingRestoreAdapter(policy,None)
        cursor=Mock()
        cursor.__enter__=Mock(return_value=cursor);cursor.__exit__=Mock(return_value=False)
        connection=Mock();connection.cursor.return_value=cursor
        row=(v.RESTORE,policy.account,3306,'NONE',0,'STRICT_TRANS_TABLES',1)
        cursor.fetchone.return_value=row
        good='GRANT SELECT ON `'+v.RESTORE.replace('_','\\_')+'`.* TO x'
        cursor.fetchall.return_value=[(good,)]
        self.assertEqual(adapter._identity(connection,v.RESTORE),['SELECT'])
        for bad in ('GRANT SELECT ON *.* TO x','GRANT SELECT ON `other`.* TO x',
                    good+' WITH GRANT OPTION',good.replace('SELECT','SELECT, DROP')):
            cursor.fetchall.return_value=[(bad,)]
            with self.subTest(grant=bad),self.assertRaises(v.recovery.RecoveryStop):
                adapter._identity(connection,v.RESTORE)
        for index,value in ((1,'wrong@localhost'),(2,3307),(3,'role'),(4,1),(6,0)):
            bad=list(row);bad[index]=value;cursor.fetchone.return_value=bad
            with self.subTest(field=index),self.assertRaises(v.recovery.RecoveryStop):
                adapter._identity(connection,v.RESTORE)

    def test_rehearsal_gate_rejects_wrong_connection_and_every_delete(self):
        policy,_source,_restored=fixtures()
        conn=NS(engine=NS(url=NS(host='127.0.0.1',port=3306,database=v.RESTORE,username='synthetic_restore')))
        gate=v.RehearsalGate(conn,policy);gate.executing=True;gate.writes_enabled=True
        for sql in ('DELETE FROM users','DROP TABLE users','INSERT INTO users VALUES (1)',
                    'USE lankapex_demo_db','CREATE DATABASE other'):
            with self.subTest(sql=sql),self.assertRaises(v.migration.Stop):
                gate.before_cursor(conn,None,sql,(),None,False)
        conn.engine.url.database=v.SOURCE
        with self.assertRaises(v.recovery.RecoveryStop):
            gate.before_cursor(conn,None,v.migration.AUDIT,(),None,False)

    def test_rehearsal_requires_explicit_authorization(self):
        for kwargs in ({},{'approved_rehearsal':True,'confirm_revision':v.START}):
            with self.assertRaises(v.recovery.RecoveryStop):
                v.verify(NS(),execute=True,confirm_source=v.SOURCE,confirm_restore=v.RESTORE,
                         writer_ddl_pause=True,target_administration_pause=True,rehearsal=True,**kwargs)

    def test_rehearsal_actual_adapter_sequence_is_mocked_and_once_only(self):
        import sqlalchemy as sa
        policy=v.RestorePolicy('synthetic_restore@localhost',frozenset(v.MINIMUM))
        adapter=Mock(policy=policy)
        conn=Mock()
        conn.__enter__=Mock(return_value=conn);conn.__exit__=Mock(return_value=False)
        conn.engine.url=NS(host='127.0.0.1',port=3306,database=v.RESTORE,username='synthetic_restore')
        callback=[None];calls=[]
        def execute(sql,params=()):
            if callback[0]:callback[0](conn,None,sql,params,None,False)
            calls.append(sql)
            return NS(scalar_one=lambda:1,scalars=lambda:NS(all=lambda:[v.START]),first=lambda:None,rowcount=1)
        conn.exec_driver_sql.side_effect=execute
        engine=Mock();engine.connect.return_value=conn
        def listen(_engine,_event,fn):
            if _engine is engine and _event == 'before_cursor_execute': callback[0]=fn
        def remove(_engine,_event,fn):
            if _engine is engine and _event == 'before_cursor_execute': callback[0]=None
        def upgrade():
            for sql in v.migration.expected_writes()[:4]:execute(sql)
        with (patch.object(sa,'create_engine',return_value=engine),
              patch.object(sa.event,'listen',side_effect=listen),patch.object(sa.event,'remove',side_effect=remove),
              patch.object(v.runpy,'run_path',return_value={'upgrade':upgrade}) as load,
              patch('alembic.migration.MigrationContext.configure',return_value=NS()),
              patch('alembic.operations.Operations',NS(context=lambda context:nullcontext())),
              patch.object(v.migration,'source_hashes',return_value={'synthetic':H})):
            v.rehearse_once(adapter)
        load.assert_called_once()
        conn.commit.assert_called_once()
        engine.dispose.assert_called_once()
        self.assertEqual(sum(sql.startswith('CREATE TABLE') for sql in calls),2)
        self.assertTrue(any('RELEASE_LOCK' in sql for sql in calls))

    def test_partial_rehearsal_failure_no_retry_no_false_result(self):
        policy,source,before=fixtures()
        policy=v.RestorePolicy(policy.account,frozenset(v.MINIMUM))
        before['privileges']=sorted(policy.rights)
        adapter=Mock(policy=policy);adapter.snapshot.side_effect=[source,before]
        with (patch.object(v,'source_hashes',return_value={'synthetic':H}),
              patch.object(v,'rehearse_once',side_effect=RuntimeError('private provider text')) as run,
              self.assertRaises(RuntimeError)):
            v.verify(adapter,execute=True,confirm_source=v.SOURCE,confirm_restore=v.RESTORE,
                     writer_ddl_pause=True,target_administration_pause=True,rehearsal=True,
                     approved_rehearsal=True,confirm_revision=v.END)
        run.assert_called_once()
        self.assertEqual(adapter.snapshot.call_count,2)

    def test_source_change_after_comparison_is_not_accepted(self):
        policy,source,before=fixtures()
        adapter=Mock(policy=policy);adapter.snapshot.side_effect=[source,before,source]
        with patch.object(v,'source_hashes',side_effect=[{'a':H},{'a':'b'*64}]), self.assertRaises(v.recovery.RecoveryStop):
            v.verify(adapter,execute=True,confirm_source=v.SOURCE,confirm_restore=v.RESTORE,
                     writer_ddl_pause=True,target_administration_pause=True)

    def test_existing_target_self_fk_normalization_never_masks_external_schema(self):
        ddl='CREATE TABLE `users` (`id` bigint, FOREIGN KEY (`id`) REFERENCES `'+v.RESTORE+'`.`businesses` (`id`)) ENGINE=InnoDB'
        normalized=v.recovery.canonical_self_references(ddl,v.RESTORE)
        v.recovery.validate_ddl('users',normalized)
        with self.assertRaises(v.recovery.RecoveryStop):
            v.recovery.validate_ddl('users',v.recovery.canonical_self_references(ddl.replace(v.RESTORE,v.SOURCE),v.RESTORE))

    def test_enriched_metadata_in_same_snapshot_is_compared_without_identity_rewrite(self):
        policy,_source,_before=fixtures()
        adapter=v.ExistingRestoreAdapter(policy,None)
        metadata={key:[] for key in v.migration.META}
        metadata['keys']=[('users','fk_synthetic','id',1,v.RESTORE,'businesses','business_id')]
        lookup={sql:key for key,sql in v.migration.META.items()}
        connection=NS(exec_driver_sql=lambda sql:metadata[lookup[sql]])
        inspector=NS(get_unique_constraints=lambda t:[])
        result={'database':v.RESTORE,'account':policy.account}
        adapter.enrich_capture(connection,inspector,result,{},v.RESTORE)
        original_hash=result['comparison_schema_sha256']
        self.assertEqual(result['database'],v.RESTORE)
        self.assertEqual(result['account'],policy.account)
        metadata['keys'][0]=('users','fk_synthetic','id',1,'other','businesses','business_id')
        with self.assertRaises(v.recovery.RecoveryStop):
            adapter.enrich_capture(connection,inspector,{}, {},v.RESTORE)
        self.assertEqual(len(original_hash),64)

    def test_typed_fingerprints_preserve_decimal_and_binary_types(self):
        from decimal import Decimal
        fp=v.recovery.row_fingerprint
        self.assertEqual(fp([(Decimal('70.10'),b'\x00\xff',None)]),fp([(Decimal('70.10'),b'\x00\xff',None)]))
        self.assertNotEqual(fp([(Decimal('70.10'),)]),fp([('70.10',)]))

    def test_original_demo_guard_still_refuses_rehearsal_evidence_for_this_target(self):
        from test_populated_demo_qr_runner import fixtures as demo_fixtures
        bundle,hashes,_live=demo_fixtures()
        bundle['rehearsal']['database']=v.RESTORE
        with self.assertRaises(v.migration.Stop):
            v.migration.validate_evidence(bundle,hashes)

    def test_full_existing_restore_capture_remains_readonly_and_uses_actual_identity(self):
        import sqlalchemy as sa
        from test_demo_qr_recovery import archive_fixture, FINANCIAL
        policy,source,_before=fixtures()
        _snapshot,archive=archive_fixture()
        calls=[]
        class Result:
            def __init__(self,rows):self.rows=rows
            def __iter__(self):return iter(self.rows)
            def one(self):return self.rows[0]
            def scalar_one(self):return self.rows[0][0]
            def scalars(self):return NS(all=lambda:[row[0] for row in self.rows])
            def close(self):pass
        class Connection:
            connection=NS(driver_connection=NS())
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def rollback(self):calls.append('ROLLBACK')
            def execution_options(self,**kwargs):return self
            def exec_driver_sql(self,sql):
                calls.append(sql)
                if sql.startswith('SHOW CREATE TABLE'):
                    name=sql.split('`')[1];return Result([(name,archive['tables'][name]['ddl'])])
                if sql.startswith('SELECT version_num') or 'FROM `alembic_version`' in sql:return Result([(v.START,)])
                if sql=='SELECT VERSION()':return Result([('8.0.46',)])
                if sql.startswith('SELECT DEFAULT_CHARACTER'):return Result([('utf8mb4','utf8mb4_unicode_ci')])
                if sql.startswith('SELECT COUNT') or 'information_schema.ROUTINES' in sql:return Result([(0,)])
                return Result([(1,)])
        inspector=NS(get_table_names=lambda:sorted(v.recovery.TABLES),get_view_names=lambda:[],
            get_columns=lambda n:[{'name':archive['tables'][n]['columns'][0]}],
            get_pk_constraint=lambda n:{'constrained_columns':archive['tables'][n]['primary_key']},
            get_foreign_keys=lambda n:[dict(name='fk_synthetic',constrained_columns=['record_id'],
                referred_columns=['record_id'],referred_table='businesses',referred_schema=None)] if n=='users' else [])
        inventory=NS(PROJECTIONS={n:'record_id' for n in FINANCIAL if n not in ('signed_account_balances','ledger_type_totals')},
            BALANCES='SELECT synthetic_balance',LEDGER_TOTALS='SELECT synthetic_totals',DUPLICATES='SELECT COUNT(*) FROM synthetic',
            fingerprint=v.recovery.row_fingerprint)
        adapter=v.ExistingRestoreAdapter(policy,None)
        engine=Mock();engine.connect.return_value=Connection()
        with (patch.object(sa,'create_engine',return_value=engine),patch.object(sa,'inspect',return_value=inspector),
              patch.dict(sys.modules,{'inventory_demo_database':inventory}),
              patch.object(adapter,'_identity',return_value=['SELECT']),
              patch.object(adapter,'enrich_capture'),
              patch.object(adapter,'current_source_hashes',return_value=source['source_hashes'])):
            report,_records=adapter._capture(v.RESTORE)
        self.assertEqual(report['database'],v.RESTORE)
        self.assertEqual(report['account'],policy.account)
        self.assertIn('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY',calls)
        self.assertGreaterEqual(calls.count('ROLLBACK'),2)
        self.assertFalse(any(sql.startswith(('INSERT','UPDATE','DELETE','CREATE','ALTER')) for sql in calls))
        engine.dispose.assert_called_once()

    def test_private_storage_failure_sanitized_before_credentials(self):
        args=['--execute','--confirm-source',v.SOURCE,'--confirm-restore',v.RESTORE,
              '--approved-restore-account','synthetic_restore@localhost','--approved-restore-grants','SELECT',
              '--confirm-private-console','--confirm-dba-object-review','--confirm-writer-ddl-pause',
              '--confirm-target-administration-pause','--tls-ca',str(Path(__file__).resolve()),'--evidence-id','1'*32]
        with (patch.object(v.recovery,'WindowsPrivateStore',side_effect=RuntimeError('secret password')),
              patch.object(v,'ExistingRestoreAdapter') as adapter,patch.object(v.migration,'no_reparse'),
              redirect_stdout(StringIO()) as output):
            self.assertEqual(v.main(args),1)
        adapter.assert_not_called()
        self.assertNotIn('secret password',output.getvalue())
        self.assertIn('stage=protected_evidence_prerequisite',output.getvalue())


if __name__ == '__main__':
    unittest.main()

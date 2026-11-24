"""Step 389: mocked database/provider boundaries, no migration execution."""
import importlib.util
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import tempfile
import json
import ssl
import subscription_suite as base  # Blocks network and replaces real config/engine.
from sqlalchemy import CheckConstraint, Column, MetaData, String, Table, update
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.dialects import mysql
from alembic.ddl.base import AddColumn

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('step389_tests', ROOT/'output/step389/driver_migration.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
guards = runner.load('test389_guards', 'output/step322/guarded_viva_setup.py')
checkpoint = runner.load('test389_hash', 'output/step336/checkpoint_viva.py')


class Result:
    def __init__(self, rows): self.rows = rows
    def __iter__(self): return iter(self.rows)
    def one(self): return self.rows[0]
    def all(self): return self.rows
    def scalar_one(self): return self.rows[0][0]
    def scalars(self): return Result([r[0] for r in self.rows])


class Inspection:
    def __init__(self, after): self.after = after
    def get_table_names(self): return sorted(set(base.Base.metadata.tables) - (set() if self.after else runner.NEW_TABLES)) + ['alembic_version']
    def get_view_names(self): return []
    def get_pk_constraint(self, name): return {'constrained_columns': [c.name for c in base.Base.metadata.tables[name].primary_key]}
    def get_check_constraints(self, name): return [{'name': c.name, 'sqltext': str(c.sqltext)} for c in base.Base.metadata.tables[name].constraints if isinstance(c, CheckConstraint)]


class Connection:
    def __init__(self, after=False): self.after = after; self.sql = []; self.bad_marker = False
    def exec_driver_sql(self, sql, params=()):
        self.sql.append(sql)
        if 'version_num' in sql: return Result([(runner.NEW if self.after else runner.OLD,)])
        if sql == 'SELECT VERSION()': return Result([('8.0.46',)])
        if 'transaction_isolation' in sql: return Result([('REPEATABLE-READ',)])
        if 'DEFAULT_CHARACTER' in sql: return Result([('utf8mb4','utf8mb4_unicode_ci')])
        if 'SELECT ENGINE' in sql: return Result([('InnoDB',)] * (35 if self.after else 33))
        if 'TABLE_CONSTRAINTS' in sql: return Result([(c.name,'YES') for c in base.Base.metadata.tables[params[1]].constraints if isinstance(c,CheckConstraint)])
        if sql.startswith('SELECT COUNT(*)'): return Result([(0,)])
        if sql.startswith('SHOW CREATE TABLE'):
            ddl = 'CREATE TABLE synthetic (\n'
            if self.after and 'driver_profiles' in sql:
                ddl += "  `legacy_document_exempt` tinyint(1) NOT NULL DEFAULT '0',\n"
            return Result([('table',ddl+'  PRIMARY KEY (`user_id`)\n)')])
        if 'CAST(' in sql: return Result([(1, 0 if self.bad_marker else 1),(2,0)])
        if sql.startswith('SELECT '): return Result([(1,'fictional-fixture')])
        raise AssertionError(sql)


class Readiness(TestCase):
    def test_graph_hash_parent_single_head(self):
        self.assertIsNotNone(runner.graph_check())
        self.assertEqual((runner.OLD,runner.NEW),('9d1a6f4e0c37','ae2b7c5f1d48'))
        with patch.object(runner,'MIGRATION_SHA256','wrong'), self.assertRaises(RuntimeError): runner.graph_check()

    def test_mysql_compiled_exact_migration_allowlist(self):
        allowed = runner.approved_sql(base.Base.metadata)
        gate = runner.migration_gate(allowed)
        for sql in allowed: gate(None,None,sql,(),None,False)
        # Capture actual migration operations, compiling them without any engine.
        migration = runner.load('test389_revision','backend/alembic/versions/ae2b7c5f1d48_driver_verification_documents.py')
        captured=[]
        class Op:
            def add_column(self, name, col): captured.append(str(AddColumn(name,col).compile(dialect=mysql.dialect())))
            def execute(self, sql): captured.append(str(sql))
            def create_table(self, name, *args, **kw):
                # Existing FK targets are represented only in metadata; no SQL runs.
                metadata=MetaData()
                for existing in ('users','driver_profiles'):
                    Table(existing,metadata,Column('user_id',base.Base.metadata.tables[existing].c.user_id.type,primary_key=True))
                for new_name in runner.NEW_TABLES - {name}:
                    base.Base.metadata.tables[new_name].to_metadata(metadata)
                table=Table(name,metadata,*args,**kw)
                captured.append(str(CreateTable(table).compile(dialect=mysql.dialect())))
            def create_index(self,name,table,columns):
                index=next(i for i in base.Base.metadata.tables[table].indexes if i.name==name)
                captured.append(str(CreateIndex(index).compile(dialect=mysql.dialect())))
        with patch.object(migration,'op',Op()): migration.upgrade()
        for sql in captured: gate(None,None,sql,(),None,False)
        version=Table('alembic_version',MetaData(),Column('version_num',String(32)))
        sql=str(update(version).where(version.c.version_num==runner.OLD).values(version_num=runner.NEW).compile(dialect=mysql.dialect(),compile_kwargs={'literal_binds':True}))
        gate(None,None,sql,(),None,False)
        self.assertEqual(len(captured),6)

    def test_unexpected_financial_or_delivery_writes_rejected(self):
        gate=runner.migration_gate(runner.approved_sql(base.Base.metadata))
        for sql in ('DROP TABLE users','UPDATE ledger_entries SET amount=0','DELETE FROM delivery_assignments',
                    'ALTER TABLE driver_profiles DROP COLUMN approval_status',
                    "UPDATE driver_profiles SET legacy_document_exempt=1",
                    "UPDATE driver_profiles SET legacy_document_exempt=1 WHERE approval_status='pending'",
                    'SELECT * FROM lankapex_demo_db.users','SELECT 1 INTO OUTFILE \'x\''):
            with self.assertRaises(RuntimeError): gate(None,None,sql,(),None,False)

    def test_schema_before_after_and_real_drift(self):
        for after in (False,True):
            with patch('sqlalchemy.inspect',return_value=Inspection(after)), patch('alembic.migration.MigrationContext.configure',return_value=object()), patch('alembic.autogenerate.compare_metadata',return_value=[]) as comparison:
                runner.schema(Connection(after),base.Base.metadata,guards,after)
                tables=comparison.call_args.args[1].tables
                self.assertEqual(len(tables),34 if after else 32)
                self.assertEqual('legacy_document_exempt' in tables['driver_profiles'].c,after)
            with patch('sqlalchemy.inspect',return_value=Inspection(after)), patch('alembic.migration.MigrationContext.configure',return_value=object()), patch('alembic.autogenerate.compare_metadata',return_value=[('unexpected_column',)]), self.assertRaises(RuntimeError):
                runner.schema(Connection(after),base.Base.metadata,guards,after)

    def test_preserves_every_original_table_and_exact_exemption_set(self):
        before=runner.snapshot(Connection(),base.Base.metadata,checkpoint)
        after=runner.snapshot(Connection(True),base.Base.metadata,checkpoint,True)
        self.assertEqual(before,after)
        self.assertEqual(len(before),33)  # 32 original tables plus exemption-set digest.
        self.assertTrue({'ledger_entries','credit_accounts','driver_profiles','delivery_assignments','delivery_status_events'} <= before.keys())
        bad=Connection(True); bad.bad_marker=True
        self.assertNotEqual(before,runner.snapshot(bad,base.Base.metadata,checkpoint,True))
        self.assertNotIn('fictional-fixture',str(before))

    def test_fresh_dba_and_continuing_writer_ddl_attestations(self):
        fresh=datetime.now(timezone.utc).isoformat()
        with patch('builtins.input',side_effect=[fresh,'1 YES 0 0 0 DDL_PAUSED','WRITERS_PAUSED']): self.assertEqual(runner.freeze_gate(),fresh)
        for timestamp in ('invalid',datetime.now().isoformat(),(datetime.now(timezone.utc)-timedelta(minutes=6)).isoformat(),(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()):
            with self.assertRaises(RuntimeError): runner.validate_observation(timestamp)
        with patch('builtins.input',side_effect=[fresh,'1 YES 1 0 0 DDL_PAUSED']), self.assertRaises(RuntimeError): runner.freeze_gate()

    def test_recovery_requires_new_explicit_decision(self):
        with patch('builtins.input',return_value='WAIVE ae2b7c5f1d48'): self.assertIn('WAIVED',runner.recovery_decision(True)['decision'])
        with patch('builtins.input',side_effect=['RECOVERY_VERIFIED','a'*64]): self.assertIn('OPERATOR_ATTESTED',runner.recovery_decision(False)['decision'])
        for waive in (True,False):
            with patch('builtins.input',return_value='previous waiver'), self.assertRaises(RuntimeError): runner.recovery_decision(waive)

    def test_noninteractive_stops_before_credentials_network_and_alembic(self):
        with patch('sys.argv',['guard','--apply-authorized-driver-migration']), patch('sys.stdin.isatty',return_value=False), patch.object(runner,'load') as load, patch('alembic.command.upgrade') as upgrade, self.assertRaises(RuntimeError): runner.main()
        load.assert_not_called(); upgrade.assert_not_called()

    def test_exact_tls_identity_privileges_and_no_reconnect(self):
        events={}
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
        ctx.minimum_version=ssl.TLSVersion.TLSv1_2
        db=SimpleNamespace(connection_options=lambda settings: {'ssl':ctx})
        engine=object()
        with patch('sqlalchemy.create_engine',return_value=engine), patch('sqlalchemy.event.listen',side_effect=lambda e,n,f: events.update({n:f})):
            runner.migrator_engine(db,'fictional-not-a-credential',guards)
        options=dict(host='127.0.0.1',port=3306,database=runner.TARGET,user=guards.MIGRATOR,ssl=ctx)
        events['do_connect'](None,None,None,options)
        with self.assertRaises(RuntimeError): events['do_connect'](None,None,None,options)
        conn=SimpleNamespace(connection=SimpleNamespace(driver_connection=SimpleNamespace(commit=lambda:None)))
        with patch.object(guards,'guard_migrator_connection') as identity, patch.object(guards,'scalar',side_effect=[0,runner.OLD]):
            events['engine_connect'](conn)
            identity.assert_called_once_with(conn,0)
        with patch.object(guards,'guard_migrator_connection',side_effect=RuntimeError('privilege mismatch')), patch.object(guards,'scalar',return_value=0), self.assertRaises(RuntimeError):
            events['engine_connect'](conn)

    def test_apply_orchestration_success_failure_and_exclusive_no_retry_marker(self):
        # No real engine or Alembic operation is called. Only fictional temp evidence.
        class Engine:
            def connect(self): return self
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def exec_driver_sql(self,sql): return Result([(runner.OLD,)])
            def dispose(self): pass
        for fails in ('none','ddl','preservation'):
            with tempfile.TemporaryDirectory() as tmp:
                report=Path(tmp)/'fictional-evidence.json'
                db=SimpleNamespace(engine=Engine(),DATABASE_URL='opaque-url',Base=base.Base)
                launcher=SimpleNamespace(prepare=lambda password: (None,db,SimpleNamespace(probe_engine=Engine())))
                modules={'step389_runtime':launcher,'step389_guards':guards,'step389_hashes':checkpoint}
                state={'driver_profiles':{'count':2,'sha256':'fictional'},'legacy_exemption_set':{'count':2,'sha256':'fictional'}}
                post={'changed_financial_fingerprint':True} if fails=='preservation' else state
                with patch('sys.argv',['guard','--apply-authorized-driver-migration','--accept-no-backup']), patch('sys.stdin.isatty',return_value=True), patch.object(runner,'REPORT',report), patch.object(runner,'verify_private_directory'), patch.object(runner,'graph_check',return_value=object()), patch.object(runner,'load',side_effect=lambda name,path: modules[name]), patch.object(runner,'recovery_decision',return_value={'decision':'WAIVED_FOR_ae2b7c5f1d48'}), patch.object(runner,'freeze_gate',return_value=datetime.now(timezone.utc).isoformat()), patch.object(runner.getpass,'getpass',return_value='fictional'), patch('builtins.input',return_value=runner.TARGET), patch('builtins.print'), patch.object(runner,'runtime_state',side_effect=[state,post]), patch.object(runner,'migrator_engine',return_value=(Engine(),'opaque-migrator-url')), patch('sqlalchemy.event.listen'), patch('alembic.command.upgrade',side_effect=RuntimeError('simulated partial DDL') if fails=='ddl' else None) as upgrade:
                    if fails!='none':
                        with self.assertRaises(RuntimeError): runner.main()
                    else: runner.main()
                    upgrade.assert_called_once()
                    self.assertEqual(upgrade.call_args.args[1],runner.NEW)
                    self.assertTrue(report.is_file())
                    self.assertEqual(json.loads(report.read_text())['before'],state)
                    with self.assertRaises(RuntimeError): runner.main()
                    upgrade.assert_called_once()  # Marker blocks a second apply.

    def test_unexpected_inventory_and_wrong_revision_stop(self):
        inspector=Inspection(False)
        with patch.object(inspector,'get_table_names',return_value=inspector.get_table_names()+['unexpected']), patch('sqlalchemy.inspect',return_value=inspector), self.assertRaises(RuntimeError):
            runner.schema(Connection(),base.Base.metadata,guards,False)
        with patch('sqlalchemy.inspect',return_value=Inspection(False)), self.assertRaises(RuntimeError):
            runner.schema(Connection(True),base.Base.metadata,guards,False)


if __name__ == '__main__': main(verbosity=2)

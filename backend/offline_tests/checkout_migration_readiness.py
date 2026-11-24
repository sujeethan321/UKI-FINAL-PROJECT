"""Step 347 tests: no MySQL, Alembic execution, private files or provider calls."""
import importlib.util
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

import subscription_suite as base  # Network blocked, dotenv/MySQL modules replaced.
from sqlalchemy import CheckConstraint, Column, MetaData, String, Table, update
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.dialects import mysql

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('step347_offline_runner', ROOT/'output/step347/checkout_migration.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
guards = runner.load('step347_offline_guards','output/step322/guarded_viva_setup.py')
checkpoint = runner.load('step347_offline_hashes','output/step336/checkpoint_viva.py')


class Result:
    def __init__(self, rows): self.rows=rows
    def __iter__(self): return iter(self.rows)
    def one(self): return self.rows[0]
    def all(self): return self.rows
    def scalar_one(self): return self.rows[0][0]
    def scalars(self): return Result([row[0] for row in self.rows])


class Inspection:
    def __init__(self, after): self.after=after
    def get_table_names(self): return list(set(base.Base.metadata.tables)-({runner.TABLE} if not self.after else set()))+['alembic_version']
    def get_view_names(self): return []
    def get_pk_constraint(self,name): return {'constrained_columns':[c.name for c in base.Base.metadata.tables[name].primary_key]}
    def get_check_constraints(self,name): return [{'name':c.name,'sqltext':str(c.sqltext)} for c in base.Base.metadata.tables[name].constraints if isinstance(c,CheckConstraint)]


class Connection:
    def __init__(self,after=False): self.after=after; self.sql=[]
    def exec_driver_sql(self,sql,params=()):
        self.sql.append(sql)
        if 'version_num' in sql: return Result([(runner.NEW if self.after else runner.OLD,)])
        if sql=='SELECT VERSION()': return Result([('8.0.46',)])
        if 'transaction_isolation' in sql: return Result([('REPEATABLE-READ',)])
        if 'DEFAULT_CHARACTER' in sql: return Result([('utf8mb4','utf8mb4_unicode_ci')])
        if 'SELECT ENGINE' in sql: return Result([('InnoDB',)]*(33 if self.after else 32))
        if 'TABLE_CONSTRAINTS' in sql:
            return Result([(c.name,'YES') for c in base.Base.metadata.tables[params[1]].constraints if isinstance(c,CheckConstraint)])
        if sql=='SELECT COUNT(*) FROM subscription_checkout_attempts': return Result([(0,)])
        if sql.startswith('SELECT * FROM '): return Result([(1,'synthetic-only')])
        if sql.startswith('SHOW CREATE TABLE '): return Result([('table','synthetic DDL '+sql)])
        raise AssertionError(sql)


class ReadinessTests(TestCase):
    def test_pinned_source_and_single_parent_graph_without_alembic_execution(self):
        self.assertIsNotNone(runner.graph_check())
        self.assertEqual((runner.OLD,runner.NEW),('8c0f5e3d9b26','9d1a6f4e0c37'))

    def test_compiled_mysql_new_table_index_and_exact_version_update_are_allowed(self):
        table=base.Base.metadata.tables[runner.TABLE]
        sqls=[str(CreateTable(table).compile(dialect=mysql.dialect()))]
        sqls += [str(CreateIndex(index).compile(dialect=mysql.dialect())) for index in table.indexes]
        version=Table('alembic_version',MetaData(),Column('version_num',String(32)))
        sqls.append(str(update(version).where(version.c.version_num==runner.OLD).values(version_num=runner.NEW)
            .compile(dialect=mysql.dialect(),compile_kwargs={'literal_binds':True})))
        for sql in sqls: runner.migration_sql(None,None,sql,None,None,False)
        self.assertIn('ON DELETE RESTRICT',sqls[0])
        self.assertEqual({tuple(c.name for c in cons.columns) for cons in table.constraints if cons.__class__.__name__=='UniqueConstraint'},
            {('active_business_id',),('request_key',),('stripe_session_id',)})

    def test_unrelated_ddl_dml_other_database_and_unpinned_versions_stop(self):
        for sql in ['DROP TABLE businesses','ALTER TABLE businesses ADD x INT','DELETE FROM ledger_entries',
            'CREATE TABLE lankapex_demo_db.subscription_checkout_attempts (x INT)',
            'UPDATE business_subscriptions SET plan=\'FREE\'',
            "UPDATE alembic_version SET version_num='wrong' WHERE alembic_version.version_num='8c0f5e3d9b26'",
            'CREATE TABLE subscription_checkout_attempts (x INT); DROP TABLE orders']:
            with self.assertRaises(RuntimeError): runner.migration_sql(None,None,sql,None,None,False)

    def test_full_schema_checks_cover_32_before_and_33_after(self):
        for after in (False,True):
            conn=Connection(after)
            with patch('sqlalchemy.inspect',return_value=Inspection(after)), \
                 patch('alembic.migration.MigrationContext.configure',return_value=object()), \
                 patch('alembic.autogenerate.compare_metadata',return_value=[]) as compare:
                runner.schema(conn,base.Base.metadata,guards,after)
                self.assertEqual(len(compare.call_args.args[1].tables),32 if after else 31)
                self.assertEqual(sum('TABLE_CONSTRAINTS' in sql for sql in conn.sql),32 if after else 31)
            with patch('sqlalchemy.inspect',return_value=Inspection(after)), \
                 patch('alembic.migration.MigrationContext.configure',return_value=object()), \
                 patch('alembic.autogenerate.compare_metadata',return_value=[('real_mismatch',)]), self.assertRaises(RuntimeError):
                runner.schema(conn,base.Base.metadata,guards,after)

    def test_preservation_hashes_include_all_existing_subscription_and_application_tables(self):
        conn=Connection()
        state=runner.snapshot(conn,base.Base.metadata,checkpoint)
        self.assertEqual(len(state),31)
        self.assertTrue({'subscription_trial_grants','business_subscriptions','subscription_payment_events','ledger_entries','orders','delivery_requests'}<=state.keys())
        self.assertNotIn(runner.TABLE,state)
        self.assertTrue(all(set(value)=={'count','sha256','ddl_sha256'} for value in state.values()))
        self.assertFalse(any(sql.startswith(('INSERT','UPDATE','DELETE','CREATE','ALTER','DROP')) for sql in conn.sql))

    def test_noninteractive_main_stops_before_credentials_or_connections(self):
        with patch('sys.argv',['runner','--apply-authorized-checkout-migration','--accept-no-backup']), \
             patch('sys.stdin.isatty',return_value=False), patch.object(runner,'load') as load, self.assertRaises(RuntimeError):
            runner.main()
        load.assert_not_called()


if __name__=='__main__': main(verbosity=2)

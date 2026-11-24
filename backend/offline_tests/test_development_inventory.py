"""Synthetic development audit tests: no application imports or connections."""
import ast
from contextlib import redirect_stdout
from decimal import Decimal
import hashlib
import importlib.util
from io import StringIO
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('development_inventory', ROOT / '.server-logs/phase33-development-audit.py')
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


class Result:
    def __init__(self, rows): self.rows = rows
    def one(self): return self.rows[0]
    def __iter__(self): return iter(self.rows)
    def scalar_one(self): return self.rows[0][0]


class InventoryTests(unittest.TestCase):
    def config(self):
        settings = NS(APP_ENV='development', MYSQL_DATABASE='lankapex_db', MYSQL_HOST='localhost', MYSQL_PORT=3306, MYSQL_USER='lankapex_app')
        url = NS(database='lankapex_db', host='localhost', port=3306, username='lankapex_app')
        args = NS(confirm_host='localhost', confirm_port=3306, confirm_database='lankapex_db', confirm_account='lankapex_app@localhost', confirm_privileges='SELECT,INSERT,UPDATE')
        return settings, url, args

    def test_exact_configuration(self):
        self.assertEqual(a.validate_configuration(*self.config()), {'SELECT','INSERT','UPDATE'})

    def test_configuration_identity_rejections(self):
        for index, field, value in [(0,'APP_ENV','production'),(0,'MYSQL_DATABASE','other'),
                (0,'MYSQL_PORT',3307),(1,'port',3307),(1,'host','127.0.0.1'),
                (1,'username','root'),(2,'confirm_account','root@%'),(2,'confirm_port',3307),
                (2,'confirm_privileges','SELECT,DROP'),(2,'confirm_privileges','ALL PRIVILEGES')]:
            values = self.config()
            setattr(values[index],field,value)
            with self.subTest(field=field), self.assertRaises(a.AuditStop):
                a.validate_configuration(*values)

    def connection(self, identity=None, grants=None):
        calls = []
        def execute(sql):
            calls.append(sql)
            return Result([identity or ('lankapex_db','lankapex_app@localhost',3306,'NONE',0)]) if sql.startswith('SELECT') else Result([(x,) for x in grants or [r'GRANT USAGE ON *.* TO `lankapex_app`@`localhost`', r'GRANT SELECT ON `lankapex\_db`.* TO `lankapex_app`@`localhost`']])
        return NS(exec_driver_sql=execute), calls

    def test_exact_live_identity_and_grants(self):
        c,calls = self.connection()
        a.validate_live_identity(c,'lankapex_app@localhost',{'SELECT'})
        self.assertEqual(len(calls),2)

    def test_live_identity_roles_port_account_and_partial_revokes(self):
        for row in [('other','lankapex_app@localhost',3306,'NONE',0),
                    ('lankapex_db','root@localhost',3306,'NONE',0),
                    ('lankapex_db','lankapex_app@localhost',3307,'NONE',0),
                    ('lankapex_db','lankapex_app@localhost',3306,'role',0),
                    ('lankapex_db','lankapex_app@localhost',3306,'NONE',1)]:
            c,calls=self.connection(identity=row)
            with self.subTest(row=row), self.assertRaises(a.AuditStop):
                a.validate_live_identity(c,'lankapex_app@localhost',{'SELECT'})
            self.assertEqual(len(calls),1)

    def test_excessive_global_wrong_scope_and_grant_option_rejected(self):
        for grant in ['GRANT SELECT ON *.* TO x',r'GRANT SELECT ON `lankapex_db`.* TO x',
                      r'GRANT SELECT ON `other`.* TO x',r'GRANT SELECT, DROP ON `lankapex\_db`.* TO x',
                      r'GRANT SELECT ON `lankapex\_db`.* TO x WITH GRANT OPTION', 'GRANT role TO x']:
            c,_calls=self.connection(grants=[grant])
            with self.subTest(grant=grant), self.assertRaises(a.AuditStop):
                a.validate_live_identity(c,'lankapex_app@localhost',{'SELECT'})

    def test_default_no_import_connection_or_output_file(self):
        with patch('builtins.open',side_effect=AssertionError('no files')), redirect_stdout(StringIO()) as out:
            self.assertEqual(a.main([]),0)
        self.assertIn('preparation only',out.getvalue())

    def test_invalid_execution_stops_before_imports_and_sanitizes(self):
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(a.main(['--execute','--confirm-host','secret-password']),1)
        self.assertEqual(out.getvalue(),'STOP: development inventory category=target_confirmation\n')

    def test_no_output_option_or_evidence_write_calls(self):
        source=Path(SPEC.origin).read_text()
        tree=ast.parse(source)
        self.assertFalse(any(isinstance(n,ast.Assert) for n in ast.walk(tree)))
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                             and n.func.attr in ('write_text','write_bytes','unlink','execute_write') for n in ast.walk(tree)))
        self.assertNotIn('phase33-development-audit.json',source)

    def test_statement_guard(self):
        for sql in ['SELECT DATABASE()','SHOW GRANTS FOR CURRENT_USER()',*a.TRANSACTION_SQL]:
            self.assertTrue(a.sql_allowed(sql))
        for sql in ['INSERT INTO users VALUES (1)','DELETE FROM users','CREATE TABLE x(id int)','UPDATE users SET x=1','COMMIT','DROP DATABASE x']:
            self.assertFalse(a.sql_allowed(sql))

    def test_unexpected_errors_and_private_text_are_not_disclosed(self):
        for error in (RuntimeError('mysql://secret-password@host/private'),
                      a.AuditStop('secret password'), ValueError('private records')):
            self.assertEqual(a.failure_category(error),'inventory_unavailable')
        self.assertEqual(a.failure_category(a.AuditStop('live_identity')),'live_identity')

    def test_missing_schema_report_and_fk_audit(self):
        calls=[]
        def execute(sql,params=None):
            calls.append((sql,params))
            return Result([(0,)])
        c=NS(exec_driver_sql=execute,dialect=NS(identifier_preparer=NS(quote=lambda x:'`'+x+'`')))
        inspector=NS(get_foreign_keys=lambda t:[dict(referred_schema=None,referred_table='users',constrained_columns=['user_id'],referred_columns=['user_id'])])
        result=dict(schema={'users':dict(columns=[],pk={},fk=[],indexes=[],unique=[],checks=[])},revision=['c9d5e8f7a237'],column_drift=[])
        a.add_readiness(c,inspector,['users'],result,NS(metadata=NS(tables={'users':None,'business_join_links':None})))
        self.assertFalse(result['current_schema_compatible'])
        self.assertIsNone(result['prerequisites']['duplicate_customer_links'])
        self.assertEqual(set(result['active_users_by_role']),{'shop_owner','customer','driver','admin'})
        self.assertTrue(any('NOT EXISTS' in sql for sql,_ in calls))
        self.assertTrue(all(sql.startswith('SELECT ') for sql,_ in calls))

    def test_historical_financial_algorithms_preserved_and_reversal_aware(self):
        # Compile only pure arithmetic definitions; never import app Settings/models.
        tree=ast.parse((ROOT/'backend/app/services/ledger_service.py').read_text())
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('effective_entries','entry_delta','account_balances')]
        scope={'Decimal':Decimal,'ZERO':Decimal('0.00')}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'pure_ledger','exec'),scope)
        entries=[NS(credit_account_id=1,entry_id=1,entry_type='credit_sale',amount=Decimal('100.20'),reverses_entry_id=None),
                 NS(credit_account_id=1,entry_id=2,entry_type='repayment',amount=Decimal('30.10'),reverses_entry_id=None)]
        self.assertEqual(scope['account_balances'](entries),{1:Decimal('70.10')})
        entries.append(NS(credit_account_id=1,entry_id=3,entry_type='reversal',amount=Decimal('30.10'),reverses_entry_id=2))
        self.assertEqual(scope['account_balances'](entries),{1:Decimal('100.20')})
        source=Path(SPEC.origin).read_text()
        self.assertIn("default=str,separators=(',',':')",source)
        self.assertIn('balances=account_balances(entries)',source)
        self.assertIn("[[k,str(v)] for k,v in sorted(balances.items())]",source)

    def test_collect_uses_readonly_snapshot_preserves_hashes_and_never_writes(self):
        calls=[]
        class Rows(Result):
            def all(self): return self.rows
            def scalars(self): return [row[0] for row in self.rows]
        class Connection:
            dialect=NS(identifier_preparer=NS(quote=lambda x:'`'+x+'`'))
            def __enter__(self): return self
            def __exit__(self,*_args): pass
            def commit(self): calls.append('connection_commit')
            def rollback(self): calls.append('connection_rollback')
            def exec_driver_sql(self,sql,params=None):
                calls.append(sql)
                if sql.startswith('SELECT DATABASE(),'): return Rows([('lankapex_db','lankapex_app@localhost',3306,'NONE',0)])
                if sql.startswith('SHOW GRANTS'): return Rows([(r'GRANT SELECT ON `lankapex\_db`.* TO x',)])
                if 'SELECT VERSION()' in sql: return Rows([('8.0.46',)])
                if 'version_num' in sql: return Rows([(a.HEAD,)])
                if 'SELECT TABLE_NAME, ENGINE' in sql: return Rows([('users','InnoDB')])
                if 'SELECT * FROM' in sql: return Rows([(1,)])
                if 'SELECT entry_type,' in sql: return Rows([('credit_sale',1)])
                return Rows([(0,)])
        inspector=NS(get_table_names=lambda:['users'],get_columns=lambda t:[dict(name='id',type='BIGINT',nullable=False)],
                     get_pk_constraint=lambda t:{'constrained_columns':['id']},get_foreign_keys=lambda t:[],
                     get_indexes=lambda t:[],get_unique_constraints=lambda t:[],get_check_constraints=lambda t:[])
        cfg=NS(set_main_option=lambda *_args:None)
        graph=NS(iterate_revisions=lambda head,start:[])
        entry=NS(entry_id=1,credit_account_id=1,entry_type='credit_sale',amount=Decimal('100.20'),
                 reverses_entry_id=None,order_id=None,idempotency_key=None,receipt_number=None)
        class Session:
            def __init__(self,**kwargs): self.kwargs=kwargs
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def scalars(self,query): return [entry]
        result=a.collect(NS(connect=lambda:Connection(),dialect=Connection.dialect),NS(metadata=NS(tables={})),
                         NS(entry_id='entry_id'),lambda entries:{1:Decimal('100.20')},Session,
                         lambda c:inspector,lambda model:NS(order_by=lambda key:None),lambda:cfg,
                         NS(from_config=lambda c:graph),'lankapex_app@localhost',{'SELECT'})
        self.assertIn('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY',calls)
        self.assertEqual(calls.count('connection_commit'),1)
        self.assertEqual(calls[-1],'connection_rollback')
        self.assertEqual(result['balance_fingerprint'],hashlib.sha256(json.dumps([[1,'100.20']],separators=(',',':')).encode()).hexdigest())
        self.assertFalse(result['current_schema_compatible'])
        for sql in calls:
            if sql not in ('connection_commit','connection_rollback'):
                self.assertTrue(a.sql_allowed(sql),sql)

if __name__ == '__main__':
    unittest.main()

"""Offline inventory safety tests. No application Settings, engine or secrets imported."""
import contextlib
import importlib.util
import io
from pathlib import Path
from unittest.mock import Mock, patch
import unittest
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('inventory',ROOT/'backend/scripts/inventory_demo_database.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def environment():
    return dict(APP_ENV='development',MYSQL_HOST='localhost',MYSQL_PORT='3306',MYSQL_DATABASE=m.TARGET,MYSQL_USER='lankapex_demo_app',MYSQL_PASSWORD='synthetic-not-a-real-credential')


def metadata():
    data={k:[] for k in m.META}
    for table in sorted(m.TABLES|{'alembic_version'}):
        data['tables'].append((table,'InnoDB','BASE TABLE'))
        columns=m.PROJECTIONS.get(table,'id').split()
        if table=='business_join_links': columns=['business_id','public_code','created_at']
        if table=='customer_join_requests': columns=['request_id','business_id','customer_user_id','status','created_at','decided_at','decided_by']
        if table=='alembic_version': columns=['version_num']
        for n,c in enumerate(columns,1): data['columns'].append((table,c,'varchar(32)' if c=='public_code' else 'varchar(20)' if c=='status' else 'datetime' if c.endswith('_at') else 'bigint','YES' if c in ('decided_by','decided_at') else 'NO','utf8mb4_bin' if c=='public_code' else None,n))
        data['keys'].append((table,'PRIMARY',columns[0],1,None,None,None))
    for table,name,columns in [('customer_profiles','uq_customer_profile_business_user',['business_id','user_id']),('business_join_links','uq_business_join_public_code',['public_code']),('customer_join_requests','uq_customer_join_business_user',['business_id','customer_user_id'])]:
        data['constraints'].append((table,name,'UNIQUE'))
        for n,c in enumerate(columns,1): data['keys'].append((table,name,c,n,None,None,None))
    for table,c,parent,target,name in [('business_join_links','business_id','businesses','business_id','fk_business_join_business'),('customer_join_requests','business_id','businesses','business_id','fk_customer_join_business'),('customer_join_requests','customer_user_id','users','user_id','fk_customer_join_user'),('customer_join_requests','decided_by','users','user_id','fk_customer_join_decider')]:
        # Include only the metadata needed for the QR and FK inventory.
        if target not in [r[1] for r in data['columns'] if r[0]==parent]: data['columns'].append((parent,target,'bigint','NO',None,2))
        data['keys'].append((table,name,c,1,m.TARGET,parent,target))
        data['constraints'].append((table,name,'FOREIGN KEY')); data['rules'].append((table,name,'RESTRICT'))
    data['indexes']=[('customer_join_requests','ix_customer_join_business_status_created',c,n,1) for n,c in enumerate(['business_id','status','created_at'],1)]
    data['constraints'].append(('customer_join_requests','ck_customer_join_status','CHECK'))
    data['checks']=[('ck_customer_join_status',"status IN ('pending','approved','rejected','cancelled')")]
    return data


class Result(list):
    def scalar_one(self): return self[0][0]


class Connection:
    def __init__(self,data=None,revision=None):
        self.data=metadata() if data is None else data; self.revision=revision or m.HEAD; self.executed=[]
    def exec_driver_sql(self,sql):
        self.executed.append(sql)
        for name,query in m.META.items():
            if sql==query: return Result(self.data[name])
        values={'SELECT DATABASE()':m.TARGET,'SELECT CURRENT_USER()':m.ACCOUNT,'SELECT CURRENT_ROLE()':'NONE','SELECT @@GLOBAL.partial_revokes':0,'SELECT @@port':3306,'SELECT version_num FROM alembic_version':self.revision,'SELECT UTC_TIMESTAMP(6)':'2026-11-15 00:00:00',m.DUPLICATES:0}
        if sql in values:return Result([(values[sql],)])
        if sql=='SHOW GRANTS FOR CURRENT_USER()':return Result([(g,) for g in GRANTS])
        if sql==m.LEDGER_TOTALS:return Result([('credit_sale',1,Decimal('100.20')),('repayment',1,Decimal('30.10'))])
        if sql==m.BALANCES:return Result([(1,Decimal('70.10'))])
        if sql.startswith('SELECT COUNT(*)'):return Result([(0,)])
        if sql in m.SETUP:return Result()
        if sql.startswith('SELECT '):return Result()
        raise AssertionError('Unsafe SQL')


GRANTS=["GRANT USAGE ON *.* TO `lankapex_demo_app`@`localhost`", "GRANT SELECT, INSERT, UPDATE, DELETE ON `lankapex\\_demo\\_db`.* TO `lankapex_demo_app`@`localhost`"]


class InventoryTests(unittest.TestCase):
    def test_default_no_connection(self):
        with patch.object(m,'run') as run,contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(m.main([]),0); run.assert_not_called()
        self.assertIn('no credentials loaded',out.getvalue())

    def test_confirmation_no_connection(self):
        with patch.object(m,'run') as run,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(['--execute','--confirm-target','lankapex_db']),1); run.assert_not_called()

    def test_targets(self):
        m.target(environment())
        for k,v in [('MYSQL_DATABASE','lankapex_test_db'),('MYSQL_HOST','127.0.0.1'),('MYSQL_PORT','3307'),('MYSQL_USER','root'),('APP_ENV','testing'),('MYSQL_PASSWORD','')]:
            env=environment();env[k]=v
            with self.subTest(k=k),self.assertRaises(m.Stop):m.target(env)

    def test_grants(self):
        self.assertEqual(m.grants(GRANTS,0,'NONE'),['DELETE','INSERT','SELECT','UPDATE'])
        for rows,role in [(GRANTS,'role'),(GRANTS+["GRANT SELECT ON *.* TO `x`@`localhost`"],'NONE'),([GRANTS[0],GRANTS[1].replace('\\_','_')],'NONE'),([GRANTS[0],GRANTS[1]+' WITH GRANT OPTION'],'NONE')]:
            with self.subTest(rows=rows),self.assertRaises(m.Stop):m.grants(rows,0,role)

    def test_complete_inventory(self):
        conn=Connection(); report=m.collect(m.Reader(conn))
        self.assertEqual(report['total_tables'],29);self.assertEqual(report['application_tables'],28)
        self.assertTrue(report['qr_structure_complete']); self.assertTrue(report['current_schema_compatible'])
        self.assertEqual(set(report['row_counts']),m.TABLES)
        self.assertEqual(set(report['preservation_fingerprints']),set(m.PROJECTIONS))
        self.assertFalse(report['database_changed']);self.assertFalse(report['evidence_file_created'])
        self.assertEqual(report['duplicate_profile_pair_count'],0)
        self.assertEqual(report['signed_account_balance_fingerprint']['rows'],1)
        self.assertIn('foreign_key_orphan_counts',report)
        self.assertTrue(all(s.startswith(('SELECT ','SHOW ')) for s in conn.executed))
        for word in ('password','public_code`','email','notes','token'):
            self.assertFalse(any(word in q.lower() for q in conn.executed if 'information_schema' not in q))

    def test_old_and_partial_schema_reported(self):
        d=metadata();d['tables']=[r for r in d['tables'] if r[0]!='business_join_links']
        report=m.collect(m.Reader(Connection(d,'6e3f2c1a9b04')))
        self.assertFalse(report['qr_structure_complete']);self.assertFalse(report['current_schema_compatible'])
        self.assertEqual(report['missing_current_tables'],['business_join_links'])

    def test_unknown_tables_stop_before_application_reads(self):
        d=metadata();d['tables'].append(('unreviewed','InnoDB','BASE TABLE')); conn=Connection(d)
        with self.assertRaises(m.Stop):m.collect(m.Reader(conn))
        self.assertFalse(any('COUNT(*)' in q for q in conn.executed))

    def test_actual_identity_stops(self):
        c=Connection();original=c.exec_driver_sql
        c.exec_driver_sql=lambda s:Result([('lankapex_db',)]) if s=='SELECT DATABASE()' else original(s)
        with self.assertRaises(m.Stop):m.collect(m.Reader(c))
        self.assertEqual(c.executed,[])

    def test_sql_write_and_cross_schema_refused(self):
        c=Connection();r=m.Reader(c)
        for q in ['DELETE FROM users','SELECT * FROM users FOR UPDATE','CREATE TEMPORARY TABLE x (id INT)','SET SESSION TRANSACTION READ WRITE', 'SELECT COUNT(*) FROM `lankapex_db`.`users`', 'SELECT COUNT(*) FROM `users`; DELETE FROM users', "SELECT * INTO OUTFILE 'x' FROM users"]:
            with self.subTest(q=q),self.assertRaises(m.Stop):r.generated(q)
            with self.subTest(exact=q),self.assertRaises(m.Stop):r.execute(q)
        self.assertEqual(c.executed,[])

    def test_fingerprints_deterministic_sensitive_not_output(self):
        a=m.fingerprint([(1,Decimal('100.20'))]); b=m.fingerprint([(1,Decimal('100.20'))]);c=m.fingerprint([(1,Decimal('100.21'))])
        self.assertEqual(a,b);self.assertNotEqual(a,c);self.assertNotIn('100.20',str(a))

    def test_sanitized_failure(self):
        for error in (ValueError('secret-password'),m.Stop('secret-password'),m.Stop('grants')):
            with patch.object(m,'run',side_effect=error),contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(m.main(['--execute','--confirm-target',m.TARGET]),1)
            self.assertNotIn('secret-password',out.getvalue())

    def test_metadata_changes_fail_closed(self):
        c=Connection(); original=c.exec_driver_sql; calls=0
        def changed(sql):
            nonlocal calls
            if sql==m.META['tables']:
                calls+=1
                if calls>1:return Result([])
            return original(sql)
        c.exec_driver_sql=changed
        with self.assertRaisesRegex(m.Stop,'metadata_changed'):m.collect(m.Reader(c))

    def test_cross_schema_fk_stops(self):
        d=metadata(); row=list(d['keys'][-1]);row[4]='lankapex_db';d['keys'][-1]=tuple(row)
        c=Connection(d)
        with self.assertRaisesRegex(m.Stop,'foreign_key_scope'):m.collect(m.Reader(c))
        self.assertFalse(any('lankapex_db' in q for q in c.executed))

    def test_missing_metadata_permission_is_not_absence(self):
        c=Connection();original=c.exec_driver_sql
        def denied(sql):
            if sql==m.META['columns']:raise PermissionError('synthetic-secret-error')
            return original(sql)
        c.exec_driver_sql=denied
        with patch.object(m,'run',side_effect=lambda env:m.collect(m.Reader(c))),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(m.main(['--execute','--confirm-target',m.TARGET]),1)
        self.assertIn('read_or_metadata_unavailable',out.getvalue());self.assertNotIn('synthetic-secret-error',out.getvalue())

    def test_wrong_constraint_and_column_type_reported(self):
        d=metadata(); d['constraints'].append(('customer_join_requests','unexpected_constraint','CHECK'))
        report=m.collect(m.Reader(Connection(d)))
        self.assertFalse(report['qr_structure_complete'])
        self.assertEqual(report['qr_metadata']['customer_join_requests']['unexpected_constraint_count'],1)
        d=metadata()
        for n,r in enumerate(d['columns']):
            if r[0]=='business_join_links' and r[1]=='public_code':
                row=list(r);row[2]='varchar(64)';d['columns'][n]=tuple(row)
        report=m.collect(m.Reader(Connection(d)))
        self.assertFalse(report['qr_structure_complete'])
        self.assertFalse(report['qr_metadata']['business_join_links']['public_code_type_collation_valid'])

    def test_balance_query_reversal_zero_and_advance(self):
        # SQLite in-memory only: executes the same SELECT over synthetic integer
        # minor units, checking SQL reversal semantics without any MySQL access.
        import sqlite3
        with contextlib.closing(sqlite3.connect(':memory:')) as c:
            c.execute('CREATE TABLE credit_accounts (credit_account_id INTEGER)')
            c.execute('CREATE TABLE ledger_entries (entry_id INTEGER,credit_account_id INTEGER,entry_type TEXT,amount INTEGER,reverses_entry_id INTEGER)')
            c.executemany('INSERT INTO credit_accounts VALUES (?)',[(n,) for n in range(1,6)])
            c.executemany('INSERT INTO ledger_entries VALUES (?,?,?,?,?)',[
                (1,1,'credit_sale',10020,None),(2,1,'repayment',3010,None),
                (3,2,'credit_sale',10000,None),(4,2,'reversal',10000,3),
                (5,3,'credit_sale',10000,None),(6,3,'repayment',3000,None),(7,3,'reversal',3000,6),
                (8,4,'credit_sale',10000,None),(9,4,'repayment',12000,None)])
            self.assertEqual(c.execute(m.BALANCES).fetchall(),[(1,7010),(2,0),(3,10000),(4,-2000),(5,0)])

    def test_wrapper_source_guards(self):
        s=(ROOT/'backend/scripts/inventory_demo_database.ps1').read_text(encoding='utf-8-sig')
        self.assertLess(s.index('if (-not $Execute)'),s.index('ConvertTo-SecureString'))
        for text in ('AreAccessRulesProtected','ZeroFreeBSTR','finally','SetEnvironmentVariable($name,$previous[$name]', '$ConfirmTarget -cne',"exit $exitCode"):
            self.assertIn(text,s)
        for text in ('Set-Acl','Set-Content','Start-Process','Invoke-WebRequest'):
            self.assertNotIn(text,s)

    def test_source_chain_and_no_application_imports(self):
        self.assertEqual(len(m.revision_chain()),16)
        source=(ROOT/'backend/scripts/inventory_demo_database.py').read_text()
        self.assertNotIn('from app.',source);self.assertNotIn('conn.commit(',source)
        self.assertIn('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY',source)

    def test_rollback_even_if_collection_fails(self):
        conn=Mock();conn.__enter__=Mock(return_value=conn);conn.__exit__=Mock(return_value=False)
        engine=Mock();engine.connect.return_value=conn
        with patch('sqlalchemy.create_engine',return_value=engine),patch.object(m,'collect',side_effect=m.Stop('grants')):
            with self.assertRaises(m.Stop):m.run(environment())
        self.assertEqual(conn.rollback.call_count,2);conn.commit.assert_not_called();engine.dispose.assert_called_once()


if __name__=='__main__':unittest.main()

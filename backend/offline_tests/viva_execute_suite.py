"""Executable workflow tests: fictional data, memory evidence, mocked OS/DB only."""
import copy
import importlib.util
import io
from pathlib import Path
import sys
import socket
import unittest
from unittest.mock import Mock,MagicMock,patch
from contextlib import contextmanager,ExitStack,nullcontext
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('viva_executable_tests',ROOT/'backend/scripts/viva_migration_execute.py')
v=importlib.util.module_from_spec(spec);sys.modules[spec.name]=v;spec.loader.exec_module(v)

def fixture():
    tables={};data={};sql=['-- Fictional current backup']
    for name in sorted(v.g.recovery_contract().tables_at(v.CHAIN[0])):
        column='version_num' if name=='alembic_version' else 'id'
        family='VARCHAR' if column=='version_num' else 'BIGINT'
        metadata={'columns':{column:{'type':{'family':family}}}}
        ddl='CREATE TABLE `'+name+'` (`'+column+'` '+('varchar(32)' if family=='VARCHAR' else 'bigint')+' NOT NULL)'
        tables[name]=dict(metadata=metadata,ddl=ddl)
        values=[{column:v.CHAIN[0] if family=='VARCHAR' else 1}]
        if name!='alembic_version':data[name]=dict(columns=[column],**v.d.a.fingerprint(values,[column]))
        sql.extend([ddl+';',"INSERT INTO `"+name+"` VALUES ("+("'"+v.CHAIN[0]+"'" if family=='VARCHAR' else '1')+");"])
    sql.append('-- Dump completed on 2026-11-24 00:00:00')
    return dict(revision=v.CHAIN[0],data=data,schema=dict(tables=tables,triggers=[],foreign_keys_checked=0)),'\n'.join(sql).encode()

class MemoryEvidence:
    def __init__(self,path):self.path=path;self.sid='OPERATOR';self.api=Mock();self.artifacts={}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def write(self,name,value):
        if name in self.artifacts:raise RuntimeError('EXCLUSIVE_EVIDENCE_COLLISION')
        self.artifacts[name]=copy.deepcopy(value)
    def open_new(self,name):
        handle=Mock();handle.value=123;handle.__enter__=Mock(return_value=handle);handle.__exit__=Mock(return_value=False)
        return handle

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.baseline,self.dump=fixture();self.evidence=MemoryEvidence(v.PARENT/'viva-current-fictional-0001')
        self.source=SimpleNamespace(current=v.CHAIN[0],cid=1,thread_id=lambda:1);self.scratch=SimpleNamespace(current=v.CHAIN[0],cid=2,thread_id=lambda:2)
        self.net=patch.object(socket.socket,'connect',side_effect=AssertionError('NO_DATABASE_CONNECTION'));self.net.start();self.addCleanup(self.net.stop)
    def args(self,mode):
        target=v.SCRATCH if mode in ('restore','rehearse') else v.SOURCE
        args=[mode,'--execute','--authorize',v.TOKENS[mode],'--confirm-target',target,'--freeze','FREEZE_MAINTAINED','--evidence',str(self.evidence.path),'--mysql-sha256','A'*64,'--mysqldump-sha256','A'*64,'--ca-sha256','A'*64]
        if mode!='backup':args+=['--manifest',str(v.PARENT/'viva-current-backup-0000'/'manifest.json'),'--manifest-sha256','B'*64]
        if mode=='migrate':args+=['--rehearsal',str(v.PARENT/'viva-current-rehearsal-0000'/'result.json'),'--rehearsal-sha256',v.sha(self.rehearsal())]
        return args
    def rehearsal(self):return v.encoded(dict(status='REHEARSAL_PASS',manifest_sha256='B'*64,provenance=v.provenance()))
    def run_mode(self,mode,*,stage_failure=None,process_failure=None,changed=False):
        self.scratch.current=None if mode=='restore' else v.CHAIN[-1] if mode=='migrate' else v.CHAIN[0]
        calls=[];provenance=v.provenance();args=self.args(mode);rehearsal=self.rehearsal()
        @contextmanager
        def connect(database,account,secret):yield self.source if database==v.SOURCE else self.scratch
        def snapshot(raw,database,account,revision,projections=None):
            if raw.current!=revision:raise RuntimeError('TEST_REVISION_MISMATCH')
            result=copy.deepcopy(self.baseline);result['revision']=revision
            if changed and revision!=v.CHAIN[0]:result['data']['orders']['content_sha256']='F'*64
            return result
        def process(argv,*,stdin=None,stdout=None):
            calls.append(('process',tuple(argv)))
            if process_failure:raise process_failure
            if mode=='backup':stdout.write(self.dump)
            else:self.scratch.current=v.CHAIN[0]
        def upgrade(raw,database,account,parent,child):
            calls.append(('upgrade',database,parent,child))
            if stage_failure:raise stage_failure
            raw.current=child
        bundle=dict(dump_sha256=v.sha(self.dump),baseline_sha256=v.sha(v.encoded(self.baseline)),ca_sha256='A'*64,mysql_sha256='A'*64,mysqldump_sha256='A'*64,provenance=provenance)
        with ExitStack() as stack:
            for name,value in dict(PrivateEvidence=Mock(return_value=self.evidence),file_sha=Mock(side_effect=lambda path:v.sha(self.dump) if Path(path).suffix=='.sql' else 'A'*64),provenance=Mock(return_value=provenance),password=Mock(return_value='FICTIONAL_SECRET'),connect=connect,dba_gate=Mock(return_value={'observed_at':1}),revision=lambda raw:raw.current,scalar=Mock(side_effect=lambda raw,sql:raw.cid if 'CONNECTION_ID()' in sql else 0 if mode=='backup' and 'log_bin_trust_function_creators' in sql else 1),snapshot=snapshot,checked_process=process,upgrade_one=upgrade,read_bundle=Mock(return_value=(bundle,self.baseline)),private_read=Mock(return_value=rehearsal),private_input=Mock(return_value=nullcontext((io.BytesIO(self.dump),self.dump))),owned_fd=Mock(return_value=42)).items():stack.enter_context(patch.object(v,name,value))
            inspector=Mock();inspector.read.return_value=[];stack.enter_context(patch.object(v,'Inspector',return_value=inspector))
            stack.enter_context(patch.object(v,'capacity'))
            stack.enter_context(patch.object(v.sys,'stdin',Mock(isatty=Mock(return_value=True))))
            stack.enter_context(patch('builtins.input',return_value='fictional_dba'))
            stack.enter_context(patch.object(v.os,'fdopen',return_value=io.BytesIO()))
            v.main(args)
        return calls
    def test_backup_executes_once_and_binds_verified_bytes(self):
        calls=self.run_mode('backup');self.assertEqual(len(calls),1)
        self.assertEqual(self.evidence.artifacts['manifest.json']['dump_sha256'],v.sha(self.dump))
        self.assertEqual(self.evidence.artifacts['manifest.json']['status'],'BACKUP_ONLY_RESTORE_NOT_VERIFIED')
    def test_restore_targets_scratch_and_verifies_baseline(self):
        calls=self.run_mode('restore');self.assertEqual(len(calls),1)
        self.assertIn('--database='+v.SCRATCH,calls[0][1]);self.assertIn('restore-verified.json',self.evidence.artifacts)
    def test_rehearsal_pins_all_three_stages(self):
        calls=self.run_mode('rehearse')
        self.assertEqual([(c[2],c[3]) for c in calls],list(zip(v.CHAIN,v.CHAIN[1:])))
        self.assertTrue(all(c[1]==v.SCRATCH for c in calls));self.assertEqual(self.source.current,v.CHAIN[0])
        self.assertEqual(self.evidence.artifacts['result.json']['status'],'REHEARSAL_PASS')
    def test_live_pins_source_only_after_rehearsal(self):
        calls=self.run_mode('migrate');self.assertTrue(all(c[1]==v.SOURCE for c in calls))
        self.assertEqual(self.evidence.artifacts['result.json']['status'],'LIVE_MIGRATION_PASS')
    def test_partial_ddl_stops_without_next_stage_or_success(self):
        original=RuntimeError('FICTIONAL_PRIVATE_SQL')
        with self.assertRaises(RuntimeError) as caught:self.run_mode('rehearse',stage_failure=original)
        self.assertIs(caught.exception,original);self.assertNotIn('stage-1-attempt.json',self.evidence.artifacts)
        self.assertNotIn('result.json',self.evidence.artifacts)
        self.assertNotIn('FICTIONAL_PRIVATE_SQL',str(self.evidence.artifacts['failure.json']))
    def test_financial_change_stops_after_first_stage(self):
        with self.assertRaises(RuntimeError):self.run_mode('rehearse',changed=True)
        self.assertNotIn('stage-1-attempt.json',self.evidence.artifacts)
    def test_partial_import_never_retries(self):
        original=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt) as caught:self.run_mode('restore',process_failure=original)
        self.assertIs(caught.exception,original);self.assertIn('failure.json',self.evidence.artifacts)
        self.assertNotIn('complete.json',self.evidence.artifacts)
    def test_missing_execute_wrong_target_and_wrong_token_before_io(self):
        args=SimpleNamespace(mode='migrate',execute=False,authorize=v.TOKENS['migrate'],confirm_target=v.SOURCE,freeze='FREEZE_MAINTAINED',evidence=self.evidence.path)
        with self.assertRaises(RuntimeError):v.authorization(args)
        args.execute=True;args.confirm_target=v.SCRATCH
        with self.assertRaises(RuntimeError):v.authorization(args)
        args.confirm_target=v.SOURCE;args.authorize='ONE_CURRENT_SCRATCH_REHEARSAL'
        with self.assertRaises(RuntimeError):v.authorization(args)
    def test_dump_data_missing_table_and_program_tampering(self):
        v.validate_backup_sql(self.dump,self.baseline)
        for raw in (self.dump.replace(b'VALUES (1)',b'VALUES (2)',1),self.dump.replace(b'CREATE TABLE `orders`',b'CREATE TABLE `unknown`'),self.dump.replace(b'-- Dump completed',b'USE `lankapex_viva_db`;\n-- Dump completed'),self.dump.replace(b'-- Dump completed',b'SET GLOBAL log_bin_trust_function_creators=1;\n-- Dump completed'),self.dump[:-20]):
            with self.assertRaises(Exception):v.validate_backup_sql(raw,self.baseline)
    def test_native_restore_cannot_target_source_or_other_binary(self):
        with self.assertRaises(RuntimeError):v.client_argv(v.MYSQL,v.g.MIGRATOR.split('@')[0],v.SOURCE)
        with self.assertRaises(RuntimeError):v.client_argv(Path('evil.exe'),v.SCRATCH_USER,v.SCRATCH)
    def test_process_interruption_preserves_original_and_reaps(self):
        child=Mock();original=KeyboardInterrupt();child.wait.side_effect=[original,0];child.poll.return_value=None
        with patch.object(v.sys,'stdin',Mock(isatty=Mock(return_value=True))),patch.object(v.subprocess,'Popen',return_value=child) as launch:
            with self.assertRaises(KeyboardInterrupt) as caught:v.checked_process(['fictional.exe'])
        self.assertIs(caught.exception,original);child.kill.assert_called_once();self.assertFalse(launch.call_args.kwargs['shell'])
    def test_native_child_does_not_inherit_provider_or_database_secrets(self):
        child=Mock();child.wait.return_value=0;child.poll.return_value=0
        with patch.dict(v.os.environ,{'MYSQL_PWD':'FICTIONAL_SECRET','MYSQL_PASSWORD':'FICTIONAL_SECRET','GROQ_API_KEY':'FICTIONAL_SECRET'}),patch.object(v.sys,'stdin',Mock(isatty=Mock(return_value=True))),patch.object(v.subprocess,'Popen',return_value=child) as launch:
            v.checked_process(['fictional.exe'])
        environment=launch.call_args.kwargs['env']
        self.assertFalse({'MYSQL_PWD','MYSQL_PASSWORD','GROQ_API_KEY'}&set(environment))
    def test_scoped_grants_reject_global_and_unescaped_patterns(self):
        account=v.SCRATCH_USER;scope=v.SCRATCH.replace('_',r'\_');rights=', '.join(sorted(v.g.RIGHTS))
        good='GRANT '+rights+' ON `'+scope+'`.* TO `'+account+'`@`127.0.0.1`'
        with patch.object(v,'scalar',return_value=0),patch.object(v,'query',return_value=[{'Grants':good}]):v.grants(Mock(),v.SCRATCH,account,v.g.RIGHTS)
        for bad in (good.replace(scope,v.SOURCE),good.replace(scope,v.SCRATCH),'GRANT ALL PRIVILEGES ON *.* TO `'+account+'`@`127.0.0.1`',good+' WITH GRANT OPTION'):
            with patch.object(v,'scalar',return_value=0),patch.object(v,'query',return_value=[{'Grants':bad}]),self.assertRaises(RuntimeError):v.grants(Mock(),v.SCRATCH,account,v.g.RIGHTS)
    def test_schema_decoder_rejects_missing_column(self):
        # Reuse fictional MySQL metadata, but invoke the real canonical decoder.
        spec=importlib.util.spec_from_file_location('exec_schema_fixture',ROOT/'backend/offline_tests/mr09_mysql_adapter_suite.py')
        f=importlib.util.module_from_spec(spec);sys.modules[spec.name]=f;spec.loader.exec_module(f)
        contract=f.fixture_contract();observed=f.observed_results(v.CHAIN[0],v.SOURCE)
        def query(raw,sql,params=()):
            key=next(key for key,value in v.d.SQL.items() if value==sql) if not sql.startswith('SHOW CREATE TABLE') else 'ddl'
            name=params[1] if len(params)==2 else sql.split('`')[1] if key=='ddl' else None
            return observed[key][name] if name else observed[key]
        with patch.object(v.d.c,'build',return_value=contract),patch.object(v,'query',side_effect=query),patch.object(v,'scalar',side_effect=lambda raw,sql:0 if 'COUNT(*)' in sql else 'STRICT_TRANS_TABLES'):
            actual=v.schema(Mock(),v.SOURCE,v.CHAIN[0],v.g.MIGRATOR.split('@')[0]);self.assertEqual(len(actual['tables']),35)
            observed['columns']['orders'].pop()
            with self.assertRaises(Exception):v.schema(Mock(),v.SOURCE,v.CHAIN[0],v.g.MIGRATOR.split('@')[0])
    def test_actual_upgrade_path_uses_only_supplied_connection_and_pinned_env(self):
        import runpy
        from sqlalchemy.engine import URL
        from alembic import context
        raw=Mock();engine=MagicMock();conn=MagicMock()
        engine.url=URL.create('mysql+pymysql',host='127.0.0.1',port=3306,username=v.SCRATCH_USER,database=v.SCRATCH)
        conn.engine=engine;conn.connection.driver_connection=raw;conn.in_transaction.return_value=False
        conn.exec_driver_sql.return_value.scalars.return_value=[v.CHAIN[0]]
        engine.connect.return_value.__enter__.return_value=conn
        def apply(cfg,stage):
            self.assertEqual(stage,v.CHAIN[1]);self.assertIs(cfg.attributes['connection'],conn)
            self.assertEqual(cfg.attributes['viva_target'],v.SCRATCH)
            with patch.object(context,'config',cfg,create=True),patch.object(context,'is_offline_mode',return_value=False),patch.object(context,'configure') as configure,patch.object(context,'begin_transaction',return_value=nullcontext()),patch.object(context,'run_migrations') as run:
                runpy.run_path(str(ROOT/'backend/viva_pending_alembic/env.py'))
                configure.assert_called_once_with(connection=conn,compare_type=True);run.assert_called_once()
        with patch('sqlalchemy.create_engine',return_value=engine) as factory,patch('sqlalchemy.event.listen') as listen,patch('sqlalchemy.event.remove'),patch('alembic.command.upgrade',side_effect=apply),patch.object(v,'identity'),patch.object(v,'revision',return_value=v.CHAIN[0]),patch.object(v,'scalar',return_value=1):
            v.upgrade_one(raw,v.SCRATCH,v.SCRATCH_USER,v.CHAIN[0],v.CHAIN[1])
            creator=factory.call_args.kwargs['creator'];borrowed=creator();borrowed.close();raw.close.assert_not_called()
            from pymysql.cursors import Cursor, DictCursor
            from sqlalchemy.dialects.mysql.base import MySQLDialect
            positional=MagicMock();positional.fetchone.return_value=('8.0.46',)
            dictionary=MagicMock();dictionary.fetchone.return_value={'VERSION()':'8.0.46'}
            dictionary.__enter__.return_value=dictionary
            dictionary.fetchall.return_value=[{'version':'8.0.46'}]
            raw.cursor.side_effect=lambda cursor=None: positional if cursor is Cursor else dictionary
            self.assertIs(borrowed.cursor(),positional)
            self.assertIs(borrowed.cursor(DictCursor),dictionary)
            version_conn=Mock();version_conn.connection=borrowed
            self.assertEqual(MySQLDialect()._get_server_version_info(version_conn),(8,0,46))
            positional.execute.assert_called_once_with('SELECT VERSION()')
            positional.close.assert_called_once()
            self.assertEqual(v.query(borrowed,'SELECT VERSION() AS version'),[{'version':'8.0.46'}])
            raw.cursor.assert_called_with(DictCursor)
            raw.close.assert_not_called()
            with self.assertRaisesRegex(RuntimeError,'RECONNECT_REFUSED'):creator()
            sql_gate=listen.call_args.args[2]
            for statement in ('UPDATE orders SET total=0','DELETE FROM ledger_entries','USE lankapex_viva_db','CREATE DATABASE anything','/* hidden */ UPDATE orders SET total=0','SET GLOBAL log_bin_trust_function_creators=1','SET SESSION sql_log_bin=0'):
                with self.assertRaises(RuntimeError):sql_gate(conn,None,statement,(),None,False)
    def test_binary_trust_zero_stops_actual_upgrade_before_engine(self):
        with patch.object(v,'identity'),patch.object(v,'revision',return_value=v.CHAIN[0]),patch.object(v,'scalar',side_effect=[1,0]),patch('sqlalchemy.create_engine') as factory:
            with self.assertRaisesRegex(RuntimeError,'DBA_BINARY_LOGGING_RESOLUTION_REQUIRED'):
                v.upgrade_one(Mock(),v.SCRATCH,v.SCRATCH_USER,v.CHAIN[0],v.CHAIN[1])
            factory.assert_not_called()
    def test_snapshot_complete_original_projections_and_rollback(self):
        raw=Mock()
        def scalar(raw,sql,parameters=()):return 1
        def rows(raw,sql,parameters=()):
            if sql.startswith('SELECT `'):return [{'id':1}]
            return []
        with patch.object(v,'identity'),patch.object(v,'revision',return_value=v.CHAIN[0]),patch.object(v,'schema',return_value=self.baseline['schema']),patch.object(v,'scalar',side_effect=scalar),patch.object(v,'query',side_effect=rows):
            captured=v.snapshot(raw,v.SOURCE,v.g.MIGRATOR.split('@')[0],v.CHAIN[0])
            self.assertEqual(captured['data'],self.baseline['data']);raw.rollback.assert_called_once()
    def test_incomplete_snapshot_does_not_emit_success(self):
        raw=Mock()
        with patch.object(v,'identity'),patch.object(v,'revision',return_value=v.CHAIN[0]),patch.object(v,'schema',return_value=self.baseline['schema']),patch.object(v,'scalar',return_value=1),patch.object(v,'query',return_value=[]):
            with self.assertRaisesRegex(RuntimeError,'CAPTURE_INCOMPLETE'):v.snapshot(raw,v.SOURCE,v.g.MIGRATOR.split('@')[0],v.CHAIN[0])
        raw.rollback.assert_called_once()
    def test_database_identity_and_leaf_pin_fail_closed(self):
        raw=Mock();row=dict(uuid=v.g.UUID,db=v.SOURCE,account=v.g.MIGRATOR,version='8.0.46',port=3306,roles='NONE',mandatory='',fk=1,uq=1,mode='STRICT_TRANS_TABLES')
        with patch.object(v.tls,'verify_socket',side_effect=ValueError('PIN_MISMATCH')),patch.object(v,'query') as query:
            with self.assertRaises(ValueError):v.identity(raw,v.SOURCE,v.g.MIGRATOR.split('@')[0])
            query.assert_not_called()
        for field,bad in (('uuid','other'),('db',v.SCRATCH),('account',v.g.SCRATCH_ACCOUNT),('roles','admin'),('fk',0),('version','8.0.45')):
            with patch.object(v.tls,'verify_socket'),patch.object(v,'query',return_value=[dict(row,**{field:bad})]),self.assertRaises(RuntimeError):v.identity(raw,v.SOURCE,v.g.MIGRATOR.split('@')[0])
    def test_dba_visibility_must_include_exact_expected_sessions(self):
        raw=Mock();raw.thread_id.return_value=100
        def scalar(raw,sql,parameters=()):return v.g.UUID if 'server_uuid' in sql else 'fictional@localhost' if 'CURRENT_USER' in sql else 100
        def query(raw,sql,parameters=()):
            if sql.startswith('SHOW GRANTS'):return [{'grant':"GRANT SELECT, PROCESS, EVENT ON *.* TO 'fictional'@'localhost'"}]
            if 'performance_schema.threads' in sql:return [dict(id=100,user='fictional',thread_name='thread/sql/one_connection',command='Query',connection_type='SSL/TLS',host='localhost',database=None),dict(id=1,user=v.g.MIGRATOR.split('@')[0],thread_name='thread/sql/one_connection',command='Sleep',connection_type='SSL/TLS',host='localhost',database=v.SOURCE),dict(id=999,user='other',thread_name='thread/sql/one_connection',command='Sleep',connection_type='SSL/TLS',host='localhost',database=None)]
            return []
        with patch('pymysql.connect',return_value=raw),patch.object(v.tls,'context'),patch.object(v.tls,'verify_socket'),patch.object(v,'scalar',side_effect=scalar),patch.object(v,'query',side_effect=query):
            with self.assertRaisesRegex(RuntimeError,'DBA_UNEXPECTED_CLIENTS_STOP'):v.dba_gate('fictional','PRIVATE',[1])
        raw.close.assert_called_once()
    def test_scratch_username_is_supported_and_not_a_database_alias(self):
        self.assertLessEqual(len(v.SCRATCH_USER),32)
        self.assertNotEqual(v.SCRATCH_USER,v.SCRATCH)
    def test_insufficient_capacity_stops_before_dump(self):
        with patch.object(v,'scalar',return_value=100),patch.object(v.shutil,'disk_usage',return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(RuntimeError,'CAPACITY_INSUFFICIENT'):v.capacity(Mock())
    def test_dedicated_alembic_graph_has_exact_single_step_transitions(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        cfg=Config();cfg.set_main_option('script_location',str(ROOT/'backend/viva_pending_alembic'));cfg.set_main_option('path_separator','os');cfg.set_main_option('version_locations',str(ROOT/'backend/alembic/versions'))
        graph=ScriptDirectory.from_config(cfg)
        self.assertEqual(graph.get_heads(),[v.CHAIN[-1]])
        for parent,child in zip(v.CHAIN,v.CHAIN[1:]):self.assertEqual(len(graph._upgrade_revs(child,parent)),1)

class WindowsDiagnosticTests(unittest.TestCase):
    SID='S-1-5-21-1-2-3-1001'
    def api(self):
        api=Mock();api.operator_sid.return_value=self.SID
        api.open.side_effect=lambda *args,**kwargs:Mock(closed=False)
        api.security.side_effect=lambda *args:nullcontext(v.w._SA())
        return api
    def args(self):return ['inspect-windows','--read-only','--confirm-parent',str(v.PARENT),'--operator-sid',self.SID]
    def test_read_only_entry_uses_same_parent_checks_without_credentials_or_creation(self):
        api=self.api()
        with patch.object(v.w,'_Win32',return_value=api),patch.object(v,'connect',side_effect=AssertionError('NO_DB')),patch.object(v,'password',side_effect=AssertionError('NO_SECRETS')),patch.object(v,'PrivateEvidence',side_effect=AssertionError('NO_FILES')),patch.object(v.subprocess,'Popen',side_effect=AssertionError('NO_PROCESS')):
            v.main(self.args())
        self.assertEqual(api.open.call_count,len(v.PARENT.parents)+1)
        for call in api.open.call_args_list:self.assertEqual(call.kwargs,dict(directory=True,read_acl=True))
        self.assertEqual(api.facts.call_args_list[-1].kwargs['owner'],self.SID)
        api.k.CreateDirectoryW.assert_not_called();api.write_and_flush.assert_not_called()
        for call in api.facts.call_args_list:call.args[0].close.assert_called_once()
    def test_read_only_operator_mismatch_stops_before_path_access(self):
        api=self.api();api.operator_sid.return_value='S-1-5-21-1-2-3-1004'
        with patch.object(v.w,'_Win32',return_value=api),self.assertRaisesRegex(v.VivaStop,'OPERATOR_IDENTITY_MISMATCH'):v.main(self.args())
        api.open.assert_not_called()
    def test_read_only_wrong_parent_and_mutation_flags_rejected_before_win32(self):
        bad=self.args();bad[bad.index('--confirm-parent')+1]=str(v.PARENT.parent)
        with patch.object(v.w,'_Win32') as native,self.assertRaises(v.VivaStop):v.main(bad)
        native.assert_not_called()
        with patch.object(v.w,'_Win32') as native,self.assertRaises(SystemExit):v.main(self.args()+['--execute'])
        native.assert_not_called()
    def test_each_precreate_ancestor_facts_failure_is_located_and_owned(self):
        count=len(v.PARENT.parents)+1
        for index in range(count):
            api=self.api();failure=v.w.WindowsIOBlocked('HANDLE_REPARSE_OR_DEVICE')
            api.facts.side_effect=[None]*index+[failure]
            with patch.object(v.w,'_Win32',return_value=api),self.assertRaises(v.w.WindowsIOBlocked) as caught:
                with v.PrivateEvidence(v.PARENT/'viva-current-fictional-0123'):pass
            self.assertIs(caught.exception,failure)
            self.assertEqual(v.windows_details(failure)['windows_location'],'ANCESTOR_'+str(index)+'_FACTS')
            for call in api.facts.call_args_list:call.args[0].close.assert_called_once()
            api.k.CreateDirectoryW.assert_not_called()
    def test_read_only_open_denial_preserves_winerror_and_closes_earlier_handles(self):
        api=self.api();handle=Mock();error=v.w.WindowsIOBlocked('EXCLUSIVE_OPEN_FAILED_WIN32_5',operation='CreateFileW',winerror=5)
        api.open.side_effect=[handle,error]
        with patch.object(v.w,'_Win32',return_value=api),self.assertRaises(v.w.WindowsIOBlocked) as caught:v.main(self.args())
        self.assertIs(caught.exception,error);handle.close.assert_called_once()
        self.assertEqual(v.diagnostic(error),'EXCLUSIVE_OPEN_FAILED')
        self.assertEqual(v.windows_details(error),dict(windows_location='ANCESTOR_1_OPEN',windows_operation='CreateFileW',windows_error=5))
        api.k.CreateDirectoryW.assert_not_called()
    def test_in_memory_descriptor_failure_precedes_directory_creation(self):
        api=self.api();error=v.w.WindowsIOBlocked('SECURITY_DESCRIPTOR_FAILED',operation='ConvertStringSecurityDescriptorToSecurityDescriptorW',winerror=1337)
        api.security.side_effect=error
        with patch.object(v.w,'_Win32',return_value=api),patch.object(v.Path,'exists',return_value=False),self.assertRaises(v.w.WindowsIOBlocked) as caught:
            with v.PrivateEvidence(v.PARENT/'viva-current-fictional-0123'):pass
        self.assertIs(caught.exception,error);self.assertEqual(v.windows_details(error)['windows_location'],'PRIVATE_DESCRIPTOR')
        api.k.CreateDirectoryW.assert_not_called()
        for call in api.facts.call_args_list:call.args[0].close.assert_called_once()
    def test_original_acl_error_survives_close_error(self):
        api=self.api();handle=Mock();handle.close.side_effect=v.w.WindowsIOBlocked('CLOSE_HANDLE_FAILED',operation='CloseHandle',winerror=6)
        api.open.return_value=handle;api.open.side_effect=None
        original=v.w.WindowsIOBlocked('HANDLE_OWNER_OR_DACL_INVALID');api.facts.side_effect=original
        with patch.object(v.w,'_Win32',return_value=api),self.assertRaises(v.w.WindowsIOBlocked) as caught:v.main(self.args())
        self.assertIs(caught.exception,original);self.assertEqual(v.diagnostic(original),'HANDLE_OWNER_OR_DACL_INVALID')
        self.assertEqual(v.windows_details(original)['evidence_cleanup'],'INCOMPLETE')
        api.k.CreateDirectoryW.assert_not_called()
    def test_read_only_cleanup_only_failure_is_not_reported_as_success(self):
        api=self.api();handle=Mock();error=v.w.WindowsIOBlocked('CLOSE_HANDLE_FAILED',operation='CloseHandle',winerror=6)
        handle.close.side_effect=error;api.open.side_effect=None;api.open.return_value=handle
        with patch.object(v.w,'_Win32',return_value=api),self.assertRaises(v.w.WindowsIOBlocked) as caught:v.main(self.args())
        self.assertIs(caught.exception,error);self.assertEqual(v.windows_details(error)['evidence_cleanup'],'INCOMPLETE')
    def test_win32_last_error_is_captured_before_cleanup_changes_it(self):
        with patch.object(v.w.c,'get_last_error',return_value=5),self.assertRaises(v.w.WindowsIOBlocked) as caught:
            v.w.win_need(False,'HANDLE_METADATA_FAILED','GetFileInformationByHandle')
        with patch.object(v.w.c,'get_last_error',return_value=999):self.assertEqual(v.windows_details(caught.exception)['windows_error'],5)
    def test_explicit_security_status_is_not_thread_last_error(self):
        with patch.object(v.w.c,'get_last_error',return_value=999),self.assertRaises(v.w.WindowsIOBlocked) as caught:
            v.w.win_need(False,'HANDLE_ACL_READ_FAILED','GetSecurityInfo',winerror=5)
        self.assertEqual(v.windows_details(caught.exception),dict(windows_operation='GetSecurityInfo',windows_error=5))
    def test_unknown_exception_messages_and_diagnostic_fields_are_redacted(self):
        error=v.w.WindowsIOBlocked('FICTIONAL_PASSWORD_AND_CUSTOMER_DATA',operation='PRIVATE_PATH',winerror=-1)
        error.windows_location='C:/FICTIONAL_PRIVATE_PATH'
        self.assertEqual(v.diagnostic(error),'EXTERNAL_FAILURE_DETAILS_REDACTED');self.assertEqual(v.windows_details(error),{})
        self.assertEqual(v.diagnostic(RuntimeError('FICTIONAL_PASSWORD_AND_CUSTOMER_DATA')),'EXTERNAL_FAILURE_DETAILS_REDACTED')
    def test_precreate_failure_never_connects_to_database(self):
        evidence=v.PARENT/'viva-current-fictional-0123';api=self.api();original=v.w.WindowsIOBlocked('DACL_NOT_PROTECTED');api.facts.side_effect=original
        args=['backup','--execute','--authorize',v.TOKENS['backup'],'--confirm-target',v.SOURCE,'--freeze','FREEZE_MAINTAINED','--evidence',str(evidence),'--mysql-sha256','A'*64,'--mysqldump-sha256','A'*64,'--ca-sha256','A'*64]
        with patch.object(v.w,'_Win32',return_value=api),patch.object(v,'file_sha',return_value='A'*64),patch.object(v,'password',return_value='FICTIONAL_SECRET'),patch.object(v.sys,'stdin',Mock(isatty=Mock(return_value=True))),patch('builtins.input',return_value='fictional_dba'),patch.object(v,'connect') as connect,patch.object(v,'dba_gate') as gate,patch.object(v,'checked_process') as process,self.assertRaises(v.w.WindowsIOBlocked):v.main(args)
        connect.assert_not_called();gate.assert_not_called();process.assert_not_called();api.k.CreateDirectoryW.assert_not_called()

class Win32PolicyRegressionTests(unittest.TestCase):
    def api(self,*,reparse=False,protected=True,ace_flags=3,rights=0x1F01FF,owner='S-1-5-21-1-2-3-1001',status=0):
        c=v.w.c;w=v.w.w;api=object.__new__(v.w._Win32);api.k=Mock();api.a=Mock()
        acl=v.w._ACL();acl.count=2
        ace=c.create_string_buffer(bytes([0,ace_flags,20,0])+rights.to_bytes(4,'little')+b'\0'*12)
        def metadata(handle,pointer):
            info=c.cast(pointer,c.POINTER(v.w._INFO)).contents;info.attributes=0x10|(0x400 if reparse else 0);info.links=1;return 1
        def final(handle,buffer,*args):buffer.value='\\\\?\\'+str(v.PARENT);return len(buffer.value)
        def security(handle,kind,flags,sid,group,dacl,sacl,sd):
            c.cast(sid,c.POINTER(c.c_void_p)).contents.value=123
            c.cast(dacl,c.POINTER(c.c_void_p)).contents.value=c.addressof(acl)
            c.cast(sd,c.POINTER(c.c_void_p)).contents.value=456
            return status
        def control(sd,pointer,revision):c.cast(pointer,c.POINTER(w.WORD)).contents.value=0x1000 if protected else 0;return 1
        def getace(dacl,index,pointer):c.cast(pointer,c.POINTER(c.c_void_p)).contents.value=c.addressof(ace);return 1
        api.k.GetFileInformationByHandle.side_effect=metadata;api.k.GetFileType.return_value=1;api.k.GetFinalPathNameByHandleW.side_effect=final
        api.a.GetSecurityInfo.side_effect=security;api.a.GetSecurityDescriptorControl.side_effect=control;api.a.GetAce.side_effect=getace
        api.sid=Mock(side_effect=[owner,'S-1-5-21-1-2-3-1001','S-1-5-18']);api.fixture_memory=(acl,ace)
        return api
    def facts(self,api):api.facts(Mock(closed=False,value=99),v.PARENT,directory=True,owner='S-1-5-21-1-2-3-1001')
    def test_actual_acl_parser_accepts_only_reviewed_private_policy(self):
        api=self.api();self.facts(api);api.k.LocalFree.assert_called_once()
        for changes,code in ((dict(protected=False),'DACL_NOT_PROTECTED'),(dict(ace_flags=19),'ACE_TYPE_OR_INHERITANCE_INVALID'),(dict(rights=0x120089),'ACE_RIGHTS_INVALID'),(dict(owner='S-1-5-18'),'HANDLE_OWNER_OR_DACL_INVALID'),(dict(reparse=True),'HANDLE_REPARSE_OR_DEVICE')):
            with self.subTest(changes=changes),self.assertRaisesRegex(v.w.WindowsIOBlocked,code):self.facts(self.api(**changes))
    def test_actual_security_api_reports_return_status_and_never_uses_stale_last_error(self):
        api=self.api(status=5)
        with patch.object(v.w.c,'get_last_error',return_value=999),self.assertRaises(v.w.WindowsIOBlocked) as caught:self.facts(api)
        self.assertEqual(v.windows_details(caught.exception),dict(windows_operation='GetSecurityInfo',windows_error=5))
    def test_open_keeps_original_readonly_access_and_sharing_policy(self):
        api=self.api();api.k.CreateFileW.return_value=42
        handle=api.open(v.PARENT,directory=True,read_acl=True)
        args=api.k.CreateFileW.call_args.args
        self.assertEqual(args[1],0x20080);self.assertEqual(args[2],3);self.assertEqual(args[4],3);self.assertEqual(args[5],0x02200000)
        handle.close();api.k.CloseHandle.assert_called_once_with(42)
    def test_actual_open_failure_retains_numeric_error_and_no_raw_path(self):
        api=self.api();api.k.CreateFileW.return_value=v.w.c.c_void_p(-1).value
        with patch.object(v.w.c,'get_last_error',return_value=5),self.assertRaises(v.w.WindowsIOBlocked) as caught:api.open(v.PARENT,directory=True)
        self.assertEqual(v.diagnostic(caught.exception),'EXCLUSIVE_OPEN_FAILED');self.assertEqual(v.windows_details(caught.exception)['windows_error'],5)
        self.assertNotIn(str(v.PARENT),str(caught.exception))

class DaemonGuardTests(unittest.TestCase):
    def daemon(self,name='thread/sql/event_scheduler'):
        return dict(id=2,user='event_scheduler' if name.endswith('event_scheduler') else None,thread_name=name,command='Daemon',connection_type=None,host='localhost' if name.endswith('event_scheduler') else None,database=None)
    def gate(self,extras=(),enabled_events=False):
        raw=Mock();raw.thread_id.return_value=100
        def scalar(raw,sql,parameters=()):return v.g.UUID if 'server_uuid' in sql else 'fictional@localhost' if 'CURRENT_USER' in sql else 100
        def query(raw,sql,parameters=()):
            if sql.startswith('SHOW GRANTS'):return [{'grant':"GRANT SELECT, PROCESS, EVENT ON *.* TO 'fictional'@'localhost'"}]
            if 'performance_schema.threads' in sql:return [dict(id=100,user='fictional',thread_name='thread/sql/one_connection',command='Query',connection_type='SSL/TLS',host='localhost',database=None),dict(id=1,user=v.g.MIGRATOR.split('@')[0],thread_name='thread/sql/one_connection',command='Sleep',connection_type='SSL/TLS',host='localhost',database=v.SOURCE)]+list(extras)
            if enabled_events and "STATUS='ENABLED'" in sql:return [dict(EVENT_NAME='fictional')]
            return []
        with patch('pymysql.connect',return_value=raw),patch.object(v.tls,'context'),patch.object(v.tls,'verify_socket'),patch.object(v,'scalar',side_effect=scalar),patch.object(v,'query',side_effect=query):return v.dba_gate('fictional','FICTIONAL_SECRET',[1])
    def test_both_server_daemons_are_excluded_without_excluding_clients(self):
        first=self.daemon();second=self.daemon('thread/sql/compress_gtid_table');second['id']=3
        self.assertEqual(self.gate([first,second])['uuid'],v.g.UUID)
    def test_names_alone_cannot_exclude_clients_or_workers(self):
        base=self.daemon()
        for changes in (dict(thread_name='thread/sql/one_connection'),dict(thread_name='thread/sql/event_worker'),dict(command='Sleep'),dict(connection_type='SSL/TLS'),dict(host='127.0.0.1'),dict(database=v.SOURCE),dict(user='application')):
            code='DBA_UNEXPECTED_CLIENTS_STOP' if 'thread_name' in changes else 'DBA_INTERNAL_DAEMON_CLASSIFICATION_FAILED'
            with self.subTest(changes=changes),self.assertRaisesRegex(v.VivaStop,code):self.gate([dict(base,**changes)])
    def test_unknown_daemon_and_idle_application_client_still_stop(self):
        for row in (self.daemon('thread/sql/unknown_daemon'),dict(id=88,user='application',thread_name='thread/sql/one_connection',command='Sleep',connection_type='SSL/TLS',host='localhost',database=None)):
            with self.assertRaisesRegex(v.VivaStop,'DBA_UNEXPECTED_CLIENTS_STOP'):self.gate([row])
    def test_internal_scheduler_does_not_bypass_enabled_event_rejection(self):
        with self.assertRaisesRegex(v.VivaStop,'EVENT_WRITER_ENABLED'):self.gate([self.daemon()],enabled_events=True)

class SourceRuntimeCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.net=patch.object(socket.socket,'connect',side_effect=AssertionError('NO_REAL_CONNECTION'));self.net.start();self.addCleanup(self.net.stop)
        self.state=v._RUN.set(dict(stage='SOURCE_BEFORE',database_connection_started=True,baseline_capture_started=False,native_dump_started=False));self.addCleanup(v._RUN.reset,self.state)
    def test_actual_installed_versions_match_reviewed_runtime(self):
        import importlib.metadata as metadata
        self.assertEqual(sys.version_info[:3],(3,14,7))
        self.assertEqual({p:metadata.version(p) for p in ('PyMySQL','SQLAlchemy','alembic')},{'PyMySQL':'1.2.3','SQLAlchemy':'2.1.6','alembic':'1.20.1'})
    def test_real_pymysql_constructor_accepts_strict_context_without_connecting(self):
        import ssl,pymysql
        with patch.object(ssl.SSLContext,'load_verify_locations'):
            context=v.tls.context();raw=pymysql.connect(host='127.0.0.1',port=3306,user='fictional',password='FICTIONAL_SECRET',database=v.SOURCE,ssl=context,charset='utf8mb4',collation='utf8mb4_unicode_ci',defer_connect=True)
        self.assertIs(raw.ctx,context);self.assertEqual(raw.ctx.verify_mode,ssl.CERT_REQUIRED);self.assertTrue(raw.ctx.verify_flags&ssl.VERIFY_X509_STRICT)
        self.assertTrue(raw.ctx.check_hostname);self.assertFalse(raw.ctx.hostname_checks_common_name)
        raw.server_status=2  # Fictional successful handshake status; no socket.
        with raw.cursor() as cursor:self.assertIn(v.SOURCE,cursor.mogrify('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s',(v.SOURCE,)))
        self.assertIsNone(raw._sock)
    def test_real_pymysql_converters_preserve_decimal_datetime_unicode_and_null(self):
        from pymysql import converters
        from decimal import Decimal
        from datetime import datetime
        metadata={'amount':{'type':{'family':'DECIMAL'},'nullable':False},'at':{'type':{'family':'DATETIME'},'nullable':False},'label':{'type':{'family':'VARCHAR'},'nullable':True}}
        row=dict(amount=Decimal('1234.50'),at=converters.convert_datetime('2026-11-24 12:34:56.123456'),label='தமிழ் සිංහල')
        self.assertIs(type(row['at']),datetime);v.validate_rows([row],list(metadata),metadata)
        digest=v.d.a.fingerprint([row],list(metadata));self.assertEqual(digest,v.d.a.fingerprint([dict(row,amount=Decimal('1234.500'))],list(metadata)))
        v.validate_rows([dict(row,label=None)],list(metadata),metadata)
    def test_parameter_free_sql_percent_literals_are_not_interpolated(self):
        import pymysql
        raw=pymysql.connect(user='fictional',defer_connect=True);raw.server_status=2
        with raw.cursor() as cursor:
            with self.assertRaises(pymysql.err.ProgrammingError):cursor.mogrify("SELECT '100% complete' AS label",())
        class OfflineCursor(pymysql.cursors.DictCursor):
            def _query(self,sql):self.last_sql=sql;return 0
            def fetchall(self):return []
        cursor=OfflineCursor(raw)
        with patch.object(raw,'cursor',return_value=cursor):v.query(raw,"SELECT '100% complete' AS label")
        self.assertEqual(cursor.last_sql,"SELECT '100% complete' AS label")
        cursor=OfflineCursor(raw)
        with patch.object(raw,'cursor',return_value=cursor):v.query(raw,'SELECT %s AS label',('100% complete',))
        self.assertEqual(cursor.last_sql,"SELECT '100% complete' AS label")
    def test_illegal_mysql_datetime_is_not_silently_hashed_as_text(self):
        from pymysql import converters
        metadata={'at':{'type':{'family':'DATETIME'},'nullable':False}}
        value=converters.convert_datetime('0000-00-00 00:00:00');self.assertIs(type(value),str)
        # Old untyped entry accepted this as text, then dump parsing failed later.
        self.assertEqual(v.d.a.fingerprint([{'at':value}],['at'])['row_count'],1)
        with self.assertRaisesRegex(v.VivaStop,'MYSQL_ROW_TYPE_MISMATCH'):v.validate_rows([{'at':value}],['at'],metadata)
    def test_null_nonfinite_and_wrong_numeric_types_remain_blocking(self):
        from decimal import Decimal
        metadata={'amount':{'type':{'family':'DECIMAL'},'nullable':False}}
        for value in (None,1.5,'1.50',Decimal('NaN'),Decimal('Infinity')):
            with self.subTest(value_type=type(value).__name__),self.assertRaises(v.VivaStop):v.validate_rows([dict(amount=value)],['amount'],metadata)
    def test_real_source_address_metadata_normalizes_mysql_eight_formats(self):
        expected=copy.deepcopy(v.d.c.build()['stages'][v.CHAIN[0]]['tables']['customer_addresses'])
        columns=[]
        specs=[('address_id','bigint','NO',None,'auto_increment'),('user_id','bigint','NO',None,''),('label','varchar(50)','NO',None,''),('recipient_name','varchar(150)','NO',None,''),('phone','varchar(20)','YES',None,''),('address_line','varchar(500)','NO',None,''),('city','varchar(100)','YES',None,''),('latitude','decimal(9,6)','YES',None,''),('longitude','decimal(10,6)','YES',None,''),('archived_at','datetime(6)','YES',None,''),('created_at','datetime(6)','NO','CURRENT_TIMESTAMP(6)','DEFAULT_GENERATED'),('updated_at','datetime(6)','NO','CURRENT_TIMESTAMP(6)','DEFAULT_GENERATED')]
        for position,(name,typ,nullable,default,extra) in enumerate(specs,1):columns.append(dict(COLUMN_NAME=name,ORDINAL_POSITION=position,COLUMN_TYPE=typ,IS_NULLABLE=nullable,COLUMN_DEFAULT=default,EXTRA=extra,CHARACTER_SET_NAME='utf8mb4' if typ.startswith('varchar') else None,COLLATION_NAME='utf8mb4_unicode_ci' if typ.startswith('varchar') else None,GENERATION_EXPRESSION=''))
        keys=[dict(CONSTRAINT_NAME=name,CONSTRAINT_TYPE=kind,COLUMN_NAME=column,ORDINAL_POSITION=index) for name,kind,fields in [('PRIMARY','PRIMARY KEY',['address_id']),('uq_address_id_user','UNIQUE',['address_id','user_id'])] for index,column in enumerate(fields,1)]
        indexes=[dict(INDEX_NAME=name,SEQ_IN_INDEX=index,COLUMN_NAME=column,NON_UNIQUE=unique,INDEX_TYPE='BTREE',SUB_PART=None,COLLATION='A',IS_VISIBLE='YES',EXPRESSION=None) for name,unique,fields in [('PRIMARY',0,['address_id']),('uq_address_id_user',0,['address_id','user_id']),('ix_address_user_archived',1,['user_id','archived_at','address_id'])] for index,column in enumerate(fields,1)]
        checks=[dict(CONSTRAINT_NAME='ck_address_'+name,CHECK_CLAUSE=expression,ENFORCED='YES') for name,expression in [('coordinates','(((`latitude` is null) and (`longitude` is null)) or ((`latitude` is not null) and (`longitude` is not null) and (`latitude` between -(90) and 90) and (`longitude` between -(180) and 180)))'),('line','(char_length(trim(`address_line`)) > 0)'),('label','(char_length(trim(`label`)) > 0)'),('recipient','(char_length(trim(`recipient_name`)) > 0)')]]
        observations=dict(columns=columns,keys=keys,indexes=indexes,checks=checks,foreign_keys=[dict(CONSTRAINT_NAME='fk_address_user',COLUMN_NAME='user_id',ORDINAL_POSITION=1,REFERENCED_TABLE_SCHEMA=v.SOURCE,REFERENCED_TABLE_NAME='users',REFERENCED_COLUMN_NAME='user_id',UPDATE_RULE='RESTRICT',DELETE_RULE='RESTRICT')],ddl=[{'Create Table':'FICTIONAL READONLY DDL'}])
        def query(raw,sql,params=()):
            key='ddl' if sql.startswith('SHOW CREATE') else next(key for key,value in v.d.SQL.items() if value==sql)
            return observations[key]
        with patch.object(v,'query',side_effect=query):actual,_,_=v.Inspector(Mock(),v.SOURCE).table('customer_addresses',expected)
        actual['options']={key:{'value':value} for key,value in dict(engine='InnoDB',charset='utf8mb4',collation='utf8mb4_unicode_ci').items()}
        for column in expected['columns'].values():
            if column['type']['family']=='VARCHAR':column.update(charset='utf8mb4',collation='utf8mb4_unicode_ci')
        v.d.c.verify_table(actual,expected)
        actual['columns']['latitude']['type']['scale']=5
        with self.assertRaisesRegex(ValueError,'Column definition mismatch'):v.d.c.verify_table(actual,expected)
    def test_mysql_boolean_numeric_and_clock_defaults_do_not_raise_value_error(self):
        for typ,value in [('tinyint(1)','0'),('bigint','1'),('decimal(14,2)','0.00'),('datetime','CURRENT_TIMESTAMP'),('datetime(6)','current_timestamp(6)')]:
            with self.subTest(typ=typ):self.assertIsInstance(v.d.c.default_sql(value,v.d.c.type_sql(typ)),dict)
    def test_real_check_expressions_keep_charset_literals_and_case(self):
        self.assertEqual(v.d.c.check_key("status IN ('PENDING','APPROVED')"),v.d.c.check_key("(`status` in (_utf8mb4'PENDING',_utf8mb4'APPROVED'))"))
        self.assertNotEqual(v.d.c.check_key("status IN ('PENDING')"),v.d.c.check_key("status IN ('pending')"))
    def test_canonical_failure_provides_code_module_function_and_state_without_values(self):
        actual={'columns':{}};expected={'columns':{'fictional':{}}}
        try:
            with v.phase('CANONICAL_SCHEMA_COMPARISON',table='orders'):v.d.c.verify_table(actual,expected)
        except ValueError as error:
            details=v.failure_details(error);self.assertEqual(v.diagnostic(error),'SCHEMA_COLUMN_INVENTORY_MISMATCH')
            self.assertEqual(details['substage'],'CANONICAL_SCHEMA_COMPARISON');self.assertEqual(details['stage'],'SOURCE_BEFORE');self.assertEqual(details['schema_table'],'orders')
            self.assertEqual(details['source_module'],'backend/scripts/mr07_canonical.py');self.assertEqual(details['source_function'],'verify_table')
            self.assertTrue(details['database_connection_started']);self.assertFalse(details['native_dump_started'])
        else:self.fail('Expected genuine schema mismatch')
    def test_unsupported_mysql_types_fail_closed_with_safe_location(self):
        try:
            with v.phase('METADATA_NORMALIZATION',table='orders'):v.d.c.type_sql('FICTIONAL_PRIVATE_PAYLOAD')
        except ValueError as error:
            self.assertEqual(v.diagnostic(error),'MYSQL_TYPE_UNSUPPORTED');self.assertEqual(v.failure_details(error)['source_function'],'type_sql')
            self.assertNotIn('FICTIONAL_PRIVATE_PAYLOAD',str(v.failure_details(error)))
        else:self.fail('Unsupported metadata accepted')
    def test_error_context_is_not_replaced_during_unwinding(self):
        original=ValueError('FICTIONAL_SECRET')
        with self.assertRaises(ValueError) as caught:
            with v.phase('BASELINE_CAPTURE'):
                with v.phase('TYPED_FINGERPRINT',table='orders'):raise original
        self.assertIs(caught.exception,original);self.assertEqual(v.failure_details(original)['substage'],'TYPED_FINGERPRINT')
        self.assertNotIn('FICTIONAL_SECRET',str(v.failure_details(original)));self.assertEqual(v.diagnostic(original),'VALUE_ERROR_DETAILS_REDACTED')
    def test_failed_snapshot_setup_rolls_back_and_does_not_mask_primary(self):
        raw=Mock();original=ValueError('FICTIONAL_CONNECTION_ERROR');raw.rollback.side_effect=RuntimeError('FICTIONAL_CLEANUP_ERROR')
        with patch.object(v,'identity'),patch.object(v,'revision',return_value=v.CHAIN[0]),patch.object(v,'query',side_effect=original),self.assertRaises(ValueError) as caught:v.snapshot(raw,v.SOURCE,'fictional',v.CHAIN[0])
        self.assertIs(caught.exception,original);raw.rollback.assert_called_once();self.assertEqual(v.failure_details(original)['substage'],'SNAPSHOT_BEGIN')
        self.assertEqual(original.snapshot_cleanup,'INCOMPLETE')
    def test_nonfinite_json_is_rejected_instead_of_writing_invalid_manifest(self):
        with self.assertRaises(ValueError) as caught:v.encoded({'value':float('nan')})
        self.assertEqual(v.failure_details(caught.exception)['substage'],'EVIDENCE_SERIALIZATION')
    def test_read_only_source_entry_cannot_create_files_or_launch_native_client(self):
        baseline,_=fixture();raw=Mock();raw.thread_id.return_value=123
        @contextmanager
        def connect(*args):yield raw
        args=['inspect-source','--read-only','--confirm-source',v.SOURCE,'--freeze','FREEZE_MAINTAINED','--ca-sha256','A'*64]
        with patch.object(v,'file_sha',return_value='A'*64),patch.object(v.sys,'stdin',Mock(isatty=Mock(return_value=True))),patch('builtins.input',return_value='fictional_dba'),patch.object(v,'password',return_value='FICTIONAL_SECRET'),patch.object(v,'connect',side_effect=connect),patch.object(v,'scalar',return_value=123),patch.object(v,'dba_gate') as gate,patch.object(v,'snapshot',return_value=baseline),patch.object(v,'PrivateEvidence',side_effect=AssertionError('NO_ARTIFACTS')),patch.object(v,'checked_process',side_effect=AssertionError('NO_NATIVE_CLIENT')),patch.object(v.subprocess,'Popen',side_effect=AssertionError('NO_PROCESS')):v.main(args)
        self.assertEqual(gate.call_count,2)
    def test_read_only_source_rejects_wrong_target_or_execution_flags(self):
        args=['inspect-source','--read-only','--confirm-source',v.SCRATCH,'--freeze','FREEZE_MAINTAINED','--ca-sha256','A'*64]
        with patch.object(v,'connect') as connect,self.assertRaises(v.VivaStop):v.main(args)
        connect.assert_not_called()
        args[args.index(v.SCRATCH)]=v.SOURCE
        with patch.object(v,'connect') as connect,self.assertRaises(SystemExit):v.main(args+['--execute'])
        connect.assert_not_called()

    def test_persisted_source_failure_contains_context_and_never_raw_error(self):
        baseline,_=fixture();evidence=MemoryEvidence(v.PARENT/'viva-current-fictional-0123');raw=Mock();raw.thread_id.return_value=123
        @contextmanager
        def connect(*args):v.run_state()['database_connection_started']=True;yield raw
        original=ValueError('FICTIONAL_PRIVATE_CUSTOMER_AND_PASSWORD')
        def snapshot(*args):
            v.run_state()['baseline_capture_started']=True
            with v.phase('METADATA_NORMALIZATION',table='orders'):raise original
        args=['backup','--execute','--authorize',v.TOKENS['backup'],'--confirm-target',v.SOURCE,'--freeze','FREEZE_MAINTAINED','--evidence',str(evidence.path),'--mysql-sha256','A'*64,'--mysqldump-sha256','A'*64,'--ca-sha256','A'*64]
        with patch.object(v,'PrivateEvidence',return_value=evidence),patch.object(v,'file_sha',return_value='A'*64),patch.object(v.sys,'stdin',Mock(isatty=Mock(return_value=True))),patch('builtins.input',return_value='fictional_dba'),patch.object(v,'password',return_value='FICTIONAL_SECRET'),patch.object(v,'connect',side_effect=connect),patch.object(v,'revision',return_value=v.CHAIN[0]),patch.object(v,'scalar',return_value=123),patch.object(v,'dba_gate'),patch.object(v,'snapshot',side_effect=snapshot),patch.object(v,'checked_process') as process,self.assertRaises(ValueError) as caught:v.main(args)
        self.assertIs(caught.exception,original);failure=evidence.artifacts['failure.json']
        self.assertEqual(failure['stage'],'SOURCE_BEFORE');self.assertEqual(failure['substage'],'METADATA_NORMALIZATION');self.assertEqual(failure['error_class'],'ValueError')
        self.assertTrue(failure['database_connection_started']);self.assertTrue(failure['baseline_capture_started']);self.assertFalse(failure['native_dump_started'])
        self.assertNotIn('FICTIONAL_PRIVATE_CUSTOMER_AND_PASSWORD',str(failure));self.assertNotIn('FICTIONAL_SECRET',str(failure))
        self.assertNotIn('source-before.json',evidence.artifacts);self.assertNotIn('manifest.json',evidence.artifacts);process.assert_not_called()

class CheckAttributionTests(unittest.TestCase):
    """Source/control fixtures only. The operator's 89-row inventory is missing."""
    def setUp(self):
        self.net=patch.object(socket.socket,'connect',side_effect=AssertionError('NO_DATABASE_CONNECTION'));self.net.start();self.addCleanup(self.net.stop)
    def test_all_stage_source_check_declarations_are_still_accepted(self):
        built=v.d.c.build();counts={revision:sum(len(table['checks']) for table in stage['tables'].values()) for revision,stage in built['stages'].items()}
        self.assertEqual([counts[r] for r in v.CHAIN],[89,100,115,118])
        self.assertEqual(built['head_model_parity']['differences'],[])
        previous={(table,check['name']):check for table,metadata in built['stages'][v.CHAIN[0]]['tables'].items() for check in metadata['checks']}
        changes=[]
        for revision in v.CHAIN[1:]:
            current={(table,check['name']):check for table,metadata in built['stages'][revision]['tables'].items() for check in metadata['checks']}
            added=set(current)-set(previous);changed={key for key in set(current)&set(previous) if current[key]!=previous[key]}
            self.assertFalse(set(previous)-set(current));changes.append((len(added),len(changed)))
            if changed:self.assertEqual(changed,{('notifications','ck_notification_type'),('notifications','ck_notification_entity_type')})
            previous=current
        self.assertEqual(changes,[(11,0),(15,2),(3,0)])
    def test_admin_introducer_control_does_not_reproduce_operator_failure(self):
        # Hand-authored controls, NOT presented as captured MySQL metadata.
        controls=[("target_type IN ('user','driver')","(`target_type` in (_utf8mb4'user',_utf8mb4'driver'))"),
                  ("action IN ('driver_approved','driver_rejected','account_suspended','account_reactivated','admin_provisioned')","(`action` in (_utf8mb4'driver_approved',_utf8mb4'driver_rejected',_utf8mb4'account_suspended',_utf8mb4'account_reactivated',_utf8mb4'admin_provisioned'))"),
                  ('target_id > 0','(`target_id` > 0)')]
        for expected,rendered in controls:self.assertEqual(v.d.c.check_key(expected),v.d.c.check_key(rendered))
    def test_transport_escaped_quotes_are_not_blindly_unescaped(self):
        expression=r"(`target_type` in (_utf8mb4\'user\',_utf8mb4\'driver\'))"
        with self.assertRaisesRegex(ValueError,'Unsupported CHECK syntax'):v.d.c.check_key(expression)
    def test_different_charsets_or_explicit_collations_fail_closed(self):
        for expression in ("target_type=_latin1'user'","target_type=_binary'user'","target_type=_utf8mb4'user' COLLATE utf8mb4_bin","target_type='user' COLLATE utf8mb4_unicode_ci"):
            with self.subTest(expression_kind='charset_or_collation'),self.assertRaises(ValueError):v.d.c.check_key(expression)
    def test_string_case_numbers_null_grouping_and_arguments_remain_distinct(self):
        for left,right in [("target_type='user'","target_type='USER'"),('amount>=0','amount>0'),('size_bytes<=5242880','size_bytes<=5242881'),('latitude BETWEEN -90 AND 90','latitude BETWEEN 90 AND 90'),('reviewed_at IS NULL','reviewed_at IS NOT NULL'),('a AND (b OR c)','(a AND b) OR c'),('a*(b+c)','(a*b)+c'),('ROUND(total*rate,2)','ROUND(total*rate,3)'),('CHAR_LENGTH(TRIM(label))>0','CHAR_LENGTH(TRIM(recipient_name))>0')]:
            with self.subTest(kind='semantic_drift'):self.assertNotEqual(v.d.c.check_key(left),v.d.c.check_key(right))
    def test_malformed_and_unknown_syntax_stays_rejected(self):
        for expression in ("target_type IN ('user',)",'amount >=','((amount>0)',"target_type='unterminated",'unknown(amount)>0','amount>0; DROP TABLE users','amount /* ignored */ >0'):
            with self.subTest(kind='malformed'),self.assertRaises(ValueError):v.d.c.check_key(expression)
    def test_named_parser_failure_contains_no_expression(self):
        row=dict(CONSTRAINT_NAME='ck_admin_audit_target',CHECK_CLAUSE=r"(`target_type` in (_utf8mb4\'user\'));",ENFORCED='YES')
        inspector=v.Inspector(Mock(),v.SOURCE);inspector.expected_checks['admin_audits']={'ck_admin_audit_target'}
        with patch.object(v,'query',return_value=[row]),self.assertRaises(ValueError) as caught:inspector.read('checks','admin_audits')
        details=v.failure_details(caught.exception)
        self.assertEqual(details['schema_table'],'admin_audits');self.assertEqual(details['schema_constraint'],'ck_admin_audit_target')
        self.assertEqual(details['substage'],'CHECK_EXPRESSION_PARSING');self.assertEqual(v.diagnostic(caught.exception),'CHECK_SYNTAX_UNSUPPORTED')
        self.assertEqual(details['source_function'],'check_tree');self.assertNotIn(row['CHECK_CLAUSE'],str(details))
    def test_unexpected_constraint_name_is_not_trusted_as_a_diagnostic_field(self):
        row=dict(CONSTRAINT_NAME='fictional_private_identifier',CHECK_CLAUSE='amount /*bad*/ > 0',ENFORCED='YES')
        inspector=v.Inspector(Mock(),v.SOURCE);inspector.expected_checks['admin_audits']={'ck_admin_audit_target'}
        with patch.object(v,'query',return_value=[row]),self.assertRaises(ValueError) as caught:inspector.read('checks','admin_audits')
        self.assertNotIn('schema_constraint',v.failure_details(caught.exception));self.assertNotIn('fictional_private_identifier',str(v.failure_details(caught.exception)))
    def test_disabled_missing_extra_and_changed_checks_still_fail_schema_comparison(self):
        spec=importlib.util.spec_from_file_location('check_negative_fixture',ROOT/'backend/offline_tests/mr09_mysql_adapter_suite.py')
        f=importlib.util.module_from_spec(spec);sys.modules[spec.name]=f;spec.loader.exec_module(f)
        contract=f.fixture_contract()
        for variant in ('disabled','missing','extra','changed'):
            observed=f.observed_results(v.CHAIN[0],v.SOURCE)
            if variant=='disabled':observed['checks']['orders'][0]['ENFORCED']='NO'
            elif variant=='missing':observed['checks']['orders'].clear()
            elif variant=='extra':observed['checks']['orders'].append(dict(CONSTRAINT_NAME='ck_unexpected',CHECK_CLAUSE='amount>=0',ENFORCED='YES'))
            else:observed['checks']['orders'][0]['CHECK_CLAUSE']='amount>0'
            def query(raw,sql,params=()):
                key='ddl' if sql.startswith('SHOW CREATE') else next(key for key,value in v.d.SQL.items() if value==sql)
                table=params[1] if len(params)==2 else sql.split('`')[1] if key=='ddl' else None
                return observed[key][table] if table else observed[key]
            with patch.object(v.d.c,'build',return_value=contract),patch.object(v,'query',side_effect=query),patch.object(v,'scalar',side_effect=lambda raw,sql:0 if 'COUNT(*)' in sql else 'STRICT_TRANS_TABLES'),self.subTest(variant=variant),self.assertRaises(ValueError):v.schema(Mock(),v.SOURCE,v.CHAIN[0],v.g.MIGRATOR.split('@')[0])

if __name__=='__main__':unittest.main()

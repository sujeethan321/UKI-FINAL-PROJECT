"""MR-03: fictional catalogs, bytes and in-memory migrations; network forbidden."""
import copy
from datetime import datetime,timezone
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from unittest import TestCase,main
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('mr03_test_adapter',ROOT/'backend/scripts/mr03_adapter.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a);m=a.m
spec=importlib.util.spec_from_file_location('mr03_fictional_mr02',Path(__file__).with_name('mr02_guard_suite.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

def columns(names):
    return [dict(name=n,type='FICTIONAL_TYPE',nullable=True,default=None,charset=None,collation=None,extra='') for n in names]

def grants(database,role):
    return {'global':['USAGE'],'schemas':{database.replace('_',r'\_'):sorted(a.MIGRATOR_RIGHTS if role=='migration' else a.READ_RIGHTS)},'tables':{},'active_roles':[],'default_roles':[],'mandatory_roles':[],'grant_option':False,'partial_revokes':False}

def state(value,revision,database=m.TARGET,account=m.ACCOUNT,role='migration'):
    contract=f.contract(revision);schema=contract['schema'];rows={};ddl={}
    for name in schema:
        schema[name]['columns']=columns(['id'])
        rows[name]=[{'id':1}] if name in m.names_at(m.CHAIN[0]) else []
        ddl[name]='FICTIONAL SHOW CREATE '+revision+':'+name
        schema[name]['ddl_sha256']=hashlib.sha256(ddl[name].encode()).hexdigest().upper()
    schema['driver_profiles']['columns']=columns(['user_id','approval_status']+([] if revision==m.CHAIN[0] else ['legacy_document_exempt']))
    rows['driver_profiles']=[dict(user_id=41,approval_status='approved'),dict(user_id=42,approval_status='pending')]
    if revision!=m.CHAIN[0]:
        for row in rows['driver_profiles']:row['legacy_document_exempt']=int(row['approval_status']=='approved')
    schema['ledger_entries']['columns']=columns(['id','amount','recorded_at','notes'])
    rows['ledger_entries']=[dict(id=1,amount=Decimal('10.01'),recorded_at=datetime(2026,11,23,10,0),notes='FICTIONAL PRIVATE NOTE')]
    schema['alembic_version']['columns']=columns(['version_num']);rows['alembic_version']=[{'version_num':revision}]
    schema['orders']['foreign_keys']=[dict(name='fk_fixture_user',columns=['id'],referred_table='users',referred_columns=['id'],ondelete='RESTRICT',onupdate='RESTRICT')]
    schema['orders']['checks']=[dict(name='ck_fixture_id',definition='id>0',enforced=True)]
    if revision==m.CHAIN[-1]:
        schema['customer_addresses']['columns']=columns(['id','create_request_key','create_request_hash'])
        rows['customer_addresses'][0].update(create_request_key=None,create_request_hash=None)
    identity=dict(database=database,current_user=account,host='127.0.0.1',port=3306,server_uuid='fictional-server-uuid',tls_verified=True,tls_version='TLSv1.3',foreign_key_checks=1,unique_checks=1,strict_sql_mode=True)
    return dict(identity=identity,permissions=grants(database,role),revisions=[revision],schema=schema,rows=rows,ddl=ddl,triggers=contract['triggers'],views=[],routines=[],events=[],relationship_checks={'orders:fk_fixture_user':0},
        freeze=dict(writer_freeze=True,ddl_freeze=True,dba_visibility=True,unexplained_sessions=0,transactions=0,locks=0,ddl=0,enabled_events=0,replication_appliers=0,scratch_isolated=True))

class AdapterTests(TestCase):
    def setUp(self):
        self.network=patch('socket.socket.connect',side_effect=AssertionError('NETWORK FORBIDDEN'));self.network.start();self.addCleanup(self.network.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.backup=Path(self.temp.name)/'fictional.backup';self.backup.write_bytes(b'FICTIONAL BACKUP NOT SQL')
        self.value=f.manifest(self.backup)
        self.states={r:state(self.value,r) for r in m.CHAIN}
        for revision,data in self.states.items():
            self.value['stages'][revision]=dict(revision=revision,**{k:copy.deepcopy(data[k]) for k in ('schema','triggers','views','routines','events')})
        self.source_port=a.MockCatalogPort(state(self.value,m.CHAIN[0],m.SOURCE,a.SOURCE_ACCOUNT,'source'))
        self.port=a.MockCatalogPort(self.states[m.CHAIN[0]])
        self.source=self.capture(self.source_port,m.SOURCE,a.SOURCE_ACCOUNT,'source')
        self.reader=self.capture(self.port)
        baseline=self.value['baseline']
        baseline['originals']={name:dict(**a.fingerprint(self.source_port.rows(name),[c['name'] for c in self.source_port.table(name)['columns']]),projection_columns=[c['name'] for c in self.source_port.table(name)['columns']]) for name in m.names_at(m.CHAIN[0])-{'alembic_version'}}
        baseline['driver_approval_flags']=self.source.driver_flags()
        self.value['source_fingerprint']=m.digest(baseline);self.value['adapter_provenance']=a.adapter_provenance();self.value['fingerprint_algorithm']=a.ALGORITHM
        self.value['dba_approval']=dict(server_uuid='fictional-server-uuid',source=m.SOURCE,scratch=m.TARGET,source_account=a.SOURCE_ACCOUNT,scratch_account=m.ACCOUNT,source_scope='SELECT_ONLY',scratch_scope='EXACT_SCRATCH_MIGRATOR',issuer='fictional-dba',max_age_seconds=120)
        self.manifest=Path(self.temp.name)/'manifest.json';self.write_manifest()
        self.writer=a.MockMigrationPort(self.port,{r:s for r,s in self.states.items() if r!=m.CHAIN[0]})
        self.evidence=a.MemoryEvidence();self.adapter=self.make_adapter()
    def capture(self,port,database=m.TARGET,account=m.ACCOUNT,role='migration'):
        return a.ReadOnlyCapture(port,database=database,account=account,role=role,server_uuid='fictional-server-uuid')
    def write_manifest(self):self.manifest.write_text(json.dumps(self.value),encoding='utf-8');self.approved=m.file_hash(self.manifest)
    def make_adapter(self):
        authority=m.evidence_contract.MockAttestationAuthority()
        envelopes=[authority.issue(dict(**{k:v for k,v in self.value['dba_approval'].items() if k!='max_age_seconds'},evidence_id='fictional-'+str(i),observed_at=1000,expires_at=1120,trigger_definers_attested=True,writer_freeze=True,ddl_freeze=True)) for i in range(128)]
        return a.PreparedAdapter(source=self.source,capture=self.reader,writer=self.writer,evidence=self.evidence,manifest_path=self.manifest,manifest_sha256=self.approved,source_fingerprint=self.value['source_fingerprint'],backup_path=self.backup,dba_authority=authority,dba_evidence=envelopes,mock_now=1000)
    def blocked(self,code,operation):
        with self.assertRaises(m.GuardFailure) as error:operation()
        self.assertEqual(error.exception.code,code)
    def run_chain(self):return m.execute_prepared(self.adapter,self.value,database=m.TARGET,account=m.ACCOUNT,execute=True,confirmation=m.TARGET,authorization=m.TOKEN,validated_evidence=self.adapter.validated_evidence)
    def test_source_target_cannot_be_migration_binding(self):
        self.blocked('MR03_BINDING_REJECTED',lambda:self.capture(self.source_port,m.SOURCE,a.SOURCE_ACCOUNT,'migration'))
    def test_wrong_scratch_accounts_and_default_hosts(self):
        self.blocked('MR03_BINDING_REJECTED',lambda:self.capture(self.port,m.TARGET,'root@localhost'))
        self.port.state['identity']['host']='localhost';self.blocked('MR03_ACTUAL_IDENTITY_MISMATCH',self.reader.inspect_identity)
    def test_actual_identity_account_database_uuid_and_tls(self):
        for key,value,code in (('database',m.SOURCE,'MR03_ACTUAL_IDENTITY_MISMATCH'),('current_user','root@localhost','MR03_ACTUAL_IDENTITY_MISMATCH'),('server_uuid','other','MR03_ACTUAL_IDENTITY_MISMATCH'),('tls_verified',False,'MR03_TLS_UNVERIFIED')):
            original=copy.deepcopy(self.port.state['identity']);self.port.state['identity'][key]=value
            self.blocked(code,self.reader.inspect_identity);self.port.state['identity']=original
    def test_raw_connection_objects_are_never_accepted(self):
        self.blocked('MR03_NONMOCK_TRANSPORT_REJECTED',lambda:self.capture(object()))
        self.blocked('MR03_NONMOCK_CAPABILITY_REJECTED',lambda:a.PreparedAdapter(source=object(),capture=self.reader,writer=self.writer,evidence=self.evidence,manifest_path=self.manifest,manifest_sha256=self.approved,source_fingerprint=self.value['source_fingerprint'],backup_path=self.backup))
    def test_fixture_cannot_hide_a_live_connection_or_callback(self):
        class Dangerous:
            def __deepcopy__(self,memo):raise AssertionError('must never be called')
        for value in (Dangerous(),lambda:None,object()):
            self.blocked('MR03_NONDATA_FIXTURE',lambda:a.MockCatalogPort({'connection':value}))
    def test_real_factory_always_blocks_and_redacts_credentials(self):
        with patch.dict('os.environ',{'MYSQL_DATABASE':m.TARGET,'MR03_ENABLE_REAL':'true'}):
            with self.assertRaises(m.GuardFailure) as error:a.blocked_real_connection(password='FICTIONAL_SECRET',host='127.0.0.1')
        self.assertEqual(str(error.exception),'MR03_REAL_CONNECTION_DISABLED');self.assertNotIn('FICTIONAL_SECRET',repr(error.exception))
    def test_no_database_or_application_libraries_imported(self):
        import ast
        tree=ast.parse((ROOT/'backend/scripts/mr03_adapter.py').read_text(encoding='utf-8'))
        imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]+[v.name for n in ast.walk(tree) if isinstance(n,ast.Import) for v in n.names]
        self.assertFalse(any(x and x.split('.')[0] in ('pymysql','sqlalchemy','alembic','app','subprocess','socket') for x in imports))
    def test_missing_backup_or_changed_backup_blocks_before_stage(self):
        self.backup.write_bytes(b'CHANGED')
        self.blocked('BACKUP_FINGERPRINT_MISMATCH',lambda:self.adapter.preflight(self.value));self.assertEqual(self.writer.attempted,[])
        self.backup.unlink();self.blocked('MISSING_BACKUP_EVIDENCE',self.make_adapter)
    def test_changed_manifest_binding_and_adapter_hash(self):
        self.manifest.write_text('{}',encoding='utf-8');self.blocked('MANIFEST_FINGERPRINT_MISMATCH',self.make_adapter)
        self.value['adapter_provenance']={};self.write_manifest();self.blocked('MR03_ADAPTER_OR_FINGERPRINT_CONTRACT_DRIFT',self.make_adapter)
    def test_privilege_global_role_and_grant_option_rejection(self):
        for key,value in (('global',['SUPER']),('active_roles',['admin']),('default_roles',['writer']),('mandatory_roles',['global']),('grant_option',True),('tables',{'other.users':['SELECT']})):
            old=copy.deepcopy(self.port.state['permissions']);self.port.state['permissions'][key]=value
            self.blocked('MR03_UNSAFE_PRIVILEGES',self.reader.inspect_identity);self.port.state['permissions']=old
    def test_cross_schema_and_unescaped_grants_rejection(self):
        self.port.state['permissions']['schemas'][m.SOURCE]=['SELECT'];self.blocked('MR03_CROSS_SCHEMA_PRIVILEGES',self.reader.inspect_identity)
        self.port.state['permissions']=grants(m.TARGET,'migration');self.port.state['permissions']['schemas']={m.TARGET:sorted(a.MIGRATOR_RIGHTS)}
        self.blocked('MR03_CROSS_SCHEMA_PRIVILEGES',self.reader.inspect_identity)
    def test_source_reader_never_needs_ddl_or_trigger_privileges(self):
        self.assertEqual(set(next(iter(self.source_port.permissions()['schemas'].values()))),{'SELECT'})
        self.source_port.state['permissions']['schemas'][m.SOURCE.replace('_',r'\_')].append('TRIGGER')
        self.blocked('MR03_UNSAFE_PRIVILEGES',self.source.inspect_identity)
    def test_partial_revokes_exact_scope(self):
        self.port.state['permissions'].update(partial_revokes=True,schemas={m.TARGET:sorted(a.MIGRATOR_RIGHTS)})
        self.reader.inspect_identity()
    def test_revision_capture_requires_single_reviewed_revision(self):
        for revision in ([],['head'],[m.CHAIN[0],m.CHAIN[1]]):
            self.port.state['revisions']=revision;self.blocked('MR03_REVISION_UNVERIFIED',self.reader.inventory)
    def test_readonly_capture_has_no_mutation_interface(self):
        self.assertFalse(hasattr(self.reader,'upgrade_one'));self.assertFalse(hasattr(self.reader,'execute'));self.assertFalse(hasattr(self.reader,'connect'))
        result=self.reader.snapshot(self.value);m.check_snapshot(result,self.value,m.CHAIN[0]);self.assertEqual(result['foreign_keys_checked'],1)
    def test_missing_altered_constraints_columns_indexes_and_ddl(self):
        for field,change in (('columns',[]),('indexes',[{'name':'extra'}]),('unique_constraints',[{'name':'unexpected'}])):
            old=copy.deepcopy(self.port.state['schema']['orders']);self.port.state['schema']['orders'][field]=change
            with self.assertRaises(m.GuardFailure):m.check_snapshot(self.reader.snapshot(self.value),self.value,m.CHAIN[0])
            self.port.state['schema']['orders']=old
        self.port.state['ddl']['orders']='ALTERED FICTIONAL DDL'
        self.blocked('STAGE_SCHEMA_OR_STORED_OBJECT_DRIFT',lambda:m.check_snapshot(self.reader.snapshot(self.value),self.value,m.CHAIN[0]))
    def test_unenforced_and_same_named_changed_check(self):
        self.port.state['schema']['orders']['checks'][0]['enforced']=False;self.blocked('CHECK_ENFORCEMENT_UNVERIFIED',self.reader.inventory)
        self.port.state['schema']['orders']['checks'][0].update(enforced=True,definition='id>=-1')
        self.blocked('STAGE_SCHEMA_OR_STORED_OBJECT_DRIFT',lambda:m.check_snapshot(self.reader.snapshot(self.value),self.value,m.CHAIN[0]))
    def test_missing_altered_unexpected_trigger_and_definer(self):
        for variant in ('missing','body','unexpected','definer'):
            port=a.MockCatalogPort(self.states[m.CHAIN[2]]);reader=self.capture(port)
            if variant=='missing':port.state['triggers'].pop()
            elif variant=='body':port.state['triggers'][0]['statement']='SELECT 1'
            elif variant=='unexpected':port.state['triggers'].append(dict(port.state['triggers'][0],name='unexpected'))
            else:port.state['triggers'][0]['definer']=''
            with self.assertRaises(m.GuardFailure):reader.inventory()
    def test_trigger_definer_change_remains_exact_mismatch(self):
        port=a.MockCatalogPort(self.states[m.CHAIN[2]]);port.state['triggers'][0]['definer']='different@localhost';reader=self.capture(port)
        self.blocked('STAGE_SCHEMA_OR_STORED_OBJECT_DRIFT',lambda:m.check_snapshot(reader.snapshot(self.value),self.value,m.CHAIN[2]))
    def test_fingerprint_order_duplicates_decimal_precision_and_types(self):
        rows=[{'x':Decimal('10.0100')},{'x':None},{'x':b'abc'}]
        self.assertEqual(a.fingerprint(rows,['x']),a.fingerprint(reversed(rows),['x']))
        self.assertEqual(a.fingerprint([{'x':Decimal('10.01')}],['x']),a.fingerprint([{'x':Decimal('10.010')}],['x']))
        self.assertNotEqual(a.fingerprint([{'x':'10.01'}],['x']),a.fingerprint([{'x':Decimal('10.01')}],['x']))
        self.assertNotEqual(a.fingerprint(rows,['x']),a.fingerprint(rows+rows,['x']))
        self.assertNotEqual(a.typed_value(Decimal('100')),a.typed_value(Decimal('100.00000000000000000000000000001')))
    def test_fingerprint_wall_clock_preserved_and_bad_types_rejected(self):
        self.assertEqual(a.typed_value(datetime(2026,11,23,1,2))[1],'2026-11-23T01:02:00.000000')
        for value in (1.1,object(),Decimal('NaN'),datetime.now(timezone.utc)):
            with self.assertRaises(m.GuardFailure):a.typed_value(value)
    def test_fingerprint_row_limits_and_count_races(self):
        with patch.object(a,'MAX_ROWS',1):
            self.blocked('MR03_ROW_CAPTURE_INCOMPLETE_OR_TOO_LARGE',lambda:a.fingerprint([{'id':1},{'id':2}],['id']))
        self.port.state['count_overrides']={'ledger_entries':2}
        self.blocked('MR03_ROW_COUNT_CHANGED_DURING_CAPTURE',lambda:self.reader.snapshot(self.value))
    def test_financial_row_change_detected_without_rows_in_error(self):
        self.port.state['rows']['ledger_entries'][0]['amount']=Decimal('10.02')
        with self.assertRaises(m.GuardFailure) as error:m.check_snapshot(self.reader.snapshot(self.value),self.value,m.CHAIN[0])
        self.assertEqual(str(error.exception),'ORIGINAL_RECORDS_CHANGED');self.assertNotIn('PRIVATE',str(error.exception))
    def test_foreign_key_missing_or_orphan_observation_rejected(self):
        self.port.state['relationship_checks']={};self.blocked('MR03_INCOMPLETE_ORPHAN_INSPECTION',lambda:self.reader.snapshot(self.value))
        self.port.state['relationship_checks']={'orders:fk_fixture_user':1}
        self.blocked('RELATIONSHIP_INTEGRITY_UNVERIFIED',lambda:m.check_snapshot(self.reader.snapshot(self.value),self.value,m.CHAIN[0]))
    def test_freeze_gate_checked_before_reservation(self):
        self.port.state['freeze']['ddl']=1;self.blocked('MR03_FRESH_DBA_GATE_UNVERIFIED',self.run_chain)
        self.assertFalse(self.evidence.reserved);self.assertEqual(self.writer.attempted,[])
    def test_complete_mock_chain_and_all_inventories(self):
        result=self.run_chain();self.assertIn('RECOVERY_AND_CONCURRENCY_NOT_VERIFIED',result)
        self.assertEqual(self.writer.attempted,list(m.CHAIN[1:]));self.assertEqual(len(self.port.table_names()),45);self.assertEqual(len(self.port.triggers()),18)
        self.assertEqual(self.evidence.records[-1]['status'],'CHAIN_VERIFIED_MOCK_ONLY')
    def test_writer_rejects_head_skip_replay_and_source(self):
        self.blocked('MR03_BINDING_REJECTED',lambda:a.MockMigrationPort(self.source_port,self.states))
        self.blocked('MR03_UNAPPROVED_STAGE',lambda:self.writer.apply_one(m.CHAIN[0],'head'))
        self.blocked('MR03_UNAPPROVED_STAGE',lambda:self.writer.apply_one(m.CHAIN[0],m.CHAIN[-1]))
        self.writer.apply_one(m.CHAIN[0],m.CHAIN[1]);self.blocked('MR03_STAGE_REPLAY_OR_REVISION_MISMATCH',lambda:self.writer.apply_one(m.CHAIN[0],m.CHAIN[1]))
    def test_source_schema_drift_blocks_with_unchanged_rows(self):
        self.source_port.state['ddl']['ledger_entries']='FICTIONAL ALTERED DDL'
        self.blocked('MR03_SOURCE_SCHEMA_CHANGED',self.run_chain)
        self.assertFalse(self.evidence.reserved);self.assertEqual(self.writer.attempted,[])
    def test_failed_stage_preserves_partial_ddl_and_latches(self):
        self.writer.fail_after_apply=True
        self.blocked('MR03_MOCK_PARTIAL_DDL_FAILURE',self.run_chain)
        self.assertEqual(self.writer.attempted,[m.CHAIN[1]]);self.assertEqual(self.port.revision(),[m.CHAIN[1]])
        self.assertTrue(self.evidence.records[-1]['partial_ddl_suspected'])
        self.blocked('MR03_FAILED_ATTEMPT_LATCHED',lambda:self.adapter.preflight(self.value))
        self.blocked('MR03_FAILED_ATTEMPT_LATCHED',lambda:self.writer.apply_one(m.CHAIN[1],m.CHAIN[2]))
    def test_failure_with_old_revision_and_new_objects_detected(self):
        self.writer.stages[m.CHAIN[1]]['revisions']=[m.CHAIN[0]];self.writer.fail_after_apply=True
        self.blocked('MR03_MOCK_PARTIAL_DDL_FAILURE',self.run_chain)
        observed=self.evidence.records[-1];self.assertEqual(observed['observed']['revisions'],[m.CHAIN[0]])
        self.assertEqual(len(observed['observed']['tables']),35);self.assertTrue(observed['partial_ddl_suspected'])
    def test_failed_check_after_stage_stops_without_later_upgrade(self):
        self.writer.stages[m.CHAIN[1]]['schema'].pop('driver_document_audits')
        with self.assertRaises(m.GuardFailure):self.run_chain()
        self.assertEqual(self.writer.attempted,[m.CHAIN[1]]);self.assertTrue(self.adapter.failed)
    def test_error_evidence_does_not_include_rows_paths_or_raw_errors(self):
        self.adapter.record_failure(m.CHAIN[1],'password=FICTIONAL_SECRET; C:\\private',True)
        evidence=json.dumps(self.evidence.records)
        for value in ('FICTIONAL_SECRET','FICTIONAL PRIVATE NOTE',str(self.manifest),'password='):self.assertNotIn(value,evidence)
    def test_partial_capture_failure_keeps_first_failure_record(self):
        self.port.state['identity']['database']=m.SOURCE;self.adapter.record_failure(m.CHAIN[1],'MR03_TEST_FAILURE')
        self.assertEqual(self.evidence.records[0]['status'],'STOP_MOCK_ONLY');self.assertEqual(self.evidence.records[1]['status'],'PARTIAL_STATE_UNAVAILABLE_PRESERVE_NO_RETRY')
    def test_source_recovery_compare_full_row_and_schema_capture(self):
        restore_port=a.MockCatalogPort(copy.deepcopy(self.source_port.state));restore_port.state['identity'].update(database=m.RESTORE_TARGET,current_user=m.RESTORE_ACCOUNT);restore_port.state['permissions']=grants(m.RESTORE_TARGET,'recovery')
        reader=self.capture(restore_port,m.RESTORE_TARGET,m.RESTORE_ACCOUNT,'recovery')
        before=self.source.recovery_snapshot();after=reader.recovery_snapshot()
        self.assertIn('PASS_CAPTURED',m.verify_recovery(before,after,m.digest(before)))
        restore_port.state['rows']['ledger_entries'][0]['amount']=Decimal('9.00')
        self.blocked('RECOVERY_RECORDS_MISMATCH',lambda:m.verify_recovery(before,reader.recovery_snapshot(),m.digest(before)))
    def test_existing_mr02_cli_blocker_unchanged(self):
        args=['execute','--database',m.TARGET,'--account',m.ACCOUNT,'--manifest',str(self.manifest),'--manifest-sha256',self.approved,'--source-fingerprint',self.value['source_fingerprint'],'--backup',str(self.backup),'--execute','--confirm-target',m.TARGET,'--authorization',m.TOKEN]
        with patch('sys.stdout',new_callable=io.StringIO) as out:self.assertEqual(m.main(args),1)
        self.assertIn('LIVE_ADAPTER_NOT_PREPARED_OR_AUTHORIZED',out.getvalue());self.assertFalse(self.evidence.reserved)

if __name__=='__main__':main()

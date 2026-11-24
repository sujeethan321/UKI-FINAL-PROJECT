"""MR-02 fictional inventories and in-memory adapters only; networking forbidden."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from unittest import TestCase,main
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('mr02_guard',ROOT/'backend/scripts/mr02_rehearsal.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def contract(revision):
    table=dict(columns=[dict(name='id',type='BIGINT',nullable=False,default=None,charset=None,collation=None,extra='')],
        primary_key=['id'],foreign_keys=[],unique_constraints=[],checks=[],indexes=[],options={'engine':'InnoDB'},ddl_sha256='A'*64)
    triggers=[]
    for name,(target,timing,event,message) in m.trigger_specs(revision).items():
        triggers.append(dict(name=name,table=target,timing=timing,event=event,orientation='ROW',definer='fictional@localhost',
            statement="SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '"+message+"'",sql_mode='STRICT_TRANS_TABLES',character_set_client='utf8mb4',collation_connection='utf8mb4_unicode_ci',database_collation='utf8mb4_unicode_ci'))
    return dict(revision=revision,schema={n:copy.deepcopy(table) for n in sorted(m.names_at(revision))},triggers=triggers,views=[],routines=[],events=[])

def manifest(backup):
    baseline=dict(originals={n:dict(row_count=0,content_sha256='B'*64,projection_columns=['id']) for n in m.names_at(m.CHAIN[0])-{'alembic_version'}},driver_approval_flags={})
    return dict(target=m.TARGET,account=m.ACCOUNT,source=dict(database=m.SOURCE,host='127.0.0.1',port=3306,revision=m.CHAIN[0]),
        source_fingerprint=m.digest(baseline),provenance=m.source_provenance(),revision_sequence=list(m.CHAIN),backup_sha256=m.file_hash(backup),
        backup_complete=True,independent_recovery_approval=True,features=dict.fromkeys(m.FEATURES,False),baseline=baseline,
        stages={revision:contract(revision) for revision in m.CHAIN})

def snapshot(value,revision):
    return dict(**copy.deepcopy(value['stages'][revision]),database=m.TARGET,account=m.ACCOUNT,host='127.0.0.1',port=3306,tls_verified=True,
        originals=copy.deepcopy(value['baseline']['originals']),driver_exemption_flags=copy.deepcopy(value['baseline']['driver_approval_flags']),
        historical_address_request_values={'row_count':value['baseline']['originals']['customer_addresses']['row_count'],'non_null_keys':0,'non_null_hashes':0},
        new_table_counts=dict.fromkeys(m.names_at(revision)-m.names_at(m.CHAIN[0]),0),foreign_keys_checked=0,orphan_count=0,foreign_key_checks=1,unique_checks=1,strict_sql_mode=True)

class FakeAdapter:
    def __init__(self,value):self.value=value;self.revision=m.CHAIN[0];self.calls=[];self.fail=False
    def preflight(self,value):self.calls.append('gate');return True
    def source_fingerprint(self):return self.value['source_fingerprint']
    def snapshot(self):return snapshot(self.value,self.revision)
    def reserve_exclusive_attempt(self):self.calls.append('reserve')
    def upgrade_one(self,previous,current):
        self.calls.append(('upgrade',previous,current));self.revision=current
        if self.fail:raise RuntimeError('fictional sensitive error must not print')
    def record_stage(self,current):self.calls.append(('verified',current))
    def record_success(self):self.calls.append('success')
    def record_failure(self,stage,code,inspect_partial):self.calls.append(('failure',stage,code,inspect_partial))

class GuardTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.backup=Path(self.temp.name)/'fictional.backup';self.backup.write_bytes(b'FICTIONAL NOT SQL')
        self.value=manifest(self.backup)
        self.network=patch('socket.socket.connect',side_effect=AssertionError('Network forbidden'));self.network.start();self.addCleanup(self.network.stop)
    def assertBlocked(self,code,operation):
        with self.assertRaises(m.GuardFailure) as error:operation()
        self.assertEqual(error.exception.code,code)
    def validate(self):return m.validate_manifest(self.value,self.backup,self.value['source_fingerprint'])
    def run_fake(self,adapter,**changes):
        path=Path(self.temp.name)/'approved-orchestration.json';path.write_text(json.dumps(self.value),encoding='utf-8')
        evidence=m.evidence_contract.issue(path,m.file_hash(path),self.backup,self.value['backup_sha256'],self.value['source_fingerprint'])
        args=dict(database=m.TARGET,account=m.ACCOUNT,execute=True,confirmation=m.TARGET,authorization=m.TOKEN,validated_evidence=evidence);args.update(changes)
        return m.execute_prepared(adapter,self.value,**args)
    def test_exact_targets_and_accounts_only(self):
        for target in ('lankapex_viva_db','lankapex_db','lankapex_test_db','lankapex_viva_recovery_step391','lankapex_driver_rehearsal_423','other'):
            self.assertBlocked('UNAPPROVED_DATABASE',lambda:m.target_guard(target,m.ACCOUNT))
        self.assertBlocked('UNAPPROVED_ACCOUNT',lambda:m.target_guard(m.TARGET,'root@localhost'))
    def test_reviewed_source_graph_and_all_stage_counts(self):
        self.assertTrue(m.source_provenance())
        self.assertEqual([len(m.names_at(r)) for r in m.CHAIN],list(m.COUNTS))
        self.assertEqual([len(m.trigger_specs(r)) for r in m.CHAIN],[0,0,10,16,18])
    def test_fictional_manifest_and_backup_binding(self):self.assertEqual(self.validate(),self.value)
    def test_wrong_backup_fingerprint(self):
        self.value['backup_sha256']='0'*64;self.assertBlocked('BACKUP_FINGERPRINT_MISMATCH',self.validate)
    def test_missing_backup_blocks(self):
        self.assertBlocked('MISSING_BACKUP_EVIDENCE',lambda:m.validate_manifest(self.value,self.backup.with_name('absent'),self.value['source_fingerprint']))
    def test_source_identity_and_fingerprint(self):
        self.assertBlocked('SOURCE_FINGERPRINT_MISMATCH',lambda:m.validate_manifest(self.value,self.backup,'0'*64))
        self.value['source']['database']='lankapex_db';self.assertBlocked('SOURCE_IDENTITY_MISMATCH',self.validate)
    def test_tooling_drift(self):
        self.value['provenance']={};self.assertBlocked('SOURCE_TOOLING_DRIFT',self.validate)
    def test_revision_order(self):
        self.value['revision_sequence'].reverse();self.assertBlocked('REVISION_SEQUENCE_DRIFT',self.validate)
    def test_incomplete_stage(self):
        self.value['stages'][m.CHAIN[2]]['schema'].pop('driver_earnings');self.assertBlocked('TABLE_INVENTORY_MISMATCH',self.validate)
    def test_disabled_feature_contract(self):
        self.value['features']['ai']=True;self.assertBlocked('FEATURE_GATE_ENABLED',self.validate)
    def test_missing_and_altered_triggers(self):
        self.value['stages'][m.CHAIN[-1]]['triggers'].pop();self.assertBlocked('MISSING_TRIGGER',self.validate)
        self.value=manifest(self.backup);self.value['stages'][m.CHAIN[-1]]['triggers'][0]['statement']='SELECT 1'
        self.assertBlocked('TRIGGER_BODY_DRIFT',self.validate)
    def test_trigger_identity_and_context(self):
        row=self.value['stages'][m.CHAIN[-1]]['triggers'][0];row['table']='orders'
        self.assertBlocked('TRIGGER_TARGET_DRIFT',self.validate)
        self.value=manifest(self.backup);self.value['stages'][m.CHAIN[-1]]['triggers'][0].pop('sql_mode')
        self.assertBlocked('TRIGGER_CONTEXT_MISSING',self.validate)
    def test_checks_and_unknown_stored_objects(self):
        self.value['stages'][m.CHAIN[0]]['schema']['orders']['checks']=[dict(name='x',definition='total>0',enforced=False)]
        self.assertBlocked('CHECK_ENFORCEMENT_UNVERIFIED',self.validate)
        self.value=manifest(self.backup);self.value['stages'][m.CHAIN[0]]['events']=[{'name':'unknown'}]
        self.assertBlocked('UNREVIEWED_STORED_OBJECTS',self.validate)
    def test_modified_schema_and_original_financial_rows(self):
        actual=snapshot(self.value,m.CHAIN[0]);actual['schema']['orders']['columns'][0]['type']='TEXT'
        self.assertBlocked('STAGE_SCHEMA_OR_STORED_OBJECT_DRIFT',lambda:m.check_snapshot(actual,self.value,m.CHAIN[0]))
        actual=snapshot(self.value,m.CHAIN[0]);actual['originals']['ledger_entries']['content_sha256']='0'*64
        self.assertBlocked('ORIGINAL_RECORDS_CHANGED',lambda:m.check_snapshot(actual,self.value,m.CHAIN[0]))
    def test_exemption_backfill_and_new_tables(self):
        actual=snapshot(self.value,m.CHAIN[1]);actual['driver_exemption_flags']={'0'*64:True}
        self.assertBlocked('DRIVER_EXEMPTION_BACKFILL_MISMATCH',lambda:m.check_snapshot(actual,self.value,m.CHAIN[1]))
        actual=snapshot(self.value,m.CHAIN[1]);actual['new_table_counts']['driver_document_audits']=1
        self.assertBlocked('NEW_TABLE_INITIALIZATION_MISMATCH',lambda:m.check_snapshot(actual,self.value,m.CHAIN[1]))
    def test_no_historical_address_request_fabrication(self):
        actual=snapshot(self.value,m.CHAIN[-1]);actual['historical_address_request_values']['non_null_keys']=1
        self.assertBlocked('HISTORICAL_ADDRESS_BACKFILL_MISMATCH',lambda:m.check_snapshot(actual,self.value,m.CHAIN[-1]))
    def test_cross_schema_foreign_keys_blocked(self):
        self.value['stages'][m.CHAIN[0]]['schema']['orders']['foreign_keys']=[dict(name='fk',columns=['id'],referred_table='users',referred_columns=['id'],referred_schema=m.SOURCE,ondelete='RESTRICT',onupdate='RESTRICT')]
        self.assertBlocked('INCOMPLETE_FOREIGN_KEYS',self.validate)
    def test_stale_schema_after_upgrade_stops_chain(self):
        adapter=FakeAdapter(self.value)
        original=adapter.snapshot
        def capture():
            result=original()
            if adapter.revision!=m.CHAIN[0]:result['schema'].pop('driver_document_audits')
            return result
        adapter.snapshot=capture
        self.assertBlocked('TABLE_INVENTORY_MISMATCH',lambda:self.run_fake(adapter))
        self.assertEqual(len([c for c in adapter.calls if isinstance(c,tuple) and c[0]=='upgrade']),1)
    def test_wrong_live_identity_revision_and_orphans(self):
        for field,value,code in (('database',m.SOURCE,'UNAPPROVED_DATABASE'),('revision',m.CHAIN[-1],'ACTUAL_REVISION_MISMATCH'),('orphan_count',1,'RELATIONSHIP_INTEGRITY_UNVERIFIED'),('tls_verified',False,'CONNECTION_IDENTITY_UNVERIFIED')):
            actual=snapshot(self.value,m.CHAIN[0]);actual[field]=value
            self.assertBlocked(code,lambda:m.check_snapshot(actual,self.value,m.CHAIN[0]))
    def test_two_column_orphan_query_uses_match_simple_and_not_exists(self):
        sql=m.orphan_query('orders',dict(columns=['id','customer_id'],referred_table='users',referred_columns=['id','customer_id']))
        self.assertIn('c.`id` IS NOT NULL AND c.`customer_id` IS NOT NULL',sql);self.assertIn('NOT EXISTS',sql)
        self.assertBlocked('UNSAFE_METADATA_IDENTIFIER',lambda:m.orphan_query('orders; DROP',dict(columns=['id'],referred_table='users',referred_columns=['id'])))
    def test_authorization_before_adapter_operations(self):
        for change in ({'execute':False},{'confirmation':'other'},{'authorization':None}):
            adapter=FakeAdapter(self.value);self.assertBlocked('EXECUTION_NOT_AUTHORIZED',lambda:self.run_fake(adapter,**change));self.assertEqual(adapter.calls,[])
    def test_mock_full_chain_has_four_explicit_upgrades(self):
        adapter=FakeAdapter(self.value);result=self.run_fake(adapter)
        self.assertIn('RECOVERY_AND_CONCURRENCY_NOT_VERIFIED',result)
        self.assertEqual([c for c in adapter.calls if isinstance(c,tuple) and c[0]=='upgrade'],[('upgrade',p,c) for p,c in zip(m.CHAIN,m.CHAIN[1:])])
    def test_partial_ddl_stops_and_records_without_retry(self):
        adapter=FakeAdapter(self.value);adapter.fail=True
        self.assertBlocked('ADAPTER_OPERATION_FAILED',lambda:self.run_fake(adapter))
        self.assertEqual(len([c for c in adapter.calls if isinstance(c,tuple) and c[0]=='upgrade']),1)
        self.assertEqual(adapter.revision,m.CHAIN[1]);self.assertEqual(adapter.calls[-1],('failure',m.CHAIN[1],'ADAPTER_OPERATION_FAILED',True))
    def test_source_changed_before_reservation(self):
        adapter=FakeAdapter(self.value);adapter.source_fingerprint=lambda:'0'*64
        self.assertBlocked('SOURCE_CHANGED_BEFORE',lambda:self.run_fake(adapter));self.assertNotIn('reserve',adapter.calls)
    def test_offline_cli_never_connects_or_writes(self):
        path=Path(self.temp.name)/'manifest.json';path.write_text(json.dumps(self.value),encoding='utf-8');before=set(Path(self.temp.name).iterdir())
        args=['offline','--database',m.TARGET,'--account',m.ACCOUNT,'--manifest',str(path),'--manifest-sha256',m.file_hash(path),'--source-fingerprint',self.value['source_fingerprint'],'--backup',str(self.backup)]
        with patch('sys.stdout',new_callable=io.StringIO) as output:self.assertEqual(m.main(args),0)
        self.assertIn('DATABASE_CONNECTIONS=0',output.getvalue());self.assertEqual(before,set(Path(self.temp.name).iterdir()))
    def test_even_authorized_cli_execution_stays_blocked_without_adapter(self):
        path=Path(self.temp.name)/'manifest.json';path.write_text(json.dumps(self.value),encoding='utf-8')
        args=['execute','--database',m.TARGET,'--account',m.ACCOUNT,'--manifest',str(path),'--manifest-sha256',m.file_hash(path),'--source-fingerprint',self.value['source_fingerprint'],'--backup',str(self.backup),'--execute','--confirm-target',m.TARGET,'--authorization',m.TOKEN]
        with patch('sys.stdout',new_callable=io.StringIO) as output:self.assertEqual(m.main(args),1)
        self.assertIn('LIVE_ADAPTER_NOT_PREPARED_OR_AUTHORIZED',output.getvalue());self.assertNotIn(str(path),output.getvalue())
    def test_unapproved_manifest_bytes(self):
        path=Path(self.temp.name)/'manifest.json';path.write_text('{}',encoding='utf-8')
        self.assertBlocked('MANIFEST_FINGERPRINT_MISMATCH',lambda:m.load_approved(path,'0'*64))
    def test_duplicate_json_fields_rejected(self):
        path=Path(self.temp.name)/'manifest.json';path.write_text('{"x":1,"x":2}',encoding='utf-8')
        self.assertBlocked('DUPLICATE_JSON_FIELD',lambda:m.load_approved(path,m.file_hash(path)))
    def test_recovery_comparison_keeps_exact_ddl_and_all_contents(self):
        source=dict(**contract(m.CHAIN[-1]),database=m.SOURCE,host='127.0.0.1',port=3306,tls_verified=True,
            records={n:dict(row_count=0,content_sha256='C'*64) for n in m.names_at(m.CHAIN[-1])},foreign_keys_checked=0,orphan_count=0)
        restored=copy.deepcopy(source);restored.update(database=m.RESTORE_TARGET,account=m.RESTORE_ACCOUNT)
        approved=m.digest(source);self.assertIn('LIVE_SOURCE_RECHECK',m.verify_recovery(source,restored,approved))
        restored['schema']['ledger_entries']['ddl_sha256']='D'*64
        self.assertBlocked('RECOVERY_SCHEMA_MISMATCH',lambda:m.verify_recovery(source,restored,approved))

if __name__=='__main__':main()

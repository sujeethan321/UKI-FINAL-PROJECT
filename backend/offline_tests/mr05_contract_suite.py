"""MR-05 isolated fictional evidence, independent declarations and mocked capture."""
import copy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import tempfile
from unittest import TestCase,TestSuite,main
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('mr05_prior_adapter_tests',Path(__file__).with_name('mr03_adapter_suite.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f);a=f.a;m=a.m;e=m.evidence_contract
spec=importlib.util.spec_from_file_location('mr05_source_ledger',ROOT/'backend/scripts/mr05_source_contracts.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

def approval():
    return dict(server_uuid='independently-approved-fixture-server',source=m.SOURCE,scratch=m.TARGET,source_account=a.SOURCE_ACCOUNT,scratch_account=m.ACCOUNT,source_scope='SELECT_ONLY',scratch_scope='EXACT_SCRATCH_MIGRATOR',issuer='fictional-dba',max_age_seconds=100)

def payload(ident='evidence-0001',**changes):
    result=dict(**{k:v for k,v in approval().items() if k!='max_age_seconds'},evidence_id=ident,observed_at=1000,expires_at=1100,trigger_definers_attested=True,writer_freeze=True,ddl_freeze=True);result.update(changes);return result

def receipt():
    auth=e.MockAttestationAuthority();return auth.verify(auth.issue(payload()),approval(),now=1000)

class ContractTests(TestCase):
    def setUp(self):
        self.network=patch('socket.socket.connect',side_effect=AssertionError('NETWORK FORBIDDEN'));self.network.start();self.addCleanup(self.network.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
    def fail(self,code,operation):
        with self.assertRaises(e.EvidenceError) as error:operation()
        self.assertEqual(str(error.exception),code)
    def test_source_ledger_is_not_observed_mock_metadata(self):
        value=c.build();self.assertFalse(value['execution_ready'])
        self.assertEqual(value['head_model_column_differences'],{})
        self.assertEqual([len(value['stages'][r]['tables'])+1 for r in c.STAGES],[33,35,40,44,45])
        self.assertEqual([len(value['stages'][r]['triggers']) for r in c.STAGES],[0,0,10,16,18])
        self.assertTrue(all(not stage['unresolved'] for stage in value['stages'].values()))
        self.assertIn('MYSQL_REFLECTION_TO_SOURCE_DECLARATION_TRANSLATION',value['unresolved_runtime_contracts'])
        with self.assertRaisesRegex(ValueError,'SOURCE_CONTRACT_RUNTIME_PARITY_UNRESOLVED'):c.require_runtime_parity(value)
    def test_saved_source_ledger_matches_current_migrations_and_models(self):
        artifact=json.loads((ROOT/'backend/contracts/MR05_SOURCE_OBJECTS.json').read_text(encoding='utf-8'))
        artifact.pop('review_status')
        current=c.build()
        # MR-07 reconciles four model files' metadata. Preserve the historical
        # MR-05 artifact; it is not an approval of the changed model source.
        allowed={'backend/app/models/business_join_link.py','backend/app/models/customer_join_request.py','backend/app/models/customer_link_invitation.py','backend/app/models/subscription.py'}
        changed={name for name,value in artifact['source_files'].items() if current['source_files'][name]!=value}
        self.assertEqual(changed,allowed)
        for name in allowed:artifact['source_files'].pop(name);current['source_files'].pop(name)
        self.assertEqual(artifact,current)
    def test_independently_authored_missing_and_changed_required_objects(self):
        # Hand-authored expectation; no observed fixture or capture helper supplies it.
        expected={'unresolved':[],'tables':{'fictional_sale':{'columns':{'sale_id':'BIGINT NOT NULL','amount':'DECIMAL(14,2) NOT NULL'},'checks':[{'name':'ck_amount','declaration':'CHECK (amount >= 0)'}],'unique_constraints':[{'name':'uq_sale','declaration':'UNIQUE (sale_id)'}],'indexes':[{'name':'ix_sale','declaration':'INDEX (sale_id)'}],'foreign_keys':[{'name':'fk_sale','declaration':'FOREIGN KEY (sale_id) REFERENCES fictional_parent (sale_id)'}]}},'triggers':{'fictional_update_deny':{'body':"SIGNAL SQLSTATE '45000'"}}}
        observed=json.loads(json.dumps(expected));c.verify_required_objects(observed,expected)
        for category in ('columns','checks','unique_constraints','indexes','foreign_keys'):
            changed=copy.deepcopy(observed);changed['tables']['fictional_sale'][category]={} if category=='columns' else []
            with self.assertRaises(ValueError):c.verify_required_objects(changed,expected)
        changed=copy.deepcopy(observed);changed['triggers']['fictional_update_deny']['body']='SELECT 1'
        with self.assertRaises(ValueError):c.verify_required_objects(changed,expected)
    def test_resolved_source_contains_real_financial_checks_and_relationships(self):
        stage=c.build()['stages'][c.STAGES[-1]]
        earning=stage['tables']['driver_earnings'];self.assertIn('amount',earning['columns'])
        self.assertIn('fk_de_completion',{x['name'] for x in earning['foreign_keys']})
        self.assertIn('ck_de_amount',{x['name'] for x in earning['checks']})
        self.assertIn('ix_de_driver_date',{x['name'] for x in earning['indexes']})
        self.assertIn('fk_oda_order_customer',{x['name'] for x in stage['tables']['order_delivery_addresses']['foreign_keys']})
    def test_unsigned_and_real_attestations_are_blocked(self):
        auth=e.MockAttestationAuthority()
        self.fail('UNTRUSTED_DBA_EVIDENCE',lambda:auth.verify(payload(),approval(),now=1000))
        self.fail('REAL_DBA_TRUST_NOT_CONFIGURED',lambda:e.verify_real_attestation(payload()))
    def test_scope_uuid_issuer_and_missing_fields(self):
        for change in ({'server_uuid':'wrong'},{'scratch':m.SOURCE},{'source_account':'root@localhost'},{'trigger_definers_attested':False}):
            auth=e.MockAttestationAuthority();envelope=auth.issue(payload(**change))
            with self.assertRaises(e.EvidenceError):auth.verify(envelope,approval(),now=1000)
        auth=e.MockAttestationAuthority();bad=payload();bad.pop('observed_at')
        self.fail('INCOMPLETE_DBA_EVIDENCE',lambda:auth.verify(auth.issue(bad),approval(),now=1000))
    def test_stale_future_and_overlong_attestations(self):
        for observed,expires,now in ((1000,1100,1101),(1001,1100,1000),(1000,1500,1000)):
            auth=e.MockAttestationAuthority()
            self.fail('STALE_DBA_EVIDENCE',lambda:auth.verify(auth.issue(payload(observed_at=observed,expires_at=expires)),approval(),now=now))
    def test_replayed_tokens_and_evidence_ids_rejected(self):
        auth=e.MockAttestationAuthority();envelope=auth.issue(payload());auth.verify(envelope,approval(),now=1000)
        self.fail('REPLAYED_DBA_EVIDENCE',lambda:auth.verify(envelope,approval(),now=1000))
        self.fail('REPLAYED_DBA_EVIDENCE',lambda:auth.verify(auth.issue(payload()),approval(),now=1000))
    def test_tampering_with_issued_dictionary_is_not_trusted(self):
        auth=e.MockAttestationAuthority();envelope=auth.issue(payload());envelope['payload']['expires_at']=1050
        self.fail('UNTRUSTED_DBA_EVIDENCE',lambda:auth.verify(envelope,approval(),now=1000))
    def test_consistent_capture_is_owned_readonly_and_bounded(self):
        now=[0];state={'rows':[{'id':1,'amount':Decimal('2.00')}]}
        view=e.MockConsistentSnapshot(state,owner='session-A',freeze_receipt=receipt(),clock=lambda:now[0])
        self.assertEqual(view.isolation,'REPEATABLE READ');self.assertTrue(view.read_only)
        self.fail('SNAPSHOT_OWNERSHIP_OR_LIFETIME',lambda:view.read('session-B'))
        self.assertEqual(view.finish('session-A'),state)
        self.fail('SNAPSHOT_OWNERSHIP_OR_LIFETIME',lambda:view.read('session-A'))
    def test_equal_counts_do_not_hide_mixed_time_updates(self):
        state={'rows':[{'id':1,'amount':Decimal('2.00')}]}
        view=e.MockConsistentSnapshot(state,owner='A',freeze_receipt=receipt())
        state['rows'][0]['amount']=Decimal('3.00')
        self.fail('MIXED_TIME_OBSERVATION',lambda:view.finish('A'));self.assertTrue(view.closed)
    def test_snapshot_expiration_interrupt_and_receipt_replay(self):
        now=[0];proof=receipt();view=e.MockConsistentSnapshot({},owner='A',freeze_receipt=proof,lifetime=1,clock=lambda:now[0])
        now[0]=2;self.fail('SNAPSHOT_EXPIRED',lambda:view.finish('A'))
        self.fail('REPLAYED_SNAPSHOT_RECEIPT',lambda:e.MockConsistentSnapshot({},owner='A',freeze_receipt=proof))
        view=e.MockConsistentSnapshot({},owner='A',freeze_receipt=receipt());view.interrupt()
        self.fail('SNAPSHOT_OWNERSHIP_OR_LIFETIME',lambda:view.read('A'))
    def test_unsigned_snapshot_receipt_rejected(self):
        self.fail('TRUSTED_MOCK_RECEIPT_REQUIRED',lambda:e.MockConsistentSnapshot({},owner='A',freeze_receipt=payload()))
    def test_exclusive_durable_sink_redaction_and_completion(self):
        sink=e.OfflineEvidenceSink(self.temp.name,'mr05-test-'+'a'*16)
        self.assertEqual(sink.status(),'INCOMPLETE_EVIDENCE')
        sink.failure(revision=m.CHAIN[1],code='password=FICTIONAL_SECRET',observed_schema={'tables':['driver_profiles'],'triggers':[],'schema_sha256':'A'*64},original_fingerprint='B'*64,source_fingerprint='C'*64)
        raw=(sink.root/'failure-0001.json').read_text(encoding='utf-8');self.assertNotIn('FICTIONAL_SECRET',raw)
        sink.complete();self.assertEqual(sink.status(),'EVIDENCE_COMPLETE_NOT_MIGRATION_SUCCESS')
        with self.assertRaises(FileExistsError):e.OfflineEvidenceSink(self.temp.name,'mr05-test-'+'a'*16)
        with self.assertRaises(FileExistsError):sink.complete()
    def test_interrupted_evidence_never_claims_completion(self):
        sink=e.OfflineEvidenceSink(self.temp.name,'mr05-test-'+'b'*16)
        (sink.root/'COMPLETE.json').write_text('partial',encoding='utf-8')
        self.assertEqual(sink.status(),'INCOMPLETE_EVIDENCE')
        self.assertTrue((sink.root/'INCOMPLETE.json').exists())
    def test_sink_rejects_unsafe_names_and_raw_observations(self):
        self.fail('INVALID_TEST_EVIDENCE_LABEL',lambda:e.OfflineEvidenceSink(self.temp.name,'../checkpoint'))
        sink=e.OfflineEvidenceSink(self.temp.name,'mr05-test-'+'c'*16)
        self.fail('UNSAFE_FAILURE_OBSERVATION',lambda:sink.failure(revision=m.CHAIN[0],code='DDL_STAGE_FAILED',observed_schema={'rows':['PRIVATE']}))

class AdapterCorrectionTests(f.AdapterTests):
    def test_direct_entry_requires_validated_immutable_evidence(self):
        fake=f.f.FakeAdapter(self.value)
        self.blocked('VALIDATED_EVIDENCE_REQUIRED',lambda:m.execute_prepared(fake,self.value,database=m.TARGET,account=m.ACCOUNT,execute=True,confirmation=m.TARGET,authorization=m.TOKEN))
        self.assertEqual(fake.calls,[])
    def test_forged_and_mutated_evidence_cannot_bypass_generic_adapter(self):
        forged=object.__new__(e.ValidatedEvidence)
        with self.assertRaises(e.EvidenceError):e.revalidate(forged,self.value)
        cap=self.adapter.validated_evidence
        with self.assertRaises(e.EvidenceError):cap._source='0'*64
        object.__setattr__(cap,'_source','0'*64)
        self.blocked('VALIDATED_EVIDENCE_CHANGED',self.run_chain)
        self.assertEqual(self.writer.attempted,[])
    def test_rehashed_backup_must_still_match_independently_approved_manifest(self):
        self.backup.write_bytes(b'CHANGED FICTIONAL BYTES')
        self.blocked('EVIDENCE_BYTES_CHANGED',self.run_chain);self.assertFalse(self.evidence.reserved)
    def test_approved_server_cannot_come_only_from_constructor(self):
        self.source.server_uuid=self.reader.server_uuid='changed-server'
        self.blocked('MR05_APPROVED_SERVER_MISMATCH',self.make_adapter)
    def test_adapter_rejects_stale_or_replayed_gate_evidence(self):
        self.adapter.mock_now=1200
        self.blocked('STALE_DBA_EVIDENCE',lambda:self.adapter.preflight(self.value))
        self.adapter.mock_now=1000;proof=self.adapter.dba_evidence[0]
        self.adapter.dba_evidence.insert(0,proof)
        self.adapter.preflight(self.value)
        self.blocked('REPLAYED_DBA_EVIDENCE',lambda:self.adapter.preflight(self.value))
    def test_coherent_capture_detects_source_update_during_same_count_read(self):
        original=self.source.original_records
        def mixed(manifest):
            result=original(manifest);self.source_port.state['rows']['ledger_entries'][0]['amount']=Decimal('99.99');return result
        with patch.object(self.source,'original_records',side_effect=mixed):
            with self.assertRaises(e.EvidenceError) as error:self.adapter.source_fingerprint()
        self.assertEqual(str(error.exception),'MIXED_TIME_OBSERVATION')
    def test_capture_rejects_replaced_catalog_state(self):
        original=self.source.original_records
        def replaced(manifest):
            result=original(manifest);self.source_port.state=copy.deepcopy(self.source_port.state);return result
        with patch.object(self.source,'original_records',side_effect=replaced):
            self.blocked('MR05_CAPTURE_STATE_REPLACED',self.adapter.source_fingerprint)
    def test_failure_sink_preserves_original_and_source_fingerprints(self):
        self.evidence=a.DurableMockEvidence(self.temp.name,'mr05-test-'+'d'*16);self.adapter=self.make_adapter();self.writer.fail_after_apply=True
        self.blocked('MR03_MOCK_PARTIAL_DDL_FAILURE',self.run_chain)
        sink=self.evidence.sink;self.assertEqual(sink.status(),'INCOMPLETE_EVIDENCE')
        records=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(sink.root.glob('failure-*.json'))]
        self.assertEqual(len(records),2);self.assertEqual(records[-1]['source_fingerprint'],self.value['source_fingerprint'])
        self.assertNotEqual(records[-1]['original_fingerprint'],'UNAVAILABLE')
        self.assertIn('driver_document_audits',records[-1]['observed']['tables'])
        self.assertEqual(self.writer.attempted,[m.CHAIN[1]])

def load_tests(loader,tests,pattern):
    return TestSuite(cls(name) for cls in (ContractTests,AdapterCorrectionTests) for name in cls.__dict__ if name.startswith('test_'))

if __name__=='__main__':main()

"""Fictional signed envelopes and mocks only; no trust anchor or key creation."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(file))
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value
c=load('three_completion_fixture','checkpoint_native_completion_suite.py');a=c.a;n=a.n;p=a.p;s=a.s

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=c.CompletionTests('test_full_integration_issues_only_model_receipt');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups);self.native=self.fixture.f.fixture.fixture
    def verify(self,payload=None):
        with patch.object(n,'_ed25519_verify',return_value=None):
            return self.native.verifier.verify_stdout(p.canonical(payload or self.fixture.stdout_payload),b'\x00'*64,
                value=self.fixture.f.fixture.auth,job=self.native.job,proposal=self.fixture.proposal)
    def test_signed_capability_accepted_and_replay_rejected(self):
        s.validate_authenticated_stdout(self.fixture.f.recipe)
        with self.assertRaises(p.Stop):self.verify()
    def test_unsigned_recipe_and_model_receipt_cannot_authorize(self):
        unsigned=s.bind_stdout_approval(self.fixture.proposal,p.sha(self.fixture.proposal),value=self.fixture.f.fixture.auth,job=self.native.job,base_recipe=self.native.native)
        with self.assertRaises(p.Stop):s.validate_authenticated_stdout(unsigned)
        for fake in (None,object.__new__(s.ModelRunReceipt),object.__new__(n.VerifiedStdoutAuthorization)):
            with self.assertRaises(p.Stop):s.bind_authenticated_stdout(self.fixture.proposal,fake,value=self.fixture.f.fixture.auth,job=self.native.job,base_recipe=self.native.native)
    def test_changed_signed_scope_rejected(self):
        for field,value in (('job_sha256','F'*64),('attempt_id','checkpoint-'+'f'*32),('argv_sha256','E'*64),('dump_path',r'C:\Other\viva.sql'),('proposal_sha256','D'*64),('writer_freeze',False)):
            with self.subTest(field=field),self.assertRaises(p.Stop):self.verify(dict(self.fixture.stdout_payload,nonce='c'*32,**{field:value}))
    def test_stale_stdout_approval_rejected(self):
        self.native.now=201
        with self.assertRaises(p.Stop):s.validate_authenticated_stdout(self.fixture.f.recipe)
    def test_invalid_signature_and_missing_dependency_fail_closed(self):
        with patch.object(n,'_ed25519_verify',side_effect=p.Stop('APPROVAL_SIGNATURE_INVALID')):
            with self.assertRaises(p.Stop):self.native.verifier.verify_stdout(p.canonical(dict(self.fixture.stdout_payload,nonce='c'*32)),b'\x00'*64,value=self.fixture.f.fixture.auth,job=self.native.job,proposal=self.fixture.proposal)
        with patch.dict(sys.modules,{'cryptography.hazmat.primitives.asymmetric.ed25519':None}):
            with self.assertRaisesRegex(p.Stop,'DEPENDENCY_UNAVAILABLE'):n._ed25519_verify(b'0'*32,b'0'*64,b'message')
    def test_missing_signer_rejected(self):
        with self.assertRaises(p.Stop):n.PinnedApprovalVerifier(signer_id='missing',public_key=None,approved_key_sha256=None,replay_store=self.native.store,clock=lambda:110)
    def test_source_post_capture_missing_or_changed_rejected(self):
        with self.assertRaises(p.Stop):n.compare_sealed_source(self.fixture.f.fixture.auth,self.native.job,object())
        self.assertEqual(len(n.compare_sealed_source(self.fixture.f.fixture.auth,self.native.job,self.native.post)),64)
        self.native.now=201
        with self.assertRaises(p.Stop):n.compare_sealed_source(self.fixture.f.fixture.auth,self.native.job,self.native.post)
    def test_model_receipt_and_unissued_native_receipt_rejected(self):
        for run in (object.__new__(s.ModelRunReceipt),object.__new__(n.VerifiedDumpRun)):
            with self.assertRaises(p.Stop):n.bind_stdout_manifest(self.fixture.f.recipe,self.fixture.f.fixture.raw,run=run,after_capture=self.native.post)
        with self.assertRaises(p.Stop):n.issue_stdout_native_receipt()
    def test_stdout_manifest_bridge_with_explicit_fictional_native_receipt(self):
        # No issuer is enabled. Register a fictional receipt only to test bridge
        # scope and manifest binding; this is NOT native execution evidence.
        self.fixture.run_prepared()
        recipe=self.fixture.f.recipe;raw=self.fixture.f.fixture.raw;job=self.native.job
        record=dict(self.fixture.f.binding,backup_sha256=p.sha(raw),backup_size=len(raw),
            baseline_sha256=n.validate_dump_bytes(self.fixture.f.fixture.auth,raw,job=job)['baseline_sha256'],
            post_capture_sha256=n.compare_sealed_source(self.fixture.f.fixture.auth,job,self.native.post),
            exit_code=0,cleanup_complete=True,flush_confirmed=True)
        run=object.__new__(n.VerifiedDumpRun);n._STDOUT_RUNS[id(run)]=(run,record)
        self.addCleanup(n._STDOUT_RUNS.pop,id(run),None)
        args=self.native.manifest_kwargs();args.pop('after_capture');args['consumption']=self.fixture.f.store
        original=self.fixture.f.store._stdout_records
        def substituted(*arguments):
            records=original(*arguments);records['stdout_validated']['result_sha256']='F'*64
            return records
        with patch.object(self.fixture.f.store,'_stdout_records',side_effect=substituted):
            with self.assertRaisesRegex(p.Stop,'STDOUT_DURABLE_RESULT_MISMATCH'):
                n.bind_stdout_manifest(recipe,raw,run=run,after_capture=self.native.post,**args)
        manifest,checksum=n.bind_stdout_manifest(recipe,raw,run=run,after_capture=self.native.post,**args)
        self.assertEqual(p.sha(manifest),checksum)
        import json
        actual=json.loads(manifest)['stdout_v1']
        self.assertEqual(actual['approval_sha256'],recipe.approval_sha256)
        self.assertEqual(actual['argv_sha256'],self.fixture.f.binding['argv_sha256'])
    def test_source_transport_bridge_complete_and_incomplete_capture(self):
        native=c.j.f.base.NativeTests('test_pinned_signer_required');native.setUp()
        self.addCleanup(native.doCleanups)
        uuid='11111111-1111-1111-1111-111111111111'
        native.config['server_uuid']=uuid;native.config_raw=p.canonical(native.config)
        native.payload.update(server_uuid=uuid,configuration_sha256=p.sha(native.config_raw))
        value=native.issue();fixtures=load('three_mr09_fixture','mr09_mysql_adapter_suite.py')
        contract=fixtures.fixture_contract();result=fixtures.observed_results(p.REVISION,p.SOURCE)
        result['identity'][0]['server_uuid']=uuid
        session=n.d.MockMySQLSession(p.SOURCE,p.typed.SOURCE_ACCOUNT,result)
        t=n.transport_policy();binding=t.SourceBinding('127.0.0.1',3306,uuid,p.SOURCE,p.typed.SOURCE_ACCOUNT,'A'*64)
        freeze=dict(source=p.SOURCE,revision=p.REVISION,server_uuid=uuid,observed_at=100,expires_at=200,
                    evidence_id='a'*32,writer_freeze=True,ddl_freeze=True)
        # TLS certificate mechanics are separately reviewed; fixture bytes are
        # never asserted to be a real CA or trusted runtime evidence.
        with patch.object(t,'certificate_context',return_value=object()),patch.object(n.d.c,'build',return_value=contract),patch.object(t.d.c,'build',return_value=contract):
            inventory,cap,metadata,ddl=n.capture_transport_model(value,t.SourceInspectionTransport(),binding,binding,b'FICTIONAL',session,'transport-pre',freeze,lambda:110)
            self.assertEqual(len(inventory['tables']),35);self.assertEqual(len(cap),35)
            self.assertFalse(session.in_snapshot)
            broken=n.d.MockMySQLSession(p.SOURCE,p.typed.SOURCE_ACCOUNT,result)
            broken.results['columns'].pop('orders')
            count=len(p._CAPTURES)
            with self.assertRaises((KeyError,n.d.m.GuardFailure)):
                n.capture_transport_model(value,t.SourceInspectionTransport(),binding,binding,b'FICTIONAL',broken,'transport-incomplete',freeze,lambda:110)
            self.assertEqual(len(p._CAPTURES),count)
    def test_source_gate_failure_prevents_completion_and_receipt(self):
        # Exercise one attempt per test; changed/missing capture semantics are
        # tested separately through the sealed-source comparison above.
        count=len(s._MODEL_RECEIPTS)
        with patch.object(n,'compare_sealed_source',side_effect=p.Stop('SOURCE_PRESERVATION_MISMATCH')):
            with self.assertRaisesRegex(p.Stop,'SOURCE_PRESERVATION_MISMATCH'):self.fixture.run_prepared()
        self.assertEqual(count,len(s._MODEL_RECEIPTS))
        self.assertFalse((self.fixture.f.root/(self.fixture.f.recipe.attempt_id+'.stdout_validated.json')).exists())
        self.assertTrue((self.fixture.f.root/(self.fixture.f.recipe.attempt_id+'.failure.json')).exists())
    def test_changed_issued_recipe_and_substituted_job_rejected(self):
        recipe=self.fixture.f.recipe
        for field,value in (('attempt_id','checkpoint-'+'f'*32),('output_path',r'C:\Other\viva.sql'),('argv',('--host=elsewhere',))):
            old=getattr(recipe,field)
            try:
                object.__setattr__(recipe,field,value)
                with self.assertRaises(p.Stop):s.validate_authenticated_stdout(recipe)
            finally:object.__setattr__(recipe,field,old)
        with self.assertRaises(p.Stop):n.stdout_authorization(self.fixture.stdout_cap,self.fixture.proposal,self.fixture.f.fixture.auth,object())
    def test_transport_scope_mismatch_and_stale_freeze(self):
        from dataclasses import replace
        t=n.transport_policy();uuid='11111111-1111-1111-1111-111111111111'
        binding=t.SourceBinding('127.0.0.1',3306,uuid,p.SOURCE,p.typed.SOURCE_ACCOUNT,'A'*64)
        session=n.d.MockMySQLSession(p.SOURCE,p.typed.SOURCE_ACCOUNT,{})
        for altered in (replace(binding,host='wrong.example'),replace(binding,account='wrong@127.0.0.1'),replace(binding,server_uuid='22222222-2222-2222-2222-222222222222')):
            with self.assertRaises((p.Stop,t.Rejected)):
                n.capture_transport_model(self.fixture.f.fixture.auth,t.SourceInspectionTransport(),altered,altered,b'FAKE',session,'scope-test',{},lambda:110)
        with self.assertRaisesRegex(p.Stop,'CAPTURE_SIGNED_FREEZE_MISMATCH'):
            n.capture_model(self.fixture.f.fixture.auth,session,'stale-freeze',dict(observed_at=1,expires_at=2,evidence_id='bad'),lambda:110)
    def test_transport_rejects_real_or_wrong_identity_without_connection(self):
        t=n.transport_policy();binding=t.SourceBinding('127.0.0.1',3306,'11111111-1111-1111-1111-111111111111',p.SOURCE,p.typed.SOURCE_ACCOUNT,'A'*64)
        with self.assertRaises(p.Stop):n.capture_transport_model(self.fixture.f.fixture.auth,t.SourceInspectionTransport(),binding,binding,b'FAKE',object(),'capture-test',{},lambda:110)
        with self.assertRaises(t.Rejected):t.SourceInspectionTransport().connect()

if __name__=='__main__':unittest.main()

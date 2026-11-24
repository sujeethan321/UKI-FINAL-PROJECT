"""Fictional public-key/DB/dump and Windows-handle models. No live operations.

Signature success is explicitly MOCKED: this suite does not assert cryptographic
verification when the optional reviewed dependency is absent. No keys generated.
"""
import copy
from datetime import datetime
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

spec=importlib.util.spec_from_file_location('native_checkpoint_test',Path(__file__).resolve().parents[1]/'scripts/checkpoint_native.py')
n=importlib.util.module_from_spec(spec);sys.modules[spec.name]=n;spec.loader.exec_module(n);p=n.p
PUBLIC=bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')

class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=p.FilesystemConsumptionStore(Path(self.temp.name));self.attempt='checkpoint-'+uuid4().hex;self.now=110
        guard=patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN'));guard.start();self.addCleanup(guard.stop)
        self.config=dict(endpoint='127.0.0.1',port=3306,server_uuid='fixture-server-uuid',schema=p.SOURCE,account='fixture_backup',
            ca_path=r'C:\Approved\ca.pem',ca_sha256='A'*64,destination=r'C:\Private\fixture',attempt_id=self.attempt)
        self.config_raw=p.canonical(self.config)
        self.payload=dict(signer_id='fictional-dba',configuration_sha256=p.sha(self.config_raw),attempt_id=self.attempt,
            server_uuid='fixture-server-uuid',source=p.SOURCE,source_account=p.typed.SOURCE_ACCOUNT,backup_account='fixture_backup',
            endpoint='127.0.0.1',port=3306,ca_sha256='A'*64,issued_at=100,expires_at=200,nonce='a'*32,writer_freeze=True,ddl_freeze=True)
        self.verifier=n.PinnedApprovalVerifier(signer_id='fictional-dba',public_key=PUBLIC,approved_key_sha256=p.sha(PUBLIC),replay_store=self.store,clock=lambda:self.now)
    def issue(self):
        # Not a real signer/approval. Only test scope/freshness/replay plumbing.
        with patch.object(n,'_ed25519_verify',return_value=None):
            return self.verifier.verify(p.canonical(self.payload),b'\x00'*64,self.config_raw,p.sha(self.config_raw))
    def dump_fixture(self):
        metadata={};rows={};definitions={};tables={};parts=['-- Fictional mysqldump fixture']
        for name in sorted(p.TABLES):
            column='version_num' if name=='alembic_version' else 'id'
            typ='VARCHAR' if name=='alembic_version' else 'BIGINT'
            metadata[name]={'columns':{column:{'type':{'family':typ}}}}
            rows[name]=[{column:p.REVISION if name=='alembic_version' else 1}]
            definitions[name]='CREATE TABLE `'+name+'` (`'+column+'` '+('varchar(32)' if typ=='VARCHAR' else 'bigint')+' NOT NULL)'
            parts.append(definitions[name]+';')
            parts.append('INSERT INTO `'+name+'` VALUES ('+("'"+p.REVISION+"'" if typ=='VARCHAR' else '1')+');')
            tables[name]=dict(p.typed.fingerprint(rows[name],[column]),schema_sha256=p.sha(definitions[name].encode()),columns=[column],
                primary_key=[column],indexes=[],foreign_keys=[],checks=[],engine='InnoDB',column_metadata=metadata[name]['columns'],canonical_metadata=metadata[name])
        parts.append('-- Dump completed on 2026-11-24 00:00:00')
        inventory=dict(database=p.SOURCE,revision=p.REVISION,host='127.0.0.1',port=3306,server_uuid='fixture-server-uuid',object_inventory_complete=True,
            tables=tables,triggers=[],views=[],routines=[],events=[])
        return '\n'.join(parts).encode(),inventory,metadata,definitions
    def bound_fixture(self,auth):
        raw,inventory,metadata,definitions=self.dump_fixture()
        rows={name:[{'version_num':p.REVISION}] if name=='alembic_version' else [{'id':1}] for name in p.TABLES}
        self.freeze=dict(source=p.SOURCE,revision=p.REVISION,server_uuid='fixture-server-uuid',observed_at=100,expires_at=200,
            evidence_id='a'*32,writer_freeze=True,ddl_freeze=True)
        snapshot=dict(owner='dump-pre-capture',capture_owner='dump-pre-capture',isolation='REPEATABLE READ',read_only=True,consistent_snapshot=True,started_at=105,finished_at=106)
        self.pre=p.capture_fingerprints(inventory,rows,snapshot,self.freeze,110,'fixture-server-uuid',attempt_id=self.attempt)
        n._seal_dump_capture(self.pre,inventory,metadata,definitions)
        sid='S-1-5-21-1-2-3-1001';path=self.config['destination']
        obs=dict(outside_public_roots=True,reparse_ancestors_clear=True,destination_absent=True,outputs_absent=True,output_reparse_clear=True,
            owner=sid,protected=True,rules={sid:'FullControl:ContainerInherit,ObjectInherit','S-1-5-18':'FullControl:ContainerInherit,ObjectInherit'})
        directory,self.destination=n.x.directory_recipe(self.attempt,path,path,obs,sid)
        self.native=n.authorized_recipe(auth,self.destination)
        approval=dict(source=p.SOURCE,revision=p.REVISION,endpoint='127.0.0.1',port=3306,server_uuid='fixture-server-uuid',backup_account='fixture_backup',ca_sha256='A'*64,attempt_id=self.attempt)
        observed=dict(approval,observed_at=100,expires_at=200,**dict.fromkeys(('tls_chain_verified','san_only_verified','backup_grants_verified','writer_freeze','ddl_freeze','no_unexplained_writers','capacity_verified','private_console','complete_inventory_verified','innoDB_only'),True))
        self.jobstore=p.OfflineConsumptionStore()
        self.job=n.x.reserve_prelaunch(self.jobstore,directory,self.native,approval,observed,110,before_capture=self.pre,inventory=inventory,expected_post_capture_id='dump-post-capture')
        self.post=p.capture_fingerprints(inventory,rows,dict(snapshot,owner='dump-post-capture',capture_owner='dump-post-capture',started_at=112,finished_at=113),self.freeze,114,'fixture-server-uuid',attempt_id=self.attempt)
        n._seal_dump_capture(self.post,inventory,metadata,definitions)
        self.now=115
        return raw,inventory,metadata,definitions
    def fictional_run(self,raw,job=None):
        # Test-only native receipt fixture. Production receipt issuer stays absent.
        job=job or self.job
        _,_,_,_,job_hash,baseline_hash=n._job_baseline(self.auth,job)
        run=object.__new__(n.VerifiedDumpRun)
        n._DUMP_RUNS[id(run)]=(run,self.attempt,self.native.argv_sha256,p.sha(raw),0,job_hash,baseline_hash)
        return run
    def manifest_kwargs(self):
        return dict(attempt_id=self.attempt,approved_uuid='fixture-server-uuid',destination=self.destination,
            dump=r'C:\Private\fixture\viva.sql',consumption=self.jobstore,after_capture=self.post,now=115,freeze_evidence_id='a'*32)
    def test_pinned_signer_required(self):
        with self.assertRaises(p.Stop):n.PinnedApprovalVerifier(signer_id='fictional-dba',public_key=PUBLIC,approved_key_sha256='0'*64,replay_store=self.store,clock=lambda:110)
    def test_mocked_signature_scope_then_expiry(self):
        auth=self.issue();self.assertEqual(n.authorization(auth)[0]['attempt_id'],self.attempt)
        self.now=200
        with self.assertRaises(p.Stop):n.authorization(auth)
    def test_signature_failure_redacted(self):
        with patch.object(n,'_ed25519_verify',side_effect=p.Stop('APPROVAL_SIGNATURE_INVALID')):
            with self.assertRaisesRegex(p.Stop,'SIGNATURE_INVALID'):self.verifier.verify(p.canonical(self.payload),b'\x00'*64,self.config_raw,p.sha(self.config_raw))
    def test_dependency_unavailable_fails_closed(self):
        original=__import__
        def missing(name,*args,**kwargs):
            if name.startswith('cryptography'):raise ImportError('fictional missing dependency')
            return original(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=missing),self.assertRaisesRegex(p.Stop,'DEPENDENCY_UNAVAILABLE'):
            n._ed25519_verify(PUBLIC,b'\x00'*64,b'fixture')
    def test_replay_across_new_verifier_instances(self):
        self.issue()
        self.verifier=n.PinnedApprovalVerifier(signer_id='fictional-dba',public_key=PUBLIC,approved_key_sha256=p.sha(PUBLIC),replay_store=p.FilesystemConsumptionStore(Path(self.temp.name)),clock=lambda:110)
        with self.assertRaises(p.Stop):self.issue()
    def test_signed_configuration_and_account_substitutions(self):
        for key,value in [('configuration_sha256','B'*64),('source_account','root@localhost'),('server_uuid','wrong'),('writer_freeze',False),('expires_at',110)]:
            old=self.payload[key];self.payload[key]=value
            with self.assertRaises(p.Stop):self.issue()
            self.payload[key]=old
    def test_windows_handle_negative_models(self):
        facts=dict(final_path=r'C:\Private\fixture',owner_sid='operator',reparse=False,delete_shared=False,hard_links=1,directory=True,dacl_protected=True,
            aces=[('operator','ALLOW','FULL_CONTROL'),('S-1-5-18','ALLOW','FULL_CONTROL')])
        n.validate_windows_handle_facts(facts,expected_path=r'C:\Private\fixture',operator_sid='operator',directory=True)
        for field,value in [('reparse',True),('delete_shared',True),('hard_links',2),('dacl_protected',False),('aces',[]),('final_path',r'C:\Public')]:
            with self.assertRaises(p.Stop):n.validate_windows_handle_facts(dict(facts,**{field:value}),expected_path=r'C:\Private\fixture',operator_sid='operator',directory=True)
    def test_native_and_process_blockers(self):
        with patch('subprocess.Popen',side_effect=AssertionError('NO_NATIVE_PROCESS')) as spawn:
            for operation in (lambda:n.WindowsNativeCheckpoint().create_directory(None,None),lambda:n.WindowsNativeCheckpoint().create_file(None,None),
                lambda:n.WindowsNativeCheckpoint().flush_directory(),lambda:n.NativeDumpRunner().run(None,None),lambda:n.NativeDumpRunner().capture_real_mysql(),lambda:n.NativeDumpRunner().execute_backup()):
                with self.assertRaises(p.Stop):operation()
            spawn.assert_not_called()
    def test_valid_dump_all_tables_schema_content_hash(self):
        auth=self.issue();raw,inventory,metadata,definitions=self.bound_fixture(auth)
        report=n.validate_dump_bytes(auth,raw,job=self.job)
        self.assertEqual(report['backup_sha256'],p.sha(raw));self.assertEqual(len(report['tables']),35)
    def test_dump_row_schema_and_object_changes_rejected(self):
        auth=self.issue();raw,inventory,metadata,definitions=self.bound_fixture(auth)
        variants=[raw.replace(b'INSERT INTO `ledger_entries` VALUES (1)',b'INSERT INTO `ledger_entries` VALUES (2)'),
            raw.replace(b'`orders` (`id` bigint',b'`orders` (`id` int'),raw.replace(b'-- Dump completed',b'-- Missing footer'),
            raw.replace(b'-- Dump completed',b"/*!50003 CREATE TRIGGER danger BEFORE DELETE ON orders FOR EACH ROW SIGNAL SQLSTATE '45000' */;\n-- Dump completed"),
            raw.replace(b'-- Dump completed',b'CREATE EVENT danger ON SCHEDULE EVERY 1 DAY DO DELETE FROM orders;\n-- Dump completed'),
            raw.replace(b'-- Dump completed',b'USE lankapex_viva_db;\n-- Dump completed')]
        for changed in variants:
            with self.assertRaises(n.dump_inspection.DumpRejected) as error:n.validate_dump_bytes(auth,changed,job=self.job)
            self.assertNotIn('ledger_entries',str(error.exception))
    def test_dump_bounds_and_no_fake_run_receipt(self):
        auth=self.issue();raw,inventory,metadata,definitions=self.bound_fixture(auth)
        with patch.object(n.dump_inspection,'MAX_BYTES',1),self.assertRaises(n.dump_inspection.DumpRejected):n.validate_dump_bytes(auth,raw,job=self.job)
        with patch.object(n.dump_inspection,'MAX_TOKENS',2),self.assertRaises(n.dump_inspection.DumpRejected):n.validate_dump_bytes(auth,raw,job=self.job)
        with self.assertRaisesRegex(p.Stop,'VERIFIED_NATIVE_DUMP_RUN'):n.bind_dump_to_manifest(auth,raw,job=self.job)
    def test_sql_literal_semicolon_is_data_not_sql(self):
        text="INSERT INTO `sample` VALUES ('a; DROP TABLE orders; \\' quote');"
        tokens=n.dump_inspection.tokens(text)
        self.assertEqual(sum(t==('punct',';') for t in tokens),1)
    def test_real_capture_transport_rejected(self):
        auth=self.issue();freeze=dict(observed_at=100,expires_at=200,evidence_id='a'*32)
        with self.assertRaisesRegex(p.Stop,'REAL_CAPTURE_TRANSPORT_DISABLED'):n.capture_model(auth,object(),'capture-model',freeze,lambda:110)
    def test_coherent_capture_model_all_35_and_mutation_no_capability(self):
        # Reuse reviewed fictional MR-09 raw metadata; no test setup/DB invoked.
        fixture_path=Path(__file__).with_name('mr09_mysql_adapter_suite.py')
        fs=importlib.util.spec_from_file_location('native_mr09_fixture',fixture_path)
        fixtures=importlib.util.module_from_spec(fs);sys.modules[fs.name]=fixtures;fs.loader.exec_module(fixtures)
        contract=fixtures.fixture_contract()
        result=fixtures.observed_results(p.REVISION,p.SOURCE)
        session=n.d.MockMySQLSession(p.SOURCE,p.typed.SOURCE_ACCOUNT,result)
        auth=self.issue();freeze=dict(source=p.SOURCE,revision=p.REVISION,server_uuid='fixture-server-uuid',observed_at=100,expires_at=200,
            evidence_id='a'*32,writer_freeze=True,ddl_freeze=True)
        with patch.object(n.d.c,'build',return_value=contract):
            inventory,capture,metadata,definitions=n.capture_model(auth,session,'native-pre-capture',freeze,lambda:110)
            self.assertEqual(len(inventory['tables']),35);self.assertEqual(len(capture),35)
            self.assertEqual(set(metadata),set(definitions))
            self.assertFalse(session.in_snapshot)
            before=len(p._CAPTURES);original=n.d.MySQLInspector.table
            def mutate(inspector,name,expected):
                value=original(inspector,name,expected)
                if name=='orders':session.results['rows']['ledger_entries'][0]['id']=2
                return value
            with patch.object(n.d.MySQLInspector,'table',mutate),self.assertRaises(n.d.m.GuardFailure):
                n.capture_model(auth,session,'native-post-capture',freeze,lambda:110)
            self.assertEqual(len(p._CAPTURES),before)
    def test_typed_dump_literals(self):
        literal=n.dump_inspection.literal
        self.assertEqual(literal(('atom','10.50'),{'type':{'family':'DECIMAL'}}),Decimal('10.50'))
        self.assertEqual(literal(('atom','0x00ff'),{'type':{'family':'BLOB'}}),b'\x00\xff')
        self.assertEqual(literal(('string','2026-11-24 01:02:03.123456'),{'type':{'family':'DATETIME'}}),datetime(2026,11,24,1,2,3,123456))
    def test_validation_rejects_replacement_baseline_fields(self):
        auth=self.issue();raw,inventory,metadata,definitions=self.bound_fixture(auth)
        for field,value in [('inventory',inventory),('metadata',metadata),('definitions',definitions),('row_fingerprints',{})]:
            with self.assertRaisesRegex(p.Stop,'CALLER_DUMP_BASELINE_REJECTED'):
                n.validate_dump_bytes(auth,raw,job=self.job,**{field:value})
        with self.assertRaises(p.Stop):n.validate_dump_bytes(auth,raw)
        with self.assertRaises(n.dump_inspection.DumpRejected):n.dump_inspection.inspect_bytes(raw,{},p)
    def test_matching_caller_generated_definition_hash_not_authoritative(self):
        auth=self.issue();raw,inventory,metadata,definitions=self.bound_fixture(auth)
        original=definitions['orders'];altered=original.replace('bigint','int')
        definitions['orders']=altered;inventory['tables']['orders']['schema_sha256']=p.sha(altered.encode())
        metadata['orders']['columns']['id']['type']['family']='INT'
        with self.assertRaises(n.dump_inspection.DumpRejected):n.validate_dump_bytes(auth,raw.replace(original.encode(),altered.encode()),job=self.job)
        # Mutating caller-owned dictionaries cannot change the sealed expectations.
        self.assertTrue(n.validate_dump_bytes(auth,raw,job=self.job)['complete'])
    def test_missing_extra_tables_and_altered_row_fingerprints_rejected(self):
        auth=self.issue();raw,inventory,metadata,definitions=self.bound_fixture(auth)
        variants=[raw.replace((definitions['orders']+';\n').encode(),b'').replace(b'INSERT INTO `orders` VALUES (1);\n',b''),
            raw.replace(b'-- Dump completed',b'CREATE TABLE `extra` (`id` bigint);\n-- Dump completed'),
            raw.replace(b'INSERT INTO `orders` VALUES (1)',b'INSERT INTO `orders` VALUES (2)')]
        inventory['tables']['orders']['content_sha256']=p.typed.fingerprint([{'id':2}],['id'])['content_sha256']
        for changed in variants:
            with self.assertRaises(n.dump_inspection.DumpRejected):n.validate_dump_bytes(auth,changed,job=self.job)
    def test_baseline_issuer_rejects_metadata_definition_and_fingerprint_mismatch(self):
        auth=self.issue();_,inventory,metadata,definitions=self.bound_fixture(auth)
        for variant in ('metadata','definition','fingerprint','missing','extra'):
            inv=copy.deepcopy(inventory);meta=copy.deepcopy(metadata);defs=copy.deepcopy(definitions)
            if variant=='metadata':meta['orders']['columns']['id']['type']['family']='INT'
            elif variant=='definition':defs['orders']=defs['orders'].replace('bigint','int')
            elif variant=='fingerprint':inv['tables']['orders']['content_sha256']='F'*64
            elif variant=='missing':defs.pop('orders')
            else:meta['extra']={}
            with self.assertRaises(n.dump_inspection.DumpRejected):n._seal_dump_capture(self.pre,inv,meta,defs)
    def test_same_attempt_unissued_job_and_expired_capture_rejected(self):
        auth=self.issue();raw,_,_,_=self.bound_fixture(auth)
        for forged in ({},object.__new__(p.ReservedJob)):
            with self.assertRaises(p.Stop):n.validate_dump_bytes(auth,raw,job=forged)
        # A current job cannot be detached from its issued exact pre-capture.
        original=p._JOBS[id(self.job)]
        fake=object.__new__(p.ReservedJob)
        p._JOBS[id(fake)]=(fake,original[1],original[2],original[3],object.__new__(p.ValidatedCapture))
        with self.assertRaises(p.Stop):n.validate_dump_bytes(auth,raw,job=fake)
        self.now=200
        with self.assertRaises(p.Stop):n.validate_dump_bytes(auth,raw,job=self.job)
    def test_valid_and_trailing_comma_insert_column_lists(self):
        auth=self.issue();raw,_,_,_=self.bound_fixture(auth)
        source=b'INSERT INTO `orders` VALUES (1)'
        valid=raw.replace(source,b'INSERT INTO `orders` (`id`) VALUES (1)')
        self.assertTrue(n.validate_dump_bytes(auth,valid,job=self.job)['complete'])
        for columns in (b'(`id`,)',b'(,`id`)',b'(`id`,,`id`)',b'(`id`,123)',b'(`id`,VALUES)'):
            with self.assertRaises(n.dump_inspection.DumpRejected):
                n.validate_dump_bytes(auth,raw.replace(source,b'INSERT INTO `orders` '+columns+b' VALUES (1)'),job=self.job)
    def test_dump_result_and_manifest_bound_to_exact_job_and_bytes(self):
        self.auth=auth=self.issue();raw,_,_,_=self.bound_fixture(auth)
        report=n.validate_dump_bytes(auth,raw,job=self.job)
        self.assertEqual(report['attempt_id'],self.attempt)
        self.assertEqual(report['job_sha256'],p.sha(p._JOBS[id(self.job)][2]))
        run=self.fictional_run(raw)
        # A syntactically valid receipt for another job is not interchangeable.
        saved=n._DUMP_RUNS[id(run)]
        n._DUMP_RUNS[id(run)]=(*saved[:5],'F'*64,saved[6])
        with self.assertRaisesRegex(p.Stop,'NATIVE_RUN_JOB_RECIPE_MISMATCH'):
            n.bind_dump_to_manifest(auth,raw,job=self.job,run=run,**self.manifest_kwargs())
        n._DUMP_RUNS[id(run)]=saved
        with self.assertRaisesRegex(p.Stop,'CALLER_DUMP_BASELINE_OR_RESULT_REJECTED'):
            n.bind_dump_to_manifest(auth,raw,job=self.job,run=run,before={},**self.manifest_kwargs())
        manifest,checksum=n.bind_dump_to_manifest(auth,raw,job=self.job,run=run,**self.manifest_kwargs())
        result=json.loads(manifest)
        self.assertEqual(result['backup_sha256'],p.sha(raw));self.assertEqual(result['job_sha256'],report['job_sha256'])
        self.assertEqual(p.sha(manifest),checksum)
        with self.assertRaises(p.Stop):n.bind_dump_to_manifest(auth,raw,job=self.job,run=run,**self.manifest_kwargs())

if __name__=='__main__':unittest.main()

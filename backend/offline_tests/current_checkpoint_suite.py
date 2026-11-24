"""Fictional 35-table inventory and row streams; no database or checkpoint I/O."""
import copy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import unittest
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('current_checkpoint',Path(__file__).resolve().parents[1]/'scripts/current_checkpoint_plan.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
import sys
sys.modules['_lankapex_current_checkpoint_plan']=p
xs=importlib.util.spec_from_file_location('checkpoint_binding_test_prepare',Path(__file__).resolve().parents[1]/'scripts/checkpoint_execution_prepare.py')
x=importlib.util.module_from_spec(xs);sys.modules[xs.name]=x;xs.loader.exec_module(x)

class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self._captures=None;self._attemptargs=None
        self.attempt="checkpoint-"+uuid4().hex
        self.consumption=p.OfflineConsumptionStore()
        guard=patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK'));guard.start();self.addCleanup(guard.stop)
        self.rows={name:[{'id':1,'amount':Decimal('10.50'),'note':None,'binary':b'\x00\xff'}] for name in p.TABLES}
        self.rows['alembic_version']=[{'version_num':p.REVISION}]
        tables={}
        for name,rows in self.rows.items():
            columns=list(rows[0]);tables[name]=dict(p.typed.fingerprint(rows,columns),columns=columns,
                schema_sha256='A'*64,primary_key=[columns[0]],indexes=[],foreign_keys=[],checks=[],engine='InnoDB')
        self.inventory=dict(database=p.SOURCE,revision=p.REVISION,host='127.0.0.1',port=3306,server_uuid='fictional-uuid',
            object_inventory_complete=True,tables=tables,triggers=[],views=[],routines=[],events=[])
        self.snapshot=dict(isolation='REPEATABLE READ',read_only=True,consistent_snapshot=True,owner='capture-1',capture_owner='capture-1',started_at=100,finished_at=110)
        self.freeze=dict(source=p.SOURCE,revision=p.REVISION,server_uuid='fictional-uuid',evidence_id='fictional-freeze',writer_freeze=True,ddl_freeze=True,observed_at=99,expires_at=120)
    def capture(self):return p.capture_fingerprints(self.inventory,self.rows,self.snapshot,self.freeze,111,'fictional-uuid',attempt_id=self.attempt)
    def test_complete_capture_all_35(self):
        self.assertEqual(len(self.capture()),35)
    def test_wrong_source_revision_and_uuid(self):
        for key,value in [('database','lankapex_db'),('revision','9d1a6f4e0c37'),('server_uuid','wrong')]:
            saved=self.inventory[key];self.inventory[key]=value
            with self.assertRaises((p.Stop,ValueError)):self.capture()
            self.inventory[key]=saved
    def test_missing_extra_table_and_trigger(self):
        original=copy.deepcopy(self.inventory)
        self.inventory['tables'].pop('orders')
        with self.assertRaises(ValueError):self.capture()
        self.inventory=copy.deepcopy(original);self.inventory['tables']['unexpected']=copy.deepcopy(self.inventory['tables']['orders'])
        with self.assertRaises(ValueError):self.capture()
        self.inventory=original;self.inventory['triggers']=[{'name':'unexpected'}]
        with self.assertRaises(ValueError):self.capture()
    def test_non_innodb_rejected(self):
        self.inventory['tables']['orders']['engine']='MyISAM'
        with self.assertRaises(p.Stop):self.capture()
    def test_content_mutation_same_count(self):
        self.rows['ledger_entries'][0]['amount']=Decimal('10.51')
        with self.assertRaises(p.Stop):self.capture()
    def test_missing_or_extra_row_columns(self):
        self.rows['users'][0]['unapproved']='private'
        with self.assertRaises(p.Stop):self.capture()
    def test_truncated_rows_rejected(self):
        self.rows['orders']=iter([])
        with self.assertRaises(p.Stop):self.capture()
    def test_row_limit_fails_never_truncates(self):
        with patch.object(p.typed,'MAX_ROWS',0),self.assertRaises(p.Stop):self.capture()
        # An unexpected stream overflow also fails even if inventory claims fewer rows.
        self.rows['orders']=iter([self.rows['orders'][0]]*2)
        with patch.object(p.typed,'MAX_ROWS',1),self.assertRaises(p.typed.m.GuardFailure):self.capture()
    def test_actual_revision_row(self):
        self.rows['alembic_version']=[{'version_num':'9d1a6f4e0c37'}]
        with self.assertRaises(p.Stop):self.capture()
    def test_snapshot_and_freeze(self):
        for key,value in [('read_only',False),('isolation','READ COMMITTED'),('capture_owner','other'),('finished_at',140)]:
            old=self.snapshot[key];self.snapshot[key]=value
            with self.assertRaises(p.Stop):self.capture()
            self.snapshot[key]=old
        self.freeze['expires_at']=110
        with self.assertRaises(p.Stop):self.capture()
    def test_private_destination(self):
        sid='S-1-5-21-1-2-3-1001';path=r'C:\Private\checkpoint-new'
        observed=dict(outside_public_roots=True,reparse_ancestors_clear=True,destination_absent=True,outputs_absent=True,output_reparse_clear=True,owner=sid,protected=True,
            rules={sid:'FullControl:ContainerInherit,ObjectInherit','S-1-5-18':'FullControl:ContainerInherit,ObjectInherit'})
        self.assertIsInstance(p.destination_policy(path,path,observed,sid,attempt_id=self.attempt),p.ValidatedDestination)
        for key in ('outside_public_roots','reparse_ancestors_clear','destination_absent','protected'):
            changed=dict(observed,**{key:False})
            with self.assertRaises(p.Stop):p.destination_policy(path,path,changed,sid,attempt_id=self.attempt)
        with self.assertRaises(p.Stop):p.destination_policy(str(p.ROOT/'backup'),str(p.ROOT/'backup'),observed,sid,attempt_id=self.attempt)
    def test_dump_command_is_trigger_aware_and_tls_verified(self):
        args=p.dump_arguments(endpoint='127.0.0.1',approved_endpoint='127.0.0.1',port=3306,approved_port=3306,
            ca_path=r'C:\Approved\ca.pem',ca_sha256='A'*64,approved_ca_sha256='A'*64,user='fictional_backup',dump=r'C:\Private\new\viva.sql',destination=self.destination(),attempt_id=self.attempt)
        for flag in ('--triggers','--routines','--events','--single-transaction','--ssl-mode=VERIFY_IDENTITY','--password'):self.assertIn(flag,args)
        self.assertEqual(args[-1],p.SOURCE);self.assertNotIn('--databases',args);self.assertNotIn('--skip-triggers',args)
    def destination(self,path=r'C:\Private\new'):
        sid='S-1-5-21-1-2-3-1001'
        observed=dict(outside_public_roots=True,reparse_ancestors_clear=True,destination_absent=True,outputs_absent=True,output_reparse_clear=True,
            owner=sid,protected=True,rules={sid:'FullControl:ContainerInherit,ObjectInherit','S-1-5-18':'FullControl:ContainerInherit,ObjectInherit'})
        return p.destination_policy(path,path,observed,sid,attempt_id=self.attempt)
    def captures(self):
        if self._captures is not None:return dict(self._captures)
        pre=self.capture()
        evidence=dict(self.snapshot,owner='capture-2',capture_owner='capture-2',started_at=112,finished_at=114)
        post=p.capture_fingerprints(self.inventory,self.rows,evidence,self.freeze,115,'fictional-uuid',attempt_id=self.attempt)
        self._captures=dict(before_capture=pre,after_capture=post,now=115)
        return dict(self._captures)
    def manifest(self,after=None):
        return p.prepare_manifest(self.inventory,after or self.inventory,approved_uuid='fictional-uuid',dump_sha256='B'*64,dump_size=100,dump_exit_code=0,
            dump_inventory=dict(tables=sorted(p.TABLES),triggers=[],views=[],routines=[],events=[]),completion_verified=True,freeze_evidence_id='fictional-freeze',**self.captures(),**self.attempt_args())
    def test_manifest_hash_and_no_restore_claim(self):
        raw,digest=self.manifest();self.assertEqual(p.sha(raw),digest)
        self.assertEqual(json.loads(raw)['recovery_verification'],'NOT_EXECUTED')
    def test_dump_failure_and_unexpected_dump_inventory(self):
        kwargs=dict(approved_uuid='fictional-uuid',dump_sha256='B'*64,dump_size=100,dump_exit_code=0,
            dump_inventory=dict(tables=sorted(p.TABLES),triggers=[],views=[],routines=[],events=[]),completion_verified=True,freeze_evidence_id='fictional-freeze',**self.captures(),**self.attempt_args())
        for key,value in [('dump_exit_code',1),('dump_size',0),('completion_verified',False),('dump_inventory',{})]:
            with self.assertRaises(p.Stop):p.prepare_manifest(self.inventory,self.inventory,**dict(kwargs,**{key:value}))
    def test_dump_binding_mismatches(self):
        kwargs=dict(endpoint='127.0.0.1',approved_endpoint='127.0.0.1',port=3306,approved_port=3306,
            ca_path=r'C:\Approved\ca.pem',ca_sha256='A'*64,approved_ca_sha256='A'*64,user='fictional_backup',dump=r'C:\Private\new\viva.sql',destination=self.destination(),attempt_id=self.attempt)
        for key,value in [('endpoint','other'),('ca_sha256','B'*64),('user','bad --password=secret')]:
            with self.assertRaises(p.Stop):p.dump_arguments(**dict(kwargs,**{key:value}))
    def test_preservation_schema_or_content_change_blocks_manifest(self):
        changed=copy.deepcopy(self.inventory);changed['tables']['ledger_entries']['content_sha256']='C'*64
        with self.assertRaises(p.Stop):self.manifest(changed)
    def test_independent_known_answer_hashes(self):
        # Constants calculated separately from literal typed-row JSON bytes using
        # SHA256(prefix || uint64_count || sorted(SHA256(row_bytes))). No typed
        # serializer or checkpoint implementation was used to derive them.
        cols=['id','amount','note','binary']
        rows=[dict(id=1,amount=Decimal('10.500'),note=None,binary=b'\x00\xff'),
              dict(id=2,amount=Decimal('-0.00'),note='hello',binary=b'')]
        self.assertEqual(p.typed.fingerprint([],cols)['content_sha256'],'033BF966B6CD1B5D029D314D37C37E52A41B13F10A9DA2E42A42295AAA1659EE')
        self.assertEqual(p.typed.fingerprint(rows[::-1],cols)['content_sha256'],'2B82AE7BA1F372AEFAA08D2E008CC72F0022CBCA4F3991A36BD059659B4860AE')
        self.assertEqual(p.typed.fingerprint(rows+[rows[0]],cols)['content_sha256'],'7019FFA71DACF90CD7DE9683A88E3AD8CC09C3FFAF2CE1C63E039AEE5146E8F0')
    def attempt_args(self):
        if self._attemptargs is not None:return dict(self._attemptargs)
        captures=self.captures();destination=self.destination();path=p._DESTINATIONS[id(destination)][1]
        config=dict(endpoint='127.0.0.1',port=3306,server_uuid='fictional-uuid',schema=p.SOURCE,account='fictional_backup',
            ca_path=r'C:\Approved\ca.pem',ca_sha256='A'*64,destination=path,attempt_id=self.attempt)
        raw=p.canonical(config);approved=x.bind_approved_configuration(raw,p.sha(raw),destination)
        native=x.native_recipe(configuration=approved)
        sid='S-1-5-21-1-2-3-1001';directory=x.WindowsDirectoryRecipe(self.attempt,path,sid,'O:'+sid+'G:'+sid+'D:P(A;OICI;FA;;;'+sid+')(A;OICI;FA;;;SY)')
        approval=dict(source=p.SOURCE,revision=p.REVISION,endpoint='127.0.0.1',port=3306,server_uuid='fictional-uuid',backup_account='fictional_backup',ca_sha256='A'*64,attempt_id=self.attempt)
        observed=dict(approval,observed_at=99,expires_at=120,**dict.fromkeys(('tls_chain_verified','san_only_verified','backup_grants_verified','writer_freeze','ddl_freeze','no_unexplained_writers','capacity_verified','private_console','complete_inventory_verified','innoDB_only'),True))
        job=x.reserve_prelaunch(self.consumption,directory,native,approval,observed,111,before_capture=captures['before_capture'],inventory=self.inventory,expected_post_capture_id='capture-2')
        self._attemptargs=dict(attempt_id=self.attempt,destination=destination,dump=str(p.PureWindowsPath(path)/'viva.sql'),consumption=self.consumption,job=job)
        return dict(self._attemptargs)
    def manifest_args(self):
        return dict(approved_uuid='fictional-uuid',dump_sha256='B'*64,dump_size=100,dump_exit_code=0,
            dump_inventory=dict(tables=sorted(p.TABLES),triggers=[],views=[],routines=[],events=[]),completion_verified=True,freeze_evidence_id='fictional-freeze',**self.attempt_args())
    def test_direct_manifest_entry_missing_and_forged_capture(self):
        for values in ({'now':115},{'now':115,'before_capture':{},'after_capture':{}}):
            with self.assertRaises(p.Stop):p.prepare_manifest(self.inventory,self.inventory,**self.manifest_args(),**values)
        with self.assertRaises(p.Stop):p.ValidatedCapture()
        fake=object.__new__(p.ValidatedCapture)
        with self.assertRaises(p.Stop):p.capture_record(fake,self.inventory,'fictional-uuid',115)
    def test_expired_reused_and_wrong_inventory_capture(self):
        captures=self.captures()
        for changed in (dict(captures,now=120),dict(captures,after_capture=captures['before_capture'])):
            with self.assertRaises(p.Stop):p.prepare_manifest(self.inventory,self.inventory,**self.manifest_args(),**changed)
        altered=copy.deepcopy(self.inventory);altered['tables']['orders']['columns'].reverse()
        with self.assertRaises(p.Stop):p.prepare_manifest(altered,altered,**self.manifest_args(),**captures)
    def test_incomplete_stream_never_issues_capture(self):
        count=len(p._CAPTURES);self.rows.pop('users')
        with self.assertRaises(p.Stop):self.capture()
        self.assertEqual(len(p._CAPTURES),count)
    def test_capture_evidence_cannot_be_changed_after_issuance(self):
        captures=self.captures();self.snapshot['owner']='tampered'
        # Issuance retains immutable serialized evidence, not caller aliases.
        raw,_=p.prepare_manifest(self.inventory,self.inventory,**self.manifest_args(),**captures)
        self.assertEqual(json.loads(raw)['before_capture_id'],'capture-1')
    def test_output_substitution_and_ambiguous_windows_paths(self):
        kwargs=dict(endpoint='127.0.0.1',approved_endpoint='127.0.0.1',port=3306,approved_port=3306,
            ca_path=r'C:\Approved\ca.pem',ca_sha256='A'*64,approved_ca_sha256='A'*64,user='fictional_backup',destination=self.destination(),attempt_id=self.attempt)
        for value in (r'C:\Other\viva.sql',r'C:\Private\new\..\viva.sql',r'C:\Private\new\viva.sql:stream',
                      r'C:\Private\new\wrong.sql',r'C:Private\new\viva.sql',r'\\?\C:\Private\new\viva.sql',
                      'C:/Private/new/viva.sql',r'C:\Private\new\viva.sql.',r'C:\Private\new\NUL',
                      r'C:\Private\new\.\viva.sql',r'C:\Private\new\\viva.sql',
                      r'\\server\share\viva.sql',r'C:\PRIVAT~1\new\viva.sql','C:\\Private\\new\\viva.sql '):
            with self.subTest(path=value),self.assertRaises(p.Stop):p.dump_arguments(dump=value,**kwargs)
        with self.assertRaises(p.Stop):p.dump_arguments(dump=r'C:\Private\new\viva.sql',**dict(kwargs,destination=None))
    def test_conflicting_outputs_and_reparse_observations(self):
        sid='S-1-5-21-1-2-3-1001';path=r'C:\Private\new'
        observed=dict(outside_public_roots=True,reparse_ancestors_clear=True,destination_absent=True,outputs_absent=True,output_reparse_clear=True,
            owner=sid,protected=True,rules={sid:'FullControl:ContainerInherit,ObjectInherit','S-1-5-18':'FullControl:ContainerInherit,ObjectInherit'})
        for key in ('outputs_absent','output_reparse_clear','reparse_ancestors_clear'):
            with self.assertRaises(p.Stop):p.destination_policy(path,path,dict(observed,**{key:False}),sid,attempt_id=self.attempt)
    def test_first_use_then_different_dump_details_rejected(self):
        captures=self.captures();kwargs=dict(self.manifest_args(),**captures)
        raw,_=p.prepare_manifest(self.inventory,self.inventory,**kwargs)
        self.assertEqual(json.loads(raw)['attempt_id'],self.attempt)
        kwargs['dump_sha256']='D'*64
        with self.assertRaisesRegex(p.Stop,'ALREADY_RESERVED'):p.prepare_manifest(self.inventory,self.inventory,**kwargs)
    def test_cross_attempt_capture_and_destination_reuse(self):
        captures=self.captures();kwargs=dict(self.manifest_args(),**captures)
        kwargs['attempt_id']='checkpoint-'+uuid4().hex
        with self.assertRaisesRegex(p.Stop,'DESTINATION_ATTEMPT_MISMATCH'):p.prepare_manifest(self.inventory,self.inventory,**kwargs)
        kwargs['destination']=self.destination_for_attempt(kwargs['attempt_id'])
        with self.assertRaisesRegex(p.Stop,'CAPTURE_ATTEMPT_MISMATCH'):p.prepare_manifest(self.inventory,self.inventory,**kwargs)
    def destination_for_attempt(self,attempt):
        original=self.attempt
        try:self.attempt=attempt;return self.destination()
        finally:self.attempt=original
    def test_concurrent_store_clients_only_one_manifest_wins(self):
        captures=self.captures();kwargs=dict(self.manifest_args(),**captures)
        def run():
            try:
                p.prepare_manifest(self.inventory,self.inventory,**kwargs);return 'PASS'
            except p.Stop:return 'STOP'
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:run(),range(2)))
        self.assertEqual(sorted(results),['PASS','STOP'])
    def test_interrupted_reservation_survives_simulated_client_restart(self):
        captures=self.captures();kwargs=dict(self.manifest_args(),**captures)
        self.consumption.interrupt_after_reserve=True
        with self.assertRaisesRegex(p.Stop,'INTERRUPTED'):p.prepare_manifest(self.inventory,self.inventory,**kwargs)
        kwargs['consumption']=p.OfflineConsumptionStore()
        with self.assertRaises(p.Stop):p.prepare_manifest(self.inventory,self.inventory,**kwargs)
        states=[state for key,state in p._CONSUMPTION_RECORDS.items() if key=='attempt:'+self.attempt]
        self.assertEqual(states[0][0],'RESERVED')
    def test_unavailable_store_and_direct_boundary_bypass(self):
        kwargs=dict(self.manifest_args(),**self.captures());self.consumption.unavailable=True
        with self.assertRaisesRegex(p.Stop,'UNAVAILABLE'):p.prepare_manifest(self.inventory,self.inventory,**kwargs)
        for forged in (None,{'consumed':False},p.DisabledDurableConsumptionStore()):
            with self.assertRaisesRegex(p.Stop,'CONSUMPTION_BOUNDARY'):p.prepare_manifest(self.inventory,self.inventory,**dict(kwargs,consumption=forged))
    def test_partial_persisted_reservation_blocks_whole_attempt(self):
        kwargs=dict(self.manifest_args(),**self.captures())
        # Fictional persisted partial record: recovery must not infer unused state.
        p._CONSUMPTION_RECORDS['attempt:'+self.attempt]=('RESERVED','UNKNOWN_AFTER_INTERRUPTION')
        with self.assertRaisesRegex(p.Stop,'ALREADY_RESERVED'):p.prepare_manifest(self.inventory,self.inventory,**kwargs)
    def test_identical_manifest_replay_and_reissued_captures_blocked(self):
        kwargs=dict(self.manifest_args(),**self.captures())
        p.prepare_manifest(self.inventory,self.inventory,**kwargs)
        with self.assertRaisesRegex(p.Stop,'ALREADY_RESERVED'):p.prepare_manifest(self.inventory,self.inventory,**kwargs)
        kwargs.update(self.captures())
        with self.assertRaisesRegex(p.Stop,'ALREADY_RESERVED'):p.prepare_manifest(self.inventory,self.inventory,**kwargs)
    def test_dump_plan_attempt_mismatch(self):
        kwargs=dict(endpoint='127.0.0.1',approved_endpoint='127.0.0.1',port=3306,approved_port=3306,
            ca_path=r'C:\Approved\ca.pem',ca_sha256='A'*64,approved_ca_sha256='A'*64,user='fictional_backup',dump=r'C:\Private\new\viva.sql',
            destination=self.destination(),attempt_id='checkpoint-'+uuid4().hex)
        with self.assertRaisesRegex(p.Stop,'DESTINATION_ATTEMPT_MISMATCH'):p.dump_arguments(**kwargs)
    def test_filesystem_consumption_integrated_with_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            self.consumption=p.FilesystemConsumptionStore(Path(directory))
            kwargs=dict(self.manifest_args(),**self.captures())
            raw,_=p.prepare_manifest(self.inventory,self.inventory,**kwargs)
            self.assertEqual(json.loads(raw)['attempt_id'],self.attempt)
            kwargs['consumption']=p.FilesystemConsumptionStore(Path(directory))
            kwargs['dump_sha256']='D'*64
            with self.assertRaises(p.Stop):p.prepare_manifest(self.inventory,self.inventory,**kwargs)
    def test_direct_manifest_requires_issued_reserved_job(self):
        kwargs=dict(self.manifest_args(),**self.captures())
        for forged in (None,{},object.__new__(p.ReservedJob)):
            with self.assertRaisesRegex(p.Stop,'ISSUED_RESERVED_JOB'):p.prepare_manifest(self.inventory,self.inventory,**dict(kwargs,job=forged))
        with self.assertRaises(p.Stop):p.ReservedJob()
    def test_same_attempt_destination_and_dump_substitution(self):
        kwargs=dict(self.manifest_args(),**self.captures());other=self.destination(r'C:\Private\other')
        with self.assertRaisesRegex(p.Stop,'JOB_CAPABILITY_MISMATCH'):
            p.prepare_manifest(self.inventory,self.inventory,**dict(kwargs,destination=other,dump=r'C:\Private\other\viva.sql'))
    def test_same_attempt_capture_substitution(self):
        kwargs=dict(self.manifest_args(),**self.captures())
        pre_evidence=dict(self.snapshot,owner='substitute-pre',capture_owner='substitute-pre')
        substitute=p.capture_fingerprints(self.inventory,self.rows,pre_evidence,self.freeze,111,'fictional-uuid',attempt_id=self.attempt)
        with self.assertRaisesRegex(p.Stop,'JOB_CAPABILITY_MISMATCH'):
            p.prepare_manifest(self.inventory,self.inventory,**dict(kwargs,before_capture=substitute))
        evidence=dict(self.snapshot,owner='unexpected-post',capture_owner='unexpected-post',started_at=112,finished_at=114)
        post=p.capture_fingerprints(self.inventory,self.rows,evidence,self.freeze,115,'fictional-uuid',attempt_id=self.attempt)
        with self.assertRaisesRegex(p.Stop,'FINAL_MANIFEST_JOB_MISMATCH'):
            p.prepare_manifest(self.inventory,self.inventory,**dict(kwargs,after_capture=post))
        duplicate=dict(self.snapshot,owner='capture-2',capture_owner='capture-2',started_at=112,finished_at=114)
        with self.assertRaisesRegex(p.Stop,'CAPTURE_ID_ALREADY_ISSUED'):
            p.capture_fingerprints(self.inventory,self.rows,duplicate,self.freeze,115,'fictional-uuid',attempt_id=self.attempt)
    def test_persisted_job_binding_substitution_and_interrupted_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            self.consumption=p.FilesystemConsumptionStore(Path(directory))
            kwargs=dict(self.manifest_args(),**self.captures())
            # Reopened store is not permitted to resume an existing job.
            with self.assertRaises(p.Stop):
                p.prepare_manifest(self.inventory,self.inventory,**dict(kwargs,consumption=p.FilesystemConsumptionStore(Path(directory))))
            record_path=Path(directory)/(self.attempt+'.execution.json')
            data=json.loads(record_path.read_text());data['job_binding']='F'*64
            record_path.write_bytes(p.canonical(data))
            with self.assertRaises(p.Stop):p.prepare_manifest(self.inventory,self.inventory,**kwargs)
    def test_cross_attempt_job_identity_substitution(self):
        kwargs=dict(self.manifest_args(),**self.captures());saved=kwargs['job']
        other_attempt='checkpoint-'+uuid4().hex
        with self.assertRaises(p.Stop):p.prepare_manifest(self.inventory,self.inventory,**dict(kwargs,attempt_id=other_attempt,job=saved))
    def test_interruption_evidence_redacted_and_execution_blocked(self):
        self.assertEqual(json.loads(p.failure_record('DUMP'))['status'],'INCOMPLETE_PRESERVE_NO_RETRY_NO_CLEANUP')
        for method in ('connect','backup','restore','write'):
            with self.assertRaises(p.Stop):getattr(p.DisabledCheckpointExecution(),method)(execute=True)

if __name__=='__main__':unittest.main()

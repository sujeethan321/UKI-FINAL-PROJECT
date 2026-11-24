"""Focused filesystem/recipe tests. Only disposable temporary evidence roots.

Child Python processes reserve fictional attempts; never run a MySQL client.
"""
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch
from uuid import uuid4

spec=importlib.util.spec_from_file_location('checkpoint_execution_test',Path(__file__).resolve().parents[1]/'scripts/checkpoint_execution_prepare.py')
x=importlib.util.module_from_spec(spec);sys.modules[spec.name]=x;spec.loader.exec_module(x);p=x.p
SCRIPT=p.__file__
WORKER="""import importlib.util,sys,os
s=importlib.util.spec_from_file_location('child_plan',sys.argv[1]);p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
try:
 store=p.FilesystemConsumptionStore(sys.argv[2]);store.reserve(sys.argv[3],('B'*64,'C'*64),'A'*64)
 if sys.argv[4]=='interrupt':os._exit(7)
 print('RESERVED')
except Exception:print('STOP');sys.exit(2)
"""

class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.attempt='checkpoint-'+uuid4().hex
        self.store=p.FilesystemConsumptionStore(self.root)
        guard=patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN'));guard.start();self.addCleanup(guard.stop)
    def reserve(self,store=None,attempt=None):return (store or self.store).reserve(attempt or self.attempt,('B'*64,'C'*64),'A'*64)
    def test_exclusive_first_use_and_new_client_rejection(self):
        token=self.reserve();self.assertEqual(token,self.attempt)
        with self.assertRaises(p.Stop):self.reserve(p.FilesystemConsumptionStore(self.root))
    def test_captures_cannot_cross_attempts(self):
        self.reserve()
        with self.assertRaises(p.Stop):self.reserve(attempt='checkpoint-'+uuid4().hex)
    def test_completion_exclusive_and_reserved_immutable(self):
        self.reserve();before=(self.root/(self.attempt+'.reserved.json')).read_bytes()
        self.store.complete(self.attempt,'A'*64)
        with self.assertRaises(FileExistsError):self.store.complete(self.attempt,'A'*64)
        self.assertEqual(before,(self.root/(self.attempt+'.reserved.json')).read_bytes())
    def test_cross_process_concurrent_reservation(self):
        args=[sys.executable,'-B','-c',WORKER,SCRIPT,str(self.root),self.attempt,'normal']
        processes=[subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False) for _ in range(2)]
        results=[proc.communicate(timeout=30)[0].decode().strip() for proc in processes]
        self.assertEqual(sorted(results),['RESERVED','STOP'])
    def test_process_interruption_preserves_reservation(self):
        result=subprocess.run([sys.executable,'-B','-c',WORKER,SCRIPT,str(self.root),self.attempt,'interrupt'],capture_output=True,timeout=30)
        self.assertEqual(result.returncode,7)
        with self.assertRaises(p.Stop):self.reserve(p.FilesystemConsumptionStore(self.root))
    def test_prelaunch_reservation_no_resume_and_same_owner_finalization(self):
        self.store.reserve_execution(self.attempt,'D'*64)
        with self.assertRaises(p.Stop):p.FilesystemConsumptionStore(self.root).reserve_execution(self.attempt,'D'*64)
        with self.assertRaisesRegex(p.Stop,'NO_AUTOMATIC_RESUME'):self.reserve(p.FilesystemConsumptionStore(self.root))
        token=self.reserve();self.store.complete(token,'A'*64)
    def test_prelaunch_failure_evidence_without_post_capture(self):
        self.store.reserve_execution(self.attempt,'D'*64);self.store.failure(self.attempt,'BASELINE')
        with self.assertRaises(p.Stop):self.reserve()
        self.assertTrue((self.root/(self.attempt+'.execution.json')).exists())
    def test_partial_journal_stops_without_repair(self):
        target=self.root/(self.attempt+'.reserved.json');target.write_bytes(b'{"partial":')
        with self.assertRaises(p.Stop):self.reserve()
        self.assertEqual(target.read_bytes(),b'{"partial":')
    def test_failure_evidence_redacted_and_completion_blocked(self):
        self.reserve();self.store.failure(self.attempt,'DUMP')
        value=json.loads((self.root/(self.attempt+'.failure.json')).read_text())
        self.assertEqual(value,dict(status='INCOMPLETE_PRESERVE_NO_RETRY',phase='DUMP'))
        with self.assertRaises(p.Stop):self.store.complete(self.attempt,'A'*64)
    def test_fsync_failure_never_acknowledges_reservation(self):
        # File may persist; no retry/cleanup is performed by the store.
        with patch.object(p.os,'fsync',side_effect=OSError('fictional')):
            with self.assertRaises(OSError):self.reserve()
        if (self.root/(self.attempt+'.reserved.json')).exists():
            with self.assertRaises(p.Stop):self.reserve(p.FilesystemConsumptionStore(self.root))
    def test_reparse_observation_rejected(self):
        target=self.root/'target';target.mkdir()
        # Portable attribute simulation: no real permissions or junction changes.
        original=Path.lstat
        class Reparse:
            st_file_attributes=0x400
        with patch.object(Path,'lstat',lambda path:Reparse() if path==self.root else original(path)):
            with self.assertRaises(p.Stop):p.FilesystemConsumptionStore(self.root)
    def recipe(self):
        sid='S-1-5-21-1-2-3-1001';path=r'C:\Private\checkpoint-new'
        obs=dict(outside_public_roots=True,reparse_ancestors_clear=True,destination_absent=True,outputs_absent=True,
            output_reparse_clear=True,owner=sid,protected=True,rules={sid:'FullControl:ContainerInherit,ObjectInherit','S-1-5-18':'FullControl:ContainerInherit,ObjectInherit'})
        return x.directory_recipe(self.attempt,path,path,obs,sid)
    def test_windows_acl_recipe_atomic_creation_and_negative_gates(self):
        recipe,_=self.recipe();self.assertEqual(recipe.api,'CreateDirectoryW_WITH_SECURITY_ATTRIBUTES')
        self.assertIn('D:P',recipe.sddl);self.assertIn(';;;SY)',recipe.sddl)
        observed=dict(attempt_id=self.attempt,path=recipe.path,owner_sid=recipe.owner_sid,sddl=recipe.sddl,
            **dict.fromkeys(recipe.required_checks,True))
        x.validate_windows_observation(recipe,observed)
        for key in recipe.required_checks:
            with self.assertRaises(p.Stop):x.validate_windows_observation(recipe,dict(observed,**{key:False}))
    def native(self,**kwargs):
        config=dict(endpoint=kwargs['endpoint'],port=kwargs['port'],server_uuid='fictional-server',schema=p.SOURCE,account=kwargs['user'],
            ca_path=kwargs['ca_path'],ca_sha256=kwargs['ca_sha256'],destination=str(p.PureWindowsPath(kwargs['dump']).parent),attempt_id=kwargs['attempt_id'])
        raw=p.canonical(config)
        approved=x.bind_approved_configuration(raw,p.sha(raw),kwargs['destination'])
        return x.native_recipe(configuration=approved)
    def capture_fixture(self,approval):
        rows={name:[{'id':1}] for name in p.TABLES};rows['alembic_version']=[{'version_num':p.REVISION}]
        tables={name:dict(p.typed.fingerprint(values,list(values[0])),columns=list(values[0]),schema_sha256='A'*64,
            primary_key=[],indexes=[],foreign_keys=[],checks=[],engine='InnoDB') for name,values in rows.items()}
        inventory=dict(database=p.SOURCE,revision=p.REVISION,host='127.0.0.1',port=3306,server_uuid=approval['server_uuid'],
            object_inventory_complete=True,tables=tables,triggers=[],views=[],routines=[],events=[])
        snapshot=dict(isolation='REPEATABLE READ',read_only=True,consistent_snapshot=True,owner='capture-pre',capture_owner='capture-pre',started_at=140,finished_at=145)
        freeze=dict(source=p.SOURCE,revision=p.REVISION,server_uuid=approval['server_uuid'],evidence_id='freeze-fictional',writer_freeze=True,ddl_freeze=True,observed_at=100,expires_at=200)
        pre=p.capture_fingerprints(inventory,rows,snapshot,freeze,150,approval['server_uuid'],attempt_id=self.attempt)
        return pre,inventory,rows,snapshot,freeze
    def test_shell_free_trigger_aware_recipe(self):
        _,destination=self.recipe()
        recipe=self.native(endpoint='127.0.0.1',approved_endpoint='127.0.0.1',port=3306,approved_port=3306,
            ca_path=r'C:\Approved\ca.pem',ca_sha256='A'*64,approved_ca_sha256='A'*64,user='fixture_backup',
            dump=r'C:\Private\checkpoint-new\viva.sql',destination=destination,attempt_id=self.attempt)
        x.validate_native_recipe(recipe);self.assertFalse(recipe.shell)
        for flag in ('--single-transaction','--triggers','--routines','--events','--ssl-mode=VERIFY_IDENTITY'):self.assertIn(flag,recipe.argv)
        with self.assertRaises(p.Stop):x.validate_native_recipe(replace(recipe,shell=True))
        with self.assertRaises(p.Stop):x.validate_native_recipe(replace(recipe,argv=recipe.argv+('--password=secret',)))
    def test_exact_tls_dba_freeze_contract_and_expiry(self):
        approval=dict(source=p.SOURCE,revision=p.REVISION,endpoint='127.0.0.1',port=3306,server_uuid='fictional-server',
            backup_account='fixture_backup',ca_sha256='A'*64,attempt_id=self.attempt)
        observed=dict(approval,observed_at=100,expires_at=200,**dict.fromkeys(('tls_chain_verified','san_only_verified','backup_grants_verified',
            'writer_freeze','ddl_freeze','no_unexplained_writers','capacity_verified','private_console','complete_inventory_verified','innoDB_only'),True))
        x.prerequisite_contract(approval,observed,150)
        with self.assertRaises(p.Stop):x.prerequisite_contract(approval,observed,200)
        with self.assertRaises(p.Stop):x.prerequisite_contract(approval,dict(observed,server_uuid='wrong'),150)
        with self.assertRaises(p.Stop):x.prerequisite_contract(approval,dict(observed,writer_freeze=False),150)
        directory,destination=self.recipe()
        native=self.native(endpoint='127.0.0.1',approved_endpoint='127.0.0.1',port=3306,approved_port=3306,
            ca_path=r'C:\Approved\ca.pem',ca_sha256='A'*64,approved_ca_sha256='A'*64,user='fixture_backup',
            dump=r'C:\Private\checkpoint-new\viva.sql',destination=destination,attempt_id=self.attempt)
        pre,inventory,*_=self.capture_fixture(approval)
        x.reserve_prelaunch(self.store,directory,native,approval,observed,150,before_capture=pre,inventory=inventory,expected_post_capture_id='capture-post')
        with self.assertRaises(p.Stop):x.reserve_prelaunch(self.store,directory,native,approval,observed,150,before_capture=pre,inventory=inventory,expected_post_capture_id='capture-post')
    def test_recomputed_recipe_hash_cannot_authorize_argv_substitution(self):
        _,destination=self.recipe()
        recipe=self.native(endpoint='127.0.0.1',approved_endpoint='127.0.0.1',port=3306,approved_port=3306,
            ca_path=r'C:\Approved\ca.pem',ca_sha256='A'*64,approved_ca_sha256='A'*64,user='fixture_backup',
            dump=r'C:\Private\checkpoint-new\viva.sql',destination=destination,attempt_id=self.attempt)
        original=list(recipe.argv)
        variants=[['--host=other.example' if a.startswith('--host=') else a for a in original],
                  [r'--ssl-ca=C:\Other\ca.pem' if a.startswith('--ssl-ca=') else a for a in original],
                  [r'--result-file=C:\Other\viva.sql' if a.startswith('--result-file=') else a for a in original],
                  [a for a in original if a!='--single-transaction'],
                  original[:-1]+['--skip-triggers',original[-1]],
                  original[:-1]+['--ssl-mode=DISABLED',original[-1]],
                  original[:-1]+['--host=other.example',original[-1]],list(reversed(original))]
        for argv in variants:
            forged=replace(recipe,argv=tuple(argv),argv_sha256=p.sha(p.canonical(argv)))
            with self.assertRaisesRegex(p.Stop,'ISSUED_NATIVE_RECIPE'):x.validate_native_recipe(forged)
    def test_issued_recipe_mutation_detected_even_with_recomputed_hash(self):
        _,destination=self.recipe()
        recipe=self.native(endpoint='127.0.0.1',port=3306,user='fixture_backup',ca_path=r'C:\Approved\ca.pem',ca_sha256='A'*64,
            dump=r'C:\Private\checkpoint-new\viva.sql',destination=destination,attempt_id=self.attempt)
        argv=recipe.argv[:-1]+('--skip-triggers',recipe.argv[-1])
        object.__setattr__(recipe,'argv',argv);object.__setattr__(recipe,'argv_sha256',p.sha(p.canonical(list(argv))))
        with self.assertRaisesRegex(p.Stop,'MUTATED'):x.validate_native_recipe(recipe)
    def test_configuration_requires_approved_bytes_and_issued_identity(self):
        _,destination=self.recipe()
        with self.assertRaises(p.Stop):x.bind_approved_configuration(b'{}','A'*64,destination)
        with self.assertRaises(p.Stop):x.native_recipe(configuration={})
        with self.assertRaises(p.Stop):x.ApprovedDumpConfiguration()
        with self.assertRaises(p.Stop):x.native_recipe(configuration=object.__new__(x.ApprovedDumpConfiguration))
    def test_all_real_execution_and_trust_blocked(self):
        for method in ('verify_real_dba','provision_private_directory','connect','run_mysqldump','execute'):
            with self.assertRaises(p.Stop):getattr(x.DisabledBackupBoundary(),method)(approved=True)
        with self.assertRaises(p.Stop):p.DisabledCheckpointExecution().backup()

if __name__=='__main__':unittest.main()

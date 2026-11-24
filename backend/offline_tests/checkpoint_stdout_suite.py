"""Mock processes and memory-only files. No real signature, filesystem or client.

Reuse existing explicitly fictional signed-approval/job fixture; never claim
its mocked signature or model receipt is real independent authorization.
"""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

base_spec=importlib.util.spec_from_file_location('stdout_native_fixture',Path(__file__).with_name('checkpoint_native_suite.py'))
base=importlib.util.module_from_spec(base_spec);sys.modules[base_spec.name]=base;base_spec.loader.exec_module(base)
sys.modules['_lankapex_checkpoint_native']=base.n
spec=importlib.util.spec_from_file_location('checkpoint_stdout_test',Path(__file__).resolve().parents[1]/'scripts/checkpoint_stdout_output.py')
s=importlib.util.module_from_spec(spec);sys.modules[spec.name]=s;spec.loader.exec_module(s);p=s.p

class StdoutTests(unittest.TestCase):
    def setUp(self):
        self.fixture=base.NativeTests('test_pinned_signer_required');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.auth=self.fixture.issue();self.raw,*_=self.fixture.bound_fixture(self.auth)
        self.proposal=s.expected_stdout_approval(self.auth,self.fixture.job,self.fixture.native)
        self.recipe=s.bind_stdout_approval(self.proposal,p.sha(self.proposal),value=self.auth,job=self.fixture.job,base_recipe=self.fixture.native)
        self.files=s.MockExclusiveFiles();self.process=s.MockDumpProcess([self.raw])
    def run_output(self):return s.run_model(self.recipe,self.files,self.process)
    def test_separate_stdout_approval_old_recipe_unchanged(self):
        self.assertTrue(any(v.startswith('--result-file=') for v in self.fixture.native.argv))
        self.assertFalse(any(v.startswith('--result-file=') for v in self.recipe.argv))
        self.assertEqual(json.loads(self.proposal)['format'],'checkpoint-stdout-v1')
        with self.assertRaises(p.Stop):s.bind_stdout_approval(self.proposal,None,value=self.auth,job=self.fixture.job,base_recipe=self.fixture.native)
    def test_full_argv_and_approval_substitution(self):
        for flag in ('--host=other','--ssl-mode=DISABLED','--result-file=C:\\Other\\viva.sql','--skip-triggers'):
            forged=replace(self.recipe,argv=self.recipe.argv[:-1]+(flag,self.recipe.argv[-1]))
            with self.assertRaises(p.Stop):s.validate_stdout_recipe(forged)
        data=json.loads(self.proposal);data['ca_sha256']='F'*64;raw=p.canonical(data)
        with self.assertRaises(p.Stop):s.bind_stdout_approval(raw,p.sha(raw),value=self.auth,job=self.fixture.job,base_recipe=self.fixture.native)
    def test_success_exclusive_handle_full_validation_model_receipt(self):
        receipt=self.run_output();record=s.model_receipt_record(receipt)
        self.assertEqual(record['status'],'MODEL_ONLY_NOT_NATIVE_BACKUP')
        self.assertEqual(record['backup_sha256'],p.sha(self.raw));self.assertTrue(record['flush_confirmed'])
        argv,handle,shell=self.process.calls[0]
        self.assertIs(handle,self.files.entries[self.recipe.output_path]);self.assertTrue(handle.closed)
        self.assertFalse(shell);self.assertEqual(argv,self.recipe.argv)
        self.assertEqual(record['job_sha256'],self.recipe.job_sha256)
        self.assertNotIsInstance(receipt,s.n.VerifiedDumpRun)
    def test_existing_output_no_overwrite_or_process(self):
        handle=self.files.create_new(self.recipe.output_path);handle.bytes.extend(b'EXISTING')
        with self.assertRaises(p.Stop):self.run_output()
        self.assertEqual(bytes(handle.bytes),b'EXISTING');self.assertEqual(self.process.calls,[])
    def test_case_equivalent_existing_output_blocks_process(self):
        existing_path=self.recipe.output_path.upper()
        handle=self.files.create_new(existing_path);handle.bytes.extend(b'PRESERVE_EXISTING')
        before=len(s._MODEL_RECEIPTS)
        self.assertIn(self.recipe.output_path,self.files.entries)
        self.assertIs(self.files.entries[self.recipe.output_path],handle)
        with self.assertRaisesRegex(p.Stop,'FAILED_CREATE_NEW'):self.run_output()
        self.assertEqual(bytes(handle.bytes),b'PRESERVE_EXISTING')
        self.assertEqual(self.process.calls,[]);self.assertEqual(before,len(s._MODEL_RECEIPTS))
    def test_windows_identity_creation_lookup_and_reservation(self):
        upper=r'C:\Private\Fixture\VIVA.SQL';lower=r'c:\private\fixture\viva.sql'
        handle=self.files.create_new(upper)
        self.assertIs(self.files.entries[lower],handle)
        with self.assertRaisesRegex(p.Stop,'OUTPUT_ALREADY_EXISTS'):self.files.create_new(lower)
        self.assertEqual(len(self.files.entries),1)
        # Namespace identity does not relax the exact approved/opened handle path.
        with self.assertRaisesRegex(p.Stop,'PATH_SUBSTITUTED'):self.files.verify(handle,lower)
        self.files.record(r'C:\Private\Fixture\STDOUT-ATTEMPT.JSON',{'status':'RESERVED'})
        with self.assertRaisesRegex(p.Stop,'OUTPUT_ALREADY_EXISTS'):
            self.files.record(r'c:\private\fixture\stdout-attempt.json',{'status':'REPLACEMENT'})
    def test_identity_normalization_does_not_accept_unsafe_paths(self):
        for path in (r'C:\Private\..\viva.sql',r'C:\Private\viva.sql:stream',
                     r'\\?\C:\Private\viva.sql',r'\\server\share\viva.sql',
                     r'C:\Private\VIVA~1.SQL',r'C:\Private\viva.sql.'):
            with self.subTest(path=path):
                with self.assertRaises(p.Stop):self.files.create_new(path)
                with self.assertRaises(p.Stop):self.files.entries.get(path)
        self.assertEqual(len(self.files.entries),0)
    def test_reparse_junction_and_parent_ownership_rejected(self):
        for field in ('reparse','parent_reparse'):
            files=s.MockExclusiveFiles();setattr(files,field,True)
            with self.assertRaises(p.Stop):files.create_new(self.recipe.output_path)
        for field in ('parent_handle_held','acl_verified'):
            files=s.MockExclusiveFiles();setattr(files,field,False)
            with self.assertRaises(p.Stop):files.create_new(self.recipe.output_path)
    def test_handle_and_path_substitutions(self):
        handle=self.files.create_new(self.recipe.output_path)
        with self.assertRaises(p.Stop):self.files.verify(handle,r'C:\Other\viva.sql')
        other=s.MockExclusiveFiles().create_new(self.recipe.output_path)
        with self.assertRaises(p.Stop):self.files.verify(other,self.recipe.output_path)
        handle.identity=object()
        with self.assertRaises(p.Stop):self.files.verify(handle,self.recipe.output_path)
    def test_substitution_after_start_preserves_failure_and_blocks_receipt(self):
        self.files.substitute_after_start=True
        with self.assertRaises(p.Stop):self.run_output()
        failure=self.files.entries[str(p.PureWindowsPath(self.recipe.output_path).parent/'stdout-failure.json')]
        self.assertEqual(json.loads(failure.bytes)['phase'],'PROCESS')
        self.assertTrue(self.files.entries[self.recipe.output_path].closed)
    def test_nonzero_process_no_receipt(self):
        self.process=s.MockDumpProcess([self.raw],returncode=1)
        before=len(s._MODEL_RECEIPTS)
        with self.assertRaises(p.Stop):self.run_output()
        self.assertEqual(bytes(self.files.entries[self.recipe.output_path].bytes),self.raw)
        self.assertEqual(before,len(s._MODEL_RECEIPTS))
    def test_interruption_preserves_partial_bytes_and_rejects_retry(self):
        self.process=s.MockDumpProcess([b'PARTIAL'],interrupted=True)
        with self.assertRaises(p.Stop):self.run_output()
        self.assertEqual(bytes(self.files.entries[self.recipe.output_path].bytes),b'PARTIAL')
        with self.assertRaisesRegex(p.Stop,'ALREADY_ATTEMPTED'):s.run_model(self.recipe,s.MockExclusiveFiles(),s.MockDumpProcess([self.raw]))
    def test_incomplete_dump_no_receipt(self):
        self.process=s.MockDumpProcess([self.raw.replace(b'-- Dump completed',b'-- Incomplete')])
        with self.assertRaisesRegex(p.Stop,'VALIDATE'):self.run_output()
    def test_digest_mismatch_no_receipt(self):
        self.files.digest_override='0'*64
        with self.assertRaises(p.Stop):self.run_output()
    def test_flush_must_be_confirmed(self):
        self.files.output_flush_ok=False;before=len(s._MODEL_RECEIPTS)
        with self.assertRaisesRegex(p.Stop,'FAILED_FLUSH'):self.run_output()
        self.assertEqual(len(self.process.calls),1);self.assertEqual(before,len(s._MODEL_RECEIPTS))
    def test_repeated_successful_job_rejected(self):
        self.run_output()
        with self.assertRaisesRegex(p.Stop,'ALREADY_ATTEMPTED'):s.run_model(self.recipe,s.MockExclusiveFiles(),s.MockDumpProcess([self.raw]))
    def test_stderr_bounded_redacted_and_separate(self):
        secret=b'password=FICTIONAL_SECRET SQL customer-data '
        self.process=s.MockDumpProcess([self.raw],stderr=[secret*1000])
        self.run_output()
        stderr=self.files.entries[str(p.PureWindowsPath(self.recipe.output_path).parent/'stderr-status.json')]
        record=json.loads(stderr.bytes)
        self.assertEqual(record['retained_bytes'],0);self.assertEqual(record['observed_bytes_bounded'],16384)
        self.assertTrue(record['truncated']);self.assertNotIn(b'FICTIONAL_SECRET',stderr.bytes)
    def test_receipt_unavailable_before_validation_and_native_blocked(self):
        with self.assertRaises(p.Stop):s.ModelRunReceipt()
        with self.assertRaises(p.Stop):s.model_receipt_record(object.__new__(s.ModelRunReceipt))
        with patch('subprocess.Popen',side_effect=AssertionError('NO_NATIVE_PROCESS')) as spawn:
            with self.assertRaises(p.Stop):s.NativeStdoutRunner().run(self.recipe,self.files)
            with self.assertRaises(p.Stop):s.NativeStdoutRunner().issue_native_receipt(approved=True)
            spawn.assert_not_called()
    def test_same_attempt_recipe_object_mutation_rejected(self):
        object.__setattr__(self.recipe,'output_path',r'C:\Other\viva.sql')
        with self.assertRaises(p.Stop):self.run_output()

if __name__=='__main__':unittest.main()

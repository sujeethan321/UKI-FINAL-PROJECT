"""Fictional approvals, memory output/processes, disposable existing journals."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import json
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('journal_fixture',Path(__file__).with_name('checkpoint_stdout_suite.py'))
f=importlib.util.module_from_spec(spec);sys.modules[spec.name]=f;spec.loader.exec_module(f)
s=f.s;p=s.p

class JournalTests(unittest.TestCase):
    def setUp(self):
        self.fixture=f.StdoutTests('test_existing_output_no_overwrite_or_process');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.store=p.FilesystemConsumptionStore(self.root)
        native=self.fixture.fixture
        _,_,raw,destination,pre=p._JOBS[id(native.job)]
        self.store.reserve_execution(native.attempt,p.sha(raw))
        native.job=p._issue_reserved_job(self.store,raw,destination,pre)
        proposal=s.expected_stdout_approval(self.fixture.auth,native.job,native.native)
        self.recipe=s.bind_stdout_approval(proposal,p.sha(proposal),value=self.fixture.auth,job=native.job,base_recipe=native.native)
        self.binding=s.journal_binding(self.recipe,self.store)
        self.files=s.MockExclusiveFiles();self.process=s.MockDumpProcess([self.fixture.raw])
    def run_model(self):return s.run_model(self.recipe,self.files,self.process,journal=self.store)
    def test_success_and_new_wrapper_reuse_rejected(self):
        receipt=self.run_model();self.assertEqual(s.model_receipt_record(receipt)['status'],'MODEL_ONLY_NOT_NATIVE_BACKUP')
        self.assertTrue((self.root/(self.recipe.attempt_id+'.stdout_validated.json')).is_file())
        with self.assertRaises(p.Stop):s.run_model(self.recipe,s.MockExclusiveFiles(),s.MockDumpProcess([self.fixture.raw]),journal=self.store)
        self.assertEqual(len(self.process.calls),1)
    def test_reopened_store_crash_at_each_boundary(self):
        self.store.reserve_stdout(self.binding)
        reopened=p.FilesystemConsumptionStore(self.root)
        for method in (reopened.reserve_stdout,reopened.consume_stdout_launch):
            with self.assertRaises(p.Stop):method(self.binding)
        self.store.consume_stdout_launch(self.binding)
        with self.assertRaises(p.Stop):reopened.consume_stdout_launch(self.binding)
        with self.assertRaises(p.Stop):self.store.consume_stdout_launch(self.binding)
    def test_crash_after_execution_reservation_before_stdout(self):
        reopened=p.FilesystemConsumptionStore(self.root)
        with self.assertRaises(p.Stop):reopened.reserve_stdout(self.binding)
    def test_separate_python_process_cannot_resume(self):
        self.store.reserve_stdout(self.binding)
        script="import sys,json; sys.path.insert(0,sys.argv[1]); import current_checkpoint_plan as p; s=p.FilesystemConsumptionStore(sys.argv[2]);\ntry:s.consume_stdout_launch(json.loads(sys.argv[3]))\nexcept p.Stop: print('RESTART_BLOCKED');sys.exit(0)\nsys.exit(9)"
        result=subprocess.run([sys.executable,'-B','-c',script,str(Path(__file__).resolve().parents[1]/'scripts'),str(self.root),json.dumps(self.binding)],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0);self.assertIn('RESTART_BLOCKED',result.stdout)
    def test_concurrent_launch_only_one_consumes(self):
        self.store.reserve_stdout(self.binding);barrier=threading.Barrier(2)
        def consume():
            barrier.wait()
            try:self.store.consume_stdout_launch(self.binding);return True
            except (p.Stop,OSError):return False
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:consume(),range(2)))
        self.assertEqual(results.count(True),1)
    def test_duplicate_or_changed_reservation_rejected(self):
        self.store.reserve_stdout(self.binding)
        for binding in (self.binding,dict(self.binding,argv_sha256='F'*64),dict(self.binding,approval_sha256='E'*64),dict(self.binding,output_path=r'C:\Other\viva.sql')):
            with self.assertRaises(p.Stop):self.store.reserve_stdout(binding)
            with self.assertRaises(p.Stop):self.store.consume_stdout_launch(binding) if binding!=self.binding else self.store.reserve_stdout(binding)
    def test_truncated_or_malformed_records_fail_closed(self):
        self.store.reserve_stdout(self.binding)
        path=self.root/(self.recipe.attempt_id+'.stdout_reserved.json')
        for raw in (b'{',b'{}',b'null',b'{"status":"stdout_reserved"}'):
            path.write_bytes(raw)  # corruption of disposable fixture only
            with self.assertRaises(p.Stop):self.store.consume_stdout_launch(self.binding)
    def test_failure_preserves_partial_bytes_and_redacts_evidence(self):
        self.process=s.MockDumpProcess([b'PARTIAL'],interrupted=True)
        with self.assertRaises(InterruptedError) as caught:self.run_model()
        self.assertEqual(caught.exception.evidence_status,'PRESERVED_MODEL_ONLY')
        self.assertEqual(bytes(self.files.entries[self.recipe.output_path].bytes),b'PARTIAL')
        record=json.loads((self.root/(self.recipe.attempt_id+'.failure.json')).read_bytes())
        self.assertEqual(record['binding'],self.binding);self.assertEqual(record['failure_code'],'STDOUT_STAGE_FAILED')
        self.assertNotIn('MODELED_INTERRUPT',str(record))
        with self.assertRaises(p.Stop):self.store.consume_stdout_launch(self.binding)
    def test_failure_record_write_error_preserves_original_and_blocks_restart(self):
        original=KeyboardInterrupt('FICTIONAL_PRIVATE');self.process.interrupted=True
        with patch.object(self.process,'run',side_effect=original),patch.object(self.store,'fail_stdout',side_effect=OSError('FICTIONAL')):
            with self.assertRaises(KeyboardInterrupt) as caught:self.run_model()
        self.assertIs(caught.exception,original);self.assertEqual(original.evidence_status,'INCOMPLETE')
        with self.assertRaises(p.Stop):p.FilesystemConsumptionStore(self.root).consume_stdout_launch(self.binding)
    def test_completion_write_failure_no_receipt(self):
        before=len(s._MODEL_RECEIPTS)
        with patch.object(self.store,'complete_stdout_model',side_effect=OSError('FICTIONAL')):
            with self.assertRaises(OSError):self.run_model()
        self.assertEqual(before,len(s._MODEL_RECEIPTS))
        self.assertTrue((self.root/(self.recipe.attempt_id+'.failure.json')).is_file())
    def close_failure(self,primary=None,validation=False,journal_error=False):
        close_error=OSError('FICTIONAL_PRIVATE_CLOSE');old_close=self.files.close
        def close(handle):
            if handle.path==self.recipe.output_path:raise close_error
            old_close(handle)
        def fail_process(*args,**kwargs):
            kwargs['write_stdout'](b'PARTIAL');raise primary
        before=len(s._MODEL_RECEIPTS)
        from contextlib import ExitStack
        with ExitStack() as stack:
            stack.enter_context(patch.object(self.files,'close',side_effect=close))
            if primary is not None:
                if validation:stack.enter_context(patch.object(s.n,'validate_dump_bytes',side_effect=primary))
                else:stack.enter_context(patch.object(self.process,'run',side_effect=fail_process))
            if journal_error:stack.enter_context(patch.object(self.store,'fail_stdout',side_effect=OSError('FICTIONAL_JOURNAL')))
            expected=primary if primary is not None else close_error
            with self.assertRaises(type(expected)) as caught:self.run_model()
        self.assertIs(caught.exception,expected)
        self.assertEqual(expected.cleanup_status,'INCOMPLETE')
        self.assertIn('OUTPUT_CLOSE_INCOMPLETE',expected.cleanup_codes)
        self.assertEqual(expected.evidence_status,'INCOMPLETE' if journal_error else 'PRESERVED_MODEL_ONLY')
        self.assertEqual(before,len(s._MODEL_RECEIPTS))
        self.assertFalse((self.root/(self.recipe.attempt_id+'.stdout_validated.json')).exists())
        output=self.files.entries[self.recipe.output_path]
        self.assertEqual(bytes(output.bytes),b'PARTIAL' if primary is not None and not validation else self.fixture.raw)
        reopened=p.FilesystemConsumptionStore(self.root)
        with self.assertRaises(p.Stop):reopened.consume_stdout_launch(self.binding)
        with self.assertRaises(p.Stop):s.run_model(self.recipe,s.MockExclusiveFiles(),s.MockDumpProcess([self.fixture.raw]),journal=self.store)
        if not journal_error:
            raw=(self.root/(self.recipe.attempt_id+'.failure.json')).read_bytes();record=json.loads(raw)
            self.assertEqual(record['binding'],self.binding)
            self.assertEqual(record['stdout_phase'],'CLOSE' if primary is None else 'VALIDATE' if validation else 'PROCESS')
            self.assertIn('OUTPUT_CLOSE_INCOMPLETE',record['cleanup_codes'])
            self.assertNotIn(b'FICTIONAL_PRIVATE',raw)
        return expected
    def test_close_failure_after_validation(self):self.close_failure()
    def test_close_failure_preserves_process_exception(self):
        self.close_failure(KeyboardInterrupt('FICTIONAL_PRIVATE_PROCESS'))
    def test_close_failure_preserves_validation_exception(self):
        self.close_failure(p.Stop('FICTIONAL_PRIVATE_VALIDATION'),validation=True)
    def test_close_and_journal_write_failure_preserve_primary(self):
        self.close_failure(InterruptedError('FICTIONAL_PRIVATE_PROCESS'),journal_error=True)
    def test_close_only_and_journal_write_failure_preserve_close(self):
        self.close_failure(journal_error=True)
    def test_close_failure_does_not_block_independent_attempt(self):
        self.close_failure()
        other=JournalTests('test_success_and_new_wrapper_reuse_rejected');other.setUp()
        self.addCleanup(other.doCleanups)
        receipt=other.run_model()
        self.assertEqual(s.model_receipt_record(receipt)['status'],'MODEL_ONLY_NOT_NATIVE_BACKUP')

if __name__=='__main__':unittest.main()

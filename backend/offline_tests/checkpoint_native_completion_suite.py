"""Bounded native integration with fictional approval, mocked Win32/child only."""
import importlib.util
from pathlib import Path
import sys
import io
import json
import ctypes
import unittest
from contextlib import nullcontext,ExitStack
from unittest.mock import Mock,patch

spec=importlib.util.spec_from_file_location('completion_journal_fixture',Path(__file__).with_name('checkpoint_stdout_journal_suite.py'))
j=importlib.util.module_from_spec(spec);sys.modules[spec.name]=j;spec.loader.exec_module(j)
sys.modules['_lankapex_checkpoint_stdout']=j.s
spec=importlib.util.spec_from_file_location('completion_windows',Path(__file__).resolve().parents[1]/'scripts/checkpoint_stdout_windows.py')
a=importlib.util.module_from_spec(spec);sys.modules[spec.name]=a;spec.loader.exec_module(a)

class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.f=j.JournalTests('test_success_and_new_wrapper_reuse_rejected');self.f.setUp();self.addCleanup(self.f.doCleanups)
        native=self.f.fixture.fixture;proposal=a.s._RECIPES[id(self.f.recipe)][1]
        payload=dict(format='checkpoint-stdout-approval-v1',signer_id=native.payload['signer_id'],
            configuration_sha256=native.payload['configuration_sha256'],attempt_id=self.f.recipe.attempt_id,
            job_sha256=self.f.recipe.job_sha256,proposal_sha256=a.p.sha(proposal),
            argv_sha256=a.p.sha(a.p.canonical(list(self.f.recipe.argv))),dump_path=self.f.recipe.output_path,
            issued_at=100,expires_at=200,nonce='b'*32,writer_freeze=True,ddl_freeze=True)
        with patch.object(a.n,'_ed25519_verify',return_value=None):
            cap=native.verifier.verify_stdout(a.p.canonical(payload),b'\x00'*64,
                value=self.f.fixture.auth,job=native.job,proposal=proposal)
        self.f.recipe=a.s.bind_authenticated_stdout(proposal,cap,value=self.f.fixture.auth,job=native.job,base_recipe=native.native)
        self.f.binding=a.s.journal_binding(self.f.recipe,self.f.store)
        self.stdout_payload=payload;self.stdout_cap=cap;self.proposal=proposal
        self.files=a.WindowsStdoutFiles();self.process=a.WindowsStdoutProcess();self.adapter=a.NativeWindowsStdoutAdapter()
        self.api=Mock();self.api.security.return_value=nullcontext('PRIVATE')
        def open_handle(*args,**kwargs):
            self.assertTrue((self.f.root/(self.f.recipe.attempt_id+'.stdout_reserved.json')).exists())
            handle=Mock(value=123,closed=False);handle.close.side_effect=lambda:setattr(handle,'closed',True)
            return handle
        self.api.open.side_effect=open_handle
        self.child=Mock();self.child.stderr=io.BytesIO();self.child.wait.return_value=0;self.child.poll.return_value=0
    def run_prepared(self,*,read=None,launch_error=None,close_error=None,journal_error=False):
        def launch(argv,fd):
            self.assertTrue((self.f.root/(self.f.recipe.attempt_id+'.stdout_launch.json')).exists())
            self.assertEqual(argv,self.f.recipe.argv)
            if launch_error:raise launch_error
            return self.child
        with ExitStack() as stack:
            stack.enter_context(patch.object(self.files,'_api',return_value=self.api))
            stack.enter_context(patch.object(self.files,'_read_native',side_effect=read or [self.f.fixture.raw,self.f.fixture.raw]))
            stack.enter_context(patch.object(self.process,'_stdout_fd',return_value=42))
            stack.enter_context(patch.object(self.process,'_launch',side_effect=launch))
            stack.enter_context(patch.object(a.os,'close'))
            if close_error:stack.enter_context(patch.object(self.files,'close',side_effect=close_error))
            if journal_error:stack.enter_context(patch.object(self.f.store,'fail_stdout',side_effect=OSError('PRIVATE_JOURNAL')))
            return self.adapter.run_prepared_model(self.f.recipe,self.files,self.process,'OPERATOR',journal=self.f.store,
                after_capture=self.f.fixture.fixture.post)
    def test_full_integration_issues_only_model_receipt(self):
        receipt=self.run_prepared();record=a.s.model_receipt_record(receipt)
        self.assertEqual(record['backup_sha256'],a.p.sha(self.f.fixture.raw))
        self.assertNotIsInstance(receipt,a.n.VerifiedDumpRun)
        self.assertTrue(self.files.output.closed)
        self.assertTrue((self.f.root/(self.f.recipe.attempt_id+'.stdout_validated.json')).exists())
        self.api.k.FlushFileBuffers.assert_called()
    def test_failed_launch_preserves_original_and_records_failure(self):
        original=OSError('PRIVATE_LAUNCH')
        with self.assertRaises(OSError) as caught:self.run_prepared(launch_error=original)
        self.assertIs(caught.exception,original);self.assertTrue(self.files.output.closed)
        raw=(self.f.root/(self.f.recipe.attempt_id+'.failure.json')).read_bytes()
        self.assertNotIn(b'PRIVATE_LAUNCH',raw)
        with self.assertRaises(a.p.Stop):a.p.FilesystemConsumptionStore(self.f.root).consume_stdout_launch(self.f.binding)
    def test_changed_readback_no_receipt(self):
        before=len(a.s._MODEL_RECEIPTS)
        with self.assertRaisesRegex(a.p.Stop,'OUTPUT_CHANGED_DURING_VALIDATION'):
            self.run_prepared(read=[self.f.fixture.raw,b'ALTERED'])
        self.assertEqual(before,len(a.s._MODEL_RECEIPTS))
    def test_partial_dump_is_rejected_and_preserved(self):
        before=len(a.s._MODEL_RECEIPTS)
        with self.assertRaises(a.n.dump_inspection.DumpRejected):self.run_prepared(read=[b'PARTIAL'])
        self.assertEqual(before,len(a.s._MODEL_RECEIPTS));self.assertTrue(self.files.output.closed)
        self.api.k.DeleteFileW.assert_not_called()
    def test_close_and_journal_failure_preserve_primary(self):
        original=KeyboardInterrupt('PRIVATE')
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.run_prepared(launch_error=original,close_error=OSError('CLOSE'),journal_error=True)
        self.assertIs(caught.exception,original);self.assertEqual(original.evidence_status,'INCOMPLETE')
        self.assertIn('OUTPUT_CLOSE_INCOMPLETE',original.cleanup_codes)
    def test_private_native_prompt_configuration_without_launch(self):
        with patch.object(a.n,'blocked',return_value=None),patch.object(a.sys,'stdin',Mock(isatty=Mock(return_value=True))),patch.object(a.subprocess,'Popen') as launch:
            self.process._launch(self.f.recipe.argv,42)
            args,kwargs=launch.call_args
            self.assertIsNone(kwargs['stdin']);self.assertFalse(kwargs['shell']);self.assertTrue(kwargs['close_fds'])
            self.assertEqual(args[0],list(self.f.recipe.argv));self.assertIn('--password',args[0])
            self.assertNotIn('env',kwargs)
        with patch.object(a.n,'blocked',return_value=None),patch.object(a.sys,'stdin',Mock(isatty=Mock(return_value=False))),patch.object(a.subprocess,'Popen') as launch:
            with self.assertRaises(a.p.Stop):self.process._launch(self.f.recipe.argv,42)
            launch.assert_not_called()
    def preparation_failure(self,code,*,close_fails=True,journal_fails=False):
        primary=a.w.WindowsIOBlocked(code)
        opened=[];original_open=self.api.open.side_effect
        def open_handle(*args,**kwargs):
            handle=original_open(*args,**kwargs);opened.append(handle)
            if close_fails:handle.close.side_effect=OSError('PRIVATE_CLEANUP')
            return handle
        def security_failure(*args,**kwargs):raise primary
        self.api.open.side_effect=open_handle;self.api.facts.side_effect=security_failure
        before=len(a.s._MODEL_RECEIPTS)
        frames=[]
        with patch.object(self.process,'_stdout_fd') as duplicate,patch.object(self.process,'_launch') as launch:
            try:self.run_prepared(journal_error=journal_fails)
            except a.w.WindowsIOBlocked as caught:
                self.assertIs(caught,primary)
                tb=caught.__traceback__
                while tb is not None:frames.append(tb.tb_frame.f_code.co_name);tb=tb.tb_next
            else:self.fail('Preparation failure was not propagated')
            duplicate.assert_not_called();launch.assert_not_called()
        self.assertIn('security_failure',frames)
        self.assertEqual(before,len(a.s._MODEL_RECEIPTS))
        self.assertTrue(opened)
        for handle in opened:handle.close.assert_called_once()
        if close_fails:
            self.assertEqual(primary.cleanup_status,'INCOMPLETE')
            self.assertIn('OUTPUT_CLOSE_INCOMPLETE',primary.cleanup_codes)
            replacement=a.WindowsStdoutFiles()
            self.assertIn((self.f.recipe.attempt_id,self.f.recipe.job_sha256),a._INCOMPLETE_OUTPUT_JOBS)
            with patch.object(replacement,'_api') as api,self.assertRaises(a.p.Stop):
                replacement.prepare(self.f.recipe,'OPERATOR')
            api.assert_not_called()
        else:self.assertTrue(all(handle.closed for handle in opened))
        self.assertEqual(primary.evidence_status,'INCOMPLETE' if journal_fails else 'PRESERVED_OFFLINE_JOURNAL')
        if not journal_fails:
            raw=(self.f.root/(self.f.recipe.attempt_id+'.failure.json')).read_bytes();record=json.loads(raw)
            self.assertEqual(record['stdout_phase'],'CREATE_NEW')
            self.assertEqual(record['binding'],self.f.binding)
            self.assertEqual(record['cleanup_codes'],['OUTPUT_CLOSE_INCOMPLETE'] if close_fails else [])
            self.assertNotIn(b'PRIVATE_CLEANUP',raw)
        with self.assertRaises(a.p.Stop):a.p.FilesystemConsumptionStore(self.f.root).consume_stdout_launch(self.f.binding)
    def test_acl_preparation_and_close_failure(self):self.preparation_failure('HANDLE_OWNER_OR_DACL_INVALID')
    def test_reparse_preparation_and_close_failure(self):self.preparation_failure('HANDLE_REPARSE_OR_DEVICE')
    def test_handle_preparation_and_close_failure(self):self.preparation_failure('FINAL_PATH_MISMATCH')
    def test_preparation_failure_successful_cleanup(self):self.preparation_failure('HANDLE_OWNER_OR_DACL_INVALID',close_fails=False)
    def test_preparation_cleanup_and_journal_failure(self):self.preparation_failure('HANDLE_REPARSE_OR_DEVICE',journal_fails=True)
    def test_preparation_cleanup_failure_does_not_block_independent_job(self):
        self.preparation_failure('FINAL_PATH_MISMATCH')
        other=CompletionTests('test_full_integration_issues_only_model_receipt');other.setUp()
        self.addCleanup(other.doCleanups)
        receipt=other.run_prepared()
        self.assertEqual(a.s.model_receipt_record(receipt)['status'],'MODEL_ONLY_NOT_NATIVE_BACKUP')
    def test_same_handle_read_algorithm_without_win32(self):
        self.files.api=self.api;self.files.output=Mock(value=987,closed=False)
        data=b'INDEPENDENT_BYTES';seen=[]
        def size(handle,out):seen.append(handle);out._obj.value=len(data);return True
        def seek(handle,offset,out,origin):seen.append(handle);out._obj.value=0;return True
        def read(handle,buffer,length,out,overlap):seen.append(handle);ctypes.memmove(buffer,data,len(data));out._obj.value=len(data);return True
        self.api.k.GetFileSizeEx.side_effect=size;self.api.k.SetFilePointerEx.side_effect=seek;self.api.k.ReadFile.side_effect=read
        with patch.object(a.n,'blocked',return_value=None):self.assertEqual(self.files._read_native(),data)
        self.assertTrue(all(value==987 for value in seen));self.api.open.assert_not_called()
    def test_same_handle_short_read_fails_closed(self):
        self.files.api=self.api;self.files.output=Mock(value=987,closed=False)
        def size(handle,out):out._obj.value=10;return True
        def seek(handle,offset,out,origin):out._obj.value=0;return True
        self.api.k.GetFileSizeEx.side_effect=size;self.api.k.SetFilePointerEx.side_effect=seek
        self.api.k.ReadFile.return_value=False
        with patch.object(a.n,'blocked',return_value=None),self.assertRaisesRegex(a.p.Stop,'OUTPUT_SHORT_READ'):
            self.files._read_native()
    def test_native_boundaries_still_block(self):
        with patch.object(a.subprocess,'Popen') as launch,patch.object(a.w,'_Win32') as win:
            for call in (lambda:self.adapter.run(),lambda:self.adapter.issue_native_receipt(),lambda:self.files._read_native()):
                with self.assertRaises(a.p.Stop):call()
            launch.assert_not_called();win.assert_not_called()

if __name__=='__main__':unittest.main()

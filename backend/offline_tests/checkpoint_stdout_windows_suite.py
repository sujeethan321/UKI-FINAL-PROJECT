"""Offline-only native primitive review: no Win32 calls or real subprocesses."""
import importlib.util
from pathlib import Path
import sys
import io
import unittest
from unittest.mock import Mock,patch
from contextlib import nullcontext

spec=importlib.util.spec_from_file_location('stdout_windows_fixture',Path(__file__).with_name('checkpoint_stdout_suite.py'))
fixture=importlib.util.module_from_spec(spec);sys.modules[spec.name]=fixture;spec.loader.exec_module(fixture)
sys.modules['_lankapex_checkpoint_stdout']=fixture.s
spec=importlib.util.spec_from_file_location('stdout_windows_test',Path(__file__).resolve().parents[1]/'scripts/checkpoint_stdout_windows.py')
a=importlib.util.module_from_spec(spec);sys.modules[spec.name]=a;spec.loader.exec_module(a)

class NativeStdoutTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.StdoutTests('test_existing_output_no_overwrite_or_process');self.base.setUp()
        self.addCleanup(self.base.doCleanups);self.recipe=self.base.recipe
    def api(self):
        api=Mock();api.security.return_value=nullcontext('PRIVATE_DESCRIPTOR')
        api.open.side_effect=lambda *args,**kwargs:Mock(closed=False,value=123)
        return api
    def prepared(self):
        files=a.WindowsStdoutFiles()
        with patch.object(files,'_api',return_value=self.api()):files.prepare(self.recipe,'OPERATOR')
        self.addCleanup(files.close)
        return files
    def test_create_new_exact_path_and_parent_owner(self):
        api=self.api();files=a.WindowsStdoutFiles()
        with patch.object(files,'_api',return_value=api):handle=files.prepare(self.recipe,'OPERATOR')
        self.assertIs(handle,files.output)
        self.assertEqual(api.open.call_args.kwargs,dict(create=True,security='PRIVATE_DESCRIPTOR'))
        self.assertEqual(str(api.open.call_args.args[0]),self.recipe.output_path)
        self.assertTrue(any(c.kwargs.get('directory') and c.kwargs.get('owner')=='OPERATOR' for c in api.facts.call_args_list))
        files.close();handle.close.assert_called_once()
    def test_existing_output_failure_preserves_no_cleanup(self):
        api=self.api();opened=[]
        def open_handle(*args,**kwargs):
            if kwargs.get('create'):raise a.p.Stop('EXISTS')
            handle=Mock(closed=False);opened.append(handle);return handle
        api.open.side_effect=open_handle;files=a.WindowsStdoutFiles()
        with patch.object(files,'_api',return_value=api),self.assertRaisesRegex(a.p.Stop,'EXISTS'):
            files.prepare(self.recipe,'OPERATOR')
        for handle in opened:handle.close.assert_called_once()
        self.assertIsNone(files.output)
    def test_facts_failure_closes_immediately_owned_handle(self):
        api=self.api();handle=Mock(closed=False);api.open.side_effect=None;api.open.return_value=handle
        api.facts.side_effect=a.p.Stop('REPARSE_OR_ACL');files=a.WindowsStdoutFiles()
        with patch.object(files,'_api',return_value=api),self.assertRaises(a.p.Stop):files.prepare(self.recipe,'OPERATOR')
        handle.close.assert_called_once();self.assertEqual(api.open.call_count,1)
    def test_mutated_recipe_rejected_before_filesystem(self):
        files=a.WindowsStdoutFiles()
        object.__setattr__(self.recipe,'output_path',r'C:\Other\viva.sql')
        with patch.object(files,'_api') as api,self.assertRaises(a.p.Stop):files.prepare(self.recipe,'OPERATOR')
        api.assert_not_called()
    def test_stderr_bounded_and_redacted(self):
        stream=io.BytesIO(b'PRIVATE_PASSWORD'*10000);drain=a.BoundedStderr(16384);drain.drain(stream)
        self.assertTrue(stream.closed);self.assertEqual(drain.report()['retained_bytes'],0)
        self.assertEqual(drain.count,16384);self.assertTrue(drain.truncated)
        self.assertNotIn('PRIVATE',str(drain.report()))
    def dispatch(self,code=0,wait_error=None,flush_error=None,launch_error=None):
        process=a.WindowsStdoutProcess();files=self.prepared();files.flush=Mock();child=Mock()
        child.stderr=io.BytesIO(b'REDACTED');child.wait.return_value=code;child.poll.return_value=code
        if wait_error:
            child.wait.side_effect=[wait_error,0];child.poll.return_value=None
        if flush_error:files.flush.side_effect=flush_error
        with patch.object(process,'_stdout_fd',return_value=42),patch.object(process,'_launch',return_value=child,side_effect=launch_error) as launch,patch.object(a.os,'close') as close:
            if wait_error or flush_error or launch_error or code:
                expected=type(wait_error or flush_error or launch_error) if (wait_error or flush_error or launch_error) else a.p.Stop
                with self.assertRaises(expected):process.dispatch(self.recipe,files,'OPERATOR')
            else:
                report=process.dispatch(self.recipe,files,'OPERATOR');self.assertEqual(report['retained_bytes'],0)
                launch.assert_called_once_with(self.recipe.argv,42);files.flush.assert_called_once_with('OPERATOR')
            close.assert_called_once_with(42)
        return child,files
    def test_dispatch_success_same_argv_and_owned_handle(self):self.dispatch()
    def test_nonzero_fails_without_flush(self):
        _,files=self.dispatch(code=1);files.flush.assert_not_called()
    def test_interruption_reaps_child(self):
        child,files=self.dispatch(wait_error=KeyboardInterrupt());child.kill.assert_called_once();files.flush.assert_not_called()
    def test_launch_failure_closes_descriptor(self):self.dispatch(launch_error=OSError('FICTIONAL'))
    def test_timeout_reaps_child_without_success(self):
        child,files=self.dispatch(wait_error=a.subprocess.TimeoutExpired('FICTIONAL',300))
        child.kill.assert_called_once();files.flush.assert_not_called()
    def test_stderr_read_failure_is_flagged(self):
        stream=Mock();stream.read.side_effect=OSError('FICTIONAL_SECRET')
        drain=a.BoundedStderr(16384);drain.drain(stream)
        self.assertTrue(drain.failed);stream.close.assert_called_once()
        self.assertNotIn('SECRET',str(drain.report()))
    def test_flush_failure_is_unsuccessful(self):self.dispatch(flush_error=a.p.Stop('FLUSH_FAILED'))
    def test_job_a_output_rejects_genuine_job_b(self):
        files=self.prepared()
        other=fixture.StdoutTests('test_existing_output_no_overwrite_or_process');other.setUp()
        self.addCleanup(other.doCleanups)
        process=a.WindowsStdoutProcess()
        with patch.object(process,'_stdout_fd') as duplicate,patch.object(process,'_launch') as launch:
            with self.assertRaisesRegex(a.p.Stop,'OUTPUT_JOB_BINDING_MISMATCH'):
                process.dispatch(other.recipe,files,'OPERATOR')
            duplicate.assert_not_called();launch.assert_not_called()
    def test_changed_attempt_destination_and_output_handle_rejected(self):
        files=self.prepared();process=a.WindowsStdoutProcess()
        for field,new in (('attempt_id','checkpoint-'+'f'*32),('output_path',r'C:\Other\viva.sql')):
            original=getattr(self.recipe,field)
            try:
                object.__setattr__(self.recipe,field,new)
                with patch.object(process,'_stdout_fd') as duplicate,self.assertRaises(a.p.Stop):
                    process.dispatch(self.recipe,files,'OPERATOR')
                duplicate.assert_not_called()
            finally:object.__setattr__(self.recipe,field,original)
        original=files.output;files.output=Mock(closed=False,value=123)
        with patch.object(process,'_stdout_fd') as duplicate,self.assertRaisesRegex(a.p.Stop,'HANDLE_SUBSTITUTED'):
            process.dispatch(self.recipe,files,'OPERATOR')
        duplicate.assert_not_called();files.output=original
        original_value=files.output.value;files.output.value=456
        with self.assertRaisesRegex(a.p.Stop,'HANDLE_SUBSTITUTED'):files.verify_binding(self.recipe,'OPERATOR')
        files.output.value=original_value
        original_path=files.path;files.path=a.p.PureWindowsPath(r'C:\Other\viva.sql')
        with self.assertRaisesRegex(a.p.Stop,'BINDING_MISMATCH'):files.verify_binding(self.recipe,'OPERATOR')
        files.path=original_path
    def test_thread_start_failure_never_joins_unstarted_reader(self):
        files=self.prepared();process=a.WindowsStdoutProcess();child=Mock();child.poll.return_value=None
        child.stderr=io.BytesIO();thread=Mock();original=RuntimeError('FICTIONAL_THREAD_START')
        thread.start.side_effect=original
        with patch.object(process,'_stdout_fd',return_value=42),patch.object(process,'_launch',return_value=child),patch.object(a.threading,'Thread',return_value=thread),patch.object(a.os,'close'):
            with self.assertRaises(RuntimeError) as caught:process.dispatch(self.recipe,files,'OPERATOR')
        self.assertIs(caught.exception,original);self.assertEqual(original.cleanup_status,'COMPLETE')
        thread.join.assert_not_called();child.kill.assert_called_once();self.assertTrue(child.stderr.closed)
    def test_blocked_reader_cancellation_and_original_failure(self):
        for cancellation_works in (True,False):
            with self.subTest(cancellation_works=cancellation_works):
                files=self.prepared();process=a.WindowsStdoutProcess();files.flush=Mock()
                child=Mock();child.poll.return_value=None;original=KeyboardInterrupt()
                child.wait.side_effect=[original,0];child.stderr=io.BytesIO()
                thread=Mock();thread.is_alive.return_value=True
                def cancel(_):
                    if cancellation_works:thread.is_alive.return_value=False
                    else:raise a.p.Stop('CANCEL_FAILED')
                with patch.object(process,'_stdout_fd',return_value=42),patch.object(process,'_launch',return_value=child),patch.object(process,'_cancel_reader',side_effect=cancel) as cancellation,patch.object(a.threading,'Thread',return_value=thread),patch.object(a.os,'close'):
                    with self.assertRaises(KeyboardInterrupt) as caught:process.dispatch(self.recipe,files,'OPERATOR')
                self.assertIs(caught.exception,original);cancellation.assert_called_once_with(thread)
                self.assertEqual(original.cleanup_status,'COMPLETE' if cancellation_works else 'INCOMPLETE')
                files.flush.assert_not_called()
                if not cancellation_works:
                    self.assertIn('STDERR_READER_INCOMPLETE',original.cleanup_codes)
                    with self.assertRaisesRegex(a.p.Stop,'PREVIOUS_CLEANUP_INCOMPLETE'):process.dispatch(self.recipe,files,'OPERATOR')
    def test_incomplete_descriptor_cleanup_prevents_success(self):
        files=self.prepared();files.flush=Mock();process=a.WindowsStdoutProcess();child=Mock()
        child.stderr=io.BytesIO();child.poll.return_value=0;child.wait.return_value=0
        with patch.object(process,'_stdout_fd',return_value=42),patch.object(process,'_launch',return_value=child),patch.object(a.os,'close',side_effect=OSError('PRIVATE')):
            with self.assertRaisesRegex(a.p.Stop,'CLEANUP_INCOMPLETE') as caught:process.dispatch(self.recipe,files,'OPERATOR')
        self.assertEqual(caught.exception.cleanup_status,'INCOMPLETE')
        self.assertIn('STDOUT_DESCRIPTOR_CLOSE_INCOMPLETE',caught.exception.cleanup_codes)
        files.flush.assert_not_called()
    def test_incomplete_cleanup_blocks_fresh_wrapper_but_not_unrelated_job(self):
        files=self.prepared();process=a.WindowsStdoutProcess();child=Mock()
        original=KeyboardInterrupt();child.wait.side_effect=[original,0]
        child.poll.return_value=None;child.stderr=io.BytesIO();thread=Mock()
        thread.is_alive.return_value=True
        with patch.object(process,'_stdout_fd',return_value=42),patch.object(process,'_launch',return_value=child),patch.object(process,'_cancel_reader',side_effect=a.p.Stop('CANCEL_FAILED')),patch.object(a.threading,'Thread',return_value=thread),patch.object(a.os,'close'):
            with self.assertRaises(KeyboardInterrupt) as caught:process.dispatch(self.recipe,files,'OPERATOR')
        self.assertIs(caught.exception,original)
        self.assertEqual(original.cleanup_status,'INCOMPLETE')
        diagnostics=original.cleanup_codes
        self.assertIn('STDERR_READER_INCOMPLETE',diagnostics)
        for wrapper in (a.WindowsStdoutProcess(),a.WindowsStdoutProcess()):
            with patch.object(wrapper,'_stdout_fd') as duplicate,patch.object(wrapper,'_launch') as launch:
                with self.assertRaisesRegex(a.p.Stop,'OUTPUT_ATTEMPT_CLEANUP_INCOMPLETE'):
                    wrapper.dispatch(self.recipe,files,'OPERATOR')
                duplicate.assert_not_called();launch.assert_not_called()
        # A replacement prepared-output object cannot clear the attempt latch.
        replacement=a.WindowsStdoutFiles()
        with patch.object(replacement,'_api') as api,self.assertRaisesRegex(a.p.Stop,'OUTPUT_ATTEMPT_CLEANUP_INCOMPLETE'):
            replacement.prepare(self.recipe,'OPERATOR')
        api.assert_not_called()
        # Independently issued job and output still dispatch successfully.
        other=fixture.StdoutTests('test_existing_output_no_overwrite_or_process');other.setUp()
        self.addCleanup(other.doCleanups);unrelated=a.WindowsStdoutFiles()
        with patch.object(unrelated,'_api',return_value=self.api()):unrelated.prepare(other.recipe,'OPERATOR')
        self.addCleanup(unrelated.close);unrelated.flush=Mock()
        wrapper=a.WindowsStdoutProcess();completed=Mock()
        completed.stderr=io.BytesIO();completed.wait.return_value=0;completed.poll.return_value=0
        with patch.object(wrapper,'_stdout_fd',return_value=43) as duplicate,patch.object(wrapper,'_launch',return_value=completed) as launch,patch.object(a.os,'close'):
            wrapper.dispatch(other.recipe,unrelated,'OPERATOR')
            duplicate.assert_called_once_with(unrelated.output)
            launch.assert_called_once_with(other.recipe.argv,43)
        self.assertIs(caught.exception,original);self.assertEqual(original.cleanup_codes,diagnostics)
        self.assertEqual(original.cleanup_status,'INCOMPLETE')
    def test_all_native_boundaries_unconditional(self):
        with patch.object(a.subprocess,'Popen') as spawn,patch.object(a.w,'_Win32') as win:
            for call in (lambda:a.WindowsStdoutFiles()._api(),lambda:a.WindowsStdoutProcess()._stdout_fd(Mock()),
                         lambda:a.WindowsStdoutProcess()._launch([],42),lambda:a.WindowsStdoutProcess()._cancel_reader(Mock()),lambda:a.NativeWindowsStdoutAdapter().run(),
                         lambda:a.NativeWindowsStdoutAdapter().issue_native_receipt(self.base.run_output())):
                with self.assertRaisesRegex(a.p.Stop,'NATIVE_CHECKPOINT_EXECUTION_DISABLED'):call()
            spawn.assert_not_called();win.assert_not_called()

if __name__=='__main__':unittest.main()

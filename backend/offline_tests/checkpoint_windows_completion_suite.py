"""Windows-native checks ONLY inside issuer-created disposable test roots."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import Mock,patch,call

spec=importlib.util.spec_from_file_location('checkpoint_windows_completion',Path(__file__).resolve().parents[1]/'scripts/checkpoint_windows_io.py')
io=importlib.util.module_from_spec(spec);sys.modules[spec.name]=io;spec.loader.exec_module(io)

class HandleCleanupTests(unittest.TestCase):
    """No native calls, temporary directories, ACL operations or provisioning."""
    def setUp(self):
        self.root=object.__new__(io.IsolatedTestRoot)
        io._TEST_ROOTS[id(self.root)]=(self.root,Path('C:/Fictional/CheckpointTest'))
        self.addCleanup(io._TEST_ROOTS.pop,id(self.root),None)
        self.kernel=Mock();self.kernel.CloseHandle.return_value=True
        self.api=Mock();self.api.operator_sid.return_value='S-1-5-21-1-2-3-1001'
    def test_first_facts_failure_closes_newly_opened_handle(self):
        handle=io.Handle(self.kernel,101);self.api.open.return_value=handle
        error=io.WindowsIOBlocked('FICTIONAL_FACTS_FAILURE');self.api.facts.side_effect=error
        with patch.object(io,'_Win32',return_value=self.api),self.assertRaises(io.WindowsIOBlocked) as caught:
            io.IsolatedWindowsFiles(self.root)
        self.assertIs(caught.exception,error);self.assertTrue(handle.closed)
        self.kernel.CloseHandle.assert_called_once_with(101)
        self.api.open.assert_called_once();self.api.facts.assert_called_once()
    def test_later_facts_failure_closes_current_and_previous_in_reverse_order(self):
        first=io.Handle(self.kernel,101);second=io.Handle(self.kernel,102)
        self.api.open.side_effect=[first,second]
        self.api.facts.side_effect=[None,io.WindowsIOBlocked('FICTIONAL_FACTS_FAILURE')]
        with patch.object(io,'_Win32',return_value=self.api),self.assertRaises(io.WindowsIOBlocked):
            io.IsolatedWindowsFiles(self.root)
        self.assertTrue(first.closed and second.closed)
        self.assertEqual(self.kernel.CloseHandle.call_args_list,[call(102),call(101)])
        self.assertEqual(self.api.open.call_count,2)
    def test_open_failure_closes_only_already_owned_handles(self):
        first=io.Handle(self.kernel,101)
        self.api.open.side_effect=[first,io.WindowsIOBlocked('FICTIONAL_OPEN_FAILURE')]
        with patch.object(io,'_Win32',return_value=self.api),self.assertRaises(io.WindowsIOBlocked):
            io.IsolatedWindowsFiles(self.root)
        self.kernel.CloseHandle.assert_called_once_with(101);self.assertTrue(first.closed)
    def test_production_methods_remain_unconditionally_blocked(self):
        with patch.object(io,'_Win32',side_effect=AssertionError('NO_NATIVE_CALLS')):
            for method in ('provision','create_file','directory_durability'):
                with self.assertRaises(io.WindowsIOBlocked):getattr(io.ProductionWindowsFiles(),method)(approved=True)

@unittest.skipUnless(os.name=='nt','Windows-native guarantees require Windows')
class WindowsCompletionTests(unittest.TestCase):
    @contextmanager
    def files(self,root):
        try:owned=io.IsolatedWindowsFiles(root)
        except io.WindowsIOBlocked as error:
            if str(error)=='EXCLUSIVE_OPEN_FAILED_WIN32_5':
                self.skipTest('BLOCKED: required ancestor handle access denied; no weaker fallback')
            raise
        try:yield owned
        finally:owned.close()
    def test_actual_exclusive_directory_file_acl_and_flush(self):
        with io.isolated_test_root() as root:
            with self.files(root) as files:
                directory=files.child('private-child',directory=True);files.verify(directory)
                output=files.child('output.bin');files.write(output,b'FICTIONAL NONDATABASE OUTPUT')
                files.verify(output)
                with self.assertRaises(io.WindowsIOBlocked):files.child('output.bin')
                with self.assertRaises(io.WindowsIOBlocked):files.child('private-child',directory=True)
    def test_traversal_ads_and_device_names(self):
        with io.isolated_test_root() as root:
            with self.files(root) as files:
                for name in ('../escape','a:stream','C:\\escape','con','nul','\\\\?\\C:\\escape','sub/file','trailing.'):
                    with self.assertRaises(io.WindowsIOBlocked):files.child(name)
    def test_parent_rename_rejected_while_handles_owned(self):
        with io.isolated_test_root() as root:
            original,path=io._TEST_ROOTS[id(root)]
            with self.files(root):
                with self.assertRaises(OSError):os.rename(path,path.with_name(path.name+'-moved'))
    def test_ownership_and_closed_handle_rejected(self):
        with io.isolated_test_root() as root:
            with self.files(root) as files:
                handle=files.child('closed.bin');handle.close()
                with self.assertRaises(io.WindowsIOBlocked):files.write(handle,b'x')
    def test_reparse_bit_rejected_on_held_handle(self):
        # Real metadata retrieval; alter only the observed attribute bit in memory.
        from unittest.mock import patch
        import ctypes
        with io.isolated_test_root() as root:
            with self.files(root) as files:
                handle=files.child('fixture.bin');original=files.api.k.GetFileInformationByHandle
                def reparse(value,pointer):
                    result=original(value,pointer)
                    ctypes.cast(pointer,ctypes.POINTER(io._INFO)).contents.attributes|=0x400
                    return result
                with patch.object(files.api.k,'GetFileInformationByHandle',side_effect=reparse):
                    with self.assertRaises(io.WindowsIOBlocked):files.verify(handle)
    def test_production_and_power_loss_guarantees_blocked(self):
        for method in ('provision','create_file','directory_durability'):
            with self.assertRaises(io.WindowsIOBlocked):getattr(io.ProductionWindowsFiles(),method)(approved=True)
        with self.assertRaises(io.WindowsIOBlocked):io.IsolatedWindowsFiles(Path('C:/Private'))

if __name__=='__main__':unittest.main()

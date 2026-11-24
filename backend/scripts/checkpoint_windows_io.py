"""Windows handle implementation; real checkpoint provisioning remains blocked.

The only enabled native exercise is restricted to an issuer-created disposable
test root. No CLI/environment flag activates production provisioning.
"""
import ctypes as c
from ctypes import wintypes as w
from contextlib import contextmanager
from pathlib import Path, PureWindowsPath
import os
import re
import tempfile

class WindowsIOBlocked(RuntimeError):
    def __init__(self,code,*,operation=None,winerror=None):
        super().__init__(code)
        self.operation=operation;self.winerror=winerror
def need(value,code):
    if not value:raise WindowsIOBlocked(code)

def win_need(value,code,operation,*,winerror=None):
    # Capture before cleanup can overwrite the thread-local Win32 last error.
    if not value:raise WindowsIOBlocked(code,operation=operation,winerror=c.get_last_error() if winerror is None else winerror)

_TEST_ROOTS={}
class IsolatedTestRoot:
    __slots__=()
    def __new__(cls):raise WindowsIOBlocked('ISOLATED_TEST_ROOT_ISSUER_REQUIRED')

@contextmanager
def isolated_test_root():
    """Explicitly authorized disposable native-test directory only, never a backup."""
    need(os.name=='nt','WINDOWS_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='lankapex-native-test-') as name:
        value=object.__new__(IsolatedTestRoot);_TEST_ROOTS[id(value)]=(value,Path(name))
        try:yield value
        finally:_TEST_ROOTS.pop(id(value),None)

class _SA(c.Structure):
    _fields_=[('length',w.DWORD),('descriptor',c.c_void_p),('inherit',w.BOOL)]
class _INFO(c.Structure):
    _fields_=[('attributes',w.DWORD),('created',w.FILETIME),('accessed',w.FILETIME),('written',w.FILETIME),
              ('volume',w.DWORD),('size_high',w.DWORD),('size_low',w.DWORD),('links',w.DWORD),('index_high',w.DWORD),('index_low',w.DWORD)]
class _ACL(c.Structure):
    _fields_=[('revision',w.BYTE),('reserved',w.BYTE),('size',w.WORD),('count',w.WORD),('reserved2',w.WORD)]

class Handle:
    def __init__(self,kernel,value):self._kernel=kernel;self.value=value;self.closed=False
    def close(self):
        if not self.closed:
            win_need(self._kernel.CloseHandle(self.value),'CLOSE_HANDLE_FAILED','CloseHandle');self.closed=True
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

class _Win32:
    def __init__(self):
        need(os.name=='nt','WINDOWS_REQUIRED')
        self.k=c.WinDLL('kernel32',use_last_error=True);self.a=c.WinDLL('advapi32',use_last_error=True)
        def bind(lib,name,args,result):
            function=getattr(lib,name);function.argtypes=args;function.restype=result
        bind(self.k,'CreateFileW',[w.LPCWSTR,w.DWORD,w.DWORD,c.POINTER(_SA),w.DWORD,w.DWORD,w.HANDLE],w.HANDLE)
        bind(self.k,'CloseHandle',[w.HANDLE],w.BOOL)
        bind(self.k,'CreateDirectoryW',[w.LPCWSTR,c.POINTER(_SA)],w.BOOL)
        bind(self.k,'GetFileInformationByHandle',[w.HANDLE,c.POINTER(_INFO)],w.BOOL)
        bind(self.k,'GetFinalPathNameByHandleW',[w.HANDLE,w.LPWSTR,w.DWORD,w.DWORD],w.DWORD)
        bind(self.k,'GetFileType',[w.HANDLE],w.DWORD)
        bind(self.k,'WriteFile',[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p],w.BOOL)
        bind(self.k,'FlushFileBuffers',[w.HANDLE],w.BOOL)
        bind(self.k,'LocalFree',[c.c_void_p],c.c_void_p)
        bind(self.k,'GetCurrentProcess',[],w.HANDLE)
        bind(self.a,'OpenProcessToken',[w.HANDLE,w.DWORD,c.POINTER(w.HANDLE)],w.BOOL)
        bind(self.a,'GetTokenInformation',[w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)],w.BOOL)
        bind(self.a,'ConvertSidToStringSidW',[c.c_void_p,c.POINTER(w.LPWSTR)],w.BOOL)
        bind(self.a,'ConvertStringSecurityDescriptorToSecurityDescriptorW',[w.LPCWSTR,w.DWORD,c.POINTER(c.c_void_p),c.POINTER(w.ULONG)],w.BOOL)
        bind(self.a,'GetSecurityInfo',[w.HANDLE,c.c_int,w.DWORD,c.POINTER(c.c_void_p),c.POINTER(c.c_void_p),c.POINTER(c.c_void_p),c.POINTER(c.c_void_p),c.POINTER(c.c_void_p)],w.DWORD)
        bind(self.a,'GetSecurityDescriptorControl',[c.c_void_p,c.POINTER(w.WORD),c.POINTER(w.DWORD)],w.BOOL)
        bind(self.a,'GetAce',[c.c_void_p,w.DWORD,c.POINTER(c.c_void_p)],w.BOOL)
    def sid(self,pointer):
        text=w.LPWSTR();win_need(self.a.ConvertSidToStringSidW(pointer,c.byref(text)),'SID_READ_FAILED','ConvertSidToStringSidW')
        try:return text.value
        finally:self.k.LocalFree(c.cast(text,c.c_void_p))
    def operator_sid(self):
        token=w.HANDLE();win_need(self.a.OpenProcessToken(self.k.GetCurrentProcess(),8,c.byref(token)),'TOKEN_READ_FAILED','OpenProcessToken')
        try:
            size=w.DWORD();self.a.GetTokenInformation(token,1,None,0,c.byref(size));need(0<size.value<=65536,'TOKEN_SIZE_INVALID')
            buffer=c.create_string_buffer(size.value)
            win_need(self.a.GetTokenInformation(token,1,buffer,size,c.byref(size)),'TOKEN_READ_FAILED','GetTokenInformation')
            return self.sid(c.c_void_p.from_buffer(buffer).value)
        finally:self.k.CloseHandle(token)
    @contextmanager
    def security(self,sid,directory):
        flags='OICI' if directory else ''
        descriptor=c.c_void_p();sddl='O:'+sid+'D:P(A;'+flags+';FA;;;'+sid+')(A;'+flags+';FA;;;SY)'
        win_need(self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,c.byref(descriptor),None),'SECURITY_DESCRIPTOR_FAILED','ConvertStringSecurityDescriptorToSecurityDescriptorW')
        try:yield _SA(c.sizeof(_SA),descriptor,False)
        finally:self.k.LocalFree(descriptor)
    def open(self,path,*,create=False,security=None,directory=False,read_acl=True):
        access=0xC0020000 if create else 0x80|(0x20000 if read_acl else 0)
        flags=0x00200000|(0x02000000 if directory else 0x80000000 if create else 0)
        raw=self.k.CreateFileW(str(path),access,0 if create else 3,c.byref(security) if security else None,1 if create else 3,flags,None)
        if raw==c.c_void_p(-1).value:
            error=c.get_last_error()
            raise WindowsIOBlocked('EXCLUSIVE_OPEN_FAILED_WIN32_'+str(error),operation='CreateFileW',winerror=error)
        return Handle(self.k,raw)
    def facts(self,handle,path,*,directory,owner=None):
        need(not handle.closed,'CLOSED_HANDLE')
        info=_INFO();win_need(self.k.GetFileInformationByHandle(handle.value,c.byref(info)),'HANDLE_METADATA_FAILED','GetFileInformationByHandle')
        need(self.k.GetFileType(handle.value)==1 and not info.attributes&0x400,'HANDLE_REPARSE_OR_DEVICE')
        need(bool(info.attributes&0x10)==directory and (directory or info.links==1),'HANDLE_TYPE_OR_LINKS_INVALID')
        buffer=c.create_unicode_buffer(32768);length=self.k.GetFinalPathNameByHandleW(handle.value,buffer,len(buffer),0)
        win_need(0<length<len(buffer),'FINAL_PATH_FAILED','GetFinalPathNameByHandleW');actual=buffer.value
        need(actual.startswith('\\\\?\\') and not actual.startswith('\\\\?\\UNC\\'),'FINAL_PATH_NOT_LOCAL')
        need(PureWindowsPath(actual[4:])==PureWindowsPath(path),'FINAL_PATH_MISMATCH')
        if owner is None:return
        sid=c.c_void_p();dacl=c.c_void_p();sd=c.c_void_p()
        status=self.a.GetSecurityInfo(handle.value,1,5,c.byref(sid),None,c.byref(dacl),None,c.byref(sd))
        win_need(status==0,'HANDLE_ACL_READ_FAILED','GetSecurityInfo',winerror=status)
        try:
            need(self.sid(sid)==owner and bool(dacl.value),'HANDLE_OWNER_OR_DACL_INVALID')
            control=w.WORD();revision=w.DWORD()
            win_need(self.a.GetSecurityDescriptorControl(sd,c.byref(control),c.byref(revision)),'DACL_CONTROL_READ_FAILED','GetSecurityDescriptorControl')
            need(control.value&0x1000,'DACL_NOT_PROTECTED')
            acl=c.cast(dacl,c.POINTER(_ACL)).contents;need(acl.count==2,'EXTRA_ACES')
            seen=[]
            for index in range(acl.count):
                ace=c.c_void_p();win_need(self.a.GetAce(dacl,index,c.byref(ace)),'ACE_READ_FAILED','GetAce')
                header=c.string_at(ace,4)
                need(header[0]==0 and header[1]==(3 if directory else 0),'ACE_TYPE_OR_INHERITANCE_INVALID')
                mask=c.c_uint32.from_address(ace.value+4).value
                need(mask==0x1F01FF,'ACE_RIGHTS_INVALID');seen.append(self.sid(ace.value+8))
            need(set(seen)=={owner,'S-1-5-18'},'ACE_IDENTITIES_INVALID')
        finally:self.k.LocalFree(sd)
    def write_and_flush(self,handle,data):
        need(type(data) is bytes and not handle.closed,'INVALID_WRITE')
        for offset in range(0,len(data),1024*1024):
            chunk=data[offset:offset+1024*1024];buffer=c.create_string_buffer(chunk);written=w.DWORD()
            win_need(self.k.WriteFile(handle.value,buffer,len(chunk),c.byref(written),None),'WRITE_FILE_FAILED','WriteFile')
            need(written.value==len(chunk),'SHORT_WRITE_PRESERVE_STATE')
        win_need(self.k.FlushFileBuffers(handle.value),'FILE_FLUSH_FAILED','FlushFileBuffers')

class IsolatedWindowsFiles:
    """Exercises the native algorithm only under a disposable issued test root."""
    def __init__(self,root):
        need(type(root) is IsolatedTestRoot and id(root) in _TEST_ROOTS,'TEST_ROOT_REQUIRED')
        original,path=_TEST_ROOTS[id(root)];need(original is root,'TEST_ROOT_IDENTITY_MISMATCH')
        self.root=path;self.api=_Win32();self.sid=self.api.operator_sid();self.handles=[];self.paths={}
        try:
            for ancestor in reversed((path,*path.parents)):
                handle=self.api.open(ancestor,directory=True,read_acl=False)
                # Own immediately: facts() may raise before validation completes.
                self.handles.append(handle)
                self.api.facts(handle,ancestor,directory=True)
        except BaseException:self.close();raise
    def child(self,name,directory=False):
        need(re.fullmatch(r'[a-z][a-z0-9_-]*(?:\.bin)?',name) and name not in ('con','nul','aux','prn'),'TEST_CHILD_NAME_INVALID')
        path=self.root/name
        with self.api.security(self.sid,directory) as security:
            if directory:
                need(self.api.k.CreateDirectoryW(str(path),c.byref(security)),'EXCLUSIVE_DIRECTORY_FAILED')
                handle=self.api.open(path,directory=True)
            else:handle=self.api.open(path,create=True,security=security)
        try:self.api.facts(handle,path,directory=directory,owner=self.sid)
        except BaseException:handle.close();raise
        self.handles.append(handle);self.paths[id(handle)]=(handle,path,directory);return handle
    def verify(self,handle):
        need(id(handle) in self.paths,'OWNED_HANDLE_REQUIRED')
        original,path,directory=self.paths[id(handle)];need(original is handle,'HANDLE_IDENTITY_MISMATCH')
        self.api.facts(handle,path,directory=directory,owner=self.sid)
    def write(self,handle,data):self.verify(handle);self.api.write_and_flush(handle,data);self.verify(handle)
    def close(self):
        errors=[]
        for handle in reversed(self.handles):
            try:handle.close()
            except BaseException:errors.append(True)
        self.handles=[]
        need(not errors,'HANDLE_CLOSE_FAILED')
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

class ProductionWindowsFiles:
    def provision(self,*args,**kwargs):raise WindowsIOBlocked('REAL_CHECKPOINT_EXECUTION_DISABLED')
    def create_file(self,*args,**kwargs):raise WindowsIOBlocked('REAL_CHECKPOINT_EXECUTION_DISABLED')
    def directory_durability(self,*args,**kwargs):raise WindowsIOBlocked('WINDOWS_POWER_LOSS_GUARANTEE_NOT_ESTABLISHED')

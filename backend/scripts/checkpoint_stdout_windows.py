"""Prepared Windows stdout primitives. Every native activation remains blocked.

Offline tests inject mock Win32/process primitives; no approval or native receipt
is issued here. Private algorithms are not an authorization boundary.
"""
import importlib.util
from pathlib import Path
import sys
import threading
import subprocess
import os

def _load(name,filename):
    if name in sys.modules:return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(filename))
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
s=_load('_lankapex_checkpoint_stdout','checkpoint_stdout_output.py')
w=_load('_lankapex_checkpoint_windows','checkpoint_windows_io.py')
p=s.p;n=s.n
_OUTPUT_BINDINGS={}
# Process-local terminal state, keyed by sealed attempt/job identities rather
# than wrapper identity. Durable cross-process enforcement remains mandatory
# at the future journal boundary. No reset/release operation is provided.
_INCOMPLETE_OUTPUT_JOBS={}

class WindowsStdoutFiles:
    def __init__(self):self.handles=[];self.output=None;self.api=None;self.path=None
    def _api(self):
        n.blocked()
        return w._Win32()
    def prepare(self,recipe,approved_owner):
        # Validates the issued job/configuration before any proposed OS access.
        _,job=s.validate_stdout_recipe(recipe)
        p.need(self.path is None,'OUTPUT_PREPARATION_ALREADY_ATTEMPTED')
        p.need((recipe.attempt_id,recipe.job_sha256) not in _INCOMPLETE_OUTPUT_JOBS,
               'OUTPUT_ATTEMPT_CLEANUP_INCOMPLETE')
        self.path=p.strict_windows_path(recipe.output_path)
        self.api=self._api()  # unconditional native blocker, mocked offline only
        try:
            for ancestor in reversed((self.path.parent,*self.path.parent.parents)):
                handle=self.api.open(ancestor,directory=True,read_acl=True)
                self.handles.append(handle)  # own before facts can fail
                self.api.facts(handle,ancestor,directory=True,
                               owner=approved_owner if ancestor==self.path.parent else None)
            with self.api.security(approved_owner,False) as security:
                # Existing reviewed primitive: CREATE_NEW=1, share=0,
                # OPEN_REPARSE_POINT and protected operator/SYSTEM descriptor.
                self.output=self.api.open(self.path,create=True,security=security)
                self.handles.append(self.output)
            _OUTPUT_BINDINGS[id(self)]=(self,recipe,job,recipe.attempt_id,recipe.job_sha256,
                recipe.approval_sha256,recipe.argv,str(self.path),approved_owner,self.api,
                tuple((handle,handle.value) for handle in self.handles))
            self.verify(approved_owner)
            return self.output
        except BaseException as primary:
            traceback=primary.__traceback__
            owned=tuple(self.handles)
            try:self.close()
            except BaseException:
                # Preserve the security failure, not cleanup exception text.
                # Retain ownership references even if close() cleared its list.
                codes=tuple(getattr(primary,'cleanup_codes',()))+('OUTPUT_CLOSE_INCOMPLETE',)
                primary.cleanup_status='INCOMPLETE';primary.cleanup_codes=codes
                _INCOMPLETE_OUTPUT_JOBS.setdefault((recipe.attempt_id,recipe.job_sha256),
                    ((self,recipe,job),codes,owned))
            raise primary.with_traceback(traceback)
    def verify_binding(self,recipe,owner):
        _,job=s.validate_stdout_recipe(recipe)
        binding=_OUTPUT_BINDINGS.get(id(self))
        p.need(binding is not None and binding[0] is self,'PREPARED_OUTPUT_BINDING_REQUIRED')
        _,issued,issued_job,attempt,job_hash,approval,argv,path,approved_owner,api,handles=binding
        p.need(recipe is issued and job is issued_job and recipe.attempt_id==attempt
               and recipe.job_sha256==job_hash and recipe.approval_sha256==approval
               and recipe.argv==argv and recipe.output_path==path==str(self.path)
               and owner==approved_owner and self.api is api,'OUTPUT_JOB_BINDING_MISMATCH')
        p.need((attempt,job_hash) not in _INCOMPLETE_OUTPUT_JOBS,
               'OUTPUT_ATTEMPT_CLEANUP_INCOMPLETE')
        p.need(len(self.handles)==len(handles) and self.output is handles[-1][0]
               and all(actual is original and actual.value==value
                       for actual,(original,value) in zip(self.handles,handles)),
               'OUTPUT_HANDLE_SUBSTITUTED')
        self.verify(owner)
    def verify(self,owner):
        p.need(self.output is not None and not self.output.closed,'OWNED_OUTPUT_REQUIRED')
        for handle,ancestor in zip(self.handles[:-1],reversed((self.path.parent,*self.path.parent.parents))):
            self.api.facts(handle,ancestor,directory=True,owner=owner if ancestor==self.path.parent else None)
        self.api.facts(self.output,self.path,directory=False,owner=owner)
    def flush(self,owner):
        self.verify(owner)
        p.need(self.api.k.FlushFileBuffers(self.output.value),'OUTPUT_FLUSH_FAILED')
        self.verify(owner)
    def _read_native(self):
        n.blocked()
        # Never reopen by pathname. Read from the original exclusive handle.
        import ctypes as c
        kernel=self.api.k;size=c.c_longlong();position=c.c_longlong()
        kernel.GetFileSizeEx.argtypes=[w.w.HANDLE,c.POINTER(c.c_longlong)]
        kernel.GetFileSizeEx.restype=w.w.BOOL
        kernel.SetFilePointerEx.argtypes=[w.w.HANDLE,c.c_longlong,c.POINTER(c.c_longlong),w.w.DWORD]
        kernel.SetFilePointerEx.restype=w.w.BOOL
        kernel.ReadFile.argtypes=[w.w.HANDLE,c.c_void_p,w.w.DWORD,c.POINTER(w.w.DWORD),c.c_void_p]
        kernel.ReadFile.restype=w.w.BOOL
        handle=self.output.value
        p.need(kernel.GetFileSizeEx(handle,c.byref(size)) and 0<size.value<=n.dump_inspection.MAX_BYTES,'OUTPUT_READ_SIZE_INVALID')
        expected=size.value
        p.need(kernel.SetFilePointerEx(handle,0,c.byref(position),0) and position.value==0,'OUTPUT_SEEK_FAILED')
        chunks=[];remaining=expected
        while remaining:
            length=min(65536,remaining);buffer=c.create_string_buffer(length);read=w.w.DWORD()
            p.need(kernel.ReadFile(handle,buffer,length,c.byref(read),None) and 0<read.value<=length,'OUTPUT_SHORT_READ')
            chunks.append(buffer.raw[:read.value]);remaining-=read.value
        p.need(kernel.GetFileSizeEx(handle,c.byref(size)) and size.value==expected,'OUTPUT_CHANGED_DURING_READ')
        return b''.join(chunks)
    def read_bound(self,recipe,owner):
        self.verify_binding(recipe,owner)
        raw=self._read_native()
        p.need(type(raw) is bytes and 0<len(raw)<=n.dump_inspection.MAX_BYTES,'OUTPUT_BYTES_REQUIRED')
        self.verify_binding(recipe,owner)
        return raw
    def close(self):
        errors=[]
        for handle in reversed(self.handles):
            try:handle.close()
            except BaseException:errors.append(True)
        self.handles=[]
        p.need(not errors,'HANDLE_CLOSE_FAILED')

class BoundedStderr:
    """Drain concurrently; discard raw bytes, retaining only bounded counts."""
    def __init__(self,limit):
        self.limit=limit;self.count=0;self.truncated=False;self.failed=False
        self.cancelled=threading.Event()
    def drain(self,stream):
        try:
            while not self.cancelled.is_set():
                data=stream.read(4096)
                if not data:break
                self.truncated|=self.count+len(data)>self.limit
                self.count=min(self.limit,self.count+len(data))
        except BaseException:self.failed=True
        finally:
            try:stream.close()
            except BaseException:self.failed=True
    def report(self):return dict(status='STDERR_REDACTED',retained_bytes=0,
                                 observed_bytes_bounded=self.count,truncated=self.truncated)

class WindowsStdoutProcess:
    def _cancel_reader(self,thread):
        n.blocked()
        # Cancel the synchronous pipe read in its owning thread. Do not close a
        # buffered pipe from another thread: close may wait on the reader lock.
        import ctypes
        api=w._Win32()
        api.k.OpenThread.argtypes=[w.w.DWORD,w.w.BOOL,w.w.DWORD]
        api.k.OpenThread.restype=w.w.HANDLE
        api.k.CancelSynchronousIo.argtypes=[w.w.HANDLE]
        api.k.CancelSynchronousIo.restype=w.w.BOOL
        raw=api.k.OpenThread(1,False,thread.native_id)
        p.need(bool(raw),'STDERR_THREAD_OPEN_FAILED')
        with w.Handle(api.k,raw):
            ok=api.k.CancelSynchronousIo(raw)
            p.need(ok or ctypes.get_last_error()==1168,'STDERR_CANCEL_FAILED')
    def _launch(self,argv,stdout_fd):
        n.blocked()
        p.need(sys.stdin is not None and sys.stdin.isatty(),'PRIVATE_INTERACTIVE_CONSOLE_REQUIRED')
        p.need(tuple(argv).count('--password')==1 and not any(v.startswith('--password=') for v in argv),'PRIVATE_NATIVE_PROMPT_REQUIRED')
        # Popen duplicates the supplied CRT stdout descriptor for the child;
        # the original exclusive Win32 handle remains owned by WindowsStdoutFiles.
        return subprocess.Popen(list(argv),shell=False,stdout=stdout_fd,
                                stderr=subprocess.PIPE,stdin=None,
                                close_fds=True)
    def _stdout_fd(self,handle):
        n.blocked()
        # Transfer only a duplicated handle to CRT ownership, never the original.
        import ctypes
        import msvcrt
        api=w._Win32();duplicate=w.w.HANDLE()
        api.k.DuplicateHandle.argtypes=[w.w.HANDLE,w.w.HANDLE,w.w.HANDLE,ctypes.POINTER(w.w.HANDLE),w.w.DWORD,w.w.BOOL,w.w.DWORD]
        api.k.DuplicateHandle.restype=w.w.BOOL
        current=api.k.GetCurrentProcess()
        p.need(api.k.DuplicateHandle(current,handle.value,current,ctypes.byref(duplicate),0,False,2),'STDOUT_DUPLICATE_FAILED')
        try:return msvcrt.open_osfhandle(duplicate.value,os.O_WRONLY|os.O_BINARY)
        except BaseException:api.k.CloseHandle(duplicate);raise
    def dispatch(self,recipe,files,owner):
        p.need(type(files) is WindowsStdoutFiles,'PREPARED_WINDOWS_OUTPUT_REQUIRED')
        p.need(getattr(self,'_incomplete_owner',None) is None,'PREVIOUS_CLEANUP_INCOMPLETE')
        files.verify_binding(recipe,owner)
        binding=_OUTPUT_BINDINGS[id(files)]
        attempt_key=(binding[3],binding[4])
        fd=self._stdout_fd(files.output);child=None;thread=None;started=False
        stderr=BoundedStderr(recipe.stderr_limit)
        failure=None;traceback=None;issues=[]
        try:
            files.verify_binding(recipe,owner)
            child=self._launch(recipe.argv,fd)
            thread=threading.Thread(target=stderr.drain,args=(child.stderr,),daemon=True)
            thread.start()
            started=True
            code=child.wait(timeout=recipe.timeout_seconds)
            thread.join(timeout=5)
            p.need(not thread.is_alive() and not stderr.failed,'STDERR_DRAIN_INCOMPLETE')
            p.need(type(code) is int and code==0,'DUMP_PROCESS_FAILED')
            files.verify_binding(recipe,owner)
        except BaseException as error:
            failure=error;traceback=error.__traceback__
        finally:
            try:
                if child is not None and child.poll() is None:
                    child.kill();child.wait(timeout=5)  # reap child; never remove partial output
            except BaseException:issues.append('CHILD_REAP_INCOMPLETE')
            if started:
                stderr.cancelled.set()
                try:
                    if thread.is_alive():self._cancel_reader(thread)
                except BaseException:issues.append('STDERR_CANCEL_INCOMPLETE')
                try:
                    thread.join(timeout=5)
                    if thread.is_alive():issues.append('STDERR_READER_INCOMPLETE')
                except BaseException:issues.append('STDERR_JOIN_INCOMPLETE')
            elif child is not None and child.stderr is not None:
                try:child.stderr.close()
                except BaseException:issues.append('STDERR_CLOSE_INCOMPLETE')
            try:os.close(fd)
            except BaseException:issues.append('STDOUT_DESCRIPTOR_CLOSE_INCOMPLETE')
        if issues:
            # Retain ownership references; never claim successful cleanup or allow
            # another wrapper/output for this sealed attempt/job to dispatch.
            # Retain fixed diagnostics and ownership, never raw exception text.
            self._incomplete_owner=(child,thread,stderr)
            _INCOMPLETE_OUTPUT_JOBS.setdefault(attempt_key,
                (binding,tuple(issues),child,thread,stderr,fd))
        if failure is not None:
            failure.cleanup_status='INCOMPLETE' if issues else 'COMPLETE'
            failure.cleanup_codes=tuple(issues)
            raise failure.with_traceback(traceback)
        if issues:
            error=p.Stop('NATIVE_STDOUT_CLEANUP_INCOMPLETE')
            error.cleanup_status='INCOMPLETE';error.cleanup_codes=tuple(issues)
            raise error
        files.verify_binding(recipe,owner);files.flush(owner)
        return stderr.report()

class NativeWindowsStdoutAdapter:
    def run(self,*args,**kwargs):n.blocked()
    def issue_native_receipt(self,*args,**kwargs):n.blocked()
    def run_prepared_model(self,recipe,files,process,owner,*,journal,after_capture=None):
        """Offline integration only: native primitives still block individually.

        Tests mock native I/O/launch methods. Only an existing model receipt is
        returned, never VerifiedDumpRun or authority for a native manifest.
        """
        p.need(type(files) is WindowsStdoutFiles and type(process) is WindowsStdoutProcess,
               'PREPARED_WINDOWS_PRIMITIVES_REQUIRED')
        binding=s.journal_binding(recipe,journal)
        value,job=s.validate_authenticated_stdout(recipe)
        stage='RESERVE';primary=None;traceback=None;result=None;cleanup=()
        try:
            journal.reserve_stdout(binding)
            stage='CREATE_NEW';files.prepare(recipe,owner)
            files.verify_binding(recipe,owner)
            stage='PROCESS';journal.consume_stdout_launch(binding)
            process.dispatch(recipe,files,owner)
            stage='FLUSH';files.verify_binding(recipe,owner);files.flush(owner)
            raw=files.read_bound(recipe,owner);digest=p.sha(raw)
            stage='VALIDATE';report=n.validate_dump_bytes(value,raw,job=job)
            p.need(p.sha(files.read_bound(recipe,owner))==digest,'OUTPUT_CHANGED_DURING_VALIDATION')
            post_hash=n.compare_sealed_source(value,job,after_capture)
            result=dict(status='MODEL_ONLY_NOT_NATIVE_BACKUP',attempt_id=recipe.attempt_id,
                job_sha256=recipe.job_sha256,stdout_approval_sha256=recipe.approval_sha256,
                stdout_argv_sha256=binding['argv_sha256'],backup_sha256=digest,backup_size=len(raw),
                baseline_sha256=report['baseline_sha256'],post_capture_sha256=post_hash,
                exit_code=0,cleanup_complete=True,flush_confirmed=True)
        except BaseException as error:
            primary=error;traceback=error.__traceback__;cleanup=getattr(error,'cleanup_codes',())
        finally:
            try:files.close()
            except BaseException as error:
                cleanup=tuple(cleanup)+('OUTPUT_CLOSE_INCOMPLETE',)
                if primary is None:primary=error;traceback=error.__traceback__;stage='CLOSE'
        if primary is not None:
            primary.cleanup_codes=cleanup
            if cleanup:primary.cleanup_status='INCOMPLETE'
            primary.evidence_status='PRESERVED_OFFLINE_JOURNAL'
            try:journal.fail_stdout(binding,stage,cleanup)
            except BaseException:primary.evidence_status='INCOMPLETE'
            primary.stdout_phase=stage
            raise primary.with_traceback(traceback)
        try:journal.complete_stdout_model(binding,result)
        except BaseException as error:
            error.evidence_status='INCOMPLETE'
            try:journal.fail_stdout(binding,'COMPLETE')
            except BaseException:pass
            raise
        receipt=object.__new__(s.ModelRunReceipt)
        s._MODEL_RECEIPTS[id(receipt)]=(receipt,p.canonical(result))
        return receipt

# Durable reservation/failure evidence and authenticated stdout approval must be
# integrated and independently reviewed before activation. No native success
# receipt can be issued by these prepared primitives.

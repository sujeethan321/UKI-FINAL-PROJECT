"""Explicit stdout-v1 approval and exclusive-output integration; models only.

No subprocess, database or real filesystem backend is activated. Model receipts
cannot be promoted to native-run receipts. Old --result-file recipes stay intact.
"""
from dataclasses import dataclass
from collections.abc import MutableMapping
import importlib.util
import json
from pathlib import Path
import sys
import threading

if '_lankapex_checkpoint_native' in sys.modules:n=sys.modules['_lankapex_checkpoint_native']
else:
    spec=importlib.util.spec_from_file_location('_lankapex_checkpoint_native',Path(__file__).with_name('checkpoint_native.py'))
    n=importlib.util.module_from_spec(spec);sys.modules[spec.name]=n;spec.loader.exec_module(n)
p=n.p;x=n.x

@dataclass(frozen=True)
class StdoutRecipe:
    attempt_id:str
    job_sha256:str
    approval_sha256:str
    argv:tuple
    output_path:str
    stderr_limit:int=16384
    timeout_seconds:int=300
    shell:bool=False

_RECIPES={};_MODEL_RECEIPTS={};_ATTEMPTS=set();_LOCK=threading.Lock()
_AUTHENTICATED_RECIPES={}

def expected_stdout_approval(value,job,base_recipe):
    """Approval proposal only; returning bytes does NOT approve them."""
    _,_,reserved,_,job_hash,_=n._job_baseline(value,job)
    config,_,config_hash=x.validate_native_recipe(base_recipe)
    p.need(config_hash==reserved['configuration_sha256'] and base_recipe.argv_sha256==reserved['native_sha256'],'STDOUT_BASE_RECIPE_MISMATCH')
    original=list(base_recipe.argv);flag='--result-file='+reserved['dump_path']
    p.need(original.count(flag)==1,'STDOUT_BASE_OUTPUT_MISMATCH')
    argv=original.copy();argv.remove(flag)
    return p.canonical(dict(format='checkpoint-stdout-v1',attempt_id=reserved['attempt_id'],job_sha256=job_hash,
        configuration_sha256=config_hash,base_argv_sha256=base_recipe.argv_sha256,argv=argv,
        endpoint=config['endpoint'],port=config['port'],server_uuid=config['server_uuid'],source=config['schema'],account=config['account'],
        ca_path=config['ca_path'],ca_sha256=config['ca_sha256'],destination=config['destination'],dump_path=reserved['dump_path'],
        output_mode='CREATE_NEW_EXCLUSIVE_OWNED_STDOUT_HANDLE',stderr_limit=16384,timeout_seconds=300,shell=False))

def bind_stdout_approval(raw,approved_sha256,*,value,job,base_recipe):
    p.need(type(raw) is bytes and 0<len(raw)<=65536 and p.sha(raw)==approved_sha256,'SEPARATE_STDOUT_APPROVAL_REQUIRED')
    expected=expected_stdout_approval(value,job,base_recipe)
    p.need(raw==expected,'STDOUT_APPROVED_CONFIGURATION_MISMATCH')
    data=json.loads(raw)
    recipe=StdoutRecipe(data['attempt_id'],data['job_sha256'],approved_sha256,tuple(data['argv']),data['dump_path'])
    _RECIPES[id(recipe)]=(recipe,bytes(raw),value,job,base_recipe,tuple(recipe.__dict__.items()))
    return recipe

def validate_stdout_recipe(recipe):
    p.need(type(recipe) is StdoutRecipe and id(recipe) in _RECIPES,'ISSUED_STDOUT_RECIPE_REQUIRED')
    original,raw,value,job,base,fields=_RECIPES[id(recipe)]
    p.need(original is recipe and tuple(recipe.__dict__.items())==fields,'STDOUT_RECIPE_MUTATED')
    expected=expected_stdout_approval(value,job,base)
    p.need(raw==expected and p.sha(raw)==recipe.approval_sha256,'STDOUT_APPROVAL_BINDING_CHANGED')
    return value,job

def bind_authenticated_stdout(raw,cap,*,value,job,base_recipe):
    expected=expected_stdout_approval(value,job,base_recipe)
    p.need(raw==expected,'STDOUT_APPROVED_CONFIGURATION_MISMATCH')
    n.stdout_authorization(cap,expected,value,job)
    recipe=bind_stdout_approval(raw,p.sha(raw),value=value,job=job,base_recipe=base_recipe)
    _AUTHENTICATED_RECIPES[id(recipe)]=(recipe,cap)
    return recipe

def validate_authenticated_stdout(recipe):
    value,job=validate_stdout_recipe(recipe)
    pair=_AUTHENTICATED_RECIPES.get(id(recipe))
    p.need(pair is not None and pair[0] is recipe,'AUTHENTICATED_STDOUT_RECIPE_REQUIRED')
    n.stdout_authorization(pair[1],_RECIPES[id(recipe)][1],value,job)
    return value,job

class _ModelHandle:
    __slots__=('path','identity','bytes','closed','flushed')
    def __init__(self,path):self.path=path;self.identity=object();self.bytes=bytearray();self.closed=False;self.flushed=False

class _WindowsEntries(MutableMapping):
    """Validated Windows identities for memory-only existence and lookup checks.

    PureWindowsPath equality/hash ignore case. Validate before constructing keys
    so path canonicalization cannot accept otherwise forbidden aliases. This is
    not an implementation of native atomic CREATE_NEW.
    """
    def __init__(self):self._entries={}
    def __getitem__(self,path):return self._entries[p.strict_windows_path(path)]
    def __setitem__(self,path,value):self._entries[p.strict_windows_path(path)]=value
    def __delitem__(self,path):del self._entries[p.strict_windows_path(path)]
    def __iter__(self):return (str(path) for path in self._entries)
    def __len__(self):return len(self._entries)

class MockExclusiveFiles:
    """In-memory filesystem fixture. No OS directories, permissions or writes."""
    def __init__(self):
        self.entries=_WindowsEntries();self.handles={};self.reparse=False;self.parent_reparse=False;self.acl_verified=True
        self.parent_handle_held=True;self.flush_ok=True;self.output_flush_ok=True;self.digest_override=None;self.substitute_after_start=False
    def create_new(self,path):
        p.strict_windows_path(path)
        p.need(not self.reparse and not self.parent_reparse and self.parent_handle_held and self.acl_verified,'OUTPUT_PARENT_OR_REPARSE_UNVERIFIED')
        p.need(path not in self.entries,'OUTPUT_ALREADY_EXISTS')
        handle=_ModelHandle(path);self.entries[path]=handle;self.handles[id(handle)]=(handle,handle.identity,path)
        return handle
    def verify(self,handle,path):
        p.need(type(handle) is _ModelHandle and id(handle) in self.handles,'OUTPUT_HANDLE_NOT_OWNED')
        original,identity,opened_path=self.handles[id(handle)]
        p.need(original is handle and identity is handle.identity and opened_path==path==handle.path and not handle.closed,'OUTPUT_HANDLE_OR_PATH_SUBSTITUTED')
        p.need(not self.reparse and not self.parent_reparse and self.parent_handle_held and self.acl_verified,'OUTPUT_PARENT_OR_REPARSE_UNVERIFIED')
    def write(self,handle,path,data):
        self.verify(handle,path);p.need(type(data) is bytes,'OUTPUT_BYTES_REQUIRED')
        p.need(len(handle.bytes)+len(data)<=n.dump_inspection.MAX_BYTES,'OUTPUT_SIZE_EXCEEDED')
        handle.bytes.extend(data);handle.flushed=False
    def flush(self,handle,path):
        self.verify(handle,path)
        p.need(self.flush_ok and (p.strict_windows_path(path).name.lower()!='viva.sql' or self.output_flush_ok),'OUTPUT_FLUSH_NOT_CONFIRMED')
        handle.flushed=True
    def read(self,handle,path):self.verify(handle,path);return bytes(handle.bytes)
    def checksum(self,handle,path):
        return self.digest_override or p.sha(self.read(handle,path))
    def record(self,path,record):
        handle=self.create_new(path)
        try:self.write(handle,path,p.canonical(record));self.flush(handle,path)
        finally:self.close(handle)
    def close(self,handle):
        p.need(id(handle) in self.handles,'OUTPUT_HANDLE_NOT_OWNED');handle.closed=True

class MockDumpProcess:
    """No executable/callback. Fixture byte streams and a modeled exit result."""
    def __init__(self,stdout,*,stderr=(),returncode=0,interrupted=False):
        p.need(type(stdout) in (tuple,list) and all(type(v) is bytes for v in stdout),'MOCK_PROCESS_BYTES_REQUIRED')
        p.need(type(stderr) in (tuple,list) and all(type(v) is bytes for v in stderr),'MOCK_PROCESS_BYTES_REQUIRED')
        self.stdout=tuple(stdout);self.stderr=tuple(stderr);self.returncode=returncode;self.interrupted=interrupted;self.calls=[]
    def run(self,argv,*,stdout_handle,stderr_consumer,write_stdout,shell,timeout):
        p.need(shell is False and timeout==300,'SHELL_OR_TIMEOUT_REJECTED')
        self.calls.append((tuple(argv),stdout_handle,shell))
        for data in self.stderr:stderr_consumer(data)
        for data in self.stdout:write_stdout(data)
        if self.interrupted:raise InterruptedError('MODELED_INTERRUPT')
        return self.returncode

class ModelRunReceipt:
    __slots__=()
    def __new__(cls):raise p.Stop('MODEL_RECEIPT_ISSUER_REQUIRED')

def model_receipt_record(value):
    p.need(type(value) is ModelRunReceipt and id(value) in _MODEL_RECEIPTS,'COMPLETED_MODEL_RECEIPT_REQUIRED')
    original,raw=_MODEL_RECEIPTS[id(value)];p.need(original is value,'MODEL_RECEIPT_IDENTITY_MISMATCH')
    return json.loads(raw)

def journal_binding(recipe,journal):
    _,job=validate_stdout_recipe(recipe)
    p.need(type(journal) is p.FilesystemConsumptionStore and p._JOBS[id(job)][1] is journal,
           'STDOUT_SAME_RESERVED_STORE_REQUIRED')
    return dict(attempt_id=recipe.attempt_id,job_sha256=recipe.job_sha256,
                approval_sha256=recipe.approval_sha256,argv_sha256=p.sha(p.canonical(list(recipe.argv))),
                output_path=recipe.output_path)

def run_model(recipe,files,process,*,journal=None):
    """Exercise the future execution ordering with EXACT model interfaces only."""
    value,job=validate_stdout_recipe(recipe)
    binding=journal_binding(recipe,journal) if journal is not None else None
    p.need(type(files) is MockExclusiveFiles and type(process) is MockDumpProcess,'REAL_OUTPUT_OR_PROCESS_DISABLED')
    with _LOCK:
        key=(recipe.attempt_id,recipe.job_sha256)
        p.need(key not in _ATTEMPTS,'STDOUT_JOB_ALREADY_ATTEMPTED');_ATTEMPTS.add(key)
    path=recipe.output_path;parent=p.PureWindowsPath(path).parent
    stage='RESERVE' if journal is not None else 'CREATE_NEW';handle=None;stderr_size=0;stderr_truncated=False;result=None
    primary=None;primary_traceback=None;close_failed=False
    def stderr_consumer(data):
        nonlocal stderr_size,stderr_truncated
        # Never retain/log raw stderr, including secrets or private SQL/path data.
        stderr_truncated|=stderr_size+len(data)>recipe.stderr_limit
        stderr_size=min(recipe.stderr_limit,stderr_size+len(data))
    try:
        if journal is not None:journal.reserve_stdout(binding)
        stage='CREATE_NEW'
        files.record(str(parent/'stdout-attempt.json'),dict(status='MODEL_ATTEMPT_RESERVED',attempt_id=recipe.attempt_id,job_sha256=recipe.job_sha256))
        handle=files.create_new(path);files.verify(handle,path)
        stage='PROCESS'
        if journal is not None:journal.consume_stdout_launch(binding)
        if files.substitute_after_start:handle.identity=object()
        code=process.run(recipe.argv,stdout_handle=handle,stderr_consumer=stderr_consumer,
            write_stdout=lambda data:files.write(handle,path,data),shell=False,timeout=recipe.timeout_seconds)
        files.verify(handle,path)
        files.record(str(parent/'stderr-status.json'),dict(status='STDERR_REDACTED',retained_bytes=0,
            observed_bytes_bounded=stderr_size,truncated=stderr_truncated))
        p.need(type(code) is int and code==0,'NATIVE_PROCESS_NONZERO_OR_UNCONFIRMED')
        stage='FLUSH';files.flush(handle,path);p.need(handle.flushed,'OUTPUT_FLUSH_NOT_CONFIRMED')
        raw=files.read(handle,path);digest=files.checksum(handle,path)
        p.need(raw and p.sha(raw)==digest,'OUTPUT_CHECKSUM_MISMATCH')
        stage='VALIDATE';report=n.validate_dump_bytes(value,raw,job=job)
        files.verify(handle,path);p.need(handle.flushed and files.checksum(handle,path)==digest,'OUTPUT_CHANGED_DURING_VALIDATION')
        result=dict(status='MODEL_ONLY_NOT_NATIVE_BACKUP',attempt_id=recipe.attempt_id,job_sha256=recipe.job_sha256,
            stdout_approval_sha256=recipe.approval_sha256,stdout_argv_sha256=p.sha(p.canonical(list(recipe.argv))),
            backup_sha256=digest,backup_size=len(raw),baseline_sha256=report['baseline_sha256'],exit_code=code,flush_confirmed=True)
    except BaseException as original:
        primary=original;primary_traceback=original.__traceback__
    finally:
        if handle is not None:
            try:files.close(handle)
            except BaseException as close_error:
                close_failed=True
                if primary is None:
                    primary=close_error;primary_traceback=close_error.__traceback__;stage='CLOSE'
    if primary is not None:
        # Failed attempts remain latched; preserve bytes, never retry/overwrite.
        evidence_status='PRESERVED_MODEL_ONLY'
        cleanup_codes=getattr(primary,'cleanup_codes',())
        if close_failed:
            cleanup_codes=tuple(cleanup_codes)+('OUTPUT_CLOSE_INCOMPLETE',)
            primary.cleanup_status='INCOMPLETE';primary.cleanup_codes=cleanup_codes
        try:files.record(str(parent/'stdout-failure.json'),dict(status='INCOMPLETE_PRESERVE_NO_RETRY',phase=stage))
        except BaseException:evidence_status='INCOMPLETE'
        if journal is not None:
            try:journal.fail_stdout(binding,stage,cleanup_codes)
            except BaseException:evidence_status='INCOMPLETE'
        if journal is not None or close_failed:
            primary.evidence_status=evidence_status;primary.stdout_phase=stage
            raise primary.with_traceback(primary_traceback)
        error=p.Stop('STDOUT_MODEL_FAILED_'+stage);error.evidence_status=evidence_status
        raise error from None
    p.need(result is not None,'MODEL_COMPLETION_REQUIRED')
    if journal is not None:
        try:journal.complete_stdout_model(binding,result)
        except BaseException as original:
            original.evidence_status='INCOMPLETE'
            try:journal.fail_stdout(binding,'COMPLETE',getattr(original,'cleanup_codes',()))
            except BaseException:pass
            raise
    receipt=object.__new__(ModelRunReceipt);_MODEL_RECEIPTS[id(receipt)]=(receipt,p.canonical(result));return receipt

class NativeStdoutRunner:
    def run(self,*args,**kwargs):n.blocked()
    def issue_native_receipt(self,*args,**kwargs):n.blocked()

if __name__=='__main__':
    print('STDOUT_OUTPUT=OFFLINE_ONLY; NATIVE_EXECUTION_DISABLED')
    raise SystemExit(2)

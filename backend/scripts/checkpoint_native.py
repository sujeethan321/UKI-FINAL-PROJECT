"""Native checkpoint candidates. Real operational entry points ALWAYS blocked.

No trust anchor, private key, connection or checkpoint is created at import.
Public-key verification and pure/model validation are separate from execution.
"""
import importlib.util
import json
from pathlib import Path
import re
import sys

def load(name):
    key='_native_checkpoint_'+name
    spec=importlib.util.spec_from_file_location(key,Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec);sys.modules[key]=module;spec.loader.exec_module(module);return module
x=load('checkpoint_execution_prepare');p=x.p
dump_inspection=load('checkpoint_dump_inspection');d=load('mr09_mysql_adapter')

def blocked():raise p.Stop('NATIVE_CHECKPOINT_EXECUTION_DISABLED')

_AUTHORIZATIONS={};_DUMP_BASELINES={}
_STDOUT_AUTHORIZATIONS={}
class VerifiedStdoutAuthorization:
    __slots__=()
    def __new__(cls):raise p.Stop('SIGNED_STDOUT_AUTHORIZATION_REQUIRED')
class VerifiedAuthorization:
    __slots__=()
    def __new__(cls):raise p.Stop('SIGNED_AUTHORIZATION_REQUIRED')

def _ed25519_verify(public_key,signature,message):
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:raise p.Stop('REVIEWED_SIGNATURE_DEPENDENCY_UNAVAILABLE') from None
    try:Ed25519PublicKey.from_public_bytes(public_key).verify(signature,message)
    except Exception:raise p.Stop('APPROVAL_SIGNATURE_INVALID') from None

def _json(raw):
    p.need(type(raw) is bytes and 0<len(raw)<=65536,'SIGNED_APPROVAL_SIZE_INVALID')
    def unique(pairs):
        value={}
        for key,item in pairs:
            p.need(key not in value,'DUPLICATE_SIGNED_FIELD');value[key]=item
        return value
    try:return json.loads(raw,object_pairs_hook=unique)
    except (ValueError,TypeError):raise p.Stop('SIGNED_APPROVAL_INVALID') from None

class PinnedApprovalVerifier:
    """External approved public key only. No default key or mock trust fallback."""
    def __init__(self,*,signer_id,public_key,approved_key_sha256,replay_store,clock):
        p.need(type(public_key) is bytes and len(public_key)==32 and p.sha(public_key)==approved_key_sha256,'PINNED_SIGNER_REQUIRED')
        p.need(type(signer_id) is str and re.fullmatch('[A-Za-z0-9_-]{8,100}',signer_id),'SIGNER_ID_INVALID')
        p.need(type(replay_store) is p.FilesystemConsumptionStore and callable(clock),'APPROVAL_RUNTIME_REQUIRED')
        self._key=bytes(public_key);self._pin=approved_key_sha256;self._signer=signer_id;self._replay=replay_store;self._clock=clock
    def verify(self,raw,signature,configuration_raw,approved_configuration_sha256):
        p.need(p.sha(self._key)==self._pin and type(signature) is bytes and len(signature)==64,'APPROVAL_SIGNATURE_INVALID')
        payload=_json(raw);config=_json(configuration_raw)
        fields={'signer_id','configuration_sha256','attempt_id','server_uuid','source','source_account','backup_account',
                'endpoint','port','ca_sha256','issued_at','expires_at','nonce','writer_freeze','ddl_freeze'}
        p.need(type(payload) is dict and set(payload)==fields,'SIGNED_APPROVAL_FIELDS_INVALID')
        _ed25519_verify(self._key,signature,raw)
        p.need(payload['signer_id']==self._signer and payload['configuration_sha256']==p.sha(configuration_raw)==approved_configuration_sha256,'SIGNED_CONFIGURATION_MISMATCH')
        p.need(payload['source']==config['schema']==p.SOURCE and payload['source_account']==p.typed.SOURCE_ACCOUNT,'SIGNED_SOURCE_SCOPE_MISMATCH')
        for field,configuration_field in [('attempt_id','attempt_id'),('server_uuid','server_uuid'),('backup_account','account'),('endpoint','endpoint'),('port','port'),('ca_sha256','ca_sha256')]:
            p.need(payload[field]==config[configuration_field],'SIGNED_IDENTITY_MISMATCH')
        p.attempt_guard(payload['attempt_id'])
        self._fresh(payload)
        p.need(payload['writer_freeze'] is True and payload['ddl_freeze'] is True
               and type(payload['nonce']) is str and re.fullmatch('[a-f0-9]{32}',payload['nonce']),'SIGNED_FREEZE_OR_NONCE_INVALID')
        # Separate private replay root required: nonce reservation is immutable;
        # uncertain acknowledgement consumes it, never retry or release it.
        nonce_attempt='checkpoint-'+p.sha(p.canonical([self._signer,payload['nonce']]))[:32].lower()
        self._replay.reserve_execution(nonce_attempt,p.sha(raw))
        value=object.__new__(VerifiedAuthorization)
        _AUTHORIZATIONS[id(value)]=(value,bytes(raw),bytes(configuration_raw),self)
        return value
    def _fresh(self,payload):
        now=self._clock()
        p.need(type(now) in (int,float) and now==now and abs(now)!=float('inf')
               and type(payload['issued_at']) in (int,float) and type(payload['expires_at']) in (int,float)
               and payload['issued_at']<=now<payload['expires_at']
               and 0<payload['expires_at']-payload['issued_at']<=300,'SIGNED_APPROVAL_EXPIRED')
    def verify_stdout(self,raw,signature,*,value,job,proposal):
        base,configuration=authorization(value)
        p.need(_AUTHORIZATIONS[id(value)][3] is self,'STDOUT_SIGNER_MISMATCH')
        payload=_json(raw);proposed=_json(proposal)
        fields={'format','signer_id','configuration_sha256','attempt_id','job_sha256','proposal_sha256',
                'argv_sha256','dump_path','issued_at','expires_at','nonce','writer_freeze','ddl_freeze'}
        p.need(type(payload) is dict and set(payload)==fields,'SIGNED_STDOUT_FIELDS_INVALID')
        p.need(p.sha(self._key)==self._pin and type(signature) is bytes and len(signature)==64,'APPROVAL_SIGNATURE_INVALID')
        _ed25519_verify(self._key,signature,raw)
        _,_,reserved,_,job_hash,_=_job_baseline(value,job)
        self._fresh(payload)
        p.need(payload['format']=='checkpoint-stdout-approval-v1' and payload['signer_id']==self._signer
               and payload['configuration_sha256']==base['configuration_sha256']==proposed['configuration_sha256']
               and payload['attempt_id']==base['attempt_id']==reserved['attempt_id']==proposed['attempt_id']
               and payload['job_sha256']==job_hash==proposed['job_sha256']
               and payload['proposal_sha256']==p.sha(proposal)
               and payload['argv_sha256']==p.sha(p.canonical(proposed['argv']))
               and payload['dump_path']==reserved['dump_path']==proposed['dump_path']
               and base['issued_at']<=payload['issued_at'] and payload['expires_at']<=base['expires_at']
               and payload['writer_freeze'] is True and payload['ddl_freeze'] is True,'SIGNED_STDOUT_BINDING_MISMATCH')
        p.need(type(payload['nonce']) is str and re.fullmatch('[a-f0-9]{32}',payload['nonce'])
               and payload['nonce']!=base['nonce'],'SIGNED_STDOUT_NONCE_INVALID')
        nonce='checkpoint-'+p.sha(p.canonical([self._signer,payload['nonce']]))[:32].lower()
        self._replay.reserve_execution(nonce,p.sha(raw))
        cap=object.__new__(VerifiedStdoutAuthorization)
        _STDOUT_AUTHORIZATIONS[id(cap)]=(cap,bytes(raw),bytes(proposal),value,job,self)
        return cap

def stdout_authorization(cap,proposal,value,job):
    p.need(type(cap) is VerifiedStdoutAuthorization and id(cap) in _STDOUT_AUTHORIZATIONS,'VERIFIED_STDOUT_AUTHORIZATION_REQUIRED')
    original,raw,approved,base,issued_job,verifier=_STDOUT_AUTHORIZATIONS[id(cap)]
    p.need(original is cap and base is value and issued_job is job and approved==proposal
           and p.sha(verifier._key)==verifier._pin,'STDOUT_AUTHORIZATION_SUBSTITUTED')
    authorization(base);verifier._fresh(_json(raw))
    return _json(raw)

def authorization(value):
    p.need(type(value) is VerifiedAuthorization and id(value) in _AUTHORIZATIONS,'VERIFIED_AUTHORIZATION_REQUIRED')
    original,raw,configuration,verifier=_AUTHORIZATIONS[id(value)]
    p.need(original is value and p.sha(verifier._key)==verifier._pin,'AUTHORIZATION_IDENTITY_MISMATCH')
    payload=_json(raw);verifier._fresh(payload)
    return payload,configuration

def authorized_recipe(value,destination):
    payload,raw=authorization(value)
    configuration=x.bind_approved_configuration(raw,payload['configuration_sha256'],destination)
    return x.native_recipe(configuration=configuration)

def capture_model(value,session,capture_id,freeze,clock):
    """Exercise real MR-09 read plans against its EXACT fixture transport only.

    This is the coherent capture interface, not a real DB adapter. It refuses
    arbitrary DBAPI connections until a separately reviewed transport release.
    """
    payload,_=authorization(value)
    p.need(freeze.get('observed_at')==payload['issued_at'] and freeze.get('expires_at')==payload['expires_at']
           and freeze.get('evidence_id')==payload['nonce'],'CAPTURE_SIGNED_FREEZE_MISMATCH')
    p.need(type(session) is d.MockMySQLSession and session.database==p.SOURCE and session.account==p.typed.SOURCE_ACCOUNT,'REAL_CAPTURE_TRANSPORT_DISABLED')
    policy=dict(server_uuid=payload['server_uuid'],charset_defaults={'ascii':'ascii_general_ci'},trigger_context={})
    inspector=d.MySQLInspector(session,policy);contract=d.c.build()['stages'][p.REVISION]
    started=clock()
    with inspector.consistent():
        actual=inspector.capture_stage(contract,p.REVISION);tables={};rows={};definitions={}
        for name,metadata in actual['tables'].items():
            columns=list(metadata['columns']);count=inspector.count(name)
            p.need(count<=p.typed.MAX_ROWS,'CAPTURE_LIMIT_EXCEEDED')
            values=inspector.read('rows',name,columns);observed=p.typed.fingerprint(values,columns)
            p.need(observed['row_count']==count==inspector.count(name),'CAPTURE_ROW_COUNT_CHANGED')
            definitions[name]=inspector.read('ddl',name)[0]['Create Table'];rows[name]=values
            tables[name]=dict(observed,schema_sha256=actual['raw_ddl_sha256'][name],columns=columns,
                column_metadata=metadata['columns'],primary_key=metadata['primary_key'],indexes=actual['physical_indexes'][name],
                foreign_keys=metadata['foreign_keys'],checks=metadata['checks'],engine=metadata['options']['engine']['value'],
                options=metadata['options'],unique_constraints=metadata['unique_constraints'],canonical_metadata=metadata)
        finished=clock();authorization(value)
        inventory=dict(database=p.SOURCE,revision=p.REVISION,host='127.0.0.1',port=3306,server_uuid=payload['server_uuid'],
            object_inventory_complete=True,tables=tables,triggers=[],views=[],routines=[],events=[])
        evidence=dict(owner=capture_id,capture_owner=capture_id,isolation='REPEATABLE READ',read_only=True,consistent_snapshot=True,started_at=started,finished_at=finished)
    # Only issue after the owned snapshot successfully closes/coherence checks pass.
    authorization(value)
    capture=p.capture_fingerprints(inventory,rows,evidence,freeze,clock(),payload['server_uuid'],attempt_id=payload['attempt_id'])
    _seal_dump_capture(capture,inventory,actual['tables'],definitions)
    return inventory,capture,actual['tables'],definitions

def validate_windows_handle_facts(facts,*,expected_path,operator_sid,directory):
    """Mandatory post-open checks; facts must come from held Win32 handles."""
    p.need(facts.get('final_path')==expected_path and facts.get('owner_sid')==operator_sid,'WINDOWS_HANDLE_IDENTITY_MISMATCH')
    p.need(facts.get('reparse') is False and facts.get('delete_shared') is False and facts.get('hard_links')==1,'WINDOWS_HANDLE_ESCAPE_REJECTED')
    p.need(facts.get('directory') is directory and (not directory or facts.get('dacl_protected') is True),'WINDOWS_HANDLE_TYPE_OR_ACL_INVALID')
    p.need(facts.get('aces')==[(operator_sid,'ALLOW','FULL_CONTROL'),('S-1-5-18','ALLOW','FULL_CONTROL')],'WINDOWS_HANDLE_ACL_INVALID')

def capture_transport_model(value,transport,binding,approved,ca_bytes,session,capture_id,freeze,clock):
    """Connect MR14 read policy to sealed capture using mock sessions ONLY."""
    t=transport_policy()
    p.need(type(transport) is t.SourceInspectionTransport and type(session) is d.MockMySQLSession,
           'REAL_CAPTURE_TRANSPORT_DISABLED')
    payload,_=authorization(value)
    t.validate_binding(binding,approved)
    p.need((binding.host,binding.port,binding.server_uuid,binding.schema,binding.account,binding.ca_sha256)==
           (payload['endpoint'],payload['port'],payload['server_uuid'],payload['source'],payload['source_account'],payload['ca_sha256']),
           'CAPTURE_TRANSPORT_IDENTITY_MISMATCH')
    t.certificate_context(binding,approved,ca_bytes)
    original=session.fetch
    def fetch(request,table=None):
        policy_plan=t.d.ReadPlan(request.key,request.statement,request.parameters,request.context)
        t.inspect_plan(policy_plan,table,revision=p.REVISION)
        return original(request,table)
    session.fetch=fetch
    try:return capture_model(value,session,capture_id,freeze,clock)
    finally:session.fetch=original

_TRANSPORT_POLICY=None
def transport_policy():
    global _TRANSPORT_POLICY
    if _TRANSPORT_POLICY is None:_TRANSPORT_POLICY=load('mr14_readonly_transport')
    return _TRANSPORT_POLICY

def compare_sealed_source(value,job,post_capture):
    baseline,bound,reserved,pre_capture,job_hash,baseline_hash=_job_baseline(value,job)
    p.need(type(post_capture) is p.ValidatedCapture and id(post_capture) in _DUMP_BASELINES,'SEALED_POST_CAPTURE_REQUIRED')
    original,post_baseline=_DUMP_BASELINES[id(post_capture)]
    actual,post_bound,_=dump_inspection.baseline_record(post_baseline,p)
    p.need(original is actual is post_capture,'POST_CAPTURE_SUBSTITUTED')
    payload,_=authorization(value);clock=_AUTHORIZATIONS[id(value)][3]._clock
    pre=p.capture_record(pre_capture,bound['inventory'],payload['server_uuid'],clock())
    post=p.capture_record(post_capture,post_bound['inventory'],payload['server_uuid'],clock())
    p.need(post['attempt_id']==pre['attempt_id'] and pre['freeze']==post['freeze']
           and pre['snapshot']['finished_at']<=post['snapshot']['started_at']
           and post['snapshot']['owner']==reserved['expected_post_capture_id']
           and bound['inventory']==post_bound['inventory'] and pre['fingerprints']==post['fingerprints'],
           'SOURCE_PRESERVATION_MISMATCH')
    return p.sha(p.canonical(post))

_STDOUT_RUNS={}
def issue_stdout_native_receipt(*args,**kwargs):blocked()

def bind_stdout_manifest(recipe,raw,*,run,after_capture,**arguments):
    """Future native manifest bridge; no native receipt issuer is enabled."""
    # The stdout module owns authenticated recipe capabilities.
    stdout=sys.modules.get('_lankapex_checkpoint_stdout')
    p.need(stdout is not None and stdout.n is sys.modules[__name__],'STDOUT_INTERFACE_REQUIRED')
    value,job=stdout.validate_authenticated_stdout(recipe)
    p.need(type(run) is VerifiedDumpRun and id(run) in _STDOUT_RUNS,'VERIFIED_STDOUT_NATIVE_RUN_REQUIRED')
    original,record=_STDOUT_RUNS[id(run)]
    post_hash=compare_sealed_source(value,job,after_capture)
    report=validate_dump_bytes(value,raw,job=job)
    binding=stdout.journal_binding(recipe,p._JOBS[id(job)][1]);store=p._JOBS[id(job)][1]
    expected=dict(binding,backup_sha256=p.sha(raw),backup_size=len(raw),baseline_sha256=report['baseline_sha256'],
                  post_capture_sha256=post_hash,exit_code=0,cleanup_complete=True,flush_confirmed=True)
    p.need(original is run and record==expected,'STDOUT_NATIVE_RECEIPT_MISMATCH')
    with store._locked():
        records=store._stdout_records(recipe.attempt_id,binding)
        p.need(set(records)=={'stdout_reserved','stdout_launch','stdout_validated'}
               and not (store.root/(recipe.attempt_id+'.failure.json')).exists(),'STDOUT_DURABLE_COMPLETION_REQUIRED')
        completion=dict(status='MODEL_ONLY_NOT_NATIVE_BACKUP',attempt_id=recipe.attempt_id,
            job_sha256=recipe.job_sha256,stdout_approval_sha256=recipe.approval_sha256,
            stdout_argv_sha256=binding['argv_sha256'],backup_sha256=p.sha(raw),backup_size=len(raw),
            baseline_sha256=report['baseline_sha256'],post_capture_sha256=post_hash,
            exit_code=0,cleanup_complete=True,flush_confirmed=True)
        p.need(records['stdout_validated']['result_sha256']==p.sha(p.canonical(completion)),
               'STDOUT_DURABLE_RESULT_MISMATCH')
    # Proof is issued only after signed recipe, sealed source, run and journal checks.
    proof=p._issue_stdout_manifest_proof(expected)
    _,bound,_,pre,_,_=_job_baseline(value,job)
    forbidden={'before','after','before_capture','after_capture','job','dump_sha256','dump_size','dump_inventory','completion_verified','dump_exit_code','stdout_proof'}
    p.need(not forbidden.intersection(arguments),'CALLER_STDOUT_RESULT_REJECTED')
    return p.prepare_manifest(before=bound['inventory'],after=bound['inventory'],before_capture=pre,
        after_capture=after_capture,job=job,dump_sha256=report['backup_sha256'],dump_size=report['backup_size'],
        dump_inventory={key:report[key] for key in ('tables','triggers','events','routines','views')},
        completion_verified=True,dump_exit_code=0,stdout_proof=proof,**arguments)

class WindowsNativeCheckpoint:
    """Win32 call candidates below are unreachable until independent release review.

    No activation flag exists. Handle ACL/final-path inspection and Windows
    directory-entry power-loss guarantees remain release-blocking dependencies.
    """
    def create_directory(self,recipe,value):
        blocked()
        # Deliberately unreachable native implementation candidate.
        import ctypes
        from ctypes import wintypes
        class SA(ctypes.Structure):
            _fields_=[('nLength',wintypes.DWORD),('lpSecurityDescriptor',ctypes.c_void_p),('bInheritHandle',wintypes.BOOL)]
        kernel=ctypes.WinDLL('kernel32',use_last_error=True);advapi=ctypes.WinDLL('advapi32',use_last_error=True)
        convert=advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
        convert.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(wintypes.ULONG)];convert.restype=wintypes.BOOL
        create=kernel.CreateDirectoryW;create.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(SA)];create.restype=wintypes.BOOL
        free=kernel.LocalFree;free.argtypes=[ctypes.c_void_p];free.restype=ctypes.c_void_p
        descriptor=ctypes.c_void_p()
        p.need(convert(recipe.sddl,1,ctypes.byref(descriptor),None),'WINDOWS_SECURITY_DESCRIPTOR_FAILED')
        try:
            attributes=SA(ctypes.sizeof(SA),descriptor,False)
            p.need(create(recipe.path,ctypes.byref(attributes)),'WINDOWS_EXCLUSIVE_DIRECTORY_FAILED')
        finally:free(descriptor)
        # Never claim successful private creation without held-handle inspection.
        raise p.Stop('WINDOWS_HANDLE_INSPECTION_NOT_IMPLEMENTED_PRESERVE_STATE')
    def create_file(self,path,value):
        blocked()
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        create=kernel.CreateFileW
        create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];create.restype=wintypes.HANDLE
        # GENERIC_READ|WRITE, no sharing, CREATE_NEW, OPEN_REPARSE_POINT|WRITE_THROUGH.
        handle=create(path,0xC0000000,0,None,1,0x00200000|0x80000000,None)
        p.need(handle!=ctypes.c_void_p(-1).value,'WINDOWS_EXCLUSIVE_FILE_FAILED')
        close=kernel.CloseHandle;close.argtypes=[wintypes.HANDLE];close.restype=wintypes.BOOL
        try:raise p.Stop('WINDOWS_HANDLE_INSPECTION_NOT_IMPLEMENTED_PRESERVE_STATE')
        finally:close(handle)
    def flush_directory(self,*args,**kwargs):
        blocked()
    def recover_or_resume(self,*args,**kwargs):
        raise p.Stop('INTERRUPTED_ATTEMPT_REQUIRES_OPERATOR_REVIEW_NO_RESUME')

class NativeDumpRunner:
    def run(self,recipe,value):
        blocked()
        # A future reviewed runner must route dump bytes to an exclusive held
        # output handle. --result-file opens by pathname and is NOT CREATE_NEW.
        # Do not silently change the issued argv to stdout or invoke Popen until
        # that reviewed recipe/output-handle binding is implemented.
    def capture_real_mysql(self,*args,**kwargs):blocked()
    def execute_backup(self,*args,**kwargs):blocked()

def _seal_dump_capture(capture,inventory,metadata,definitions):
    baseline=dump_inspection._issue_captured_baseline(capture,inventory,metadata,definitions,p)
    _DUMP_BASELINES[id(capture)]=(capture,baseline)
    return baseline

def _job_baseline(value,job):
    payload,configuration_raw=authorization(value)
    p.need(type(job) is p.ReservedJob and id(job) in p._JOBS,'ISSUED_RESERVED_JOB_REQUIRED')
    original,store,raw_job,destination,pre_capture=p._JOBS[id(job)]
    p.need(original is job and id(pre_capture) in _DUMP_BASELINES,'CAPTURE_BOUND_DUMP_BASELINE_REQUIRED')
    original_pre,baseline=_DUMP_BASELINES[id(pre_capture)]
    capture,bound,baseline_hash=dump_inspection.baseline_record(baseline,p)
    p.need(original_pre is capture is pre_capture,'DUMP_CAPTURE_IDENTITY_MISMATCH')
    config=_json(configuration_raw);reserved=json.loads(raw_job);inventory=bound['inventory']
    verifier=_AUTHORIZATIONS[id(value)][3]
    pre=p.capture_record(pre_capture,inventory,payload['server_uuid'],verifier._clock())
    p.need(reserved['attempt_id']==pre['attempt_id']==payload['attempt_id']
           and reserved['server_uuid']==payload['server_uuid'] and inventory['revision']==p.REVISION
           and reserved['configuration_sha256']==payload['configuration_sha256']
           and reserved['inventory_sha256']==p.sha(p.canonical(inventory))
           and reserved['before_capture_sha256']==p.sha(p.canonical(pre))
           and reserved['directory']==config['destination']
           and reserved['dump_path']==str(p.PureWindowsPath(config['destination'])/'viva.sql')
           and reserved['manifest_path']==str(p.PureWindowsPath(config['destination'])/'manifest.json'),'DUMP_RESERVED_BASELINE_MISMATCH')
    store.verify_execution(payload['attempt_id'],p.sha(raw_job))
    return baseline,bound,reserved,pre_capture,p.sha(raw_job),baseline_hash

def validate_dump_bytes(value,raw,*,job=None,**baseline_overrides):
    p.need(not baseline_overrides,'CALLER_DUMP_BASELINE_REJECTED')
    baseline,bound,reserved,pre_capture,job_hash,baseline_hash=_job_baseline(value,job)
    report=dump_inspection.inspect_bytes(raw,baseline,p)
    p.need(report['baseline_sha256']==baseline_hash,'DUMP_BASELINE_RESULT_MISMATCH')
    report.update(attempt_id=reserved['attempt_id'],job_sha256=job_hash,before_capture_sha256=reserved['before_capture_sha256'])
    return report

_DUMP_RUNS={}
class VerifiedDumpRun:
    __slots__=()
    def __new__(cls):raise p.Stop('NATIVE_DUMP_RECEIPT_REQUIRED')

def bind_dump_to_manifest(value,raw,*,job=None,run=None,**manifest_arguments):
    # No receipt issuer is enabled while native execution remains blocked.
    p.need(type(run) is VerifiedDumpRun and id(run) in _DUMP_RUNS,'VERIFIED_NATIVE_DUMP_RUN_REQUIRED')
    original,attempt,recipe_hash,bytes_hash,exit_code,run_job_hash,run_baseline_hash=_DUMP_RUNS[id(run)]
    p.need(original is run and bytes_hash==p.sha(raw) and exit_code==0,'NATIVE_DUMP_RECEIPT_MISMATCH')
    report=validate_dump_bytes(value,raw,job=job)
    baseline,bound,reserved,pre_capture,job_hash,baseline_hash=_job_baseline(value,job)
    payload,_=authorization(value)
    p.need(attempt==report['attempt_id']==payload['attempt_id'] and run_job_hash==job_hash
           and run_baseline_hash==baseline_hash and reserved['native_sha256']==recipe_hash,'NATIVE_RUN_JOB_RECIPE_MISMATCH')
    forbidden={'before','after','before_capture','dump_sha256','dump_size','dump_inventory','completion_verified','dump_exit_code'}
    p.need(not forbidden.intersection(manifest_arguments),'CALLER_DUMP_BASELINE_OR_RESULT_REJECTED')
    post_capture=manifest_arguments.get('after_capture')
    p.need(type(post_capture) is p.ValidatedCapture and id(post_capture) in _DUMP_BASELINES,'CAPTURE_BOUND_POST_BASELINE_REQUIRED')
    original_post,post_baseline=_DUMP_BASELINES[id(post_capture)]
    issued_post,post_bound,_=dump_inspection.baseline_record(post_baseline,p)
    p.need(original_post is issued_post is post_capture and post_bound['inventory']==bound['inventory'],'POST_DUMP_BASELINE_MISMATCH')
    p.need(manifest_arguments.get('attempt_id')==attempt and manifest_arguments.get('approved_uuid')==payload['server_uuid'],'DUMP_AUTHORIZATION_BINDING_MISMATCH')
    return p.prepare_manifest(before=bound['inventory'],after=post_bound['inventory'],before_capture=pre_capture,job=job,
        dump_sha256=report['backup_sha256'],dump_size=report['backup_size'],
        dump_inventory={key:report[key] for key in ('tables','triggers','events','routines','views')},completion_verified=True,
        dump_exit_code=exit_code,**manifest_arguments)

if __name__=='__main__':
    print('NATIVE_CHECKPOINT=OFFLINE_CANDIDATES_ONLY; EXECUTION_DISABLED')
    raise SystemExit(2)

"""Current 35-table checkpoint integration; pure offline validation, no I/O execution.

Caller-supplied evidence is NOT independently trusted by this module. Real
capture, DBA verification, ACL inspection and exclusive writing remain blocked.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import re
import threading
import os
from contextlib import contextmanager

def load(name):
    spec=importlib.util.spec_from_file_location('_checkpoint_'+name,Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

recovery=load('security_recovery_plan');typed=load('mr03_adapter')
SOURCE='lankapex_viva_db';REVISION='ae2b7c5f1d48'
TABLES=frozenset(recovery.tables_at(REVISION))
ROOT=PureWindowsPath(r'C:\Users\admin\Desktop\LankaPex')

class Stop(RuntimeError):pass
def need(value,code):
    if not value:raise Stop(code)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def sha(value):return hashlib.sha256(value).hexdigest().upper()

# Issuer-only process-local offline capabilities; not DBA authentication or a sandbox.
_CAPTURES={};_DESTINATIONS={};_JOBS={};_CAPTURE_IDS=set()
_CONSUMPTION_LOCK=threading.Lock();_CONSUMPTION_RECORDS={};_SIMULATED_EXECUTIONS={}
def attempt_guard(attempt_id):
    need(type(attempt_id) is str and re.fullmatch(r'checkpoint-[a-f0-9]{32}',attempt_id),'CHECKPOINT_ATTEMPT_REQUIRED')
class OfflineConsumptionStore:
    """Shared in-memory crash-state simulation ONLY; not durable across OS processes.

    Future store must atomically reserve attempt/capture IDs with unique constraints,
    fsync before success, preserve RESERVED after interruption, and fail closed on
    unavailable/uncertain outcomes. No caller-provided consumed booleans accepted.
    """
    def __init__(self):self.interrupt_after_reserve=False;self.unavailable=False;self._execution_tokens={}
    def reserve_execution(self,attempt_id,job_binding):
        attempt_guard(attempt_id);need(not self.unavailable,'CONSUMPTION_STORE_UNAVAILABLE')
        with _CONSUMPTION_LOCK:
            need(attempt_id not in _SIMULATED_EXECUTIONS,'EXECUTION_ATTEMPT_ALREADY_RESERVED')
            _SIMULATED_EXECUTIONS[attempt_id]=job_binding;self._execution_tokens[attempt_id]=job_binding
    def verify_execution(self,attempt_id,job_binding):
        with _CONSUMPTION_LOCK:
            need(not self.unavailable,'CONSUMPTION_STORE_UNAVAILABLE')
            need(self._execution_tokens.get(attempt_id)==job_binding
                 and _SIMULATED_EXECUTIONS.get(attempt_id)==job_binding,'RESERVED_JOB_NOT_CURRENT')
    def reserve(self,attempt_id,capture_ids,binding):
        need(not self.unavailable,'CONSUMPTION_STORE_UNAVAILABLE')
        keys=('attempt:'+attempt_id,)+tuple('capture:'+x for x in capture_ids)
        with _CONSUMPTION_LOCK:
            need(all(k not in _CONSUMPTION_RECORDS for k in keys),'ATTEMPT_OR_CAPTURE_ALREADY_RESERVED')
            for k in keys:_CONSUMPTION_RECORDS[k]=('RESERVED',binding)
        if self.interrupt_after_reserve:raise Stop('CONSUMPTION_INTERRUPTED_PRESERVE_RESERVATION')
        return keys
    def complete(self,keys,binding):
        need(not self.unavailable,'CONSUMPTION_STORE_UNAVAILABLE')
        with _CONSUMPTION_LOCK:
            need(all(_CONSUMPTION_RECORDS.get(k)==('RESERVED',binding) for k in keys),'CONSUMPTION_STATE_UNCERTAIN')
            for k in keys:_CONSUMPTION_RECORDS[k]=('COMPLETE',binding)
class DisabledDurableConsumptionStore:
    def reserve(self,*args,**kwargs):raise Stop('REAL_DURABLE_CONSUMPTION_NOT_REVIEWED')
    def complete(self,*args,**kwargs):raise Stop('REAL_DURABLE_CONSUMPTION_NOT_REVIEWED')

class FilesystemConsumptionStore:
    """Review candidate: immutable journals + OS lock, tested only in temp roots.

    Existing root must be private, local and ACL-verified by the future boundary.
    No root provisioning, deletion, reset or retries. fsync is not a claim of
    verified Windows storage/power-loss durability; activation remains blocked.
    """
    def __init__(self,root):
        self.root=Path(root)
        self._execution_tokens={}
        self._stdout_tokens={}
        need(self.root.is_absolute() and self.root.is_dir(),'RESERVATION_ROOT_REQUIRED')
        self._paths_clear()
    def _paths_clear(self):
        for path in (self.root,*self.root.parents):
            info=path.lstat()
            need(not path.is_symlink() and not getattr(info,'st_file_attributes',0)&0x400,'RESERVATION_REPARSE_REJECTED')
        for path in self.root.iterdir():
            info=path.lstat()
            need(path.is_file() and not path.is_symlink() and not getattr(info,'st_file_attributes',0)&0x400,'RESERVATION_ENTRY_REJECTED')
            need(path.name=='store.lock' or re.fullmatch(r'checkpoint-[a-f0-9]{32}\.(execution|reserved|complete|failure|stdout_reserved|stdout_launch|stdout_validated)\.json',path.name),'RESERVATION_UNEXPECTED_ENTRY')
    @contextmanager
    def _locked(self):
        self._paths_clear()
        flags=os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_BINARY',0)
        fd=os.open(self.root/'store.lock',flags,0o600)
        locked=False
        try:
            if os.name=='nt':
                import msvcrt
                if os.fstat(fd).st_size==0:os.write(fd,b'0');os.fsync(fd)
                os.lseek(fd,0,os.SEEK_SET);msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            locked=True;self._paths_clear();yield
        finally:
            if locked:
                if os.name=='nt':
                    os.lseek(fd,0,os.SEEK_SET);msvcrt.locking(fd,msvcrt.LK_UNLCK,1)
                else:fcntl.flock(fd,fcntl.LOCK_UN)
            os.close(fd)
    def _write(self,name,record):
        raw=canonical(record)
        with (self.root/name).open('xb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        # Directory fsync on POSIX; Windows metadata flush semantics need separate
        # platform/storage review. Windows production activation stays blocked.
        if os.name!='nt':
            fd=os.open(self.root,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
            try:os.fsync(fd)
            finally:os.close(fd)
    def _records(self):
        self._execution_records()
        records={}
        for path in self.root.glob('*.reserved.json'):
            try:
                record=json.loads(path.read_bytes())
                need(set(record)=={'attempt_id','capture_ids','binding','status'},'RESERVATION_CORRUPT')
                attempt_guard(record['attempt_id'])
                need(path.name==record['attempt_id']+'.reserved.json' and record['status']=='RESERVED'
                     and len(record['capture_ids'])==2 and len(set(record['capture_ids']))==2
                     and all(re.fullmatch('[A-F0-9]{64}',v) for v in [record['binding'],*record['capture_ids']]),'RESERVATION_CORRUPT')
                records[record['attempt_id']]=record
            except (ValueError,TypeError,KeyError):raise Stop('RESERVATION_CORRUPT_PRESERVE_STATE') from None
        # An orphan completion/failure is uncertain state, never evidence of reuse.
        for suffix in ('complete','failure'):
            for path in self.root.glob('*.'+suffix+'.json'):
                attempt=path.name.split('.')[0]
                need(attempt in records or (suffix=='failure' and (self.root/(attempt+'.execution.json')).exists()),'RESERVATION_ORPHAN_EVIDENCE')
        return records
    def _execution_records(self):
        records={}
        for path in self.root.glob('*.execution.json'):
            try:
                raw=path.read_bytes();record=json.loads(raw);attempt_guard(record['attempt_id'])
                need(set(record)=={'attempt_id','job_binding','status'} and record['status']=='EXECUTION_RESERVED'
                     and path.name==record['attempt_id']+'.execution.json'
                     and re.fullmatch('[A-F0-9]{64}',record['job_binding']),'EXECUTION_JOURNAL_CORRUPT')
                records[record['attempt_id']]=raw
            except (ValueError,TypeError,KeyError):raise Stop('EXECUTION_JOURNAL_CORRUPT') from None
        return records
    def reserve_execution(self,attempt_id,job_binding):
        """Durable pre-launch candidate; reopen never silently resumes an attempt."""
        attempt_guard(attempt_id)
        need(type(job_binding) is str and re.fullmatch('[A-F0-9]{64}',job_binding),'EXECUTION_JOB_BINDING_INVALID')
        with self._locked():
            executions=self._execution_records();records=self._records()
            need(attempt_id not in executions and attempt_id not in records,'EXECUTION_ATTEMPT_ALREADY_RESERVED')
            record=dict(attempt_id=attempt_id,job_binding=job_binding,status='EXECUTION_RESERVED')
            self._write(attempt_id+'.execution.json',record)
            self._execution_tokens[attempt_id]=canonical(record)
    def verify_execution(self,attempt_id,job_binding):
        attempt_guard(attempt_id)
        with self._locked():
            raw=self._execution_records().get(attempt_id)
            need(raw is not None and self._execution_tokens.get(attempt_id)==raw,'RESERVED_JOB_NOT_CURRENT')
            need(json.loads(raw)['job_binding']==job_binding and not (self.root/(attempt_id+'.failure.json')).exists(),'RESERVED_JOB_BINDING_MISMATCH')
    def reserve(self,attempt_id,capture_ids,binding):
        attempt_guard(attempt_id)
        need(len(capture_ids)==2 and len(set(capture_ids))==2
             and all(type(v) is str and re.fullmatch('[A-F0-9]{64}',v) for v in [binding,*capture_ids]),'RESERVATION_BINDING_INVALID')
        with self._locked():
            records=self._records();executions=self._execution_records()
            if attempt_id in executions:
                need(self._execution_tokens.get(attempt_id)==executions[attempt_id],'INTERRUPTED_EXECUTION_NO_AUTOMATIC_RESUME')
                need(not (self.root/(attempt_id+'.failure.json')).exists(),'FAILED_ATTEMPT_LATCHED')
            used={v for record in records.values() for v in record['capture_ids']}
            need(attempt_id not in records and not used.intersection(capture_ids),'ATTEMPT_OR_CAPTURE_ALREADY_RESERVED')
            record=dict(attempt_id=attempt_id,capture_ids=list(capture_ids),binding=binding,status='RESERVED')
            self._write(attempt_id+'.reserved.json',record)
        return attempt_id
    def complete(self,attempt_id,binding):
        attempt_guard(attempt_id)
        with self._locked():
            record=self._records().get(attempt_id)
            need(record is not None and record['binding']==binding,'RESERVATION_COMPLETION_MISMATCH')
            need(not (self.root/(attempt_id+'.failure.json')).exists(),'FAILED_ATTEMPT_LATCHED')
            self._write(attempt_id+'.complete.json',dict(status='COMPLETE',binding=binding))
    def failure(self,attempt_id,phase):
        attempt_guard(attempt_id)
        need(phase in ('BASELINE','DUMP','POST_CAPTURE','MANIFEST'),'UNKNOWN_PHASE')
        with self._locked():
            need(attempt_id in self._records() or attempt_id in self._execution_records(),'RESERVATION_REQUIRED')
            self._write(attempt_id+'.failure.json',dict(status='INCOMPLETE_PRESERVE_NO_RETRY',phase=phase))

    def _stdout_records(self,attempt,binding):
        """Strict immutable records in the SAME store; no restart token recovery."""
        attempt_guard(attempt)
        need(set(binding)=={'attempt_id','job_sha256','approval_sha256','argv_sha256','output_path'}
             and binding['attempt_id']==attempt,'STDOUT_BINDING_INVALID')
        for field in ('job_sha256','approval_sha256','argv_sha256'):
            need(type(binding[field]) is str and re.fullmatch('[A-F0-9]{64}',binding[field]),'STDOUT_BINDING_INVALID')
        strict_windows_path(binding['output_path'])
        execution=self._execution_records().get(attempt)
        need(execution is not None and json.loads(execution)['job_binding']==binding['job_sha256'],'STDOUT_EXECUTION_MISMATCH')
        records={}
        for suffix in ('stdout_reserved','stdout_launch','stdout_validated'):
            path=self.root/(attempt+'.'+suffix+'.json')
            if path.exists():
                try:
                    raw=path.read_bytes();value=json.loads(raw)
                    need(raw==canonical(value) and set(value)=={'status','binding','result_sha256'}
                         and value['status']==suffix and value['binding']==binding,'STDOUT_JOURNAL_CORRUPT_OR_CHANGED')
                    need(value['result_sha256'] is None if suffix!='stdout_validated' else
                         type(value['result_sha256']) is str and re.fullmatch('[A-F0-9]{64}',value['result_sha256']), 'STDOUT_JOURNAL_CORRUPT')
                    records[suffix]=value
                except (ValueError,TypeError,KeyError):raise Stop('STDOUT_JOURNAL_CORRUPT') from None
        need(not records or 'stdout_reserved' in records,'STDOUT_ORPHAN_RECORD')
        need('stdout_validated' not in records or 'stdout_launch' in records,'STDOUT_ORPHAN_RECORD')
        return records
    def reserve_stdout(self,binding):
        attempt=binding['attempt_id']
        with self._locked():
            records=self._stdout_records(attempt,binding)
            need(self._execution_tokens.get(attempt)==self._execution_records().get(attempt),'INTERRUPTED_EXECUTION_NO_AUTOMATIC_RESUME')
            need(not records and not (self.root/(attempt+'.failure.json')).exists(),'STDOUT_ATTEMPT_ALREADY_USED')
            self._write(attempt+'.stdout_reserved.json',dict(status='stdout_reserved',binding=binding,result_sha256=None))
            self._stdout_tokens[attempt]=(canonical(binding),'RESERVED')
    def consume_stdout_launch(self,binding):
        attempt=binding['attempt_id']
        with self._locked():
            records=self._stdout_records(attempt,binding)
            need(self._stdout_tokens.get(attempt)==(canonical(binding),'RESERVED')
                 and set(records)=={'stdout_reserved'} and not (self.root/(attempt+'.failure.json')).exists(),'STDOUT_LAUNCH_ALREADY_CONSUMED_OR_INTERRUPTED')
            # Exclusive file creation under the existing OS lock. A crash after
            # this write consumes launch even if no child was started.
            self._write(attempt+'.stdout_launch.json',dict(status='stdout_launch',binding=binding,result_sha256=None))
            self._stdout_tokens[attempt]=(canonical(binding),'LAUNCHED')
    def complete_stdout_model(self,binding,result):
        attempt=binding['attempt_id']
        with self._locked():
            records=self._stdout_records(attempt,binding)
            need(self._stdout_tokens.get(attempt)==(canonical(binding),'LAUNCHED')
                 and set(records)=={'stdout_reserved','stdout_launch'}
                 and not (self.root/(attempt+'.failure.json')).exists(),'STDOUT_COMPLETION_REJECTED')
            need(result['status']=='MODEL_ONLY_NOT_NATIVE_BACKUP' and result['flush_confirmed'] is True
                 and result['exit_code']==0 and result['attempt_id']==attempt
                 and result['job_sha256']==binding['job_sha256']
                 and result['stdout_approval_sha256']==binding['approval_sha256']
                 and result['stdout_argv_sha256']==binding['argv_sha256'],'STDOUT_RESULT_BINDING_MISMATCH')
            self._write(attempt+'.stdout_validated.json',dict(status='stdout_validated',binding=binding,result_sha256=sha(canonical(result))))
            self._stdout_tokens[attempt]=(canonical(binding),'COMPLETE')
    def fail_stdout(self,binding,phase,cleanup_codes=()):
        attempt=binding['attempt_id']
        need(phase in ('RESERVE','CREATE_NEW','PROCESS','FLUSH','VALIDATE','CLOSE','COMPLETE'),'STDOUT_FAILURE_PHASE_INVALID')
        allowed={'CHILD_REAP_INCOMPLETE','STDERR_CANCEL_INCOMPLETE','STDERR_READER_INCOMPLETE','STDERR_JOIN_INCOMPLETE','STDERR_CLOSE_INCOMPLETE','STDOUT_DESCRIPTOR_CLOSE_INCOMPLETE','OUTPUT_CLOSE_INCOMPLETE'}
        need(type(cleanup_codes) is tuple and all(code in allowed for code in cleanup_codes),'STDOUT_CLEANUP_CODE_INVALID')
        with self._locked():
            self._stdout_records(attempt,binding)
            self._write(attempt+'.failure.json',dict(status='INCOMPLETE_PRESERVE_NO_RETRY',phase='DUMP',
                stdout_phase=phase,binding=binding,failure_code='STDOUT_STAGE_FAILED',cleanup_codes=list(cleanup_codes)))

class ValidatedCapture:
    __slots__=()
    def __new__(cls):raise Stop('CAPTURE_ISSUER_REQUIRED')
    def __len__(self):return len(TABLES)
class ValidatedDestination:
    __slots__=()
    def __new__(cls):raise Stop('DESTINATION_ISSUER_REQUIRED')
def capture_record(value,inventory,approved_uuid,now):
    need(type(value) is ValidatedCapture and id(value) in _CAPTURES,'VALIDATED_CAPTURE_REQUIRED')
    original,raw=_CAPTURES[id(value)];need(original is value,'CAPTURE_IDENTITY_MISMATCH')
    record=json.loads(raw)
    need(record['inventory_sha256']==sha(canonical(inventory)) and record['server_uuid']==approved_uuid
         and record['revision']==REVISION and set(record['fingerprints'])==TABLES,'CAPTURE_BINDING_MISMATCH')
    validate_snapshot(record['snapshot'],record['freeze'],now)
    return record

class ReservedJob:
    __slots__=()
    def __new__(cls):raise Stop('RESERVED_JOB_ISSUER_REQUIRED')
def _issue_reserved_job(store,raw,destination,pre_capture):
    # Private issuer used only after approved recipe/capture validation and reserve.
    job=json.loads(raw);store.verify_execution(job['attempt_id'],sha(raw))
    value=object.__new__(ReservedJob);_JOBS[id(value)]=(value,store,bytes(raw),destination,pre_capture)
    return value

def reserved_job_record(value,store,destination,pre_capture,pre,post,attempt_id,output,inventory,approved_uuid):
    need(type(value) is ReservedJob and id(value) in _JOBS,'ISSUED_RESERVED_JOB_REQUIRED')
    original,issued_store,raw,issued_destination,issued_pre=_JOBS[id(value)]
    need(original is value and issued_store is store and issued_destination is destination
         and issued_pre is pre_capture,'RESERVED_JOB_CAPABILITY_MISMATCH')
    job=json.loads(raw)
    need(job['attempt_id']==attempt_id and job['server_uuid']==approved_uuid
         and job['dump_path']==str(output) and job['directory']==str(output.parent)
         and job['manifest_path']==str(output.parent/'manifest.json')
         and job['before_capture_sha256']==sha(canonical(pre))
         and job['inventory_sha256']==sha(canonical(inventory))
         and job['expected_post_capture_id']==post['snapshot']['owner'],'FINAL_MANIFEST_JOB_MISMATCH')
    store.verify_execution(attempt_id,sha(raw));return job,sha(raw)

def strict_windows_path(value):
    need(type(value) is str and re.match(r'^[A-Za-z]:\\',value) is not None,'AMBIGUOUS_WINDOWS_PATH')
    path=PureWindowsPath(value)
    need(str(path)==value and len(path.parts)>1,'AMBIGUOUS_WINDOWS_PATH')
    for part in path.parts[1:]:
        need(part not in ('.','..') and not part.endswith((' ','.'))
             and not re.search(r'[<>:"/|?*~\x00-\x1f]',part)
             and not re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',part,re.I),'UNSAFE_WINDOWS_COMPONENT')
    return path

def validate_inventory(inventory,approved_uuid):
    recovery.validate_inventory(inventory,REVISION)
    need(inventory['server_uuid']==approved_uuid,'SERVER_IDENTITY_MISMATCH')
    need(len(TABLES)==35 and all(t.get('engine')=='InnoDB' for t in inventory['tables'].values()),'NON_INNODB_OR_WRONG_INVENTORY')

def validate_snapshot(evidence,freeze,now):
    # Evidence capture/trust must be independently verified before a future live run.
    need(evidence['isolation']=='REPEATABLE READ' and evidence['read_only'] is True
         and evidence['consistent_snapshot'] is True and type(evidence['owner']) is str
         and re.fullmatch('[A-Za-z0-9_-]{8,100}',evidence['owner']) and evidence['owner']==evidence['capture_owner'],'SNAPSHOT_CONTRACT_FAILED')
    need(0<=evidence['finished_at']-evidence['started_at']<=30 and evidence['started_at']<=evidence['finished_at']<=now,'SNAPSHOT_TIME_INVALID')
    need(freeze['source']==SOURCE and freeze['revision']==REVISION and bool(freeze['evidence_id'])
         and freeze['writer_freeze'] is True and freeze['ddl_freeze'] is True
         and freeze['observed_at']<=evidence['started_at'] and now<freeze['expires_at']
         and 0<freeze['expires_at']-freeze['observed_at']<=300,'FREEZE_EVIDENCE_INVALID')

def capture_fingerprints(inventory,rows,evidence,freeze,now,approved_uuid,*,attempt_id=None):
    """Consume complete supplied streams; MAX_ROWS overflow rejects, never truncates.

    This function does not establish a real snapshot or inspect a live database.
    Both complete counts and typed content must agree with the supplied inventory.
    """
    attempt_guard(attempt_id)
    validate_inventory(inventory,approved_uuid);validate_snapshot(evidence,freeze,now)
    need(freeze.get('server_uuid')==approved_uuid,'FREEZE_SERVER_MISMATCH')
    need(set(rows)==TABLES,'ROW_STREAM_INVENTORY_MISMATCH');result={}
    for name in sorted(TABLES):
        table=inventory['tables'][name];columns=table['columns']
        need(columns and all(type(c) is str for c in columns) and len(set(columns))==len(columns),'COLUMN_PROJECTION_INVALID')
        need(table['row_count']<=typed.MAX_ROWS,'CAPTURE_LIMIT_EXCEEDED')
        def complete_stream():
            for row in rows[name]:
                need(type(row) is dict and set(row)==set(columns),'INCOMPLETE_ROW_PROJECTION')
                if name=='alembic_version':need(row=={'version_num':REVISION},'ACTUAL_REVISION_MISMATCH')
                yield row
        observed=typed.fingerprint(complete_stream(),columns)
        need(observed['row_count']==table['row_count'] and observed['content_sha256']==table['content_sha256'],'COUNT_OR_CONTENT_MISMATCH')
        if name=='alembic_version':need(observed['row_count']==1,'REVISION_ROW_COUNT_INVALID')
        result[name]=dict(observed,columns=columns)
    record=dict(attempt_id=attempt_id,revision=REVISION,server_uuid=approved_uuid,inventory_sha256=sha(canonical(inventory)),
                fingerprints=result,snapshot=copy.deepcopy(evidence),freeze=copy.deepcopy(freeze))
    with _CONSUMPTION_LOCK:
        identity=(attempt_id,evidence['owner'])
        need(identity not in _CAPTURE_IDS,'CAPTURE_ID_ALREADY_ISSUED')
        value=object.__new__(ValidatedCapture);_CAPTURES[id(value)]=(value,canonical(record));_CAPTURE_IDS.add(identity)
    return value

def destination_policy(path,approved_path,observation,operator_sid,*,attempt_id=None):
    attempt_guard(attempt_id)
    path=strict_windows_path(path);strict_windows_path(approved_path)
    need(path==PureWindowsPath(approved_path) and path.is_absolute() and not str(path).startswith('\\\\')
         and '..' not in path.parts and not any(':' in part for part in path.parts[1:])
         and path!=ROOT and ROOT not in path.parents,'PRIVATE_PATH_REJECTED')
    need(re.fullmatch(r'S-1-5-21-(?:\d+-){3}\d+',operator_sid) is not None,'OPERATOR_SID_INVALID')
    need(observation['outside_public_roots'] is True and observation['reparse_ancestors_clear'] is True
         and observation['destination_absent'] is True and observation.get('outputs_absent') is True
         and observation.get('output_reparse_clear') is True,'UNSAFE_DESTINATION')
    # Proposed/final ACL policy must be checked by the future operator, not inferred.
    need(observation['owner']==operator_sid and observation['protected'] is True
         and observation['rules']=={operator_sid:'FullControl:ContainerInherit,ObjectInherit',
                                    'S-1-5-18':'FullControl:ContainerInherit,ObjectInherit'},'ACL_POLICY_MISMATCH')
    value=object.__new__(ValidatedDestination)
    _DESTINATIONS[id(value)]=(value,str(path),attempt_id);return value

def dump_arguments(*,endpoint,approved_endpoint,port,approved_port,ca_path,ca_sha256,approved_ca_sha256,user,dump,destination=None,attempt_id=None):
    attempt_guard(attempt_id)
    need(type(destination) is ValidatedDestination and id(destination) in _DESTINATIONS,'VALIDATED_DESTINATION_REQUIRED')
    original,directory,destination_attempt=_DESTINATIONS[id(destination)];need(destination_attempt==attempt_id,'DESTINATION_ATTEMPT_MISMATCH');need(original is destination,'DESTINATION_IDENTITY_MISMATCH')
    output=strict_windows_path(dump)
    need(output.parent==PureWindowsPath(directory) and output.name=='viva.sql','DUMP_DESTINATION_MISMATCH')
    need(endpoint==approved_endpoint=='127.0.0.1' and port==approved_port==3306,'ENDPOINT_NOT_APPROVED')
    need(re.fullmatch(r'[A-Za-z0-9_]{1,32}',user) is not None,'BACKUP_ACCOUNT_INVALID')
    need(PureWindowsPath(ca_path).is_absolute() and PureWindowsPath(dump).is_absolute(),'ABSOLUTE_PATH_REQUIRED')
    need(re.fullmatch('[A-F0-9]{64}',ca_sha256) and ca_sha256==approved_ca_sha256,'CA_APPROVAL_MISMATCH')
    return [r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe','--no-defaults',
            '--protocol=TCP','--host='+endpoint,'--port='+str(port),'--user='+user,'--password',
            '--ssl-mode=VERIFY_IDENTITY','--ssl-ca='+str(ca_path),'--tls-version=TLSv1.2,TLSv1.3',
            '--default-character-set=utf8mb4','--single-transaction','--quick','--hex-blob','--order-by-primary',
            '--set-gtid-purged=OFF','--no-tablespaces','--column-statistics=0','--triggers','--routines','--events',
            '--skip-add-drop-table','--skip-add-locks','--skip-disable-keys','--skip-lock-tables',
            '--result-file='+str(dump),SOURCE]

_STDOUT_MANIFEST_PROOFS={}
class StdoutManifestProof:
    __slots__=()
    def __new__(cls):raise Stop('ISSUED_STDOUT_MANIFEST_PROOF_REQUIRED')
def _issue_stdout_manifest_proof(record):
    value=object.__new__(StdoutManifestProof)
    _STDOUT_MANIFEST_PROOFS[id(value)]=(value,canonical(record));return value

def prepare_manifest(before,after,*,approved_uuid,dump_sha256,dump_size,dump_exit_code,
                     dump_inventory,completion_verified,freeze_evidence_id,before_capture=None,after_capture=None,now=None,attempt_id=None,destination=None,dump=None,consumption=None,job=None,stdout_proof=None):
    attempt_guard(attempt_id)
    need(type(consumption) in (OfflineConsumptionStore,FilesystemConsumptionStore),'VALIDATED_CONSUMPTION_BOUNDARY_REQUIRED')
    need(type(destination) is ValidatedDestination and id(destination) in _DESTINATIONS,'VALIDATED_DESTINATION_REQUIRED')
    original,directory,destination_attempt=_DESTINATIONS[id(destination)]
    need(original is destination and destination_attempt==attempt_id,'DESTINATION_ATTEMPT_MISMATCH')
    output=strict_windows_path(dump)
    need(output.parent==PureWindowsPath(directory) and output.name=='viva.sql','DUMP_DESTINATION_MISMATCH')
    validate_inventory(before,approved_uuid);validate_inventory(after,approved_uuid)
    need(type(now) in (int,float) and now==now and abs(now)!=float('inf'),'FRESH_VERIFICATION_TIME_REQUIRED')
    pre=capture_record(before_capture,before,approved_uuid,now);post=capture_record(after_capture,after,approved_uuid,now)
    need(pre['attempt_id']==post['attempt_id']==attempt_id,'CAPTURE_ATTEMPT_MISMATCH')
    reserved_job,job_hash=reserved_job_record(job,consumption,destination,before_capture,pre,post,attempt_id,output,before,approved_uuid)
    need(before_capture is not after_capture and pre['snapshot']['owner']!=post['snapshot']['owner']
         and pre['snapshot']['finished_at']<=post['snapshot']['started_at'],'DISTINCT_ORDERED_CAPTURES_REQUIRED')
    need(pre['freeze']==post['freeze'] and pre['freeze']['evidence_id']==freeze_evidence_id,'CONTINUOUS_FREEZE_BINDING_MISMATCH')
    need(before==after and pre['fingerprints']==post['fingerprints'],'SOURCE_PRESERVATION_MISMATCH')
    need(dump_exit_code==0 and type(dump_size) is int and dump_size>0
         and completion_verified is True,'DUMP_INCOMPLETE')
    need(re.fullmatch('[A-F0-9]{64}',dump_sha256) is not None,'DUMP_HASH_INVALID')
    need(dump_inventory=={'tables':sorted(TABLES),'triggers':[],'views':[],'routines':[],'events':[]},'DUMP_OBJECTS_MISMATCH')
    need(type(freeze_evidence_id) is str and re.fullmatch('[A-Za-z0-9_-]{8,100}',freeze_evidence_id),'FREEZE_ID_INVALID')
    record=dict(job_sha256=job_hash,configuration_sha256=reserved_job['configuration_sha256'],native_sha256=reserved_job['native_sha256'],manifest_path=reserved_job['manifest_path'],attempt_id=attempt_id,dump_path=str(output),format='current-viva-checkpoint-v1',database=SOURCE,revision=REVISION,server_uuid=approved_uuid,
                tables=35,triggers=0,backup_sha256=dump_sha256,backup_size=dump_size,
                before_sha256=sha(canonical(before)),after_sha256=sha(canonical(after)),
                before_capture_sha256=sha(canonical(pre)),after_capture_sha256=sha(canonical(post)),
                before_capture_id=pre['snapshot']['owner'],after_capture_id=post['snapshot']['owner'],
                fingerprint_algorithm=typed.ALGORITHM,freeze_evidence_id=freeze_evidence_id,
                source_preservation='MATCH',recovery_verification='NOT_EXECUTED',status='OFFLINE_DRAFT_NOT_EXECUTION_EVIDENCE')
    if stdout_proof is not None:
        need(type(stdout_proof) is StdoutManifestProof and id(stdout_proof) in _STDOUT_MANIFEST_PROOFS,'ISSUED_STDOUT_MANIFEST_PROOF_REQUIRED')
        original,raw_proof=_STDOUT_MANIFEST_PROOFS[id(stdout_proof)];proof=json.loads(raw_proof)
        need(original is stdout_proof and proof['attempt_id']==attempt_id and proof['job_sha256']==job_hash
             and proof['output_path']==str(output) and proof['backup_sha256']==dump_sha256
             and proof['backup_size']==dump_size and proof['post_capture_sha256']==sha(canonical(post))
             and proof['exit_code']==0 and proof['cleanup_complete'] is True and proof['flush_confirmed'] is True,
             'STDOUT_MANIFEST_PROOF_MISMATCH')
        record['stdout_v1']=proof
    binding=sha(canonical(record))
    keys=consumption.reserve(attempt_id,(sha(canonical(pre)),sha(canonical(post))),binding)
    raw=canonical(record)
    consumption.complete(keys,binding)
    return raw,sha(raw)

def failure_record(phase):
    need(phase in ('BASELINE','DUMP','POST_CAPTURE','MANIFEST'),'UNKNOWN_PHASE')
    return canonical(dict(status='INCOMPLETE_PRESERVE_NO_RETRY_NO_CLEANUP',phase=phase))

class DisabledCheckpointExecution:
    def connect(self,*args,**kwargs):raise Stop('CHECKPOINT_EXECUTION_DISABLED')
    def backup(self,*args,**kwargs):raise Stop('CHECKPOINT_EXECUTION_DISABLED')
    def restore(self,*args,**kwargs):raise Stop('CHECKPOINT_EXECUTION_DISABLED')
    def write(self,*args,**kwargs):raise Stop('CHECKPOINT_EXECUTION_DISABLED')

if __name__=='__main__':
    print('CHECKPOINT=OFFLINE_PREPARATION_ONLY; EXECUTION_DISABLED')
    raise SystemExit(2)

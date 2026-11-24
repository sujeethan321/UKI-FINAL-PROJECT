"""Dedicated DBA-operated VIVA recovery/migration workflow. No I/O on import.

Every executable mode requires its own exact authorization, absent evidence
destination, hidden credentials and fresh DBA gate. Historical MR/native runners
remain unchanged. Never import application settings or an application engine.
"""
import argparse
import copy
import ctypes
import getpass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import warnings
import shutil
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from datetime import date,datetime
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value
g=load('viva_current_guards','backend/scripts/viva_pending_migrations.py')
d=load('viva_current_metadata','backend/scripts/mr09_mysql_adapter.py')
w=load('viva_current_windows','backend/scripts/checkpoint_windows_io.py')
sys.path.insert(0,str(ROOT/'backend'))
from app.core import viva_tls as tls
SOURCE=g.SOURCE;SCRATCH=g.SCRATCH;CHAIN=g.CHAIN
SCRATCH_USER=g.SCRATCH_ACCOUNT.split('@')[0]
PARENT=Path(r'C:\Users\admin\AppData\Local\LankaPex\VivaCheckpoints')
MYSQL=Path(r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe')
DUMP=MYSQL.with_name('mysqldump.exe')
TOKENS={'backup':'ONE_CURRENT_VIVA_BACKUP','restore':'ONE_CURRENT_SCRATCH_RESTORE',
        'rehearse':'ONE_CURRENT_SCRATCH_REHEARSAL','migrate':'ONE_CURRENT_VIVA_MIGRATION'}
MAX_SECONDS=300
TABLE_NAMES=frozenset(g.recovery_contract().TABLES)
_RUN=ContextVar('viva_execution_diagnostics',default=None)

def run_state():
    value=_RUN.get()
    if value is None:
        value=dict(stage='PRECHECK',database_connection_started=False,baseline_capture_started=False,native_dump_started=False)
        _RUN.set(value)
    return value

VALUE_CODES={
    'Unsupported MySQL type':'MYSQL_TYPE_UNSUPPORTED','Unreviewed integer display width':'MYSQL_INTEGER_WIDTH_UNSUPPORTED',
    'Unsupported SQL default':'MYSQL_DEFAULT_UNSUPPORTED','Invalid default precision':'MYSQL_DEFAULT_PRECISION_INVALID',
    'Column inventory mismatch':'SCHEMA_COLUMN_INVENTORY_MISMATCH','Primary key mismatch':'SCHEMA_PRIMARY_KEY_MISMATCH',
    'Table options mismatch':'SCHEMA_TABLE_OPTIONS_MISMATCH','Named object mismatch':'SCHEMA_NAMED_OBJECT_MISMATCH',
    'Unexpected supporting index':'SCHEMA_SUPPORTING_INDEX_MISMATCH','Missing explicit index':'SCHEMA_EXPLICIT_INDEX_MISSING',
    'Missing FK supporting index':'SCHEMA_FK_SUPPORTING_INDEX_MISSING','Explicit index mismatch':'SCHEMA_INDEX_MISMATCH',
    'Unsupported CHECK syntax':'CHECK_SYNTAX_UNSUPPORTED','Unreviewed CHECK suffix':'CHECK_SUFFIX_UNSUPPORTED',
    'Unreviewed CHECK function':'CHECK_FUNCTION_UNSUPPORTED','Unexpected CHECK token':'CHECK_TOKEN_UNSUPPORTED',
    'Incomplete CHECK':'CHECK_DEFINITION_INCOMPLETE','Invalid CHECK definition':'CHECK_DEFINITION_INVALID',
    'Unsupported MySQL CHECK metadata escape':'CHECK_METADATA_ESCAPE_UNSUPPORTED',
    'Invalid MySQL CHECK metadata encoding':'CHECK_METADATA_ENCODING_INVALID',
    'Unsupported CHECK literal escape':'CHECK_LITERAL_ESCAPE_UNSUPPORTED',
    'VIVA_CA_PATH_MISMATCH':'VIVA_CA_PATH_MISMATCH','VIVA_STRICT_TLS_UNSUPPORTED':'VIVA_STRICT_TLS_UNSUPPORTED',
    'VIVA_TLS_SOCKET_REQUIRED':'VIVA_TLS_SOCKET_REQUIRED','VIVA_TLS_POLICY_MISMATCH':'VIVA_TLS_POLICY_MISMATCH',
    'VIVA_SERVER_CERTIFICATE_MISMATCH':'VIVA_SERVER_CERTIFICATE_MISMATCH'}

def source_location(error):
    """Code identity only: never exception text, SQL, arguments or frame locals."""
    result=dict(source_module='UNAVAILABLE',source_function='UNAVAILABLE');tb=error.__traceback__
    while tb:
        frame=tb.tb_frame;filename=str(frame.f_globals.get('__file__','')).replace('\\','/');function=frame.f_code.co_name
        relative=filename[len(str(ROOT).replace('\\','/'))+1:] if filename.startswith(str(ROOT).replace('\\','/')+'/') else ''
        module=relative if relative in {'backend/scripts/viva_migration_execute.py','backend/scripts/viva_pending_migrations.py','backend/scripts/mr09_mysql_adapter.py','backend/scripts/mr03_adapter.py','backend/scripts/mr02_rehearsal.py','backend/scripts/mr07_canonical.py','backend/scripts/mr05_source_contracts.py','backend/scripts/checkpoint_dump_inspection.py','backend/scripts/checkpoint_windows_io.py','backend/app/core/viva_tls.py','backend/app/services/schema_integrity.py'} else ''
        if not module:
            for package in ('pymysql','sqlalchemy','alembic'):
                marker='/site-packages/'+package+'/'
                if marker in filename:module=package+'/'+filename.split(marker,1)[1]
        if module and function.isidentifier() and function not in ('need','require','wrapped','dba_stop'):
            result=dict(source_module=module,source_function=function)
        tb=tb.tb_next
    return result

@contextmanager
def phase(substage,*,table=None,columns=(),constraint=None):
    try:yield
    except BaseException as error:
        if not hasattr(error,'viva_failure'):
            details=dict(run_state(),substage=substage,**source_location(error))
            if type(table) is str and table in TABLE_NAMES:details['schema_table']=table
            if type(constraint) is str and re.fullmatch(r'[a-z][a-z0-9_]{0,63}',constraint):details['schema_constraint']=constraint
            if type(error) is ValueError and details['source_module']=='backend/scripts/mr07_canonical.py' and details['source_function']=='verify_table':
                match=re.fullmatch(r'Column definition mismatch: ([a-z][a-z0-9_]{0,63})',str(error))
                if match and match[1] in columns:details['schema_column']=match[1]
            error.viva_failure=details
        raise

def traced(substage):
    def decorate(function):
        @wraps(function)
        def wrapped(*args,**kwargs):
            with phase(substage):return function(*args,**kwargs)
        return wrapped
    return decorate

def failure_details(error):
    details=getattr(error,'viva_failure',None)
    details=details if type(details) is dict else dict(run_state(),substage='UNCLASSIFIED',**source_location(error))
    safe={key:details.get(key) is True for key in ('database_connection_started','baseline_capture_started','native_dump_started')}
    safe['stage']=details.get('stage') if details.get('stage') in ('PRECHECK','RESERVE','SOURCE_BEFORE','DUMP','RESTORE','SOURCE_AFTER','READ_ONLY_SOURCE',*CHAIN) else 'UNCLASSIFIED'
    substage=details.get('substage');safe['substage']=substage if type(substage) is str and re.fullmatch('[A-Z_]{1,60}',substage) else 'UNCLASSIFIED'
    location=source_location(error)
    # Tracebacks may be cleared after unwinding (including exception holders).
    # Retain the already captured code identity, never arbitrary exception text.
    if location['source_module']=='UNAVAILABLE':
        module=details.get('source_module');function=details.get('source_function')
        if (type(module) is str and re.fullmatch(r'backend/(?:scripts|app/core|app/services)/[a-z][a-z0-9_]*\.py|(?:pymysql|sqlalchemy|alembic)/(?:[a-z_]+/)*[a-z_]+\.py',module)
                and type(function) is str and function.isidentifier()):location=dict(source_module=module,source_function=function)
    safe.update(location)
    if type(details.get('schema_table')) is str and details['schema_table'] in TABLE_NAMES:safe['schema_table']=details['schema_table']
    column=details.get('schema_column')
    if 'schema_table' in safe and type(column) is str and re.fullmatch('[a-z][a-z0-9_]{0,63}',column):safe['schema_column']=column
    constraint=details.get('schema_constraint')
    if 'schema_table' in safe and type(constraint) is str and re.fullmatch('[a-z][a-z0-9_]{0,63}',constraint):safe['schema_constraint']=constraint
    gate=getattr(error,'dba_diagnostics',None)
    if type(gate) is dict:
        for key in ('expected_client_count','foreground_count','internal_daemon_count','observed_client_count','unexpected_client_count','missing_expected_count','sql_connection_id','handshake_connection_id'):
            value=gate.get(key)
            if type(value) is int and 0<=value<2**64:safe['dba_'+key]=value
        if type(gate.get('self_visible')) is bool:safe['dba_self_visible']=gate['self_visible']
        for key in ('expected_connection_ids','unexpected_connection_ids','missing_connection_ids'):
            values=gate.get(key)
            if type(values) is list and len(values)<=8 and all(valid_connection_id(value) for value in values):safe['dba_'+key]=','.join(str(value) for value in values) or 'NONE'
        if type(gate.get('id_list_truncated')) is bool:safe['dba_id_list_truncated']=gate['id_list_truncated']
        if gate.get('daemon_kind') in ('event_scheduler','compress_gtid_table'):safe['dba_daemon_kind']=gate['daemon_kind']
        if gate.get('daemon_reason') in ('USER_MISMATCH','COMMAND_MISMATCH','CONNECTION_TYPE_PRESENT','HOST_MISMATCH','DATABASE_PRESENT','FIELDS_MISSING'):safe['dba_daemon_reason']=gate['daemon_reason']
    if getattr(error,'dba_cleanup',None)=='INCOMPLETE':safe['dba_cleanup']='INCOMPLETE'
    code=getattr(error,'dba_mysql_code',None)
    if type(code) is int and 0<=code<=65535:safe['dba_mysql_code']=code
    return safe

class VivaStop(RuntimeError):pass
def need(value,code):
    if not value:raise VivaStop(code)
WINDOWS_CODES=frozenset(('WINDOWS_REQUIRED TOKEN_READ_FAILED TOKEN_SIZE_INVALID SID_READ_FAILED SECURITY_DESCRIPTOR_FAILED '
    'CLOSE_HANDLE_FAILED CLOSED_HANDLE HANDLE_METADATA_FAILED HANDLE_REPARSE_OR_DEVICE HANDLE_TYPE_OR_LINKS_INVALID '
    'FINAL_PATH_FAILED FINAL_PATH_NOT_LOCAL FINAL_PATH_MISMATCH HANDLE_ACL_READ_FAILED HANDLE_OWNER_OR_DACL_INVALID '
    'DACL_CONTROL_READ_FAILED DACL_NOT_PROTECTED EXTRA_ACES ACE_READ_FAILED ACE_TYPE_OR_INHERITANCE_INVALID '
    'ACE_RIGHTS_INVALID ACE_IDENTITIES_INVALID INVALID_WRITE WRITE_FILE_FAILED SHORT_WRITE_PRESERVE_STATE FILE_FLUSH_FAILED '
    'EXCLUSIVE_EVIDENCE_DIRECTORY_FAILED').split())
WINDOWS_APIS=frozenset(('CreateFileW CloseHandle OpenProcessToken GetTokenInformation ConvertSidToStringSidW '
    'ConvertStringSecurityDescriptorToSecurityDescriptorW GetFileInformationByHandle GetFinalPathNameByHandleW '
    'GetSecurityInfo GetSecurityDescriptorControl GetAce WriteFile FlushFileBuffers CreateDirectoryW').split())

def diagnostic(error):
    if type(error) is VivaStop:return str(error)
    if getattr(error,'dba_failure_code',None) in ('DBA_VISIBILITY_PERMISSION_DENIED','DBA_VISIBILITY_UNAVAILABLE','DBA_QUERY_FAILED'):return error.dba_failure_code
    if isinstance(error,w.WindowsIOBlocked):
        code=str(error)
        if code in WINDOWS_CODES:return code
        if re.fullmatch(r'EXCLUSIVE_OPEN_FAILED_WIN32_[0-9]{1,10}',code):return 'EXCLUSIVE_OPEN_FAILED'
    if type(error) is ValueError:
        if str(error) in VALUE_CODES:return VALUE_CODES[str(error)]
        if str(error).startswith('Column definition mismatch: '):return 'SCHEMA_COLUMN_DEFINITION_MISMATCH'
        if str(error) in ('foreign_keys mismatch','unique_constraints mismatch','checks mismatch'):return 'SCHEMA_RELATIONSHIP_OR_CHECK_MISMATCH'
        location=source_location(error)
        if location['source_module']=='backend/scripts/checkpoint_dump_inspection.py' and location['source_function']=='literal':return 'DUMP_LITERAL_VALUE_INVALID'
        if location['source_function']=='encoded':return 'EVIDENCE_VALUE_INVALID'
        if location['source_module'].startswith('pymysql/'):return 'DBAPI_VALUE_ERROR'
        return 'VALUE_ERROR_DETAILS_REDACTED'
    if type(error).__name__=='GuardFailure' and type(getattr(error,'code',None)) is str and re.fullmatch(r'MR[0-9]{2}_[A-Z0-9_]{1,100}',error.code):return error.code
    return 'EXTERNAL_FAILURE_DETAILS_REDACTED'

def windows_details(error):
    # Never serialize exception text, paths, SIDs, credentials or raw stderr.
    details={}
    location=getattr(error,'windows_location',None)
    if type(location) is str and re.fullmatch(r'WINDOWS_INIT|OPERATOR_IDENTITY|ANCESTOR_[0-9]{1,2}_(?:OPEN|FACTS)|PRIVATE_DESCRIPTOR|EVIDENCE_(?:CREATE|OPEN|FACTS)|ARTIFACT_(?:OPEN|FACTS|CLOSE)|PARENT_CLEANUP',location):details['windows_location']=location
    operation=getattr(error,'operation',None)
    if type(operation) is str and operation in WINDOWS_APIS:details['windows_operation']=operation
    code=getattr(error,'winerror',None)
    if type(code) is int and 0<=code<=0xFFFFFFFF and (isinstance(error,w.WindowsIOBlocked) or details):details['windows_error']=code
    if getattr(error,'evidence_cleanup',None)=='INCOMPLETE':details['evidence_cleanup']='INCOMPLETE'
    return details

@contextmanager
def windows_step(location):
    try:yield
    except BaseException as error:
        if not hasattr(error,'windows_location'):error.windows_location=location
        raise

def hold_checkpoint_parent(api,sid,handles,observe=None):
    for index,ancestor in enumerate(reversed((PARENT,*PARENT.parents))):
        with windows_step('ANCESTOR_'+str(index)+'_OPEN'):
            handle=api.open(ancestor,directory=True,read_acl=True);handles.append(handle)
        with windows_step('ANCESTOR_'+str(index)+'_FACTS'):
            api.facts(handle,ancestor,directory=True,owner=sid if ancestor==PARENT else None)
        if observe:observe(index)

def inspect_windows(argv):
    """Same pre-creation checks, read-only: no credentials, DB or output creation."""
    parser=argparse.ArgumentParser(description='Read-only existing checkpoint-parent inspection')
    parser.add_argument('--read-only',action='store_true',required=True)
    parser.add_argument('--confirm-parent',type=Path,required=True)
    parser.add_argument('--operator-sid',required=True)
    args=parser.parse_args(argv)
    need(args.confirm_parent==PARENT and re.fullmatch(r'S-1-5-21-(?:[0-9]+-){3}[0-9]+',args.operator_sid),'EXACT_PARENT_AND_OPERATOR_REQUIRED')
    handles=[];primary=None
    try:
        with windows_step('WINDOWS_INIT'):api=w._Win32()
        with windows_step('OPERATOR_IDENTITY'):
            sid=api.operator_sid();need(sid==args.operator_sid,'INSPECTION_OPERATOR_IDENTITY_MISMATCH')
        print('WINDOWS_OPERATOR=APPROVED_SID_MATCH')
        hold_checkpoint_parent(api,sid,handles,lambda index:print('WINDOWS_ANCESTOR_'+str(index)+'=PASS_READ_ONLY; ACCESS=0x20080'))
        with windows_step('PRIVATE_DESCRIPTOR'):
            with api.security(sid,True):pass  # In-memory SDDL parsing only.
    except BaseException as error:primary=error;raise
    finally:
        failed=False
        for handle in reversed(handles):
            try:
                with windows_step('PARENT_CLEANUP'):handle.close()
            except BaseException as error:
                failed=True
                if primary is None:primary=error
        if failed:
            primary.evidence_cleanup='INCOMPLETE'
            if sys.exc_info()[0] is None:raise primary
    print('WINDOWS_INSPECTION=PASS_READ_ONLY; PRECREATE_CHECKS=PASS; CREATION_NOT_TESTED; DATABASE_CONNECTIONS=0; FILES_CREATED=0')
@traced('EVIDENCE_SERIALIZATION')
def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest().upper()
def file_sha(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):result.update(block)
    return result.hexdigest().upper()
def provenance():
    files=list((ROOT/'backend/alembic/versions').glob('*.py'))+list((ROOT/'backend/scripts').glob('mr*.py'))+[Path(__file__),ROOT/'backend/scripts/viva_pending_migrations.py',ROOT/'backend/scripts/security_recovery_plan.py',ROOT/'backend/scripts/checkpoint_dump_inspection.py',ROOT/'backend/scripts/checkpoint_windows_io.py',ROOT/'backend/app/core/viva_tls.py',ROOT/'backend/contracts/MR07_CANONICAL_OBJECTS.json',ROOT/'backend/viva_pending_alembic/env.py']
    return {str(path.relative_to(ROOT)):file_sha(path) for path in sorted(files)}
def password(label):
    need(sys.stdin.isatty(),'PRIVATE_CONSOLE_REQUIRED')
    with warnings.catch_warnings():
        warnings.simplefilter('error',getpass.GetPassWarning);value=getpass.getpass(label+': ')
    need(bool(value) and '\0' not in value,'PASSWORD_REQUIRED');return value
def target(database,account):g.target_guard(database,account+'@127.0.0.1')
def authorization(args):
    expected=SCRATCH if args.mode in ('restore','rehearse') else SOURCE
    need(args.execute and args.authorize==TOKENS[args.mode] and args.confirm_target==expected,'SEPARATE_EXACT_AUTHORIZATION_REQUIRED')
    need(args.freeze=='FREEZE_MAINTAINED','CONTINUOUS_FREEZE_REQUIRED')
    need(args.evidence.parent==PARENT and re.fullmatch('viva-current-[a-z0-9-]{12,90}',args.evidence.name),'PRIVATE_NEW_EVIDENCE_PATH_REQUIRED')

class PrivateEvidence:
    """Atomic protected creation in an existing operator/SYSTEM-only parent."""
    def __init__(self,path):self.path=path;self.api=None;self.handles=[]
    def __enter__(self):
        try:
            need(self.path.parent==PARENT,'PRIVATE_NEW_EVIDENCE_PATH_REQUIRED')
            with windows_step('WINDOWS_INIT'):self.api=w._Win32()
            with windows_step('OPERATOR_IDENTITY'):self.sid=self.api.operator_sid()
            hold_checkpoint_parent(self.api,self.sid,self.handles)
            need(not self.path.exists(),'EXISTING_EVIDENCE_STOP')
            with windows_step('PRIVATE_DESCRIPTOR'):
                with self.api.security(self.sid,True) as security:
                    with windows_step('EVIDENCE_CREATE'):
                        w.win_need(self.api.k.CreateDirectoryW(str(self.path),ctypes.byref(security)),'EXCLUSIVE_EVIDENCE_DIRECTORY_FAILED','CreateDirectoryW')
            with windows_step('EVIDENCE_OPEN'):
                handle=self.api.open(self.path,directory=True);self.handles.append(handle)
            with windows_step('EVIDENCE_FACTS'):self.api.facts(handle,self.path,directory=True,owner=self.sid)
            self.write('attempt.json',dict(status='RESERVED_NO_RETRY',pid=os.getpid()))
            return self
        except BaseException as primary:
            self.__exit__(type(primary),primary,primary.__traceback__);raise
    @contextmanager
    def open_new(self,name):
        need(re.fullmatch(r'[a-z0-9_-]+\.(json|sql)',name),'ARTIFACT_NAME_INVALID')
        with windows_step('ARTIFACT_OPEN'):
            with self.api.security(self.sid,False) as security:
                handle=self.api.open(self.path/name,create=True,security=security)
        primary=None
        try:
            with windows_step('ARTIFACT_FACTS'):self.api.facts(handle,self.path/name,directory=False,owner=self.sid)
            yield handle
        except BaseException as error:primary=error;raise
        finally:
            try:
                with windows_step('ARTIFACT_CLOSE'):handle.close()
            except BaseException:
                if primary is None:raise
                primary.evidence_cleanup='INCOMPLETE'
    def write(self,name,value):
        with self.open_new(name) as handle:
            self.api.write_and_flush(handle,encoded(value));self.api.facts(handle,self.path/name,directory=False,owner=self.sid)
    def __exit__(self,*args):
        errors=[]
        for handle in reversed(self.handles):
            try:
                with windows_step('PARENT_CLEANUP'):handle.close()
            except BaseException:errors.append(True)
        self.handles=[]
        if errors:
            if not args[0]:raise RuntimeError('EVIDENCE_HANDLE_CLEANUP_INCOMPLETE')
            args[1].evidence_cleanup='INCOMPLETE'

def private_read(path):
    """Read evidence only under approved parent; inspect existing held handles."""
    need(path.parent.parent==PARENT and re.fullmatch(r'[a-z0-9_-]+\.(json|sql)',path.name),'PRIVATE_ARTIFACT_REQUIRED')
    api=w._Win32();sid=api.operator_sid();handles=[]
    try:
        for ancestor in reversed((path.parent,*path.parent.parents)):
            handle=api.open(ancestor,directory=True,read_acl=True);handles.append(handle)
            api.facts(handle,ancestor,directory=True,owner=sid if ancestor in (PARENT,path.parent) else None)
        handle=api.open(path);handles.append(handle);api.facts(handle,path,directory=False,owner=sid)
        # Ancestors deny deletion/rename while reading; operator and SYSTEM only.
        return path.read_bytes()
    finally:
        for handle in reversed(handles):handle.close()

@traced('APPROVED_BACKUP_BINDING')
def read_bundle(path,approved):
    raw=private_read(path);need(sha(raw)==approved.upper(),'APPROVED_MANIFEST_HASH_MISMATCH')
    result=json.loads(raw);need(result['format']=='viva-current-backup-v1' and result['provenance']==provenance(),'BACKUP_PROVENANCE_MISMATCH')
    need(result['source']==SOURCE and result['uuid']==g.UUID and result['revision']==CHAIN[0],'BACKUP_IDENTITY_MISMATCH')
    baseline_raw=private_read(path.parent/'baseline.json')
    need(sha(baseline_raw)==result['baseline_sha256'],'BASELINE_HASH_MISMATCH')
    need(file_sha(path.parent/'viva.sql')==result['dump_sha256'],'DUMP_HASH_MISMATCH')
    return result,json.loads(baseline_raw)

@traced('DATABASE_QUERY')
def query(raw,sql,parameters=None):
    from pymysql.cursors import DictCursor
    with raw.cursor(DictCursor) as cursor:
        # PyMySQL 1.2 performs percent interpolation even for an empty tuple.
        # Parameter-free SQL must be sent without a binding argument.
        if parameters is None or parameters==():cursor.execute(sql)
        else:cursor.execute(sql,parameters)
        return list(cursor.fetchall())
def scalar(raw,sql,parameters=()):
    rows=query(raw,sql,parameters);need(len(rows)==1 and len(rows[0])==1,'SCALAR_SHAPE_INVALID');return next(iter(rows[0].values()))
@traced('ACCOUNT_PRIVILEGES')
def grants(raw,database,account,rights):
    partial=scalar(raw,'SELECT @@GLOBAL.partial_revokes');scope=database if partial else database.replace('_',r'\_')
    recipient=r"(?:`"+re.escape(account)+r"`|'"+re.escape(account)+r"')@(?:`127\.0\.0\.1`|'127\.0\.0\.1')"
    found=set()
    for row in query(raw,'SHOW GRANTS FOR CURRENT_USER()'):
        text=next(iter(row.values()))
        if re.fullmatch(r'GRANT USAGE ON \*\.\* TO '+recipient,text):continue
        match=re.fullmatch(r'GRANT (.*?) ON `(.*?)`\.\* TO '+recipient,text)
        need(match and match[2]==scope and 'GRANT OPTION' not in text,'UNSAFE_EFFECTIVE_GRANTS')
        found.update(match[1].split(', '))
    need(found==rights,'SCOPED_PRIVILEGES_MISMATCH')
@traced('DATABASE_IDENTITY')
def identity(raw,database,account,*,check_grants=True):
    with phase('TLS_SOCKET_VERIFICATION'):tls.verify_socket(raw._sock)
    row=query(raw,'SELECT @@server_uuid AS uuid,DATABASE() AS db,CURRENT_USER() AS account,VERSION() AS version,@@port AS port,CURRENT_ROLE() AS roles,@@GLOBAL.mandatory_roles AS mandatory,@@SESSION.foreign_key_checks AS fk,@@SESSION.unique_checks AS uq,@@SESSION.sql_mode AS mode')[0]
    need((row['uuid'],row['db'],row['account'],row['version'],row['port'])==(g.UUID,database,account+'@127.0.0.1','8.0.46',3306),'LIVE_IDENTITY_MISMATCH')
    need(row['roles']=='NONE' and not row['mandatory'] and row['fk']==row['uq']==1 and {'STRICT_TRANS_TABLES','STRICT_ALL_TABLES'}&set(row['mode'].split(',')),'SESSION_ENFORCEMENT_OR_ROLES_INVALID')
    need(scalar(raw,'SELECT @@GLOBAL.log_bin')==1,'BINARY_LOGGING_DISABLED')
    if check_grants:grants(raw,database,account,g.RIGHTS)
    return row
@contextmanager
def connect(database,account,secret):
    import pymysql
    target(database,account)
    with phase('TLS_CONFIGURATION'):context=tls.context()
    with phase('DATABASE_CONNECT'):
        run_state()['database_connection_started']=True
        raw=pymysql.connect(host='127.0.0.1',port=3306,user=account,password=secret,database=database,
            ssl=context,charset='utf8mb4',collation='utf8mb4_unicode_ci',autocommit=True,connect_timeout=5,read_timeout=30,write_timeout=30,
            cursorclass=pymysql.cursors.DictCursor,local_infile=False,init_command="SET time_zone='+00:00'")
    primary=None
    try:identity(raw,database,account);yield raw
    except BaseException as error:primary=error;raise
    finally:
        try:raw.close()
        except BaseException:
            if primary is None:raise
            primary.connection_cleanup='INCOMPLETE'

DAEMON_USERS={'thread/sql/event_scheduler':'event_scheduler','thread/sql/compress_gtid_table':None}
THREAD_FIELDS=frozenset(('id','user','thread_name','command','host','database','connection_type'))

def internal_mysql_daemon(row):
    # Instrument names are server-owned. Never exclude clients by username alone.
    if type(row) is not dict or not THREAD_FIELDS<=row.keys():return False
    name=row.get('thread_name')
    return (type(name) is str and name in DAEMON_USERS and row.get('user')==DAEMON_USERS[name]
            and row.get('command')=='Daemon' and row.get('connection_type') is None
            and row.get('host') in (None,'localhost') and row.get('database') is None)

def dba_stop(code,**details):
    error=VivaStop(code);error.dba_diagnostics=details;raise error

def valid_connection_id(value):return type(value) is int and 0<value<2**64

@traced('CONNECTION_ID_VERIFICATION')
def verified_connection_id(raw):
    value=scalar(raw,'SELECT CONNECTION_ID()');handshake=raw.thread_id()
    if not valid_connection_id(value) or not valid_connection_id(handshake):dba_stop('DBA_CONNECTION_ID_INVALID')
    if value!=handshake:dba_stop('DBA_CONNECTION_ID_MISMATCH',sql_connection_id=value,handshake_connection_id=handshake)
    bound=vars(raw).get('_viva_bound_connection_id')
    if bound is not None and not valid_connection_id(bound):dba_stop('DBA_CONNECTION_ID_INVALID')
    if bound is not None and bound!=value:dba_stop('DBA_CONNECTION_ID_CHANGED',sql_connection_id=value,handshake_connection_id=bound)
    raw._viva_bound_connection_id=value
    return value

def gate_for(user,secret,*connections):
    """Recheck each still-owned socket; never reuse a cached or reconnected ID."""
    return dba_gate(user,secret,[verified_connection_id(raw) for raw in connections])

@traced('DBA_CLIENT_INVENTORY')
def check_client_inventory(rows,allowed_ids,own,user):
    if (type(allowed_ids) is not list or not 1<=len(allowed_ids)<=2 or not all(valid_connection_id(value) for value in allowed_ids)
            or len(set(allowed_ids))!=len(allowed_ids) or not valid_connection_id(own) or own in allowed_ids):dba_stop('DBA_EXPECTED_CONNECTION_IDS_INVALID')
    expected=set(allowed_ids)|{own};summary=dict(expected_client_count=len(expected))
    if type(rows) is not list:dba_stop('DBA_THREAD_METADATA_INCOMPLETE',**summary)
    summary['foreground_count']=len(rows);seen=set();clients=[];internal=0
    for row in rows:
        if type(row) is not dict or not THREAD_FIELDS<=row.keys():dba_stop('DBA_THREAD_METADATA_INCOMPLETE',**summary)
        if (not valid_connection_id(row['id']) or any(value is not None and type(value) is not str for key,value in row.items() if key in THREAD_FIELDS-{'id'})
                or not row['thread_name'] or not row['command']):dba_stop('DBA_THREAD_METADATA_INVALID',**summary)
        if row['id'] in seen:dba_stop('DBA_DUPLICATE_PROCESSLIST_ID',**summary)
        seen.add(row['id'])
        if row['thread_name'] in DAEMON_USERS:
            if not internal_mysql_daemon(row):
                reason=('USER_MISMATCH' if row['user']!=DAEMON_USERS[row['thread_name']] else 'COMMAND_MISMATCH' if row['command']!='Daemon'
                    else 'CONNECTION_TYPE_PRESENT' if row['connection_type'] is not None else 'HOST_MISMATCH' if row['host'] not in (None,'localhost') else 'DATABASE_PRESENT')
                dba_stop('DBA_INTERNAL_DAEMON_CLASSIFICATION_FAILED',**summary,daemon_kind=row['thread_name'].rsplit('/',1)[1],daemon_reason=reason)
            internal+=1
        else:clients.append(row)
    visible={row['id'] for row in clients};missing=expected-visible;extra=visible-expected
    summary.update(internal_daemon_count=internal,observed_client_count=len(clients),unexpected_client_count=len(extra),missing_expected_count=len(missing),self_visible=own in visible,
        expected_connection_ids=sorted(expected),unexpected_connection_ids=sorted(extra)[:8],missing_connection_ids=sorted(missing),id_list_truncated=len(extra)>8)
    if own not in visible:dba_stop('DBA_SELF_CONNECTION_NOT_VISIBLE',**summary)
    if missing and extra:dba_stop('DBA_UNEXPECTED_AND_MISSING_CLIENTS_STOP',**summary)
    if missing:dba_stop('DBA_EXPECTED_CONNECTION_NOT_VISIBLE',**summary)
    if extra:dba_stop('DBA_UNEXPECTED_CLIENTS_STOP',**summary)
    roles=[]
    for row in clients:
        if row['thread_name']!='thread/sql/one_connection' or row['connection_type']!='SSL/TLS':dba_stop('DBA_EXPECTED_CLIENT_IDENTITY_MISMATCH',**summary)
        if row['id']==own:
            if row['user']!=user or row['database'] is not None or row['command']!='Query':dba_stop('DBA_EXPECTED_CLIENT_IDENTITY_MISMATCH',**summary)
        else:
            role=(row['database'],row['user'])
            if role not in ((SOURCE,g.MIGRATOR.split('@')[0]),(SCRATCH,SCRATCH_USER)) or row['command']!='Sleep':dba_stop('DBA_EXPECTED_CLIENT_IDENTITY_MISMATCH',**summary)
            roles.append(role)
    if roles.count((SOURCE,g.MIGRATOR.split('@')[0]))!=1 or len(set(roles))!=len(roles):dba_stop('DBA_EXPECTED_CLIENT_IDENTITY_MISMATCH',**summary)
    return summary

@traced('DBA_PREFLIGHT')
def dba_gate(user,secret,allowed_ids):
    """Fresh independent DBA visibility; never changes privileges or settings."""
    import pymysql
    raw=pymysql.connect(host='127.0.0.1',port=3306,user=user,password=secret,ssl=tls.context(),autocommit=True,
        connect_timeout=5,read_timeout=10,cursorclass=pymysql.cursors.DictCursor)
    primary=None
    try:
        tls.verify_socket(raw._sock);need(scalar(raw,'SELECT @@server_uuid')==g.UUID,'DBA_SERVER_MISMATCH')
        authenticated=scalar(raw,'SELECT CURRENT_USER()')
        need(type(authenticated) is str and authenticated.split('@')[0]==user,'DBA_ACCOUNT_MISMATCH')
        own=verified_connection_id(raw)
        privileges=' '.join(next(iter(row.values())) for row in query(raw,'SHOW GRANTS FOR CURRENT_USER()'))
        need(re.search(r'GRANT (?:ALL PRIVILEGES|[^\n]*\bPROCESS\b[^\n]*) ON \*\.\*',privileges) is not None,'DBA_PROCESS_VISIBILITY_REQUIRED')
        for right in ('SELECT','EVENT'):
            need(re.search(r'GRANT (?:ALL PRIVILEGES|[^\n]*\b'+right+r'\b[^\n]*) ON \*\.\*',privileges) is not None,'DBA_METADATA_VISIBILITY_REQUIRED')
        sessions=query(raw,"SELECT PROCESSLIST_ID AS id,PROCESSLIST_USER AS user,NAME AS thread_name,PROCESSLIST_COMMAND AS command,PROCESSLIST_HOST AS host,PROCESSLIST_DB AS `database`,CONNECTION_TYPE AS connection_type FROM performance_schema.threads WHERE TYPE='FOREGROUND'")
        inventory=check_client_inventory(sessions,allowed_ids,own,user);allowed=set(allowed_ids)|{own}
        need(not query(raw,'SELECT trx_mysql_thread_id AS id FROM information_schema.innodb_trx WHERE trx_mysql_thread_id NOT IN ('+','.join('%s' for _ in allowed)+')',tuple(allowed)),'UNEXPLAINED_TRANSACTION')
        need(not query(raw,"SELECT EVENT_NAME FROM information_schema.EVENTS WHERE STATUS='ENABLED'"),'EVENT_WRITER_ENABLED')
        need(not query(raw,'SELECT ROUTINE_NAME FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA IN (%s,%s)',(SOURCE,SCRATCH)),'UNEXPECTED_ROUTINE')
        need(not query(raw,'SELECT EVENT_NAME FROM information_schema.EVENTS WHERE EVENT_SCHEMA IN (%s,%s)',(SOURCE,SCRATCH)),'UNEXPECTED_EVENT')
        need(not query(raw,"SELECT CHANNEL_NAME FROM performance_schema.replication_applier_status WHERE SERVICE_STATE='ON'"),'REPLICATION_WRITER_ENABLED')
        need(not query(raw,"SELECT OBJECT_NAME FROM performance_schema.metadata_locks WHERE LOCK_STATUS='PENDING'"),'PENDING_METADATA_LOCK')
        return dict(observed_at=time.time(),uuid=g.UUID,account=authenticated,certificate_sha256=tls.CERT_SHA256,writer_freeze='OPERATOR_CONTINUOUS_AND_DBA_CLIENT_GATE',client_inventory=inventory)
    except BaseException as error:
        primary=error
        if isinstance(error,pymysql.err.MySQLError) and error.args and type(error.args[0]) is int and 0<=error.args[0]<=65535:
            error.dba_mysql_code=error.args[0]
            error.dba_failure_code='DBA_VISIBILITY_PERMISSION_DENIED' if error.args[0] in (1044,1142,1143,1227) else 'DBA_VISIBILITY_UNAVAILABLE' if error.args[0]==1146 else 'DBA_QUERY_FAILED'
        raise
    finally:
        try:raw.close()
        except BaseException:
            if primary is None:raise VivaStop('DBA_CONNECTION_CLOSE_FAILED') from None
            primary.dba_cleanup='INCOMPLETE'

class Inspector(d.MySQLInspector):
    """Reuse reviewed metadata decoding; do not activate or alter MR09 transport."""
    def __init__(self,raw,database):self.raw=raw;self.database=database;self.raw_ddl_hashes={};self.expected_checks={}
    def read(self,key,table=None,columns=None):
        names=g.recovery_contract().tables_at(CHAIN[-1])
        if table is not None:need(table in names,'UNKNOWN_TABLE')
        if key=='ddl':
            with phase('METADATA_DDL',table=table):return query(self.raw,'SHOW CREATE TABLE `'+table+'`')
        need(key in d.SQL,'UNKNOWN_METADATA_READ')
        parameters=(self.database,table) if key in ('columns','keys','foreign_keys','checks','indexes') else (self.database,) if key in ('tables','triggers','routines','events') else ()
        with phase('METADATA_'+key.upper(),table=table):rows=query(self.raw,d.SQL[key],parameters)
        if key=='checks':
            for row in rows:
                name=row.get('CONSTRAINT_NAME')
                known=name if type(name) is str and name in self.expected_checks.get(table,set()) else None
                # Prevalidate with the SAME canonicalizer used by the adapter.
                # This adds attribution only; the full comparison still follows.
                with phase('CHECK_EXPRESSION_PARSING',table=table,constraint=known):d.c.check_key(row['CHECK_CLAUSE'],representation='mysql8_information_schema')
        return rows
    def table(self,name,expected):
        self.expected_checks[name]={check['name'] for check in expected['checks']}
        with phase('METADATA_NORMALIZATION',table=name):return super().table(name,expected)

@traced('SCHEMA_CAPTURE')
def schema(raw,database,revision,account):
    inspector=Inspector(raw,database)
    with phase('CANONICAL_CONTRACT'):contract=d.c.build()['stages'][revision]
    tables=inspector.read('tables');need({r['TABLE_NAME'] for r in tables}==set(contract['tables']) and all(r['TABLE_TYPE']=='BASE TABLE' for r in tables),'COMPLETE_TABLE_INVENTORY_MISMATCH')
    need(not inspector.read('routines') and not inspector.read('events'),'UNEXPECTED_STORED_OBJECT')
    collations={r['COLLATION_NAME']:r['CHARACTER_SET_NAME'] for r in inspector.read('collations')}
    result={};orphans=0
    for row in tables:
        name=row['TABLE_NAME'];expected=copy.deepcopy(contract['tables'][name])
        actual,effective,physical=inspector.table(name,expected)
        actual['options']={'engine':{'value':row['ENGINE']},'charset':{'value':collations[row['TABLE_COLLATION']]},'collation':{'value':row['TABLE_COLLATION']}}
        for column in expected['columns'].values():
            if column['type']['family'] not in ('VARCHAR','CHAR','TEXT'):continue
            if column['collation'] is not None:column['charset']=column['charset'] or collations[column['collation']]
            elif column['charset'] is not None:
                need(column['charset']=='ascii','UNAPPROVED_CHARACTER_SET_DEFAULT');column['collation']='ascii_general_ci'
            else:column['charset']=actual['options']['charset']['value'];column['collation']=row['TABLE_COLLATION']
        with phase('CANONICAL_SCHEMA_COMPARISON',table=name,columns=expected['columns']):d.c.verify_table(actual,expected)
        for fk in actual['foreign_keys']:
            statement=d.m.orphan_query(name,fk)
            need(scalar(raw,statement)==0,'FOREIGN_KEY_ORPHAN');orphans+=1
        result[name]=dict(metadata=actual,ddl=inspector.read('ddl',name)[0]['Create Table'])
    triggers=inspector.read('triggers');need({r['TRIGGER_NAME'] for r in triggers}==set(contract['triggers']),'TRIGGER_INVENTORY_MISMATCH')
    mode=scalar(raw,'SELECT @@SESSION.sql_mode')
    for row in triggers:
        expected=contract['triggers'][row['TRIGGER_NAME']]
        need((row['EVENT_OBJECT_TABLE'],row['ACTION_TIMING'],row['EVENT_MANIPULATION'],row['ACTION_ORIENTATION'])==(expected['table'],expected['timing'],expected['event'],'ROW')
             and row['ACTION_STATEMENT'].strip().rstrip(';')==expected['body'].strip().rstrip(';')
             and row['DEFINER']==account+'@127.0.0.1' and set(row['SQL_MODE'].split(','))==set(mode.split(','))
             and row['CHARACTER_SET_CLIENT']=='utf8mb4' and row['COLLATION_CONNECTION']=='utf8mb4_unicode_ci'
             and row['DATABASE_COLLATION']=='utf8mb4_unicode_ci','TRIGGER_DEFINITION_OR_CONTEXT_MISMATCH')
    return dict(tables=result,triggers=triggers,foreign_keys_checked=orphans)

@traced('ALEMBIC_REVISION')
def revision(raw):
    rows=query(raw,'SELECT version_num FROM alembic_version');need(len(rows)==1,'REVISION_SHAPE_INVALID');return rows[0]['version_num']
@traced('BASELINE_CAPTURE')
def snapshot(raw,database,account,expected,projections=None):
    run_state()['baseline_capture_started']=True
    identity(raw,database,account);need(revision(raw)==expected,'REVISION_MISMATCH')
    started=time.monotonic()
    primary=None
    try:
        with phase('SNAPSHOT_BEGIN'):
            raw.commit();query(raw,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');query(raw,'SET TRANSACTION READ ONLY')
            query(raw,'START TRANSACTION WITH CONSISTENT SNAPSHOT')
        need(revision(raw)==expected,'SNAPSHOT_REVISION_CHANGED')
        structure=schema(raw,database,expected,account);data={}
        for name,table in structure['tables'].items():
            if name=='alembic_version':continue
            columns=list(table['metadata']['columns']) if projections is None else projections.get(name)
            if columns is None:continue
            need(columns and set(columns)<=set(table['metadata']['columns']),'ORIGINAL_PROJECTION_MISMATCH')
            count=scalar(raw,'SELECT COUNT(*) FROM `'+name+'`');need(count<=d.a.MAX_ROWS,'ROW_LIMIT_EXCEEDED')
            with phase('ROW_CAPTURE',table=name):rows=query(raw,'SELECT '+','.join('`'+c+'`' for c in columns)+' FROM `'+name+'` LIMIT '+str(d.a.MAX_ROWS+1))
            with phase('TYPED_FINGERPRINT',table=name):
                validate_rows(rows,columns,table['metadata']['columns'])
                digest=d.a.fingerprint(rows,columns);need(digest['row_count']==count,'CAPTURE_INCOMPLETE')
            data[name]=dict(columns=columns,**digest)
            need(time.monotonic()-started<=MAX_SECONDS,'CAPTURE_DEADLINE_EXCEEDED')
        if expected!=CHAIN[0]:
            for name in set(structure['tables'])-g.recovery_contract().tables_at(CHAIN[0]):need(scalar(raw,'SELECT COUNT(*) FROM `'+name+'`')==0,'NEW_TABLE_NOT_EMPTY')
            if expected==CHAIN[-1]:need(scalar(raw,'SELECT COUNT(*) FROM customer_addresses WHERE create_request_key IS NOT NULL OR create_request_hash IS NOT NULL')==0,'HISTORICAL_ADDRESS_BACKFILL')
        need(revision(raw)==expected,'SNAPSHOT_REVISION_CHANGED')
        return dict(revision=expected,data=data,schema=structure)
    except BaseException as error:primary=error;raise
    finally:
        try:raw.rollback()
        except BaseException:
            if primary is None:raise
            primary.snapshot_cleanup='INCOMPLETE'

def validate_rows(rows,columns,metadata):
    """PyMySQL can return illegal/zero DATETIME as str: never hash it as text."""
    families={'BIGINT':int,'INT':int,'SMALLINT':int,'TINYINT':int,'DECIMAL':Decimal,'DATETIME':datetime,'DATE':date,'VARCHAR':str,'CHAR':str,'TEXT':str}
    for row in rows:
        for column in columns:
            spec=metadata[column];value=row[column]
            if value is None:
                need(spec.get('nullable',True),'ROW_NULLABILITY_MISMATCH');continue
            expected=families.get(spec['type']['family']);need(expected is not None and type(value) is expected,'MYSQL_ROW_TYPE_MISMATCH')
            if type(value) is Decimal:need(value.is_finite(),'MYSQL_ROW_DECIMAL_INVALID')
            if type(value) is datetime:need(value.tzinfo is None,'MYSQL_ROW_TIMEZONE_UNSUPPORTED')

@traced('SOURCE_PRESERVATION')
def source_match(baseline,current):g.preservation(baseline['data'],current['data'])
@traced('BACKUP_CAPACITY')
def capacity(raw):
    estimate=int(scalar(raw,'SELECT COALESCE(SUM(DATA_LENGTH+INDEX_LENGTH),0) FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s',(SOURCE,)))
    need(estimate>=0 and shutil.disk_usage(PARENT).free>=max(256*1024*1024,3*estimate+64*1024*1024),'BACKUP_STORAGE_CAPACITY_INSUFFICIENT')
def client_argv(executable,account,database,*,dump=False):
    target(database,account)
    need((executable,database)==(DUMP,SOURCE) if dump else (executable,database)==(MYSQL,SCRATCH),'NATIVE_CLIENT_TARGET_MISMATCH')
    args=[str(executable),'--no-defaults','--protocol=TCP','--host=127.0.0.1','--port=3306','--user='+account,'--password','--ssl-mode=VERIFY_IDENTITY','--ssl-ca='+str(tls.CA_PATH),'--tls-version=TLSv1.2,TLSv1.3','--default-character-set=utf8mb4']
    if dump:args+=['--single-transaction','--quick','--hex-blob','--order-by-primary','--set-gtid-purged=OFF','--no-tablespaces','--column-statistics=0','--triggers','--skip-routines','--skip-events','--skip-add-drop-table','--skip-add-locks','--skip-disable-keys','--skip-lock-tables',database]
    else:args+=['--binary-mode','--local-infile=0','--database='+database]
    return args
@traced('NATIVE_CLIENT_EXECUTION')
def checked_process(argv,*,stdin=None,stdout=None):
    need(sys.stdin.isatty(),'PRIVATE_NATIVE_PASSWORD_CONSOLE_REQUIRED')
    # No raw stderr is retained; errors are categorized from exit status only.
    # Native MySQL owns the hidden console prompt (must be operator-verified).
    print('NATIVE_MYSQL_PASSWORD: enter the approved account password at the native hidden prompt')
    environment={key:value for key,value in os.environ.items() if key.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP','PATH','SYSTEMDRIVE','PATHEXT','COMSPEC'}}
    if argv and argv[0]==str(DUMP):run_state()['native_dump_started']=True
    child=subprocess.Popen(argv,shell=False,stdin=stdin,stdout=stdout,stderr=subprocess.DEVNULL,close_fds=True,env=environment)
    primary=None
    try:need(child.wait(timeout=300)==0,'MYSQL_CLIENT_FAILED')
    except BaseException as error:primary=error;raise
    finally:
        try:
            if child.poll() is None:child.kill();child.wait(timeout=5)
        except BaseException:
            if primary is None:raise RuntimeError('NATIVE_PROCESS_CLEANUP_INCOMPLETE') from None
            primary.process_cleanup='INCOMPLETE'

def owned_fd(api,handle,*,read_only=False):
    import msvcrt
    duplicate=w.w.HANDLE();api.k.DuplicateHandle.argtypes=[w.w.HANDLE,w.w.HANDLE,w.w.HANDLE,ctypes.POINTER(w.w.HANDLE),w.w.DWORD,w.w.BOOL,w.w.DWORD];api.k.DuplicateHandle.restype=w.w.BOOL
    process=api.k.GetCurrentProcess();need(api.k.DuplicateHandle(process,handle.value,process,ctypes.byref(duplicate),0,False,2),'DUPLICATE_OUTPUT_FAILED')
    try:return msvcrt.open_osfhandle(duplicate.value,(os.O_RDONLY if read_only else os.O_RDWR)|os.O_BINARY)
    except BaseException:api.k.CloseHandle(duplicate);raise

@contextmanager
def private_input(path,approved_hash):
    """One immutable held input handle: deny concurrent writes/deletion."""
    api=w._Win32();sid=api.operator_sid();handles=[]
    need(path.parent.parent==PARENT and path.name=='viva.sql','PRIVATE_DUMP_PATH_REQUIRED')
    try:
        for ancestor in reversed((path.parent,*path.parent.parents)):
            handle=api.open(ancestor,directory=True,read_acl=True);handles.append(handle)
            api.facts(handle,ancestor,directory=True,owner=sid if ancestor in (PARENT,path.parent) else None)
        raw=api.k.CreateFileW(str(path),0x80020080,1,None,3,0x00200000,None)
        need(raw!=ctypes.c_void_p(-1).value,'EXCLUSIVE_INPUT_OPEN_FAILED')
        handle=w.Handle(api.k,raw);handles.append(handle);api.facts(handle,path,directory=False,owner=sid)
        with os.fdopen(owned_fd(api,handle,read_only=True),'rb',buffering=0) as stream:
            raw_bytes=stream.read(64*1024*1024+1)
            need(sha(raw_bytes)==approved_hash,'RESTORE_INPUT_HASH_MISMATCH');stream.seek(0)
            yield stream,raw_bytes
    finally:
        for handle in reversed(handles):handle.close()

@traced('PINNED_MIGRATION_STAGE')
def upgrade_one(raw,database,account,parent,stage):
    """Same versions, dedicated exact-connection Alembic env; no app engine."""
    from sqlalchemy import create_engine,event
    from sqlalchemy.engine import URL
    from sqlalchemy.pool import StaticPool
    from alembic import command
    from alembic.config import Config
    target(database,account);g.stage_guard(parent,stage);identity(raw,database,account)
    need(revision(raw)==parent,'PARENT_REVISION_MISMATCH')
    need(scalar(raw,'SELECT @@GLOBAL.log_bin')==1 and scalar(raw,'SELECT @@GLOBAL.log_bin_trust_function_creators')==1,'DBA_BINARY_LOGGING_RESOLUTION_REQUIRED')
    class Borrowed:
        def __getattr__(self,name):return getattr(raw,name)
        def cursor(self,cursor=None):
            from pymysql.cursors import Cursor
            return raw.cursor(Cursor if cursor is None else cursor)
        def close(self):pass  # Caller retains the sole real socket through postchecks.
    opened=False
    def creator():
        nonlocal opened
        need(not opened,'RECONNECT_REFUSED');opened=True;return Borrowed()
    raw.commit();engine=create_engine(URL.create('mysql+pymysql',host='127.0.0.1',port=3306,username=account,database=database),creator=creator,poolclass=StaticPool,pool_pre_ping=False,echo=False,hide_parameters=True)
    def sql_guard(conn,cursor,statement,parameters,context,executemany):
        sql=statement.strip()
        need(re.match(r'(?is)^(SELECT|SHOW|DESCRIBE|SET|CREATE|ALTER|INSERT|UPDATE|DELETE)\s',sql) is not None,'UNREVIEWED_MIGRATION_STATEMENT')
        need(not re.search(r'(?i)\bSET\s+(?:@@)?GLOBAL\b|\bsql_log_bin\b',sql),'GLOBAL_SETTING_CHANGE_REFUSED')
        need(not re.search(r'(?i)\b(USE|GRANT|REVOKE|TRUNCATE)\b|\b(?:CREATE|DROP|ALTER)\s+DATABASE\b',sql),'UNSAFE_MIGRATION_SQL')
        need(not re.match(r'(?is)^(UPDATE|DELETE|INSERT)\b',sql) or re.match(r'(?is)^(?:UPDATE|DELETE\s+FROM|INSERT\s+INTO)\s+`?alembic_version`?\b',sql),'HISTORICAL_DML_REFUSED')
        for name in ('lankapex_db','lankapex_test_db','lankapex_demo_db',SOURCE if database==SCRATCH else SCRATCH):need(not re.search(r'\b'+name+r'\b',sql,re.I),'OTHER_SCHEMA_REFERENCE')
    event.listen(engine,'before_cursor_execute',sql_guard)
    try:
        with engine.connect() as conn:
            # SQLAlchemy's PyMySQL on_connect issues SET NAMES without COLLATE;
            # restore the reviewed trigger creation context before any DDL.
            conn.exec_driver_sql('SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci');conn.commit()
            cfg=Config();cfg.set_main_option('script_location',str(ROOT/'backend/viva_pending_alembic'));cfg.set_main_option('path_separator','os');cfg.set_main_option('version_locations',str(ROOT/'backend/alembic/versions'))
            cfg.attributes.update(connection=conn,viva_target=database,viva_account=account,viva_parent=parent,viva_stage=stage,viva_identity=identity)
            command.upgrade(cfg,stage)
    except BaseException as error:
        try:
            error.partial_state=dict(revision=revision(raw),tables=[r['TABLE_NAME'] for r in Inspector(raw,database).read('tables')],
                triggers=[r['TRIGGER_NAME'] for r in Inspector(raw,database).read('triggers')])
        except BaseException:error.partial_state={'status':'UNAVAILABLE_PRESERVE_STATE'}
        raise
    finally:
        # Do not dispose/close the caller-owned socket before postverification.
        event.remove(engine,'before_cursor_execute',sql_guard)
        engine.dispose()

@traced('DUMP_VALIDATION')
def validate_backup_sql(raw,baseline):
    """Current zero-program dump only. Reject cross-schema/client directives."""
    need(raw and len(raw)<=64*1024*1024 and re.search(rb'(?m)^-- Dump completed on [^\r\n]+\s*\Z',raw),'INCOMPLETE_DUMP')
    parser=load('viva_dump_lexer','backend/scripts/checkpoint_dump_inspection.py')
    tokens=parser.tokens(raw.decode('utf-8'))
    # Inspect SQL-aware tokens, not literals containing financial/customer data.
    words=[v.upper() for kind,v in tokens if kind=='atom']
    need(not {'DATABASE','USE','TRIGGER','PROCEDURE','FUNCTION','EVENT','GRANT','REVOKE','OUTFILE','DUMPFILE','SOURCE'}&set(words),'UNEXPECTED_DUMP_PROGRAM_OR_TARGET')
    need(('punct','.') not in tokens,'QUALIFIED_DUMP_TARGET_REFUSED')
    statements=[];part=[]
    for token in tokens:
        if token==('punct',';'):
            need(part,'EMPTY_DUMP_STATEMENT');statements.append(part);part=[]
        else:part.append(token)
    need(not part,'TRUNCATED_DUMP_STATEMENT')
    names=g.recovery_contract().tables_at(CHAIN[0]);created=set();rows={name:[] for name in names}
    for statement in statements:
        prefix=[(kind,value.upper() if kind=='atom' else value) for kind,value in statement[:2]]
        if prefix[0]==('atom','SET'):
            need(parser.normalized(statement) in parser.ALLOWED_SETS,'UNREVIEWED_DUMP_SETTING');continue
        if prefix==[('atom','CREATE'),('atom','TABLE')]:
            need(len(statement)>3 and statement[2][0]=='identifier','INVALID_CREATE_TABLE')
            name=statement[2][1];need(name in names and name not in created,'DUMP_TABLE_INVENTORY_MISMATCH');created.add(name);continue
        need(prefix==[('atom','INSERT'),('atom','INTO')] and len(statement)>5 and statement[2][0]=='identifier','UNSUPPORTED_DUMP_STATEMENT')
        name=statement[2][1];need(name in created,'INSERT_TARGET_MISMATCH')
        columns=['version_num'] if name=='alembic_version' else baseline['data'][name]['columns']
        i=3
        if statement[i]==('punct','('):
            i+=1;specified=[]
            while True:
                need(statement[i][0]=='identifier','INVALID_INSERT_COLUMNS');specified.append(statement[i][1]);i+=1
                if statement[i]==('punct',')'):i+=1;break
                need(statement[i]==('punct',','),'INVALID_INSERT_COLUMNS');i+=1
            need(specified==columns,'DUMP_COLUMN_ORDER_MISMATCH')
        need(statement[i]==('atom','VALUES'),'UNSUPPORTED_INSERT');i+=1
        while i<len(statement):
            need(statement[i]==('punct','('),'INVALID_INSERT');i+=1;record={}
            for index,column in enumerate(columns):
                record[column]=parser.literal(statement[i],baseline['schema']['tables'][name]['metadata']['columns'][column]);i+=1
                if index+1<len(columns):need(statement[i]==('punct',','),'INVALID_INSERT');i+=1
            need(statement[i]==('punct',')'),'INVALID_INSERT');i+=1;rows[name].append(record)
            need(len(rows[name])<=d.a.MAX_ROWS,'DUMP_ROW_LIMIT_EXCEEDED')
            if i<len(statement):need(statement[i]==('punct',','),'INVALID_INSERT');i+=1;need(i<len(statement),'TRAILING_INSERT_COMMA')
    need(created==names,'INCOMPLETE_DUMP_TABLE_INVENTORY')
    for name in names-{'alembic_version'}:
        expected=baseline['data'][name];found=d.a.fingerprint(rows[name],expected['columns'])
        need(found=={key:expected[key] for key in ('row_count','content_sha256')},'DUMP_CONTENT_MISMATCH')
    need(rows['alembic_version']==[{'version_num':CHAIN[0]}],'DUMP_REVISION_MISMATCH')
    return raw

def inspect_source(argv):
    """Operator-only live READ-ONLY diagnostic; never writes checkpoint artifacts."""
    parser=argparse.ArgumentParser(description='Read-only SOURCE_BEFORE diagnosis; no backup or evidence creation')
    parser.add_argument('--read-only',action='store_true',required=True)
    parser.add_argument('--confirm-source',required=True);parser.add_argument('--freeze',required=True);parser.add_argument('--ca-sha256',required=True)
    args=parser.parse_args(argv);need(args.confirm_source==SOURCE and args.freeze=='FREEZE_MAINTAINED','EXACT_SOURCE_AND_FREEZE_REQUIRED')
    need(file_sha(tls.CA_PATH)==args.ca_sha256.upper(),'APPROVED_CA_HASH_MISMATCH');g.graph()
    need(sys.stdin.isatty(),'PRIVATE_CONSOLE_REQUIRED')
    dba_user=input('Existing DBA username (not password): ');dba_secret=password('Existing DBA password');source_secret=password('Existing VIVA migrator password')
    run_state()['stage']='READ_ONLY_SOURCE'
    with connect(SOURCE,g.MIGRATOR.split('@')[0],source_secret) as source:
        gate_for(dba_user,dba_secret,source)
        baseline=snapshot(source,SOURCE,g.MIGRATOR.split('@')[0],CHAIN[0])
        encoded(baseline)  # Exercise the same serialization, but persist nothing.
        gate_for(dba_user,dba_secret,source)
    print('SOURCE_BEFORE_READ_ONLY=PASS; TABLES=35; REVISION='+CHAIN[0]+'; BASELINE_CAPTURE=PASS; SERIALIZATION=PASS; NATIVE_DUMP_STARTED=no; FILES_CREATED=0')

def _main(argv=None):
    arguments=list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0]=='inspect-windows':return inspect_windows(arguments[1:])
    if arguments and arguments[0]=='inspect-source':return inspect_source(arguments[1:])
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=tuple(TOKENS));parser.add_argument('--execute',action='store_true');parser.add_argument('--authorize',required=True);parser.add_argument('--confirm-target',required=True);parser.add_argument('--freeze',required=True)
    parser.add_argument('--evidence',type=Path,required=True);parser.add_argument('--manifest',type=Path);parser.add_argument('--manifest-sha256');parser.add_argument('--rehearsal',type=Path);parser.add_argument('--rehearsal-sha256');parser.add_argument('--mysql-sha256',required=True);parser.add_argument('--mysqldump-sha256',required=True);parser.add_argument('--ca-sha256',required=True)
    args=parser.parse_args(arguments);authorization(args);g.graph();need(file_sha(MYSQL)==args.mysql_sha256.upper() and file_sha(DUMP)==args.mysqldump_sha256.upper(),'APPROVED_CLIENT_BINARY_MISMATCH')
    need(file_sha(tls.CA_PATH)==args.ca_sha256.upper(),'APPROVED_CA_HASH_MISMATCH')
    need(sys.stdin.isatty(),'PRIVATE_CONSOLE_REQUIRED');dba_user=input('Existing DBA username (not password): ');dba_secret=password('Existing DBA password')
    source_account=g.MIGRATOR.split('@')[0];source_secret=password('Existing VIVA migrator password')
    bundle=baseline=None
    if args.mode!='backup':
        need(args.manifest is not None and args.manifest_sha256,'APPROVED_CURRENT_BACKUP_REQUIRED');bundle,baseline=read_bundle(args.manifest,args.manifest_sha256)
        need(bundle['ca_sha256']==args.ca_sha256.upper() and bundle['mysql_sha256']==args.mysql_sha256.upper()
             and bundle['mysqldump_sha256']==args.mysqldump_sha256.upper(),'BACKUP_CLIENT_OR_CA_CHANGED')
    stage='RESERVE';run_state()['stage']=stage;pending_result=None
    with PrivateEvidence(args.evidence) as evidence:
        try:
            with connect(SOURCE,source_account,source_secret) as source:
                started=revision(source);need(started==CHAIN[0],'SOURCE_NOT_CURRENT_BASELINE')
                gate=gate_for(dba_user,dba_secret,source);stage='SOURCE_BEFORE';run_state()['stage']=stage
                before=snapshot(source,SOURCE,source_account,CHAIN[0]);evidence.write('source-before.json',before)
                if baseline is not None:source_match(baseline,before)
                if args.mode=='backup':
                    capacity(source)
                    need(scalar(source,'SELECT @@GLOBAL.log_bin')==1 and scalar(source,'SELECT @@GLOBAL.log_bin_trust_function_creators')==0,'EXPECTED_PREWINDOW_BINARY_LOGGING_STATE_REQUIRED')
                    stage='DUMP';run_state()['stage']=stage;evidence.write('baseline.json',before)
                    gate_for(dba_user,dba_secret,source)
                    with evidence.open_new('viva.sql') as handle:
                        fd=owned_fd(evidence.api,handle)
                        try:
                            with os.fdopen(fd,'r+b',buffering=0) as output:
                                checked_process(client_argv(DUMP,source_account,SOURCE,dump=True),stdout=output)
                                need(evidence.api.k.FlushFileBuffers(handle.value),'OUTPUT_FLUSH_FAILED');output.seek(0);raw=validate_backup_sql(output.read(64*1024*1024+1),before)
                        finally:evidence.api.facts(handle,args.evidence/'viva.sql',directory=False,owner=evidence.sid)
                    stage='SOURCE_AFTER';run_state()['stage']=stage
                    after=snapshot(source,SOURCE,source_account,CHAIN[0]);source_match(before,after);need(before['schema']==after['schema'],'SOURCE_SCHEMA_CHANGED')
                    need(file_sha(args.evidence/'viva.sql')==sha(raw),'DUMP_CHECKSUM_READBACK_MISMATCH')
                    evidence.write('source-after.json',after)
                    manifest=dict(format='viva-current-backup-v1',source=SOURCE,uuid=g.UUID,revision=CHAIN[0],dump_sha256=sha(raw),baseline_sha256=sha(encoded(before)),provenance=provenance(),status='BACKUP_ONLY_RESTORE_NOT_VERIFIED',gate=gate,
                        ca_sha256=args.ca_sha256.upper(),mysql_sha256=args.mysql_sha256.upper(),mysqldump_sha256=args.mysqldump_sha256.upper(),certificate_sha256=tls.CERT_SHA256,binary_logging_before=dict(enabled=True,trust_function_creators=0))
                    evidence.write('manifest.json',manifest);print('BACKUP_MANIFEST_SHA256='+sha(encoded(manifest)));print('BACKUP_SHA256='+sha(raw))
                else:
                    scratch_secret=password('Existing rehearsal-only account password')
                    with connect(SCRATCH,SCRATCH_USER,scratch_secret) as scratch:
                        gate_for(dba_user,dba_secret,source,scratch)
                        if args.mode=='restore':
                            stage='RESTORE';run_state()['stage']=stage;need(not Inspector(scratch,SCRATCH).read('tables') and not Inspector(scratch,SCRATCH).read('triggers') and not Inspector(scratch,SCRATCH).read('routines') and not Inspector(scratch,SCRATCH).read('events'),'SCRATCH_NOT_EMPTY')
                            with private_input(args.manifest.parent/'viva.sql',bundle['dump_sha256']) as (stream,raw):
                                validate_backup_sql(raw,baseline);gate_for(dba_user,dba_secret,source,scratch)
                                checked_process(client_argv(MYSQL,SCRATCH_USER,SCRATCH),stdin=stream,stdout=subprocess.DEVNULL)
                            restored=snapshot(scratch,SCRATCH,SCRATCH_USER,CHAIN[0]);source_match(baseline,restored)
                            need({k:v['metadata'] for k,v in baseline['schema']['tables'].items()}=={k:v['metadata'] for k,v in restored['schema']['tables'].items()},'RESTORED_SCHEMA_MISMATCH')
                            evidence.write('restore-verified.json',dict(status='RESTORE_VERIFIED',manifest_sha256=args.manifest_sha256,baseline_sha256=bundle['baseline_sha256'],snapshot=restored))
                        else:
                            if args.mode=='migrate':
                                need(args.rehearsal is not None and args.rehearsal_sha256,'VERIFIED_REHEARSAL_REQUIRED')
                                data=private_read(args.rehearsal);need(sha(data)==args.rehearsal_sha256.upper(),'REHEARSAL_HASH_MISMATCH');report=json.loads(data)
                                need(report['status']=='REHEARSAL_PASS' and report['manifest_sha256']==args.manifest_sha256 and report['provenance']==provenance(),'REHEARSAL_EVIDENCE_MISMATCH')
                                verified=snapshot(scratch,SCRATCH,SCRATCH_USER,CHAIN[-1],{k:v['columns'] for k,v in baseline['data'].items()});source_match(baseline,verified)
                            selected=source if args.mode=='migrate' else scratch;database=SOURCE if args.mode=='migrate' else SCRATCH;account=source_account if args.mode=='migrate' else SCRATCH_USER
                            current=snapshot(selected,database,account,CHAIN[0]);source_match(baseline,current)
                            for index,(parent,child) in enumerate(zip(CHAIN,CHAIN[1:])):
                                stage=child;run_state()['stage']=stage;need(bundle['provenance']==provenance(),'MIGRATION_SOURCES_CHANGED')
                                gate_for(dba_user,dba_secret,source,scratch);evidence.write('stage-'+str(index)+'-attempt.json',dict(parent=parent,revision=child,database=database))
                                upgrade_one(selected,database,account,parent,child)
                                post=snapshot(selected,database,account,child,{k:v['columns'] for k,v in baseline['data'].items()});source_match(baseline,post);evidence.write('stage-'+str(index)+'-verified.json',post)
                            pending_result=dict(status='LIVE_MIGRATION_PASS' if args.mode=='migrate' else 'REHEARSAL_PASS',database=database,manifest_sha256=args.manifest_sha256,provenance=provenance(),final_revision=CHAIN[-1],tables=45,triggers=18)
                    stage='SOURCE_AFTER';run_state()['stage']=stage
                    expected=CHAIN[-1] if args.mode=='migrate' else CHAIN[0]
                    final=snapshot(source,SOURCE,source_account,expected,{k:v['columns'] for k,v in baseline['data'].items()});source_match(baseline,final);evidence.write('source-after.json',final)
                gate_for(dba_user,dba_secret,source)
            evidence.write('complete.json',dict(status='PASS',mode=args.mode))
            if pending_result is not None:
                evidence.write('result.json',pending_result);print('RESULT_SHA256='+sha(encoded(pending_result)))
            print('VIVA_OPERATION=PASS; MODE='+args.mode)
        except BaseException as error:
            try:
                details=failure_details(error)
                if details['stage']=='UNCLASSIFIED':details['stage']=stage
                evidence.write('failure.json',dict(status='STOP_PRESERVE_NO_RETRY',error_class=type(error).__name__,diagnostic_code=diagnostic(error),partial_state=getattr(error,'partial_state',None),**details,**windows_details(error)))
            except BaseException:print('FAILURE_EVIDENCE=INCOMPLETE')
            raise

def main(argv=None):
    token=_RUN.set(dict(stage='PRECHECK',database_connection_started=False,baseline_capture_started=False,native_dump_started=False))
    try:
        with phase('EXECUTION'):return _main(argv)
    finally:_RUN.reset(token)
if __name__=='__main__':
    try:main()
    except BaseException as error:
        details=''.join('; '+key.upper()+'='+str(value) for key,value in {**failure_details(error),**windows_details(error)}.items())
        print('VIVA_OPERATION=STOP; ERROR_CLASS='+type(error).__name__+'; DIAGNOSTIC_CODE='+diagnostic(error)+details+'; PRESERVE_NO_RETRY');raise SystemExit(1)

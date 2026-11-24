"""Prepared Windows/native backup boundary. NO process, DB or directory execution.

Filesystem reservation implementation lives in current_checkpoint_plan.py.
Production activation requires a separate reviewed release and operator approval.
"""
from dataclasses import dataclass
import hashlib
import importlib.util
from pathlib import Path
import re
import sys

if '_lankapex_current_checkpoint_plan' in sys.modules:
    p=sys.modules['_lankapex_current_checkpoint_plan']
else:
    spec=importlib.util.spec_from_file_location('_lankapex_current_checkpoint_plan',Path(__file__).with_name('current_checkpoint_plan.py'))
    p=importlib.util.module_from_spec(spec);sys.modules[spec.name]=p;spec.loader.exec_module(p)

@dataclass(frozen=True)
class WindowsDirectoryRecipe:
    attempt_id:str
    path:str
    owner_sid:str
    sddl:str
    # Security descriptor must be supplied at CreateDirectoryW, not applied later.
    api:str='CreateDirectoryW_WITH_SECURITY_ATTRIBUTES'
    required_checks:tuple=('approved_parent_handle','all_ancestors_not_reparse',
        'target_absent','exclusive_create','protected_exact_owner_SYSTEM_acl',
        'no_inherited_or_extra_aces','empty_directory','held_nondelete_shared_handles',
        'output_CREATE_NEW_no_reparse','final_file_owner_and_acl')

def directory_recipe(attempt_id,path,approved_path,observation,operator_sid):
    capability=p.destination_policy(path,approved_path,observation,operator_sid,attempt_id=attempt_id)
    sddl='O:'+operator_sid+'G:'+operator_sid+'D:P(A;OICI;FA;;;'+operator_sid+')(A;OICI;FA;;;SY)'
    return WindowsDirectoryRecipe(attempt_id,path,operator_sid,sddl),capability

def validate_windows_observation(recipe,observed):
    p.need(type(recipe) is WindowsDirectoryRecipe,'DIRECTORY_RECIPE_REQUIRED')
    p.need(observed.get('attempt_id')==recipe.attempt_id and observed.get('path')==recipe.path
           and observed.get('owner_sid')==recipe.owner_sid and observed.get('sddl')==recipe.sddl,'WINDOWS_DIRECTORY_IDENTITY_MISMATCH')
    p.need(all(observed.get(check) is True for check in recipe.required_checks),'WINDOWS_HANDLE_ACL_OR_REPARSE_UNVERIFIED')

@dataclass(frozen=True)
class NativeDumpRecipe:
    attempt_id:str
    argv:tuple
    argv_sha256:str
    shell:bool=False
    credential_mode:str='NATIVE_PRIVATE_CONSOLE_PASSWORD_PROMPT'
    stdin_mode:str='INHERIT_PRIVATE_CONSOLE'
    error_mode:str='CAPTURE_PRIVATELY_REDACT_PUBLIC_STATUS'
    timeout_seconds:int=300

_CONFIGURATIONS={};_RECIPES={}
class ApprovedDumpConfiguration:
    __slots__=()
    def __new__(cls):raise p.Stop('APPROVED_CONFIGURATION_ISSUER_REQUIRED')

def bind_approved_configuration(raw,approved_sha256,destination):
    """Bind externally approved bytes; hash equality is NOT independent DBA trust.

    Fictional approvals are used in tests. Real approval issuance stays blocked.
    """
    import json
    p.need(type(raw) is bytes and len(raw)<=65536 and p.sha(raw)==approved_sha256,'APPROVED_CONFIGURATION_BYTES_MISMATCH')
    def unique(pairs):
        value={}
        for k,v in pairs:
            p.need(k not in value,'DUPLICATE_CONFIGURATION_FIELD');value[k]=v
        return value
    config=json.loads(raw,object_pairs_hook=unique)
    p.need(set(config)=={'endpoint','port','server_uuid','schema','account','ca_path','ca_sha256','destination','attempt_id'},'CONFIGURATION_FIELDS_MISMATCH')
    p.need(config['schema']==p.SOURCE and type(config['server_uuid']) is str and bool(config['server_uuid']),'CONFIGURATION_SOURCE_MISMATCH')
    p.need(type(destination) is p.ValidatedDestination and id(destination) in p._DESTINATIONS,'VALIDATED_DESTINATION_REQUIRED')
    original,path,attempt=p._DESTINATIONS[id(destination)]
    p.need(original is destination and path==config['destination'] and attempt==config['attempt_id'],'CONFIGURATION_DESTINATION_MISMATCH')
    _expected_argv(config,destination)
    value=object.__new__(ApprovedDumpConfiguration)
    _CONFIGURATIONS[id(value)]=(value,bytes(raw),approved_sha256,destination)
    return value

def _configuration(value):
    import json
    p.need(type(value) is ApprovedDumpConfiguration and id(value) in _CONFIGURATIONS,'ISSUED_CONFIGURATION_REQUIRED')
    original,raw,digest,destination=_CONFIGURATIONS[id(value)]
    p.need(original is value and p.sha(raw)==digest,'CONFIGURATION_IDENTITY_MISMATCH')
    return json.loads(raw),destination,digest

def _expected_argv(config,destination):
    return p.dump_arguments(endpoint=config['endpoint'],approved_endpoint=config['endpoint'],port=config['port'],approved_port=config['port'],
        ca_path=config['ca_path'],ca_sha256=config['ca_sha256'],approved_ca_sha256=config['ca_sha256'],user=config['account'],
        dump=str(p.PureWindowsPath(config['destination'])/'viva.sql'),destination=destination,attempt_id=config['attempt_id'])

def native_recipe(*,configuration=None):
    config,destination,digest=_configuration(configuration)
    argv=_expected_argv(config,destination)
    value=NativeDumpRecipe(config['attempt_id'],tuple(argv),p.sha(p.canonical(argv)))
    _RECIPES[id(value)]=(value,configuration,tuple(value.__dict__.items()))
    return value

def validate_native_recipe(recipe):
    p.need(type(recipe) is NativeDumpRecipe and id(recipe) in _RECIPES,'ISSUED_NATIVE_RECIPE_REQUIRED')
    original,configuration,fields=_RECIPES[id(recipe)]
    p.need(original is recipe and tuple(recipe.__dict__.items())==fields,'NATIVE_RECIPE_MUTATED')
    config,destination,digest=_configuration(configuration)
    expected=tuple(_expected_argv(config,destination))
    p.need(recipe.argv==expected and recipe.argv_sha256==p.sha(p.canonical(list(expected)))
           and recipe.attempt_id==config['attempt_id'] and recipe.shell is False,'NATIVE_DUMP_BINDING_MISMATCH')
    return config,destination,digest

def prerequisite_contract(approval,observed,now):
    """Validate offline DTOs only: does NOT establish independent DBA trust."""
    p.need(approval.get('source')==p.SOURCE and approval.get('revision')==p.REVISION
           and approval.get('endpoint')=='127.0.0.1' and approval.get('port')==3306,'SOURCE_APPROVAL_MISMATCH')
    for key in ('server_uuid','source','revision','endpoint','port','backup_account','ca_sha256','attempt_id'):
        p.need(bool(approval.get(key)) and observed.get(key)==approval[key],'OBSERVED_APPROVAL_MISMATCH')
    p.attempt_guard(approval['attempt_id'])
    p.need(type(now) in (float,int) and observed['observed_at']<=now<observed['expires_at']
           and 0<observed['expires_at']-observed['observed_at']<=300,'STALE_EXECUTION_GATE')
    for key in ('tls_chain_verified','san_only_verified','backup_grants_verified',
                'writer_freeze','ddl_freeze','no_unexplained_writers','capacity_verified',
                'private_console','complete_inventory_verified','innoDB_only'):
        p.need(observed.get(key) is True,'EXECUTION_PREREQUISITE_UNVERIFIED')

def reserve_prelaunch(store,directory,native,approval,observed,now,*,before_capture=None,inventory=None,expected_post_capture_id=None):
    """Issue a reserved-job capability; no native operation is activated."""
    p.need(type(store) in (p.FilesystemConsumptionStore,p.OfflineConsumptionStore) and type(directory) is WindowsDirectoryRecipe,'EXECUTION_RESERVATION_BOUNDARY_REQUIRED')
    prerequisite_contract(approval,observed,now)
    config,destination,configuration_hash=validate_native_recipe(native)
    p.need(directory.attempt_id==native.attempt_id==approval['attempt_id'],'EXECUTION_ATTEMPT_MISMATCH')
    p.need(directory.path==config['destination'] and directory.sddl=='O:'+directory.owner_sid+'G:'+directory.owner_sid+'D:P(A;OICI;FA;;;'+directory.owner_sid+')(A;OICI;FA;;;SY)','EXECUTION_DIRECTORY_MISMATCH')
    p.need(config['account']==approval['backup_account'] and config['server_uuid']==approval['server_uuid']
           and config['ca_sha256']==approval['ca_sha256'] and config['endpoint']==approval['endpoint']
           and config['port']==approval['port'],'EXECUTION_CONFIGURATION_APPROVAL_MISMATCH')
    pre=p.capture_record(before_capture,inventory,approval['server_uuid'],now)
    p.need(pre['attempt_id']==native.attempt_id,'PRELAUNCH_CAPTURE_ATTEMPT_MISMATCH')
    p.need(type(expected_post_capture_id) is str and re.fullmatch('[A-Za-z0-9_-]{8,100}',expected_post_capture_id)
           and expected_post_capture_id!=pre['snapshot']['owner'],'EXPECTED_POST_CAPTURE_ID_REQUIRED')
    job=dict(attempt_id=native.attempt_id,directory=directory.path,sddl=directory.sddl,
        dump_path=str(p.PureWindowsPath(directory.path)/'viva.sql'),manifest_path=str(p.PureWindowsPath(directory.path)/'manifest.json'),
        native_sha256=native.argv_sha256,configuration_sha256=configuration_hash,server_uuid=config['server_uuid'],
        before_capture_sha256=p.sha(p.canonical(pre)),inventory_sha256=p.sha(p.canonical(inventory)),
        expected_post_capture_id=expected_post_capture_id,approval_sha256=p.sha(p.canonical(approval)))
    raw=p.canonical(job)
    store.reserve_execution(native.attempt_id,p.sha(raw))
    return p._issue_reserved_job(store,raw,destination,before_capture)

class DisabledBackupBoundary:
    def verify_real_dba(self,*args,**kwargs):raise p.Stop('REAL_DBA_TRUST_NOT_REVIEWED')
    def provision_private_directory(self,*args,**kwargs):raise p.Stop('BACKUP_EXECUTION_NOT_APPROVED')
    def connect(self,*args,**kwargs):raise p.Stop('BACKUP_EXECUTION_NOT_APPROVED')
    def run_mysqldump(self,*args,**kwargs):raise p.Stop('BACKUP_EXECUTION_NOT_APPROVED')
    def execute(self,*args,**kwargs):raise p.Stop('BACKUP_EXECUTION_NOT_APPROVED')

if __name__=='__main__':
    print('CHECKPOINT=PREPARED_ONLY; BACKUP_EXECUTION_DISABLED')
    raise SystemExit(2)

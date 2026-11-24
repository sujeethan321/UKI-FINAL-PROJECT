"""Current-baseline VIVA migration preparation. No database access on import/CLI.

The operator plan is not execution approval. Historical runners are unchanged.
Actual stage execution stays blocked pending independent review and live gates.
"""
import argparse
import ast
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE='lankapex_viva_db'
SCRATCH='lankapex_migration_verify_viva20261124'
UUID='7bc6e90d-aced-11f1-be0b-10e7c6704500'
CHAIN=('ae2b7c5f1d48','bf38d2a90176','c04d9e7a6201','d15a8c902e64')
COUNTS=((35,0),(40,10),(44,16),(45,18))
MIGRATOR='lankapex_viva_migrator@127.0.0.1'
SCRATCH_ACCOUNT='lankapex_viva_rehearsal@127.0.0.1'
RIGHTS={'SELECT','INSERT','UPDATE','DELETE','CREATE','ALTER','INDEX','REFERENCES','TRIGGER'}

def require(ok,code):
    if not ok:raise RuntimeError(code)

def recovery_contract():
    spec=importlib.util.spec_from_file_location('viva_recovery_contract',ROOT/'backend/scripts/security_recovery_plan.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def graph():
    found={}
    for path in (ROOT/'backend/alembic/versions').glob('*.py'):
        values={}
        for node in ast.parse(path.read_text(encoding='utf-8')).body:
            targets=node.targets if isinstance(node,ast.Assign) else [node.target] if isinstance(node,ast.AnnAssign) else []
            for target in targets:
                if isinstance(target,ast.Name) and target.id in ('revision','down_revision'):
                    values[target.id]=ast.literal_eval(node.value)
        if 'revision' in values:
            require(values['revision'] not in found,'DUPLICATE_REVISION')
            found[values['revision']]=values['down_revision']
    require(len(found)==22 and set(found)-set(found.values())=={CHAIN[-1]},'GRAPH_CHANGED')
    for parent,child in zip(CHAIN,CHAIN[1:]):require(found[child]==parent,'PENDING_CHAIN_CHANGED')
    seen=set();revision=CHAIN[-1]
    while revision is not None:
        require(revision in found and revision not in seen,'GRAPH_BROKEN')
        seen.add(revision);revision=found[revision]
    require(len(seen)==22,'GRAPH_BRANCH_OR_DISCONNECTED')
    return found

def target_guard(database,account):
    require((database,account) in ((SOURCE,MIGRATOR),(SCRATCH,SCRATCH_ACCOUNT)),'EXACT_TARGET_ACCOUNT_REQUIRED')

def stage_guard(before,after):
    require((before,after) in tuple(zip(CHAIN,CHAIN[1:])),'ONE_PINNED_STAGE_REQUIRED')

def observed_guard(value,*,database,account,revision,now):
    target_guard(database,account)
    require((value.get('host'),value.get('port'),value.get('server_uuid'),value.get('database'),value.get('account'),value.get('revision'))
            ==('127.0.0.1',3306,UUID,database,account,revision),'OBSERVED_IDENTITY_MISMATCH')
    require(value.get('version')=='8.0.46' and value.get('tls_verified') is True,'SERVER_TLS_UNVERIFIED')
    require(value.get('roles')=='NONE' and value.get('mandatory_roles')=='' and set(value.get('grants',()))==RIGHTS
            and value.get('grant_scope')==database and value.get('grant_option') is False,'SCOPED_GRANTS_REQUIRED')
    require(value.get('writer_freeze') is True and value.get('ddl_freeze') is True
            and value['observed_at']<=now<value['expires_at'] and 0<value['expires_at']-value['observed_at']<=300,'FRESH_DBA_FREEZE_REQUIRED')
    require(value.get('log_bin') is True and value.get('log_bin_trust_function_creators')==1,'DBA_BINARY_LOGGING_RESOLUTION_REQUIRED')
    contract=recovery_contract()
    require(set(value.get('tables',()))==contract.tables_at(revision)
            and value.get('triggers')==contract.trigger_contract(revision),'SCHEMA_OR_TRIGGER_INVENTORY_CHANGED')

def preservation(before,after):
    """Full typed hashes supplied by approved capture, original projections only.

    No timestamps, counts alone or newly added column values can replace hashes.
    Input dictionaries are NOT a trusted runtime authorization mechanism.
    """
    import re
    expected=recovery_contract().tables_at(CHAIN[0])-{'alembic_version'}
    require(set(before)==set(after)==expected,'INCOMPLETE_ORIGINAL_DATA_CAPTURE')
    for name in expected:
        left=before[name];right=after[name]
        require(left==right and set(left)=={'columns','row_count','content_sha256'}
                and type(left['row_count']) is int and left['row_count']>=0
                and type(left['columns']) is list and len(left['columns'])>0
                and len(set(left['columns']))==len(left['columns'])
                and re.fullmatch('[A-F0-9]{64}',left['content_sha256']),'ORIGINAL_DATA_CHANGED')

def execute_stage(*args,**kwargs):
    raise RuntimeError('LIVE_STAGE_RELEASE_AND_RECOVERY_EVIDENCE_NOT_APPROVED')

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',action='store_true',required=True)
    parser.add_argument('--database',choices=(SOURCE,SCRATCH),required=True)
    args=parser.parse_args(argv);graph();contract=recovery_contract()
    for revision,count in zip(CHAIN,COUNTS):
        require((len(contract.tables_at(revision)),len(contract.trigger_contract(revision)))==count,'STAGE_INVENTORY_CHANGED')
    print(json.dumps(dict(status='PREPARED_NOT_EXECUTED',database=args.database,server_uuid=UUID,
        stages=[dict(parent=a,revision=b,tables=COUNTS[i+1][0],triggers=COUNTS[i+1][1]) for i,(a,b) in enumerate(zip(CHAIN,CHAIN[1:]))],execution_enabled=False)))
if __name__=='__main__':
    try:main()
    except BaseException as error:
        print('VIVA_PREPARATION=STOP; ERROR_CLASS='+type(error).__name__+'; NO_RETRY');raise SystemExit(1)

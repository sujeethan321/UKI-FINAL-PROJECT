"""MR-02 offline contracts and injectable orchestration, never a live DB client.

The CLI intentionally has no MySQL/Alembic execution adapter. Passing --execute
cannot load plugins, environment URLs or application settings. The future adapter
requires separate source review and authorization; mocked orchestration is tested.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
TARGET='lankapex_mr02_rehearsal'
ACCOUNT=TARGET+'@127.0.0.1'
RESTORE_TARGET='lankapex_mr02_recovery'
RESTORE_ACCOUNT=RESTORE_TARGET+'@127.0.0.1'
SOURCE='lankapex_viva_db'
CHAIN=('9d1a6f4e0c37','ae2b7c5f1d48','bf38d2a90176','c04d9e7a6201','d15a8c902e64')
COUNTS=(33,35,40,44,45)
TOKEN='MR02_ONE_ISOLATED_UPGRADE'
SCHEMA_FIELDS={'columns','primary_key','foreign_keys','unique_constraints','checks','indexes','options','ddl_sha256'}
FEATURES=('driver_finance','support','address_book','address_checkout','ai')
_spec=importlib.util.spec_from_file_location('mr02_recovery_contract',ROOT/'backend/scripts/security_recovery_plan.py')
recovery=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(recovery)
if '_lankapex_mr05_evidence' not in sys.modules:
    _evidence_spec=importlib.util.spec_from_file_location('_lankapex_mr05_evidence',ROOT/'backend/scripts/mr05_evidence.py')
    _evidence_module=importlib.util.module_from_spec(_evidence_spec)
    sys.modules[_evidence_spec.name]=_evidence_module;_evidence_spec.loader.exec_module(_evidence_module)
evidence_contract=sys.modules['_lankapex_mr05_evidence']

class GuardFailure(RuntimeError):
    def __init__(self,code):super().__init__(code);self.code=code

def require(value,code):
    if not value:raise GuardFailure(code)

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest().upper()

def hexhash(value):return isinstance(value,str) and re.fullmatch('[A-Fa-f0-9]{64}',value) is not None

def file_hash(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest().upper()

def target_guard(database,account):
    require(database==TARGET,'UNAPPROVED_DATABASE')
    require(account==ACCOUNT,'UNAPPROVED_ACCOUNT')

def names_at(revision):
    require(revision in CHAIN,'UNAPPROVED_REVISION')
    if revision==CHAIN[0]:return recovery.tables_at(CHAIN[1])-{'driver_verification_documents','driver_document_audits'}
    return recovery.tables_at(revision)

def trigger_specs(revision):return {} if revision==CHAIN[0] else recovery.trigger_contract(revision)

def source_provenance():
    """AST and bytes only: never import a migration or application settings."""
    graph={};files={}
    for path in sorted((ROOT/'backend/alembic/versions').glob('*.py')):
        values={}
        for node in ast.parse(path.read_text(encoding='utf-8')).body:
            if isinstance(node,(ast.Assign,ast.AnnAssign)):
                for target in (node.targets if isinstance(node,ast.Assign) else [node.target]):
                    if isinstance(target,ast.Name) and target.id in ('revision','down_revision','depends_on','branch_labels'):
                        values[target.id]=ast.literal_eval(node.value)
        if 'revision' in values:
            revision=values['revision'];require(revision not in graph,'DUPLICATE_REVISION')
            require(values.get('depends_on') is None and values.get('branch_labels') is None,'UNREVIEWED_DEPENDENCY')
            graph[revision]=values['down_revision'];files[path.relative_to(ROOT).as_posix()]=file_hash(path)
    require(len(graph)==22 and set(graph)-{v for v in graph.values() if v}=={CHAIN[-1]},'MIGRATION_GRAPH_DRIFT')
    visited=set();revision=CHAIN[-1]
    while revision is not None:
        require(revision in graph and revision not in visited,'MIGRATION_GRAPH_DRIFT')
        visited.add(revision);revision=graph[revision]
    require(len(visited)==22,'MIGRATION_GRAPH_DRIFT')
    for previous,current in zip(CHAIN,CHAIN[1:]):require(graph[current]==previous,'REVISION_SEQUENCE_DRIFT')
    for name in ('backend/scripts/mr02_rehearsal.py','backend/scripts/security_recovery_plan.py','backend/scripts/mr05_evidence.py','backend/scripts/mr05_source_contracts.py'):
        files[name]=file_hash(ROOT/name)
    return files

def load_approved(path,approved):
    require(hexhash(approved),'INVALID_MANIFEST_FINGERPRINT')
    with Path(path).open('rb') as stream:raw=stream.read(32*1024*1024+1)
    require(len(raw)<=32*1024*1024,'MANIFEST_TOO_LARGE')
    require(hashlib.sha256(raw).hexdigest().upper()==approved.upper(),'MANIFEST_FINGERPRINT_MISMATCH')
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'DUPLICATE_JSON_FIELD');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=unique)

def schema_guard(schema,revision,*,database=TARGET):
    require(isinstance(schema,dict) and set(schema)==names_at(revision),'TABLE_INVENTORY_MISMATCH')
    for name,table in schema.items():
        require(isinstance(table,dict) and set(table)==SCHEMA_FIELDS,'INCOMPLETE_SCHEMA_CONTRACT')
        require(hexhash(table['ddl_sha256']),'MISSING_EXACT_DDL_HASH')
        require(all(isinstance(table[field],list) for field in SCHEMA_FIELDS-{'options','ddl_sha256'}),'INCOMPLETE_SCHEMA_METADATA')
        require(bool(table['columns']) and isinstance(table['options'],dict) and table['options'].get('engine')=='InnoDB','UNVERIFIED_TABLE_OPTIONS')
        require(all(isinstance(c,dict) and {'name','type','nullable','default','charset','collation','extra'}<=set(c) for c in table['columns']),'INCOMPLETE_COLUMN_METADATA')
        require(all(isinstance(c,dict) and {'name','definition','enforced'}<=set(c) and c['enforced'] is True for c in table['checks']),'CHECK_ENFORCEMENT_UNVERIFIED')
        require(all(isinstance(f,dict) and {'name','columns','referred_table','referred_columns','ondelete','onupdate'}<=set(f) and f['referred_table'] in schema and f.get('referred_schema') in (None,database) and len(f['columns'])==len(f['referred_columns'])>0 for f in table['foreign_keys']),'INCOMPLETE_FOREIGN_KEYS')

def trigger_guard(rows,revision):
    expected=trigger_specs(revision);seen=set()
    require(isinstance(rows,list),'MISSING_TRIGGER_INVENTORY')
    for row in rows:
        name=row.get('name');require(name in expected and name not in seen,'UNEXPECTED_OR_DUPLICATE_TRIGGER');seen.add(name)
        table,timing,event,message=expected[name]
        require((row.get('table'),row.get('timing'),row.get('event'))==(table,timing,event),'TRIGGER_TARGET_DRIFT')
        require(row.get('orientation')=='ROW' and bool(row.get('definer')),'TRIGGER_DEFINER_UNVERIFIED')
        require({'sql_mode','character_set_client','collation_connection','database_collation'}<=set(row),'TRIGGER_CONTEXT_MISSING')
        match=re.fullmatch(r"\s*SIGNAL\s+SQLSTATE\s+'45000'\s+SET\s+MESSAGE_TEXT\s*=\s*'([^']+)'\s*;?\s*",row.get('statement',''),re.I)
        require(match is not None and match[1]==message,'TRIGGER_BODY_DRIFT')
    require(seen==set(expected),'MISSING_TRIGGER')

def validate_manifest(manifest,backup_path,approved_source):
    require(isinstance(manifest,dict),'INVALID_MANIFEST')
    target_guard(manifest.get('target'),manifest.get('account'))
    require(manifest.get('source')=={'database':SOURCE,'host':'127.0.0.1','port':3306,'revision':CHAIN[0]},'SOURCE_IDENTITY_MISMATCH')
    require(hexhash(approved_source) and manifest.get('source_fingerprint')==approved_source.upper(),'SOURCE_FINGERPRINT_MISMATCH')
    require(manifest.get('provenance')==source_provenance(),'SOURCE_TOOLING_DRIFT')
    require(manifest.get('revision_sequence')==list(CHAIN),'REVISION_SEQUENCE_DRIFT')
    require(hexhash(manifest.get('backup_sha256')) and Path(backup_path).is_file(),'MISSING_BACKUP_EVIDENCE')
    require(file_hash(backup_path)==manifest['backup_sha256'].upper(),'BACKUP_FINGERPRINT_MISMATCH')
    require(manifest.get('backup_complete') is True and manifest.get('independent_recovery_approval') is True,'RECOVERY_EVIDENCE_UNAPPROVED')
    require(manifest.get('features')==dict.fromkeys(FEATURES,False),'FEATURE_GATE_ENABLED')
    require(set(manifest.get('stages',{}))==set(CHAIN),'MISSING_STAGE_CONTRACT')
    for revision,contract in manifest['stages'].items():
        require(contract.get('revision')==revision,'STAGE_REVISION_MISMATCH')
        schema_guard(contract.get('schema'),revision);trigger_guard(contract.get('triggers'),revision)
        require(all(contract.get(field)==[] for field in ('views','routines','events')),'UNREVIEWED_STORED_OBJECTS')
    baseline=manifest.get('baseline',{})
    require(set(baseline.get('originals',{}))==names_at(CHAIN[0])-{'alembic_version'},'INCOMPLETE_ORIGINAL_RECORDS')
    for table,data in baseline['originals'].items():
        require(type(data.get('row_count')) is int and data['row_count']>=0 and hexhash(data.get('content_sha256')),'INVALID_ORIGINAL_FINGERPRINT')
        require(isinstance(data.get('projection_columns'),list) and data['projection_columns']==[c['name'] for c in manifest['stages'][CHAIN[0]]['schema'][table]['columns']],'ORIGINAL_PROJECTION_DRIFT')
    require(digest(baseline)==approved_source.upper(),'APPROVED_BASELINE_FINGERPRINT_MISMATCH')
    require(isinstance(baseline.get('driver_approval_flags'),dict) and all(hexhash(k) and type(v) is bool for k,v in baseline['driver_approval_flags'].items()),'DRIVER_BASELINE_MISSING')
    require(len(baseline['driver_approval_flags'])==baseline['originals']['driver_profiles']['row_count'],'INCOMPLETE_DRIVER_BASELINE')
    return manifest

def orphan_query(table,fk):
    """MATCH SIMPLE: a composite reference with ANY NULL is not an orphan."""
    def quote(name):
        require(isinstance(name,str) and re.fullmatch('[a-z][a-z0-9_]*',name) is not None,'UNSAFE_METADATA_IDENTIFIER')
        return '`'+name+'`'
    require(len(fk['columns'])==len(fk['referred_columns'])>0,'INVALID_COMPOSITE_KEY')
    present=' AND '.join('c.'+quote(c)+' IS NOT NULL' for c in fk['columns'])
    equality=' AND '.join('p.'+quote(p)+'=c.'+quote(c) for c,p in zip(fk['columns'],fk['referred_columns']))
    return 'SELECT COUNT(*) FROM '+quote(table)+' c WHERE '+present+' AND NOT EXISTS (SELECT 1 FROM '+quote(fk['referred_table'])+' p WHERE '+equality+')'

def check_snapshot(snapshot,manifest,revision):
    target_guard(snapshot.get('database'),snapshot.get('account'))
    require(snapshot.get('host')=='127.0.0.1' and snapshot.get('port')==3306 and snapshot.get('tls_verified') is True,'CONNECTION_IDENTITY_UNVERIFIED')
    require(snapshot.get('revision')==revision,'ACTUAL_REVISION_MISMATCH')
    schema_guard(snapshot.get('schema'),revision);trigger_guard(snapshot.get('triggers'),revision)
    actual={k:snapshot.get(k) for k in ('revision','schema','triggers','views','routines','events')}
    require(actual==manifest['stages'][revision],'STAGE_SCHEMA_OR_STORED_OBJECT_DRIFT')
    require(snapshot.get('originals')==manifest['baseline']['originals'],'ORIGINAL_RECORDS_CHANGED')
    if revision!=CHAIN[0]:
        require(snapshot.get('driver_exemption_flags')==manifest['baseline']['driver_approval_flags'],'DRIVER_EXEMPTION_BACKFILL_MISMATCH')
    expected_new=names_at(revision)-names_at(CHAIN[0])
    require(snapshot.get('new_table_counts')==dict.fromkeys(expected_new,0),'NEW_TABLE_INITIALIZATION_MISMATCH')
    if revision==CHAIN[-1]:
        require(snapshot.get('historical_address_request_values')=={'row_count':manifest['baseline']['originals']['customer_addresses']['row_count'],'non_null_keys':0,'non_null_hashes':0},'HISTORICAL_ADDRESS_BACKFILL_MISMATCH')
    expected_fk=sum(len(t['foreign_keys']) for t in snapshot['schema'].values())
    require(type(snapshot.get('foreign_keys_checked')) is int and snapshot['foreign_keys_checked']==expected_fk and snapshot.get('orphan_count')==0,'RELATIONSHIP_INTEGRITY_UNVERIFIED')
    require(snapshot.get('foreign_key_checks')==1 and snapshot.get('unique_checks')==1 and snapshot.get('strict_sql_mode') is True,'SESSION_ENFORCEMENT_UNVERIFIED')

def verify_recovery(source,restored,approved_source_hash):
    """Compare privately captured inventories; no restore is performed here.

    Keep exact DDL differences visible. No implicit schema-name/DEFINER rewrite
    or semantic normalization is accepted by this separate strict comparison.
    """
    require(hexhash(approved_source_hash) and digest(source)==approved_source_hash.upper(),'RECOVERY_BASELINE_FINGERPRINT_MISMATCH')
    require(source.get('database')==SOURCE and restored.get('database')==RESTORE_TARGET and restored.get('account')==RESTORE_ACCOUNT,'RECOVERY_TARGET_MISMATCH')
    require(source.get('revision') in CHAIN and restored.get('revision')==source['revision'],'RECOVERY_REVISION_MISMATCH')
    revision=source['revision']
    for snapshot in (source,restored):
        require(snapshot.get('host')=='127.0.0.1' and snapshot.get('port')==3306 and snapshot.get('tls_verified') is True,'RECOVERY_CONNECTION_UNVERIFIED')
        schema_guard(snapshot.get('schema'),revision,database=snapshot['database']);trigger_guard(snapshot.get('triggers'),revision)
        require(set(snapshot.get('records',{}))==names_at(revision),'RECOVERY_RECORD_INVENTORY_INCOMPLETE')
        for record in snapshot['records'].values():
            require(type(record.get('row_count')) is int and record['row_count']>=0 and hexhash(record.get('content_sha256')),'RECOVERY_RECORD_FINGERPRINT_INVALID')
        require(snapshot.get('orphan_count')==0 and snapshot.get('foreign_keys_checked')==sum(len(t['foreign_keys']) for t in snapshot['schema'].values()),'RECOVERY_RELATIONSHIPS_UNVERIFIED')
        require(all(snapshot.get(k)==[] for k in ('views','routines','events')),'UNREVIEWED_STORED_OBJECTS')
    for field in ('schema','triggers','records','views','routines','events'):
        require(source[field]==restored[field],'RECOVERY_'+field.upper()+'_MISMATCH')
    return 'PASS_CAPTURED_RECOVERY_COMPARISON_ONLY; LIVE_SOURCE_RECHECK_AND_DENIAL_TESTS_REQUIRED'

def execute_prepared(adapter,manifest,*,database,account,execute=False,confirmation=None,authorization=None,validated_evidence=None):
    """Future adapter protocol, exercised ONLY with fictional mocks in MR-02.

    Adapter must enforce scratch identity and grants BEFORE all connections and
    writes. No adapter/plugin is accepted by the CLI. One upgrade call per stage.
    Its private evidence implementation must use exclusive files and verified ACLs.
    """
    target_guard(database,account)
    require(execute and confirmation==TARGET and authorization==TOKEN,'EXECUTION_NOT_AUTHORIZED')
    def bound_evidence():
        try:backup,approved_source=evidence_contract.revalidate(validated_evidence,manifest)
        except evidence_contract.EvidenceError as error:raise GuardFailure(str(error)) from None
        except Exception:raise GuardFailure('APPROVED_EVIDENCE_UNAVAILABLE') from None
        validate_manifest(manifest,backup,approved_source)
    bound_evidence() # Generic adapter cannot self-attest backup/manifest validity.
    require(manifest.get('provenance')==source_provenance() and manifest.get('revision_sequence')==list(CHAIN),'SOURCE_TOOLING_DRIFT')
    require(digest(manifest.get('baseline'))==manifest.get('source_fingerprint'),'APPROVED_BASELINE_FINGERPRINT_MISMATCH')
    require(adapter.preflight(manifest) is True,'FRESH_DBA_FREEZE_SCOPE_GATE_FAILED')
    require(adapter.source_fingerprint()==manifest['source_fingerprint'],'SOURCE_CHANGED_BEFORE')
    check_snapshot(adapter.snapshot(),manifest,CHAIN[0])
    adapter.reserve_exclusive_attempt() # No mutation before every initial guard.
    stage='BASELINE_VERIFIED'
    try:
        for previous,current in zip(CHAIN,CHAIN[1:]):
            stage=current
            bound_evidence()
            require(adapter.preflight(manifest) is True,'FREEZE_OR_SCOPE_CHANGED')
            require(adapter.source_fingerprint()==manifest['source_fingerprint'],'SOURCE_CHANGED_DURING')
            check_snapshot(adapter.snapshot(),manifest,previous)
            adapter.upgrade_one(previous,current)
            check_snapshot(adapter.snapshot(),manifest,current)
            adapter.record_stage(current)
        require(adapter.source_fingerprint()==manifest['source_fingerprint'],'SOURCE_CHANGED_AFTER')
        bound_evidence()
        adapter.record_success()
        return 'PASS_MIGRATION_STAGES_ONLY; RECOVERY_AND_CONCURRENCY_NOT_VERIFIED'
    except BaseException as error:
        code=error.code if isinstance(error,GuardFailure) else 'OPERATION_INTERRUPTED' if isinstance(error,KeyboardInterrupt) else 'ADAPTER_OPERATION_FAILED'
        try:adapter.record_failure(stage,code,inspect_partial=True)
        except BaseException:pass # Preserve the original failure, never clean up.
        raise GuardFailure(code) from None

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('offline','execute'))
    parser.add_argument('--database',required=True);parser.add_argument('--account',required=True)
    parser.add_argument('--manifest',required=True);parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--source-fingerprint',required=True);parser.add_argument('--backup',required=True)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--confirm-target');parser.add_argument('--authorization')
    args=parser.parse_args(argv)
    try:
        target_guard(args.database,args.account)
        if args.mode=='offline':require(not args.execute and args.confirm_target is None and args.authorization is None,'OFFLINE_EXECUTION_FLAGS_REJECTED')
        else:require(args.execute and args.confirm_target==TARGET and args.authorization==TOKEN,'EXECUTION_NOT_AUTHORIZED')
        manifest=load_approved(args.manifest,args.manifest_sha256)
        validate_manifest(manifest,args.backup,args.source_fingerprint)
        if args.mode=='execute':raise GuardFailure('LIVE_ADAPTER_NOT_PREPARED_OR_AUTHORIZED')
        print('MR02=PASS_OFFLINE_CONTRACT_ONLY; DATABASE_CONNECTIONS=0; EXECUTION_READY=no')
        return 0
    except Exception as error:
        code=error.code if isinstance(error,GuardFailure) else 'INVALID_OR_UNAVAILABLE_EVIDENCE'
        print('MR02=STOP; CODE='+code+'; PRESERVE_STATE; NO_RETRY');return 1

if __name__=='__main__':raise SystemExit(main())

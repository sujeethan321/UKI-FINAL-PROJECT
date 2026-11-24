"""MR-03 mock-only MySQL capture/execution interfaces. NOT a live DB adapter.

No database library, application configuration, credentials, SQL executor or
connection factory is imported. Only exact in-memory port types are accepted.
The unchanged MR-02 CLI remains blocked. A real adapter requires a new release.
"""
import copy
from datetime import date,datetime,time
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
_spec=importlib.util.spec_from_file_location('mr03_contract',ROOT/'backend/scripts/mr02_rehearsal.py')
m=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(m)
ALGORITHM='mr03-typed-sorted-row-sha256-v1'
SOURCE_ACCOUNT='lankapex_mr03_source_reader@127.0.0.1'
MIGRATOR_RIGHTS={'SELECT','INSERT','UPDATE','DELETE','CREATE','ALTER','INDEX','REFERENCES','TRIGGER'}
READ_RIGHTS={'SELECT'}
MAX_ROWS=100000

def blocked_real_connection(*args,**kwargs):
    raise m.GuardFailure('MR03_REAL_CONNECTION_DISABLED') from None

def adapter_provenance():
    return {'backend/scripts/mr03_adapter.py':m.file_hash(Path(__file__))}

def fixture_data(value,depth=0):
    """Reject connections/callbacks before deepcopy can invoke custom methods."""
    m.require(depth<64,'MR03_NONDATA_FIXTURE')
    if type(value) in (type(None),bool,int,str,bytes,Decimal,date,datetime,time):return
    if type(value) in (list,tuple):
        for item in value:fixture_data(item,depth+1)
        return
    if type(value) is dict:
        m.require(all(type(key) is str for key in value),'MR03_NONDATA_FIXTURE')
        for item in value.values():fixture_data(item,depth+1)
        return
    raise m.GuardFailure('MR03_NONDATA_FIXTURE')

def binding_guard(database,account,role):
    expected={'source':(m.SOURCE,SOURCE_ACCOUNT),'migration':(m.TARGET,m.ACCOUNT),'recovery':(m.RESTORE_TARGET,m.RESTORE_ACCOUNT)}
    m.require(role in expected and (database,account)==expected[role],'MR03_BINDING_REJECTED')

def typed_value(value):
    if value is None:return ['null']
    if type(value) is bool:return ['bool',value]
    if type(value) is int:return ['int',str(value)]
    if type(value) is Decimal:
        m.require(value.is_finite(),'MR03_NONFINITE_NUMBER')
        # Exact formatting without Decimal.normalize() context rounding.
        text=format(value,'f')
        if '.' in text:text=text.rstrip('0').rstrip('.')
        if Decimal(text)==0:text='0'
        return ['decimal',text]
    if type(value) is str:return ['text',value]
    if type(value) is bytes:return ['bytes',value.hex()]
    if type(value) in (datetime,time):
        m.require(value.tzinfo is None,'MR03_TIMESTAMP_CONVENTION_UNREVIEWED')
        return [type(value).__name__,value.isoformat(timespec='microseconds')]
    if type(value) is date:return ['date',value.isoformat()]
    raise m.GuardFailure('MR03_UNSUPPORTED_ROW_TYPE')

def fingerprint(rows,columns):
    m.require(type(columns) is list and bool(columns) and len(set(columns))==len(columns),'MR03_INVALID_PROJECTION')
    hashes=[]
    for row in rows:
        m.require(len(hashes)<MAX_ROWS and type(row) is dict and all(c in row for c in columns),'MR03_ROW_CAPTURE_INCOMPLETE_OR_TOO_LARGE')
        raw=json.dumps([typed_value(row[c]) for c in columns],ensure_ascii=False,separators=(',',':')).encode('utf-8')
        hashes.append(hashlib.sha256(raw).digest())
    # Fixed-length row digests, sorted with multiplicity: stable without PK/order,
    # duplicate rows preserved, bounded memory, no financial rows in evidence.
    out=hashlib.sha256();out.update(ALGORITHM.encode());out.update(len(hashes).to_bytes(8,'big'))
    for row_hash in sorted(hashes):out.update(row_hash)
    return {'row_count':len(hashes),'content_sha256':out.hexdigest().upper()}

class MockCatalogPort:
    """Fictional transport: primitive fixture data only, no executable callback.

    A future transport must supply these independent metadata reads from MySQL
    and a coherent bounded snapshot. This type itself cannot open connections.
    """
    def __init__(self,state):fixture_data(state);self.state=copy.deepcopy(state)
    def identity(self):return copy.deepcopy(self.state['identity'])
    def permissions(self):return copy.deepcopy(self.state['permissions'])
    def revision(self):return copy.deepcopy(self.state['revisions'])
    def table_names(self):return sorted(self.state['schema'])
    def table(self,name):return copy.deepcopy(self.state['schema'][name])
    def show_create(self,name):return self.state['ddl'][name]
    def triggers(self):return copy.deepcopy(self.state['triggers'])
    def stored_objects(self):return copy.deepcopy({k:self.state[k] for k in ('views','routines','events')})
    def rows(self,name):return iter(copy.deepcopy(self.state['rows'][name]))
    def row_count(self,name):return self.state.get('count_overrides',{}).get(name,len(self.state['rows'][name]))
    def relationships(self):return copy.deepcopy(self.state['relationship_checks'])
    def freeze_observation(self):return copy.deepcopy(self.state['freeze'])

def permissions_guard(grants,database,role):
    m.require(type(grants) is dict and set(grants)=={'global','schemas','tables','active_roles','default_roles','mandatory_roles','grant_option','partial_revokes'},'MR03_GRANTS_INCOMPLETE')
    m.require(grants['global'] in ([],['USAGE']) and not grants['tables'] and grants['active_roles']==grants['default_roles']==grants['mandatory_roles']==[] and grants['grant_option'] is False,'MR03_UNSAFE_PRIVILEGES')
    m.require(type(grants['partial_revokes']) is bool,'MR03_PRIVILEGE_PATTERN_UNVERIFIED')
    pattern=database if grants['partial_revokes'] else database.replace('_',r'\_')
    required=MIGRATOR_RIGHTS if role=='migration' else READ_RIGHTS
    m.require(type(grants['schemas']) is dict and set(grants['schemas'])=={pattern},'MR03_CROSS_SCHEMA_PRIVILEGES')
    rights=grants['schemas'][pattern]
    m.require(type(rights) is list and len(rights)==len(set(rights)) and set(rights)==required,'MR03_UNSAFE_PRIVILEGES')

class ReadOnlyCapture:
    """Separate capability: reads fixture catalog; never exposes stage mutation."""
    def __init__(self,port,*,database,account,role,server_uuid):
        binding_guard(database,account,role)
        m.require(type(port) is MockCatalogPort,'MR03_NONMOCK_TRANSPORT_REJECTED')
        m.require(type(server_uuid) is str and bool(server_uuid),'MR03_SERVER_ID_UNAPPROVED')
        self.port=port;self.database=database;self.account=account;self.role=role;self.server_uuid=server_uuid
    def inspect_identity(self):
        binding_guard(self.database,self.account,self.role)
        identity=self.port.identity()
        m.require(identity.get('database')==self.database and identity.get('current_user')==self.account and identity.get('host')=='127.0.0.1' and identity.get('port')==3306 and identity.get('server_uuid')==self.server_uuid,'MR03_ACTUAL_IDENTITY_MISMATCH')
        m.require(identity.get('tls_verified') is True and identity.get('tls_version') in ('TLSv1.2','TLSv1.3'),'MR03_TLS_UNVERIFIED')
        m.require(identity.get('foreign_key_checks')==1 and identity.get('unique_checks')==1 and identity.get('strict_sql_mode') is True,'MR03_SESSION_ENFORCEMENT_UNVERIFIED')
        permissions_guard(self.port.permissions(),self.database,self.role)
        return identity
    def actual_revision(self):
        values=self.port.revision()
        m.require(type(values) is list and len(values)==1 and values[0] in m.CHAIN,'MR03_REVISION_UNVERIFIED')
        return values[0]
    def inventory(self):
        self.inspect_identity();revision=self.actual_revision();schema={}
        for name in self.port.table_names():
            table=self.port.table(name);ddl=self.port.show_create(name)
            m.require(type(ddl) is str and 0<len(ddl)<=1024*1024,'MR03_DDL_CAPTURE_UNVERIFIED')
            table['ddl_sha256']=hashlib.sha256(ddl.encode('utf-8')).hexdigest().upper();schema[name]=table
        m.schema_guard(schema,revision,database=self.database)
        triggers=self.port.triggers();m.trigger_guard(triggers,revision)
        objects=self.port.stored_objects()
        m.require(all(objects.get(k)==[] for k in ('views','routines','events')),'MR03_UNREVIEWED_STORED_OBJECTS')
        return dict(revision=revision,schema=schema,triggers=triggers,**objects)
    def table_fingerprint(self,name,columns):
        m.require(name in self.port.table_names(),'MR03_UNKNOWN_TABLE')
        result=fingerprint(self.port.rows(name),columns)
        m.require(result['row_count']==self.port.row_count(name),'MR03_ROW_COUNT_CHANGED_DURING_CAPTURE')
        return result
    def original_records(self,manifest):
        result={}
        for name,expected in manifest['baseline']['originals'].items():
            columns=expected['projection_columns']
            result[name]=dict(**self.table_fingerprint(name,columns),projection_columns=copy.deepcopy(columns))
        return result
    def driver_flags(self,*,exempt=False):
        result={}
        for row in self.port.rows('driver_profiles'):
            m.require(type(row.get('user_id')) is int and row.get('approval_status') in ('pending','approved','rejected'),'MR03_DRIVER_CAPTURE_INVALID')
            key=m.digest(['driver-identity-v1',row['user_id']])
            m.require(key not in result,'MR03_DUPLICATE_DRIVER_IDENTITY')
            if exempt:
                m.require(type(row.get('legacy_document_exempt')) in (int,bool) and row['legacy_document_exempt'] in (0,1),'MR03_DRIVER_EXEMPTION_INVALID')
                result[key]=bool(row['legacy_document_exempt'])
            else:result[key]=row['approval_status']=='approved'
        m.require(len(result)==self.port.row_count('driver_profiles'),'MR03_DRIVER_COUNT_MISMATCH')
        return result
    def baseline(self,manifest):
        inventory=self.inventory()
        m.require(inventory['revision']==m.CHAIN[0],'MR03_SOURCE_BASELINE_REVISION_MISMATCH')
        m.require(inventory==manifest['stages'][m.CHAIN[0]],'MR03_SOURCE_SCHEMA_CHANGED')
        m.require(self.relationship_summary(inventory)['orphan_count']==0,'MR03_SOURCE_ORPHANS')
        return dict(originals=self.original_records(manifest),driver_approval_flags=self.driver_flags())
    def relationship_summary(self,inventory):
        expected={}
        for table,metadata in inventory['schema'].items():
            for fk in metadata['foreign_keys']:
                m.orphan_query(table,fk) # Validates identifiers and MATCH SIMPLE structure; never executes SQL.
                key=table+':'+fk['name'];m.require(key not in expected,'MR03_DUPLICATE_FOREIGN_KEY');expected[key]=fk
        observed=self.port.relationships()
        m.require(type(observed) is dict and set(observed)==set(expected) and all(type(v) is int and v>=0 for v in observed.values()),'MR03_INCOMPLETE_ORPHAN_INSPECTION')
        return dict(foreign_keys_checked=len(observed),orphan_count=sum(observed.values()))
    def snapshot(self,manifest):
        inventory=self.inventory();revision=inventory['revision'];identity=self.inspect_identity()
        result=dict(**inventory,database=self.database,account=self.account,host='127.0.0.1',port=3306,tls_verified=True,
            originals=self.original_records(manifest),new_table_counts={name:self.port.row_count(name) for name in m.names_at(revision)-m.names_at(m.CHAIN[0])},
            foreign_key_checks=identity['foreign_key_checks'],unique_checks=identity['unique_checks'],strict_sql_mode=identity['strict_sql_mode'],**self.relationship_summary(inventory))
        if revision!=m.CHAIN[0]:result['driver_exemption_flags']=self.driver_flags(exempt=True)
        if revision==m.CHAIN[-1]:
            rows=list(self.port.rows('customer_addresses'))
            m.require(all('create_request_key' in r and 'create_request_hash' in r for r in rows),'MR03_ADDRESS_CAPTURE_INCOMPLETE')
            result['historical_address_request_values']=dict(row_count=len(rows),non_null_keys=sum(r['create_request_key'] is not None for r in rows),non_null_hashes=sum(r['create_request_hash'] is not None for r in rows))
        return result
    def recovery_snapshot(self):
        inventory=self.inventory()
        records={name:self.table_fingerprint(name,[c['name'] for c in table['columns']]) for name,table in inventory['schema'].items()}
        return dict(**inventory,database=self.database,account=self.account,host='127.0.0.1',port=3306,tls_verified=True,records=records,**self.relationship_summary(inventory))
    def inspect_partial(self):
        """Non-validating structural observation, so failed CHECK/trigger sets survive."""
        self.inspect_identity()
        names=self.port.table_names();triggers=self.port.triggers()
        observed=dict(revisions=self.port.revision(),tables=names,trigger_names=sorted(r.get('name','') for r in triggers))
        observed['schema_digest']=m.digest({n:self.port.table(n) for n in names})
        observed['exact_ddl_digest']=m.digest({n:hashlib.sha256(self.port.show_create(n).encode()).hexdigest().upper() for n in names})
        observed['trigger_digest']=m.digest(triggers)
        return observed
    def coherent_capture(self,manifest,receipt,*,operation='snapshot',clock=None):
        """Mock transaction boundary; cannot activate an actual MySQL session."""
        e=m.evidence_contract
        payload=e.receipt_payload(receipt)
        m.require(payload['server_uuid']==self.server_uuid and payload['source']==m.SOURCE and payload['scratch']==m.TARGET,'MR03_SNAPSHOT_APPROVAL_BINDING_MISMATCH')
        m.require(payload['source_account']==SOURCE_ACCOUNT and payload['scratch_account']==m.ACCOUNT,'MR03_SNAPSHOT_APPROVAL_BINDING_MISMATCH')
        m.require(operation in ('snapshot','baseline'),'MR03_UNAPPROVED_CAPTURE_OPERATION')
        owner='mr05-'+m.digest([self.database,self.account,payload['evidence_id']])
        options={} if clock is None else {'clock':clock}
        transaction=e.MockConsistentSnapshot(self.port.state,owner=owner,freeze_receipt=receipt,**options)
        try:
            transaction.read(owner)
            result=getattr(self,operation)(manifest)
            m.require(self.port.state is transaction.state,'MR05_CAPTURE_STATE_REPLACED')
            transaction.finish(owner)
            return result
        except BaseException:
            transaction.interrupt();raise

class MockMigrationPort:
    """Fixture-only writer. No SQL/Alembic executor or callable injection exists."""
    def __init__(self,catalog,stage_states):
        m.require(type(catalog) is MockCatalogPort,'MR03_NONMOCK_TRANSPORT_REJECTED')
        identity=catalog.identity();binding_guard(identity.get('database'),identity.get('current_user'),'migration')
        fixture_data(stage_states)
        self.catalog=catalog;self.stages=copy.deepcopy(stage_states);self.attempted=[];self.fail_after_apply=False;self.failed=False
    def apply_one(self,previous,current):
        m.require(not self.failed,'MR03_FAILED_ATTEMPT_LATCHED')
        identity=self.catalog.identity();binding_guard(identity.get('database'),identity.get('current_user'),'migration')
        m.require((previous,current) in tuple(zip(m.CHAIN,m.CHAIN[1:])),'MR03_UNAPPROVED_STAGE')
        m.require(self.catalog.revision()==[previous] and current in self.stages and current not in self.attempted,'MR03_STAGE_REPLAY_OR_REVISION_MISMATCH')
        m.require(self.stages[current]['identity']==identity and self.stages[current]['permissions']==self.catalog.permissions(),'MR03_STAGE_BINDING_OR_GRANTS_CHANGED')
        self.attempted.append(current);self.catalog.state=copy.deepcopy(self.stages[current])
        if self.fail_after_apply:
            self.failed=True;raise m.GuardFailure('MR03_MOCK_PARTIAL_DDL_FAILURE')

class MemoryEvidence:
    """Mock-only exclusive evidence sink; never writes a real evidence file."""
    def __init__(self):self.records=[];self.reserved=False
    def reserve(self):
        m.require(not self.reserved,'MR03_ATTEMPT_ALREADY_RESERVED');self.reserved=True;self.records.append({'status':'RESERVED_MOCK_ONLY'})
    def append(self,value):self.records.append(copy.deepcopy(value))

class DurableMockEvidence(MemoryEvidence):
    """Offline test evidence only; no live Windows ACL assurance is implied."""
    def __init__(self,parent,label):
        super().__init__();self.sink=m.evidence_contract.OfflineEvidenceSink(parent,label)
    def append(self,value):
        super().append(value)
        if value.get('status')=='STOP_MOCK_ONLY':
            self.sink.failure(revision=value['stage'],code='DDL_STAGE_FAILED',observed_schema={})
        elif value.get('status')=='PARTIAL_STATE_OBSERVED_MOCK_ONLY':
            observed=value['observed'];revisions=observed['revisions']
            if len(revisions)==1 and revisions[0] in m.CHAIN:
                self.sink.failure(revision=revisions[0],code='UNEXPECTED_STATE',observed_schema={'tables':observed['tables'],'triggers':observed['trigger_names'],'schema_sha256':observed['schema_digest']},original_fingerprint=value.get('original_fingerprint'),source_fingerprint=value.get('source_fingerprint'))
        elif value.get('status')=='CHAIN_VERIFIED_MOCK_ONLY':self.sink.complete()

class PreparedAdapter:
    """MR-02 adapter implementation restricted to exact mocked capabilities."""
    def __init__(self,*,source,capture,writer,evidence,manifest_path,manifest_sha256,source_fingerprint,backup_path,dba_authority=None,dba_evidence=None,mock_now=0):
        m.require(type(source) is ReadOnlyCapture and type(capture) is ReadOnlyCapture and type(writer) is MockMigrationPort and type(evidence) in (MemoryEvidence,DurableMockEvidence),'MR03_NONMOCK_CAPABILITY_REJECTED')
        m.require(source.role=='source' and capture.role=='migration' and writer.catalog is capture.port,'MR03_CAPABILITY_BINDING_MISMATCH')
        self.source=source;self.capture=capture;self.writer=writer;self.evidence=evidence
        self.manifest_path=Path(manifest_path);self.manifest_sha256=manifest_sha256;self.source_hash=source_fingerprint;self.backup_path=Path(backup_path)
        self.dba_authority=dba_authority;self.dba_evidence=copy.deepcopy(dba_evidence or []);self.mock_now=mock_now
        self.manifest=self._approved();self.last_verified=None;self.failed=False
        self.validated_evidence=m.evidence_contract.issue(self.manifest_path,self.manifest_sha256,self.backup_path,self.manifest['backup_sha256'],self.source_hash)
    def _approved(self):
        value=m.load_approved(self.manifest_path,self.manifest_sha256)
        m.validate_manifest(value,self.backup_path,self.source_hash)
        m.require(value.get('adapter_provenance')==adapter_provenance() and value.get('fingerprint_algorithm')==ALGORITHM,'MR03_ADAPTER_OR_FINGERPRINT_CONTRACT_DRIFT')
        approval=value.get('dba_approval',{})
        m.require(set(approval)=={'server_uuid','source','scratch','source_account','scratch_account','source_scope','scratch_scope','issuer','max_age_seconds'},'MR05_DBA_APPROVAL_REQUIRED')
        m.require(approval['server_uuid']==self.source.server_uuid==self.capture.server_uuid and bool(approval['server_uuid']),'MR05_APPROVED_SERVER_MISMATCH')
        m.require((approval['source'],approval['scratch'],approval['source_account'],approval['scratch_account'],approval['source_scope'],approval['scratch_scope'])==(m.SOURCE,m.TARGET,SOURCE_ACCOUNT,m.ACCOUNT,'SELECT_ONLY','EXACT_SCRATCH_MIGRATOR'),'MR05_APPROVED_IDENTITY_SCOPE_MISMATCH')
        return value
    def _receipt(self):
        e=m.evidence_contract
        m.require(type(self.dba_authority) is e.MockAttestationAuthority and bool(self.dba_evidence),'MR05_TRUSTED_MOCK_DBA_EVIDENCE_REQUIRED')
        envelope=self.dba_evidence.pop(0)
        try:return self.dba_authority.verify(envelope,self.manifest['dba_approval'],now=self.mock_now)
        except e.EvidenceError as error:raise m.GuardFailure(str(error)) from None
    def preflight(self,manifest):
        m.require(not self.failed,'MR03_FAILED_ATTEMPT_LATCHED')
        m.require(self._approved()==manifest==self.manifest,'MR03_APPROVED_BINDING_CHANGED')
        self.source.inspect_identity();self.capture.inspect_identity()
        self._receipt() # Independently issued, scope-bound, fresh, single-use MOCK receipt.
        freeze=self.capture.port.freeze_observation()
        m.require(freeze==dict(writer_freeze=True,ddl_freeze=True,dba_visibility=True,unexplained_sessions=0,transactions=0,locks=0,ddl=0,enabled_events=0,replication_appliers=0,scratch_isolated=True),'MR03_FRESH_DBA_GATE_UNVERIFIED')
        return True
    def source_fingerprint(self):return m.digest(self.source.coherent_capture(self.manifest,self._receipt(),operation='baseline'))
    def snapshot(self):
        result=self.capture.coherent_capture(self.manifest,self._receipt());m.check_snapshot(result,self.manifest,result['revision'])
        self.last_verified=self.capture.inspect_partial();return result
    def reserve_exclusive_attempt(self):self.evidence.reserve()
    def upgrade_one(self,previous,current):
        m.require(self.evidence.reserved and not self.failed,'MR03_ATTEMPT_NOT_READY')
        self.preflight(self.manifest)
        m.require(self.source_fingerprint()==self.source_hash,'MR03_SOURCE_CHANGED')
        m.check_snapshot(self.capture.coherent_capture(self.manifest,self._receipt()),self.manifest,previous)
        try:self.writer.apply_one(previous,current)
        except BaseException:
            self.failed=True;raise
    def record_stage(self,current):
        m.check_snapshot(self.capture.coherent_capture(self.manifest,self._receipt()),self.manifest,current)
        self.evidence.append(dict(status='STAGE_VERIFIED_MOCK_ONLY',revision=current))
    def record_success(self):self.evidence.append(dict(status='CHAIN_VERIFIED_MOCK_ONLY',revision=m.CHAIN[-1]))
    def record_failure(self,stage,code,inspect_partial=True):
        self.failed=True
        # Persist a safe error first, then one best-effort observation. No retry.
        known=code if type(code) is str and re.fullmatch(r'MR03_[A-Z0-9_]{1,80}',code) else 'STAGE_OPERATION_FAILED'
        record=dict(status='STOP_MOCK_ONLY',stage=stage if stage in m.CHAIN else 'UNKNOWN',code=known)
        self.evidence.append(record)
        if inspect_partial:
            try:
                observed=self.capture.inspect_partial()
                try:original_hash=m.digest(self.capture.original_records(self.manifest))
                except BaseException:original_hash='UNAVAILABLE'
                try:source_hash=self.source_fingerprint()
                except BaseException:source_hash='UNAVAILABLE'
                self.evidence.append(dict(status='PARTIAL_STATE_OBSERVED_MOCK_ONLY',observed=observed,
                    changed_since_last_verified=observed!=self.last_verified,partial_ddl_suspected=observed!=self.last_verified,original_fingerprint=original_hash,source_fingerprint=source_hash))
            except BaseException:self.evidence.append(dict(status='PARTIAL_STATE_UNAVAILABLE_PRESERVE_NO_RETRY'))

if __name__=='__main__':
    print('MR03=OFFLINE_INTERFACES_ONLY; REAL_EXECUTION_DISABLED; DATABASE_CONNECTIONS=0')
    raise SystemExit(2)

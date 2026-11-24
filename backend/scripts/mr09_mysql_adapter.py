"""MR-09 inspection/query plans and stage adapter; real transport ALWAYS blocked.

Only exact mocked interfaces can be instantiated in this release. No MySQL,
application configuration or Alembic execution library is imported. SQL below is
an explicit inspection plan, executed ONLY by a fixture dispatcher in tests.
"""
from dataclasses import dataclass
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import time

ROOT=Path(__file__).resolve().parents[2]
def load(key,path):
    spec=importlib.util.spec_from_file_location(key,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
a=load('mr09_previous_adapter','backend/scripts/mr03_adapter.py');m=a.m;e=m.evidence_contract
c=load('mr09_canonical','backend/scripts/mr07_canonical.py')
CONTRACT=ROOT/'backend/contracts/MR07_CANONICAL_OBJECTS.json'

SQL={
 'identity':"SELECT DATABASE() AS database_name,CURRENT_USER() AS account,@@server_uuid AS server_uuid,@@SESSION.foreign_key_checks AS fk_checks,@@SESSION.unique_checks AS unique_checks,@@SESSION.sql_mode AS sql_mode,@@GLOBAL.partial_revokes AS partial_revokes,@@GLOBAL.mandatory_roles AS mandatory_roles,CURRENT_ROLE() AS active_roles,VERSION() AS version",
 'tls':"SHOW SESSION STATUS WHERE Variable_name IN ('Ssl_version','Ssl_cipher')",
 'grants':'SHOW GRANTS FOR CURRENT_USER()',
 'revision':'SELECT version_num FROM alembic_version',
 'tables':'SELECT TABLE_NAME,ENGINE,TABLE_COLLATION,TABLE_TYPE FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME',
 'columns':'SELECT COLUMN_NAME,ORDINAL_POSITION,COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT,EXTRA,CHARACTER_SET_NAME,COLLATION_NAME,GENERATION_EXPRESSION FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION',
 'keys':"SELECT tc.CONSTRAINT_NAME,tc.CONSTRAINT_TYPE,k.COLUMN_NAME,k.ORDINAL_POSITION FROM information_schema.TABLE_CONSTRAINTS tc JOIN information_schema.KEY_COLUMN_USAGE k ON k.CONSTRAINT_SCHEMA=tc.CONSTRAINT_SCHEMA AND k.TABLE_NAME=tc.TABLE_NAME AND k.CONSTRAINT_NAME=tc.CONSTRAINT_NAME WHERE tc.TABLE_SCHEMA=%s AND tc.TABLE_NAME=%s AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY','UNIQUE') ORDER BY tc.CONSTRAINT_NAME,k.ORDINAL_POSITION",
 'foreign_keys':"SELECT k.CONSTRAINT_NAME,k.COLUMN_NAME,k.ORDINAL_POSITION,k.REFERENCED_TABLE_SCHEMA,k.REFERENCED_TABLE_NAME,k.REFERENCED_COLUMN_NAME,r.UPDATE_RULE,r.DELETE_RULE FROM information_schema.KEY_COLUMN_USAGE k JOIN information_schema.REFERENTIAL_CONSTRAINTS r ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND r.TABLE_NAME=k.TABLE_NAME AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME WHERE k.TABLE_SCHEMA=%s AND k.TABLE_NAME=%s AND k.REFERENCED_TABLE_NAME IS NOT NULL ORDER BY k.CONSTRAINT_NAME,k.ORDINAL_POSITION",
 'checks':"SELECT tc.CONSTRAINT_NAME,cc.CHECK_CLAUSE,tc.ENFORCED FROM information_schema.TABLE_CONSTRAINTS tc JOIN information_schema.CHECK_CONSTRAINTS cc ON cc.CONSTRAINT_SCHEMA=tc.CONSTRAINT_SCHEMA AND cc.CONSTRAINT_NAME=tc.CONSTRAINT_NAME WHERE tc.TABLE_SCHEMA=%s AND tc.TABLE_NAME=%s AND tc.CONSTRAINT_TYPE='CHECK' ORDER BY tc.CONSTRAINT_NAME",
 'indexes':'SELECT INDEX_NAME,SEQ_IN_INDEX,COLUMN_NAME,NON_UNIQUE,INDEX_TYPE,SUB_PART,COLLATION,IS_VISIBLE,EXPRESSION FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY INDEX_NAME,SEQ_IN_INDEX',
 'triggers':'SELECT TRIGGER_NAME,EVENT_OBJECT_TABLE,ACTION_TIMING,EVENT_MANIPULATION,ACTION_ORIENTATION,ACTION_STATEMENT,DEFINER,SQL_MODE,CHARACTER_SET_CLIENT,COLLATION_CONNECTION,DATABASE_COLLATION FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s ORDER BY TRIGGER_NAME',
 'routines':'SELECT ROUTINE_NAME,ROUTINE_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s',
 'events':'SELECT EVENT_NAME,STATUS FROM information_schema.EVENTS WHERE EVENT_SCHEMA=%s',
 'collations':'SELECT COLLATION_NAME,CHARACTER_SET_NAME FROM information_schema.COLLATIONS',
}

@dataclass(frozen=True)
class ReadPlan:
    key:str
    statement:str
    parameters:tuple
    context:tuple=()

def plan(key,database,table=None,columns=None):
    m.require(database in (m.SOURCE,m.TARGET),'MR09_UNAPPROVED_DATABASE')
    if table is not None:m.require(table in m.names_at(m.CHAIN[-1]),'MR09_UNAPPROVED_TABLE')
    if key in ('rows','count','ddl','columns','keys','foreign_keys','checks','indexes'):m.require(table is not None,'MR09_TABLE_REQUIRED')
    if key=='rows':
        m.require(type(columns) is list and columns and all(re.fullmatch('[a-z][a-z0-9_]*',x) for x in columns),'MR09_UNSAFE_PROJECTION')
        return ReadPlan(key,'SELECT '+','.join('`'+x+'`' for x in columns)+' FROM `'+table+'` LIMIT '+str(a.MAX_ROWS+1),())
    if key=='count':return ReadPlan(key,'SELECT COUNT(*) AS row_count FROM `'+table+'`',())
    if key=='ddl':return ReadPlan(key,'SHOW CREATE TABLE `'+table+'`',())
    m.require(key in SQL,'MR09_UNAPPROVED_INSPECTION')
    parameters=(database,table) if key in ('columns','keys','foreign_keys','checks','indexes') else (database,) if key in ('tables','triggers','routines','events') else ()
    return ReadPlan(key,SQL[key],parameters)

def orphan_plan(database,table,fk):
    m.require(database in (m.SOURCE,m.TARGET) and table in m.names_at(m.CHAIN[-1]) and fk['referred_table'] in m.names_at(m.CHAIN[-1]),'MR09_ORPHAN_SCOPE_REJECTED')
    statement=m.orphan_query(table,fk).replace('SELECT COUNT(*) ','SELECT COUNT(*) AS orphan_count ',1)
    return ReadPlan('orphan',statement,(),(table,fk['name'],tuple(fk['columns']),fk['referred_table'],tuple(fk['referred_columns'])))

class DisabledRealTransport:
    def connect(self,*args,**kwargs):raise m.GuardFailure('MR09_REAL_EXECUTION_DISABLED')
    def fetch(self,*args,**kwargs):raise m.GuardFailure('MR09_REAL_EXECUTION_DISABLED')
    def upgrade(self,*args,**kwargs):raise m.GuardFailure('MR09_REAL_EXECUTION_DISABLED')

class MockMySQLSession:
    """Fixture results for explicit read plans, no SQL interpretation/execution."""
    def __init__(self,database,account,results):
        role='source' if database==m.SOURCE else 'migration';a.binding_guard(database,account,role)
        a.fixture_data(results);self.database=database;self.account=account;self.results=copy.deepcopy(results);self.calls=[];self.in_snapshot=False
    def fetch(self,request,table=None):
        m.require(type(request) is ReadPlan,'MR09_INVALID_READ_PLAN')
        if request.key=='orphan':
            context=request.context;m.require(len(context)==5 and context[0]==table,'MR09_ORPHAN_SCOPE_REJECTED')
            fk=dict(name=context[1],columns=list(context[2]),referred_table=context[3],referred_columns=list(context[4]))
            m.require(request==orphan_plan(self.database,table,fk),'MR09_INSPECTION_PLAN_CHANGED')
            self.calls.append(('orphan',table));return copy.deepcopy(self.results['orphans'][table][fk['name']])
        expected=plan(request.key,self.database,table,cols_from_plan(request) if request.key=='rows' else None)
        m.require(request==expected,'MR09_INSPECTION_PLAN_CHANGED')
        self.calls.append((request.key,table))
        value=self.results[request.key]
        if table is not None:value=value[table]
        if request.key=='rows':return [{name:row[name] for name in cols_from_plan(request)} for row in copy.deepcopy(value[:a.MAX_ROWS+1])]
        return copy.deepcopy(value)
    def begin_readonly(self):
        m.require(not self.in_snapshot,'MR09_SNAPSHOT_ALREADY_OWNED');self.in_snapshot=True
        self._before=e.MockConsistentSnapshot._bytes(self.results)
        self._deadline=time.monotonic()+30
        # Future reviewed transport must issue these exact transaction intents.
        self.transaction_intent=('REPEATABLE READ','WITH CONSISTENT SNAPSHOT','READ ONLY')
    def end_readonly(self):
        try:m.require(self.in_snapshot and time.monotonic()<self._deadline and self._before==e.MockConsistentSnapshot._bytes(self.results),'MR09_MIXED_CAPTURE')
        finally:self.in_snapshot=False

def cols_from_plan(request):return re.findall(r'`([a-z][a-z0-9_]*)`',request.statement.split(' FROM ')[0])

def grouped(rows,key,ordinal):
    result={}
    for row in rows:
        m.require(type(row[key]) is str and bool(row[key]) and type(row[ordinal]) is int,'MR09_METADATA_IDENTITY_UNAVAILABLE')
        result.setdefault(row[key],[]).append(row)
    for values in result.values():
        values.sort(key=lambda x:x[ordinal]);m.require([x[ordinal] for x in values]==list(range(1,len(values)+1)),'MR09_METADATA_ORDINAL_DRIFT')
    return result

class MySQLInspector:
    def __init__(self,session,approval):
        m.require(type(session) is MockMySQLSession,'MR09_REAL_TRANSPORT_DISABLED')
        self.session=session;self.database=session.database;self.approval=copy.deepcopy(approval);self.raw_ddl_hashes={}
    def read(self,key,table=None,columns=None):return self.session.fetch(plan(key,self.database,table,columns),table)
    @contextmanager
    def consistent(self):
        self.session.begin_readonly()
        try:yield
        except BaseException:
            try:self.session.end_readonly()
            except BaseException:pass
            raise
        else:self.session.end_readonly()
    def identity(self):
        rows=self.read('identity');m.require(len(rows)==1,'MR09_IDENTITY_INCOMPLETE');row=rows[0]
        account=a.SOURCE_ACCOUNT if self.database==m.SOURCE else m.ACCOUNT
        m.require(row['database_name']==self.database and row['account']==account and row['server_uuid']==self.approval['server_uuid'],'MR09_ACTUAL_IDENTITY_MISMATCH')
        m.require(str(row['version']).split('-')[0]=='8.0.46','MR09_UNREVIEWED_MYSQL_VERSION')
        m.require(row['fk_checks']==row['unique_checks']==1 and {'STRICT_TRANS_TABLES','STRICT_ALL_TABLES'}.intersection(row['sql_mode'].split(',')),'MR09_SESSION_ENFORCEMENT_UNVERIFIED')
        tls={v['Variable_name']:v['Value'] for v in self.read('tls')}
        m.require(tls.get('Ssl_version') in ('TLSv1.2','TLSv1.3') and bool(tls.get('Ssl_cipher')),'MR09_TLS_UNVERIFIED')
        m.require(row['active_roles']=='NONE' and not row['mandatory_roles'],'MR09_ROLE_PRIVILEGES_UNVERIFIED')
        # Every role-grant line below is rejected, including inactive roles.
        # No mysql.* SELECT grant is added to the source reader for inspection.
        wanted=a.READ_RIGHTS if self.database==m.SOURCE else a.MIGRATOR_RIGHTS
        scope=self.database if row['partial_revokes'] else self.database.replace('_',r'\_');rights=set()
        user,host=account.split('@');recipient=r"(?:`"+user+r"`|'"+user+r"')@(?:`127\.0\.0\.1`|'127\.0\.0\.1')"
        for value in self.read('grants'):
            m.require(type(value) is dict and len(value)==1,'MR09_GRANT_CAPTURE_INCOMPLETE')
            text=next(iter(value.values()));m.require(type(text) is str,'MR09_GRANT_CAPTURE_INCOMPLETE')
            if re.fullmatch(r'GRANT USAGE ON \*\.\* TO '+recipient,text):continue
            match=re.fullmatch(r'GRANT (.*?) ON `(.*?)`\.\* TO '+recipient,text)
            m.require(match is not None and match[2]==scope and 'GRANT OPTION' not in text,'MR09_UNSAFE_GRANTS')
            rights.update(match[1].split(', '))
        m.require(rights==wanted,'MR09_UNSAFE_GRANTS')
        return row
    def revision(self):
        rows=self.read('revision');m.require(len(rows)==1 and rows[0]['version_num'] in m.CHAIN,'MR09_REVISION_UNVERIFIED');return rows[0]['version_num']
    def table(self,name,expected):
        rows=self.read('columns',name);m.require([r['ORDINAL_POSITION'] for r in rows]==list(range(1,len(rows)+1)),'MR09_COLUMN_ORDINAL_DRIFT')
        columns={};effective={}
        for row in rows:
            field=row['COLUMN_NAME'];m.require(field not in columns and not row['GENERATION_EXPRESSION'],'MR09_UNREVIEWED_COLUMN')
            m.require(row['IS_NULLABLE'] in ('YES','NO'),'MR09_NULLABILITY_UNAVAILABLE')
            typ=c.type_sql(row['COLUMN_TYPE']);extra=row['EXTRA'].lower();m.require(extra in ('','auto_increment','default_generated'),'MR09_UNREVIEWED_COLUMN_EXTRA')
            default=row['COLUMN_DEFAULT']
            if default is not None:
                default=c.default_sql(str(default),typ) if typ['family'] in ('DATETIME','DECIMAL','INT','BIGINT','SMALLINT','TINYINT') else {'kind':'literal','value':str(default)}
            columns[field]=dict(type=typ,nullable=row['IS_NULLABLE']=='YES',server_default=default,autoincrement=extra=='auto_increment',charset=row['CHARACTER_SET_NAME'],collation=row['COLLATION_NAME'])
            effective[field]={'charset':row['CHARACTER_SET_NAME'],'collation':row['COLLATION_NAME']}
        keys=grouped(self.read('keys',name),'CONSTRAINT_NAME','ORDINAL_POSITION');primary=[];uniques=[]
        for key,parts in keys.items():
            kind=parts[0]['CONSTRAINT_TYPE'];m.require(all(p['CONSTRAINT_TYPE']==kind for p in parts),'MR09_KEY_DRIFT');names=[p['COLUMN_NAME'] for p in parts]
            if kind=='PRIMARY KEY':m.require(not primary,'MR09_DUPLICATE_PRIMARY');primary=names
            else:m.require(kind=='UNIQUE','MR09_UNKNOWN_KEY');uniques.append({'name':key,'columns':names})
        foreign=[]
        for key,parts in grouped(self.read('foreign_keys',name),'CONSTRAINT_NAME','ORDINAL_POSITION').items():
            first=parts[0]
            m.require(first['UPDATE_RULE'] in ('RESTRICT','NO ACTION','CASCADE','SET NULL') and first['DELETE_RULE'] in ('RESTRICT','NO ACTION','CASCADE','SET NULL'),'MR09_FK_ACTION_UNAVAILABLE')
            m.require(all(p['REFERENCED_TABLE_SCHEMA']==self.database and (p['REFERENCED_TABLE_NAME'],p['UPDATE_RULE'],p['DELETE_RULE'])==(first['REFERENCED_TABLE_NAME'],first['UPDATE_RULE'],first['DELETE_RULE']) for p in parts),'MR09_CROSS_SCHEMA_OR_INCONSISTENT_FK')
            foreign.append(dict(name=key,columns=[p['COLUMN_NAME'] for p in parts],referred_table=first['REFERENCED_TABLE_NAME'],referred_columns=[p['REFERENCED_COLUMN_NAME'] for p in parts],ondelete=c.action(first['DELETE_RULE']),onupdate=c.action(first['UPDATE_RULE'])))
        check_rows=self.read('checks',name);check_values=[dict(name=r['CONSTRAINT_NAME'],definition=c.check_key(r['CHECK_CLAUSE'],representation='mysql8_information_schema'),enforced=r['ENFORCED']=='YES') for r in check_rows]
        m.require(len({r['name'] for r in check_values})==len(check_values),'MR09_DUPLICATE_CHECK')
        indexes=[];physical=[];explicit={i['name']:i for i in expected['indexes']}
        for key,parts in grouped(self.read('indexes',name),'INDEX_NAME','SEQ_IN_INDEX').items():
            m.require(all(p['INDEX_TYPE']=='BTREE' and p['SUB_PART'] is None and p['EXPRESSION'] is None and p['COLLATION']=='A' and p['IS_VISIBLE']=='YES' and p['NON_UNIQUE']==parts[0]['NON_UNIQUE'] for p in parts),'MR09_UNREVIEWED_INDEX')
            item={'name':key,'columns':[p['COLUMN_NAME'] for p in parts],'unique':parts[0]['NON_UNIQUE']==0};physical.append(item)
            if key=='PRIMARY':m.require(item['unique'] and item['columns']==primary,'MR09_PRIMARY_INDEX_DRIFT');continue
            if key in explicit:indexes.append(item);continue
            if item['unique'] and any(u['name']==key and u['columns']==item['columns'] for u in uniques):continue
            indexes.append(item)
        m.require(not primary or any(i['name']=='PRIMARY' for i in physical),'MR09_PRIMARY_INDEX_MISSING')
        # MySQL reports an explicit UNIQUE INDEX as both an index and a UNIQUE
        # constraint. Preserve physical evidence; classify only exact duplicates.
        uniques=[u for u in uniques if not (u['name'] in explicit and explicit[u['name']]['unique'] and explicit[u['name']]['columns']==u['columns'])]
        ddl=self.read('ddl',name);m.require(len(ddl)==1 and type(ddl[0].get('Create Table')) is str and bool(ddl[0]['Create Table']),'MR09_DDL_UNAVAILABLE')
        self.raw_ddl_hashes[name]=hashlib.sha256(ddl[0]['Create Table'].encode()).hexdigest().upper()
        return dict(columns=columns,primary_key=primary,foreign_keys=foreign,unique_constraints=uniques,checks=check_values,indexes=indexes),effective,physical
    def capture_stage(self,contract,revision):
        if not self.session.in_snapshot:
            with self.consistent():return self.capture_stage(contract,revision)
        self.identity();m.require(self.revision()==revision,'MR09_WRONG_STAGE_REVISION')
        tables=self.read('tables');m.require(len({r['TABLE_NAME'] for r in tables})==len(tables) and {r['TABLE_NAME'] for r in tables}==set(contract['tables']),'MR09_COMPLETE_TABLE_INVENTORY_MISMATCH')
        m.require(all(r['TABLE_TYPE']=='BASE TABLE' for r in tables) and self.read('routines')==[] and self.read('events')==[],'MR09_UNEXPECTED_STORED_OBJECT')
        collations={r['COLLATION_NAME']:r['CHARACTER_SET_NAME'] for r in self.read('collations')};observed={};physical={};effective={}
        for table in tables:
            name=table['TABLE_NAME'];wanted=contract['tables'][name];actual,effective[name],physical[name]=self.table(name,wanted)
            m.require(table['TABLE_COLLATION'] in collations,'MR09_UNKNOWN_TABLE_COLLATION')
            actual['options']={'engine':{'value':table['ENGINE']},'charset':{'value':collations[table['TABLE_COLLATION']]},'collation':{'value':table['TABLE_COLLATION']}}
            # Resolve only the EXPECTATION from declared inheritance and approved
            # runtime policy. Observed effective values above are never replaced.
            resolved=copy.deepcopy(wanted)
            for field,col in resolved['columns'].items():
                if col['type']['family'] not in ('VARCHAR','CHAR','TEXT'):continue
                if col['collation'] is not None:
                    m.require(col['collation'] in collations,'MR09_UNKNOWN_DECLARED_COLLATION');col['charset']=col['charset'] or collations[col['collation']]
                elif col['charset'] is not None:
                    m.require(col['charset'] in self.approval['charset_defaults'],'MR09_UNAPPROVED_CHARSET_DEFAULT');col['collation']=self.approval['charset_defaults'][col['charset']]
                    m.require(collations.get(col['collation'])==col['charset'],'MR09_CHARSET_POLICY_MISMATCH')
                else:
                    col['charset']=actual['options']['charset']['value'];col['collation']=table['TABLE_COLLATION']
            c.verify_table(actual,resolved);observed[name]=actual
        foreign_checked=0
        for table,value in observed.items():
            for fk in value['foreign_keys']:
                rows=self.session.fetch(orphan_plan(self.database,table,fk),table)
                m.require(len(rows)==1 and type(rows[0]['orphan_count']) is int and rows[0]['orphan_count']==0,'MR09_ORPHAN_RELATIONSHIP')
                foreign_checked+=1
        triggers=self.read('triggers');expected=contract['triggers'];m.require(len(triggers)==len(expected) and {r['TRIGGER_NAME'] for r in triggers}==set(expected),'MR09_COMPLETE_TRIGGER_INVENTORY_MISMATCH')
        for row in triggers:
            wanted=expected[row['TRIGGER_NAME']];context=self.approval['trigger_context']
            m.require((row['EVENT_OBJECT_TABLE'],row['ACTION_TIMING'],row['EVENT_MANIPULATION'],row['ACTION_ORIENTATION'])==(wanted['table'],wanted['timing'],wanted['event'],'ROW') and row['ACTION_STATEMENT'].strip().rstrip(';')==wanted['body'].strip().rstrip(';'),'MR09_TRIGGER_DEFINITION_MISMATCH')
            m.require(row['DEFINER'] in context['definers'] and set(row['SQL_MODE'].split(','))==set(context['sql_mode'].split(',')) and all(row[field]==context[key] for field,key in [('CHARACTER_SET_CLIENT','character_set_client'),('COLLATION_CONNECTION','collation_connection'),('DATABASE_COLLATION','database_collation')]),'MR09_TRIGGER_CONTEXT_UNVERIFIED')
        return dict(revision=revision,tables=observed,triggers=triggers,physical_indexes=physical,effective_columns=effective,raw_ddl_sha256=copy.deepcopy(self.raw_ddl_hashes),foreign_keys_checked=foreign_checked,orphan_count=0)
    def count(self,table):
        rows=self.read('count',table);m.require(len(rows)==1 and type(rows[0]['row_count']) is int and rows[0]['row_count']>=0,'MR09_COUNT_UNVERIFIED');return rows[0]['row_count']
    def fingerprints(self,baseline,revision,*,include_driver_flags=True):
        m.require(self.session.in_snapshot,'MR09_CONSISTENT_SNAPSHOT_REQUIRED')
        self.identity()
        originals={}
        for table,expected in baseline['originals'].items():
            count=self.count(table);m.require(count<=a.MAX_ROWS,'MR09_FINGERPRINT_BOUND_EXCEEDED')
            columns=expected['projection_columns'];values=self.read('rows',table,columns);observed=a.fingerprint(values,columns)
            m.require(observed['row_count']==count and count==self.count(table),'MR09_COUNT_CONTENT_RACE')
            originals[table]=dict(**observed,projection_columns=columns)
        if not include_driver_flags:return {'originals':originals}
        flags={};columns=['user_id','approval_status']+(['legacy_document_exempt'] if revision!=m.CHAIN[0] else [])
        for row in self.read('rows','driver_profiles',columns):
            m.require(type(row['user_id']) is int and row['approval_status'] in ('approved','pending','rejected'),'MR09_DRIVER_BASELINE_INVALID')
            key=m.digest(['driver-identity-v1',row['user_id']]);m.require(key not in flags,'MR09_DUPLICATE_DRIVER')
            if revision==m.CHAIN[0]:flags[key]=row['approval_status']=='approved'
            else:
                m.require(type(row['legacy_document_exempt']) in (int,bool) and row['legacy_document_exempt'] in (0,1),'MR09_EXEMPTION_INVALID');flags[key]=bool(row['legacy_document_exempt'])
        m.require(len(flags)==self.count('driver_profiles'),'MR09_DRIVER_COUNT_INVALID')
        return dict(originals=originals,driver_approval_flags=flags)
    def partial(self):
        self.identity();tables=self.read('tables');triggers=self.read('triggers')
        try:revisions=[r['version_num'] for r in self.read('revision')]
        except BaseException:revisions=[]
        safe_revisions=[r if type(r) is str and re.fullmatch('[a-f0-9]{12}',r) else 'UNVERIFIED_VALUE' for r in revisions]
        observed={};unavailable=[]
        for table in tables:
            name=table['TABLE_NAME']
            if name not in m.names_at(m.CHAIN[-1]):unavailable.append(name);continue
            observed[name]={}
            for key in ('columns','keys','foreign_keys','checks','indexes','ddl'):
                try:observed[name][key]=hashlib.sha256(e.MockConsistentSnapshot._bytes(self.read(key,name))).hexdigest().upper()
                except BaseException:unavailable.append(name+':'+key)
        return dict(tables=sorted(t['TABLE_NAME'] for t in tables),triggers=sorted(t['TRIGGER_NAME'] for t in triggers),revision=revisions[0] if len(revisions)==1 and revisions[0] in m.CHAIN else None,observed_revision_values=safe_revisions,schema_sha256=m.digest({'tables':tables,'triggers':triggers,'objects':observed}),object_hashes=observed,unavailable=unavailable)

@dataclass(frozen=True)
class StagePlan:
    database:str
    account:str
    previous:str
    target:str

def stage_plan(database,account,previous,target):
    m.target_guard(database,account);m.require((previous,target) in tuple(zip(m.CHAIN,m.CHAIN[1:])),'MR09_UNAPPROVED_TRANSITION')
    return StagePlan(database,account,previous,target)

class MockStageExecutor:
    def __init__(self,session,states):
        m.require(type(session) is MockMySQLSession and session.database==m.TARGET and session.account==m.ACCOUNT,'MR09_EXECUTION_SCOPE_REJECTED')
        a.fixture_data(states);self.session=session;self.states=copy.deepcopy(states);self.attempts=[];self.failed=False;self.fail_after_apply=False
    def execute(self,request):
        m.require(type(request) is StagePlan and request==stage_plan(request.database,request.account,request.previous,request.target),'MR09_INVALID_STAGE_PLAN')
        m.require(not self.failed and not self.session.in_snapshot and request.target not in self.attempts,'MR09_STAGE_REPLAY_OR_FAILED')
        m.require(self.session.results['revision']==[{'version_num':request.previous}],'MR09_WRONG_STAGE_REVISION')
        next_state=self.states[request.target]
        m.require(next_state['identity']==self.session.results['identity'] and next_state['grants']==self.session.results['grants'],'MR09_STAGE_IDENTITY_CHANGED')
        self.attempts.append(request.target);self.session.results=copy.deepcopy(next_state)
        if self.fail_after_apply:self.failed=True;raise m.GuardFailure('MR09_PARTIAL_MIGRATION_FAILURE')

class MockDBAObservations:
    """Issuer-bound detailed freeze observations; MOCK trust only, never PKI."""
    def __init__(self,authority):
        m.require(type(authority) is e.MockAttestationAuthority,'MR09_REAL_TRUST_DISABLED')
        self.authority=authority;self.records={}
    def register(self,envelope,observation):
        token=envelope['token'];payload=e.canonical(envelope['payload'])
        m.require(self.authority._issued.get(token)==payload,'MR09_DBA_OBSERVATION_UNTRUSTED')
        a.fixture_data(observation);self.records[token]=(payload,e.canonical(observation))
    def verify(self,envelope,approval):
        token=envelope['token'];payload=e.canonical(envelope['payload'])
        m.require(token in self.records and self.records[token][0]==payload,'MR09_DBA_OBSERVATION_UNTRUSTED')
        observed=json.loads(self.records[token][1])
        expected=dict(server_uuid=approval['server_uuid'],source=m.SOURCE,scratch=m.TARGET,unexplained_sessions=0,transactions=0,data_locks=0,metadata_locks=0,ddl=0,enabled_events=0,replication_appliers=0,writer_freeze=True,ddl_freeze=True)
        m.require(observed==expected,'MR09_WRITER_DDL_GATE_FAILED')

# Exact code/message allowlists: never serialize arbitrary exception text.
SAFE_FAILURE_CODES=frozenset({
    'MR09_ACTUAL_IDENTITY_MISMATCH','MR09_TLS_UNVERIFIED','MR09_UNSAFE_GRANTS',
    'MR09_ROLE_PRIVILEGES_UNVERIFIED','MR09_FINANCIAL_PRESERVATION_MISMATCH',
    'MR09_COMPLETE_TABLE_INVENTORY_MISMATCH','MR09_COMPLETE_TRIGGER_INVENTORY_MISMATCH',
    'MR09_TRIGGER_DEFINITION_MISMATCH','MR09_TRIGGER_CONTEXT_UNVERIFIED',
    'MR09_ORPHAN_RELATIONSHIP','MR09_WRONG_STAGE_REVISION','MR09_PARTIAL_MIGRATION_FAILURE',
    'MR09_CANONICAL_SOURCE_DRIFT','MR09_FRESH_DBA_EVIDENCE_REQUIRED',
    'MR09_WRITER_DDL_GATE_FAILED','MR09_NEW_TABLE_NOT_EMPTY','MR09_HISTORICAL_ADDRESS_CHANGED',
    'MR11_INVALID_CLOCK','STALE_DBA_EVIDENCE','REPLAYED_DBA_EVIDENCE',
    'UNTRUSTED_DBA_EVIDENCE','DBA_SCOPE_OR_SERVER_MISMATCH','EVIDENCE_BYTES_CHANGED',
})
SAFE_SCHEMA_MESSAGES=frozenset({'Column inventory mismatch','Primary key mismatch',
    'foreign_keys mismatch','unique_constraints mismatch','checks mismatch',
    'Table options mismatch','Explicit index mismatch','Missing explicit index',
    'Unexpected supporting index','Missing FK supporting index','Named object mismatch'})
SAFE_FAILURE_PHASES=frozenset({'DBA_GATE','FINAL_DBA_GATE','SOURCE_CAPTURE',
    'SCRATCH_CAPTURE','STAGE_EXECUTION','EVIDENCE_COMPLETION'})
def safe_failure_diagnostic(error,phase):
    code='MR09_REDACTED_OPERATION_FAILURE'
    if isinstance(error,m.GuardFailure) and error.code in SAFE_FAILURE_CODES:code=error.code
    elif isinstance(error,e.EvidenceError) and str(error) in SAFE_FAILURE_CODES:code=str(error)
    elif type(error) is ValueError and (str(error) in SAFE_SCHEMA_MESSAGES or str(error).startswith('Column definition mismatch: ')):
        code='MR11_SCHEMA_COMPARISON_FAILED'
    return dict(status='STOP_PRESERVE_NO_RETRY',original_code=code,
                phase=phase if phase in SAFE_FAILURE_PHASES else 'UNCLASSIFIED_PHASE')

class GuardedAdapter:
    """Future-stage orchestration using real inspection plans but MOCK transport.

    Neither arbitrary connections nor caller-supplied execution callbacks can be
    injected. Every public real connection/execution method remains disabled.
    """
    def __init__(self,*,source,scratch,executor,manifest_path,manifest_sha256,backup_path,source_fingerprint,authority,envelopes,clock,sink,observations):
        m.require(type(source) is MockMySQLSession and type(scratch) is MockMySQLSession and type(executor) is MockStageExecutor and executor.session is scratch,'MR09_REAL_TRANSPORT_DISABLED')
        m.require(source.database==m.SOURCE and source.account==a.SOURCE_ACCOUNT and scratch.database==m.TARGET and scratch.account==m.ACCOUNT,'MR09_ADAPTER_BINDING_REJECTED')
        m.require(type(authority) is e.MockAttestationAuthority and type(sink) is e.OfflineEvidenceSink,'MR09_REAL_TRUST_OR_SINK_DISABLED')
        m.require(type(observations) is MockDBAObservations and observations.authority is authority,'MR09_DBA_OBSERVATION_UNTRUSTED')
        self.observations=observations
        self.source=source;self.scratch=scratch;self.executor=executor;self.authority=authority;self.envelopes=copy.deepcopy(envelopes);self.clock=clock;self.sink=sink;self.phase="INITIALIZATION"
        m.require(callable(clock),"MR11_CLOCK_REQUIRED")
        self.manifest=m.load_approved(manifest_path,manifest_sha256);self.backup_path=Path(backup_path);self.failed=False;self.started=False
        self.evidence=e.issue(manifest_path,manifest_sha256,backup_path,self.manifest['backup_sha256'],source_fingerprint)
        self.contract=m.load_approved(CONTRACT,self.manifest['canonical_sha256'])
        m.require(self.contract==c.build(),'MR09_CANONICAL_SOURCE_DRIFT')
        m.require(self.contract.get('format')=='mr07-canonical-source-v1' and self.contract.get('head_model_parity',{}).get('differences')==[],'MR09_STATIC_ACCEPTANCE_REQUIRED')
        self._validate_approval(source_fingerprint)
        self.used_dba_ids=[]
        self.source_inspector=MySQLInspector(source,self.manifest);self.scratch_inspector=MySQLInspector(scratch,self.manifest)
    def _validate_approval(self,source_fingerprint):
        value=self.manifest;m.target_guard(value['target'],value['account']);approval=value['dba_approval']
        m.require(type(value['server_uuid']) is str and bool(value['server_uuid']),'MR09_SERVER_APPROVAL_REQUIRED')
        m.require(value['source']=={'database':m.SOURCE,'account':a.SOURCE_ACCOUNT,'revision':m.CHAIN[0]} and value['source_fingerprint']==source_fingerprint,'MR09_SOURCE_APPROVAL_MISMATCH')
        m.require(value['features']==dict.fromkeys(m.FEATURES,False) and value['revision_sequence']==list(m.CHAIN),'MR09_APPROVAL_SCOPE_MISMATCH')
        m.require(value['adapter_sha256']==m.file_hash(Path(__file__)) and value['fingerprint_algorithm']==a.ALGORITHM,'MR09_ADAPTER_PROVENANCE_MISMATCH')
        m.require(value['server_uuid']==approval['server_uuid'] and (approval['source'],approval['scratch'],approval['source_account'],approval['scratch_account'],approval['source_scope'],approval['scratch_scope'])==(m.SOURCE,m.TARGET,a.SOURCE_ACCOUNT,m.ACCOUNT,'SELECT_ONLY','EXACT_SCRATCH_MIGRATOR'),'MR09_DBA_APPROVAL_MISMATCH')
        baseline=value['baseline'];m.require(set(baseline)=={'originals','driver_approval_flags'} and set(baseline['originals'])==m.names_at(m.CHAIN[0])-{'alembic_version'} and m.digest(baseline)==source_fingerprint,'MR09_INCOMPLETE_APPROVED_BASELINE')
        m.require(value['trigger_context']['definers']==[m.ACCOUNT],'MR09_UNAPPROVED_TRIGGER_DEFINER')
        for table,entry in baseline['originals'].items():
            m.require(type(entry['row_count']) is int and entry['row_count']>=0 and m.hexhash(entry['content_sha256']),'MR09_INVALID_APPROVED_FINGERPRINT')
            m.require(set(entry['projection_columns'])==set(self.contract['stages'][m.CHAIN[0]]['tables'][table]['columns']) and len(entry['projection_columns'])==len(set(entry['projection_columns'])),'MR09_APPROVED_PROJECTION_MISMATCH')
    def gate(self):
        m.require(not self.failed,'MR09_FAILED_ATTEMPT_LATCHED')
        e.revalidate(self.evidence,self.manifest)
        m.require(m.file_hash(CONTRACT)==self.manifest['canonical_sha256'] and self.contract==c.build() and m.file_hash(Path(__file__))==self.manifest['adapter_sha256'],'MR09_CANONICAL_SOURCE_DRIFT')
        m.require(self.envelopes,'MR09_FRESH_DBA_EVIDENCE_REQUIRED')
        envelope=self.envelopes.pop(0)
        current=self.clock()
        m.require(type(current) in (int,float) and current==current and abs(current)!=float('inf'),'MR11_INVALID_CLOCK')
        receipt=self.authority.verify(envelope,self.manifest['dba_approval'],now=current)
        self.observations.verify(envelope,self.manifest['dba_approval'])
        self.used_dba_ids.append(e.receipt_payload(receipt)['evidence_id'])
        self.source_inspector.identity();self.scratch_inspector.identity()
    def _capture(self,inspector,revision):
        with inspector.consistent():
            observed=inspector.capture_stage(self.contract['stages'][revision],revision)
            financial=inspector.fingerprints(self.manifest['baseline'],revision)
            m.require(financial['originals']==self.manifest['baseline']['originals'] and financial['driver_approval_flags']==self.manifest['baseline']['driver_approval_flags'],'MR09_FINANCIAL_PRESERVATION_MISMATCH')
            for name in m.names_at(revision)-m.names_at(m.CHAIN[0]):m.require(inspector.count(name)==0,'MR09_NEW_TABLE_NOT_EMPTY')
            if revision==m.CHAIN[-1]:
                rows=inspector.read('rows','customer_addresses',['create_request_key','create_request_hash'])
                m.require(all(r['create_request_key'] is None and r['create_request_hash'] is None for r in rows),'MR09_HISTORICAL_ADDRESS_CHANGED')
            return observed,financial
    def inspect(self,revision):
        self.phase='DBA_GATE';self.gate()
        self.phase='SOURCE_CAPTURE';self._capture(self.source_inspector,m.CHAIN[0])
        self.phase='SCRATCH_CAPTURE';return self._capture(self.scratch_inspector,revision)
    def execute_one(self,previous,target,*,execute=False,confirm_target=None,authorization=None):
        m.require(execute is True and confirm_target==m.TARGET and authorization==m.TOKEN,'MR09_STAGE_NOT_AUTHORIZED')
        request=stage_plan(m.TARGET,m.ACCOUNT,previous,target)
        m.require(not self.started and not self.failed,'MR09_ATTEMPT_ALREADY_USED');self.started=True
        try:
            self.inspect(previous);self.phase='FINAL_DBA_GATE';self.gate()
            self.phase='SOURCE_CAPTURE';self._capture(self.source_inspector,m.CHAIN[0])
            self.phase='SCRATCH_CAPTURE';self._capture(self.scratch_inspector,previous)
            self.phase='STAGE_EXECUTION';self.executor.execute(request)
            result=self.inspect(target)
            self.phase='EVIDENCE_COMPLETION'
            self.sink._write('verified-'+target+'.json',{'status':'MR09_MOCK_STAGE_VERIFIED_NOT_LIVE','revision':target,'tables':sorted(result[0]['tables']),'raw_ddl_sha256':result[0]['raw_ddl_sha256'],'source_fingerprint':self.manifest['source_fingerprint'],'dba_evidence_ids':self.used_dba_ids})
            self.sink.complete()
            # One explicitly authorized stage, never upgrade head/whole chain.
            return result
        except BaseException as error:
            self.failed=True;self.executor.failed=True
            incomplete=False
            diagnostic=safe_failure_diagnostic(error,self.phase)
            try:self.sink._write('original-failure.json',diagnostic)
            except BaseException:incomplete=True
            try:self.sink.failure(revision=previous,code='DDL_STAGE_FAILED',observed_schema={})
            except BaseException:incomplete=True
            observation={};source_hash=original_hash=None
            try:observation=self.scratch_inspector.partial()
            except BaseException:pass
            try:
                with self.source_inspector.consistent():source_hash=m.digest(self.source_inspector.fingerprints(self.manifest['baseline'],m.CHAIN[0]))
            except BaseException:pass
            try:
                with self.scratch_inspector.consistent():original_hash=m.digest(self.scratch_inspector.fingerprints(self.manifest['baseline'],target,include_driver_flags=False)['originals'])
            except BaseException:pass
            summary={key:observation[key] for key in ('tables','triggers','schema_sha256') if key in observation}
            try:
                self.sink.failure(revision=observation.get('revision') or previous,code='UNEXPECTED_STATE',observed_schema=summary,source_fingerprint=source_hash,original_fingerprint=original_hash)
                self.sink._write('partial-observation.json',{'status':'PARTIAL_STATE_NOT_VERIFIED','observed':observation,'source_fingerprint':source_hash or 'UNAVAILABLE','original_fingerprint':original_hash or 'UNAVAILABLE'})
            except BaseException:incomplete=True
            code=error.code if isinstance(error,m.GuardFailure) else 'MR09_REDACTED_OPERATION_FAILURE'
            result=m.GuardFailure(code);result.evidence_status='INCOMPLETE' if incomplete else 'PRESERVED_PARTIAL_NOT_VERIFIED'
            raise result from None

if __name__=='__main__':
    print('MR09=SOURCE_AND_MOCKS_ONLY; REAL_EXECUTION_DISABLED; DATABASE_CONNECTIONS=0')
    raise SystemExit(2)

"""MR-09 independently authored fictional SQL result sets; no MySQL client.

The controller fixture replaces approved contract IO with an explicitly fictional
small-column contract across the allowlisted stage names. It is NOT evidence of
production MySQL parity. MR-07's unmodified full source contract is checked too.
"""
import copy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import tempfile
from unittest import TestCase,main
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('mr09_test_adapter',ROOT/'backend/scripts/mr09_mysql_adapter.py')
d=importlib.util.module_from_spec(spec)
# Dataclass resolves its defining module through sys.modules.
import sys
sys.modules[spec.name]=d;spec.loader.exec_module(d);m=d.m;a=d.a;c=d.c;e=d.e

def expected_table(kind):
    basic={'columns':{'id':"sa.Column('id',sa.BigInteger(),primary_key=True,autoincrement=True)"},'primary_keys':[{'name':None,'declaration':"sa.PrimaryKeyConstraint('id')"}], 'foreign_keys':[],'unique_constraints':[],'checks':[],'indexes':[],'options':[]}
    if kind=='framework':return c.framework_contract()['table']
    if kind=='driver':
        basic['columns']={'user_id':"sa.Column('user_id',sa.BigInteger(),primary_key=True,autoincrement=False)",'approval_status':"sa.Column('approval_status',sa.String(20),nullable=False)"};basic['primary_keys']=[{'name':None,'declaration':"sa.PrimaryKeyConstraint('user_id')"}]
    if kind=='driver-new':
        return dict(expected_table('driver'),columns=dict(expected_table('driver')['columns'],legacy_document_exempt={'type':c.type_sql('BOOL'),'nullable':False,'server_default':{'kind':'literal','value':'0'},'autoincrement':False,'charset':None,'collation':None,'client_default':None,'original':'fictional declaration'}))
    if kind=='sale':
        basic['columns'].update(customer_id="sa.Column('customer_id',sa.BigInteger(),nullable=False)",amount="sa.Column('amount',sa.Numeric(14,2),nullable=False,server_default=sa.text('0'))",status="sa.Column('status',sa.String(12),nullable=False,server_default='pending')")
        basic['foreign_keys']=[{'name':'fk_fixture_customer','declaration':'CONSTRAINT fk_fixture_customer FOREIGN KEY(customer_id) REFERENCES users (id) ON DELETE RESTRICT ON UPDATE RESTRICT'}]
        basic['checks']=[{'name':'ck_fixture_amount','declaration':'CONSTRAINT ck_fixture_amount CHECK (amount>=0)'}]
        basic['unique_constraints']=[{'name':'uq_fixture_id_customer','declaration':'CONSTRAINT uq_fixture_id_customer UNIQUE (id, customer_id)'}]
        basic['indexes']=[{'name':'ix_fixture_status','declaration':'CREATE INDEX ix_fixture_status ON orders (status)'}]
    if kind=='address-new':
        basic['columns'].update(create_request_key="sa.Column('create_request_key',sa.String(100),nullable=True)",create_request_hash="sa.Column('create_request_hash',sa.String(64),nullable=True)")
    if kind=='ascii':basic['columns']['digest']="sa.Column('digest',mysql.CHAR(64,charset='ascii'),nullable=False)"
    return c.canonical_table(basic)

def raw_column(name,typ,position,*,nullable='NO',default=None,extra='',charset=None,collation=None):
    return dict(COLUMN_NAME=name,ORDINAL_POSITION=position,COLUMN_TYPE=typ,IS_NULLABLE=nullable,COLUMN_DEFAULT=default,EXTRA=extra,CHARACTER_SET_NAME=charset,COLLATION_NAME=collation,GENERATION_EXPRESSION='')

def raw_index(name,columns,unique=False):
    return [dict(INDEX_NAME=name,SEQ_IN_INDEX=i+1,COLUMN_NAME=col,NON_UNIQUE=0 if unique else 1,INDEX_TYPE='BTREE',SUB_PART=None,COLLATION='A',IS_VISIBLE='YES',EXPRESSION=None) for i,col in enumerate(columns)]

def observed_results(revision,database=m.TARGET):
    """Observed rows are hand-authored independently from expected_table()."""
    account=a.SOURCE_ACCOUNT if database==m.SOURCE else m.ACCOUNT
    rights=a.READ_RIGHTS if database==m.SOURCE else a.MIGRATOR_RIGHTS;scope=database.replace('_',r'\_')
    result={'identity':[dict(database_name=database,account=account,server_uuid='fixture-server-uuid',fk_checks=1,unique_checks=1,sql_mode='STRICT_TRANS_TABLES',partial_revokes=0,mandatory_roles='',active_roles='NONE',version='8.0.46')],
        'tls':[{'Variable_name':'Ssl_version','Value':'TLSv1.3'},{'Variable_name':'Ssl_cipher','Value':'FICTIONAL_TLS_CIPHER'}],
        'grants':[{'Grants for '+account:'GRANT '+', '.join(sorted(rights))+' ON `'+scope+'`.* TO \''+account.split('@')[0]+"'@'127.0.0.1'"}],
        'revision':[{'version_num':revision}],'tables':[],'columns':{},'keys':{},'foreign_keys':{},'checks':{},'indexes':{},'ddl':{},'rows':{},'count':{},'orphans':{},'triggers':[], 'routines':[],'events':[],
        'collations':[{'COLLATION_NAME':'utf8mb4_unicode_ci','CHARACTER_SET_NAME':'utf8mb4'},{'COLLATION_NAME':'ascii_general_ci','CHARACTER_SET_NAME':'ascii'}]}
    for table in sorted(m.names_at(revision)):
        result['tables'].append(dict(TABLE_NAME=table,ENGINE='InnoDB',TABLE_COLLATION='utf8mb4_unicode_ci',TABLE_TYPE='BASE TABLE'))
        result['columns'][table]=[raw_column('id','bigint',1,extra='auto_increment')]
        result['rows'][table]=[{'id':1}] if table in m.names_at(m.CHAIN[0]) else []
        result['keys'][table]=[dict(CONSTRAINT_NAME='PRIMARY',CONSTRAINT_TYPE='PRIMARY KEY',COLUMN_NAME='id',ORDINAL_POSITION=1)]
        result['indexes'][table]=raw_index('PRIMARY',['id'],True)
        result['foreign_keys'][table]=[];result['checks'][table]=[];result['orphans'][table]={}
        result['ddl'][table]=[{'Table':table,'Create Table':'FICTIONAL SHOW CREATE '+revision+':'+table}]
    result['columns']['alembic_version']=[raw_column('version_num','varchar(32)',1,charset='utf8mb4',collation='utf8mb4_unicode_ci')]
    result['rows']['alembic_version']=[{'version_num':revision}];result['keys']['alembic_version']=[dict(CONSTRAINT_NAME='PRIMARY',CONSTRAINT_TYPE='PRIMARY KEY',COLUMN_NAME='version_num',ORDINAL_POSITION=1)];result['indexes']['alembic_version']=raw_index('PRIMARY',['version_num'],True)
    result['columns']['driver_profiles']=[raw_column('user_id','bigint',1),raw_column('approval_status','varchar(20)',2,charset='utf8mb4',collation='utf8mb4_unicode_ci')]
    result['rows']['driver_profiles']=[dict(user_id=41,approval_status='approved'),dict(user_id=42,approval_status='pending')]
    result['keys']['driver_profiles']=[dict(CONSTRAINT_NAME='PRIMARY',CONSTRAINT_TYPE='PRIMARY KEY',COLUMN_NAME='user_id',ORDINAL_POSITION=1)];result['indexes']['driver_profiles']=raw_index('PRIMARY',['user_id'],True)
    if revision!=m.CHAIN[0]:
        result['columns']['driver_profiles'].append(raw_column('legacy_document_exempt','tinyint(1)',3,default='0'))
        for row in result['rows']['driver_profiles']:row['legacy_document_exempt']=int(row['approval_status']=='approved')
    result['columns']['orders'].extend([raw_column('customer_id','bigint',2),raw_column('amount','decimal(14,2)',3,default='0'),raw_column('status','varchar(12)',4,default='pending',charset='utf8mb4',collation='utf8mb4_unicode_ci')])
    result['rows']['orders']=[dict(id=1,customer_id=1,amount=Decimal('10.01'),status='pending')]
    result['foreign_keys']['orders']=[dict(CONSTRAINT_NAME='fk_fixture_customer',COLUMN_NAME='customer_id',ORDINAL_POSITION=1,REFERENCED_TABLE_SCHEMA=database,REFERENCED_TABLE_NAME='users',REFERENCED_COLUMN_NAME='id',UPDATE_RULE='RESTRICT',DELETE_RULE='RESTRICT')]
    result['keys']['orders'] += [dict(CONSTRAINT_NAME='uq_fixture_id_customer',CONSTRAINT_TYPE='UNIQUE',COLUMN_NAME=col,ORDINAL_POSITION=i+1) for i,col in enumerate(['id','customer_id'])]
    result['indexes']['orders'] += raw_index('uq_fixture_id_customer',['id','customer_id'],True)+raw_index('ix_fixture_status',['status'])+raw_index('customer_id',['customer_id'])
    result['checks']['orders']=[dict(CONSTRAINT_NAME='ck_fixture_amount',CHECK_CLAUSE='(`amount` >= 0)',ENFORCED='YES')];result['orphans']['orders']={'fk_fixture_customer':[{'orphan_count':0}]}
    result['columns']['vehicle_documents'].append(raw_column('digest','char(64)',2,charset='ascii',collation='ascii_general_ci'));result['rows']['vehicle_documents'][0]['digest']='fictional-digest'
    if revision==m.CHAIN[-1]:
        result['columns']['customer_addresses'].extend([raw_column('create_request_key','varchar(100)',2,nullable='YES',charset='utf8mb4',collation='utf8mb4_unicode_ci'),raw_column('create_request_hash','varchar(64)',3,nullable='YES',charset='utf8mb4',collation='utf8mb4_unicode_ci')])
        for row in result['rows']['customer_addresses']:row.update(create_request_key=None,create_request_hash=None)
    position=m.CHAIN.index(revision);groups=[]
    if position>=2:groups.extend((t,'df_'+t,'Driver finance history is append-only') for t in ('order_fulfilment_charges','driver_earnings','driver_fee_collections','driver_settlement_events','driver_financial_audits'))
    if position>=3:groups.extend((t,'sd_'+t,'Support history is append-only') for t in ('support_case_messages','support_case_events','support_case_references'))
    if position>=4:groups.append(('order_delivery_addresses','ca_order_destination','Order destinations are immutable'))
    for table,prefix,message in groups:
        for event in ('UPDATE','DELETE'):
            result['triggers'].append(dict(TRIGGER_NAME=prefix+'_'+event.lower()+'_deny',EVENT_OBJECT_TABLE=table,ACTION_TIMING='BEFORE',EVENT_MANIPULATION=event,ACTION_ORIENTATION='ROW',ACTION_STATEMENT="SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '"+message+"'",DEFINER=m.ACCOUNT,SQL_MODE='STRICT_TRANS_TABLES',CHARACTER_SET_CLIENT='utf8mb4',COLLATION_CONNECTION='utf8mb4_unicode_ci',DATABASE_COLLATION='utf8mb4_unicode_ci'))
    for table,rows in result['rows'].items():result['count'][table]=[{'row_count':len(rows)}]
    return result

def fixture_contract():
    real=json.loads(d.CONTRACT.read_text(encoding='utf-8'));value={'format':'mr07-canonical-source-v1','head_model_parity':{'differences':[]},'stages':{}}
    for revision in m.CHAIN:
        tables={table:expected_table('basic') for table in m.names_at(revision)}
        tables['alembic_version']=expected_table('framework');tables['driver_profiles']=expected_table('driver-new' if revision!=m.CHAIN[0] else 'driver')
        tables['orders']=expected_table('sale');tables['vehicle_documents']=expected_table('ascii')
        if revision==m.CHAIN[-1]:tables['customer_addresses']=expected_table('address-new')
        value['stages'][revision]=dict(tables=tables,triggers=real['stages'][revision]['triggers'])
    return value

class AdapterTests(TestCase):
    def setUp(self):
        self.network=patch('socket.socket.connect',side_effect=AssertionError('NETWORK FORBIDDEN'));self.network.start();self.addCleanup(self.network.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.contract=fixture_contract();self.contract_path=Path(self.temp.name)/'fictional-contract.json';self.contract_path.write_text(json.dumps(self.contract),encoding='utf-8')
        self.patch_path=patch.object(d,'CONTRACT',self.contract_path);self.patch_path.start();self.addCleanup(self.patch_path.stop)
        self.patch_builder=patch.object(c,'build',return_value=self.contract);self.patch_builder.start();self.addCleanup(self.patch_builder.stop)
        self.backup=Path(self.temp.name)/'fictional.backup';self.backup.write_bytes(b'FICTIONAL NOT SQL')
        self.states={r:observed_results(r) for r in m.CHAIN}
        self.source=d.MockMySQLSession(m.SOURCE,a.SOURCE_ACCOUNT,observed_results(m.CHAIN[0],m.SOURCE));self.scratch=d.MockMySQLSession(m.TARGET,m.ACCOUNT,self.states[m.CHAIN[0]])
        original={}
        for table in m.names_at(m.CHAIN[0])-{'alembic_version'}:
            columns=list(self.contract['stages'][m.CHAIN[0]]['tables'][table]['columns'])
            original[table]=dict(**a.fingerprint(self.source.results['rows'][table],columns),projection_columns=columns)
        baseline=dict(originals=original,driver_approval_flags={m.digest(['driver-identity-v1',41]):True,m.digest(['driver-identity-v1',42]):False})
        approval=dict(server_uuid='fixture-server-uuid',source=m.SOURCE,scratch=m.TARGET,source_account=a.SOURCE_ACCOUNT,scratch_account=m.ACCOUNT,source_scope='SELECT_ONLY',scratch_scope='EXACT_SCRATCH_MIGRATOR',issuer='fictional-dba',max_age_seconds=120)
        self.manifest=dict(target=m.TARGET,account=m.ACCOUNT,source=dict(database=m.SOURCE,account=a.SOURCE_ACCOUNT,revision=m.CHAIN[0]),server_uuid='fixture-server-uuid',source_fingerprint=m.digest(baseline),baseline=baseline,backup_sha256=m.file_hash(self.backup),canonical_sha256=m.file_hash(self.contract_path),adapter_sha256=m.file_hash(ROOT/'backend/scripts/mr09_mysql_adapter.py'),fingerprint_algorithm=a.ALGORITHM,features=dict.fromkeys(m.FEATURES,False),revision_sequence=list(m.CHAIN),dba_approval=approval,charset_defaults={'ascii':'ascii_general_ci'},trigger_context=dict(definers=[m.ACCOUNT],sql_mode='STRICT_TRANS_TABLES',character_set_client='utf8mb4',collation_connection='utf8mb4_unicode_ci',database_collation='utf8mb4_unicode_ci'))
        self.path=Path(self.temp.name)/'fictional-manifest.json';self.save_manifest()
        self.authority=e.MockAttestationAuthority();self.envelopes=[self.authority.issue(dict(**{k:v for k,v in approval.items() if k!='max_age_seconds'},evidence_id='mr09-fixture-'+str(i),observed_at=1000,expires_at=1120,writer_freeze=True,ddl_freeze=True,trigger_definers_attested=True)) for i in range(16)]
        self.executor=d.MockStageExecutor(self.scratch,{r:self.states[r] for r in m.CHAIN[1:]})
        self.sink=e.OfflineEvidenceSink(self.temp.name,'mr05-test-'+'9'*16);self.adapter=self.make_adapter()
    def save_manifest(self):self.path.write_text(json.dumps(self.manifest),encoding='utf-8');self.approved=m.file_hash(self.path)
    def make_adapter(self):
        observations=d.MockDBAObservations(self.authority)
        for envelope in self.envelopes:observations.register(envelope,dict(server_uuid='fixture-server-uuid',source=m.SOURCE,scratch=m.TARGET,unexplained_sessions=0,transactions=0,data_locks=0,metadata_locks=0,ddl=0,enabled_events=0,replication_appliers=0,writer_freeze=True,ddl_freeze=True))
        return d.GuardedAdapter(source=self.source,scratch=self.scratch,executor=self.executor,manifest_path=self.path,manifest_sha256=self.approved,backup_path=self.backup,source_fingerprint=self.manifest['source_fingerprint'],authority=self.authority,envelopes=self.envelopes,clock=lambda:1000,sink=self.sink,observations=observations)
    def block(self,code,operation):
        with self.assertRaises(m.GuardFailure) as error:operation()
        self.assertEqual(error.exception.code,code)
    def inspect(self,revision=None):return self.adapter.inspect(revision or m.CHAIN[0])
    def execute(self,previous=None,target=None):return self.adapter.execute_one(previous or m.CHAIN[0],target or m.CHAIN[1],execute=True,confirm_target=m.TARGET,authorization=m.TOKEN)
    def test_full_baseline_raw_metadata_and_fingerprints(self):
        observed,financial=self.inspect();self.assertEqual(len(observed['tables']),33);self.assertEqual(observed['foreign_keys_checked'],1);self.assertEqual(financial,self.manifest['baseline'])
        self.assertEqual(observed['effective_columns']['vehicle_documents']['digest']['charset'],'ascii')
    def test_wrong_server_uuid(self):
        self.scratch.results['identity'][0]['server_uuid']='other';self.block('MR09_ACTUAL_IDENTITY_MISMATCH',self.inspect)
    def test_wrong_source_and_scratch_accounts(self):
        for session in (self.source,self.scratch):
            original=session.results['identity'][0]['account'];session.results['identity'][0]['account']='root@localhost'
            self.block('MR09_ACTUAL_IDENTITY_MISMATCH',self.inspect);session.results['identity'][0]['account']=original
    def test_no_default_or_source_destination_substitution(self):
        self.block('MR03_BINDING_REJECTED',lambda:d.MockMySQLSession(m.SOURCE,m.ACCOUNT,{}))
        self.block('MR09_EXECUTION_SCOPE_REJECTED',lambda:d.MockStageExecutor(self.source,{}))
    def test_missing_dba_evidence(self):
        self.adapter.envelopes=[];self.block('MR09_FRESH_DBA_EVIDENCE_REQUIRED',self.inspect)
    def test_stale_dba_evidence(self):
        self.adapter.clock=lambda:1200
        with self.assertRaises(e.EvidenceError):self.inspect()
    def test_detailed_writer_gate_is_not_replaced_by_boolean_attestation(self):
        envelope=self.adapter.envelopes[0]
        self.adapter.observations.register(envelope,dict(server_uuid='fixture-server-uuid',source=m.SOURCE,scratch=m.TARGET,unexplained_sessions=0,transactions=1,data_locks=0,metadata_locks=0,ddl=0,enabled_events=0,replication_appliers=0,writer_freeze=True,ddl_freeze=True))
        self.block('MR09_WRITER_DDL_GATE_FAILED',self.inspect);self.assertEqual(self.executor.attempts,[])
    def test_backup_mismatch(self):
        self.backup.write_bytes(b'CHANGED')
        with self.assertRaises(e.EvidenceError):self.inspect()
        self.assertEqual(self.executor.attempts,[])
    def test_contract_binding_rechecked_before_inspection(self):
        self.contract_path.write_text('{}',encoding='utf-8')
        self.block('MR09_CANONICAL_SOURCE_DRIFT',self.inspect)
        self.assertEqual(self.source.calls,[]);self.assertEqual(self.scratch.calls,[])
    def test_missing_and_extra_stage_table(self):
        self.scratch.results['tables'].pop();self.block('MR09_COMPLETE_TABLE_INVENTORY_MISMATCH',self.inspect)
        self.scratch.results=copy.deepcopy(self.states[m.CHAIN[0]]);self.scratch.results['tables'].append(dict(TABLE_NAME='unexpected',ENGINE='InnoDB',TABLE_COLLATION='utf8mb4_unicode_ci',TABLE_TYPE='BASE TABLE'))
        self.block('MR09_COMPLETE_TABLE_INVENTORY_MISMATCH',self.inspect)
    def test_missing_altered_unexpected_trigger(self):
        for variant in ('missing','body','extra'):
            self.scratch.results=copy.deepcopy(self.states[m.CHAIN[2]])
            if variant=='missing':self.scratch.results['triggers'].pop()
            elif variant=='extra':self.scratch.results['triggers'].append(dict(self.scratch.results['triggers'][0],TRIGGER_NAME='unexpected'))
            else:self.scratch.results['triggers'][0]['ACTION_STATEMENT']='SELECT 1'
            self.block('MR09_TRIGGER_DEFINITION_MISMATCH' if variant=='body' else 'MR09_COMPLETE_TRIGGER_INVENTORY_MISMATCH',lambda:self.inspect(m.CHAIN[2]))
    def test_wrong_trigger_definer_and_context(self):
        self.scratch.results=copy.deepcopy(self.states[m.CHAIN[2]]);self.scratch.results['triggers'][0]['DEFINER']='root@localhost'
        self.block('MR09_TRIGGER_CONTEXT_UNVERIFIED',lambda:self.inspect(m.CHAIN[2]))
    def test_incorrect_fk_and_check_enforcement(self):
        self.scratch.results['foreign_keys']['orders'][0]['DELETE_RULE']='CASCADE'
        with self.assertRaises(ValueError):self.inspect()
        self.scratch.results=copy.deepcopy(self.states[m.CHAIN[0]]);self.scratch.results['checks']['orders'][0]['ENFORCED']='NO'
        with self.assertRaises(ValueError):self.inspect()
    def test_wrong_inherited_table_and_column_options(self):
        self.scratch.results['tables'][0]['ENGINE']='MyISAM'
        with self.assertRaises(ValueError):self.inspect()
        self.scratch.results=copy.deepcopy(self.states[m.CHAIN[0]]);self.scratch.results['columns']['orders'][-1]['COLLATION_NAME']='ascii_general_ci';self.scratch.results['columns']['orders'][-1]['CHARACTER_SET_NAME']='ascii'
        with self.assertRaises(ValueError):self.inspect()
    def test_missing_framework_pk_is_rejected(self):
        self.scratch.results['keys']['alembic_version']=[];self.scratch.results['indexes']['alembic_version']=[]
        with self.assertRaises(ValueError):self.inspect()
    def test_orphan_is_rejected(self):
        self.scratch.results['orphans']['orders']['fk_fixture_customer'][0]['orphan_count']=1
        self.block('MR09_ORPHAN_RELATIONSHIP',self.inspect)
    def test_global_or_role_grants_rejected_without_extra_runtime_privileges(self):
        self.scratch.results['grants'].append({'grant':"GRANT SUPER ON *.* TO 'lankapex_mr02_rehearsal'@'127.0.0.1'"})
        self.block('MR09_UNSAFE_GRANTS',self.inspect)
        self.scratch.results['grants'].pop();self.scratch.results['grants'].append({'grant':"GRANT 'admin_role'@'%' TO 'lankapex_mr02_rehearsal'@'127.0.0.1'"})
        self.block('MR09_UNSAFE_GRANTS',self.inspect)
    def test_source_fingerprint_mismatch(self):
        self.source.results['rows']['orders'][0]['amount']=Decimal('99.99');self.block('MR09_FINANCIAL_PRESERVATION_MISMATCH',self.inspect)
    def test_source_change_at_final_gate_prevents_any_upgrade(self):
        original=self.adapter.gate;count=[0]
        def gate():
            original();count[0]+=1
            if count[0]==2:self.source.results['rows']['orders'][0]['amount']=Decimal('99.99')
        with patch.object(self.adapter,'gate',side_effect=gate):self.block('MR09_FINANCIAL_PRESERVATION_MISMATCH',self.execute)
        self.assertEqual(self.executor.attempts,[])
    def test_single_stage_success_records_durable_evidence(self):
        observed,financial=self.execute();self.assertEqual(len(observed['tables']),35);self.assertEqual(self.executor.attempts,[m.CHAIN[1]])
        self.assertEqual(self.sink.status(),'EVIDENCE_COMPLETE_NOT_MIGRATION_SUCCESS')
        self.block('MR09_ATTEMPT_ALREADY_USED',lambda:self.execute(m.CHAIN[1],m.CHAIN[2]))
    def test_partial_migration_failure_preserves_state_and_no_retry(self):
        self.executor.fail_after_apply=True;self.block('MR09_PARTIAL_MIGRATION_FAILURE',self.execute)
        self.assertEqual(self.scratch.results['revision'],[{'version_num':m.CHAIN[1]}]);self.assertEqual(self.executor.attempts,[m.CHAIN[1]])
        self.assertTrue(self.adapter.failed);self.assertEqual(self.sink.status(),'INCOMPLETE_EVIDENCE')
        records=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(self.sink.root.glob('failure-*.json'))]
        self.assertEqual(len(records),2);self.assertEqual(len(records[-1]['observed']['tables']),35)
    def test_evidence_io_failure_does_not_mask_original_failure_or_retry(self):
        self.executor.fail_after_apply=True
        with patch.object(self.sink,'failure',side_effect=OSError('FICTIONAL_PRIVATE_ERROR')):
            with self.assertRaises(m.GuardFailure) as error:self.execute()
        self.assertEqual(error.exception.code,'MR09_PARTIAL_MIGRATION_FAILURE');self.assertEqual(error.exception.evidence_status,'INCOMPLETE')
        self.assertNotIn('PRIVATE',str(error.exception));self.assertEqual(self.executor.attempts,[m.CHAIN[1]])
    def test_all_four_exact_transitions_and_no_head(self):
        for previous,target in zip(m.CHAIN,m.CHAIN[1:]):self.assertEqual(d.stage_plan(m.TARGET,m.ACCOUNT,previous,target).target,target)
        self.block('MR09_UNAPPROVED_TRANSITION',lambda:d.stage_plan(m.TARGET,m.ACCOUNT,m.CHAIN[0],'head'))
        self.block('MR09_UNAPPROVED_TRANSITION',lambda:d.stage_plan(m.TARGET,m.ACCOUNT,m.CHAIN[0],m.CHAIN[-1]))
    def test_real_transport_is_unconditionally_disabled(self):
        for method in ('connect','fetch','upgrade'):
            self.block('MR09_REAL_EXECUTION_DISABLED',lambda:getattr(d.DisabledRealTransport(),method)(password='fictional-secret'))
        self.block('MR09_REAL_TRANSPORT_DISABLED',lambda:d.MySQLInspector(object(),self.manifest))
    def test_consistent_capture_detects_same_count_mutation(self):
        inspector=self.adapter.scratch_inspector;original=inspector.table
        def changed(name,expected):
            value=original(name,expected)
            if name=='orders':self.scratch.results['rows']['orders'][0]['amount']=Decimal('55.00')
            return value
        # Preserve the first financial error; snapshot cleanup must not replace it.
        with patch.object(inspector,'table',side_effect=changed):self.block('MR09_FINANCIAL_PRESERVATION_MISMATCH',self.inspect)
        self.assertFalse(self.scratch.in_snapshot)
    def test_each_of_four_stages_can_execute_once_in_an_independent_mock_attempt(self):
        for index,(previous,target) in enumerate(zip(m.CHAIN,m.CHAIN[1:])):
            self.scratch.results=copy.deepcopy(self.states[previous]);self.executor=d.MockStageExecutor(self.scratch,{r:self.states[r] for r in m.CHAIN[1:]})
            self.authority=e.MockAttestationAuthority();approval=self.manifest['dba_approval']
            self.envelopes=[self.authority.issue(dict(**{k:v for k,v in approval.items() if k!='max_age_seconds'},evidence_id='independent-'+str(index)+'-'+str(i),observed_at=1000,expires_at=1120,writer_freeze=True,ddl_freeze=True,trigger_definers_attested=True)) for i in range(16)]
            self.sink=e.OfflineEvidenceSink(self.temp.name,'mr05-test-'+str(index)*16);self.adapter=self.make_adapter()
            observed,_=self.execute(previous,target)
            self.assertEqual(len(observed['tables']),m.COUNTS[index+1]);self.assertEqual(len(observed['triggers']),[0,10,16,18][index]);self.assertEqual(self.executor.attempts,[target])
    def test_partial_missing_revision_retains_observed_schema(self):
        self.executor.states[m.CHAIN[1]]['revision']=[];self.executor.fail_after_apply=True
        self.block('MR09_PARTIAL_MIGRATION_FAILURE',self.execute)
        value=json.loads((self.sink.root/'partial-observation.json').read_text(encoding='utf-8'))
        self.assertEqual(value['observed']['observed_revision_values'],[])
        self.assertEqual(len(value['observed']['tables']),35);self.assertIn('orders',value['observed']['object_hashes'])
    def test_explicit_unique_index_is_not_double_counted_as_a_unique_constraint(self):
        self.contract['stages'][m.CHAIN[0]]['tables']['users']['indexes']=[{'name':'ix_fixture_unique','columns':['id'],'unique':True}]
        for session in (self.source,self.scratch):
            session.results['keys']['users'].append(dict(CONSTRAINT_NAME='ix_fixture_unique',CONSTRAINT_TYPE='UNIQUE',COLUMN_NAME='id',ORDINAL_POSITION=1))
            session.results['indexes']['users']+=raw_index('ix_fixture_unique',['id'],True)
        self.contract_path.write_text(json.dumps(self.contract),encoding='utf-8');self.manifest['canonical_sha256']=m.file_hash(self.contract_path);self.save_manifest();self.adapter=self.make_adapter()
        observed,_=self.inspect()
        self.assertEqual(observed['tables']['users']['unique_constraints'],[])
        self.assertEqual(observed['tables']['users']['indexes'],[{'name':'ix_fixture_unique','columns':['id'],'unique':True}])
        self.assertEqual(len(observed['physical_indexes']['users']),2)
    def test_unapproved_sql_and_real_execution_scope_are_rejected(self):
        request=d.ReadPlan('tables','DROP DATABASE lankapex_viva_db',())
        self.block('MR09_INSPECTION_PLAN_CHANGED',lambda:self.scratch.fetch(request))
        self.block('UNAPPROVED_DATABASE',lambda:d.stage_plan(m.SOURCE,m.ACCOUNT,m.CHAIN[0],m.CHAIN[1]))
    def test_missing_authorization_does_not_consume_an_attempt(self):
        self.block('MR09_STAGE_NOT_AUTHORIZED',lambda:self.adapter.execute_one(m.CHAIN[0],m.CHAIN[1]))
        self.assertFalse(self.adapter.started);self.assertEqual(self.executor.attempts,[])
    def test_mr11_expiration_between_preflight_and_execution(self):
        ticks=iter([1000,1120]);self.adapter.clock=lambda:next(ticks)
        self.block('MR09_REDACTED_OPERATION_FAILURE',self.execute)
        self.assertEqual(self.executor.attempts,[]);self.assertTrue(self.adapter.failed)
        record=json.loads((self.sink.root/'original-failure.json').read_text())
        self.assertEqual(record['original_code'],'STALE_DBA_EVIDENCE');self.assertEqual(record['phase'],'FINAL_DBA_GATE')
    def test_mr11_clock_boundaries(self):
        self.adapter.clock=lambda:1119.999;self.inspect()
        self.adapter.clock=lambda:1120
        with self.assertRaises(e.EvidenceError):self.inspect()
        self.adapter.clock=lambda:999.999
        with self.assertRaises(e.EvidenceError):self.inspect()
    def test_mr11_invalid_clock_fails_closed(self):
        for value in (float('nan'),float('inf'),True,'1000'):
            self.adapter.clock=lambda:value
            self.block('MR11_INVALID_CLOCK',self.inspect)
    def test_mr11_persisted_identity_authentication_guard(self):
        self.scratch.results['identity'][0]['account']='wrong@localhost'
        self.block('MR09_ACTUAL_IDENTITY_MISMATCH',self.execute)
        record=json.loads((self.sink.root/'original-failure.json').read_text())
        self.assertEqual(record['original_code'],'MR09_ACTUAL_IDENTITY_MISMATCH');self.assertEqual(record['phase'],'DBA_GATE')
        self.assertTrue(self.executor.failed)
    def test_mr11_persisted_preservation_failure(self):
        self.source.results['rows']['orders'][0]['amount']=Decimal('99.99')
        self.block('MR09_FINANCIAL_PRESERVATION_MISMATCH',self.execute)
        record=json.loads((self.sink.root/'original-failure.json').read_text())
        self.assertEqual(record['original_code'],'MR09_FINANCIAL_PRESERVATION_MISMATCH');self.assertEqual(record['phase'],'SOURCE_CAPTURE')
        partial=json.loads((self.sink.root/'partial-observation.json').read_text())
        self.assertNotEqual(partial['source_fingerprint'],'UNAVAILABLE')
    def test_mr11_persisted_schema_failure(self):
        self.scratch.results['checks']['orders'][0]['ENFORCED']='NO'
        self.block('MR09_REDACTED_OPERATION_FAILURE',self.execute)
        record=json.loads((self.sink.root/'original-failure.json').read_text())
        self.assertEqual(record['original_code'],'MR11_SCHEMA_COMPARISON_FAILED');self.assertEqual(record['phase'],'SCRATCH_CAPTURE')
    def test_mr11_sensitive_errors_are_not_persisted(self):
        for error in (RuntimeError('password=fictional SQL values'),m.GuardFailure('SECRET_CODE'),ValueError('private exception')):
            record=d.safe_failure_diagnostic(error,'private phase')
            self.assertEqual(record['original_code'],'MR09_REDACTED_OPERATION_FAILURE');self.assertEqual(record['phase'],'UNCLASSIFIED_PHASE')
            self.assertNotIn('private',json.dumps(record))
    def test_mr11_partial_failure_retains_original_code_and_phase(self):
        self.executor.fail_after_apply=True;self.block('MR09_PARTIAL_MIGRATION_FAILURE',self.execute)
        record=json.loads((self.sink.root/'original-failure.json').read_text())
        self.assertEqual(record['original_code'],'MR09_PARTIAL_MIGRATION_FAILURE');self.assertEqual(record['phase'],'STAGE_EXECUTION')
        self.assertTrue((self.sink.root/'original-failure.json.sha256').exists())
        self.block('MR09_ATTEMPT_ALREADY_USED',self.execute)
    def test_real_saved_contract_not_replaced_by_fictional_spec(self):
        # Stop the unit-test IO substitution for this source-only check.
        self.patch_builder.stop();self.patch_path.stop()
        value=json.loads(d.CONTRACT.read_text(encoding='utf-8'));self.assertEqual(value,c.build())
        self.assertEqual([len(s['tables']) for s in value['stages'].values()],[33,35,40,44,45])

if __name__=='__main__':main()

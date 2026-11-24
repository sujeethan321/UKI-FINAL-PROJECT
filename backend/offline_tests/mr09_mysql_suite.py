"""MR-09 raw MySQL-shaped fixtures; no real SQL, connectors or migration calls."""
import copy,hashlib,importlib.util,json
from pathlib import Path
import tempfile
from unittest import TestCase,main
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('mr09_under_test',ROOT/'backend/scripts/mr09_mysql_adapter.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r);m=r.m;a=r.a;e=r.e

def policy():return dict(server_uuid='fictional-server',source=m.SOURCE,scratch=m.TARGET,source_account=a.SOURCE_ACCOUNT,scratch_account=m.ACCOUNT,source_scope='SELECT_ONLY',scratch_scope='EXACT_SCRATCH_MIGRATOR',issuer='fictional-dba',max_age_seconds=120,trigger_definer=m.ACCOUNT,trigger_context={'sql_mode':'STRICT_TRANS_TABLES','character_set_client':'utf8mb4','collation_connection':'utf8mb4_unicode_ci','database_collation':'utf8mb4_unicode_ci'})

def expectation(revision):
    # Hand-authored toy schema ONLY for exercising protocol boundaries on the
    # approved name inventory. It is NOT a project schema or rehearsal baseline.
    tables={}
    for name in sorted(m.names_at(revision)):
        field='version_num' if name=='alembic_version' else 'id'
        typ={'family':'VARCHAR','unsigned':False,'length':32} if name=='alembic_version' else {'family':'BIGINT','unsigned':False}
        tables[name]={'columns':{field:{'type':typ,'nullable':False,'server_default':None,'autoincrement':False,'charset':None,'collation':None}},'primary_key':[field],'foreign_keys':[],'unique_constraints':[],'checks':[],'indexes':[],
            'options':{k:{'value':v,'origin':'declared','required_runtime_policy':v} for k,v in {'engine':'InnoDB','charset':'utf8mb4','collation':'utf8mb4_unicode_ci'}.items()},'permitted_implicit_indexes':[]}
    tables['driver_profiles']['columns']={'user_id':{'type':{'family':'BIGINT','unsigned':False},'nullable':False,'server_default':None,'autoincrement':False,'charset':None,'collation':None},'approval_status':{'type':{'family':'VARCHAR','unsigned':False,'length':20},'nullable':False,'server_default':{'kind':'literal','value':'pending'},'autoincrement':False,'charset':None,'collation':None}}
    tables['driver_profiles']['primary_key']=['user_id']
    if revision!=m.CHAIN[0]:tables['driver_profiles']['columns']['legacy_document_exempt']={'type':{'family':'TINYINT','unsigned':False,'display_width':1},'nullable':False,'server_default':{'kind':'literal','value':'0'},'autoincrement':False,'charset':None,'collation':None}
    if revision==m.CHAIN[-1]:
        for field,length in (('create_request_key',100),('create_request_hash',64)):
            tables['customer_addresses']['columns'][field]={'type':{'family':'VARCHAR','unsigned':False,'length':length},'nullable':True,'server_default':None,'autoincrement':False,'charset':None,'collation':'utf8mb4_bin' if field=='create_request_key' else None}
    tables['orders']['foreign_keys']=[{'name':None,'columns':['id'],'referred_table':'users','referred_columns':['id'],'ondelete':'RESTRICT','onupdate':'RESTRICT'}]
    tables['orders']['checks']=[{'name':'ck_fixture','definition':['>=',['identifier','id'],['number','0']],'enforced':True}]
    triggers={name:{'table':table,'timing':timing,'event':event,'body':"SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '"+message+"'"} for name,(table,timing,event,message) in m.trigger_specs(revision).items()}
    return {'tables':tables,'triggers':triggers}

def raw_rows(revision,database=m.TARGET,account=m.ACCOUNT,role='migration'):
    # Independently authored raw INFORMATION_SCHEMA responses, not converted
    # from expectation() or the canonical contract builder.
    rights=a.MIGRATOR_RIGHTS if role=='migration' else a.READ_RIGHTS
    username=account.split('@')[0];scope=database.replace('_',r'\_')
    value={'identity':[{'db':database,'account':account,'server_uuid':'fictional-server','fk_checks':1,'uq_checks':1,'sql_mode':'STRICT_TRANS_TABLES','active_role':'NONE','mandatory_roles':'','partial_revokes':0}],
        'tls':[{'Variable_name':'Ssl_version','Value':'TLSv1.3'},{'Variable_name':'Ssl_cipher','Value':'fictional-cipher'}],
        'grants':[{'grant':"GRANT "+', '.join(sorted(rights))+" ON `"+scope+"`.* TO `"+username+"`@`127.0.0.1`"}],
        'revision':[{'version_num':revision}],'tables':[],'columns':[],'constraints':[],'keys':[],'references':[],'checks':[],'indexes':[],'triggers':[],'routines':[],'events':[],
        'collations':[{'COLLATION_NAME':'utf8mb4_unicode_ci','CHARACTER_SET_NAME':'utf8mb4'},{'COLLATION_NAME':'utf8mb4_bin','CHARACTER_SET_NAME':'utf8mb4'},{'COLLATION_NAME':'ascii_general_ci','CHARACTER_SET_NAME':'ascii'}],
        'charsets':[{'CHARACTER_SET_NAME':'utf8mb4','DEFAULT_COLLATE_NAME':'utf8mb4_unicode_ci'},{'CHARACTER_SET_NAME':'ascii','DEFAULT_COLLATE_NAME':'ascii_general_ci'}]}
    for table in sorted(m.names_at(revision)):
        framework=table=='alembic_version';field='version_num' if framework else 'user_id' if table=='driver_profiles' else 'id'
        value['tables'].append({'TABLE_NAME':table,'TABLE_TYPE':'BASE TABLE','ENGINE':'InnoDB','TABLE_COLLATION':'utf8mb4_unicode_ci'})
        value['columns'].append({'TABLE_NAME':table,'COLUMN_NAME':field,'ORDINAL_POSITION':1,'COLUMN_TYPE':'varchar(32)' if framework else 'bigint','IS_NULLABLE':'NO','COLUMN_DEFAULT':None,'EXTRA':'','CHARACTER_SET_NAME':'utf8mb4' if framework else None,'COLLATION_NAME':'utf8mb4_unicode_ci' if framework else None,'GENERATION_EXPRESSION':''})
        value['constraints'].append({'TABLE_NAME':table,'CONSTRAINT_NAME':'PRIMARY','CONSTRAINT_TYPE':'PRIMARY KEY','ENFORCED':'YES'})
        value['keys'].append({'TABLE_NAME':table,'CONSTRAINT_NAME':'PRIMARY','COLUMN_NAME':field,'ORDINAL_POSITION':1,'REFERENCED_TABLE_SCHEMA':None,'REFERENCED_TABLE_NAME':None,'REFERENCED_COLUMN_NAME':None})
        value['indexes'].append({'TABLE_NAME':table,'INDEX_NAME':'PRIMARY','NON_UNIQUE':0,'SEQ_IN_INDEX':1,'COLUMN_NAME':field,'SUB_PART':None,'COLLATION':'A','INDEX_TYPE':'BTREE','IS_VISIBLE':'YES','EXPRESSION':None})
        value['ddl:'+table]=[{'Table':table,'Create Table':'FICTIONAL RAW SHOW CREATE '+table}];value['rows:'+table]=[];value['count:'+table]=[{'count':0}]
    value['columns'].append({'TABLE_NAME':'driver_profiles','COLUMN_NAME':'approval_status','ORDINAL_POSITION':2,'COLUMN_TYPE':'varchar(20)','IS_NULLABLE':'NO','COLUMN_DEFAULT':'pending','EXTRA':'','CHARACTER_SET_NAME':'utf8mb4','COLLATION_NAME':'utf8mb4_unicode_ci','GENERATION_EXPRESSION':''})
    if revision!=m.CHAIN[0]:value['columns'].append({'TABLE_NAME':'driver_profiles','COLUMN_NAME':'legacy_document_exempt','ORDINAL_POSITION':3,'COLUMN_TYPE':'tinyint(1)','IS_NULLABLE':'NO','COLUMN_DEFAULT':'0','EXTRA':'','CHARACTER_SET_NAME':None,'COLLATION_NAME':None,'GENERATION_EXPRESSION':''})
    if revision==m.CHAIN[-1]:
        for field,position,length in (('create_request_key',2,100),('create_request_hash',3,64)):
            value['columns'].append({'TABLE_NAME':'customer_addresses','COLUMN_NAME':field,'ORDINAL_POSITION':position,'COLUMN_TYPE':'varchar('+str(length)+')','IS_NULLABLE':'YES','COLUMN_DEFAULT':None,'EXTRA':'','CHARACTER_SET_NAME':'utf8mb4','COLLATION_NAME':'utf8mb4_bin' if field=='create_request_key' else 'utf8mb4_unicode_ci','GENERATION_EXPRESSION':''})
    value['constraints'] += [{'TABLE_NAME':'orders','CONSTRAINT_NAME':'orders_ibfk_1','CONSTRAINT_TYPE':'FOREIGN KEY','ENFORCED':'YES'},{'TABLE_NAME':'orders','CONSTRAINT_NAME':'ck_fixture','CONSTRAINT_TYPE':'CHECK','ENFORCED':'YES'}]
    value['keys'].append({'TABLE_NAME':'orders','CONSTRAINT_NAME':'orders_ibfk_1','COLUMN_NAME':'id','ORDINAL_POSITION':1,'REFERENCED_TABLE_SCHEMA':database,'REFERENCED_TABLE_NAME':'users','REFERENCED_COLUMN_NAME':'id'})
    value['references']=[{'TABLE_NAME':'orders','CONSTRAINT_NAME':'orders_ibfk_1','REFERENCED_TABLE_NAME':'users','UNIQUE_CONSTRAINT_SCHEMA':database,'UPDATE_RULE':'RESTRICT','DELETE_RULE':'RESTRICT'}]
    value['checks']=[{'TABLE_NAME':'orders','CONSTRAINT_NAME':'ck_fixture','CHECK_CLAUSE':'(`id` >= 0)'}]
    value['orphans:orders:orders_ibfk_1']=[{'count':0}]
    for name,(table,timing,event,message) in m.trigger_specs(revision).items():
        value['triggers'].append({'TRIGGER_NAME':name,'EVENT_MANIPULATION':event,'EVENT_OBJECT_TABLE':table,'ACTION_TIMING':timing,'ACTION_ORIENTATION':'ROW','ACTION_STATEMENT':"SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '"+message+"'",'DEFINER':m.ACCOUNT,'SQL_MODE':'STRICT_TRANS_TABLES','CHARACTER_SET_CLIENT':'utf8mb4','COLLATION_CONNECTION':'utf8mb4_unicode_ci','DATABASE_COLLATION':'utf8mb4_unicode_ci'})
    return value

class InspectorTests(TestCase):
    def setUp(self):
        self.block_network=patch('socket.socket.connect',side_effect=AssertionError('NETWORK FORBIDDEN'));self.block_network.start();self.addCleanup(self.block_network.stop)
        self.session=r.MockMySQLSession(database=m.TARGET,account=m.ACCOUNT,role='migration',responses=raw_rows(m.CHAIN[0]))
        self.reader=r.MySQLInspector(self.session,policy());self.expected=expectation(m.CHAIN[0]);self.session.begin_consistent('test')
    def reject(self,operation):
        with self.assertRaises((r.Stop,ValueError,m.GuardFailure,e.EvidenceError)):operation()
    def test_positive_raw_metadata_full_inventory(self):
        value=self.reader.stage(m.CHAIN[0],self.expected);self.assertEqual(len(value['tables']),33);self.assertEqual(value['foreign_keys_checked'],1)
        self.assertEqual(value['tables']['orders']['foreign_keys'][0]['name'],'orders_ibfk_1');self.session.finish('test')
    def test_every_stage_complete_inventory_and_trigger_context(self):
        for revision,count in zip(m.CHAIN,(33,35,40,44,45)):
            session=r.MockMySQLSession(database=m.TARGET,account=m.ACCOUNT,role='migration',responses=raw_rows(revision));session.begin_consistent('stage')
            result=r.MySQLInspector(session,policy()).stage(revision,expectation(revision))
            self.assertEqual(len(result['tables']),count);self.assertEqual(len(result['triggers']),len(m.trigger_specs(revision)));session.finish('stage')
    def test_real_source_contract_is_current_outside_lifecycle_test_double(self):
        self.assertEqual(r.c.build(),json.loads((ROOT/'backend/contracts/MR07_CANONICAL_OBJECTS.json').read_text(encoding='utf-8')))
    def test_wrong_uuid(self):self.session.responses['identity'][0]['server_uuid']='wrong';self.reject(self.reader.identity)
    def test_wrong_source_scratch_account(self):
        self.session.responses['identity'][0]['account']=a.SOURCE_ACCOUNT;self.reject(self.reader.identity)
        self.reject(lambda:r.MockMySQLSession(database=m.SOURCE,account=a.SOURCE_ACCOUNT,role='migration',responses={}))
    def test_unsafe_grants_or_roles(self):
        self.session.responses['grants']=[{'grant':'GRANT ALL PRIVILEGES ON *.* TO root'}];self.reject(self.reader.identity)
    def test_missing_stage_table(self):self.session.responses['tables'].pop();self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_extra_stage_table(self):self.session.responses['tables'].append({'TABLE_NAME':'unexpected','TABLE_TYPE':'BASE TABLE'});self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_missing_framework_pk(self):
        self.session.responses['constraints']=[r for r in self.session.responses['constraints'] if r['TABLE_NAME']!='alembic_version'];self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_missing_primary_index_metadata(self):
        self.session.responses['indexes']=[x for x in self.session.responses['indexes'] if x['TABLE_NAME']!='alembic_version'];self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_orphaned_constraint_metadata_rejected(self):
        self.session.responses['references'].append(dict(self.session.responses['references'][0],CONSTRAINT_NAME='unexpected_fk'));self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_duplicate_column_metadata_rejected(self):
        self.session.responses['columns'].append(dict(self.session.responses['columns'][0],ORDINAL_POSITION=2));self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_wrong_inherited_option(self):
        self.expected['tables']['users']['options']['engine']={'value':None,'origin':'inherited_unknown','required_runtime_policy':'InnoDB'}
        next(x for x in self.session.responses['tables'] if x['TABLE_NAME']=='users')['ENGINE']='MyISAM';self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_wrong_effective_column_collation(self):
        next(x for x in self.session.responses['columns'] if x['TABLE_NAME']=='alembic_version')['COLLATION_NAME']='utf8mb4_bin';self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_decimal_defaults_and_precision_are_captured_from_raw_metadata(self):
        self.expected['tables']['ledger_entries']['columns']['amount']={'type':{'family':'DECIMAL','unsigned':False,'precision':14,'scale':2},'nullable':False,'server_default':{'kind':'literal','value':'0'},'autoincrement':False,'charset':None,'collation':None}
        extra={'TABLE_NAME':'ledger_entries','COLUMN_NAME':'amount','ORDINAL_POSITION':2,'COLUMN_TYPE':'decimal(14,2)','IS_NULLABLE':'NO','COLUMN_DEFAULT':'0.00','EXTRA':'','CHARACTER_SET_NAME':None,'COLLATION_NAME':None,'GENERATION_EXPRESSION':''}
        self.session.responses['columns'].append(extra);self.reader.stage(m.CHAIN[0],self.expected)
        extra['COLUMN_TYPE']='decimal(14,3)';self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_explicit_ascii_charset_uses_independent_server_default_collation(self):
        self.expected['tables']['ledger_entries']['columns']['digest']={'type':{'family':'CHAR','unsigned':False,'length':64},'nullable':False,'server_default':None,'autoincrement':False,'charset':'ascii','collation':None}
        raw={'TABLE_NAME':'ledger_entries','COLUMN_NAME':'digest','ORDINAL_POSITION':2,'COLUMN_TYPE':'char(64)','IS_NULLABLE':'NO','COLUMN_DEFAULT':None,'EXTRA':'','CHARACTER_SET_NAME':'ascii','COLLATION_NAME':'ascii_general_ci','GENERATION_EXPRESSION':''}
        self.session.responses['columns'].append(raw);self.reader.stage(m.CHAIN[0],self.expected)
        raw['COLLATION_NAME']='ascii_bin';self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_incorrect_fk_relationship(self):self.session.responses['keys'][-1]['REFERENCED_TABLE_NAME']='businesses';self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_cross_schema_fk(self):self.session.responses['keys'][-1]['REFERENCED_TABLE_SCHEMA']=m.SOURCE;self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_incorrect_check_enforcement(self):self.session.responses['constraints'][-1]['ENFORCED']='NO';self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_incorrect_check_expression(self):self.session.responses['checks'][0]['CHECK_CLAUSE']='id>=-1';self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_foreign_key_orphans(self):self.session.responses['orphans:orders:orders_ibfk_1']=[{'count':1}];self.reject(lambda:self.reader.stage(m.CHAIN[0],self.expected))
    def test_missing_altered_extra_trigger(self):
        for variant in ('missing','altered','extra','definer'):
            self.session.responses=raw_rows(m.CHAIN[2]);self.expected=expectation(m.CHAIN[2])
            if variant=='missing':self.session.responses['triggers'].pop()
            elif variant=='altered':self.session.responses['triggers'][0]['ACTION_STATEMENT']='SELECT 1'
            elif variant=='extra':self.session.responses['triggers'].append(dict(self.session.responses['triggers'][0],TRIGGER_NAME='unexpected'))
            else:self.session.responses['triggers'][0]['DEFINER']='root@localhost'
            self.reject(lambda:self.reader.stage(m.CHAIN[2],self.expected))
    def test_actual_trigger_context_and_expected_body_cannot_be_omitted(self):
        self.session.responses=raw_rows(m.CHAIN[2]);expected=expectation(m.CHAIN[2]);self.session.responses['triggers'][0]['SQL_MODE']=''
        self.reject(lambda:self.reader.stage(m.CHAIN[2],expected))
        self.session.responses['triggers'][0]['SQL_MODE']='STRICT_TRANS_TABLES';next(iter(expected['triggers'].values()))['body']='SELECT 1'
        self.reject(lambda:self.reader.stage(m.CHAIN[2],expected))
    def test_snapshot_content_change_even_same_count(self):self.session.responses['checks'][0]['CHECK_CLAUSE']='id>0';self.reject(lambda:self.session.finish('test'))
    def test_only_mock_transport_and_real_blocker(self):
        self.reject(lambda:r.MySQLInspector(object(),policy()));self.reject(lambda:r.real_connect(password='FICTIONAL_SECRET'))
    def test_inspection_queries_are_read_only_and_schema_bound(self):
        self.reader.stage(m.CHAIN[0],self.expected)
        for key,sql,params in (x for x in self.session.calls if len(x)==3):self.assertTrue(sql.startswith(('SELECT ','SHOW ')))
        self.reject(lambda:self.session.query('tables',(m.SOURCE,)));self.reject(lambda:self.session.query('rows:users;DROP',('id',)))
        self.reject(lambda:self.session.query('rows:users',('missing_column',)))

class AdapterTests(TestCase):
    def setUp(self):
        self.network=patch('socket.socket.connect',side_effect=AssertionError('NETWORK FORBIDDEN'));self.network.start();self.addCleanup(self.network.stop)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.contracts={'stages':{rev:expectation(rev) for rev in m.CHAIN}}
        self.stub=patch.object(r.c,'build',return_value=self.contracts);self.stub.start();self.addCleanup(self.stub.stop)
        original={name:dict(**a.fingerprint([],['user_id','approval_status'] if name=='driver_profiles' else ['id']),projection_columns=['user_id','approval_status'] if name=='driver_profiles' else ['id']) for name in m.names_at(m.CHAIN[0])-{'alembic_version'}}
        baseline={'originals':original,'driver_approval_flags':{}}
        self.backup=Path(self.tmp.name)/'fictional.backup';self.backup.write_bytes(b'FICTIONAL NOT SQL')
        self.hash=hashlib.sha256(e.canonical(self.contracts)).hexdigest().upper()
        self.manifest={'source':{'database':m.SOURCE,'host':'127.0.0.1','port':3306,'revision':m.CHAIN[0]},'revision_sequence':list(m.CHAIN),'canonical_contract_sha256':self.hash,'features':dict.fromkeys(m.FEATURES,False),'dba_approval':policy(),'baseline':baseline,'source_fingerprint':m.digest(baseline),'backup_sha256':e.sha(self.backup)}
        self.path=Path(self.tmp.name)/'manifest.json';self.path.write_text(json.dumps(self.manifest),encoding='utf-8')
        self.cap=e.issue(self.path,e.sha(self.path),self.backup,self.manifest['backup_sha256'],self.manifest['source_fingerprint'])
        self.target=r.MockMySQLSession(database=m.TARGET,account=m.ACCOUNT,role='migration',responses=raw_rows(m.CHAIN[0]))
        self.source=r.MockMySQLSession(database=m.SOURCE,account=a.SOURCE_ACCOUNT,role='source',responses=raw_rows(m.CHAIN[0],m.SOURCE,a.SOURCE_ACCOUNT,'source'))
        self.executor=r.MockStageExecutor(self.target);self.sink=e.OfflineEvidenceSink(self.tmp.name,'mr05-test-'+'e'*16)
        authority=e.MockAttestationAuthority();approval={k:v for k,v in policy().items() if k not in ('trigger_definer','trigger_context','max_age_seconds')}
        self.envelopes=[authority.issue(dict(**approval,evidence_id='mr09-test-'+str(i),observed_at=1000,expires_at=1120,trigger_definers_attested=True,writer_freeze=True,ddl_freeze=True)) for i in range(20)]
        self.adapter=r.GuardedAdapter(inspector=r.MySQLInspector(self.target,policy()),source=r.MySQLInspector(self.source,policy()),executor=self.executor,evidence=self.cap,manifest=self.manifest,contracts=self.contracts,contracts_sha256=self.hash,authority=authority,envelopes=self.envelopes,now=1000,sink=self.sink)
    def reject(self,operation):
        with self.assertRaises((r.Stop,ValueError,m.GuardFailure,e.EvidenceError)):operation()
    def test_missing_or_stale_dba_evidence(self):
        self.adapter.envelopes=[];self.reject(self.adapter.receipt)
        self.adapter.envelopes=copy.deepcopy(self.envelopes);self.adapter.now=1200;self.reject(self.adapter.receipt)
    def test_replayed_dba_evidence_rejected(self):
        self.adapter.receipt();self.adapter.envelopes.insert(0,self.envelopes[0]);self.reject(self.adapter.receipt)
    def test_backup_mismatch_before_any_stage(self):
        self.backup.write_bytes(b'CHANGED');self.reject(self.adapter.binding);self.assertEqual(self.executor.attempts,[])
    def test_source_fingerprint_mismatch(self):
        self.source.responses['rows:users']=[{'id':1}];self.source.responses['count:users']=[{'count':1}]
        self.reject(lambda:self.adapter.capture(self.adapter.source,m.CHAIN[0]));self.assertEqual(self.executor.attempts,[])
    def test_positive_mock_source_capture(self):
        value=self.adapter.capture(self.adapter.source,m.CHAIN[0]);self.assertEqual(len(value['tables']),33);self.assertIsNone(self.source.owner)
    def test_partial_migration_preserved_without_retry(self):
        self.executor.fail_next=True;self.executor.partial_responses={'tables':raw_rows(m.CHAIN[1])['tables']}
        with self.assertRaisesRegex(r.Stop,'PRESERVE_PARTIAL_STATE'):
            self.adapter.upgrade_one(m.CHAIN[0],m.CHAIN[1],execute=True,confirm_target=m.TARGET,authorization=m.TOKEN)
        self.assertEqual(self.executor.attempts,[m.CHAIN[1]]);self.assertTrue(self.adapter.failed)
        self.assertTrue((self.sink.root/('partial-'+m.CHAIN[1]+'.json')).exists());self.assertEqual(self.sink.status(),'INCOMPLETE_EVIDENCE')
        self.reject(lambda:self.executor.apply_one(m.CHAIN[0],m.CHAIN[1]));self.assertEqual(len(self.executor.attempts),1)
    def test_failure_evidence_error_remains_redacted_and_latched(self):
        self.executor.fail_next=True
        original=self.sink._write
        def fail_after_reservation(name,value):
            if name.startswith('failure-'):raise OSError('FICTIONAL PRIVATE PATH')
            return original(name,value)
        with patch.object(self.sink,'_write',side_effect=fail_after_reservation):
            with self.assertRaisesRegex(r.Stop,'STAGE_FAILED_EVIDENCE_INCOMPLETE_NO_RETRY') as error:self.adapter.upgrade_one(m.CHAIN[0],m.CHAIN[1],execute=True,confirm_target=m.TARGET,authorization=m.TOKEN)
        self.assertNotIn('PRIVATE PATH',str(error.exception));self.assertTrue(self.adapter.failed);self.assertEqual(self.sink.status(),'INCOMPLETE_EVIDENCE')
    def test_stage_authorization_and_skips_rejected(self):
        self.reject(lambda:self.adapter.upgrade_one(m.CHAIN[0],m.CHAIN[1]))
        self.reject(lambda:self.executor.apply_one(m.CHAIN[0],'head'));self.assertEqual(self.executor.attempts,[])
    def test_unconditional_existing_cli_blocker(self):
        text=(ROOT/'backend/scripts/mr02_rehearsal.py').read_text(encoding='utf-8')
        self.assertIn("if args.mode=='execute':raise GuardFailure('LIVE_ADAPTER_NOT_PREPARED_OR_AUTHORIZED')",text)

if __name__=='__main__':main()

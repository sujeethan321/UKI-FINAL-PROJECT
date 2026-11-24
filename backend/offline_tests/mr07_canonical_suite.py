"""MR-07 independent source expectations and separately authored catalog fixtures."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('canonical_contract','backend/scripts/mr07_canonical.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

def expected_source():
    # Independent, reviewed fictional migration declarations. NOT observed data.
    return {'columns':{'sale_id':"sa.Column('sale_id', sa.BigInteger(), primary_key=True, autoincrement=True)",
        'customer_id':"sa.Column('customer_id', sa.BigInteger(), nullable=False)",
        'amount':"sa.Column('amount', sa.Numeric(14,2), nullable=False, server_default=sa.text('0'))",
        'status':"sa.Column('status', sa.String(12), nullable=False, server_default='pending')"},
        'primary_keys':[{'name':None,'declaration':"sa.Column('sale_id', sa.BigInteger(), primary_key=True, autoincrement=True)"}],
        'foreign_keys':[{'name':'fk_sale_customer','declaration':'CONSTRAINT fk_sale_customer FOREIGN KEY(customer_id) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT'}],
        'unique_constraints':[{'name':'uq_sale_customer','declaration':'CONSTRAINT uq_sale_customer UNIQUE (sale_id, customer_id)'}],
        'checks':[{'name':'ck_sale_amount','declaration':'CONSTRAINT ck_sale_amount CHECK (amount>=0)'}],
        'indexes':[{'name':'ix_sale_status','declaration':'CREATE INDEX ix_sale_status ON fictional_sales (status)'}],
        'options':["mysql_engine='InnoDB'","mysql_charset='utf8mb4'","mysql_collate='utf8mb4_unicode_ci'"]}

def observed_catalog():
    # Hand-authored separately from expected_source and the canonical builder.
    def col(typ,nullable=False,default=None,auto=False):return {'type':typ,'nullable':nullable,'server_default':default,'autoincrement':auto,'charset':None,'collation':None,'client_default':None,'original':'independent fictional metadata'}
    return {'columns':{'sale_id':col({'family':'BIGINT','unsigned':False},auto=True),'customer_id':col({'family':'BIGINT','unsigned':False}),
        'amount':col({'family':'DECIMAL','unsigned':False,'precision':14,'scale':2},default={'kind':'literal','value':'0'}),
        'status':col({'family':'VARCHAR','unsigned':False,'length':12},default={'kind':'literal','value':'pending'})},
        'primary_key':['sale_id'],'foreign_keys':[{'name':'fk_sale_customer','columns':['customer_id'],'referred_table':'users','referred_columns':['user_id'],'ondelete':'RESTRICT','onupdate':'RESTRICT'}],
        'unique_constraints':[{'name':'uq_sale_customer','columns':['sale_id','customer_id']}],
        'checks':[{'name':'ck_sale_amount','definition':['>=',['identifier','amount'],['number','0']],'enforced':True}],
        'indexes':[{'name':'ix_sale_status','columns':['status'],'unique':False},{'name':'mysql_generated_support','columns':['customer_id'],'unique':False}],
        'options':{'engine':{'value':'InnoDB'},'charset':{'value':'utf8mb4'},'collation':{'value':'utf8mb4_unicode_ci'}}}

class CanonicalTests(TestCase):
    def setUp(self):
        self.network=patch('socket.socket.connect',side_effect=AssertionError('NETWORK FORBIDDEN'));self.network.start();self.addCleanup(self.network.stop)
        self.expected=c.canonical_table(expected_source());self.actual=observed_catalog()
    def reject(self,mutate):
        mutate(self.actual)
        with self.assertRaises(ValueError):c.verify_table(self.actual,self.expected)
    def test_independent_positive_catalog(self):c.verify_table(self.actual,self.expected)
    def test_missing_fk(self):self.reject(lambda x:x['foreign_keys'].clear())
    def test_incorrect_fk_columns(self):self.reject(lambda x:x['foreign_keys'][0].update(columns=['sale_id']))
    def test_wrong_fk_action(self):self.reject(lambda x:x['foreign_keys'][0].update(ondelete='CASCADE'))
    def test_missing_unique(self):self.reject(lambda x:x['unique_constraints'].clear())
    def test_incorrect_check(self):self.reject(lambda x:x['checks'][0].update(definition=['>',['identifier','amount'],['number','0']]))
    def test_unenforced_check(self):self.reject(lambda x:x['checks'][0].update(enforced=False))
    def test_wrong_decimal_scale(self):self.reject(lambda x:x['columns']['amount']['type'].update(scale=3))
    def test_incorrect_nullability(self):self.reject(lambda x:x['columns']['amount'].update(nullable=True))
    def test_missing_server_default(self):self.reject(lambda x:x['columns']['status'].update(server_default=None))
    def test_incorrect_table_options(self):self.reject(lambda x:x['options']['collation'].update(value='utf8mb4_bin'))
    def test_unexpected_supporting_index(self):self.reject(lambda x:x['indexes'].append({'name':'extra','columns':['amount'],'unique':False}))
    def test_duplicate_supporting_index(self):self.reject(lambda x:x['indexes'].append({'name':'extra','columns':['customer_id'],'unique':False}))
    def test_unique_index_cannot_masquerade_as_support(self):self.reject(lambda x:x['indexes'][1].update(unique=True))
    def test_missing_explicit_index(self):self.reject(lambda x:x['indexes'].pop(0))
    def test_missing_supporting_index(self):self.reject(lambda x:x['indexes'].pop())
    def test_generated_fk_names_are_separate_from_structural_identity(self):
        self.expected['foreign_keys'][0]['name']=None;self.actual['foreign_keys'][0]['name']='server_generated_01'
        c.verify_table(self.actual,self.expected)
        self.assertEqual(self.actual['foreign_keys'][0]['name'],'server_generated_01')
    def test_primary_key_is_required(self):self.reject(lambda x:x.update(primary_key=[]))
    def test_framework_expected_not_application_migration(self):
        result=c.framework_contract();self.assertEqual(result['versions'],{'alembic':'1.20.1','sqlalchemy':'2.1.6'})
        self.assertEqual(result['table']['columns']['version_num']['type'],{'family':'VARCHAR','unsigned':False,'length':32})
        self.assertEqual(result['table']['primary_key'],['version_num']);self.assertEqual(result['naming']['declared_primary_key'],'alembic_version_pkc')
        self.assertIsNone(result['table']['options']['engine']['value'])
    def test_missing_alembic_version_table_primary_key(self):
        expected=c.framework_contract()['table']
        actual={'columns':{'version_num':{'type':{'family':'VARCHAR','unsigned':False,'length':32},'nullable':False,'server_default':None,'autoincrement':False,'charset':None,'collation':None}},'primary_key':[], 'foreign_keys':[],'unique_constraints':[],'checks':[],'indexes':[], 'options':{'engine':{'value':'InnoDB'},'charset':{'value':'utf8mb4'},'collation':{'value':'utf8mb4_unicode_ci'}}}
        with self.assertRaises(ValueError):c.verify_table(actual,expected)
    def test_numeric_boolean_datetime_and_integer_variants(self):
        self.assertEqual(c.type_sql('NUMERIC(14, 2)'),c.type_sql('DECIMAL(14,2)'))
        self.assertEqual(c.type_ast(ast.parse('mysql.NUMERIC(14,2)',mode='eval').body)[0],c.type_sql('DECIMAL(14,2)'))
        self.assertEqual(c.type_sql('BOOL'),c.type_sql('TINYINT(1)'))
        self.assertEqual(c.type_sql('DATETIME'),c.type_sql('DATETIME(0)'))
        self.assertNotEqual(c.type_sql('DATETIME(6)'),c.type_sql('DATETIME'))
        self.assertEqual(c.type_sql('BIGINT(20)'),c.type_sql('BIGINT'))
        self.assertNotEqual(c.type_sql('INT UNSIGNED'),c.type_sql('INT'))
    def test_unsupported_conversions_fail_closed(self):
        for text in ('DECIMAL','DECIMAL(0,0)','DECIMAL(14)','DECIMAL(65,31)','BIGINT(30)','VARCHAR','VARCHAR(65536)','CHAR(256)','VARCHAR(20) GENERATED ALWAYS','TEXT(20)','INT ZEROFILL','JSON'):
            with self.assertRaises(ValueError):c.type_sql(text)
        with self.assertRaises(ValueError):c.type_ast(ast.parse('Boolean(create_constraint=True)',mode='eval').body)
        for text in ('Text(length=20)','DateTime(fsp=6)','BigInteger(unsigned=True)'):
            with self.assertRaises(ValueError):c.type_ast(ast.parse(text,mode='eval').body)
        self.assertEqual(c.type_sql('TEXT')['max_bytes'],65535)
    def test_nullable_inference_and_client_only_defaults(self):
        _,value,_=c.column_ast(ast.parse("mapped_column(String(20), default='pending')",mode='eval').body,'Mapped[str | None]')
        self.assertTrue(value['nullable']);self.assertIsNone(value['server_default']);self.assertEqual(value['client_default'],"'pending'")
    def test_datetime_and_ascii_declarations(self):
        typ,charset,collation=c.type_ast(ast.parse("CHAR(64,charset='ascii')",mode='eval').body)
        self.assertEqual(typ['length'],64);self.assertEqual(charset,'ascii')
        _,value,_=c.column_sql('updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)')
        self.assertEqual(value['server_default'],{'kind':'current_timestamp','fsp':6})
    def test_inherited_options_are_unknown_not_invented(self):
        result=c.options_contract([]);self.assertTrue(all(x['origin']=='inherited_unknown' and x['value'] is None for x in result.values()))
        self.assertEqual(result['engine']['required_runtime_policy'],'InnoDB')
    def test_saved_contract_matches_current_source_and_compiler(self):
        value=json.loads((ROOT/'backend/contracts/MR07_CANONICAL_OBJECTS.json').read_text(encoding='utf-8'))
        self.assertEqual(value,c.build())
    def test_full_source_stage_counts_model_parity_and_symbolic_expansion(self):
        value=c.build();self.assertFalse(value['real_execution_enabled'])
        self.assertEqual([len(v['tables']) for v in value['stages'].values()],[33,35,40,44,45])
        self.assertEqual([len(v['triggers']) for v in value['stages'].values()],[0,0,10,16,18])
        self.assertEqual(value['head_model_parity']['differences'],[])
        self.assertEqual(value['head_model_parity']['columns_compared'],424)
        self.assertEqual(len(value['head_model_parity']['naming_observations']),3)
        self.assertEqual(sum(t['options']['engine']['value'] is None for t in value['stages'][c.ledger.STAGES[-1]]['tables'].values()),21)
        models=c.model_tables();tables=value['stages'][c.ledger.STAGES[-1]]['tables']
        for name in ('business_join_links','customer_join_requests','customer_link_invitations','subscription_trial_grants','business_subscriptions','subscription_payment_events','subscription_checkout_attempts'):
            self.assertEqual(models[name]['options'],tables[name]['options'])
            self.assertTrue(all(v['origin']=='declared' for v in models[name]['options'].values()))
    def test_unnamed_fk_local_columns_recovered_from_source(self):
        value=c.build()['stages'][c.ledger.STAGES[-1]]['tables']
        self.assertEqual(sum(len(t['foreign_keys']) for t in value.values()),114)
        self.assertTrue(all(fk['columns'] and len(fk['columns'])==len(fk['referred_columns']) for table in value.values() for fk in table['foreign_keys']))
    def test_existing_execution_blocker_unchanged(self):
        text=(ROOT/'backend/scripts/mr02_rehearsal.py').read_text(encoding='utf-8')
        self.assertIn("if args.mode=='execute':raise GuardFailure('LIVE_ADAPTER_NOT_PREPARED_OR_AUTHORIZED')",text)

if __name__=='__main__':main()

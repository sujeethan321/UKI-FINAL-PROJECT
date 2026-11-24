"""Step 13.49: exact operator CHECK inventory; no network or SQL execution."""
import copy
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import re
import sys
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[2]
FIXTURE=Path(__file__).with_name('fixtures')/'viva_check_constraints_89.txt'
FIXTURE_SHA256='47C5834A0A9F39098BB946E507C9FB2F8588EA2570A93C9B9024A656E35E9EA7'
spec=importlib.util.spec_from_file_location('actual_check_executor',ROOT/'backend/scripts/viva_migration_execute.py')
v=importlib.util.module_from_spec(spec);sys.modules[spec.name]=v;spec.loader.exec_module(v)
c=v.d.c

def inventory():
    raw=FIXTURE.read_bytes()
    assert len(raw)==104586 and hashlib.sha256(raw).hexdigest().upper()==FIXTURE_SHA256,'ACTUAL_FIXTURE_INTEGRITY_FAILURE'
    rows=[]
    for line in raw.decode('utf-8-sig').splitlines():
        if not line.startswith('| ') or line.startswith('| TABLE_NAME'):continue
        parts=line.split('|',4)
        assert len(parts)==5 and parts[-1].endswith('|'),'INVALID_CAPTURED_TABLE_ROW'
        table,name,enforced=(value.strip() for value in parts[1:4])
        expression=parts[4][:-1].strip()  # Remove table padding, not SQL escaping.
        rows.append(dict(TABLE_NAME=table,CONSTRAINT_NAME=name,ENFORCED=enforced,CHECK_CLAUSE=expression))
    assert len(rows)==89 and len({(r['TABLE_NAME'],r['CONSTRAINT_NAME']) for r in rows})==89
    assert all(r['ENFORCED']=='YES' for r in rows)
    return rows

def expected_checks(revision):
    return {(table,check['name']):check for table,metadata in c.build()['stages'][revision]['tables'].items() for check in metadata['checks']}

def metadata_control(sql):
    """Synthetic FUTURE-stage control only; baseline always uses captured bytes.

    Independent str.translate encoder follows MySQL String::print. The source
    expression is retained (no expression-tree rewriting or copied mock state).
    """
    introduced=re.sub(r"'(?:[^'\\]|'')*'",lambda match:'_utf8mb4'+match[0],sql)
    return introduced.translate(str.maketrans({'\\':r'\\',"'":r"\'",'\0':r'\0','\n':r'\n','\r':r'\r','\x1a':r'\Z'}))

def declared_expression(entry):
    declaration=entry['declaration']
    if declaration.startswith('CONSTRAINT '):return re.fullmatch(r'CONSTRAINT\s+\w+\s+CHECK\s*\((.*)\)',declaration,re.S)[1]
    call=ast.parse(declaration,mode='eval').body
    kind=call.func.attr if isinstance(call.func,ast.Attribute) else call.func.id
    return ast.literal_eval(call.args[2 if kind=='create_check_constraint' else 0])

class ActualCheckTests(unittest.TestCase):
    def setUp(self):
        self.net=patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN'));self.net.start();self.addCleanup(self.net.stop)
        self.rows=inventory()
    def test_exact_original_fixture_size_hash_count_and_enforcement(self):
        self.assertEqual(len(self.rows),89)
    def test_all_actual_baseline_constraints_match_independent_source(self):
        expected=expected_checks(v.CHAIN[0]);actual={}
        for row in self.rows:
            key=(row['TABLE_NAME'],row['CONSTRAINT_NAME'])
            with self.subTest(table=key[0],constraint=key[1]):
                actual[key]=dict(name=key[1],definition=c.check_key(row['CHECK_CLAUSE'],representation='mysql8_information_schema'),enforced=row['ENFORCED']=='YES')
                self.assertEqual(actual[key],expected[key])
        self.assertEqual(actual,expected)
    def test_plain_sql_parser_still_rejects_encoded_metadata(self):
        first=self.rows[0]
        self.assertEqual((first['TABLE_NAME'],first['CONSTRAINT_NAME']),('admin_audits','ck_admin_audit_action'))
        self.assertIn("_utf8mb4\\'driver_approved\\'",first['CHECK_CLAUSE'])
        with self.assertRaisesRegex(ValueError,'Unsupported CHECK syntax'):c.check_key(first['CHECK_CLAUSE'])
    def test_first_exact_expression_reproduces_original_tokenizer_failure(self):
        expression=self.rows[0]['CHECK_CLAUSE']
        self.assertEqual(expression,r"(`action` in (_utf8mb4\'driver_approved\',_utf8mb4\'driver_rejected\',_utf8mb4\'account_suspended\',_utf8mb4\'account_reactivated\',_utf8mb4\'admin_provisioned\'))")
        with self.assertRaisesRegex(ValueError,'Unsupported CHECK syntax'):c.checks.check_tree(expression)
        self.assertEqual(c.check_key(expression,representation='mysql8_information_schema'),expected_checks(v.CHAIN[0])[('admin_audits','ck_admin_audit_action')]['definition'])
    def test_all_actual_rows_pass_executor_prevalidation_without_changing_input(self):
        before=copy.deepcopy(self.rows);built=c.build()['stages'][v.CHAIN[0]]['tables'];inspector=v.Inspector(Mock(),v.SOURCE)
        for table in sorted({r['TABLE_NAME'] for r in self.rows}):
            rows=[r for r in self.rows if r['TABLE_NAME']==table];inspector.expected_checks[table]={r['name'] for r in built[table]['checks']}
            with patch.object(v,'query',return_value=rows):self.assertIs(inspector.read('checks',table),rows)
        self.assertEqual(self.rows,before)
    def test_actual_charsets_case_signs_limits_null_and_grouping_are_not_erased(self):
        originals={(r['TABLE_NAME'],r['CONSTRAINT_NAME']):r for r in self.rows}
        chosen=[(('admin_audits','ck_admin_audit_target'),"user","USER"),
                (('admin_audits','ck_admin_audit_target_id'),'> 0','>= 0'),
                (('customer_addresses','ck_address_coordinates'),'-(90)','90'),
                (('customer_addresses','ck_address_coordinates'),'is null','is not null')]
        for key,old,new in chosen:
            original=originals[key]['CHECK_CLAUSE'];self.assertIn(old,original)
            self.assertNotEqual(c.check_key(original,representation='mysql8_information_schema'),c.check_key(original.replace(old,new,1),representation='mysql8_information_schema'))
        original=originals[('admin_audits','ck_admin_audit_target')]['CHECK_CLAUSE']
        for charset in ('_latin1','_binary','_utf8mb3'):
            with self.assertRaises(ValueError):c.check_key(original.replace('_utf8mb4',charset),representation='mysql8_information_schema')
        for collation in ('utf8mb4_bin','utf8mb4_unicode_ci'):
            with self.assertRaises(ValueError):c.check_key(original+' COLLATE '+collation,representation='mysql8_information_schema')
    def test_one_metadata_layer_and_inner_literal_escapes_are_distinct(self):
        cases=[(r"label = _utf8mb4\'O\\\'Brien\'","O'Brien"),
               (r"label = _utf8mb4\'C:\\\\tmp\'","C:\\tmp"),
               (r"label = _utf8mb4\'\\\\n\'",r'\n'),
               (r"label = _utf8mb4\'\\n\'",'\n'),
               (r"label = _utf8mb4\'\'",'')]
        for metadata,value in cases:
            with self.subTest(kind='literal_encoding'):self.assertEqual(c.checks.mysql_check_tree(metadata),('=',('identifier','label'),('string',value)))
        self.assertNotEqual(c.checks.mysql_check_tree(cases[2][0]),c.checks.mysql_check_tree(cases[3][0]))
    def test_bad_mixed_or_double_encoded_metadata_is_not_auto_repaired(self):
        for expression in ("label='raw SQL'",r"label=\'truncated",r"label=\q",r"label = _utf8mb4\'bad\x41\'",r"label = _utf8mb4\'unclosed",r"label = _utf8mb4\\\'double\\\'"):
            with self.subTest(kind='malformed'),self.assertRaises(ValueError):c.check_key(expression,representation='mysql8_information_schema')
        with self.assertRaises(ValueError):c.check_key('amount>0',representation='auto')
    def test_decoding_metadata_cannot_add_sql_or_unreviewed_functions(self):
        for sql in ("label='x'; DROP TABLE users",'amount /*comment*/ >=0','unknown(amount)>0',"label IN ('x',)",'amount>=','a AND (b OR c'):
            with self.subTest(kind='unsupported_sql'),self.assertRaises(ValueError):c.check_key(metadata_control(sql),representation='mysql8_information_schema')
    def test_pending_stage_controls_cover_all_31_added_or_replaced_checks(self):
        built=c.build();actual={(r['TABLE_NAME'],r['CONSTRAINT_NAME']):dict(name=r['CONSTRAINT_NAME'],definition=c.check_key(r['CHECK_CLAUSE'],representation='mysql8_information_schema'),enforced=r['ENFORCED']=='YES') for r in self.rows}
        covered=[]
        for revision,total in zip(v.CHAIN[1:],(100,115,118)):
            stage=built['stages'][revision]
            for table,metadata in stage['tables'].items():
                for check in metadata['checks']:
                    key=(table,check['name'])
                    if actual.get(key)==check:continue
                    declaration=next(item for item in built['original_declarations'][revision]['tables'][table]['checks'] if item['name']==check['name'])
                    sql=declared_expression(declaration)
                    definition=c.check_key(metadata_control(sql),representation='mysql8_information_schema')
                    self.assertEqual(definition,check['definition']);actual[key]=dict(name=key[1],definition=definition,enforced=True);covered.append((revision,key))
                    self.assertNotEqual(c.check_key(metadata_control('('+sql+') AND 1=0'),representation='mysql8_information_schema'),definition)
            wanted={(table,check['name']):check for table,metadata in stage['tables'].items() for check in metadata['checks']}
            self.assertEqual(len(actual),total);self.assertEqual(actual,wanted)
        self.assertEqual([sum(revision==r for revision,key in covered) for r in v.CHAIN[1:]],[11,17,3])
    def test_actual_constraint_enforcement_and_inventory_are_required(self):
        expected=expected_checks(v.CHAIN[0])
        actual={(r['TABLE_NAME'],r['CONSTRAINT_NAME']):dict(name=r['CONSTRAINT_NAME'],definition=c.check_key(r['CHECK_CLAUSE'],representation='mysql8_information_schema'),enforced=r['ENFORCED']=='YES') for r in self.rows}
        self.assertEqual(actual,expected)
        for mutation in ('disabled','missing','extra','changed'):
            variant=copy.deepcopy(actual);key=('admin_audits','ck_admin_audit_action')
            if mutation=='disabled':variant[key]['enforced']=False
            elif mutation=='missing':variant.pop(key)
            elif mutation=='extra':variant[('admin_audits','ck_unexpected')]=copy.deepcopy(variant[key])
            else:variant[key]['definition']=['=', ['number','1'],['number','1']]
            self.assertNotEqual(variant,expected)
    def test_production_comparator_rejects_tampered_actual_admin_checks(self):
        # Isolate the CHECK boundary. Other objects are source scaffolding,
        # not claimed to be captured database metadata.
        expected=c.build()['stages'][v.CHAIN[0]]['tables']['admin_audits']
        actual=dict(columns={name:c.ddl_column(column) for name,column in expected['columns'].items()},primary_key=copy.deepcopy(expected['primary_key']),foreign_keys=copy.deepcopy(expected['foreign_keys']),unique_constraints=copy.deepcopy(expected['unique_constraints']),indexes=copy.deepcopy(expected['indexes']),options={key:{'value':spec['value'] if spec['origin']=='declared' else spec['required_runtime_policy']} for key,spec in expected['options'].items()})
        covering=[actual['primary_key']]+[item['columns'] for item in actual['unique_constraints']]+[item['columns'] for item in actual['indexes']]
        for fk in actual['foreign_keys']:
            if not any(columns[:len(fk['columns'])]==fk['columns'] for columns in covering):
                actual['indexes'].append(dict(name='fictional_fk_support_'+str(len(actual['indexes'])),columns=fk['columns'],unique=False));covering.append(fk['columns'])
        actual['checks']=[dict(name=row['CONSTRAINT_NAME'],definition=c.check_key(row['CHECK_CLAUSE'],representation='mysql8_information_schema'),enforced=True) for row in self.rows if row['TABLE_NAME']=='admin_audits']
        c.verify_table(actual,expected)
        for mutation in ('disabled','missing','extra','changed'):
            variant=copy.deepcopy(actual)
            if mutation=='disabled':variant['checks'][0]['enforced']=False
            elif mutation=='missing':variant['checks'].pop()
            elif mutation=='extra':variant['checks'].append(dict(variant['checks'][0],name='ck_unexpected'))
            else:variant['checks'][0]['definition']=['=', ['number','1'],['number','1']]
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):c.verify_table(variant,expected)
    def test_unknown_metadata_escape_has_fixed_redacted_diagnostics(self):
        inspector=v.Inspector(Mock(),v.SOURCE);inspector.expected_checks['admin_audits']={'ck_admin_audit_action'}
        row=dict(self.rows[0],CHECK_CLAUSE=self.rows[0]['CHECK_CLAUSE']+r'\q')
        with patch.object(v,'query',return_value=[row]),self.assertRaises(ValueError) as caught:inspector.read('checks','admin_audits')
        self.assertEqual(v.diagnostic(caught.exception),'CHECK_METADATA_ESCAPE_UNSUPPORTED')
        details=v.failure_details(caught.exception);self.assertEqual(details['schema_constraint'],'ck_admin_audit_action');self.assertNotIn(row['CHECK_CLAUSE'],str(details))
    def test_pinned_expectations_are_still_derived_from_source(self):
        saved=json.loads((ROOT/'backend/contracts/MR07_CANONICAL_OBJECTS.json').read_bytes());self.assertEqual(saved,c.build())

if __name__=='__main__':unittest.main()

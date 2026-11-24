"""Pure synthetic recovery-contract tests: no settings, MySQL or network imports."""
import ast,copy,importlib.util
from pathlib import Path
from unittest import TestCase,main

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('recovery_plan',ROOT/'backend/scripts/security_recovery_plan.py')
plan=importlib.util.module_from_spec(spec);spec.loader.exec_module(plan)

def inventory(revision):
    value=dict(database=plan.SOURCE,host='127.0.0.1',port=3306,revision=revision,server_uuid='fictional',object_inventory_complete=True,
        tables={name:dict(row_count=0,content_sha256='a'*64,schema_sha256='b'*64,columns=[],primary_key=[],indexes=[],foreign_keys=[],checks=[]) for name in plan.tables_at(revision)},views=[],routines=[],events=[],triggers=[])
    for name,(table,timing,event,message) in plan.trigger_contract(revision).items():
        value['triggers'].append(dict(name=name,table=table,timing=timing,event=event,orientation='ROW',definer='fictional@localhost',statement="SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '"+message+"'"))
    return value

class RecoveryTests(TestCase):
    def test_table_inventory_matches_source_models_without_loading_settings(self):
        names=set()
        for path in (ROOT/'backend/app/models').glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__tablename__' for t in node.targets):names.add(ast.literal_eval(node.value))
        self.assertEqual(names|{'alembic_version'},plan.TABLES)
    def test_revision_specific_inventory(self):
        for revision,tables,triggers in zip(plan.REVISIONS,(35,40,44,45),(0,10,16,18)):
            result=plan.validate_inventory(inventory(revision),revision)
            self.assertEqual((result['tables'],result['triggers']),(tables,triggers))
    def test_wrong_targets_and_unknown_revisions_fail(self):
        for target in ('lankapex_viva_db','lankapex_db','lankapex_test_db','lankapex_viva_recovery_step391','other'):
            with self.assertRaises(ValueError):plan.target_guard(plan.SOURCE,plan.REVISIONS[-1],target)
        with self.assertRaises(ValueError):plan.tables_at('unknown')
    def test_complete_trigger_definitions_required(self):
        original=inventory(plan.REVISIONS[-1])
        for field,value in (('statement','SELECT 1'),('definer',''),('timing','AFTER'),('event','INSERT'),('orientation','STATEMENT')):
            changed=copy.deepcopy(original);changed['triggers'][0][field]=value
            with self.assertRaises(ValueError):plan.validate_inventory(changed,plan.REVISIONS[-1])
        original['triggers'].pop()
        with self.assertRaises(ValueError):plan.validate_inventory(original,plan.REVISIONS[-1])
    def test_partial_tables_and_unreviewed_programs_fail(self):
        for field in ('views','routines','events'):
            changed=inventory(plan.REVISIONS[-1]);changed[field]=[{'name':'unexpected'}]
            with self.assertRaises(ValueError):plan.validate_inventory(changed,plan.REVISIONS[-1])
        changed=inventory(plan.REVISIONS[-1]);changed['tables'].pop('ledger_entries')
        with self.assertRaises(ValueError):plan.validate_inventory(changed,plan.REVISIONS[-1])
    def test_source_identity_and_fingerprints_required(self):
        for field,value in (('database','other'),('host','elsewhere'),('port',3307),('object_inventory_complete',False)):
            changed=inventory(plan.REVISIONS[-1]);changed[field]=value
            with self.assertRaises(ValueError):plan.validate_inventory(changed,plan.REVISIONS[-1])
        changed=inventory(plan.REVISIONS[-1]);changed['tables']['ledger_entries']['content_sha256']='missing'
        with self.assertRaises(ValueError):plan.validate_inventory(changed,plan.REVISIONS[-1])

if __name__=='__main__':main()

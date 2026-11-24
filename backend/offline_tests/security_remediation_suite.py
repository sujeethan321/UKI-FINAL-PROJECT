"""SV-02 fictional SQLite/temp files and mocked ASGI; network blocked by base."""
import asyncio
from unittest import TestCase,main,TestSuite
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
import subprocess
import driver_registration_suite as registration
import support_suite as support
from sqlalchemy import select,CheckConstraint
from fastapi import HTTPException
from app.models import User,DriverVerificationDocument
from app.models.support import SupportCase,SupportEvent
from app.schemas.support import Command
from app.services import driver_vehicle_service as vehicle,support_service as cases
from app.services.driver_document_storage import DocumentError,ValidatedDocument
from app.services.schema_integrity import check_tree,verify_checks
from app.core.request_limits import RequestBodyLimitMiddleware
from app.core.rate_limit import configure_rate_limits,_consume

class CleanupTests(registration.RegistrationFixture):
    def count(self):return len(list(self.store.root.iterdir()))
    def test_second_failure_repeatedly_removes_only_new_first_candidate(self):
        for _ in range(3):
            self.assertEqual(self.submit(second=('fake.exe',b'bad','application/octet-stream')).status_code,422)
            self.assertEqual(self.count(),0)
        self.assertEqual(list(self.db.scalars(select(DriverVerificationDocument))),[])
    def test_first_validation_failure_creates_no_application(self):
        self.assertEqual(self.submit(first=('fake.png',b'bad','image/png')).status_code,422)
        self.assertEqual(self.count(),0)
    def test_known_precommit_rollback_cleans_both_candidates(self):
        with patch.object(vehicle,'append_version',side_effect=RuntimeError('private sentinel')):
            result=self.submit()
        self.assertEqual(result.status_code,503);self.assertNotIn('sentinel',result.text);self.assertEqual(self.count(),0)
        self.assertEqual(list(self.db.scalars(select(DriverVerificationDocument))),[])
    def test_uncertain_commit_preserves_candidates_and_never_retries(self):
        with patch.object(self.db,'commit',side_effect=RuntimeError('uncertain')) as commit:
            self.assertEqual(self.submit().status_code,503);self.assertEqual(commit.call_count,1)
        self.assertEqual(self.count(),2)
    def test_previous_committed_documents_survive_failed_replacement(self):
        self.assertEqual(self.submit().status_code,201)
        docs=list(self.db.scalars(select(DriverVerificationDocument)));keys={d.storage_key for d in docs}
        docs[0].review_status='REJECTED';docs[0].reviewed_by=1;docs[0].reviewed_at=registration.foundation.datetime(2026,1,1);docs[0].rejection_code='UNREADABLE';self.db.commit()
        self.assertEqual(self.submit(second=('bad.exe',b'bad','image/png')).status_code,422)
        self.assertEqual({p.name for p in self.store.root.iterdir()},keys)
    def test_reference_check_never_deletes_committed_candidate(self):
        self.assertEqual(self.submit().status_code,201);row=self.db.scalar(select(DriverVerificationDocument))
        candidate=ValidatedDocument(row.storage_key,row.media_type,row.size_bytes,row.content_sha256)
        vehicle.rollback_candidates(self.db,self.store,[candidate],False)
        self.assertEqual(self.count(),2)
    def test_failed_rollback_preserves_files_for_review(self):
        with patch.object(self.db,'rollback',side_effect=RuntimeError('unverified rollback')):
            result=self.submit(second=('bad.exe',b'bad','image/png'))
        self.assertEqual(result.status_code,503);self.assertEqual(self.count(),1)

class SupportLockTests(support.SupportTests):
    def test_two_admin_directions_lock_user_ids_before_case_in_same_order(self):
        admin=User(user_id=6,full_name='Fictional second Admin',email='second-admin@invalid.example',password_hash='unused',platform_role='admin',account_status='active')
        self.db.add(admin);self.db.commit()
        first=self.create();second=self.create(request_key='support-create-key-0002')
        for actor,target,record in ((admin,1,first),(self.admin,6,second)):
            trace=[];original=self.db.scalar
            def scalar(query,*args,**kwargs):
                if getattr(query,'_for_update_arg',None) is not None:
                    entity=query.column_descriptions[0].get('entity')
                    if entity is User:trace.append(('user',query._where_criteria[0].right.value))
                    if entity is SupportCase:trace.append(('case',None))
                return original(query,*args,**kwargs)
            payload=Command(action='assignment',admin_id=target,expected_version=record['case']['version'],request_key='assign-stable-key-'+str(target))
            with patch.object(self.db,'scalar',side_effect=scalar):cases.command(self.db,actor,record['case']['reference'],payload,True)
            self.db.commit();self.assertEqual(trace[:3],[('user',1),('user',6),('case',None)])
    def test_failed_assignment_rolls_back_without_history_or_version_change(self):
        record=self.create();row=self.db.scalar(select(SupportCase));before=(row.version,row.assigned_admin_id)
        count=len(list(self.db.scalars(select(SupportEvent))))
        with self.assertRaises(HTTPException):cases.command(self.db,self.admin,row.reference,Command(action='assignment',admin_id=2,expected_version=row.version,request_key='invalid-admin-assignment'),True)
        self.db.rollback();self.db.refresh(row)
        self.assertEqual((row.version,row.assigned_admin_id),before);self.assertEqual(len(list(self.db.scalars(select(SupportEvent)))),count)

class BodyTests(TestCase):
    def invoke(self,messages=None,slow=False,downstream_status=204,path='/api/v1/auth/login',limit=8):
        async def run():
            output=[];called=[];items=iter(messages or [])
            async def receive():
                if slow:await asyncio.sleep(1)
                try:return next(items)
                except StopIteration:await asyncio.sleep(1);return {'type':'http.disconnect'}
            async def send(message):output.append(message)
            async def app(scope,receive,send):
                called.append(await receive());await send({'type':'http.response.start','status':downstream_status,'headers':[]});await send({'type':'http.response.body','body':b''})
            await RequestBodyLimitMiddleware(app,max_bytes=limit,read_timeout=.02)({'type':'http','method':'POST','path':path,'headers':[]},receive,send)
            return output,called
        return asyncio.run(run())
    def test_oversized_and_slow_or_incomplete_chunked_bodies(self):
        self.assertEqual(self.invoke([{'type':'http.request','body':b'123456789'}])[0][0]['status'],413)
        self.assertEqual(self.invoke(slow=True)[0][0]['status'],408)
        self.assertEqual(self.invoke([{'type':'http.request','body':b'x','more_body':True}])[0][0]['status'],408)
    def test_disconnect_and_cancellation_never_invoke_application(self):
        self.assertEqual(self.invoke([{'type':'http.disconnect'}]),([],[]))
        async def run():
            async def receive():raise asyncio.CancelledError()
            async def prohibited(*args):raise AssertionError('Unexpected downstream call')
            with self.assertRaises(asyncio.CancelledError):await RequestBodyLimitMiddleware(prohibited)({'type':'http','method':'POST','path':'/api/v1/x','headers':[]},receive,prohibited)
        asyncio.run(run())
    def test_valid_body_and_auth_errors_are_preserved(self):
        output,called=self.invoke([{'type':'http.request','body':b'{}'}],downstream_status=403)
        self.assertEqual(output[0]['status'],403);self.assertEqual(called[0]['body'],b'{}')
    def test_upload_path_retains_11_mib_limit(self):
        output,called=self.invoke([{'type':'http.request','body':b'x'*100}],path='/api/v1/driver/vehicle')
        self.assertEqual(output[0]['status'],204);self.assertEqual(len(called[0]['body']),100)

class SchemaTests(TestCase):
    def test_numeric_comparison_never_rounds_tampered_long_literals(self):
        self.assertNotEqual(check_tree('amount<=100'),check_tree('amount<=100.00000000000000000000000000001'))
        self.assertEqual(check_tree('amount<=100'),check_tree('amount<=100.00000000000000000000000000000'))
    def test_reviewed_parentheses_charset_and_numeric_formatting_equivalence(self):
        for expected,actual in [("kind='LKR' AND amount>=0","((`kind` = _utf8mb4'LKR') and (`amount` >= 0))"),('fee_rate=0.030000','(`fee_rate`=0.03)'),('a IS NOT NULL OR b BETWEEN -90 AND 90','((`a` is not null) or (`b` between -(90) and 90))')]:
            self.assertEqual(check_tree(expected),check_tree(actual))
    def test_changed_grouping_literals_comparisons_and_unsupported_sql_rejected(self):
        for left,right in [('a+(b*c)','(a+b)*c'),("currency='LKR'","currency='USD'"),('amount>=0','amount>0'),('a AND (b OR c)','(a AND b) OR c')]:self.assertNotEqual(check_tree(left),check_tree(right))
        for value in ('1=1; DROP TABLE x','a /*comment*/ = 1',"a=_latin1'LKR'",'evil(a)>0'):
            with self.assertRaises(ValueError):check_tree(value)
    def test_every_reviewed_model_check_is_supported(self):
        from app.models import CustomerAddress,UserPreference,Notification,OrderDeliveryAddress
        from app.models.driver_finance import OrderFulfilmentCharge,DriverEarning,DriverFeeCollection,DriverSettlementEvent,DriverFinancialAudit
        from app.models.support import SupportCase,SupportMessage,SupportEvent,SupportReference
        for model in (CustomerAddress,UserPreference,Notification,OrderDeliveryAddress,OrderFulfilmentCharge,DriverEarning,DriverFeeCollection,DriverSettlementEvent,DriverFinancialAudit,SupportCase,SupportMessage,SupportEvent,SupportReference):
            for constraint in model.__table__.constraints:
                if isinstance(constraint,CheckConstraint):check_tree(str(constraint.sqltext))
    def test_fake_inspector_missing_changed_or_unenforced_constraint_fails_closed(self):
        from app.models.driver_finance import DriverEarning
        table=DriverEarning.__table__;definitions=[dict(name=c.name,sqltext=str(c.sqltext)) for c in table.constraints if isinstance(c,CheckConstraint)]
        class Result:
            def __init__(self,value):self.value=value
            def mappings(self):return self
            def all(self):return self.value
            def one(self):return self.value
        enforced=[{'CONSTRAINT_NAME':c['name'],'ENFORCED':'YES'} for c in definitions]
        class DB:
            def execute(self,query,params=None):return Result(enforced if 'TABLE_CONSTRAINTS' in str(query) else dict(fk_checks=1,unique_checks=1,sql_mode='STRICT_TRANS_TABLES'))
        inspector=SimpleNamespace(dialect=SimpleNamespace(name='mysql'),get_check_constraints=lambda name:definitions)
        verify_checks(DB(),inspector,table)
        for replacement in ([],[dict(definitions[0],sqltext='amount>=-1')]):
            with patch.object(inspector,'get_check_constraints',return_value=replacement):
                with self.assertRaises(ValueError):verify_checks(DB(),inspector,table)
        enforced[0]['ENFORCED']='NO'
        with self.assertRaises(ValueError):verify_checks(DB(),inspector,table)

class PackagingAndRateTests(TestCase):
    def test_external_mode_has_local_backstop_without_claiming_shared_quota(self):
        app=SimpleNamespace(state=SimpleNamespace());config=SimpleNamespace(APP_ENV='production',RATE_LIMIT_MODE='external',JWT_SECRET_KEY='fictional-only-key')
        configure_rate_limits(app,config);request=SimpleNamespace(app=app)
        _consume(request,[('test','actor',1)])
        with self.assertRaises(HTTPException) as error:_consume(request,[('test','actor',1)])
        self.assertEqual(error.exception.status_code,429)
        app.state.rate_limiter=None
        with self.assertRaises(HTTPException):_consume(request,[('test','actor',1)])
    def test_git_policy_includes_source_but_excludes_private_artifacts(self):
        root=Path(__file__).resolve().parents[2]
        def ignored(path):
            result=subprocess.run(['git','-c','safe.directory='+root.as_posix(),'check-ignore','--no-index','-q',path],cwd=root,capture_output=True)
            self.assertIn(result.returncode,(0,1));return result.returncode==0
        for path in ('backend/offline_tests/security_remediation_suite.py','backend/tests/test_groq_client.py','frontend/tests/reportAIReader.test.js','frontend/tests/fixtures/adminReportsFixtures.js'):self.assertFalse(ignored(path),path)
        for path in ('backend/.env','backend/tests/private/customer.py','backend/tests/real_credentials.py','frontend/tests/evidence/customer.js','backup.sql','output/step400/result.json'):self.assertTrue(ignored(path),path)
        result=subprocess.run(['git','-c','safe.directory='+root.as_posix(),'check-attr','export-ignore','--','backend/.env','backend/.env.example','backend/tests/test_groq_client.py','output/checkpoint.json','backend/tests/private/document.py','backup.sql'],cwd=root,capture_output=True,text=True,check=True)
        expected={'backend/.env':'set','backend/.env.example':'unset','backend/tests/test_groq_client.py':'unspecified','output/checkpoint.json':'set','backend/tests/private/document.py':'set','backup.sql':'set'}
        for line in result.stdout.splitlines():
            path,attribute,value=line.rsplit(': ',2)
            self.assertEqual(value,expected[path])

def load_tests(loader,tests,pattern):
    return TestSuite(cls(name) for cls in (CleanupTests,SupportLockTests,BodyTests,SchemaTests,PackagingAndRateTests) for name in cls.__dict__ if name.startswith('test_'))

if __name__=='__main__':main()

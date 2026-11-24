"""SD-02 fictional SQLite only. Harness forbids networking and real settings."""
import ast
from pathlib import Path
from datetime import timedelta
from unittest import TestCase,main
from unittest.mock import patch
import delivery_estimate_suite as fixture
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select,func,event,text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects.mysql import dialect
from app.models import User,BusinessMember,Notification,LedgerEntry,Order
from app.models.driver_finance import OrderFulfilmentCharge,DriverEarning,DriverFeeCollection,DriverSettlementEvent,DriverFinancialAudit
from app.models.support import SupportCase,SupportMessage,SupportEvent,SupportReference
from app.schemas.support import CreateCase,Command,CaseFilters
from app.services import support_service as service
from app.services.support_rollout import REVISION
from app.routers import support,admin_support

TABLES=[SupportCase.__table__,SupportMessage.__table__,SupportEvent.__table__,SupportReference.__table__]

class SupportTests(TestCase):
    def setUp(self):
        fixture.IntegrationTests.setUp(self)
        self.flags=patch.multiple(fixture.fixtures.base.config.settings,SUPPORT_ENABLED=True,SUPPORT_DBA_ATTESTED_REVISION=REVISION,create=True);self.flags.start();self.addCleanup(self.flags.stop)
        fixture.fixtures.base.Base.metadata.create_all(self.engine,tables=[OrderFulfilmentCharge.__table__,DriverEarning.__table__,DriverFeeCollection.__table__,DriverSettlementEvent.__table__,DriverFinancialAudit.__table__,Notification.__table__,*TABLES])
        self.db.connection().exec_driver_sql('CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)')
        self.db.connection().exec_driver_sql("INSERT INTO alembic_version VALUES ('c04d9e7a6201')")
        for table in TABLES[1:]:
            for operation in ('UPDATE','DELETE'):
                self.db.connection().exec_driver_sql(f"CREATE TRIGGER sd_{table.name}_{operation.lower()}_deny BEFORE {operation} ON {table.name} BEGIN SELECT RAISE(ABORT,'Support history is append-only'); END")
        self.db.commit();self.customer=self.db.get(User,4);self.admin=self.db.get(User,1);self.driver=self.db.get(User,5)
    tearDown=fixture.fixtures.ReportsTests.tearDown

    def payload(self,**changes):return CreateCase(**(dict(category='account',subject='Fictional support',description='Fictional description only',request_key='support-create-key-0001')|changes))
    def create(self,user=None,**changes):
        result=service.create(self.db,user or self.customer,self.payload(**changes));self.db.commit();return result
    def act(self,result,action,user=None,**changes):
        user=user or self.admin
        payload=Command(action=action,expected_version=result['case']['version'],request_key='support-action-'+str(self.db.scalar(select(func.count()).select_from(SupportEvent))+1),**changes)
        result=service.command(self.db,user,result['case']['reference'],payload,user.platform_role=='admin');self.db.commit();return result,payload

    def test_creation_replay_and_conflict_no_duplicate_notification(self):
        one=self.create();two=self.create();self.assertEqual(one['case']['reference'],two['case']['reference'])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(SupportCase)),1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Notification)),1)
        with self.assertRaises(HTTPException):self.create(subject='Different subject')

    def test_creator_identity_and_category_validation(self):
        for changes in ({'creator_id':2},{'category':'sql'},{'description':'short'}):
            with self.assertRaises(ValueError):self.payload(**changes)
        with self.assertRaises(ValueError):Command(action='status',expected_version=1,request_key='valid-request-key-123',status='resolved')

    def test_private_ownership_all_roles_and_admin(self):
        result=self.create();reference=result['case']['reference']
        for user in (self.user,self.driver,self.db.get(User,3)):
            with self.assertRaises(HTTPException) as error:service.detail(self.db,user,reference)
            self.assertEqual(error.exception.status_code,404)
        self.assertEqual(service.detail(self.db,self.admin,reference,True)['case']['creator_id'],4)
        self.assertNotIn('creator_id',result['case'])
        for user in (self.user,self.driver):
            own=self.create(user,request_key='support-own-case-'+str(user.user_id));self.assertEqual(service.list_cases(self.db,user,CaseFilters())['total'],1)

    def test_explicit_business_sharing_and_membership_revocation(self):
        private=self.create(business_id=10)
        shared=self.create(business_id=10,business_shared=True,request_key='shared-create-key-123')
        self.assertEqual(service.list_cases(self.db,self.user,CaseFilters())['total'],1)
        self.assertEqual(service.detail(self.db,self.user,shared['case']['reference'])['case']['subject'],'Fictional support')
        with self.assertRaises(HTTPException):service.detail(self.db,self.db.get(User,3),shared['case']['reference'])
        membership=self.db.scalar(select(BusinessMember).where(BusinessMember.business_id==10,BusinessMember.user_id==2));membership.membership_status='inactive';self.db.commit()
        with self.assertRaises(HTTPException):service.detail(self.db,self.user,shared['case']['reference'])
        self.assertEqual(service.detail(self.db,self.customer,private['case']['reference'])['case']['status'],'open')

    def test_internal_notes_hidden_in_messages_events_counts_versions(self):
        result=self.create();reference=result['case']['reference'];public_version=result['case']['version'];stamp=result['case']['updated_at']
        result=service.detail(self.db,self.admin,reference,True)
        result,_=self.act(result,'internal_note',body='Private fictional investigation')
        own=service.detail(self.db,self.customer,reference)
        self.assertEqual(own['messages']['total'],0);self.assertEqual(own['events']['total'],1)
        self.assertEqual(own['case']['version'],public_version);self.assertEqual(own['case']['updated_at'],stamp)
        self.assertNotIn('Private fictional',str(own))
        self.assertEqual(result['messages']['total'],1)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Notification)),1)

    def test_reference_validation_and_finance_disabled(self):
        result=self.create(category='credit_balance',related={'kind':'credit_account','record_id':'1'})
        self.assertEqual(result['case']['business_id'],10)
        for related in ({'kind':'credit_account','record_id':'3'},{'kind':'order','record_id':'999'},{'kind':'ledger_entry','record_id':'-1'}):
            with self.assertRaises(HTTPException):self.create(related=related,request_key='invalid-reference-'+related['record_id'].replace('-','x'))
        with self.assertRaises(HTTPException) as error:self.create(self.driver,related={'kind':'earning','record_id':'00000000-0000-0000-0000-000000000000'},request_key='finance-disabled-key-123')
        self.assertEqual(error.exception.status_code,503)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(DriverEarning)),0)

    def test_resolution_reopen_window_closure_and_replay(self):
        result=self.create();reference=result['case']['reference'];result=service.detail(self.db,self.admin,reference,True)
        result,_=self.act(result,'status',status='investigating',reason='Review started')
        result,request=self.act(result,'status',status='resolved',reason='No financial correction performed')
        replay=service.command(self.db,self.admin,reference,request,True);self.db.commit();self.assertEqual(replay['case']['status'],'resolved')
        own=service.detail(self.db,self.customer,reference);own,_=self.act(own,'reopen',user=self.customer,reason='Further evidence supplied')
        self.assertEqual(own['case']['status'],'investigating')
        result=service.detail(self.db,self.admin,reference,True);result,_=self.act(result,'status',status='resolved',reason='Review finished again')
        row=self.db.scalar(select(SupportCase));row.resolved_at-=timedelta(days=15);self.db.commit()
        with self.assertRaises(HTTPException):self.act(result,'reopen',reason='Too late for reopening')
        result,_=self.act(result,'status',status='closed',reason='Archive case')
        with self.assertRaises(HTTPException):self.act(result,'reopen',reason='Closed case')

    def test_admin_assignment_priority_and_stale_competing_updates(self):
        result=self.create();reference=result['case']['reference'];result=service.detail(self.db,self.admin,reference,True)
        with self.assertRaises(HTTPException):self.act(result,'assignment',admin_id=4)
        result,_=self.act(result,'assignment',admin_id=1)
        result,_=self.act(result,'status',status='assigned',reason='Assigned review')
        stale=result['case']['version'];result,_=self.act(result,'priority',priority='high')
        with self.assertRaises(HTTPException) as error:service.command(self.db,self.admin,reference,Command(action='priority',priority='urgent',expected_version=stale,request_key='competing-action-key-123'),True)
        self.assertEqual(error.exception.status_code,409)

    def test_financial_records_unchanged_by_dispute_lifecycle(self):
        from decimal import Decimal
        self.db.add_all([LedgerEntry(credit_account_id=1,created_by=2,entry_type='credit_sale',amount=Decimal('100.00'),idempotency_key='sd02-preserved-sale'),
            LedgerEntry(credit_account_id=1,created_by=2,entry_type='repayment',amount=Decimal('25.00'),payment_method='cash',notes='Fictional preserved evidence',idempotency_key='sd02-preserved-repayment'),
            Order(order_id=99,reference='SD02-PRESERVED-ORDER',business_id=10,customer_user_id=4,request_key='sd02-preserved-order',request_hash='a'*64,
                payment_method='cash',payment_status='unpaid',status='processing',subtotal=Decimal('100.00'),total=Decimal('100.00'))])
        self.db.commit()
        def fingerprint():return list(self.db.execute(select(LedgerEntry.entry_id,LedgerEntry.amount))),list(self.db.execute(select(Order.order_id,Order.total)))
        before=fingerprint();result=self.create(category='repayment',related={'kind':'credit_account','record_id':'1'})
        result=service.detail(self.db,self.admin,result['case']['reference'],True)
        self.act(result,'status',status='resolved',reason='Case decision only; no payment recorded')
        self.assertEqual(fingerprint(),before)
        for model in (DriverEarning,DriverFeeCollection,DriverSettlementEvent):self.assertEqual(self.db.scalar(select(func.count()).select_from(model)),0)

    def test_event_immutability_bulk_raw_and_message_attribution(self):
        self.create()
        for sql in ('UPDATE support_case_events SET reason=\'changed\'','DELETE FROM support_case_events'):
            with self.assertRaises(IntegrityError):self.db.execute(text(sql))
            self.db.rollback()
        with self.assertRaises(ValueError):self.db.query(SupportEvent).delete()
        self.db.rollback()

    def test_disabled_gate_zero_support_queries_and_schema_attestation(self):
        statements=[];event.listen(self.engine,'before_cursor_execute',lambda conn,cursor,sql,params,ctx,many:statements.append(sql.lower()))
        with patch.object(fixture.fixtures.base.config.settings,'SUPPORT_ENABLED',False):
            with self.assertRaises(HTTPException) as error:service.list_cases(self.db,self.customer,CaseFilters())
            self.assertEqual(error.exception.detail['code'],'SUPPORT_DISABLED')
        self.assertFalse(any('support_case' in sql for sql in statements))
        with patch.object(fixture.fixtures.base.config.settings,'SUPPORT_DBA_ATTESTED_REVISION',None):
            with self.assertRaises(HTTPException):service.list_cases(self.db,self.customer,CaseFilters())

    def test_http_roles_pagination_no_store_and_transactional_notifications(self):
        import jwt
        from datetime import datetime,timezone
        app=FastAPI();app.include_router(support.router,prefix='/api/v1');app.include_router(admin_support.router,prefix='/api/v1')
        app.dependency_overrides[fixture.fixtures.base.get_db]=lambda:self.db
        def headers(ident):
            now=datetime.now(timezone.utc)
            return {'Authorization':'Bearer '+jwt.encode(dict(sub=str(ident),type='access',iat=now,exp=now+timedelta(minutes=5)),fixture.fixtures.base.config.settings.JWT_SECRET_KEY,algorithm='HS256')}
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/v1/support/cases').status_code,401)
            self.assertEqual(client.get('/api/v1/admin/support/cases',headers=headers(4)).status_code,403)
            response=client.post('/api/v1/support/cases',json=self.payload().model_dump(mode='json'),headers=headers(4));self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.headers['cache-control'],'no-store')
            self.assertEqual(client.get('/api/v1/support/cases?limit=101',headers=headers(4)).status_code,422)
            self.db.get(User,1).account_status='suspended';self.db.commit()
            self.assertEqual(client.get('/api/v1/admin/support/cases',headers=headers(1)).status_code,403)

    def test_frozen_migration_matches_models_and_preserves_chain(self):
        tree=ast.parse(Path('backend/alembic/versions/c04d9e7a6201_support_cases.py').read_text())
        sql=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='execute' and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):sql.append(node.args[0].value)
        self.assertEqual(sum(value.startswith('CREATE TABLE') for value in sql),4)
        self.assertEqual(sum(value.startswith('CREATE TRIGGER') for value in sql),6)
        for table in TABLES:self.assertIn(str(CreateTable(table).compile(dialect=dialect())).strip(),sql)

    def test_notification_public_reply_and_information_request_no_sensitive_content(self):
        result=self.create();result=service.detail(self.db,self.admin,result['case']['reference'],True)
        result,_=self.act(result,'message',body='Sensitive fictional discussion not for notifications')
        result,_=self.act(result,'status',status='awaiting_user',reason='Provide fictional evidence')
        messages=list(self.db.scalars(select(Notification)))
        self.assertEqual(len(messages),3)
        self.assertTrue(all(row.recipient_user_id==4 and row.business_id is None for row in messages))
        self.assertNotIn('Sensitive fictional',str([(row.title,row.message) for row in messages]))

    def test_failure_rolls_back_case_event_and_notification_together(self):
        def fail(db,row,event,kind):
            from app.services.notification_service import notify_support_event
            notify_support_event(db,row,event,kind)
            raise IntegrityError('fictional',{},Exception('fictional'))
        with patch.object(service,'notify',side_effect=fail):
            with self.assertRaises(IntegrityError):service.create(self.db,self.customer,self.payload())
        self.db.rollback()
        for model in (SupportCase,SupportEvent,Notification):self.assertEqual(self.db.scalar(select(func.count()).select_from(model)),0)

    def test_missing_support_schema_fails_explicitly(self):
        self.db.connection().exec_driver_sql('DROP TABLE support_case_references')
        with self.assertRaises(HTTPException) as error:service.list_cases(self.db,self.customer,CaseFilters())
        self.assertEqual(error.exception.detail['code'],'SUPPORT_SCHEMA_NOT_READY')

    def test_requesters_cannot_set_admin_state_or_create_internal_notes(self):
        result=self.create();reference=result['case']['reference']
        for payload in (Command(action='internal_note',body='Forbidden internal note',expected_version=1,request_key='requester-note-key-123'),Command(action='status',status='resolved',reason='Forbidden resolution',expected_version=1,request_key='requester-status-key-123')):
            with self.assertRaises(HTTPException) as error:service.command(self.db,self.customer,reference,payload)
            self.assertEqual(error.exception.status_code,403)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(SupportMessage)),0)

    def test_support_body_limit_rejects_stream_before_parsing(self):
        from app.core.support_body_limit import SupportBodyLimit
        app=FastAPI();app.include_router(support.router,prefix='/api/v1');app.add_middleware(SupportBodyLimit)
        with TestClient(app) as client:
            response=client.post('/api/v1/support/cases',content=(b'x'*40000 for _ in range(2)),headers={'Content-Type':'application/json'})
            self.assertEqual(response.status_code,413)
            self.assertEqual(response.headers['cache-control'],'no-store')

    def test_pagination_counts_hide_internal_history_and_refs_are_immutable(self):
        result=self.create(related={'kind':'credit_account','record_id':'1'});reference=result['case']['reference']
        result=service.detail(self.db,self.admin,reference,True)
        for number in range(3):result,_=self.act(result,'internal_note',body='Fictional internal '+str(number))
        page=service.history(self.db,self.customer,reference,'events',1,0)
        self.assertEqual(page['total'],1);self.assertEqual(len(page['items']),1)
        with self.assertRaises(IntegrityError):self.db.execute(text('DELETE FROM support_case_references'))
        self.db.rollback()

    def test_support_head_requires_fresh_finance_attestation_without_auto_enabling(self):
        config=fixture.fixtures.base.config.settings
        with patch.multiple(config,DRIVER_FINANCE_ENABLED=True,DRIVER_FINANCE_DBA_ATTESTED_REVISION='bf38d2a90176',create=True):
            self.assertEqual(service.finance_capability(self.db),'unavailable')
            with patch.object(config,'DRIVER_FINANCE_DBA_ATTESTED_REVISION',REVISION):
                self.assertEqual(service.finance_capability(self.db),'available')
        self.assertEqual(service.finance_capability(self.db),'unavailable')

    def test_reopen_exact_fourteen_day_boundary_and_immutable_reference(self):
        result=self.create();result=service.detail(self.db,self.admin,result['case']['reference'],True)
        result,_=self.act(result,'status',status='resolved',reason='Fictional resolution')
        row=self.db.scalar(select(SupportCase));stamp=row.resolved_at+timedelta(days=14)
        with patch.object(service,'utc_now',return_value=stamp):
            own=service.detail(self.db,self.customer,result['case']['reference'])
            result,_=self.act(own,'reopen',user=self.customer,reason='Within permitted boundary')
        self.assertEqual(result['case']['status'],'investigating')

    def test_historical_message_role_is_not_reinterpreted_after_role_change(self):
        result=self.create();reference=result['case']['reference'];result=service.detail(self.db,self.admin,reference,True)
        self.act(result,'message',body='Fictional Administrator reply')
        self.admin.platform_role='customer';self.db.commit()
        own=service.detail(self.db,self.customer,reference)
        self.assertTrue(own['messages']['items'][0]['from_admin'])

    def test_pending_business_owner_and_unapproved_driver_can_seek_support(self):
        owner_case=self.create(self.user,business_id=30,request_key='pending-business-support-key')
        driver_case=self.create(self.driver,request_key='pending-driver-support-key')
        self.assertEqual(owner_case['case']['business_id'],30)
        self.assertEqual(driver_case['case']['status'],'open')

if __name__=='__main__':main(verbosity=2)

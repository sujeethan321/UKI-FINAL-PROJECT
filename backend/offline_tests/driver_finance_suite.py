"""SQLite-only direct-finance integration; the fixture blocks all networking."""
from decimal import Decimal
from unittest import TestCase,main
from unittest.mock import patch
import delivery_estimate_suite as fixture
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.models import User,DriverProfile,Order,LedgerEntry,DeliveryRequest,DeliveryAssignment,DeliveryStatusEvent
from app.models.driver_finance import OrderFulfilmentCharge,DriverEarning,DriverFeeCollection,DriverSettlementEvent,DriverFinancialAudit
from app.services import order_service,driver_service,driver_finance_service as finance
from app.services.driver_fee_pricing import amounts,commitment
from app.schemas.order import Cart,OrderCreate
from app.routers import driver_finance as routes

TABLES=[DriverEarning.__table__,DriverFeeCollection.__table__,DriverSettlementEvent.__table__,DriverFinancialAudit.__table__]


class FinanceTests(fixture.IntegrationTests):
    def setUp(self):
        self.rollout=patch.multiple(fixture.fixtures.base.config.settings,DRIVER_FINANCE_ENABLED=True,
            DRIVER_FINANCE_DBA_ATTESTED_REVISION='bf38d2a90176',create=True);self.rollout.start()
        self.addCleanup(self.rollout.stop)
        super().setUp();fixture.fixtures.base.Base.metadata.create_all(self.engine,tables=TABLES)
        self.db.connection().exec_driver_sql('CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)')
        self.db.connection().exec_driver_sql("INSERT INTO alembic_version VALUES ('bf38d2a90176')")
        for table in [OrderFulfilmentCharge.__tablename__]+[t.name for t in TABLES]:
            for action in ('UPDATE','DELETE'):
                self.db.connection().exec_driver_sql(f"CREATE TRIGGER df_{table}_{action.lower()}_deny BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Driver finance history is append-only'); END")
        profile=self.db.get(DriverProfile,5);profile.approval_status='approved';profile.reviewed_by=1;profile.reviewed_at=fixture.datetime(2026,1,1)
        profile.vehicle_type='Bike';profile.registration_reference='FICTIONAL';profile.legacy_document_exempt=True;self.db.commit()
        self.driver=self.db.get(User,5);self.admin=self.db.get(User,1)

    def tearDown(self):
        try:super().tearDown()
        finally:self.rollout.stop()

    def completed(self,status='delivered',initial='in_transit'):
        with patch.object(order_service,'notify_event'):
            order=order_service.create(self.db,self.db.get(User,4),self.payload())
        delivery=DeliveryRequest(business_id=10,created_by=2,reference='DR-FICTIONAL',pickup_area='Shop',delivery_area='Customer',status=initial)
        self.db.add(delivery);self.db.flush()
        self.db.get(Order,order['order_id']).delivery_request_id=delivery.delivery_request_id
        self.db.add(DeliveryAssignment(delivery_request_id=delivery.delivery_request_id,driver_user_id=5));self.db.commit()
        with patch('app.services.notification_service.notify_event'):
            driver_service.transition_delivery(self.db,5,delivery.delivery_request_id,status,initial)
        self.db.commit();return self.db.scalar(select(DriverEarning))

    def declaration(self,earning,**changes):
        return routes.Collection(**(dict(kind='declared',amount='150.00',evidence='Fictional cash receipt checked',request_key='declaration-key-0001')|changes))

    def test_completion_declared_verified_direct_no_platform_payout(self):
        earning=self.completed();self.assertEqual(earning.amount,Decimal('150.00'))
        self.assertEqual(finance.history(self.db,self.driver)['summary']['pending'],'150.00')
        data=finance.operation(self.db,self.driver,earning.earning_id,self.declaration(earning));self.db.commit()
        self.assertEqual(data['status'],'collection_declared');self.assertFalse(data['collection_verified'])
        command=routes.Verification(kind='direct_settled',collection_id=data['collections'][0]['collection_id'],
            evidence='Independent fictional receipt verification',request_key='verification-key-0001')
        settled=finance.operation(self.db,self.admin,earning.earning_id,command,True);self.db.commit()
        self.assertTrue(settled['collection_verified']);self.assertEqual(settled['status'],'directly_settled')
        finance.operation(self.db,self.admin,earning.earning_id,command,True);self.db.commit()
        self.assertEqual(self.db.scalar(select(func.count()).select_from(DriverSettlementEvent)),1)
        sums=finance.history(self.db,self.driver)['summary']
        self.assertEqual(sums['directly_settled'],'150.00');self.assertEqual(sums['available'],'0.00');self.assertEqual(sums['platform_paid'],'0.00')
        self.assertEqual(self.db.scalar(select(func.count()).select_from(LedgerEntry)),0)
        with self.assertRaises(fixture.fixtures.HTTPException):driver_service.transition_delivery(self.db,5,earning.delivery_request_id,'delivered','in_transit')
        self.assertEqual(self.db.scalar(select(func.count()).select_from(DriverEarning)),1)

    def test_partial_exception_rejected_verification_and_ownership(self):
        earning=self.completed()
        for amount in ['149.99','150.01']:
            with self.assertRaises(fixture.fixtures.HTTPException):finance.operation(self.db,self.driver,earning.earning_id,self.declaration(earning,amount=amount))
        self.db.rollback()
        exception=routes.Collection(kind='exception',amount='50.00',evidence='Partial cash collection requires review',request_key='exception-key-00001')
        data=finance.operation(self.db,self.driver,earning.earning_id,exception);self.db.commit();self.assertEqual(data['status'],'exception_review')
        with self.assertRaises(fixture.fixtures.HTTPException):finance.operation(self.db,self.admin,earning.earning_id,
            routes.Verification(kind='direct_settled',evidence='Independent evidence is not sufficient here',request_key='verify-exception-0001'),True)
        self.db.rollback()
        with self.assertRaises(fixture.fixtures.HTTPException):finance.operation(self.db,self.admin,earning.earning_id,exception)
        self.db.rollback()

    def test_immutable_adjustment_and_no_auto_refund(self):
        earning=self.completed();data=finance.operation(self.db,self.driver,earning.earning_id,self.declaration(earning));self.db.commit()
        finance.operation(self.db,self.admin,earning.earning_id,routes.Verification(kind='direct_settled',collection_id=data['collections'][0]['collection_id'],evidence='Verified independent fictional evidence',request_key='verified-key-000001'),True);self.db.commit()
        finance.operation(self.db,self.admin,earning.earning_id,routes.Verification(kind='reversed',evidence='Correction requires review; no refund proven',request_key='reversal-key-000001'),True);self.db.commit()
        history=finance.history(self.db,self.driver);self.assertEqual(history['summary']['directly_settled'],'0.00');self.assertEqual(history['summary']['review'],'150.00')
        self.assertEqual(len(history['earnings'][0]['settlement_events']),2)
        earning.amount=Decimal('1')
        with self.assertRaises(ValueError):self.db.flush()
        self.db.rollback()

    def test_signed_quote_pickup_stale_and_forgery(self):
        customer=self.db.get(User,4);cart=Cart(business_id=10,items=[dict(product_id=1,quantity=1)],fulfilment_mode='pickup')
        quote=order_service.quote(self.db,customer,cart);self.assertEqual(quote['delivery_fee'],'0.00');self.assertEqual(quote['customer_total'],'5000.00')
        payload=OrderCreate(**cart.model_dump(),quote_token=quote['quote_token'],payment_method='cash',request_key='pickup-request-0001')
        with patch.object(order_service,'notify_event'):result=order_service.create(self.db,customer,payload)
        self.assertEqual(result['total'],'5000.00');self.assertEqual(result['delivery_fee'],'0.00')
        self.assertEqual(amounts(Decimal('0.50'),'delivery')['delivery_fee'],'0.02')
        changed=payload.model_copy(update={'fulfilment_mode':'delivery','request_key':'changed-request-0001'})
        with self.assertRaises(fixture.fixtures.HTTPException):order_service.create(self.db,customer,changed)
        with patch('app.services.driver_fee_pricing.time.time',return_value=0):
            with self.assertRaises(fixture.fixtures.HTTPException):commitment(4,10,[],Decimal('5000'),'pickup',quote['quote_token'])

    def test_http_authorization_cache_and_input_validation(self):
        earning=self.completed();app=FastAPI();app.include_router(routes.router,prefix='/api/v1')
        actor=[self.driver]
        app.dependency_overrides[fixture.fixtures.base.get_db]=lambda:self.db
        app.dependency_overrides[fixture.fixtures.base.get_current_user]=lambda:actor[0]
        with TestClient(app) as client:
            response=client.get('/api/v1/driver/earnings');self.assertEqual(response.status_code,200);self.assertEqual(response.headers['cache-control'],'no-store')
            self.assertEqual(client.post('/api/v1/driver/earnings/'+earning.earning_id+'/collections',json={'kind':'declared','amount':'150.001','evidence':'Fictional evidence','request_key':'test-request-00001'}).status_code,422)
            self.assertEqual(client.get('/api/v1/admin/drivers/5/earnings').status_code,403)
            actor[0]=self.admin;self.assertEqual(client.get('/api/v1/admin/drivers/5/earnings').status_code,200)
            del app.dependency_overrides[fixture.fixtures.base.get_current_user]
            self.assertEqual(client.get('/api/v1/driver/earnings').status_code,401)

    def test_cancelled_deliveries_and_empty_business_create_no_earnings(self):
        self.assertEqual(finance.history(self.db,self.driver)['summary']['total_earned'],'0.00')
        self.assertIsNone(self.completed('cancelled','assigned'))
        self.assertEqual(self.db.scalar(select(func.count()).select_from(DriverEarning)),0)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(DriverFinancialAudit)),0)

    def test_database_uniqueness_and_null_slot_protection(self):
        earning=self.completed()
        duplicate=DriverEarning(order_id=earning.order_id,delivery_request_id=earning.delivery_request_id,assignment_id=earning.assignment_id,
            completion_event_id=earning.completion_event_id,driver_user_id=5,amount=earning.amount)
        self.db.add(duplicate)
        with self.assertRaises(IntegrityError):self.db.flush()
        self.db.rollback()
        broken=DriverFeeCollection(earning_id=earning.earning_id,actor_user_id=5,kind='declared',declaration_slot=None,
            amount=earning.amount,evidence='Fictional evidence reference',request_key='invalid-slot-000001',request_hash='a'*64)
        self.db.add(broken)
        with self.assertRaises(IntegrityError):self.db.flush()
        self.db.rollback()

    def test_zero_rounded_fee_does_not_fabricate_collection(self):
        product=self.db.get(fixture.Product,1);product.unit_price=Decimal('0.15');self.db.commit()
        earning=self.completed();self.assertEqual(earning.amount,Decimal('0.00'))
        self.assertEqual(finance.history(self.db,self.driver)['earnings'][0]['status'],'no_fee_due')
        command=routes.Collection(kind='declared',amount='0.00',evidence='No amount is actually due',request_key='zero-fee-request-0001')
        with self.assertRaises(fixture.fixtures.HTTPException):finance.operation(self.db,self.driver,earning.earning_id,command)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(DriverFeeCollection)),0)

    def test_migration_matches_models_and_contains_only_additive_ddl(self):
        import ast
        from pathlib import Path
        from sqlalchemy.schema import CreateTable
        from sqlalchemy.dialects import mysql
        path=Path(__file__).resolve().parents[1]/'alembic/versions/bf38d2a90176_customer_driver_direct_finance.py'
        tree=ast.parse(path.read_text())
        upgrade=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='upgrade')
        statements=[ast.literal_eval(n.value.args[0]) for n in upgrade.body if isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='execute']
        self.assertTrue(all(s.startswith(('CREATE TABLE','CREATE INDEX','ALTER TABLE','CREATE TRIGGER')) for s in statements))
        for cls in (OrderFulfilmentCharge,DriverEarning,DriverFeeCollection,DriverSettlementEvent,DriverFinancialAudit):
            expected=str(CreateTable(cls.__table__).compile(dialect=mysql.dialect())).strip()
            self.assertTrue(any(s.startswith(expected) for s in statements),cls.__tablename__)
        self.assertEqual(sum(s.startswith('CREATE TABLE') for s in statements),5)
        self.assertEqual(sum(s.startswith('CREATE TRIGGER') for s in statements),10)
        self.assertEqual(sum(s.startswith('ALTER TABLE') for s in statements),5)


if __name__=='__main__':main(verbosity=2)

"""Address checkout integration on fictional SQLite fixtures; no networking."""
from unittest import TestCase,main
from unittest.mock import patch
from decimal import Decimal
import driver_finance_suite as base
import customer_address_suite as addresses
from sqlalchemy.schema import CreateTable
from sqlalchemy import select,func,update
from fastapi import HTTPException
from app.models import CustomerAddress,UserPreference,OrderDeliveryAddress,User,Order,DeliveryRequest,DeliveryAssignment,LedgerEntry
from app.schemas.customer_address import AddressVersion,AddressUpdate
from app.schemas.order import Cart,OrderCreate
from app.services import customer_address_service as book,customer_address_rollout as rollout,order_service,order_address_service,driver_service

class CheckoutTests(base.FinanceTests):
    setUpFinance=base.FinanceTests.setUp
    tearDown=base.FinanceTests.tearDown
    def setUp(self):
        self.setUpFinance()
        self.options=patch.multiple(base.fixture.fixtures.base.config.settings,ADDRESS_BOOK_ENABLED=True,ADDRESS_CHECKOUT_ENABLED=True,create=True)
        self.options.start();self.addCleanup(self.options.stop)
        self.readiness=patch.object(rollout,'require_ready');self.readiness.start();self.addCleanup(self.readiness.stop)
        for table in (CustomerAddress.__table__,UserPreference.__table__,OrderDeliveryAddress.__table__):
            self.db.connection().exec_driver_sql(str(CreateTable(table).compile(self.engine)).replace('CURRENT_TIMESTAMP(6)','CURRENT_TIMESTAMP'))
        self.customer=self.db.get(User,4)
        result=book.mutate(self.db,self.customer,addresses.AddressTests.payload(self),'create');self.db.commit()
        self.address_id=result['address']['address_id']
    def payload(self,mode='delivery',method='cash'):
        cart=Cart(business_id=10,items=[dict(product_id=1,quantity=1)],fulfilment_mode=mode,
            **(dict(address_id=self.address_id,address_version=2) if mode=='delivery' else {}))
        quote=order_service.quote(self.db,self.customer,cart)
        return OrderCreate(**cart.model_dump(),quote_token=quote['quote_token'],payment_method=method,request_key='address-checkout-'+mode+'-'+method)
    def create(self,payload):
        with patch.object(order_service,'notify_event'):result=order_service.create(self.db,self.customer,payload)
        self.db.commit();return result
    def test_delivery_snapshot_and_replay_after_archival(self):
        payload=self.payload();result=self.create(payload)
        self.assertEqual(result['delivery_fee'],'150.00');self.assertEqual(result['total'],'5000.00')
        self.assertEqual(result['destination']['address_line'],'Fictional lane\nFloor 2')
        book.mutate(self.db,self.customer,AddressVersion(version=2),'archive',self.address_id);self.db.commit()
        again=self.create(payload)
        self.assertEqual(again['order_id'],result['order_id']);self.assertEqual(again['destination'],result['destination'])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(OrderDeliveryAddress)),1)
        with self.assertRaises(ValueError):self.db.execute(update(OrderDeliveryAddress).values(city='Changed'))
        self.assertEqual(order_service.listing(self.db,self.customer,1,10)['orders'][0]['destination'],result['destination'])
    def test_edit_between_quote_and_confirmation_rejected(self):
        payload=self.payload()
        book.mutate(self.db,self.customer,AddressUpdate(version=2,label='Home',recipient_name='Different',address_line='Different fictional road'),'edit',self.address_id);self.db.commit()
        with self.assertRaises(HTTPException):self.create(payload)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Order)),0)
    def test_archived_address_not_available_for_new_order(self):
        payload=self.payload();book.mutate(self.db,self.customer,AddressVersion(version=2),'archive',self.address_id);self.db.commit()
        with self.assertRaises(HTTPException):self.create(payload)
    def test_pickup_no_snapshot_no_fee(self):
        result=self.create(self.payload('pickup'))
        self.assertEqual(result['delivery_fee'],'0.00');self.assertIsNone(result['destination'])
        self.assertEqual(self.db.scalar(select(func.count()).select_from(OrderDeliveryAddress)),0)
    def test_credit_approval_remains_product_only(self):
        result=self.create(self.payload(method='credit'))
        with patch.object(order_service,'notify_event'),patch('app.services.shop_owner_credit_sale_service.notify_event'):
            approved=order_service.decide(self.db,self.db.get(User,2),result['order_id'],'approve',10)
        self.assertEqual(self.db.get(LedgerEntry,approved['credit_sale_id']).amount,Decimal('5000.00'))
    def test_driver_active_assignment_only_and_business_scope(self):
        result=self.create(self.payload())
        delivery=DeliveryRequest(reference='ADDRESS-FICTIONAL',business_id=10,created_by=2,pickup_area='Shop',delivery_area='Area only',status='assigned')
        self.db.add(delivery);self.db.flush()
        self.db.add(DeliveryAssignment(delivery_request_id=delivery.delivery_request_id,driver_user_id=5))
        self.db.get(Order,result['order_id']).delivery_request_id=delivery.delivery_request_id;self.db.commit()
        active=driver_service.assigned_delivery_detail(self.db,self.driver,delivery.delivery_request_id)
        self.assertEqual(active['delivery']['destination'],result['destination'])
        with self.assertRaises(HTTPException):driver_service.assigned_delivery_detail(self.db,self.customer,delivery.delivery_request_id)
        delivery.status='delivered';self.db.commit()
        self.assertIsNone(driver_service.assigned_delivery_detail(self.db,self.driver,delivery.delivery_request_id)['delivery']['destination'])
        with self.assertRaises(HTTPException):order_service.detail(self.db,self.db.get(User,3),result['order_id'],20)
    def test_checkout_dependency_and_disabled_paths(self):
        payload=self.payload()
        with patch.object(rollout,'enabled',return_value=False):
            with self.assertRaises(HTTPException):order_address_service.acceptance(self.db,self.customer,payload)
            self.assertIsNone(order_address_service.snapshot_projection(None,1))

def load_tests(loader,tests,pattern):
    from unittest import TestSuite
    return TestSuite(CheckoutTests(name) for name in CheckoutTests.__dict__ if name.startswith('test_'))

if __name__=='__main__':main()

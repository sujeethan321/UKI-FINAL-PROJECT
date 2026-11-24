"""Synthetic SQLite only; display estimates never alter stored order amounts."""
from datetime import datetime
from decimal import Decimal
from unittest import TestCase, main
from unittest.mock import patch
import reports_suite as fixtures
from app.models import Order, OrderItem, Product, ProductCategory, DriverProfile, DeliveryRequest, DeliveryAssignment, DeliveryStatusEvent, LedgerEntry
from app.schemas.order import Cart, OrderCreate
from app.services import order_service, driver_service
from app.services.delivery_estimate_service import delivery_estimate
from app.models.driver_finance import OrderFulfilmentCharge
from sqlalchemy import select, func


class RoundingTests(TestCase):
    def test_decimal_rounding(self):
        for subtotal,fee,total in [('5000.00','150.00','5150.00'),('0.50','0.02','0.52'),
                ('0.15','0.00','0.15'),('100.99','3.03','104.02'),('1.50','0.05','1.55')]:
            self.assertEqual(delivery_estimate(Decimal(subtotal)),dict(estimated_delivery_fee=fee,estimated_total_with_delivery=total))
        for value in [1.0,Decimal('NaN'),Decimal('-1')]:
            with self.assertRaises(ValueError):delivery_estimate(value)


class IntegrationTests(TestCase):
    def setUp(self):
        fixtures.ReportsTests.setUp(self)
        self.db.connection().connection.driver_connection.create_function('CHAR_LENGTH',1,len)
        for name in ('utf8mb4_unicode_ci','utf8mb4_bin'):
            self.db.connection().connection.driver_connection.create_collation(name,lambda a,b:(a>b)-(a<b))
        fixtures.base.Base.metadata.create_all(self.engine,tables=[ProductCategory.__table__,Product.__table__,
            DriverProfile.__table__,DeliveryRequest.__table__,DeliveryAssignment.__table__,DeliveryStatusEvent.__table__,Order.__table__,OrderItem.__table__]+
            ([OrderFulfilmentCharge.__table__] if getattr(fixtures.base.config.settings,'DRIVER_FINANCE_ENABLED',False) else []))
        self.db.get(fixtures.CustomerProfile,1).user_id=4
        self.db.get(fixtures.CreditAccount,1).credit_limit=Decimal('6000')
        self.db.add(Product(product_id=1,business_id=10,name='Fictional product',unit_price=Decimal('5000.00'),currency='LKR',availability_status='available',publication_status='published'))
        self.db.add(DriverProfile(user_id=5,approval_status='pending'))
        self.db.commit()
    tearDown=fixtures.ReportsTests.tearDown

    def payload(self,method='cash'):
        if not getattr(fixtures.base.config.settings,'DRIVER_FINANCE_ENABLED',False):
            return OrderCreate(business_id=10,items=[dict(product_id=1,quantity=1)],payment_method=method,request_key='estimate-only-'+method)
        if not hasattr(self,'accepted_payloads'):self.accepted_payloads={}
        if method in self.accepted_payloads:return self.accepted_payloads[method]
        cart=Cart(business_id=10,items=[dict(product_id=1,quantity=1)],fulfilment_mode='delivery')
        quote=order_service.quote(self.db,self.db.get(fixtures.base.User,4),cart)
        payload=OrderCreate(**cart.model_dump(),quote_token=quote['quote_token'],payment_method=method,request_key='estimate-only-'+method)
        self.accepted_payloads[method]=payload
        return payload

    def test_quote_and_cash_order_keep_original_payable_total(self):
        customer=self.db.get(fixtures.base.User,4)
        result=order_service.quote(self.db,customer,Cart(business_id=10,items=[dict(product_id=1,quantity=1)]))
        self.assertEqual((result['total'],result['estimated_delivery_fee'],result['estimated_total_with_delivery']),('5000.00','150.00','5150.00'))
        with patch.object(order_service,'notify_event'):
            order=order_service.create(self.db,customer,self.payload())
            again=order_service.create(self.db,customer,self.payload())
        self.assertEqual(order['total'],'5000.00');self.assertEqual(again['order_id'],order['order_id'])
        self.assertEqual(order['payment_status'],'unpaid')
        self.assertEqual(self.db.scalar(select(func.count()).select_from(LedgerEntry)),0)
        with self.assertRaises(ValueError):OrderCreate(**{**self.payload().model_dump(),'estimated_delivery_fee':'150.00'})

    def test_credit_submission_and_approval_post_product_amount_only(self):
        customer=self.db.get(fixtures.base.User,4)
        with patch.object(order_service,'notify_event'):
            order=order_service.create(self.db,customer,self.payload('credit'))
        self.assertEqual(order['payment_status'],'pending')
        self.assertEqual(self.db.scalar(select(func.count()).select_from(LedgerEntry)),0)
        with patch.object(order_service,'notify_event'),patch('app.services.shop_owner_credit_sale_service.notify_event'):
            approved=order_service.decide(self.db,self.user,order['order_id'],'approve',10)
        self.assertEqual(approved['total'],'5000.00')
        self.assertEqual(self.db.get(LedgerEntry,approved['credit_sale_id']).amount,Decimal('5000.00'))

    def test_linked_active_order_only_scoped_no_duplicate_or_history_earning(self):
        for ident in (1,2,3):
            self.db.add(DeliveryRequest(delivery_request_id=ident,reference='EST-'+str(ident),business_id=10,created_by=2,pickup_area='Fictional A',delivery_area='Fictional B',status='assigned'))
            self.db.flush()
            self.db.add(DeliveryAssignment(delivery_request_id=ident,driver_user_id=5))
        self.db.add(Order(order_id=1,reference='EST-ORDER',customer_user_id=4,business_id=10,request_key='estimate-fixture-1',request_hash='a'*64,
            payment_method='cash',payment_status='unpaid',status='processing',subtotal=Decimal('5000'),total=Decimal('5000'),delivery_request_id=1))
        self.db.add(Order(order_id=2,reference='EST-ORDER-2',customer_user_id=4,business_id=10,request_key='estimate-fixture-2',request_hash='b'*64,
            payment_method='cash',payment_status='unpaid',status='processing',subtotal=Decimal('100.50'),total=Decimal('100.50'),delivery_request_id=3))
        self.db.commit()
        rows=driver_service.assigned_deliveries(self.db,self.db.get(fixtures.base.User,5),1,5)['deliveries']
        self.assertEqual(len(rows),3)
        self.assertEqual([r['estimated_delivery_earning'] for r in rows if r['delivery_request_id']==1],['150.00'])
        self.assertIsNone(next(r for r in rows if r['delivery_request_id']==2)['estimated_delivery_earning'])
        self.assertEqual(next(r for r in rows if r['delivery_request_id']==3)['estimated_delivery_earning'],'3.02')
        self.assertEqual(driver_service.assigned_deliveries(self.db,self.db.get(fixtures.base.User,4),1,5)['deliveries'],[])
        self.assertFalse(self.db.dirty)
        self.db.get(Order,1).status='cancelled';self.db.commit()
        rows=driver_service.assigned_deliveries(self.db,self.db.get(fixtures.base.User,5),1,5)['deliveries']
        self.assertIsNone(next(r for r in rows if r['delivery_request_id']==1)['estimated_delivery_earning'])
        self.db.get(DeliveryRequest,1).status='delivered'
        self.db.add(DeliveryStatusEvent(delivery_request_id=1,status='delivered',actor_user_id=5));self.db.commit()
        history=driver_service.assigned_deliveries(self.db,self.db.get(fixtures.base.User,5),1,5,history=True)['deliveries']
        self.assertEqual(len(history),1);self.assertIsNone(history[0]['estimated_delivery_earning'])


if __name__=='__main__':main(verbosity=2)

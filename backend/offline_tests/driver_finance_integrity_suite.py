"""DF-03: ephemeral SQLite and pure source tests. Networking blocked by fixtures."""
from unittest import TestCase,main
from unittest.mock import patch
from decimal import Decimal
import driver_finance_suite as base
from sqlalchemy import select,func,text,update
from sqlalchemy.exc import IntegrityError
from app.models import Order,User,DriverProfile,DeliveryRequest,DeliveryAssignment,DeliveryStatusEvent,LedgerEntry
from app.models.driver_finance import OrderFulfilmentCharge,DriverEarning,DriverFeeCollection,DriverSettlementEvent,DriverFinancialAudit
from app.services import driver_finance_service as finance,order_service,driver_service,order_delivery_service
from app.services.driver_finance_states import check_transition,ALLOWED
from app.services.driver_finance_rollout import require_ready,enabled
from app.schemas.order import OrderCreate
from app.routers.driver_finance import Collection,Verification


class IntegrityTests(base.FinanceTests):
    setUp=base.FinanceTests.setUp
    tearDown=base.FinanceTests.tearDown
    payload=base.FinanceTests.payload
    completed=base.FinanceTests.completed
    declaration=base.FinanceTests.declaration

    def another_earning(self):
        with patch.object(order_service,'notify_event'):
            order=order_service.create(self.db,self.db.get(User,4),self.payload().model_copy(update={'request_key':'second-order-request'}))
        delivery=DeliveryRequest(reference='SECOND-FICTIONAL',business_id=10,created_by=2,pickup_area='Shop',delivery_area='Customer',status='delivered')
        self.db.add(delivery);self.db.flush()
        self.db.get(Order,order['order_id']).delivery_request_id=delivery.delivery_request_id
        assignment=DeliveryAssignment(delivery_request_id=delivery.delivery_request_id,driver_user_id=5)
        event=DeliveryStatusEvent(delivery_request_id=delivery.delivery_request_id,actor_user_id=5,status='delivered')
        self.db.add_all([assignment,event]);self.db.commit()
        return dict(order_id=order['order_id'],delivery_request_id=delivery.delivery_request_id,assignment_id=assignment.assignment_id,
            completion_event_id=event.event_id,driver_user_id=5,amount=Decimal('150.00'))

    def test_database_rejects_missing_wrong_collection_and_wrong_amount(self):
        first=self.completed();data=finance.operation(self.db,self.driver,first.earning_id,self.declaration(first));self.db.commit()
        collection_id=data['collections'][0]['collection_id']
        fields=self.another_earning();second=DriverEarning(**fields);self.db.add(second);self.db.commit()
        for values in [dict(collection_id=None,collection_kind='declared',amount='150'),
                       dict(collection_id=collection_id,collection_kind='declared',amount='150'),
                       dict(collection_id=None,collection_kind=None,amount='150')]:
            row=DriverSettlementEvent(earning_id=second.earning_id,actor_user_id=1,kind='direct_settled',settlement_slot=1,
                sequence_no=1,
                evidence='Independent fictional evidence',request_key='bad-settlement-00001',request_hash='a'*64,**values)
            self.db.add(row)
            with self.assertRaises(IntegrityError):self.db.flush()
            self.db.rollback()
        row=DriverFeeCollection(earning_id=second.earning_id,actor_user_id=5,kind='declared',declaration_slot=1,declared_amount=Decimal('149.99'),
            amount=Decimal('149.99'),evidence='Fictional partial receipt',request_key='bad-full-amount-00001',request_hash='b'*64)
        self.db.add(row)
        with self.assertRaises(IntegrityError):self.db.flush()
        self.db.rollback()

    def test_database_binds_completion_actor_and_fee_basis(self):
        self.completed();fields=self.another_earning()
        self.db.add(User(user_id=6,full_name='Fictional Driver',email='driver6@example.invalid',password_hash='unused',platform_role='driver',account_status='active'))
        self.db.flush();self.db.add(DriverProfile(user_id=6,approval_status='pending'));self.db.commit()
        for changes in [dict(driver_user_id=6),dict(amount=Decimal('149.99')),dict(completion_status='picked_up'),dict(charge_mode='pickup')]:
            self.db.add(DriverEarning(**(fields|changes)))
            with self.assertRaises(IntegrityError):self.db.flush()
            self.db.rollback()

    def test_typed_audit_cannot_misattribute_an_event(self):
        earning=self.completed();result=finance.operation(self.db,self.driver,earning.earning_id,self.declaration(earning));self.db.commit()
        row=DriverFinancialAudit(earning_id=earning.earning_id,actor_user_id=2,action='declared',collection_id=result['collections'][0]['collection_id'])
        self.db.add(row)
        with self.assertRaises(IntegrityError):self.db.flush()
        self.db.rollback()

    def test_orm_bulk_and_raw_sql_changes_are_blocked(self):
        earning=self.completed();identifier=earning.earning_id
        with self.assertRaises(ValueError):self.db.execute(update(DriverEarning).where(DriverEarning.earning_id==identifier).values(amount=Decimal('1')))
        self.db.rollback()
        for sql in ['UPDATE driver_earnings SET amount=amount','DELETE FROM driver_earnings']:
            with self.assertRaises(IntegrityError):self.db.connection().exec_driver_sql(sql)
            self.db.rollback()
        self.assertEqual(self.db.get(DriverEarning,identifier).amount,Decimal('150.00'))

    def test_refund_is_terminal_and_duplicate_key_is_a_safe_replay(self):
        earning=self.completed();result=finance.operation(self.db,self.driver,earning.earning_id,self.declaration(earning));self.db.commit()
        for kind in ['direct_settled','reversed','refund_confirmed']:
            command=Verification(kind=kind,collection_id=result['collections'][0]['collection_id'] if kind=='direct_settled' else None,
                evidence='Independent full-amount evidence reviewed',request_key='state-sequence-'+kind)
            finance.operation(self.db,self.admin,earning.earning_id,command,True);self.db.commit()
        self.assertEqual(finance.history(self.db,self.driver)['earnings'][0]['status'],'refund_confirmed')
        finance.operation(self.db,self.admin,earning.earning_id,command,True);self.db.commit()
        before=self.db.scalar(select(func.count()).select_from(DriverSettlementEvent))
        for kind in ['disputed','reversed','direct_settled']:
            with self.assertRaises(base.fixture.fixtures.HTTPException):finance.operation(self.db,self.admin,earning.earning_id,
                Verification(kind=kind,evidence='New action cannot contradict refund',request_key='terminal-block-'+kind),True)
            self.db.rollback()
        self.assertEqual(self.db.scalar(select(func.count()).select_from(DriverSettlementEvent)),before)
        self.assertEqual(finance.history(self.db,self.driver)['summary']['available'],'0.00')

    def test_enabled_missing_or_wrong_revision_fails_closed(self):
        require_ready(self.db)
        self.db.connection().exec_driver_sql("UPDATE alembic_version SET version_num='unreviewed-revision'")
        with self.assertRaises(base.fixture.fixtures.HTTPException) as caught:require_ready(self.db)
        self.assertEqual(caught.exception.detail['code'],'DRIVER_FINANCE_SCHEMA_NOT_READY');self.db.rollback()

    def test_attestation_required_before_enabled_schema_access(self):
        with patch.object(base.fixture.fixtures.base.config.settings,'DRIVER_FINANCE_DBA_ATTESTED_REVISION',None):
            with self.assertRaises(base.fixture.fixtures.HTTPException) as error:require_ready(self.db)
            self.assertEqual(error.exception.detail['code'],'DRIVER_FINANCE_SCHEMA_NOT_READY')

    def test_illegal_inserted_event_sequence_is_not_silently_projected(self):
        earning=self.completed();result=finance.operation(self.db,self.driver,earning.earning_id,self.declaration(earning));self.db.commit()
        for kind in ('direct_settled','refund_confirmed'):
            finance.operation(self.db,self.admin,earning.earning_id,Verification(kind=kind,
                collection_id=result['collections'][0]['collection_id'] if kind=='direct_settled' else None,
                evidence='Independent immutable evidence reference',request_key='sequence-fixture-'+kind),True);self.db.commit()
        # An INSERT outside the reviewed service boundary can still be attempted;
        # the read projection must reject the impossible post-refund transition.
        row=DriverSettlementEvent(earning_id=earning.earning_id,actor_user_id=1,kind='disputed',amount=earning.amount,
            sequence_no=3,previous_sequence_no=2,evidence='Synthetic invalid sequence',request_key='invalid-sequence-fixture',request_hash='e'*64)
        self.db.add(row);self.db.commit()
        with self.assertRaises(base.fixture.fixtures.HTTPException):finance.history(self.db,self.driver)


class StateTests(TestCase):
    def test_complete_transition_matrix_and_unverified_refunds(self):
        actions={'declared','exception','direct_settled','disputed','reversed','refund_confirmed'}
        for state,allowed in ALLOWED.items():
            for action in actions:
                if action in allowed:check_transition(state,action,verified=True)
                else:
                    with self.assertRaises(base.fixture.fixtures.HTTPException):check_transition(state,action,verified=True)
        with self.assertRaises(base.fixture.fixtures.HTTPException):check_transition('refund_pending','refund_confirmed',verified=False)


class LegacyGateTests(base.fixture.IntegrationTests):
    def setUp(self):
        off=patch.object(base.fixture.fixtures.base.config.settings,'DRIVER_FINANCE_ENABLED',False,create=True)
        off.start();self.addCleanup(off.stop);super().setUp()
    def test_disabled_gate_uses_no_finance_tables_for_order_reads_and_completion(self):
        self.assertFalse(enabled())
        from sqlalchemy import event,inspect
        self.assertNotIn('driver_earnings',inspect(self.engine).get_table_names())
        self.assertNotIn('order_fulfilment_charges',inspect(self.engine).get_table_names())
        statements=[]
        def capture(conn,cursor,sql,params,ctx,many):statements.append(sql.lower())
        event.listen(self.engine,'before_cursor_execute',capture)
        with patch.object(order_service,'notify_event'):
            result=order_service.create(self.db,self.db.get(User,4),self.payload())
        self.assertFalse(result['finance_enabled']);self.assertIsNone(result['delivery_fee'])
        order_service.detail(self.db,self.db.get(User,4),result['order_id'])
        order_service.listing(self.db,self.db.get(User,4),1,10)
        profile=self.db.get(DriverProfile,5);profile.approval_status='approved';profile.vehicle_type='Bike';profile.registration_reference='LEGACY'
        profile.reviewed_by=1;profile.reviewed_at=base.fixture.datetime(2026,1,1);profile.legacy_document_exempt=True
        delivery=DeliveryRequest(reference='LEGACY-COMPLETE',business_id=10,created_by=2,pickup_area='Shop',delivery_area='Customer',status='in_transit')
        self.db.add(delivery);self.db.flush();self.db.add(DeliveryAssignment(delivery_request_id=delivery.delivery_request_id,driver_user_id=5));self.db.commit()
        with patch('app.services.notification_service.notify_event'):driver_service.transition_delivery(self.db,5,delivery.delivery_request_id,'delivered','in_transit')
        self.db.commit()
        self.assertFalse(any(any(name in sql for name in ('driver_earnings','order_fulfilment_charges','driver_settlement_events','driver_fee_collections','driver_financial_audits')) for sql in statements))
        with self.assertRaises(base.fixture.fixtures.HTTPException) as error:finance.history(self.db,self.db.get(User,5))
        self.assertEqual(error.exception.detail['code'],'DRIVER_FINANCE_NOT_ENABLED')
        with patch.multiple(base.fixture.fixtures.base.config.settings,DRIVER_FINANCE_ENABLED=True,DRIVER_FINANCE_DBA_ATTESTED_REVISION='bf38d2a90176',create=True):
            with self.assertRaises(base.fixture.fixtures.HTTPException) as error:require_ready(self.db)
            self.assertEqual(error.exception.detail['code'],'DRIVER_FINANCE_SCHEMA_NOT_READY')


if __name__=='__main__':main(verbosity=2)

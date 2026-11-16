"""Independent MySQL connections arbitrate linked delivery creation and lifecycle races."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from uuid import uuid4
from sqlalchemy import select, delete, update, event, text, func
from sqlalchemy.orm import Session
import pytest
from app.core.database import engine
from app.core.config import settings
from app.core.security import create_access_token
from app.models import (Order, DeliveryRequest, DeliveryAssignment, DeliveryStatusEvent,
                        Notification, DriverProfile, User, LedgerEntry)
from app.services import driver_service
from test_orders_concurrency import committed_orders, post

AREAS = dict(pickup_area='Pickup district', delivery_area='Destination district')


@pytest.fixture
def committed_fulfilment(committed_orders):
    ctx = committed_orders; users = []; ctx['delivery_users'] = users
    try:
        result = post(ctx, 'customer/orders', dict(business_id=ctx['bid'],
            items=[dict(product_id=ctx['pid'],quantity=1)],payment_method='cash',request_key=uuid4().hex))
        assert result.status_code == 201, result.text
        ctx['order'] = result.json()['order_id']
        assert post(ctx, f'shop-owner/orders/{ctx["order"]}/decision', {'action':'process'}, True).status_code == 200
        with Session(engine) as db:
            for role in ['driver','admin']:
                row = User(full_name='Linked delivery race '+role,email=uuid4().hex+'@example.com',
                    password_hash='test-fixture-disabled',platform_role=role,account_status='active')
                db.add(row); db.flush(); users.append(row.user_id)
            ctx['driver'] = users[0]; ctx['driver_admin'] = users[1]
            driver_service.create_profile(db,users[0],'van','TEST-ONLY')
            driver_service.review_profile(db,users[1],users[0],'approved'); db.commit()
        yield ctx
    finally:
        # Delete only this fixture's records, before the parent order fixture.
        if settings.MYSQL_DATABASE != engine.url.database or engine.url.database != 'lankapex_test_db':
            raise RuntimeError('Test database required')
        with engine.begin() as db:
            if db.scalar(text('SELECT DATABASE()')) != 'lankapex_test_db': raise RuntimeError('Test database required')
            ids = list(db.scalars(select(DeliveryRequest.delivery_request_id).where(DeliveryRequest.business_id==ctx['bid'])))
            db.execute(delete(Notification).where(Notification.business_id==ctx['bid']))
            db.execute(delete(DeliveryStatusEvent).where(DeliveryStatusEvent.delivery_request_id.in_(ids)))
            db.execute(delete(DeliveryAssignment).where(DeliveryAssignment.delivery_request_id.in_(ids)))
            db.execute(update(Order).where(Order.business_id==ctx['bid']).values(delivery_request_id=None))
            db.execute(delete(DeliveryRequest).where(DeliveryRequest.business_id==ctx['bid']))
            if users:
                db.execute(delete(DriverProfile).where(DriverProfile.user_id.in_(users)))
                db.execute(delete(User).where(User.user_id.in_(users)))


def bridge(ctx,payload=None):
    return post(ctx,f'shop-owner/orders/{ctx["order"]}/delivery',payload or AREAS,True)


def race(model, ident, calls):
    attempted=Event(); mutex=Lock(); attempts=0
    def observe(conn,cursor,sql,params,context,many):
        nonlocal attempts
        if 'FROM '+model.__tablename__ in sql and 'FOR UPDATE' in sql:
            with mutex:
                attempts += 1
                if attempts >= 2: attempted.set()
    with engine.connect() as blocker:
        transaction=blocker.begin()
        blocker.execute(select(model.__mapper__.primary_key[0]).where(model.__mapper__.primary_key[0]==ident).with_for_update()).all()
        event.listen(engine,'before_cursor_execute',observe)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(call) for call in calls]
                try:
                    assert attempted.wait(20),'Both independent requests must reach the locked row'
                    assert all(not future.done() for future in futures)
                finally: transaction.rollback()
                return [future.result(timeout=30) for future in futures]
        finally: event.remove(engine,'before_cursor_execute',observe)


@pytest.mark.parametrize('conflicting',[False,True])
def test_simultaneous_delivery_requests_link_at_most_one(committed_fulfilment,conflicting):
    c=committed_fulfilment
    responses=race(Order,c['order'],[lambda:bridge(c), lambda:bridge(c,{**AREAS,'delivery_area':'Other destination'} if conflicting else AREAS)])
    assert sorted(r.status_code for r in responses)==([201,409] if conflicting else [201,201])
    with Session(engine) as db:
        rows=list(db.scalars(select(DeliveryRequest).where(DeliveryRequest.business_id==c['bid'])))
        assert len(rows)==1 and rows[0].status=='available'
        requested=list(db.scalars(select(Notification).where(Notification.business_id==c['bid'],Notification.notification_type=='delivery_requested')))
        assert len(requested)==1 and requested[0].recipient_user_id==c['customer']
        assert requested[0].related_entity_type=='order' and requested[0].related_entity_id==c['order']
        assert db.get(Order,c['order']).delivery_request_id==rows[0].delivery_request_id
        assert db.scalar(select(func.count()).select_from(LedgerEntry).where(LedgerEntry.order_id==c['order']))==0
    if not conflicting:
        assert responses[0].json()['delivery']['delivery_request_id']==responses[1].json()['delivery']['delivery_request_id']


def test_order_completion_and_delivery_creation_are_serialized(committed_fulfilment):
    c=committed_fulfilment
    responses=race(Order,c['order'],[lambda:bridge(c),lambda:post(c,f'shop-owner/orders/{c["order"]}/decision',{'action':'complete'},True)])
    assert responses[1].status_code==200 and responses[0].status_code in (201,409)
    with Session(engine) as db:
        order=db.get(Order,c['order']); count=db.scalar(select(func.count()).select_from(DeliveryRequest).where(DeliveryRequest.business_id==c['bid']))
        assert order.status=='completed' and order.payment_status=='unpaid'
        assert count==(1 if responses[0].status_code==201 else 0)
        assert (order.delivery_request_id is not None)==(count==1)


def test_linked_request_assignment_vs_cancellation_uses_existing_atomic_rules(committed_fulfilment):
    c=committed_fulfilment; created=bridge(c); assert created.status_code==201
    ident=created.json()['delivery']['delivery_request_id']
    def accept():
        return c['client'].post(f'/api/v1/driver/jobs/{ident}/accept',json={},
            headers={'Authorization':'Bearer '+create_access_token(c['driver'])})
    responses=race(DeliveryRequest,ident,[accept,lambda:post(c,f'shop-owner/deliveries/{ident}/cancel',{},True)])
    assert sorted(r.status_code for r in responses)==[200,409]
    with Session(engine) as db:
        row=db.get(DeliveryRequest,ident)
        assigned=db.scalar(select(DeliveryAssignment).where(DeliveryAssignment.delivery_request_id==ident))
        cancelled=db.scalar(select(DeliveryStatusEvent).where(DeliveryStatusEvent.delivery_request_id==ident,DeliveryStatusEvent.status=='cancelled'))
        assigned_alerts=list(db.scalars(select(Notification).where(Notification.business_id==c['bid'],Notification.notification_type=='delivery_assigned')))
        cancelled_alerts=list(db.scalars(select(Notification).where(Notification.business_id==c['bid'],Notification.notification_type=='delivery_cancelled')))
        if row.status=='assigned':
            assert assigned is not None and cancelled is None and not cancelled_alerts
            assert len(assigned_alerts)==3 and {n.recipient_user_id for n in assigned_alerts}=={c['owner'],c['customer'],c['driver']}
        else:
            assert row.status=='cancelled' and assigned is None and cancelled is not None and not assigned_alerts
            assert len(cancelled_alerts)==1 and cancelled_alerts[0].recipient_user_id==c['customer']
        assert db.get(Order,c['order']).delivery_request_id==ident
    replay=bridge(c); assert replay.status_code==201 and replay.json()['delivery']['delivery_request_id']==ident


def test_concurrent_notification_upsert_keeps_one_read_record(committed_fulfilment):
    from threading import Barrier
    from app.services.notification_service import notify_event, utc_now
    c=committed_fulfilment; did=bridge(c).json()['delivery']['delivery_request_id']
    with Session(engine) as db:
        record=db.scalar(select(Notification).where(Notification.business_id==c['bid'],Notification.notification_type=='delivery_requested'))
        record.is_read=True; record.read_at=utc_now(); db.commit(); first=(record.notification_id,record.created_at,record.read_at)
    barrier=Barrier(2)
    def emit():
        with Session(engine) as db:
            barrier.wait(timeout=10); ids=notify_event(db,'delivery_requested',did); db.commit(); return ids
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(emit) for _ in range(2)]; results=[f.result(timeout=30) for f in futures]
    assert results[0]==results[1]==[first[0]]
    with Session(engine) as db:
        rows=list(db.scalars(select(Notification).where(Notification.business_id==c['bid'],Notification.notification_type=='delivery_requested')))
        assert len(rows)==1 and rows[0].is_read and (rows[0].notification_id,rows[0].created_at,rows[0].read_at)==first


def test_two_driver_race_notifies_only_persisted_winner(committed_fulfilment):
    c=committed_fulfilment; did=bridge(c).json()['delivery']['delivery_request_id']
    with Session(engine) as db:
        driver=User(full_name='Other race driver',email=uuid4().hex+'@example.com',password_hash='disabled-fixture',platform_role='driver',account_status='active')
        db.add(driver); db.flush(); other=driver.user_id; c['delivery_users'].append(other)
        driver_service.create_profile(db,other,'van','TEST-ONLY')
        driver_service.review_profile(db,c['driver_admin'],other,'approved'); db.commit()
    def accept(uid):
        return c['client'].post(f'/api/v1/driver/jobs/{did}/accept',json={},headers={'Authorization':'Bearer '+create_access_token(uid)})
    responses=race(DeliveryRequest,did,[lambda:accept(c['driver']),lambda:accept(other)])
    assert sorted(r.status_code for r in responses)==[200,409]
    with Session(engine) as db:
        assigned=db.scalar(select(DeliveryAssignment).where(DeliveryAssignment.delivery_request_id==did))
        rows=list(db.scalars(select(Notification).where(Notification.business_id==c['bid'],Notification.notification_type=='delivery_assigned')))
        assert len(rows)==3 and {n.recipient_user_id for n in rows}=={c['owner'],c['customer'],assigned.driver_user_id}
        loser=other if assigned.driver_user_id==c['driver'] else c['driver']
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.recipient_user_id==loser))==0


def test_assignment_resolves_new_order_link_despite_old_auth_snapshot(committed_fulfilment):
    c=committed_fulfilment
    with Session(engine) as old_reader:
        assert old_reader.get(Order,c['order']).delivery_request_id is None
        did=bridge(c).json()['delivery']['delivery_request_id']
        driver_service.accept_delivery(old_reader,c['driver'],did); old_reader.commit()
    with Session(engine) as db:
        rows=list(db.scalars(select(Notification).where(Notification.business_id==c['bid'],Notification.notification_type=='delivery_assigned')))
        assert len(rows)==3 and {n.recipient_user_id for n in rows}=={c['owner'],c['customer'],c['driver']}
        customer=next(n for n in rows if n.recipient_user_id==c['customer'])
        assert (customer.related_entity_type,customer.related_entity_id)==('order',c['order'])

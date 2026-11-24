"""Real JWT/database coordination through existing order and delivery services."""
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import pytest
from app.models import Notification, DeliveryRequest, Order, BusinessMember
from app.services.notification_service import notify_event
from test_order_delivery import shop, api, db, ready, create, approved_driver, finance
from test_catalogue import request
from test_orders import decision


def notices(s, kind):
    return list(s['db'].scalars(select(Notification).where(
        Notification.business_id == s['business'], Notification.notification_type == kind)))


def test_order_delivery_journey_has_exact_recipients_safe_links_and_no_financial_side_effects(shop):
    s=shop; ident=ready(s,'credit','approved')
    assert {n.recipient_user_id for n in notices(s,'order_submitted')} == {s['owner'].user_id}
    assert {n.recipient_user_id for n in notices(s,'order_approved')} == {s['user'].user_id}
    assert decision(s,ident,'process').status_code == 200
    assert {n.recipient_user_id for n in notices(s,'order_processing')} == {s['user'].user_id}
    before=finance(s); delivery=create(s,ident).json()['delivery']; did=delivery['delivery_request_id']
    requested=notices(s,'delivery_requested')
    assert len(requested)==1 and requested[0].recipient_user_id==s['user'].user_id
    assert (requested[0].related_entity_type,requested[0].related_entity_id)==('order',ident)
    first=requested[0]; first.is_read=True; from app.services.notification_service import utc_now
    first.read_at=utc_now(); s['db'].flush(); stamp=first.created_at
    assert create(s,ident).status_code==201
    assert notices(s,'delivery_requested')[0].is_read and len(notices(s,'delivery_requested'))==1
    assert notices(s,'delivery_requested')[0].created_at==stamp
    driver=approved_driver(s)
    assert request(s,f'/driver/jobs/{did}/accept','post',{},actor=driver).status_code==200
    assert request(s,f'/driver/jobs/{did}/accept','post',{},actor=driver).status_code==200
    for old,new in [('assigned','picked_up'),('picked_up','in_transit'),('in_transit','delivered')]:
        assert request(s,f'/driver/deliveries/{did}/status','post',dict(expected_status=old,status=new),actor=driver).status_code==200
        rows=notices(s,'delivery_'+new)
        assert {n.recipient_user_id for n in rows}=={s['owner'].user_id,s['user'].user_id}
        customer=next(n for n in rows if n.recipient_user_id==s['user'].user_id)
        assert (customer.related_entity_type,customer.related_entity_id)==('order',ident)
        owner=next(n for n in rows if n.recipient_user_id==s['owner'].user_id)
        assert (owner.related_entity_type,owner.related_entity_id)==('delivery_request',did)
        assert notify_event(s['db'],'delivery_'+new,did)
        assert len(notices(s,'delivery_'+new))==2
    assigned=notices(s,'delivery_assigned')
    assert {n.recipient_user_id for n in assigned}=={s['owner'].user_id,s['user'].user_id,driver.user_id}
    assert len(assigned)==3
    assert finance(s)==before
    for n in s['db'].scalars(select(Notification).where(Notification.business_id==s['business'])):
        assert all(value not in n.message+n.title for value in ['PRIVATE','250.50','077','@','pickup district'])
    assert 'marked as delivered by the driver' in notices(s,'delivery_delivered')[0].message
    assert request(s,'/notifications',actor='other').json()['total']==0
    assert request(s,'/notifications',actor='other_owner').json()['total']==0


@pytest.mark.parametrize('canceller',['creator','coowner'])
def test_cancellation_notifies_customer_and_other_active_owners_once_without_reversing_credit(shop,canceller):
    s=shop; coowner=s['make_user']('shop_owner')
    s['db'].add(BusinessMember(business_id=s['business'],user_id=coowner.user_id,business_role='owner',membership_status='active'));s['db'].flush()
    ident=ready(s,'credit','approved'); before=finance(s); did=create(s,ident).json()['delivery']['delivery_request_id']
    for _ in range(2):
        assert request(s,f'/shop-owner/deliveries/{did}/cancel','post',{},actor='owner' if canceller=='creator' else coowner,business_id=s['business']).status_code==200
    rows=notices(s,'delivery_cancelled')
    assert len(rows)==2 and {n.recipient_user_id for n in rows}=={s['user'].user_id,coowner.user_id if canceller=='creator' else s['owner'].user_id}
    assert finance(s)==before
    assert create(s,ident).json()['delivery']['status']=='cancelled'
    assert len(notices(s,'delivery_requested'))==1
    assert len(notices(s,'delivery_cancelled'))==2


@pytest.mark.parametrize('status',['suspended','inactive'])
def test_inactive_customer_is_not_a_delivery_recipient(shop,status):
    s=shop; ident=ready(s,status='processing')
    # User account statuses permit active/suspended; a different platform role
    # likewise makes the persisted user ineligible for Customer delivery alerts.
    if status=='suspended': s['user'].account_status='suspended'
    else: s['user'].platform_role='driver'
    s['db'].flush()
    assert create(s,ident).status_code==201
    assert notices(s,'delivery_requested')==[]


@pytest.mark.parametrize('failure',['notification','commit'])
def test_failed_creation_leaves_no_delivery_link_or_success_notification(shop,monkeypatch,failure):
    s=shop; ident=ready(s,status='processing'); before=finance(s)
    def fail(*args,**kwargs): raise SQLAlchemyError('PRIVATE diagnostics')
    if failure=='commit': monkeypatch.setattr(Session,'commit',fail)
    else: monkeypatch.setattr('app.services.notification_service.notify_event',fail)
    response=create(s,ident)
    assert response.status_code==503 and 'PRIVATE' not in response.text
    assert s['db'].get(Order,ident).delivery_request_id is None
    assert s['db'].scalar(select(func.count()).select_from(DeliveryRequest))==0
    assert notices(s,'delivery_requested')==[] and finance(s)==before


def test_recipient_owned_read_endpoints_and_updates_cannot_change_financial_records(shop):
    s=shop; ident=ready(s,status='processing'); create(s,ident); before=finance(s)
    row=notices(s,'delivery_requested')[0]
    for actor in ['other','other_owner',s['make_user']('driver')]:
        assert request(s,f'/notifications/{row.notification_id}/read','patch',actor=actor).status_code==404
    assert request(s,'/notifications',actor='user',notification_type='delivery_requested').json()['total']==1
    assert request(s,f'/notifications/{row.notification_id}/read','patch',actor='user').status_code==200
    assert request(s,'/notifications/read-all','patch',actor='user').status_code==200
    assert request(s,'/notifications/unread-count',actor='user').json()['unread_count']==0
    assert finance(s)==before


def test_missing_transition_or_order_link_cannot_fabricate_notifications(shop):
    s=shop; ident=ready(s,status='processing'); did=create(s,ident).json()['delivery']['delivery_request_id']
    with pytest.raises(ValueError): notify_event(s['db'],'delivery_cancelled',did)
    with pytest.raises(ValueError): notify_event(s['db'],'delivery_assigned',did)
    assert notices(s,'delivery_cancelled')==[] and notices(s,'delivery_assigned')==[]


def test_cancel_commit_failure_rolls_back_event_and_alerts(shop,monkeypatch):
    s=shop; ident=ready(s,status='processing'); did=create(s,ident).json()['delivery']['delivery_request_id']; before=finance(s)
    def fail(*args,**kwargs): raise SQLAlchemyError('PRIVATE commit failure')
    monkeypatch.setattr(Session,'commit',fail)
    response=request(s,f'/shop-owner/deliveries/{did}/cancel','post',{},business_id=s['business'])
    assert response.status_code==503 and 'PRIVATE' not in response.text
    assert s['db'].get(DeliveryRequest,did).status=='available'
    assert notices(s,'delivery_cancelled')==[] and finance(s)==before


def test_existing_internal_assigned_cancellation_alerts_affected_driver_without_public_bypass(shop):
    from app.services import driver_service
    s=shop; ident=ready(s,status='processing'); did=create(s,ident).json()['delivery']['delivery_request_id']; driver=approved_driver(s)
    assert request(s,f'/driver/jobs/{did}/accept','post',{},actor=driver).status_code==200
    assert request(s,f'/shop-owner/deliveries/{did}/cancel','post',{},business_id=s['business']).status_code==409
    before=finance(s)
    driver_service.cancel_business_delivery(s['db'],s['owner'].user_id,s['business'],did)
    assert {n.recipient_user_id for n in notices(s,'delivery_cancelled')}=={s['user'].user_id,driver.user_id}
    assert finance(s)==before

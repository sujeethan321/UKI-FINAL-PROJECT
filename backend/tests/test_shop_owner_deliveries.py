"""Real JWT and MySQL Shop Owner delivery creation/management contracts."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from sqlalchemy import func, select, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models import (Business, BusinessMember, DeliveryRequest, DeliveryAssignment, DeliveryStatusEvent,
                        CreditAccount, LedgerEntry, PaymentReminder, Notification)
from app.services import driver_service
from app.services import shop_owner_delivery_service as service
from test_driver_dashboard import ctx, api, db, approve, request
from test_customer_dashboard import make_business, entry

ROOT = '/api/v1/shop-owner/deliveries'
AREAS = {'pickup_area':'Pickup district', 'delivery_area':'Destination district'}


@pytest.fixture
def owner_api(ctx):
    ctx['headers'] = {'Authorization':'Bearer '+create_access_token(ctx['owner'].user_id)}
    return ctx


def create(ctx, payload=None, business=None):
    return ctx['client'].post(ROOT, headers=ctx['headers'], params={'business_id':business or ctx['business']},
                              json=AREAS if payload is None else payload)


def read(ctx, suffix='', **params):
    return ctx['client'].get(ROOT+suffix, headers=ctx['headers'], params={'business_id':ctx['business'], **params})


def cancel(ctx, ident, **params):
    return ctx['client'].post(ROOT+f'/{ident}/cancel', headers=ctx['headers'],
                              params={'business_id':ctx['business'], **params}, json={})


def test_owner_creates_available_request_without_order_and_driver_can_accept(owner_api):
    ctx=owner_api;approve(ctx)
    response=create(ctx, {'pickup_area':'  Colombo & <shop> "A"  ', 'delivery_area':'யாழ்ப்பாணம் — North'})
    assert response.status_code==201 and response.headers['cache-control']=='no-store'
    data=response.json();ident=data['delivery_request_id']
    assert data['business_id']==ctx['business'] and data['status']=='available' and data['can_cancel'] is True
    assert data['pickup_area']=='Colombo & <shop> "A"' and data['delivery_area']=='யாழ்ப்பாணம் — North'
    assert data['assigned_driver'] is None and data['events']==[]
    assert ctx['db'].get(DeliveryRequest,ident).created_by==ctx['owner'].user_id
    assert read(ctx,f'/{ident}').json()==data
    headers={'Authorization':'Bearer '+create_access_token(ctx['driver'].user_id)}
    jobs=ctx['client'].get('/api/v1/driver/jobs',headers=headers).json()
    assert jobs['total']==1 and jobs['jobs'][0]['delivery_request_id']==ident
    accepted=ctx['client'].post(f'/api/v1/driver/jobs/{ident}/accept',headers=headers,json={})
    assert accepted.status_code==200
    assert ctx['client'].get('/api/v1/driver/jobs',headers=headers).json()['total']==0
    detail=read(ctx,f'/{ident}').json()
    assert detail['status']=='assigned' and detail['can_cancel'] is False
    assert detail['assigned_driver']=={'full_name':ctx['driver'].full_name,'assigned_at':accepted.json()['delivery']['assigned_at']}
    assert detail['events']==[{'status':'assigned','occurred_at':accepted.json()['delivery']['assigned_at']}]
    assert set(detail)=={'delivery_request_id','reference','business_id','pickup_area','delivery_area','status',
                        'created_at','updated_at','assigned_driver','events','can_cancel'}
    for key in ['email','phone','password','registration_reference','reviewed_by','credit_limit','outstanding_balance','earnings']:
        assert key not in str(detail)


@pytest.mark.parametrize('role',[None,'driver','customer','admin'])
def test_all_routes_require_verified_shop_owner_role(owner_api,role):
    ctx=owner_api
    ctx['headers']={} if role is None else {'Authorization':'Bearer '+create_access_token(ctx['make_user'](role).user_id)}
    for response in [create(ctx),read(ctx),read(ctx,'/1'),cancel(ctx,1)]:
        assert response.status_code==(401 if role is None else 403)


def test_expired_invalid_and_suspended_accounts_are_rejected(owner_api):
    ctx=owner_api
    token=jwt.encode({'sub':str(ctx['owner'].user_id),'type':'access','iat':datetime.now(timezone.utc)-timedelta(minutes=3),
        'exp':datetime.now(timezone.utc)-timedelta(seconds=1)},settings.JWT_SECRET_KEY,algorithm='HS256')
    for token in [token,'invalid']:
        ctx['headers']={'Authorization':'Bearer '+token}
        assert create(ctx).status_code==401 and read(ctx).status_code==401
    ctx['headers']={'Authorization':'Bearer '+create_access_token(ctx['owner'].user_id)}
    ctx['owner'].account_status='suspended';ctx['db'].flush()
    assert create(ctx).status_code==403 and read(ctx).status_code==403


@pytest.mark.parametrize('state',['pending','rejected'])
def test_unapproved_business_denied_for_create_read_and_cancel(owner_api,state):
    ctx=owner_api;ident=create(ctx).json()['delivery_request_id']
    ctx['db'].get(Business,ctx['business']).approval_status=state;ctx['db'].flush()
    assert create(ctx).status_code==403 and read(ctx).status_code==403
    assert read(ctx,f'/{ident}').status_code==403 and cancel(ctx,ident).status_code==403


@pytest.mark.parametrize('restriction',['inactive','staff','foreign'])
def test_membership_owner_policy_and_cross_business_access(owner_api,restriction):
    ctx=owner_api;ident=create(ctx).json()['delivery_request_id']
    if restriction=='foreign':
        ctx['headers']={'Authorization':'Bearer '+create_access_token(ctx['make_user']('shop_owner').user_id)}
    else:
        member=ctx['db'].scalar(select(BusinessMember).where(BusinessMember.business_id==ctx['business']))
        if restriction=='inactive':member.membership_status='inactive'
        else:member.business_role='staff'
        ctx['db'].flush()
    for response in [create(ctx),read(ctx),read(ctx,f'/{ident}'),cancel(ctx,ident)]:
        assert response.status_code==404


def test_owned_business_selection_does_not_authorize_other_request_ids(owner_api):
    ctx=owner_api;ident=create(ctx).json()['delivery_request_id']
    second=make_business(ctx['db'])
    ctx['db'].add(BusinessMember(business_id=second,user_id=ctx['owner'].user_id,business_role='owner',membership_status='active'));ctx['db'].flush()
    new=create(ctx,business=second);assert new.status_code==201
    assert read(ctx,business_id=second).json()['total']==1
    assert read(ctx,f'/{ident}',business_id=second).status_code==404
    assert cancel(ctx,ident,business_id=second).status_code==404
    unrelated=make_business(ctx['db'])
    assert create(ctx,business=unrelated).status_code==404
    assert read(ctx,business_id=unrelated).status_code==404


@pytest.mark.parametrize('field,value',[('pickup_area',''),('pickup_area','   '),('pickup_area','a'*161),
    ('pickup_area','a\nb'),('delivery_area',''),('delivery_area',None),('delivery_area',False),
    ('delivery_area','a'*161),('delivery_area','a\x00b')])
def test_invalid_areas_do_not_create_requests(owner_api,field,value):
    ctx=owner_api
    assert create(ctx,{**AREAS,field:value}).status_code==422
    assert ctx['db'].scalar(select(func.count()).select_from(DeliveryRequest))==0


@pytest.mark.parametrize('extra', [{'business_id':1},{'created_by':1},{'status':'assigned'},
    {'driver_id':1},{'required_vehicle_type':'spaceship'},{'order_id':1},{'weight':-1},{'idempotency_key':'unsupported'}])
def test_unstored_fields_and_identity_or_status_injection_rejected(owner_api,extra):
    assert create(owner_api,{**AREAS,**extra}).status_code==422


def test_required_fields_boundaries_and_validated_identifiers(owner_api):
    ctx=owner_api
    assert create(ctx,{}).status_code==422
    assert create(ctx,{'pickup_area':'a'*160,'delivery_area':'b'*160}).status_code==201
    assert ctx['client'].post(ROOT,headers=ctx['headers'],json=AREAS).status_code==422
    for ident in ['bad','0','-1','9223372036854775808']:
        assert read(ctx,'/'+ident).status_code==422 and cancel(ctx,ident).status_code==422
    for params in [{'page':0},{'page_size':101},{'status':'draft'},{'business_id':0}]:
        assert read(ctx,**params).status_code==422
    assert read(ctx,'/9223372036854775807').status_code==404


def test_deterministic_pages_status_filters_and_business_isolation(owner_api):
    ctx=owner_api
    assert read(ctx).json()=={'business_id':ctx['business'],'total':0,'page':1,'page_size':10,'deliveries':[]}
    ids=[create(ctx).json()['delivery_request_id'] for _ in range(5)]
    for ident in ids:ctx['db'].get(DeliveryRequest,ident).created_at=datetime(2026,1,1)
    ctx['db'].flush();assert cancel(ctx,ids[0]).status_code==200
    a=read(ctx,page_size=2).json();b=read(ctx,page_size=2,page=2).json()
    assert a['total']==b['total']==5
    assert [r['delivery_request_id'] for r in a['deliveries']+b['deliveries']]==list(reversed(ids))[0:4]
    assert read(ctx,status='available').json()['total']==4
    assert read(ctx,status='cancelled').json()['total']==1
    assert read(ctx,page=50).json()['deliveries']==[]


def test_unassigned_cancellation_is_atomic_idempotent_and_not_available_to_drivers(owner_api):
    ctx=owner_api;approve(ctx);ident=create(ctx).json()['delivery_request_id']
    first=cancel(ctx,ident);assert first.status_code==200 and first.headers['cache-control']=='no-store'
    assert first.json()['status']=='cancelled' and first.json()['can_cancel'] is False
    assert first.json()['events'][0]['status']=='cancelled'
    assert cancel(ctx,ident).json()==first.json()
    assert ctx['db'].scalar(select(func.count()).select_from(DeliveryStatusEvent))==1
    headers={'Authorization':'Bearer '+create_access_token(ctx['driver'].user_id)}
    assert ctx['client'].get('/api/v1/driver/jobs',headers=headers).json()['total']==0
    assert ctx['client'].post(f'/api/v1/driver/jobs/{ident}/accept',headers=headers,json={}).status_code==409


def test_assigned_progress_and_completed_cancellation_restricted_with_correct_timeline(owner_api):
    ctx=owner_api;approve(ctx);ident=create(ctx).json()['delivery_request_id']
    driver_service.accept_delivery(ctx['db'],ctx['driver'].user_id,ident)
    for status in ['assigned','picked_up','in_transit','delivered']:
        if status!='assigned':driver_service.transition_delivery(ctx['db'],ctx['driver'].user_id,ident,status)
        assert cancel(ctx,ident).status_code==409
        result=read(ctx,f'/{ident}').json();assert result['status']==status and result['can_cancel'] is False
    assert [e['status'] for e in result['events']]==['assigned','picked_up','in_transit','delivered']
    assert result['events'][0]['occurred_at']==result['assigned_driver']['assigned_at']
    for method in ['put','patch']:
        assert getattr(ctx['client'],method)(ROOT+f'/{ident}',headers=ctx['headers'],params={'business_id':ctx['business']},json=AREAS).status_code==405


@pytest.mark.parametrize('operation',['create','cancel'])
def test_commit_failure_rolls_back_status_creation_and_events(owner_api,monkeypatch,operation):
    ctx=owner_api;ident=create(ctx).json()['delivery_request_id']
    def fail(*args,**kwargs):raise SQLAlchemyError('private database diagnostics')
    monkeypatch.setattr(Session,'commit',fail)
    response=create(ctx) if operation=='create' else cancel(ctx,ident)
    assert response.status_code==503 and 'private database' not in response.text
    ctx['db'].expire_all()
    assert ctx['db'].scalar(select(func.count()).select_from(DeliveryRequest))==1
    assert ctx['db'].get(DeliveryRequest,ident).status=='available'
    assert ctx['db'].scalar(select(func.count()).select_from(DeliveryStatusEvent))==0


def test_read_failures_are_sanitized_and_read_operations_do_not_write(owner_api,monkeypatch):
    ctx=owner_api;ident=create(ctx).json()['delivery_request_id'];writes=[]
    def observe(conn,cursor,sql,*args):
        if sql.lstrip().split()[0].upper() in {'INSERT','UPDATE','DELETE','REPLACE'}:writes.append(sql)
    connection=ctx['db'].connection();event.listen(connection,'before_cursor_execute',observe)
    try:
        assert read(ctx).status_code==200 and read(ctx,f'/{ident}').status_code==200
    finally:event.remove(connection,'before_cursor_execute',observe)
    assert not writes
    def fail(*args,**kwargs):raise SQLAlchemyError('private SQL')
    monkeypatch.setattr(service,'list_requests',fail)
    result=read(ctx);assert result.status_code==503 and 'private SQL' not in result.text


def test_create_and_cancel_preserve_existing_financial_records(owner_api):
    ctx=owner_api;profile,account=ctx['profile'](ctx['business'])
    entry(ctx,account,'credit_sale','200.00');entry(ctx,account,'repayment','25.00')
    stamp=datetime(2026,11,6,10)
    reminder=PaymentReminder(business_id=ctx['business'],customer_id=profile.customer_id,
        credit_account_id=account.credit_account_id,created_by=ctx['owner'].user_id,outstanding_amount='175.00',
        channel='internal',language='en',template_version='test',message='Financial fixture',
        idempotency_key=uuid4().hex,created_at=stamp,updated_at=stamp)
    ctx['db'].add(reminder);ctx['db'].flush()
    ctx['db'].add(Notification(recipient_user_id=ctx['user'].user_id,business_id=ctx['business'],
        notification_type='payment_reminder_recorded',title='Financial fixture',message='Private financial reference',
        related_entity_type='payment_reminder',related_entity_id=reminder.reminder_id,event_key=uuid4().hex,created_at=stamp))
    ctx['db'].flush()
    def snapshot():
        return [ctx['db'].execute(select(model.__table__).order_by(*model.__table__.primary_key)).all()
                for model in [CreditAccount,LedgerEntry,PaymentReminder,Notification]]
    before=snapshot();ident=create(ctx).json()['delivery_request_id']
    assert cancel(ctx,ident).status_code==200 and snapshot()==before

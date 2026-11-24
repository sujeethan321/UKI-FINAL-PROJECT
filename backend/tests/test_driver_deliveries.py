"""Driver management HTTP contracts on the guarded MySQL test database."""
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.security import create_access_token
from app.models import DeliveryRequest, DeliveryStatusEvent, CreditAccount, LedgerEntry
from app.services import driver_service as service
from test_driver_dashboard import ctx, api, db, approve, request, get, ROOT


def assigned(ctx):
    approve(ctx)
    row=request(ctx)
    service.accept_delivery(ctx['db'],ctx['driver'].user_id,row.delivery_request_id)
    return row.delivery_request_id


def update(ctx,ident,before,after):
    return ctx['client'].post(ROOT+f'/deliveries/{ident}/status',headers=ctx['headers'],
                              json=dict(expected_status=before,status=after))


def test_progress_lifecycle_timeline_counts_and_no_credit_mutation(ctx):
    _,account=ctx['profile'](ctx['business'])
    from test_customer_dashboard import entry
    entry(ctx,account,'credit_sale','125.00')
    def credit_state():
        return (ctx['db'].execute(select(CreditAccount.__table__)).all(),
                ctx['db'].execute(select(LedgerEntry.__table__)).all())
    before=credit_state();ident=assigned(ctx)
    dates=[]
    for old,new in [('assigned','picked_up'),('picked_up','in_transit'),('in_transit','delivered')]:
        response=update(ctx,ident,old,new)
        assert response.status_code==200 and response.headers['cache-control']=='no-store'
        result=response.json();assert result['delivery']['status']==new
        dates.append(result['events'][-1]['occurred_at'])
    assert [e['status'] for e in result['events']]==['assigned','picked_up','in_transit','delivered']
    assert result['allowed_next_status'] is None and dates==sorted(dates)
    persisted=list(ctx['db'].scalars(select(DeliveryStatusEvent).where(DeliveryStatusEvent.delivery_request_id==ident).order_by(DeliveryStatusEvent.event_id)))
    assert [event.status for event in persisted]==['picked_up','in_transit','delivered']
    assert [event.occurred_at.isoformat() for event in persisted]==dates
    assert get(ctx,'/deliveries').json()['total']==0
    history=get(ctx,'/history').json();assert history['total']==1
    assert history['deliveries'][0]['finished_at']==dates[-1]
    summary=get(ctx,'/dashboard/summary').json()
    assert summary['active_deliveries_count']==0 and summary['completed_deliveries_count']==1
    assert credit_state()==before


@pytest.mark.parametrize('before,after',[('assigned','in_transit'),('assigned','delivered'),('picked_up','delivered'),('in_transit','picked_up')])
def test_invalid_and_stale_transitions_do_not_write_events(ctx,before,after):
    ident=assigned(ctx)
    assert update(ctx,ident,before,after).status_code==409
    assert ctx['db'].get(DeliveryRequest,ident).status=='assigned'
    assert ctx['db'].scalar(select(func.count()).select_from(DeliveryStatusEvent))==0


def test_duplicates_terminal_and_cancelled_deliveries_are_immutable(ctx):
    ident=assigned(ctx)
    for old,new in [('assigned','picked_up'),('picked_up','in_transit'),('in_transit','delivered')]:
        assert update(ctx,ident,old,new).status_code==200
        assert update(ctx,ident,old,new).status_code==409
    assert update(ctx,ident,'assigned','picked_up').status_code==409
    cancelled=request(ctx);service.accept_delivery(ctx['db'],ctx['driver'].user_id,cancelled.delivery_request_id)
    service.cancel_business_delivery(ctx['db'],ctx['owner'].user_id,ctx['business'],cancelled.delivery_request_id)
    assert update(ctx,cancelled.delivery_request_id,'assigned','picked_up').status_code==409
    result=get(ctx,f'/deliveries/{cancelled.delivery_request_id}').json()
    assert result['allowed_next_status'] is None and result['events'][-1]['status']=='cancelled'
    assert get(ctx,'/history',status='cancelled').json()['total']==1
    assert ctx['db'].scalar(select(func.count()).select_from(DeliveryStatusEvent))==4


@pytest.mark.parametrize('path',['/history','/deliveries/1','/deliveries/1/status'])
def test_management_routes_require_verified_driver_jwt(ctx,path):
    method='post' if path.endswith('/status') else 'get'
    for role in [None,'customer','shop_owner','admin']:
        headers={} if role is None else {'Authorization':'Bearer '+create_access_token(ctx['make_user'](role).user_id)}
        response=getattr(ctx['client'],method)(ROOT+path,headers=headers,**({'json':{'expected_status':'assigned','status':'picked_up'}} if method=='post' else {}))
        assert response.status_code==(401 if role is None else 403)
    ctx['headers']={'Authorization':'Bearer invalid'}
    assert getattr(ctx['client'],method)(ROOT+path,headers=ctx['headers'],**({'json':{'expected_status':'assigned','status':'picked_up'}} if method=='post' else {})).status_code==401


def test_cross_driver_list_detail_history_and_updates_are_scoped(ctx):
    ident=assigned(ctx);approve(ctx,ctx['other_driver'])
    ctx['headers']={'Authorization':'Bearer '+create_access_token(ctx['other_driver'].user_id)}
    assert get(ctx,'/deliveries',driver_id=ctx['driver'].user_id).json()['total']==0
    assert get(ctx,'/history').json()['total']==0
    assert get(ctx,f'/deliveries/{ident}').status_code==404
    assert update(ctx,ident,'assigned','picked_up').status_code==404
    assert update(ctx,9223372036854775807,'assigned','picked_up').status_code==404


@pytest.mark.parametrize('decision',['pending','rejected','suspended'])
def test_approval_restrictions_retain_read_access_but_block_progress(ctx,decision):
    ident=assigned(ctx)
    if decision=='pending':
        from app.models import DriverProfile
        ctx['db'].get(DriverProfile,ctx['driver'].user_id).approval_status='pending';ctx['db'].flush()
    else:service.review_profile(ctx['db'],ctx['admin'].user_id,ctx['driver'].user_id,decision)
    assert update(ctx,ident,'assigned','picked_up').status_code==403
    result=get(ctx,f'/deliveries/{ident}');assert result.status_code==200 and result.json()['allowed_next_status'] is None


def test_status_commit_failure_rolls_back_state_and_event(ctx,monkeypatch):
    ident=assigned(ctx)
    def fail(*args,**kwargs):raise SQLAlchemyError('sensitive database failure')
    monkeypatch.setattr(Session,'commit',fail)
    response=update(ctx,ident,'assigned','picked_up')
    assert response.status_code==503 and 'sensitive' not in response.text
    ctx['db'].expire_all()
    assert ctx['db'].get(DeliveryRequest,ident).status=='assigned'
    assert ctx['db'].scalar(select(func.count()).select_from(DeliveryStatusEvent))==0


def test_pagination_filters_empty_states_and_missing_historical_times(ctx):
    assert get(ctx,'/history').json()['deliveries']==[]
    ident=assigned(ctx)
    for _ in range(4):
        row=request(ctx);service.accept_delivery(ctx['db'],ctx['driver'].user_id,row.delivery_request_id)
    a=get(ctx,'/deliveries',page_size=2).json();b=get(ctx,'/deliveries',page_size=2,page=2).json()
    assert a['total']==5 and len({r['delivery_request_id'] for r in a['deliveries']+b['deliveries']})==4
    assert get(ctx,'/deliveries',status='picked_up').json()['total']==0
    assert update(ctx,ident,'assigned','picked_up').status_code==200
    assert get(ctx,'/deliveries',status='picked_up').json()['total']==1
    row=ctx['db'].get(DeliveryRequest,ident);row.status='delivered';ctx['db'].flush() # legacy terminal record: no invented completion event
    result=get(ctx,'/history',status='delivered').json()
    assert result['total']==1 and result['deliveries'][0]['finished_at'] is None
    assert [e['status'] for e in get(ctx,f'/deliveries/{ident}').json()['events']]==['assigned','picked_up']
    for path,params in [('/history',{'status':'assigned'}),('/deliveries',{'status':'delivered'}),('/history',{'page':0}),('/history',{'page_size':101})]:
        assert get(ctx,path,**params).status_code==422


def test_status_payload_forbids_identity_injection_and_public_cancellation(ctx):
    ident=assigned(ctx)
    for payload in [{'expected_status':'assigned','status':'cancelled'}, {'expected_status':'assigned','status':'picked_up','driver_id':ctx['other_driver'].user_id}, {'status':'picked_up'}]:
        assert ctx['client'].post(ROOT+f'/deliveries/{ident}/status',headers=ctx['headers'],json=payload).status_code==422


def test_expired_jwt_and_inactive_account_cannot_progress_or_read_history(ctx):
    from datetime import datetime,timedelta,timezone
    import jwt
    from app.core.config import settings
    ident=assigned(ctx)
    valid=ctx['headers']
    token=jwt.encode(dict(sub=str(ctx['driver'].user_id),type='access',
        iat=datetime.now(timezone.utc)-timedelta(minutes=5),exp=datetime.now(timezone.utc)-timedelta(seconds=1)),settings.JWT_SECRET_KEY,algorithm='HS256')
    ctx['headers']={'Authorization':'Bearer '+token}
    assert update(ctx,ident,'assigned','picked_up').status_code==401
    assert get(ctx,'/history').status_code==401
    ctx['headers']=valid;ctx['driver'].account_status='suspended';ctx['db'].flush()
    assert update(ctx,ident,'assigned','picked_up').status_code==403
    assert get(ctx,'/history').status_code==403


def test_missing_stored_vehicle_blocks_progress(ctx):
    from app.models import DriverProfile
    ident=assigned(ctx);profile=ctx['db'].get(DriverProfile,ctx['driver'].user_id)
    profile.vehicle_type=None;profile.registration_reference=None;ctx['db'].flush()
    assert update(ctx,ident,'assigned','picked_up').status_code==403
    assert get(ctx,f'/deliveries/{ident}').json()['allowed_next_status'] is None

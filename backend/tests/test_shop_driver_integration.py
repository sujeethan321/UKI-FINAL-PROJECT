"""One request, two roles, real JWT/SQL transactions throughout the journey."""
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.security import create_access_token
from app.models import DeliveryRequest, DeliveryAssignment, DeliveryStatusEvent, CreditAccount, LedgerEntry
from app.services import driver_service
from test_driver_dashboard import ctx, api, db, approve
from test_customer_dashboard import entry, make_business


def call(ctx,actor,path,method='get',payload=None,**params):
    return getattr(ctx['client'],method)('/api/v1'+path,
        headers={'Authorization':'Bearer '+create_access_token(actor.user_id)},params=params,
        **({'json':payload if payload is not None else {}} if method=='post' else {}))


def create(ctx):
    result=call(ctx,ctx['owner'],'/shop-owner/deliveries','post',
        {'pickup_area':'Public pickup area','delivery_area':'Public destination area'},business_id=ctx['business'])
    assert result.status_code==201
    return result.json()


def test_complete_cross_role_journey_same_record_events_counts_and_financial_isolation(ctx):
    approve(ctx);approve(ctx,ctx['other_driver'])
    pending=ctx['make_user']('driver');driver_service.create_profile(ctx['db'],pending.user_id,'van','PENDING-TEST')
    _,account=ctx['profile'](ctx['business']);entry(ctx,account,'credit_sale','200.00');entry(ctx,account,'repayment','50.00')
    def financial():return [ctx['db'].execute(select(model.__table__).order_by(*model.__table__.primary_key)).all() for model in [CreditAccount,LedgerEntry]]
    before=financial();created=create(ctx);ident=created['delivery_request_id'];reference=created['reference']
    owner_path=f'/shop-owner/deliveries/{ident}';driver_path=f'/driver/deliveries/{ident}'
    for driver in [ctx['driver'],ctx['other_driver']]:
        jobs=call(ctx,driver,'/driver/jobs').json();assert jobs['total']==1
        assert jobs['jobs'][0]['reference']==reference and jobs['jobs'][0]['delivery_request_id']==ident
        assert set(jobs['jobs'][0])=={'delivery_request_id','reference','business_name','pickup_area','delivery_area','status','created_at'}
    assert call(ctx,pending,'/driver/jobs').status_code==403
    assert call(ctx,pending,f'/driver/jobs/{ident}/accept','post').status_code==403
    accepted=call(ctx,ctx['driver'],f'/driver/jobs/{ident}/accept','post')
    assert accepted.status_code==200 and accepted.json()['delivery']['delivery_request_id']==ident
    assert call(ctx,ctx['other_driver'],f'/driver/jobs/{ident}/accept','post').status_code==409
    assert call(ctx,ctx['other_driver'],driver_path).status_code==404
    assert call(ctx,ctx['other_driver'],driver_path+'/status','post',{'expected_status':'assigned','status':'picked_up'}).status_code==404
    assert call(ctx,ctx['driver'],'/driver/deliveries').json()['deliveries'][0]['reference']==reference
    assert call(ctx,ctx['other_driver'],'/driver/deliveries').json()['total']==0
    for driver in [ctx['driver'],ctx['other_driver']]:assert call(ctx,driver,'/driver/jobs').json()['total']==0
    owner=call(ctx,ctx['owner'],owner_path,business_id=ctx['business']).json()
    assert owner['status']=='assigned' and owner['assigned_driver']['full_name']==ctx['driver'].full_name and not owner['can_cancel']
    assert call(ctx,ctx['owner'],owner_path+'/cancel','post',business_id=ctx['business']).status_code==409
    unrelated=ctx['make_user']('shop_owner')
    assert call(ctx,unrelated,owner_path,business_id=ctx['business']).status_code==404
    assert call(ctx,ctx['owner'],owner_path,business_id=make_business(ctx['db'])).status_code==404
    for old,new in [('assigned','picked_up'),('picked_up','in_transit'),('in_transit','delivered')]:
        result=call(ctx,ctx['driver'],driver_path+'/status','post',{'expected_status':old,'status':new})
        assert result.status_code==200
        owner=call(ctx,ctx['owner'],owner_path,business_id=ctx['business']).json()
        assert owner['status']==new and owner['reference']==reference
        assert owner['events']==result.json()['events']
        assert call(ctx,ctx['owner'],'/shop-owner/deliveries',business_id=ctx['business'],status=new).json()['total']==1
        counts=call(ctx,ctx['owner'],'/shop-owner/deliveries/summary',business_id=ctx['business']).json()
        driver_counts=call(ctx,ctx['driver'],'/driver/dashboard/summary').json()
        assert counts['total_requests_count']==1 and counts['available_requests_count']==0
        assert counts['in_progress_count']==driver_counts['active_deliveries_count']==(0 if new=='delivered' else 1)
        assert counts['completed_count']==driver_counts['completed_deliveries_count']==(1 if new=='delivered' else 0)
    assert call(ctx,ctx['driver'],'/driver/history').json()['deliveries'][0]['reference']==reference
    assert call(ctx,ctx['driver'],'/driver/deliveries').json()['total']==0
    assert [event['status'] for event in owner['events']]==['assigned','picked_up','in_transit','delivered']
    assert ctx['db'].scalar(select(func.count()).select_from(DeliveryRequest))==1
    assert ctx['db'].scalar(select(func.count()).select_from(DeliveryAssignment))==1
    assert ctx['db'].scalar(select(func.count()).select_from(DeliveryStatusEvent))==3
    assert financial()==before


@pytest.mark.parametrize('missing',['vehicle','approval'])
def test_published_request_does_not_bypass_driver_eligibility(ctx,missing):
    profile=driver_service.create_profile(ctx['db'],ctx['driver'].user_id,*(('van','PENDING') if missing=='approval' else (None,None)))
    if missing=='vehicle':driver_service.review_profile(ctx['db'],ctx['admin'].user_id,profile.user_id,'approved')
    created=create(ctx);ident=created['delivery_request_id']
    assert call(ctx,ctx['driver'],'/driver/jobs').status_code==403
    assert call(ctx,ctx['driver'],f'/driver/jobs/{ident}/accept','post').status_code==403
    assert ctx['db'].get(DeliveryRequest,ident).status=='available'


@pytest.mark.parametrize('stage',['accept','progress'])
def test_failed_driver_transaction_is_visible_as_original_owner_state(ctx,monkeypatch,stage):
    approve(ctx);created=create(ctx);ident=created['delivery_request_id']
    if stage=='progress':assert call(ctx,ctx['driver'],f'/driver/jobs/{ident}/accept','post').status_code==200
    def fail(*args,**kwargs):raise SQLAlchemyError('private failure')
    monkeypatch.setattr(Session,'commit',fail)
    path=f'/driver/jobs/{ident}/accept' if stage=='accept' else f'/driver/deliveries/{ident}/status'
    result=call(ctx,ctx['driver'],path,'post',None if stage=='accept' else {'expected_status':'assigned','status':'picked_up'})
    assert result.status_code==503 and 'private failure' not in result.text
    owner=call(ctx,ctx['owner'],f'/shop-owner/deliveries/{ident}',business_id=ctx['business']).json()
    assert owner['status']==('available' if stage=='accept' else 'assigned')
    assert len(owner['events'])==(0 if stage=='accept' else 1)
    assert ctx['db'].scalar(select(func.count()).select_from(DeliveryRequest))==1

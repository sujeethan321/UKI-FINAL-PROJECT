from app.core.security import create_access_token
from app.services import driver_service
from test_shop_owner_deliveries import owner_api, ctx, api, db, create, read
from test_driver_dashboard import approve
from test_customer_dashboard import make_business


def test_summary_counts_all_statuses_independent_of_pagination_and_business(owner_api):
    context=owner_api
    empty=read(context,'/summary')
    assert empty.status_code==200 and empty.headers['cache-control']=='no-store'
    assert empty.json()==dict(business_id=context['business'],total_requests_count=0,
        available_requests_count=0,in_progress_count=0,completed_count=0)
    approve(context)
    for target in ['available','assigned','picked_up','in_transit','delivered','cancelled']:
        ident=create(context).json()['delivery_request_id']
        if target=='available':continue
        if target=='cancelled':
            driver_service.cancel_business_delivery(context['db'],context['owner'].user_id,context['business'],ident)
        else:
            driver_service.accept_delivery(context['db'],context['driver'].user_id,ident)
            for status in ['picked_up','in_transit','delivered']:
                if target=='assigned':break
                driver_service.transition_delivery(context['db'],context['driver'].user_id,ident,status)
                if status==target:break
    assert read(context,'/summary').json()==dict(business_id=context['business'],total_requests_count=6,
        available_requests_count=1,in_progress_count=3,completed_count=1)
    from app.models import BusinessMember
    other=make_business(context['db'])
    context['db'].add(BusinessMember(business_id=other,user_id=context['owner'].user_id,business_role='owner',membership_status='active'))
    context['db'].flush();assert create(context,business=other).status_code==201
    assert read(context,'/summary').json()['total_requests_count']==6
    assert read(context,'/summary',business_id=other).json()['total_requests_count']==1
    assert read(context,page_size=1,status='available').json()['total']==1
    context['headers']={'Authorization':'Bearer '+create_access_token(context['make_user']('shop_owner').user_id)}
    assert read(context,'/summary').status_code==404


def test_summary_requires_owner_role_approval_and_verified_jwt(owner_api):
    from app.models import Business
    context=owner_api;headers=context['headers']
    context['headers']={};assert read(context,'/summary').status_code==401
    for role in ['customer','driver','admin']:
        context['headers']={'Authorization':'Bearer '+create_access_token(context['make_user'](role).user_id)}
        assert read(context,'/summary').status_code==403
    context['headers']=headers
    context['db'].get(Business,context['business']).approval_status='pending';context['db'].flush()
    assert read(context,'/summary').status_code==403

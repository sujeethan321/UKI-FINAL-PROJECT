"""Real JWT, guarded MySQL, rollback-isolated Administrator contracts."""
from datetime import datetime,timedelta,timezone
import jwt
import pytest
from sqlalchemy import select,func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import create_access_token,verify_password
from app.models import (User,DriverProfile,AdminAudit,Notification,Business,BusinessApprovalAudit,
    CreditAccount,LedgerEntry,Order,DeliveryRequest,DeliveryAssignment)
from app.schemas.auth import ShopOwnerRegister
from app.services import driver_service
from app.services.admin_provisioning import provision_admin
from test_catalogue import api,db,shop,request,entry

@pytest.fixture
def admin(shop):
    shop['admin']=shop['make_user']('admin')
    shop['driver']=shop['make_user']('driver')
    driver_service.create_profile(shop['db'],shop['driver'].user_id,'van','ADMIN-123')
    return shop

def call(s,path,method='get',payload=None,**params):
    return request(s,'/admin'+path,method,payload,actor='admin',**params)

def decision(s,value='approve',**extra):
    return call(s,f"/drivers/{s['driver'].user_id}/decision",'patch',{'decision':value,**extra})

def status(s,user,value,**extra):
    return call(s,f'/users/{user.user_id}/status','patch',{'account_status':value,'reason':'Operational review',**extra})

def count(s,model):return s['db'].scalar(select(func.count()).select_from(model))

@pytest.mark.parametrize('path',['/overview','/users','/drivers','/businesses','/audit-events'])
@pytest.mark.parametrize('role',['customer','shop_owner','driver'])
def test_cross_role_denial(admin,path,role):
    user=admin['make_user'](role)
    assert request(admin,'/admin'+path,actor=user).status_code==403

@pytest.mark.parametrize('kind',['missing','expired','forged','suspended','role_claim'])
def test_jwt_and_current_account_are_authoritative(admin,kind):
    user=admin['admin']; now=datetime.now(timezone.utc)
    headers={}
    if kind=='suspended':
        user.account_status='suspended';admin['db'].flush()
        token=create_access_token(user.user_id)
    elif kind=='missing':token=None
    else:
        token=jwt.encode({'sub':str((admin['user'] if kind=='role_claim' else user).user_id),
            'role':'admin','platform_role':'admin','type':'access','iat':now-timedelta(hours=2),
            'exp':now-timedelta(hours=1) if kind=='expired' else now+timedelta(hours=1)},
            'x'*64 if kind=='forged' else settings.JWT_SECRET_KEY,algorithm='HS256')
    if token:headers={'Authorization':'Bearer '+token}
    response=admin['client'].get('/api/v1/admin/overview',headers=headers)
    assert response.status_code==(403 if kind in {'suspended','role_claim'} else 401)


def test_summary_uses_database_aggregates_and_safe_dtos(admin):
    data=call(admin,'/overview');assert data.status_code==200
    assert data.json()['total_shop_owners']==2
    assert data.json()['total_customers']==2 and data.json()['total_drivers']==1
    assert data.json()['pending_driver_approvals']==1 and data.json()['approved_drivers']==0
    assert data.json()['total_businesses']==2 and data.json()['approved_businesses']==2
    assert data.json()['total_orders']==data.json()['total_delivery_requests']==0
    assert data.headers['cache-control']=='no-store'
    for role in ['shop_owner','customer','driver']:
        response=call(admin,'/users',role=role,limit=1)
        assert response.status_code==200 and len(response.json()['users'])==1
        row=response.json()['users'][0]
        assert set(row)=={'user_id','full_name','email','platform_role','account_status','created_at'}
        assert call(admin,f"/users/{row['user_id']}").json()==row
    assert call(admin,f"/users/{admin['admin'].user_id}").status_code==404
    assert call(admin,f"/users/{admin['owner'].user_id}/businesses").json()['total']==1
    assert call(admin,f"/users/{admin['user'].user_id}/businesses").status_code==404
    assert call(admin,'/drivers',approval_status='pending').json()['total']==1
    assert call(admin,'/drivers',approval_status='approved').json()['drivers']==[]
    missing=admin['make_user']('driver')
    assert call(admin,'/drivers',approval_status='not_submitted').json()['drivers'][0]['profile'] is None
    assert call(admin,f'/drivers/{missing.user_id}').json()['profile'] is None

@pytest.mark.parametrize('params',[{'limit':0},{'limit':101},{'offset':-1},{'offset':1000001},
    {'q':' '},{'q':'x'*101},{'q':'a\nb'},{'status':'deleted'}])
@pytest.mark.parametrize('path',['/users','/drivers','/businesses'])
def test_bounds_and_search_validation(admin,path,params):
    assert call(admin,path,**params).status_code==422


def test_literal_search_and_deterministic_pages(admin):
    admin['owner'].full_name='100%_Owner';admin['db'].flush()
    result=call(admin,'/users',q='%_').json()
    assert result['total']==1 and result['users'][0]['user_id']==admin['owner'].user_id
    assert call(admin,'/users',q="' OR 1=1 --").json()['total']==0
    one=call(admin,'/users',limit=2).json();two=call(admin,'/users',limit=2,offset=2).json()
    assert one['total']==two['total']==5
    assert not {x['user_id'] for x in one['users']} & {x['user_id'] for x in two['users']}
    assert call(admin,'/users',role='admin').status_code==422
    assert call(admin,'/drivers',approval_status='verified').status_code==422

@pytest.mark.parametrize('value,state',[('approve','approved'),('reject','rejected')])
def test_driver_review_is_atomic_audited_recipient_scoped_and_pending_only(admin,value,state):
    response=decision(admin,value,review_note='Reviewed stored vehicle')
    assert response.status_code==200,response.text
    assert response.json()['profile']['approval_status']==state
    assert response.json()['profile']['reviewed_by']==admin['admin'].user_id
    for retry in ['approve','reject']:assert decision(admin,retry).status_code==409
    events=call(admin,'/audit-events',target_type='driver').json()
    assert events['total']==1
    row=events['events'][0]
    assert (row['previous_state'],row['new_state'],row['target_id'])==('pending',state,admin['driver'].user_id)
    notifications=list(admin['db'].scalars(select(Notification)))
    assert len(notifications)==1
    n=notifications[0]
    assert n.recipient_user_id==admin['driver'].user_id and n.business_id is None
    assert n.notification_type=='driver_'+state and n.related_entity_type=='admin_audit'
    result=request(admin,'/notifications',actor='driver')
    assert result.status_code==200 and result.json()['total']==1
    assert request(admin,'/notifications',actor='other').json()['total']==0
    job=driver_service.create_delivery(admin['db'],admin['owner'].user_id,admin['business'],'Pickup','Destination')
    admin['db'].flush()
    if state=='approved':
        assert driver_service.accept_delivery(admin['db'],admin['driver'].user_id,job.delivery_request_id).driver_user_id==admin['driver'].user_id
    else:
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as denied:driver_service.accept_delivery(admin['db'],admin['driver'].user_id,job.delivery_request_id)
        assert denied.value.status_code==403


def test_invalid_driver_and_immutable_admin_fields(admin):
    missing=admin['make_user']('driver')
    assert call(admin,f'/drivers/{missing.user_id}/decision','patch',{'decision':'approve'}).status_code==409
    profile=admin['db'].get(DriverProfile,admin['driver'].user_id)
    profile.vehicle_type=None;profile.registration_reference=None;admin['db'].flush()
    assert decision(admin).status_code==409
    for changes in [{'decision':'suspend'},{'platform_role':'admin'},{'review_note':' '},{'review_note':'x'*501},{'reviewed_by':1}]:
        assert decision(admin,**changes).status_code==422
    assert count(admin,AdminAudit)==count(admin,Notification)==0
    assert call(admin,f"/drivers/{admin['user'].user_id}/decision",'patch',{'decision':'approve'}).status_code==404


def test_suspension_current_jwt_reactivation_and_admin_protection(admin):
    token=create_access_token(admin['user'].user_id)
    assert status(admin,admin['user'],'suspended').status_code==200
    assert status(admin,admin['user'],'suspended').status_code==200
    assert count(admin,AdminAudit)==1
    assert admin['client'].get('/api/v1/customer/dashboard/summary',headers={'Authorization':'Bearer '+token}).status_code==403
    assert status(admin,admin['user'],'active').status_code==200
    assert admin['client'].get('/api/v1/customer/dashboard/summary',headers={'Authorization':'Bearer '+token}).status_code==200
    assert count(admin,AdminAudit)==2
    assert status(admin,admin['admin'],'suspended').status_code==404
    assert status(admin,admin['owner'],'suspended').status_code==409
    assert status(admin,admin['driver'],'suspended').status_code==200
    assert decision(admin).status_code==403
    assert status(admin,admin['driver'],'active').status_code==200
    assert call(admin,f"/drivers/{admin['driver'].user_id}").json()['profile']['approval_status']=='pending'


def test_active_assignment_suspension_is_deferred_without_reassignment(admin):
    assert decision(admin).status_code==200
    job=driver_service.create_delivery(admin['db'],admin['owner'].user_id,admin['business'],'Pickup','Destination')
    assignment=driver_service.accept_delivery(admin['db'],admin['driver'].user_id,job.delivery_request_id)
    admin['db'].flush()
    assert status(admin,admin['driver'],'suspended').status_code==409
    admin['db'].expire_all()
    assert admin['db'].get(DeliveryAssignment,assignment.assignment_id).driver_user_id==admin['driver'].user_id
    assert admin['db'].get(DeliveryRequest,job.delivery_request_id).status=='assigned'

@pytest.mark.parametrize('payload',[{'account_status':'deleted','reason':'No'},
    {'account_status':'suspended','reason':' '},{'account_status':'suspended','reason':'x'*501},
    {'account_status':'suspended','reason':'Review','platform_role':'admin'},
    {'account_status':'suspended'}])
def test_account_mutation_schema_blocks_escalation(admin,payload):
    assert call(admin,f"/users/{admin['user'].user_id}/status",'patch',payload).status_code==422

@pytest.mark.parametrize('decision_value,state',[('approve','approved'),('reject','rejected')])
def test_business_existing_review_and_unified_audit(admin,decision_value,state):
    business=admin['db'].get(Business,admin['business']);business.approval_status='pending';admin['db'].flush()
    path=f"/businesses/{admin['business']}/decision"
    response=call(admin,path,'patch',{'decision':decision_value,'review_note':'Registration reviewed'})
    assert response.status_code==200,response.text
    assert response.json()['approval_status']==state
    assert call(admin,path,'patch',{'decision':'approve'}).status_code==409
    assert count(admin,BusinessApprovalAudit)==1 and count(admin,AdminAudit)==0
    assert call(admin,f"/businesses/{admin['business']}/audit-history",limit=1).json()['total']==1
    event=call(admin,'/audit-events',target_type='business').json()['events'][0]
    assert event['action']=='business_'+state and event['target_id']==admin['business']
    assert admin['db'].scalar(select(Notification)).recipient_user_id==admin['owner'].user_id
    product=request(admin,'/shop-owner/products','post',{'name':'Rice','unit_price':'1.00'},business_id=admin['business'])
    assert product.status_code==(201 if state=='approved' else 403)


def test_failed_commit_preserves_state_and_leaves_no_false_audit_or_notification(admin,monkeypatch):
    def fail(*a,**k):raise SQLAlchemyError('private connection diagnostic')
    monkeypatch.setattr(Session,'commit',fail)
    response=decision(admin)
    assert response.status_code==503 and 'private connection diagnostic' not in response.text
    assert call(admin,f"/drivers/{admin['driver'].user_id}").json()['profile']['approval_status']=='pending'
    assert count(admin,AdminAudit)==count(admin,Notification)==0


def test_financial_isolation_and_no_audit_editing(admin):
    _,account=admin['profile'](admin['business']);entry(admin,account,'credit_sale','100.25');entry(admin,account,'repayment','25.10')
    models=[CreditAccount,LedgerEntry,Order,DeliveryRequest,DeliveryAssignment]
    def snapshot():return [admin['db'].execute(select(m.__table__).order_by(*m.__table__.primary_key)).all() for m in models]
    before=snapshot()
    assert decision(admin).status_code==200
    assert status(admin,admin['user'],'suspended').status_code==200
    assert status(admin,admin['user'],'active').status_code==200
    assert call(admin,'/overview').status_code==200 and snapshot()==before
    for method in ['post','patch','delete']:
        assert call(admin,'/audit-events',method).status_code==405
    assert request(admin,'/shop-owner/products','post',{'name':'Forbidden','unit_price':'1.00'},actor='admin',business_id=admin['business']).status_code==403


def test_operator_provisioning_is_explicit_hashed_idempotent_and_never_promotes(admin):
    data=ShopOwnerRegister(full_name='Operator Admin',email='operator-admin@example.com',password='TestOnly-Strong-Password-16')
    row,created=provision_admin(admin['db'],data)
    assert created and row.platform_role=='admin' and verify_password(data.password,row.password_hash)
    old=row.password_hash;row.account_status='suspended';admin['db'].flush()
    second,created=provision_admin(admin['db'],data)
    assert not created and second.user_id==row.user_id and second.password_hash==old and second.account_status=='suspended'
    assert count(admin,AdminAudit)==1
    with pytest.raises(ValueError):provision_admin(admin['db'],data.model_copy(update={'email':admin['user'].email}))
    with pytest.raises(ValueError):provision_admin(admin['db'],data.model_copy(update={'full_name':'  '}))
    assert admin['client'].post('/api/v1/auth/register/admin',json=data.model_dump()).status_code==404
    for role in ['customer','shop-owner','driver']:
        result=admin['client'].post('/api/v1/auth/register/'+role,json={**data.model_dump(),'platform_role':'admin'})
        assert result.status_code==422,result.text

@pytest.mark.parametrize('state',['submitted','approved','processing'])
def test_customer_active_orders_block_suspension(admin,state):
    from test_order_delivery import ready
    ready(admin,status=state)
    assert status(admin,admin['user'],'suspended').status_code==409
    assert count(admin,AdminAudit)==0


def test_business_approval_requires_active_owner_and_rollback_is_atomic(admin,monkeypatch):
    business=admin['db'].get(Business,admin['business']);business.approval_status='pending'
    admin['owner'].account_status='suspended';admin['db'].flush()
    path=f"/businesses/{admin['business']}/decision"
    assert call(admin,path,'patch',{'decision':'approve'}).status_code==409
    admin['owner'].account_status='active';admin['db'].flush()
    def fail(*a,**k):raise SQLAlchemyError('private diagnostics')
    monkeypatch.setattr(Session,'commit',fail)
    response=call(admin,path,'patch',{'decision':'approve'})
    assert response.status_code==500 and 'private diagnostics' not in response.text
    assert call(admin,f"/businesses/{admin['business']}").json()['approval_status']=='pending'
    assert count(admin,BusinessApprovalAudit)==count(admin,Notification)==0


def test_suspending_one_of_two_owners_preserves_business_and_other_owner(admin):
    from app.models import BusinessMember
    admin['db'].add(BusinessMember(user_id=admin['other_owner'].user_id,business_id=admin['business'],business_role='owner',membership_status='active'));admin['db'].flush()
    assert status(admin,admin['owner'],'suspended').status_code==200
    assert status(admin,admin['other_owner'],'suspended').status_code==409
    assert admin['db'].get(Business,admin['business']).approval_status=='approved'


def test_provision_cli_refuses_wrong_database_before_password_prompt(monkeypatch,capsys):
    from scripts import provision_admin as cli
    def forbidden(*a,**k):raise AssertionError('Must not prompt or connect')
    monkeypatch.setattr(cli.getpass,'getpass',forbidden)
    monkeypatch.setattr(cli,'Session',forbidden)
    assert cli.main(['--email','operator@example.com','--name','Operator','--confirm-database','lankapex_db'])==2
    assert 'does not match' in capsys.readouterr().err

@pytest.mark.parametrize('role',['customer','shop_owner','driver'])
def test_privileged_writes_are_role_guarded(admin,role):
    actor=admin['make_user'](role)
    for path,payload in [
        (f"/admin/drivers/{admin['driver'].user_id}/decision",{'decision':'approve'}),
        (f"/admin/users/{admin['user'].user_id}/status",{'account_status':'suspended','reason':'Denied'}),
        (f"/admin/businesses/{admin['business']}/decision",{'decision':'reject'})]:
        assert request(admin,path,'patch',payload,actor=actor).status_code==403
    assert count(admin,AdminAudit)==0


def test_profile_has_no_role_update_surface(admin):
    for method in ['patch','put']:
        assert request(admin,'/driver/profile',method,{'platform_role':'admin'},actor='driver').status_code==405
    assert request(admin,'/driver/profile','post',{'vehicle_type':'van','registration_reference':'SAFE','platform_role':'admin'},actor='driver').status_code==422
    assert call(admin,f"/users/{admin['user'].user_id}",'patch',{'platform_role':'admin'}).status_code==405
    assert admin['db'].get(User,admin['user'].user_id).platform_role=='customer'

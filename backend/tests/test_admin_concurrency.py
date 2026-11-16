"""Independent real MySQL transactions, exact fixture cleanup, forced overlapping locks."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event,Lock
import pytest
from fastapi import HTTPException,Response
from sqlalchemy import select,delete,event,func
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models import User,DriverProfile,DeliveryRequest,AdminAudit,Notification,Business,BusinessMember,BusinessApprovalAudit,DeliveryAssignment
from app.schemas.admin import DriverDecision,AccountDecision
from app.schemas.admin_business import BusinessDecisionRequest
from app.services import admin_service,driver_service
from app.routers.admin_businesses import decide_business
from test_driver_concurrency import race_data

@pytest.fixture
def context(race_data):
    ctx=race_data.copy()
    with Session(engine) as db:
        profile=db.get(DriverProfile,ctx['drivers'][0]);ctx['admin']=profile.reviewed_by
        delivery=db.get(DeliveryRequest,ctx['request']);ctx['business']=delivery.business_id;ctx['owner']=delivery.created_by
    try:yield ctx
    finally:
        with engine.begin() as c:
            c.execute(delete(Notification).where((Notification.recipient_user_id.in_(ctx['drivers'])) | (Notification.business_id==ctx['business'])))
            c.execute(delete(AdminAudit).where(AdminAudit.admin_user_id==ctx['admin']))
            c.execute(delete(BusinessApprovalAudit).where(BusinessApprovalAudit.business_id==ctx['business']))


def overlap(ctx,model,ident,operations):
    reached=Event();guard=Lock();calls=0
    def observe(conn,cursor,sql,parameters,execution,many):
        nonlocal calls
        if ('from '+model.__tablename__) in sql.lower() and ('for update' in sql.lower() or 'lock in share mode' in sql.lower() or 'for share' in sql.lower()) and (model is Business or ident in (parameters.values() if isinstance(parameters,dict) else parameters)):
            with guard:
                calls+=1
                if calls>=2:reached.set()
    def perform(operation):
        with Session(engine) as db:
            try:result=operation(db);db.commit();return 200,result
            except HTTPException as exc:db.rollback();return exc.status_code,None
    with engine.connect() as blocker:
        transaction=blocker.begin()
        blocker.execute(select(model).where(model.__mapper__.primary_key[0]==ident).with_for_update()).all()
        event.listen(engine,'before_cursor_execute',observe)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(perform,op) for op in operations]
                try:
                    assert reached.wait(20),'Both operations must attempt the held row lock'
                    assert all(not f.done() for f in futures)
                finally:transaction.rollback()
                return [f.result(timeout=30) for f in futures]
        finally:
            if transaction.is_active:transaction.rollback()
            event.remove(engine,'before_cursor_execute',observe)

@pytest.mark.parametrize('decisions',[['approve','reject'],['approve','approve']])
def test_concurrent_driver_reviews_have_one_winner_one_audit_one_notification(context,decisions):
    ctx=context;driver=ctx['drivers'][0]
    with Session(engine) as db:
        profile=db.get(DriverProfile,driver);profile.approval_status='pending';profile.reviewed_by=None;profile.reviewed_at=None;db.commit()
    results=overlap(ctx,DriverProfile,driver,[lambda db,value=value:admin_service.decide_driver(db,db.get(User,ctx['admin']),driver,DriverDecision(decision=value))['profile']['approval_status'] for value in decisions])
    assert sorted(r[0] for r in results)==[200,409]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(AdminAudit).where(AdminAudit.target_id==driver,AdminAudit.target_type=='driver'))==1
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.recipient_user_id==driver,Notification.related_entity_type=='admin_audit'))==1
        assert db.get(DriverProfile,driver).approval_status==next(r[1] for r in results if r[0]==200)


def test_concurrent_business_review_is_one_transaction(context):
    ctx=context
    with Session(engine) as db:db.get(Business,ctx['business']).approval_status='pending';db.commit()
    results=overlap(ctx,Business,ctx['business'],[lambda db,value=value:decide_business(ctx['business'],BusinessDecisionRequest(decision=value),Response(),db.get(User,ctx['admin']),db)['approval_status'] for value in ['approve','reject']])
    assert sorted(r[0] for r in results)==[200,409]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(BusinessApprovalAudit).where(BusinessApprovalAudit.business_id==ctx['business']))==1
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.business_id==ctx['business'],Notification.related_entity_type=='business_approval_audit'))==1


def test_suspend_and_accept_serialize_current_driver_state(context):
    ctx=context;driver=ctx['drivers'][0]
    results=overlap(ctx,User,driver,[
        lambda db:driver_service.accept_delivery(db,driver,ctx['request']).assignment_id,
        lambda db:admin_service.account_status(db,db.get(User,ctx['admin']),driver,AccountDecision(account_status='suspended',reason='Operational review'))['account_status']])
    assert sorted(r[0] for r in results) in [[200,403],[200,409]]
    with Session(engine) as db:
        assigned=db.scalar(select(DeliveryAssignment).where(DeliveryAssignment.delivery_request_id==ctx['request']))
        user=db.get(User,driver)
        assert (assigned is None and user.account_status=='suspended') or (assigned.driver_user_id==driver and user.account_status=='active')


def test_concurrent_suspensions_cannot_remove_last_two_active_owners(context):
    ctx=context;second=ctx['drivers'][1]
    with Session(engine) as db:
        db.delete(db.get(DriverProfile,second));db.get(User,second).platform_role='shop_owner'
        db.add(BusinessMember(user_id=second,business_id=ctx['business'],business_role='owner',membership_status='active'));db.commit()
    results=overlap(ctx,Business,ctx['business'],[lambda db,ident=ident:admin_service.account_status(db,db.get(User,ctx['admin']),ident,AccountDecision(account_status='suspended',reason='Operational review'))['account_status'] for ident in [ctx['owner'],second]])
    assert sorted(r[0] for r in results)==[200,409]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User).where(User.user_id.in_([ctx['owner'],second]),User.account_status=='active'))==1
        assert db.scalar(select(func.count()).select_from(AdminAudit).where(AdminAudit.admin_user_id==ctx['admin']))==1

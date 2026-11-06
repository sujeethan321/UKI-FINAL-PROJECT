"""Independent MySQL transactions; unique test seeds and exact-ID cleanup only."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session
from app.core.database import engine
from app.core.config import settings
from app.models import User, Business, BusinessMember, DriverProfile, DeliveryRequest, DeliveryAssignment, DeliveryStatusEvent
from app.services import driver_service as service


@pytest.fixture
def race_data():
    assert settings.MYSQL_DATABASE==engine.url.database=="lankapex_test_db"
    with engine.connect() as connection:assert connection.scalar(text("SELECT DATABASE()"))=="lankapex_test_db"
    ids=[];business_id=None;request_id=None
    try:
        with Session(engine) as session:
            for role in ["driver","driver","admin","shop_owner"]:
                user=User(full_name="Driver race fixture",email=f"driver-race-{uuid4().hex}@example.com",password_hash="test-only",platform_role=role,account_status="active",preferred_language="en")
                session.add(user);session.flush();ids.append(user.user_id)
            business=Business(business_name="Driver race fixture",business_type="retail",approval_status="approved")
            session.add(business);session.flush();business_id=business.business_id
            session.add(BusinessMember(business_id=business_id,user_id=ids[3],business_role="owner",membership_status="active"));session.flush()
            for driver_id in ids[:2]:
                service.create_profile(session,driver_id,"van","RACE-123")
                service.review_profile(session,ids[2],driver_id,"approved")
            row=service.create_delivery(session,ids[3],business_id,"Race pickup area","Race destination")
            request_id=row.delivery_request_id;session.commit()
        yield dict(drivers=ids[:2],request=request_id)
    finally:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT DATABASE()"))=="lankapex_test_db"
            if request_id is not None:
                connection.execute(delete(DeliveryStatusEvent).where(DeliveryStatusEvent.delivery_request_id==request_id))
                connection.execute(delete(DeliveryAssignment).where(DeliveryAssignment.delivery_request_id==request_id))
                connection.execute(delete(DeliveryRequest).where(DeliveryRequest.delivery_request_id==request_id))
            if business_id is not None:
                connection.execute(delete(BusinessMember).where(BusinessMember.business_id==business_id))
                connection.execute(delete(Business).where(Business.business_id==business_id))
            if ids:
                connection.execute(delete(DriverProfile).where(DriverProfile.user_id.in_(ids)))
                connection.execute(delete(User).where(User.user_id.in_(ids)))


def race(ctx,operations):
    attempted=Event();counter=Lock();calls=0
    def observe(conn,cursor,sql,parameters,context,executemany):
        nonlocal calls
        if "from delivery_requests" in sql.lower() and "for update" in sql.lower():
            with counter:
                calls+=1
                if calls>=2:attempted.set()
    def perform(operation):
        with Session(engine) as session:
            try:
                result=operation(session);session.commit();return (200,result)
            except HTTPException as error:
                session.rollback();return (error.status_code,None)
    with engine.connect() as blocker:
        transaction=blocker.begin()
        blocker.execute(select(DeliveryRequest).where(DeliveryRequest.delivery_request_id==ctx["request"]).with_for_update()).all()
        event.listen(engine,"before_cursor_execute",observe)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(perform,operation) for operation in operations]
                try:
                    assert attempted.wait(20),"Both independent transactions must reach the request row lock"
                    assert all(not future.done() for future in futures)
                finally:transaction.rollback()
                return [future.result(timeout=30) for future in futures]
        finally:
            if transaction.is_active:transaction.rollback()
            event.remove(engine,"before_cursor_execute",observe)


def test_two_drivers_cannot_accept_one_delivery(race_data):
    ctx=race_data
    results=race(ctx,[lambda s,driver=driver:service.accept_delivery(s,driver,ctx["request"]).driver_user_id for driver in ctx["drivers"]])
    assert sorted(result[0] for result in results)==[200,409]
    with Session(engine) as session:
        assignments=list(session.scalars(select(DeliveryAssignment).where(DeliveryAssignment.delivery_request_id==ctx["request"])))
        assert len(assignments)==1 and assignments[0].driver_user_id==next(result[1] for result in results if result[0]==200)
        assert session.get(DeliveryRequest,ctx["request"]).status=="assigned"


def test_duplicate_acceptance_by_same_driver_is_idempotent(race_data):
    ctx=race_data;driver=ctx["drivers"][0]
    results=race(ctx,[lambda s:service.accept_delivery(s,driver,ctx["request"]).assignment_id]*2)
    assert [result[0] for result in results]==[200,200] and results[0][1]==results[1][1]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(DeliveryAssignment).where(DeliveryAssignment.delivery_request_id==ctx["request"]))==1


def test_competing_status_transitions_use_current_locked_state(race_data):
    ctx=race_data;driver=ctx["drivers"][0]
    with Session(engine) as session:service.accept_delivery(session,driver,ctx["request"]);session.commit()
    results=race(ctx,[lambda s:service.transition_delivery(s,driver,ctx["request"],"picked_up").status,
                      lambda s:service.transition_delivery(s,driver,ctx["request"],"cancelled").status])
    assert sorted(result[0] for result in results)==[200,409]
    with Session(engine) as session:assert session.get(DeliveryRequest,ctx["request"]).status==next(result[1] for result in results if result[0]==200)

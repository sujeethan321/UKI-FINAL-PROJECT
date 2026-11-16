"""Real JWT tests with the existing verified-test-DB rollback fixture."""
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import event, select
from app.core.config import settings
from app.core.security import create_access_token
from app.models import Business, BusinessMember, DeliveryAssignment, DeliveryRequest, DriverProfile, User
from app.services import driver_service as service
from test_customer_dashboard import api, db, make_business

ROOT = "/api/v1/driver"
PATHS = ["/profile", "/dashboard/summary", "/deliveries"]


@pytest.fixture
def ctx(api):
    driver=api["make_user"]("driver"); other=api["make_user"]("driver"); admin=api["make_user"]("admin")
    owner=api["make_user"]("shop_owner")
    business=make_business(api["db"])
    api["db"].add(BusinessMember(business_id=business,user_id=owner.user_id,business_role="owner",membership_status="active"));api["db"].flush()
    api.update(driver=driver,other_driver=other,admin=admin,owner=owner,business=business)
    api["headers"]={"Authorization":"Bearer "+create_access_token(driver.user_id)}
    return api


def get(ctx,path,**params):
    return ctx["client"].get(ROOT+path,headers=ctx["headers"],params=params)


def approve(ctx,driver=None):
    driver=driver or ctx["driver"]
    service.create_profile(ctx["db"],driver.user_id,"motorcycle","TEST-123")
    return service.review_profile(ctx["db"],ctx["admin"].user_id,driver.user_id,"approved")


def request(ctx):
    return service.create_delivery(ctx["db"],ctx["owner"].user_id,ctx["business"],"Pickup area","Delivery area")


def test_unsubmitted_profile_reads_are_safe_and_do_not_auto_create_or_approve(ctx):
    profile=get(ctx,"/profile")
    assert profile.status_code==200 and profile.headers["cache-control"]=="no-store"
    assert profile.json()==dict(driver_user_id=ctx["driver"].user_id,full_name=ctx["driver"].full_name,
        account_status="active",approval_status="not_submitted",eligible_for_jobs=False,eligibility_reason="profile_required",vehicle=None)
    assert ctx["db"].get(DriverProfile,ctx["driver"].user_id) is None
    assert get(ctx,"/dashboard/summary").json()==dict(driver_user_id=ctx["driver"].user_id,available_jobs_count=0,active_deliveries_count=0,completed_deliveries_count=0)
    assert get(ctx,"/deliveries").json()["deliveries"]==[]


@pytest.mark.parametrize("decision,eligible,reason",[("pending",False,"approval_pending"),("approved",True,"eligible"),("rejected",False,"approval_rejected"),("suspended",False,"approval_suspended")])
def test_profile_and_vehicle_approval_never_imply_automatic_verification(ctx,decision,eligible,reason):
    service.create_profile(ctx["db"],ctx["driver"].user_id,"van","TEST-456")
    if decision!="pending":service.review_profile(ctx["db"],ctx["admin"].user_id,ctx["driver"].user_id,decision)
    data=get(ctx,"/profile").json()
    assert data["approval_status"]==decision and data["eligible_for_jobs"]==eligible and data["eligibility_reason"]==reason
    assert data["vehicle"]==dict(vehicle_type="van",registration_reference="TEST-456")
    for key in ["reviewed_by","reviewed_at","password","email","notes"]:assert key not in data


def test_approved_profile_without_vehicle_remains_ineligible(ctx):
    service.create_profile(ctx["db"],ctx["driver"].user_id)
    service.review_profile(ctx["db"],ctx["admin"].user_id,ctx["driver"].user_id,"approved")
    data=get(ctx,"/profile").json();assert data["vehicle"] is None and data["eligibility_reason"]=="vehicle_required"
    with pytest.raises(HTTPException) as error:service.accept_delivery(ctx["db"],ctx["driver"].user_id,request(ctx).delivery_request_id)
    assert error.value.status_code==403


@pytest.mark.parametrize("path",PATHS)
def test_jwt_roles_and_inactive_account_restrictions(ctx,path):
    assert ctx["client"].get(ROOT+path).status_code==401
    for role in ["customer","shop_owner","admin"]:
        user=ctx["make_user"](role)
        assert ctx["client"].get(ROOT+path,headers={"Authorization":"Bearer "+create_access_token(user.user_id)}).status_code==403
    expired=jwt.encode(dict(sub=str(ctx["driver"].user_id),type="access",iat=datetime.now(timezone.utc)-timedelta(minutes=2),exp=datetime.now(timezone.utc)-timedelta(seconds=1)),settings.JWT_SECRET_KEY,algorithm="HS256")
    assert ctx["client"].get(ROOT+path,headers={"Authorization":"Bearer "+expired}).status_code==401
    ctx["driver"].account_status="suspended";ctx["db"].flush()
    assert get(ctx,path).status_code==403
    assert ctx["client"].get(ROOT+path,headers={"Authorization":"Bearer invalid"}).status_code==401


def test_actual_counts_preview_pagination_and_cross_driver_scope(ctx):
    approve(ctx);approve(ctx,ctx["other_driver"])
    own=[]
    for target in ["assigned","picked_up","in_transit","delivered","cancelled"]:
        row=request(ctx);own.append(row)
        service.accept_delivery(ctx["db"],ctx["driver"].user_id,row.delivery_request_id)
        if target=="cancelled":service.transition_delivery(ctx["db"],ctx["driver"].user_id,row.delivery_request_id,"cancelled")
        else:
            for status in ["picked_up","in_transit","delivered"]:
                if row.status==target:break
                service.transition_delivery(ctx["db"],ctx["driver"].user_id,row.delivery_request_id,status)
    foreign=request(ctx);service.accept_delivery(ctx["db"],ctx["other_driver"].user_id,foreign.delivery_request_id)
    request(ctx);request(ctx)
    pending=make_business(ctx["db"],"pending")
    ctx["db"].add(DeliveryRequest(reference="DR-hidden",business_id=pending,created_by=ctx["owner"].user_id,pickup_area="Hidden pickup",delivery_area="Hidden delivery"));ctx["db"].flush()
    data=get(ctx,"/dashboard/summary",user_id=ctx["other_driver"].user_id).json()
    assert data==dict(driver_user_id=ctx["driver"].user_id,available_jobs_count=2,active_deliveries_count=3,completed_deliveries_count=1)
    first=get(ctx,"/deliveries",page_size=2,user_id=ctx["other_driver"].user_id).json()
    second=get(ctx,"/deliveries",page=2,page_size=2).json()
    assert first["total"]==second["total"]==3
    ids=[row["delivery_request_id"] for row in first["deliveries"]+second["deliveries"]]
    assert len(set(ids))==3 and set(ids)=={row.delivery_request_id for row in own[:3]}
    assert all("driver_user_id" not in row and "created_by" not in row for row in first["deliveries"])
    assert get(ctx,"/profile",driver_user_id=ctx["other_driver"].user_id).json()["driver_user_id"]==ctx["driver"].user_id
    ctx["headers"]={"Authorization":"Bearer "+create_access_token(ctx["other_driver"].user_id)}
    assert get(ctx,"/deliveries").json()["total"]==1


def test_pending_or_revoked_driver_has_no_available_jobs_but_retains_own_read_history(ctx):
    approve(ctx);row=request(ctx);service.accept_delivery(ctx["db"],ctx["driver"].user_id,row.delivery_request_id)
    request(ctx)
    service.review_profile(ctx["db"],ctx["admin"].user_id,ctx["driver"].user_id,"suspended")
    assert get(ctx,"/dashboard/summary").json()["available_jobs_count"]==0
    assert get(ctx,"/deliveries").json()["total"]==1
    with pytest.raises(HTTPException) as error:service.transition_delivery(ctx["db"],ctx["driver"].user_id,row.delivery_request_id,"picked_up")
    assert error.value.status_code==403


def test_lifecycle_ownership_idempotency_and_terminal_states(ctx):
    approve(ctx);approve(ctx,ctx["other_driver"]);row=request(ctx)
    first=service.accept_delivery(ctx["db"],ctx["driver"].user_id,row.delivery_request_id)
    assert service.accept_delivery(ctx["db"],ctx["driver"].user_id,row.delivery_request_id).assignment_id==first.assignment_id
    with pytest.raises(HTTPException) as error:service.transition_delivery(ctx["db"],ctx["other_driver"].user_id,row.delivery_request_id,"picked_up")
    assert error.value.status_code==404
    with pytest.raises(HTTPException) as error:service.transition_delivery(ctx["db"],ctx["driver"].user_id,row.delivery_request_id,"delivered")
    assert error.value.status_code==409
    for status in ["picked_up","in_transit","delivered"]:assert service.transition_delivery(ctx["db"],ctx["driver"].user_id,row.delivery_request_id,status).status==status
    for status in ["assigned","available","cancelled","delivered"]:
        with pytest.raises(HTTPException):service.transition_delivery(ctx["db"],ctx["driver"].user_id,row.delivery_request_id,status)
    with pytest.raises(HTTPException):service.accept_delivery(ctx["db"],ctx["other_driver"].user_id,row.delivery_request_id)


def test_business_scope_and_cancellation_rules(ctx):
    approve(ctx);row=request(ctx)
    with pytest.raises(HTTPException):service.create_delivery(ctx["db"],ctx["driver"].user_id,ctx["business"],"A","B")
    other_business=make_business(ctx["db"])
    with pytest.raises(HTTPException):service.cancel_business_delivery(ctx["db"],ctx["owner"].user_id,other_business,row.delivery_request_id)
    service.cancel_business_delivery(ctx["db"],ctx["owner"].user_id,ctx["business"],row.delivery_request_id)
    with pytest.raises(HTTPException):service.accept_delivery(ctx["db"],ctx["driver"].user_id,row.delivery_request_id)
    row=request(ctx);service.accept_delivery(ctx["db"],ctx["driver"].user_id,row.delivery_request_id)
    service.transition_delivery(ctx["db"],ctx["driver"].user_id,row.delivery_request_id,"picked_up")
    with pytest.raises(HTTPException):service.cancel_business_delivery(ctx["db"],ctx["owner"].user_id,ctx["business"],row.delivery_request_id)


def test_no_public_self_approval_and_only_supported_status_route(ctx):
    service.create_profile(ctx["db"],ctx["driver"].user_id,"van","TEST-123")
    with pytest.raises(HTTPException) as error:service.review_profile(ctx["db"],ctx["driver"].user_id,ctx["driver"].user_id,"approved")
    assert error.value.status_code==403
    for path in PATHS:
        # First-time submission exists; privileged approval fields stay forbidden.
        assert ctx["client"].post(ROOT+path,headers=ctx["headers"],json={"approval_status":"approved"}).status_code==(422 if path=='/profile' else 405)
    for path in ["/deliveries/1/accept","/profile/approve"]:
        assert ctx["client"].post(ROOT+path,headers=ctx["headers"],json={}).status_code==404
    assert ctx["client"].post(ROOT+"/deliveries/1/status",headers=ctx["headers"],json={}).status_code==422


@pytest.mark.parametrize("params",[{"page":0},{"page_size":0},{"page_size":101},{"page":1000001}])
def test_pagination_bounds(ctx,params):
    assert get(ctx,"/deliveries",**params).status_code==422


def test_read_endpoints_issue_no_mutation_sql_and_errors_are_sanitized(ctx,monkeypatch):
    approve(ctx);seen=[];connection=ctx["db"].connection()
    def observe(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().split()[0].upper() in {"INSERT","UPDATE","DELETE","REPLACE"}:seen.append(statement)
    event.listen(connection,"before_cursor_execute",observe)
    try:
        for path in PATHS:assert get(ctx,path).status_code==200
    finally:event.remove(connection,"before_cursor_execute",observe)
    assert seen==[]
    from sqlalchemy.exc import SQLAlchemyError
    def fail(*args):raise SQLAlchemyError("secret database details")
    monkeypatch.setattr(service,"summary",fail)
    response=get(ctx,"/dashboard/summary")
    assert response.status_code==503 and response.json()=={"detail":"Driver information is temporarily unavailable"}

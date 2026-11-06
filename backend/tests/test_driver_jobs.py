"""Available jobs, HTTP acceptance, data isolation and transaction rollback."""
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import create_access_token
from app.models import DeliveryRequest, DeliveryAssignment
from app.services import driver_service as service
from test_driver_dashboard import ctx, api, db, approve, request, get, ROOT


def accept(ctx,ident,**kwargs):
    return ctx["client"].post(ROOT+f"/jobs/{ident}/accept",headers=ctx["headers"],json={},**kwargs)


def test_listing_empty_then_actual_ordering_pagination_and_minimal_detail(ctx):
    approve(ctx)
    assert get(ctx,"/jobs").json()==dict(driver_user_id=ctx["driver"].user_id,total=0,page=1,page_size=10,jobs=[])
    rows=[request(ctx) for _ in range(6)]
    for row in rows:row.created_at=datetime(2026,1,1,12)
    ctx["db"].flush()
    one=get(ctx,"/jobs",page_size=2).json();two=get(ctx,"/jobs",page=2,page_size=2).json()
    assert one["total"]==two["total"]==6
    assert [row["delivery_request_id"] for row in one["jobs"]+two["jobs"]]==[row.delivery_request_id for row in reversed(rows)][:4]
    detail=get(ctx,f"/jobs/{rows[0].delivery_request_id}")
    assert detail.status_code==200 and detail.headers["cache-control"]=="no-store"
    assert set(detail.json()["job"])=={"delivery_request_id","reference","business_name","pickup_area","delivery_area","status","created_at"}
    for forbidden in ["phone","address","customer_id","credit_limit","fee","vehicle_requirement","created_by","reviewed_by"]:assert forbidden not in detail.text


def test_availability_excludes_assigned_terminal_and_unapproved_business_records(ctx):
    approve(ctx)
    assigned=request(ctx);service.accept_delivery(ctx["db"],ctx["driver"].user_id,assigned.delivery_request_id)
    cancelled=request(ctx);service.cancel_business_delivery(ctx["db"],ctx["owner"].user_id,ctx["business"],cancelled.delivery_request_id)
    completed=request(ctx);service.accept_delivery(ctx["db"],ctx["driver"].user_id,completed.delivery_request_id)
    for status in ["picked_up","in_transit","delivered"]:service.transition_delivery(ctx["db"],ctx["driver"].user_id,completed.delivery_request_id,status)
    live=request(ctx)
    assert get(ctx,"/jobs").json()["total"]==1
    assert get(ctx,"/jobs").json()["jobs"][0]["delivery_request_id"]==live.delivery_request_id
    for row in [assigned,cancelled,completed]:assert get(ctx,f"/jobs/{row.delivery_request_id}").json()=={"detail":"Available delivery not found"}
    from app.models import Business
    ctx["db"].get(Business,ctx["business"]).approval_status="pending";ctx["db"].flush()
    assert get(ctx,"/jobs").json()["total"]==0
    assert accept(ctx,live.delivery_request_id).status_code==409


def test_acceptance_uses_jwt_identity_is_idempotent_and_integrates_my_deliveries(ctx):
    approve(ctx);approve(ctx,ctx["other_driver"]);row=request(ctx)
    response=accept(ctx,row.delivery_request_id,params={"driver_id":ctx["other_driver"].user_id})
    assert response.status_code==200 and response.headers["cache-control"]=="no-store"
    result=response.json();assert result["driver_user_id"]==ctx["driver"].user_id and result["delivery"]["status"]=="assigned"
    assert accept(ctx,row.delivery_request_id).json()["assignment_id"]==result["assignment_id"]
    assert get(ctx,"/jobs").json()["total"]==0
    assert get(ctx,"/dashboard/summary").json()["active_deliveries_count"]==1
    assert get(ctx,"/deliveries").json()["deliveries"][0]["delivery_request_id"]==row.delivery_request_id
    detail=get(ctx,f"/deliveries/{row.delivery_request_id}").json()
    assert all(detail[key]==value for key,value in result.items())
    assert detail["events"]==[{"status":"assigned","occurred_at":result["delivery"]["assigned_at"]}]
    ctx["headers"]={"Authorization":"Bearer "+create_access_token(ctx["other_driver"].user_id)}
    assert accept(ctx,row.delivery_request_id).status_code==409
    assert get(ctx,f"/deliveries/{row.delivery_request_id}").status_code==404
    assert get(ctx,f"/jobs/{row.delivery_request_id}").status_code==404


@pytest.mark.parametrize("decision",[None,"pending","rejected","suspended"])
def test_ineligible_drivers_cannot_read_available_jobs_or_accept(ctx,decision):
    row=request(ctx)
    if decision is not None:
        service.create_profile(ctx["db"],ctx["driver"].user_id,"van","TEST-123")
        if decision!="pending":service.review_profile(ctx["db"],ctx["admin"].user_id,ctx["driver"].user_id,decision)
    assert get(ctx,"/jobs").status_code==403
    assert get(ctx,f"/jobs/{row.delivery_request_id}").status_code==403
    assert accept(ctx,row.delivery_request_id).status_code==403
    assert ctx["db"].scalar(select(func.count()).select_from(DeliveryAssignment))==0


def test_approved_missing_vehicle_and_inactive_general_accounts_cannot_accept(ctx):
    row=request(ctx);service.create_profile(ctx["db"],ctx["driver"].user_id)
    service.review_profile(ctx["db"],ctx["admin"].user_id,ctx["driver"].user_id,"approved")
    assert accept(ctx,row.delivery_request_id).status_code==403
    ctx["driver"].account_status="suspended";ctx["db"].flush()
    assert get(ctx,"/jobs").status_code==403 and accept(ctx,row.delivery_request_id).status_code==403


@pytest.mark.parametrize("role",[None,"customer","shop_owner","admin"])
def test_all_new_job_routes_require_driver_authentication(ctx,role):
    headers={} if role is None else {"Authorization":"Bearer "+create_access_token(ctx["make_user"](role).user_id)}
    for method,path in [("get","/jobs"),("get","/jobs/1"),("get","/deliveries/1"),("post","/jobs/1/accept")]:
        response=getattr(ctx["client"],method)(ROOT+path,headers=headers,**({"json":{}} if method=="post" else {}))
        assert response.status_code==(401 if role is None else 403)


def test_expired_jwt_rejects_acceptance(ctx):
    token=jwt.encode(dict(sub=str(ctx["driver"].user_id),type="access",iat=datetime.now(timezone.utc)-timedelta(minutes=5),exp=datetime.now(timezone.utc)-timedelta(seconds=1)),settings.JWT_SECRET_KEY,algorithm="HS256")
    ctx["headers"]={"Authorization":"Bearer "+token}
    assert accept(ctx,1).status_code==401


@pytest.mark.parametrize("value",[0,-1,"invalid",9223372036854775808])
def test_job_identifiers_and_acceptance_body_are_bounded(ctx,value):
    approve(ctx)
    assert get(ctx,f"/jobs/{value}").status_code==422
    assert accept(ctx,value).status_code==422


def test_payload_cannot_change_driver_status_or_identity(ctx):
    approve(ctx);row=request(ctx)
    for payload in [{"driver_id":ctx["other_driver"].user_id},{"status":"delivered"},{"approval_status":"approved"}]:
        assert ctx["client"].post(ROOT+f"/jobs/{row.delivery_request_id}/accept",headers=ctx["headers"],json=payload).status_code==422
    assert get(ctx,"/jobs").json()["total"]==1


def test_accepting_cancelled_or_completed_jobs_conflicts_and_unknown_is_safe(ctx):
    approve(ctx)
    cancelled=request(ctx);service.cancel_business_delivery(ctx["db"],ctx["owner"].user_id,ctx["business"],cancelled.delivery_request_id)
    assert accept(ctx,cancelled.delivery_request_id).status_code==409
    completed=request(ctx);service.accept_delivery(ctx["db"],ctx["driver"].user_id,completed.delivery_request_id)
    for status in ["picked_up","in_transit","delivered"]:service.transition_delivery(ctx["db"],ctx["driver"].user_id,completed.delivery_request_id,status)
    assert accept(ctx,completed.delivery_request_id).status_code==409
    assert accept(ctx,9223372036854775807).status_code==404
    assert get(ctx,"/jobs/9223372036854775807").json()=={"detail":"Available delivery not found"}


def test_failed_commit_rolls_back_assignment_and_status(ctx,monkeypatch):
    approve(ctx);row=request(ctx)
    def fail(*args,**kwargs):raise SQLAlchemyError("private commit failure")
    monkeypatch.setattr(Session,"commit",fail)
    response=accept(ctx,row.delivery_request_id)
    assert response.status_code==503 and "private commit failure" not in response.text
    ctx["db"].expire_all()
    assert ctx["db"].get(DeliveryRequest,row.delivery_request_id).status=="available"
    assert ctx["db"].scalar(select(func.count()).select_from(DeliveryAssignment))==0


@pytest.mark.parametrize("params",[{"page":0},{"page_size":101},{"page_size":0}])
def test_job_pagination_bounds(ctx,params):
    approve(ctx);assert get(ctx,"/jobs",**params).status_code==422

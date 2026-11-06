"""Public HTTP acceptance races against the actual MySQL request row lock."""
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models import Notification
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from test_driver_concurrency import race_data, race


def http_accept(client,driver,ident):
    response=client.post(f"/api/v1/driver/jobs/{ident}/accept",headers={"Authorization":"Bearer "+create_access_token(driver)},json={})
    if response.status_code!=200:raise HTTPException(response.status_code)
    return response.json()


def test_two_driver_http_requests_cannot_both_win(race_data):
    assert not app.dependency_overrides
    ctx=race_data
    with TestClient(app) as client:
        results=race(ctx,[lambda session,driver=driver:http_accept(client,driver,ctx["request"]) for driver in ctx["drivers"]])
    assert sorted(result[0] for result in results)==[200,409]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Notification).where(Notification.related_entity_type=="delivery_request", Notification.related_entity_id==ctx["request"], Notification.notification_type=="delivery_assigned"))==1
    result=next(row[1] for row in results if row[0]==200)
    assert result["driver_user_id"] in ctx["drivers"] and result["delivery"]["status"]=="assigned"


def test_same_driver_http_race_returns_one_current_assignment_to_both_retries(race_data):
    assert not app.dependency_overrides
    ctx=race_data
    with TestClient(app) as client:
        results=race(ctx,[lambda session:http_accept(client,ctx["drivers"][0],ctx["request"])]*2)
    assert [result[0] for result in results]==[200,200]
    assert results[0][1]["assignment_id"]==results[1][1]["assignment_id"]
    assert all(result[1]["delivery"]["status"]=="assigned" for result in results)

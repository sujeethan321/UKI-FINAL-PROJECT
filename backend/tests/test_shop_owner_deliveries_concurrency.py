"""Independent MySQL HTTP transactions race acceptance against cancellation."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.core.security import create_access_token
from app.main import app
from app.models import DeliveryRequest, DeliveryAssignment, DeliveryStatusEvent
from test_driver_concurrency import race_data, race


def context(ctx):
    with Session(engine) as session:
        row=session.get(DeliveryRequest,ctx['request'])
        return row.created_by,row.business_id


def operation(client,ctx,owner,business,cancelling):
    if cancelling:
        result=client.post(f"/api/v1/shop-owner/deliveries/{ctx['request']}/cancel",
            headers={'Authorization':'Bearer '+create_access_token(owner)},params={'business_id':business},json={})
    else:
        result=client.post(f"/api/v1/driver/jobs/{ctx['request']}/accept",
            headers={'Authorization':'Bearer '+create_access_token(ctx['drivers'][0])},json={})
    if result.status_code!=200:raise HTTPException(result.status_code)
    return result.json()


@pytest.mark.parametrize('attempt',range(3))
def test_http_acceptance_and_cancellation_cannot_both_win(race_data,attempt):
    assert not app.dependency_overrides
    ctx=race_data;owner,business=context(ctx)
    with TestClient(app) as client:
        results=race(ctx,[lambda session:operation(client,ctx,owner,business,False),
                          lambda session:operation(client,ctx,owner,business,True)])
    assert sorted(result[0] for result in results)==[200,409]
    with Session(engine) as session:
        row=session.get(DeliveryRequest,ctx['request'])
        assigned=session.scalar(select(func.count()).select_from(DeliveryAssignment).where(DeliveryAssignment.delivery_request_id==ctx['request']))
        events=session.scalar(select(func.count()).select_from(DeliveryStatusEvent).where(DeliveryStatusEvent.delivery_request_id==ctx['request']))
        assert (row.status,assigned,events) in [('assigned',1,0),('cancelled',0,1)]


def test_concurrent_cancel_retries_preserve_one_event_and_timestamp(race_data):
    ctx=race_data;owner,business=context(ctx)
    with TestClient(app) as client:
        results=race(ctx,[lambda session:operation(client,ctx,owner,business,True)]*2)
    assert [result[0] for result in results]==[200,200]
    assert results[0][1]==results[1][1]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(DeliveryStatusEvent).where(DeliveryStatusEvent.delivery_request_id==ctx['request']))==1
        assert session.scalar(select(func.count()).select_from(DeliveryAssignment).where(DeliveryAssignment.delivery_request_id==ctx['request']))==0

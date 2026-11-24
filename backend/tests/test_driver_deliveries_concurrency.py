from fastapi import HTTPException
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.main import app
from app.core.database import engine
from app.core.security import create_access_token
from app.models import DeliveryStatusEvent,DeliveryRequest,Notification
from app.services import driver_service as service
from test_driver_concurrency import race_data,race


@pytest.mark.parametrize('before,after',[('assigned','picked_up'),('in_transit','delivered')])
def test_competing_http_updates_record_exactly_one_event(race_data,before,after):
    ctx=race_data;driver=ctx['drivers'][0]
    with Session(engine) as session:
        service.accept_delivery(session,driver,ctx['request'])
        if before=='in_transit':
            for status in ['picked_up','in_transit']:service.transition_delivery(session,driver,ctx['request'],status)
        session.commit()
    def pickup(session):
        response=client.post(f"/api/v1/driver/deliveries/{ctx['request']}/status",headers={'Authorization':'Bearer '+create_access_token(driver)},json={'expected_status':before,'status':after})
        if response.status_code!=200:raise HTTPException(response.status_code)
        return response.json()
    with TestClient(app) as client:
        results=race(ctx,[pickup,pickup])
    assert sorted(result[0] for result in results)==[200,409]
    with Session(engine) as session:
        assert session.get(DeliveryRequest,ctx['request']).status==after
        assert session.scalar(select(func.count()).select_from(DeliveryStatusEvent).where(DeliveryStatusEvent.delivery_request_id==ctx['request'],DeliveryStatusEvent.status==after))==1
        assert session.scalar(select(func.count()).select_from(Notification).where(Notification.related_entity_type=="delivery_request", Notification.related_entity_id==ctx["request"], Notification.notification_type=="delivery_"+after))==1

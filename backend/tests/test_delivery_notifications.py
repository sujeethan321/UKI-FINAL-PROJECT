"""Real JWT transitions and recipient-owned notifications on guarded test DB."""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.models import Notification
from app.services.notification_service import notify_event
from test_shop_driver_integration import ctx, api, db, approve, call, create


def rows(ctx):
    return list(ctx['db'].scalars(select(Notification).where(Notification.notification_type.like('delivery_%'), Notification.business_id == ctx['business'])))


def test_delivery_notifications_follow_persisted_transitions_and_retries(ctx):
    approve(ctx)
    ident = create(ctx)['delivery_request_id']
    assert rows(ctx) == []
    accept = f'/driver/jobs/{ident}/accept'
    for _ in range(2):
        assert call(ctx, ctx['driver'], accept, 'post').status_code == 200
    assert len(rows(ctx)) == 2
    for old, new in [('assigned','picked_up'),('picked_up','in_transit'),('in_transit','delivered')]:
        payload = {'expected_status': old, 'status': new}
        path = f'/driver/deliveries/{ident}/status'
        assert call(ctx, ctx['driver'], path, 'post', payload).status_code == 200
        assert call(ctx, ctx['driver'], path, 'post', payload).status_code == 409
        # Internal notification replay preserves original read state and timestamp.
        notify_event(ctx['db'], 'delivery_' + new, ident)
    notifications = rows(ctx)
    assert len(notifications) == 5
    assert {n.recipient_user_id for n in notifications} == {ctx['owner'].user_id, ctx['driver'].user_id}
    assert {n.notification_type for n in notifications} == {'delivery_assigned','delivery_picked_up','delivery_in_transit','delivery_delivered'}
    assert all(n.related_entity_type == 'delivery_request' and n.related_entity_id == ident for n in notifications)
    assert all('077' not in n.message and 'balance' not in n.message for n in notifications)
    own = call(ctx, ctx['owner'], '/notifications').json()
    assert own['total'] == 4
    assert call(ctx, ctx['other_driver'], '/notifications').json()['total'] == 0
    first = notifications[0].notification_id
    assert call(ctx, ctx['other_driver'], f'/notifications/{first}/read', 'patch').status_code == 404


@pytest.mark.parametrize('stage', ['assigned', 'picked_up'])
def test_delivery_notification_rolls_back_with_transition(ctx, monkeypatch, stage):
    approve(ctx)
    ident = create(ctx)['delivery_request_id']
    if stage == 'picked_up':
        assert call(ctx,ctx['driver'],f'/driver/jobs/{ident}/accept','post').status_code == 200
    before = len(rows(ctx))
    def fail(*args, **kwargs):
        raise SQLAlchemyError('private failure')
    monkeypatch.setattr(Session, 'commit', fail)
    path = f'/driver/jobs/{ident}/accept' if stage == 'assigned' else f'/driver/deliveries/{ident}/status'
    response = call(ctx,ctx['driver'],path,'post',None if stage == 'assigned' else {'expected_status':'assigned','status':'picked_up'})
    assert response.status_code == 503
    assert len(rows(ctx)) == before


def test_cancellation_has_no_assigned_recipient(ctx):
    ident=create(ctx)['delivery_request_id']
    for _ in range(2):
        assert call(ctx,ctx['owner'],f'/shop-owner/deliveries/{ident}/cancel','post',business_id=ctx['business']).status_code == 200
    assert rows(ctx) == []

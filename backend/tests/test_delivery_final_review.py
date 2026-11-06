"""Final Day 13 recipient, link-authorization and atomic-write checks."""
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models import BusinessMember, DeliveryAssignment, DeliveryRequest, Notification
from app.services import notification_service
from test_shop_driver_integration import ctx, api, db, approve, call, create


def test_delivery_recipient_policy_excludes_inactive_members_accounts_and_wrong_roles(ctx):
    approve(ctx)
    expected = {ctx['owner'].user_id}
    excluded = []
    for role, account_status, membership_status, business_role in [
        ('shop_owner', 'active', 'active', 'owner'),
        ('shop_owner', 'suspended', 'active', 'owner'),
        ('shop_owner', 'active', 'inactive', 'owner'),
        ('shop_owner', 'active', 'active', 'staff'),
        ('customer', 'active', 'active', 'owner'),
    ]:
        user = ctx['make_user'](role, account_status)
        ctx['db'].add(BusinessMember(business_id=ctx['business'], user_id=user.user_id,
            business_role=business_role, membership_status=membership_status))
        if (role, account_status, membership_status, business_role) == ('shop_owner', 'active', 'active', 'owner'):
            expected.add(user.user_id)
        else:
            excluded.append(user)
    ctx['db'].flush()
    ident = create(ctx)['delivery_request_id']
    assert call(ctx, ctx['driver'], f'/driver/jobs/{ident}/accept', 'post').status_code == 200
    rows = list(ctx['db'].scalars(select(Notification).where(
        Notification.related_entity_type == 'delivery_request', Notification.related_entity_id == ident)))
    assert {row.recipient_user_id for row in rows} == expected
    assert len(rows) == len(expected)
    for user in excluded:
        # Suspended users cannot even read their inbox; other excluded users have no event.
        response = call(ctx, user, '/notifications')
        assert response.status_code == (403 if user.account_status != 'active' else 200)
        if response.status_code == 200:
            assert response.json()['total'] == 0


def test_old_notification_does_not_authorize_tracking_after_membership_revocation(ctx):
    approve(ctx)
    ident = create(ctx)['delivery_request_id']
    assert call(ctx, ctx['driver'], f'/driver/jobs/{ident}/accept', 'post').status_code == 200
    notification = call(ctx, ctx['owner'], '/notifications').json()['notifications'][0]
    member = ctx['db'].scalar(select(BusinessMember).where(
        BusinessMember.business_id == ctx['business'], BusinessMember.user_id == ctx['owner'].user_id))
    member.membership_status = 'inactive'
    ctx['db'].flush()
    assert call(ctx, ctx['owner'], f'/shop-owner/deliveries/{notification["related_entity_id"]}',
        business_id=notification['business_id']).status_code == 404
    # An existing personal inbox entry grants no business access, and remains recipient-owned.
    first = call(ctx, ctx['owner'], f'/notifications/{notification["notification_id"]}/read', 'patch')
    second = call(ctx, ctx['owner'], f'/notifications/{notification["notification_id"]}/read', 'patch')
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


def test_notification_insert_failure_cannot_leave_successful_assignment(ctx, monkeypatch):
    approve(ctx)
    ident = create(ctx)['delivery_request_id']
    def fail(*args, **kwargs):
        raise SQLAlchemyError('private notification insert failure')
    monkeypatch.setattr(notification_service, 'notify_event', fail)
    response = call(ctx, ctx['driver'], f'/driver/jobs/{ident}/accept', 'post')
    assert response.status_code == 503
    assert 'private notification insert failure' not in response.text
    assert ctx['db'].get(DeliveryRequest, ident).status == 'available'
    assert ctx['db'].scalar(select(DeliveryAssignment).where(DeliveryAssignment.delivery_request_id == ident)) is None
    assert call(ctx, ctx['owner'], '/notifications').json()['total'] == 0

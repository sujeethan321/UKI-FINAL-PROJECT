"""Final Driver-module checks across actual financial and business records."""
from datetime import date, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select

from app.models import CreditAccount, LedgerEntry, PaymentReminder, Notification, DeliveryRequest
from app.services import driver_service as service
from app.services import customer_dashboard_service as customer
from test_customer_dashboard import entry
from test_driver_dashboard import ctx, api, db, approve, request, get, ROOT


def test_delivery_lifecycle_preserves_statements_reminders_and_financial_notifications(ctx):
    profile, account = ctx['profile'](ctx['business'])
    entry(ctx, account, 'credit_sale', '200.00')
    entry(ctx, account, 'repayment', '25.00')
    stamp = datetime(2026, 11, 6, 10)
    reminder = PaymentReminder(business_id=ctx['business'], customer_id=profile.customer_id,
        credit_account_id=account.credit_account_id, created_by=ctx['owner'].user_id,
        outstanding_amount='175.00', currency='LKR', channel='internal', language='en',
        template_version='review-fixture', message='Private financial reminder', status='recorded',
        idempotency_key=uuid4().hex, created_at=stamp, updated_at=stamp)
    ctx['db'].add(reminder); ctx['db'].flush()
    ctx['db'].add(Notification(recipient_user_id=ctx['user'].user_id, business_id=ctx['business'],
        notification_type='payment_reminder_recorded', title='Private reminder', message='Private financial notification',
        related_entity_type='payment_reminder', related_entity_id=reminder.reminder_id,
        event_key=uuid4().hex, is_read=False, created_at=stamp))
    ctx['db'].flush()

    def snapshot():
        result = {}
        for model in [CreditAccount, LedgerEntry, PaymentReminder, Notification]:
            query = select(model.__table__).order_by(*model.__table__.primary_key)
            if model is Notification:
                query = query.where(~Notification.notification_type.like('delivery_%'))
            result[model.__tablename__] = ctx['db'].execute(query).all()
        return result

    before = snapshot()
    period = (date(2026, 1, 1), date(2026, 12, 31))
    statement_before = customer.statement(ctx['db'], ctx['user'].user_id, account.credit_account_id, *period)
    writes = []
    def observe(conn, cursor, sql, parameters, context, executemany):
        if sql.lstrip().split()[0].upper() in {'INSERT', 'UPDATE', 'DELETE', 'REPLACE'}:
            writes.append(sql.lower())
    connection = ctx['db'].connection()
    event.listen(connection, 'before_cursor_execute', observe)
    try:
        approve(ctx); row = request(ctx)
        response = ctx['client'].post(ROOT+f'/jobs/{row.delivery_request_id}/accept', headers=ctx['headers'], json={})
        assert response.status_code == 200
        for before_status, after_status in [('assigned','picked_up'), ('picked_up','in_transit'), ('in_transit','delivered')]:
            response = ctx['client'].post(ROOT+f'/deliveries/{row.delivery_request_id}/status', headers=ctx['headers'],
                json={'expected_status':before_status,'status':after_status})
            assert response.status_code == 200
    finally:
        event.remove(connection, 'before_cursor_execute', observe)
    assert snapshot() == before
    assert customer.statement(ctx['db'], ctx['user'].user_id, account.credit_account_id, *period) == statement_before
    assert writes and not any(table in sql for sql in writes for table in before if table != 'notifications')
    delivery_notifications=list(ctx['db'].scalars(select(Notification).where(Notification.related_entity_type=='delivery_request',Notification.related_entity_id==row.delivery_request_id)))
    assert len(delivery_notifications)==5
    driver_alerts=[n for n in delivery_notifications if n.recipient_user_id==ctx['driver'].user_id]
    assert len(driver_alerts)==1 and driver_alerts[0].notification_type=='delivery_assigned'
    assert {n.recipient_user_id for n in delivery_notifications}=={ctx['owner'].user_id,ctx['driver'].user_id}
    assert get(ctx, '/history').json()['deliveries'][0]['status'] == 'delivered'


@pytest.mark.parametrize('role', ['customer', 'shop_owner', 'admin'])
def test_forged_role_claim_never_overrides_database_role(ctx, role):
    # A validly signed test token deliberately claims Driver; the stored role wins.
    import jwt
    from datetime import timedelta, timezone
    from app.core.config import settings
    user = ctx['make_user'](role)
    token = jwt.encode({'sub':str(user.user_id),'type':'access','role':'driver','platform_role':'driver',
        'iat':datetime.now(timezone.utc),'exp':datetime.now(timezone.utc)+timedelta(minutes=5)},
        settings.JWT_SECRET_KEY, algorithm='HS256')
    ctx['headers'] = {'Authorization':'Bearer '+token}
    assert get(ctx, '/profile').status_code == 403
    assert get(ctx, '/jobs').status_code == 403


def test_driver_cannot_read_another_vehicles_profile_or_private_financial_apis(ctx):
    approve(ctx); approve(ctx, ctx['other_driver'])
    from app.models import DriverProfile
    ctx['db'].get(DriverProfile, ctx['other_driver'].user_id).registration_reference = 'OTHER-PRIVATE-VEHICLE'
    ctx['db'].flush()
    own = get(ctx, '/profile', driver_user_id=ctx['other_driver'].user_id).json()
    assert own['driver_user_id'] == ctx['driver'].user_id
    assert own['vehicle']['registration_reference'] == 'TEST-123'
    for path in ['/api/v1/customer/dashboard/summary', '/api/v1/customer/transactions',
                 '/api/v1/shop-owner/dashboard/summary']:
        assert ctx['client'].get(path, headers=ctx['headers']).status_code == 403


def test_status_and_history_sql_failures_hide_database_diagnostics(ctx, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    def fail(*args, **kwargs):
        raise SQLAlchemyError('private-driver-database-diagnostics')
    monkeypatch.setattr(service, 'assigned_deliveries', fail)
    response = get(ctx, '/history')
    assert response.status_code == 503 and 'private-driver' not in response.text


def test_unowned_business_cannot_cancel_assigned_delivery_or_append_event(ctx):
    from test_customer_dashboard import make_business
    from app.models import DeliveryStatusEvent
    approve(ctx); row = request(ctx)
    service.accept_delivery(ctx['db'], ctx['driver'].user_id, row.delivery_request_id)
    other_business = make_business(ctx['db'])
    with pytest.raises(HTTPException) as error:
        service.cancel_business_delivery(ctx['db'], ctx['owner'].user_id, other_business, row.delivery_request_id)
    assert error.value.status_code == 404
    assert ctx['db'].get(DeliveryRequest, row.delivery_request_id).status == 'assigned'
    assert ctx['db'].scalar(select(DeliveryStatusEvent).where(DeliveryStatusEvent.delivery_request_id == row.delivery_request_id)) is None

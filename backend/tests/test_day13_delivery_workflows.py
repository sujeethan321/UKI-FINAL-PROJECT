"""Additional Day 13 HTTP workflow and two-owner isolation coverage."""
from sqlalchemy import select

from app.core.security import create_access_token
from app.models import BusinessMember, DeliveryRequest
from test_customer_dashboard import make_business
from test_driver_dashboard import approve
from test_shop_owner_deliveries import (
    ROOT, AREAS, owner_api, ctx, api, db, create, read, cancel,
)


def test_owner_tracks_driver_http_progress_after_database_reload(owner_api):
    context = owner_api
    approve(context)
    created = create(context)
    assert created.status_code == 201
    ident = created.json()['delivery_request_id']
    headers = {'Authorization': 'Bearer ' + create_access_token(context['driver'].user_id)}
    accepted = context['client'].post(
        f'/api/v1/driver/jobs/{ident}/accept', headers=headers, json={})
    assert accepted.status_code == 200
    expected_events = ['assigned']
    for before, after in [('assigned', 'picked_up'), ('picked_up', 'in_transit'),
                          ('in_transit', 'delivered')]:
        changed = context['client'].post(
            f'/api/v1/driver/deliveries/{ident}/status', headers=headers,
            json={'expected_status': before, 'status': after})
        assert changed.status_code == 200
        expected_events.append(after)
        context['db'].expire_all()
        detail = read(context, f'/{ident}')
        assert detail.status_code == 200
        data = detail.json()
        assert data['status'] == after
        assert [event['status'] for event in data['events']] == expected_events
        assert data['assigned_driver']['assigned_at'] == accepted.json()['delivery']['assigned_at']
        assert context['db'].get(DeliveryRequest, ident).status == after
        listing = read(context, status=after)
        assert listing.status_code == 200
        assert [row['delivery_request_id'] for row in listing.json()['deliveries']] == [ident]


def test_two_owners_with_separate_businesses_cannot_access_each_others_requests(owner_api):
    context = owner_api
    first_business = context['business']
    first_headers = context['headers']
    first = create(context).json()['delivery_request_id']
    other = context['make_user']('shop_owner')
    second_business = make_business(context['db'])
    context['db'].add(BusinessMember(business_id=second_business, user_id=other.user_id,
                                   business_role='owner', membership_status='active'))
    context['db'].flush()
    second_headers = {'Authorization': 'Bearer ' + create_access_token(other.user_id)}
    context['headers'] = second_headers
    second = create(context, business=second_business)
    assert second.status_code == 201
    second = second.json()['delivery_request_id']
    for headers, own_business, foreign_business, foreign_id in [
        (first_headers, first_business, second_business, second),
        (second_headers, second_business, first_business, first),
    ]:
        context['headers'] = headers
        assert read(context, business_id=own_business).json()['total'] == 1
        for selected in [own_business, foreign_business]:
            detail = read(context, f'/{foreign_id}', business_id=selected)
            missing = read(context, '/9223372036854775807', business_id=selected)
            assert detail.status_code == missing.status_code == 404
            assert detail.json() == missing.json()
            denied = cancel(context, foreign_id, business_id=selected)
            assert denied.status_code == 404
        assert read(context, business_id=foreign_business).status_code == 404
        assert create(context, business=foreign_business).status_code == 404
    context['db'].expire_all()
    assert context['db'].get(DeliveryRequest, first).status == 'available'
    assert context['db'].get(DeliveryRequest, second).status == 'available'


def test_repeated_create_is_distinct_requests_not_an_idempotent_operation(owner_api):
    context = owner_api
    first, second = create(context), create(context)
    assert first.status_code == second.status_code == 201
    a, b = first.json(), second.json()
    assert a['delivery_request_id'] != b['delivery_request_id']
    assert a['reference'] != b['reference']
    rows = list(context['db'].scalars(select(DeliveryRequest).where(
        DeliveryRequest.business_id == context['business'])))
    assert len(rows) == 2
    assert all(row.created_by == context['owner'].user_id for row in rows)
    unsupported = create(context, {**AREAS, 'idempotency_key': 'synthetic-retry'})
    assert unsupported.status_code == 422
    assert read(context).json()['total'] == 2

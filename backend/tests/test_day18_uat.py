"""Continuous HTTP acceptance journeys; real login tokens, isolated MySQL only.

These are in-process API UAT, not browser E2E certification. Existing suites
retain registration, repayments, concurrency and individual error coverage.
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models import LedgerEntry
from app.services import driver_service
from test_catalogue import shop, api, db
from test_order_delivery import finance


@pytest.mark.parametrize('payment_method', ['cash', 'credit'])
def test_login_to_order_approval_delivery_and_customer_reconciliation(shop, payment_method):
    s = shop
    admin = s['make_user']('admin')
    driver = s['make_user']('driver')
    unrelated_driver = s['make_user']('driver')
    for user in (driver, unrelated_driver):
        driver_service.create_profile(s['db'], user.user_id, 'van', 'UAT-' + uuid4().hex[:8])
    _, account = s['profile'](s['business'])
    actors = dict(owner=s['owner'], customer=s['user'], admin=admin,
                  driver=driver, other_customer=s['other'],
                  other_owner=s['other_owner'], other_driver=unrelated_driver)
    # One ephemeral synthetic password/hash per journey. Neither tokens nor
    # credentials are included in assertion messages or evidence artifacts.
    password = uuid4().hex + uuid4().hex
    hashed = hash_password(password)
    for user in actors.values():
        user.password_hash = hashed
    s['db'].flush()
    tokens = {}
    for role, user in actors.items():
        result = s['client'].post('/api/v1/auth/login', data={
            'username': user.email, 'password': password})
        assert result.status_code == 200
        tokens[role] = result.json()['access_token']

    def call(role, path, method='get', payload=None, **params):
        response = getattr(s['client'], method)('/api/v1' + path,
            headers={'Authorization': 'Bearer ' + tokens[role]}, params=params,
            **({'json': payload} if payload is not None else {}))
        return response

    assert call('customer', '/admin/overview').status_code == 403
    assert call('driver', '/driver/jobs').status_code == 403
    for role in ('driver', 'other_driver'):
        response = call('admin', f'/admin/drivers/{actors[role].user_id}/decision',
                        'patch', {'decision': 'approve'})
        assert response.status_code == 200
    # Previously issued tokens must observe the newly persisted approval state.
    assert call('driver', '/driver/jobs').status_code == 200

    created = call('owner', '/shop-owner/products', 'post', {
        'name': 'Synthetic UAT item', 'unit_price': '125.25',
        'publication_status': 'published'}, business_id=s['business'])
    assert created.status_code == 201
    product_id = created.json()['product_id']
    assert call('customer', f'/customer/catalogue/shops/{s["business"]}/products').status_code == 200
    payload = dict(business_id=s['business'], payment_method=payment_method,
                   items=[dict(product_id=product_id, quantity=2)], request_key=uuid4().hex)
    submitted = call('customer', '/customer/orders', 'post', payload)
    assert submitted.status_code == 201
    order_id = submitted.json()['order_id']
    assert submitted.json()['total'] == '250.50'
    assert submitted.json()['payment_status'] == ('pending' if payment_method == 'credit' else 'unpaid')
    assert call('customer', '/customer/orders', 'post', payload).json()['order_id'] == order_id
    assert list(s['db'].scalars(select(LedgerEntry))) == []
    assert call('other_customer', f'/customer/orders/{order_id}').status_code == 404
    assert call('other_owner', f'/shop-owner/orders/{order_id}', business_id=s['business']).status_code == 404

    def decision(action):
        return call('owner', f'/shop-owner/orders/{order_id}/decision', 'post',
                    {'action': action}, business_id=s['business'])

    if payment_method == 'credit':
        first = decision('approve')
        assert first.status_code == 200
        assert decision('approve').json()['credit_sale_id'] == first.json()['credit_sale_id']
        entries = list(s['db'].scalars(select(LedgerEntry)))
        assert len(entries) == 1
        assert entries[0].order_id == order_id
        assert entries[0].credit_account_id == account.credit_account_id
        assert entries[0].amount == Decimal('250.50')
    assert decision('process').status_code == 200
    assert call('customer', f'/customer/orders/{order_id}/delivery').json()['delivery_requested'] is False
    before = finance(s)
    path = f'/shop-owner/orders/{order_id}/delivery'
    areas = dict(pickup_area='Synthetic shop area', delivery_area='Synthetic destination')
    result = call('owner', path, 'post', areas, business_id=s['business'])
    assert result.status_code == 201
    delivery_id = result.json()['delivery']['delivery_request_id']
    assert call('owner', path, 'post', areas, business_id=s['business']).json()['delivery']['delivery_request_id'] == delivery_id
    assert call('driver', f'/driver/jobs/{delivery_id}/accept', 'post', {}).status_code == 200
    assert call('other_driver', f'/driver/jobs/{delivery_id}/accept', 'post', {}).status_code == 409
    assert call('other_driver', f'/driver/deliveries/{delivery_id}').status_code == 404
    assert call('driver', f'/driver/deliveries/{delivery_id}/status', 'post',
                dict(expected_status='assigned', status='delivered')).status_code == 409
    for previous, current in [('assigned', 'picked_up'), ('picked_up', 'in_transit'), ('in_transit', 'delivered')]:
        assert call('driver', f'/driver/deliveries/{delivery_id}/status', 'post',
                    dict(expected_status=previous, status=current)).status_code == 200
        assert call('customer', f'/customer/orders/{order_id}/delivery').json()['delivery']['status'] == current
    assert finance(s) == before
    assert call('admin', '/admin/overview').status_code == 200
    assert call('admin', '/admin/audit-events').json()['total'] == 2
    assert finance(s) == before
    expected = '250.50' if payment_method == 'credit' else '0.00'
    assert call('customer', '/customer/dashboard/summary').json()['total_outstanding_balance'] == expected
    assert call('customer', f'/customer/orders/{order_id}').json()['payment_status'] == ('posted' if payment_method == 'credit' else 'unpaid')
    notifications = call('customer', '/notifications', notification_type='delivery_delivered').json()
    assert notifications['total'] == 1
    notice_id = notifications['notifications'][0]['notification_id']
    assert call('other_customer', f'/notifications/{notice_id}/read', 'patch').status_code == 404
    assert call('customer', f'/notifications/{notice_id}/read', 'patch').status_code == 200

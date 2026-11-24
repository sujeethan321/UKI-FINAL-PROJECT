"""JWT/HTTP/MySQL bridge checks with rollback-isolated existing order fixtures."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import jwt
import pytest
from sqlalchemy import select, func, event
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import (Order, OrderItem, Business, BusinessMember, CreditAccount,
    LedgerEntry, DeliveryRequest, DeliveryAssignment, DeliveryStatusEvent, Notification)
from app.services import driver_service
from app.services.ledger_service import account_balances, load_ledger_entries
from test_catalogue import shop, api, db, request
from test_orders import submit, decision

AREAS = dict(pickup_area='Shop pickup district', delivery_area='Customer delivery district')


def ready(s, method='cash', status=None):
    if method == 'credit' and 'account' not in s:
        _, s['account'] = s['profile'](s['business'])
    result = submit(s, method)
    assert result.status_code == 201, result.text
    ident = result.json()['order_id']
    if status in {'approved', 'processing', 'completed'}:
        if method == 'credit':
            assert decision(s, ident, 'approve').status_code == 200
        if status in {'processing', 'completed'}:
            assert decision(s, ident, 'process').status_code == 200
        if status == 'completed':
            assert decision(s, ident, 'complete').status_code == 200
    elif status in {'rejected', 'cancelled'}:
        assert decision(s, ident, 'reject' if status == 'rejected' else 'cancel').status_code == 200
    return ident


def create(s, ident, payload=None, actor='owner', business=None):
    return request(s, f'/shop-owner/orders/{ident}/delivery', 'post',
        AREAS if payload is None else payload, actor=actor,
        business_id=business or s['business'])


def summary(s, ident, customer=False, actor=None, business=None):
    return request(s, f'/{"customer" if customer else "shop-owner"}/orders/{ident}/delivery',
        actor=actor or ('user' if customer else 'owner'),
        **({} if customer else {'business_id': business or s['business']}))


def approved_driver(s):
    driver = s['make_user']('driver'); admin = s['make_user']('admin')
    driver.full_name = 'PRIVATE-DRIVER-NAME'; driver.phone = 'PRIVATE-DRIVER-PHONE'
    driver_service.create_profile(s['db'], driver.user_id, 'van', 'PRIVATE-REGISTRATION')
    driver_service.review_profile(s['db'], admin.user_id, driver.user_id, 'approved')
    s['db'].flush()
    return driver


def finance(s):
    fields = (Order.order_id, Order.status, Order.payment_method, Order.payment_status,
              Order.subtotal, Order.total, Order.credit_sale_id, Order.credit_account_id)
    return [s['db'].execute(select(*fields).order_by(Order.order_id)).all(), *[
        s['db'].execute(select(model.__table__).order_by(*model.__table__.primary_key)).all()
        for model in [OrderItem, CreditAccount, LedgerEntry]],
        s['db'].execute(select(Notification.__table__).where(
            Notification.related_entity_type == 'ledger_entry').order_by(Notification.notification_id)).all()]


@pytest.mark.parametrize('method,status', [('cash','processing'), ('credit','approved'), ('credit','processing')])
def test_eligible_order_creates_one_link_and_equivalent_replay(shop, method, status):
    s = shop; ident = ready(s, method, status)
    before = finance(s)
    assert summary(s, ident).json() == dict(order_id=ident, delivery_requested=False, delivery=None,
        can_request_delivery=True, delivery_unavailable_reason=None)
    assert summary(s, ident, customer=True).json() == dict(order_id=ident, delivery_requested=False, delivery=None)
    response = create(s, ident)
    assert response.status_code == 201, response.text
    data = response.json(); delivery = data['delivery']; linked = delivery['delivery_request_id']
    assert data['order_id'] == ident and data['delivery_requested']
    assert data['can_request_delivery'] is False and data['delivery_unavailable_reason']
    assert delivery['status'] == 'available' and delivery['assigned_driver'] is None
    assert delivery['business_id'] == s['business'] and delivery['events'] == []
    assert s['db'].get(Order, ident).delivery_request_id == linked
    assert create(s, ident, {k:'  '+v+'  ' for k,v in AREAS.items()}).json() == data
    assert summary(s, ident).json() == data
    assert s['db'].scalar(select(func.count()).select_from(DeliveryRequest)) == 1
    assert s['db'].scalar(select(func.count()).select_from(DeliveryAssignment)) == 0
    assert finance(s) == before
    assert 'delivery_request_id' not in request(s, f'/customer/orders/{ident}', actor='user').json()


@pytest.mark.parametrize('method,status', [(m,t) for m in ['cash','credit'] for t in ['submitted','rejected','cancelled','completed']])
def test_ineligible_orders_do_not_create_delivery(shop, method, status):
    ident = ready(shop, method, status)
    before = finance(shop)
    eligibility = summary(shop, ident).json()
    assert eligibility['can_request_delivery'] is False
    assert eligibility['delivery_unavailable_reason']
    assert finance(shop) == before
    assert create(shop, ident).status_code == 409
    assert shop['db'].get(Order, ident).delivery_request_id is None
    assert shop['db'].scalar(select(func.count()).select_from(DeliveryRequest)) == 0


@pytest.mark.parametrize('role', ['customer','driver','admin'])
def test_owner_endpoint_role_guard_is_authoritative(shop, role):
    ident = ready(shop, status='processing'); actor = shop['make_user'](role)
    assert create(shop, ident, actor=actor).status_code == 403
    assert summary(shop, ident, actor=actor).status_code == 403


def test_unauthenticated_expired_suspended_and_customer_roles(shop):
    ident = ready(shop, status='processing')
    path = f'/api/v1/shop-owner/orders/{ident}/delivery'
    assert shop['client'].post(path, params={'business_id':shop['business']}, json=AREAS).status_code == 401
    now = datetime.now(timezone.utc)
    token = jwt.encode(dict(sub=str(shop['owner'].user_id), type='access',
        iat=now-timedelta(hours=2), exp=now-timedelta(hours=1)), settings.JWT_SECRET_KEY, algorithm='HS256')
    assert shop['client'].post(path, params={'business_id':shop['business']}, json=AREAS,
        headers={'Authorization':'Bearer '+token}).status_code == 401
    for role in ['shop_owner','driver','admin']:
        assert summary(shop, ident, customer=True, actor=shop['make_user'](role)).status_code == 403
    shop['owner'].account_status = 'suspended'; shop['db'].flush()
    assert create(shop, ident).status_code == 403


@pytest.mark.parametrize('status', ['pending','rejected'])
def test_business_approval_restriction(shop, status):
    ident = ready(shop, status='processing')
    shop['db'].get(Business, shop['business']).approval_status = status; shop['db'].flush()
    assert create(shop, ident).status_code == 403
    assert summary(shop, ident).status_code == 403


def test_membership_business_and_customer_order_isolation(shop):
    ident = ready(shop, status='processing')
    assert create(shop, ident, actor='other_owner').status_code == 404
    assert create(shop, ident, business=shop['foreign']).status_code == 404
    assert summary(shop, ident, customer=True, actor='other').status_code == 404
    assert summary(shop, 9223372036854775807, customer=True).status_code == 404
    member = shop['db'].scalar(select(BusinessMember).where(BusinessMember.user_id == shop['owner'].user_id))
    member.membership_status = 'inactive'; shop['db'].flush()
    assert create(shop, ident).status_code == 404


@pytest.mark.parametrize('payload', [
    {}, {**AREAS,'pickup_area':' '}, {**AREAS,'delivery_area':'x'*161},
    {**AREAS,'delivery_area':'line\nbreak'}, {**AREAS,'pickup_area':None},
    *[{**AREAS, key:value} for key,value in [
        ('business_id',1),('order_id',1),('delivery_request_id',1),('driver_user_id',1),
        ('recipient_phone','PRIVATE'),('recipient_address','PRIVATE'),('total','0.01'),
        ('vehicle_type','van'),('coordinates',[0,0]),('status','assigned')]],
])
def test_only_valid_supported_public_areas_are_accepted(shop, payload):
    ident = ready(shop, status='processing')
    assert create(shop, ident, payload).status_code == 422
    assert shop['db'].scalar(select(func.count()).select_from(DeliveryRequest)) == 0


def test_different_payload_conflicts_and_cancelled_link_is_retained(shop):
    ident = ready(shop, 'credit', 'approved'); before = finance(shop)
    data = create(shop, ident).json(); linked = data['delivery']['delivery_request_id']
    assert create(shop, ident, {**AREAS,'delivery_area':'Different district'}).status_code == 409
    cancelled = request(shop, f'/shop-owner/deliveries/{linked}/cancel','post',{}, business_id=shop['business'])
    assert cancelled.status_code == 200, cancelled.text
    replay = create(shop, ident)
    assert replay.status_code == 201 and replay.json()['delivery']['status'] == 'cancelled'
    assert replay.json()['delivery']['delivery_request_id'] == linked
    assert shop['db'].scalar(select(func.count()).select_from(DeliveryRequest)) == 1
    assert [e['status'] for e in summary(shop,ident,customer=True).json()['delivery']['events']] == ['cancelled']
    assert finance(shop) == before


@pytest.mark.parametrize('method', ['cash','credit'])
def test_same_job_acceptance_progress_history_privacy_and_financial_isolation(shop, method):
    ident = ready(shop, method, 'processing'); before = finance(shop)
    linked = create(shop, ident).json()['delivery']['delivery_request_id']; driver = approved_driver(shop)
    jobs = request(shop, '/driver/jobs', actor=driver)
    assert jobs.status_code == 200 and jobs.json()['jobs'][0]['delivery_request_id'] == linked
    assert set(jobs.json()['jobs'][0]) == {'delivery_request_id','reference','business_name','pickup_area','delivery_area','status','created_at'}
    assert '250.50' not in jobs.text and 'customer_user_id' not in jobs.text
    assert request(shop, f'/driver/jobs/{linked}/accept','post',{},actor=driver).status_code == 200
    for status in ['picked_up','in_transit','delivered']:
        result = request(shop, f'/driver/deliveries/{linked}/status','post',
            {'status':status,'expected_status':{'picked_up':'assigned','in_transit':'picked_up','delivered':'in_transit'}[status]},actor=driver)
        assert result.status_code == 200, result.text
        assert summary(shop, ident, customer=True).json()['delivery']['status'] == status
    owner = summary(shop, ident).json()['delivery']
    assert owner['assigned_driver']['full_name'] == driver.full_name
    customer = summary(shop, ident, customer=True)
    assert set(customer.json()['delivery']) == {'reference','status','created_at','updated_at','events'}
    for private in ['PRIVATE','full_name','driver_user_id','phone','email','pickup_area','delivery_area','credit_sale_id','250.50']:
        assert private not in customer.text
    assert [e['status'] for e in customer.json()['delivery']['events']] == ['assigned','picked_up','in_transit','delivered']
    assert customer.json()['delivery']['events'] == owner['events']
    assert request(shop,f'/shop-owner/deliveries/{linked}',business_id=shop['business']).json()['events'] == owner['events']
    assert finance(shop) == before  # Delivered never means completed/paid/repaid.
    assert create(shop, ident).json()['delivery']['status'] == 'delivered'


@pytest.mark.parametrize('invalid', ['backlink','reversed','amount'])
def test_credit_requires_a_valid_posted_approval(shop, invalid):
    ident = ready(shop, 'credit', 'approved'); row = shop['db'].get(Order,ident)
    sale = shop['db'].get(LedgerEntry,row.credit_sale_id)
    if invalid == 'backlink': sale.order_id = None
    if invalid == 'amount': sale.amount = Decimal('1.00')
    if invalid == 'reversed':
        shop['db'].add(LedgerEntry(credit_account_id=sale.credit_account_id,created_by=shop['owner'].user_id,
            entry_type='reversal',amount=sale.amount,reverses_entry_id=sale.entry_id,idempotency_key=uuid4().hex))
    shop['db'].flush()
    before = finance(shop)
    capability = summary(shop, ident).json()
    assert capability['can_request_delivery'] is False
    assert capability['delivery_unavailable_reason'] == 'Order credit approval is no longer valid for delivery'
    assert finance(shop) == before
    assert create(shop, ident).status_code == 409


def test_delivery_does_not_charge_available_credit_a_second_time(shop):
    ident = ready(shop,'credit','approved'); account = shop['account']
    from test_customer_dashboard import entry
    entry(shop,account,'credit_sale','749.50')
    assert account_balances(load_ledger_entries(shop['db'],[account.credit_account_id]))[account.credit_account_id] == Decimal('1000.00')
    account.account_status = 'closed'; shop['db'].flush()
    before = finance(shop)
    assert create(shop,ident).status_code == 201
    assert finance(shop) == before


def test_database_enforces_business_consistency_and_one_order_per_delivery(shop):
    first = ready(shop,status='processing'); linked = create(shop,first).json()['delivery']['delivery_request_id']
    second = ready(shop,status='processing')
    foreign = request(shop,'/shop-owner/deliveries','post',AREAS,actor='other_owner',business_id=shop['foreign'])
    assert foreign.status_code == 201
    for delivery_id in [linked,foreign.json()['delivery_request_id']]:
        with pytest.raises(IntegrityError):
            with shop['db'].begin_nested():
                shop['db'].get(Order,second).delivery_request_id = delivery_id; shop['db'].flush()
    assert shop['db'].get(Order,second).delivery_request_id is None


@pytest.mark.parametrize('failure', ['link','commit'])
def test_failed_creation_rolls_back_both_records_and_sanitizes_errors(shop,monkeypatch,failure):
    ident = ready(shop,status='processing'); before = finance(shop)
    if failure == 'commit':
        def fail(*args,**kwargs): raise SQLAlchemyError('private database diagnostics')
        monkeypatch.setattr(Session,'commit',fail)
    else:
        from app.services import order_delivery_service
        real = order_delivery_service.deliveries.create_request
        def fail(*args,**kwargs):
            real(*args,**kwargs)
            raise SQLAlchemyError('private database diagnostics')
        monkeypatch.setattr(order_delivery_service.deliveries,'create_request',fail)
    response = create(shop,ident)
    assert response.status_code == 503 and 'private database diagnostics' not in response.text
    assert shop['db'].get(Order,ident).delivery_request_id is None
    assert shop['db'].scalar(select(func.count()).select_from(DeliveryRequest)) == 0
    assert finance(shop) == before


def test_summaries_are_read_only_and_existing_link_replays_after_owner_completion(shop):
    ident = ready(shop,status='processing'); create(shop,ident)
    seen = []; connection = shop['db'].connection()
    def observe(conn,cursor,statement,params,context,many):
        if statement.lstrip().split()[0].upper() in {'INSERT','UPDATE','DELETE','REPLACE'}: seen.append(statement)
    event.listen(connection,'before_cursor_execute',observe)
    try:
        assert summary(shop,ident).status_code == 200
        assert summary(shop,ident,customer=True).status_code == 200
    finally: event.remove(connection,'before_cursor_execute',observe)
    assert seen == []
    assert decision(shop,ident,'complete').status_code == 200
    assert create(shop,ident).status_code == 201
    assert shop['db'].scalar(select(func.count()).select_from(DeliveryRequest)) == 1

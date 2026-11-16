"""Bounded, synthetic, rollback-isolated local measurements; never a production SLA."""
import json
import math
import platform
import time
from decimal import Decimal
from pathlib import Path

from sqlalchemy import event, select, text
from app.models import User, Product, LedgerEntry, DeliveryRequest
from app.services import order_service
from test_catalogue import shop, api, db, request
from test_orders import submit
from test_order_delivery import approved_driver, finance


def measure(db, operation, repetitions=20):
    calls, durations, statements = [], [], []
    errors = 0
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    connection = db.connection()
    event.listen(connection, 'before_cursor_execute', record)
    try:
        for _ in range(repetitions):
            start_count = len(statements)
            started = time.perf_counter()
            result = operation()
            if hasattr(result, 'status_code') and result.status_code != 200:
                errors += 1
            durations.append((time.perf_counter() - started) * 1000)
            calls.append(len(statements) - start_count)
    finally:
        event.remove(connection, 'before_cursor_execute', record)
    ordered = sorted(durations)
    return result, dict(requests=repetitions, errors=errors, concurrency=1, p50_ms=ordered[math.ceil(len(ordered)*.5)-1],
        p95_ms=ordered[math.ceil(len(ordered)*.95)-1], max_queries=max(calls),
        statements=statements)


def test_order_list_query_scaling_and_local_latency(shop):
    for _ in range(20):
        assert submit(shop).status_code == 201
    s = shop
    # Expunge identity-map cached related rows to measure real query growth.
    s['db'].expunge_all()
    user = s['db'].get(User, s['user'].user_id)
    one, small = measure(s['db'], lambda: order_service.listing(s['db'], user, 1, 1), 5)
    many, large = measure(s['db'], lambda: order_service.listing(s['db'], user, 1, 20))
    assert one['total'] == many['total'] == 20
    assert len(many['orders']) == 20
    assert large['max_queries'] == small['max_queries'] == 3
    output = {key: value for key, value in large.items() if key != 'statements'}
    output.update(dataset={'orders':20, 'items_per_order':1}, environment=platform.platform(),
                  small_page_max_queries=small['max_queries'], errors=0)
    root = Path(__file__).resolve().parents[2]
    (root / '.server-logs/day17-3-order-benchmark.json').write_text(json.dumps(output, indent=2))


def test_controlled_synthetic_http_read_workload(shop):
    from uuid import uuid4
    from app.core.security import hash_password
    s = shop
    for _ in range(20):
        assert submit(s).status_code == 201
    s['db'].add_all([Product(business_id=s['business'], name=f'Synthetic product {n}',
        unit_price=Decimal('1.25'), publication_status='published') for n in range(19)])
    _, account = s['profile'](s['business'])
    s['db'].add_all([LedgerEntry(credit_account_id=account.credit_account_id,
        created_by=s['owner'].user_id, entry_type='credit_sale', amount=Decimal('1.25'),
        idempotency_key=uuid4().hex) for _ in range(20)])
    driver = approved_driver(s)
    admin = s['make_user']('admin')
    s['db'].add_all([DeliveryRequest(reference='synthetic-'+uuid4().hex,
        business_id=s['business'], created_by=s['owner'].user_id,
        pickup_area='Synthetic pickup', delivery_area='Synthetic destination') for _ in range(20)])
    s['user'].password_hash = hash_password('Synthetic-only-login-fixture-2026')
    s['db'].flush()
    before = finance(s)
    scenarios = {
        'shops': lambda: request(s, '/customer/catalogue/shops', actor='user', page_size=10),
        'products': lambda: request(s, f'/customer/catalogue/shops/{s["business"]}/products', actor='user', page_size=10),
        'order_history': lambda: request(s, '/customer/orders', actor='user', page_size=10),
        'transactions': lambda: request(s, '/customer/transactions', actor='user', page_size=10),
        'customer_dashboard': lambda: request(s, '/customer/dashboard/summary', actor='user'),
        'owner_dashboard': lambda: request(s, '/shop-owner/dashboard/summary', business_id=s['business']),
        'driver_jobs': lambda: request(s, '/driver/jobs', actor=driver, page_size=10),
        'admin_overview': lambda: request(s, '/admin/overview', actor=admin),
    }
    results = {}
    for name, operation in scenarios.items():
        response, measured = measure(s['db'], operation, 10)
        assert response.status_code == 200, (name, response.status_code)
        assert measured['errors'] == 0, name
        results[name] = {key: value for key,value in measured.items() if key != 'statements'}
        assert not any(sql.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for sql in measured['statements'])
    def login():
        return s['client'].post('/api/v1/auth/login', data={
            'username':s['user'].email, 'password':'Synthetic-only-login-fixture-2026'})
    response, measured = measure(s['db'], login, 3)
    assert response.status_code == 200
    assert measured['errors'] == 0
    results['login'] = {key:value for key,value in measured.items() if key != 'statements'}
    assert finance(s) == before
    plan = s['db'].execute(text('EXPLAIN SELECT order_id FROM orders WHERE customer_user_id=:user ORDER BY order_id DESC LIMIT 10'),
                           {'user':s['user'].user_id}).mappings().all()
    output = dict(results=results, errors=sum(item['errors'] for item in results.values()), concurrency=1, environment=platform.platform(),
        cpu_count=__import__('os').cpu_count(), dataset=dict(orders=20, order_items=20,
        products=20, ledger_entries=20, jobs=20), explain=[{
            key:row[key] for key in ('table','type','key','rows','Extra')} for row in plan])
    (Path(__file__).resolve().parents[2] / '.server-logs/day17-3-http-benchmark.json').write_text(json.dumps(output,indent=2))

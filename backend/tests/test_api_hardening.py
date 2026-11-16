"""Deterministic limiter/HTTP tests plus actual authenticated JWT integration."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import Settings, settings
from app.core.http_security import configure_http_security
from app.core.rate_limit import LocalLimiter, authenticated_limit, login_limit, registration_limit
from app.core.request_limits import RequestBodyLimitMiddleware
from test_catalogue import shop, api, db, request as scoped_request, public
from test_orders import submit
from test_production_config import production_values


def http_app():
    app = FastAPI()
    config = settings.model_copy(update={'RATE_LIMIT_LOGIN': 2, 'RATE_LIMIT_LOGIN_IP': 4,
        'RATE_LIMIT_REGISTRATION': 2, 'RATE_LIMIT_MUTATION': 2, 'RATE_LIMIT_EXPORT': 1,
        'MAX_REQUEST_BODY_BYTES': 1024})
    configure_http_security(app, config)

    @app.post('/login', dependencies=[Depends(login_limit)])
    def login():
        return {'ok': True}

    @app.post('/register', dependencies=[Depends(registration_limit)])
    def register():
        return {'ok': True}

    @app.post('/mutation/{ident}')
    def mutation(request: Request, ident: int, actor: int = 1):
        # Synthetic actor for identity-unit tests only, not a production endpoint.
        authenticated_limit(request, actor)
        return {'ok': True}

    return app


def test_limiter_expiry_atomic_keys_and_bounded_capacity():
    now = [100.0]
    limiter = LocalLimiter(window=10, capacity=2, clock=lambda: now[0])
    assert limiter.consume([('a', 2), ('b', 1)]) is None
    assert limiter.consume([('a', 2), ('b', 1)]) == 10
    assert limiter.entries['a'][1] == 1  # No partial consumption on rejection.
    assert limiter.consume([('c', 2)]) == 10
    assert len(limiter.entries) == 2
    now[0] = 110
    assert limiter.consume([('c', 1)]) is None
    assert list(limiter.entries) == ['c']


def test_concurrent_local_consume_never_exceeds_quota():
    limiter = LocalLimiter()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: limiter.consume([('same', 5)]), range(40)))
    assert results.count(None) == 5
    assert sum(value is not None for value in results) == 35


def test_normalized_login_key_forwarded_spoofing_429_retry_and_cors():
    app = http_app()
    with TestClient(app) as client:
        for email in [' User@Example.invalid ', 'user@example.invalid']:
            assert client.post('/login', data={'username': email, 'password': 'private-sentinel'}).status_code == 200
        blocked = client.post('/login', data={'username': 'USER@example.invalid', 'password': 'private-sentinel'},
            headers={'X-Forwarded-For': '198.51.100.20', 'Forwarded': 'for=198.51.100.21',
                     'Origin': 'http://localhost:5173'})
        assert blocked.status_code == 429
        assert int(blocked.headers['retry-after']) >= 1
        assert blocked.headers['access-control-allow-origin'] == 'http://localhost:5173'
        assert 'Retry-After' in blocked.headers['access-control-expose-headers']
        assert 'private-sentinel' not in blocked.text
        assert not any('example.invalid' in str(key) for key in app.state.rate_limiter.entries)
        # Identifier changes do not bypass the independent peer-IP quota.
        for email in ['other1@example.invalid', 'other2@example.invalid']:
            assert client.post('/login', data={'username': email, 'password': 'fixture'}).status_code == 200
        assert client.post('/login', data={'username': 'other3@example.invalid', 'password': 'fixture'}).status_code == 429


def test_user_operation_and_application_instance_isolation():
    with TestClient(http_app()) as client:
        assert client.post('/mutation/1?actor=1').status_code == 200
        assert client.post('/mutation/2?actor=1').status_code == 200
        assert client.post('/mutation/3?actor=1&business_id=99').status_code == 429
        assert client.post('/mutation/3?actor=2').status_code == 200
        assert client.post('/register').status_code == 200
    # Independent application instances have independent stores: NOT distributed.
    with TestClient(http_app()) as other:
        assert other.post('/mutation/1?actor=1').status_code == 200


def test_request_body_limit_request_ids_and_normal_form_compatibility():
    with TestClient(http_app()) as client:
        response = client.post('/register', content=b'x'*1025, headers={'X-Request-ID': 'untrusted-id'})
        assert response.status_code == 413
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert len(response.headers['x-request-id']) == 32
        assert response.headers['x-request-id'] != 'untrusted-id'
        valid = client.post('/login', data={'username': 'fixture@example.invalid', 'password': 'fixture'})
        assert valid.status_code == 200
        assert valid.headers['x-request-id'] != response.headers['x-request-id']


def test_chunked_body_limit_without_content_length():
    called = []
    async def downstream(scope, receive, send):
        called.append(True)
    middleware = RequestBodyLimitMiddleware(downstream, max_bytes=10)
    messages = iter([{'type': 'http.request', 'body': b'123456', 'more_body': True},
                     {'type': 'http.request', 'body': b'123456', 'more_body': False}])
    sent = []
    async def receive():
        return next(messages)
    async def send(message):
        sent.append(message)
    asyncio.run(middleware({'type': 'http', 'method': 'POST', 'headers': []}, receive, send))
    assert not called
    assert sent[0]['status'] == 413


def test_production_refuses_process_local_limiter(monkeypatch):
    for key in Settings.model_fields:
        monkeypatch.delenv(key, raising=False)
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **(production_values() | {'RATE_LIMIT_MODE': 'local'}))
    config = Settings(_env_file=None, **production_values())
    assert config.RATE_LIMIT_MODE == 'external'


def test_real_jwt_mutation_limits_are_user_scoped_and_do_not_log_out(shop, monkeypatch):
    from app.main import app
    monkeypatch.setattr(settings, 'RATE_LIMIT_MUTATION', 1)
    first = submit(shop)
    assert first.status_code == 201
    second = submit(shop)
    assert second.status_code == 429
    assert scoped_request(shop, '/customer/orders', actor='user').status_code == 200
    assert scoped_request(shop, '/customer/orders', actor='other').status_code == 200
    assert app.state.rate_limiter is not None


def test_oversized_search_pagination_injection_and_private_errors(shop):
    assert public(shop, q='x'*201).status_code == 422
    assert public(shop, page_size=101).status_code == 422
    response = public(shop, q="' OR 1=1 --")
    assert response.status_code == 200 and response.json()['products'] == []
    assert 'password' not in response.text.lower()


def test_missing_account_still_verifies_dummy_password(monkeypatch):
    from app.routers.auth import login
    spy = Mock(return_value=False)
    monkeypatch.setattr('app.routers.auth.verify_password', spy)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        login(OAuth2PasswordRequestForm(username='missing@example.invalid', password='fixture'),
              SimpleNamespace(scalar=lambda _: None))
    assert error.value.status_code == 401
    assert spy.call_count == 1


def test_legacy_reads_fail_explicitly_instead_of_returning_partial_balances(shop, monkeypatch):
    from app.models import LedgerEntry
    from decimal import Decimal
    from uuid import uuid4
    s = shop
    for _ in range(2):
        s['profile'](s['business'])
    monkeypatch.setattr(settings, 'MAX_INTERACTIVE_CUSTOMERS', 1)
    response = scoped_request(s, '/shop-owner/customers', business_id=s['business'])
    assert response.status_code == 422 and 'customers' not in response.json()
    monkeypatch.setattr(settings, 'MAX_INTERACTIVE_CUSTOMERS', 1000)
    _, account = s['profile'](s['business'])
    for _ in range(2):
        s['db'].add(LedgerEntry(credit_account_id=account.credit_account_id,
            created_by=s['owner'].user_id, entry_type='credit_sale', amount=Decimal('1.25'),
            idempotency_key=uuid4().hex))
    s['db'].flush()
    monkeypatch.setattr(settings, 'MAX_READ_LEDGER_ENTRIES', 1)
    assert scoped_request(s, '/shop-owner/customers', business_id=s['business']).status_code == 422
    assert scoped_request(s, '/shop-owner/dashboard/summary', business_id=s['business']).status_code == 422


def test_admin_audit_read_limit_and_role_boundary(shop, monkeypatch):
    monkeypatch.setattr(settings, 'RATE_LIMIT_EXPORT', 1)
    admin = shop['make_user']('admin')
    assert scoped_request(shop, '/admin/audit-events', actor='user').status_code == 403
    assert scoped_request(shop, '/admin/audit-events', actor=admin).status_code == 200
    assert scoped_request(shop, '/admin/audit-events', actor=admin).status_code == 429

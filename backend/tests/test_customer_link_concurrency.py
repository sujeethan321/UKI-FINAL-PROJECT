"""Independent MySQL connections prove a six-digit invitation links at most once."""
from concurrent.futures import ThreadPoolExecutor
from itertools import count
from threading import Event, Lock
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.core.security import create_access_token
from app.main import app
from app.models import Business, BusinessMember, CustomerLinkInvitation, CustomerProfile, User
from app.services import customer_link_service


def test_simultaneous_reissue_and_acceptance_are_serialized(monkeypatch):
    assert settings.APP_ENV == 'testing' and settings.MYSQL_DATABASE == engine.url.database == 'lankapex_test_db'
    with engine.connect() as connection:
        assert connection.scalar(text('SELECT DATABASE()')) == 'lankapex_test_db'
        assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '7b9e4d2c8a15'
    assert not app.dependency_overrides
    owner_id = customer_id = business_id = profile_id = customer_email = None
    try:
        with Session(engine) as session:
            owner = User(full_name='Synthetic owner', email=f'link-race-owner-{uuid4().hex}@example.com',
                         password_hash='test-only', platform_role='shop_owner', account_status='active', preferred_language='en')
            customer = User(full_name='Synthetic customer', email=f'link-race-customer-{uuid4().hex}@example.com',
                            password_hash='test-only', platform_role='customer', account_status='active', preferred_language='en')
            session.add_all([owner, customer]); session.flush()
            owner_id, customer_id, customer_email = owner.user_id, customer.user_id, customer.email
            business = Business(business_name='Synthetic invitation race shop', business_type='retail', approval_status='approved')
            session.add(business); session.flush()
            business_id = business.business_id
            session.add(BusinessMember(business_id=business_id, user_id=owner_id,
                                       business_role='owner', membership_status='active'))
            profile = CustomerProfile(business_id=business_id, customer_name='Synthetic customer')
            session.add(profile); session.flush()
            profile_id = profile.customer_id
            session.commit()

        owner_headers = {'Authorization': 'Bearer ' + create_access_token(owner_id)}
        customer_headers = {'Authorization': 'Bearer ' + create_access_token(customer_id)}
        issue_path = f'/api/v1/shop-owner/customers/{profile_id}/link-invitations'
        accept_path = '/api/v1/customer/link-invitations/accept'
        with TestClient(app) as client:
            issued = client.post(issue_path, params={'business_id': business_id},
                                 json={'recipient_email': customer_email}, headers=owner_headers)
            assert issued.status_code == 200
            code = issued.json()['invitation']
            assert len(code) == 6 and code.isascii() and code.isdecimal()
            def race(send):
                reached = Event()
                guard = Lock()
                attempts = 0

                def observe_lock(connection, cursor, statement, parameters, context, executemany):
                    nonlocal attempts
                    sql = statement.lower()
                    if 'from businesses' in sql and 'for update' in sql:
                        with guard:
                            attempts += 1
                            if attempts >= 2:
                                reached.set()

                with engine.connect() as blocker:
                    transaction = blocker.begin()
                    blocker.execute(select(Business.business_id).where(Business.business_id == business_id).with_for_update()).all()
                    event.listen(engine, 'before_cursor_execute', observe_lock)
                    try:
                        with ThreadPoolExecutor(max_workers=2) as pool:
                            futures = [pool.submit(send) for _ in range(2)]
                            try:
                                assert reached.wait(20), 'Both requests must reach the business row lock'
                                assert all(not future.done() for future in futures)
                            finally:
                                transaction.rollback()
                            return [future.result(timeout=30) for future in futures]
                    finally:
                        if transaction.is_active:
                            transaction.rollback()
                        event.remove(engine, 'before_cursor_execute', observe_lock)

            # Distinct deterministic test codes remove the rare random-collision flake.
            sequence = count(1)
            monkeypatch.setattr(customer_link_service, 'randbelow',
                                lambda _: (int(code) + next(sequence)) % 1_000_000)
            reissued = race(lambda: client.post(issue_path, params={'business_id': business_id},
                                                 json={'recipient_email': customer_email}, headers=owner_headers))
            assert [response.status_code for response in reissued] == [200, 200]
            new_codes = [response.json()['invitation'] for response in reissued]
            assert len(set(new_codes)) == 2 and code not in new_codes
            with Session(engine) as session:
                current_digest = session.get(CustomerLinkInvitation, profile_id).code_digest
            active = [value for value in new_codes if customer_link_service._digest(value) == current_digest]
            assert len(active) == 1
            assert client.post(accept_path, json={'invitation': code}, headers=customer_headers).status_code == 404
            inactive = next(value for value in new_codes if value != active[0])
            assert client.post(accept_path, json={'invitation': inactive}, headers=customer_headers).status_code == 404
            code = active[0]
            responses = race(lambda: client.post(accept_path, json={'invitation': code}, headers=customer_headers))
            assert sorted(response.status_code for response in responses) == [200, 404]
            assert client.post(accept_path, json={'invitation': code}, headers=customer_headers).status_code == 404
        with Session(engine) as session:
            assert session.get(CustomerProfile, profile_id).user_id == customer_id
            assert session.scalar(select(func.count()).select_from(CustomerLinkInvitation).where(
                CustomerLinkInvitation.customer_id == profile_id)) == 0
    finally:
        with engine.begin() as connection:
            assert connection.scalar(text('SELECT DATABASE()')) == 'lankapex_test_db'
            if profile_id is not None:
                connection.execute(delete(CustomerLinkInvitation).where(CustomerLinkInvitation.customer_id == profile_id))
                connection.execute(delete(CustomerProfile).where(CustomerProfile.customer_id == profile_id))
            if business_id is not None:
                connection.execute(delete(BusinessMember).where(BusinessMember.business_id == business_id))
                connection.execute(delete(Business).where(Business.business_id == business_id))
            if owner_id is not None:
                connection.execute(delete(User).where(User.user_id.in_([owner_id, customer_id])))

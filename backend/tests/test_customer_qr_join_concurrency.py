"""Independent MySQL sessions verify two owner approvals create one profile."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from uuid import uuid4

from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.models import Business, BusinessMember, CustomerJoinRequest, CustomerProfile, User
from app.services import customer_join_service


def test_simultaneous_approvals_create_exactly_one_profile():
    assert settings.APP_ENV == "testing" and settings.MYSQL_DATABASE == engine.url.database == "lankapex_test_db"
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT DATABASE()")) == "lankapex_test_db"
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "7b9e4d2c8a15"
    owner_id = customer_id = business_id = request_id = None
    try:
        with Session(engine) as db:
            owner = User(full_name="Synthetic QR owner", email=f"qr-race-o-{uuid4().hex}@example.com",
                         password_hash="test-only", platform_role="shop_owner", account_status="active", preferred_language="en")
            customer = User(full_name="Synthetic QR customer", email=f"qr-race-c-{uuid4().hex}@example.com",
                            password_hash="test-only", platform_role="customer", account_status="active", preferred_language="en")
            db.add_all((owner, customer))
            db.flush()
            owner_id, customer_id = owner.user_id, customer.user_id
            business = Business(business_name="Synthetic QR race shop", business_type="retail", approval_status="approved")
            db.add(business)
            db.flush()
            business_id = business.business_id
            db.add(BusinessMember(business_id=business_id, user_id=owner_id,
                                  business_role="owner", membership_status="active"))
            request = CustomerJoinRequest(business_id=business_id, customer_user_id=customer_id, status="pending")
            db.add(request)
            db.commit()
            request_id = request.request_id

        reached = Event()
        guard = Lock()
        attempts = 0

        def observe_lock(connection, cursor, statement, parameters, context, executemany):
            nonlocal attempts
            sql = statement.lower()
            if "from businesses" in sql and "for update" in sql:
                with guard:
                    attempts += 1
                    if attempts >= 2:
                        reached.set()

        def approve():
            with Session(engine) as session:
                owner = session.get(User, owner_id)
                result = customer_join_service.decide(session, owner, business_id, request_id, "approve")
                session.commit()
                return result["status"]

        with engine.connect() as blocker:
            transaction = blocker.begin()
            blocker.execute(select(Business.business_id).where(
                Business.business_id == business_id).with_for_update()).all()
            event.listen(engine, "before_cursor_execute", observe_lock)
            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(approve) for _ in range(2)]
                    try:
                        assert reached.wait(20), "Both approvals must reach the business lock"
                        assert all(not future.done() for future in futures)
                    finally:
                        transaction.rollback()
                    assert [future.result(timeout=30) for future in futures] == ["approved", "approved"]
            finally:
                if transaction.is_active:
                    transaction.rollback()
                event.remove(engine, "before_cursor_execute", observe_lock)
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(CustomerProfile).where(
                CustomerProfile.business_id == business_id,
                CustomerProfile.user_id == customer_id)) == 1
            assert db.get(CustomerJoinRequest, request_id).status == "approved"
    finally:
        if business_id is not None:
            with Session(engine) as db:
                db.execute(delete(CustomerProfile).where(CustomerProfile.business_id == business_id,
                                                         CustomerProfile.user_id == customer_id))
                db.execute(delete(CustomerJoinRequest).where(CustomerJoinRequest.business_id == business_id))
                db.execute(delete(BusinessMember).where(BusinessMember.business_id == business_id))
                db.execute(delete(Business).where(Business.business_id == business_id))
                if owner_id is not None:
                    db.execute(delete(User).where(User.user_id == owner_id))
                if customer_id is not None:
                    db.execute(delete(User).where(User.user_id == customer_id))
                db.commit()

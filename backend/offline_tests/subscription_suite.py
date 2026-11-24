"""Run directly with Python: SQLite-only integration tests, with networking blocked.

Does not import real settings, dotenv, MySQL engine, or tests/conftest.py.
"""
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch
from datetime import datetime, timezone
import socket
import threading
import tempfile
import importlib.util

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def forbidden(*args, **kwargs):
    raise AssertionError("Network is forbidden in the offline subscription suite")

original_connect, original_socketpair = socket.socket.connect, socket.socketpair
ipc = threading.local()

def offline_connect(sock, address):
    # Windows asyncio implements its wake-up socketpair over loopback TCP.
    # Only that synchronous stdlib call may connect; all application networking
    # (including any attempt to connect to MySQL) remains blocked.
    if getattr(ipc, "creating_pair", False):
        return original_connect(sock, address)
    return forbidden()

def offline_socketpair(*args, **kwargs):
    ipc.creating_pair = True
    try:
        return original_socketpair(*args, **kwargs)
    finally:
        ipc.creating_pair = False

socket.socketpair = offline_socketpair
socket.create_connection = forbidden
socket.socket.connect = offline_connect
socket.socket.connect_ex = forbidden

from sqlalchemy import BigInteger, create_engine, event, select, func
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.pool import StaticPool

@compiles(BigInteger, "sqlite")
def sqlite_bigint(type_, compiler, **kwargs):
    return "INTEGER"

class Base(DeclarativeBase):
    pass

def get_db():
    raise AssertionError("Tests must explicitly inject a SQLite session")

database = ModuleType("app.core.database")
database.Base, database.get_db = Base, get_db
config = ModuleType("app.core.config")
config.settings = SimpleNamespace(JWT_SECRET_KEY="offline-synthetic-only", ACCESS_TOKEN_EXPIRE_MINUTES=30)
sys.modules["app.core.database"] = database
sys.modules["app.core.config"] = config

from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient
from app.models import Business, BusinessApprovalAudit, BusinessMember, User
from app.models.subscription import BusinessSubscription, SubscriptionTrialGrant, SubscriptionPaymentEvent
from app.services import subscription_service as service
from app.routers import subscriptions
from app.routers import admin_businesses
from app.core.auth_dependencies import get_current_user
from app.schemas.admin_business import BusinessDecisionRequest

TABLES = [User.__table__, Business.__table__, BusinessMember.__table__, BusinessApprovalAudit.__table__,
    BusinessSubscription.__table__, SubscriptionTrialGrant.__table__, SubscriptionPaymentEvent.__table__]

def create_tables(engine):
    @event.listens_for(engine, "connect")
    def fk(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine, tables=TABLES)

def seed(db):
    db.add_all([User(user_id=i, full_name=f"Synthetic {i}", email=f"synthetic{i}@example.invalid", password_hash="unused", platform_role=role, account_status="active")
        for i, role in [(1, "admin"), (2, "shop_owner"), (3, "shop_owner"), (4, "customer"), (5, "driver")]])
    db.flush()
    db.add_all([Business(business_id=i, business_name=f"Synthetic Shop {i}", business_type="retail", approval_status="pending") for i in [10, 20, 30]])
    db.flush()
    db.add_all([BusinessMember(business_id=b, user_id=u, business_role="owner", membership_status="active") for b, u in [(10, 2), (20, 3), (30, 2)]])
    db.commit()

class SubscriptionTests(TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        create_tables(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        seed(self.db)
        self.now = datetime(2028, 1, 31, 17, 45, 20, 123456)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def decide(self, decision="approve"):
        with patch.object(admin_businesses, "admin_actor"), patch.object(admin_businesses, "notify_event"), patch.object(admin_businesses, "utc_now", return_value=self.now):
            return admin_businesses.decide_business(10, BusinessDecisionRequest(decision=decision), Response(), self.db.get(User, 1), self.db)

    def test_first_approval_is_atomic_and_shares_persisted_audit_timestamp(self):
        self.assertEqual(self.decide()["approval_status"], "approved")
        grant = self.db.get(SubscriptionTrialGrant, 10)
        audit = self.db.scalar(select(BusinessApprovalAudit))
        self.assertEqual(grant.trial_started_at, audit.created_at)
        self.assertEqual(grant.trial_started_at, self.now)
        self.assertEqual(grant.trial_ends_at, datetime(2028, 2, 29, 17, 45, 20, 123456))
        self.assertEqual(self.db.get(BusinessSubscription, 10).status, "TRIALING")
        self.assertIsNone(self.db.get(BusinessSubscription, 10).stripe_customer_id)
        self.assertEqual(service.evaluate(self.db.get(BusinessSubscription, 10), grant, self.now)["effective_plan"], "PRO")

    def test_repeated_approval_and_pending_reset_never_extend_trial(self):
        self.decide()
        original = self.db.get(SubscriptionTrialGrant, 10).trial_ends_at
        with self.assertRaises(HTTPException) as error:
            self.decide()
        self.assertEqual(error.exception.status_code, 409)
        self.db.get(Business, 10).approval_status = "pending"
        self.db.commit()
        self.now = datetime(2028, 3, 1)
        self.decide()
        self.assertEqual(self.db.get(SubscriptionTrialGrant, 10).trial_ends_at, original)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(SubscriptionTrialGrant)), 1)

    def test_failure_rolls_back_business_audit_subscription_and_grant(self):
        with patch.object(admin_businesses, "admin_actor"), patch.object(admin_businesses, "notify_event", side_effect=RuntimeError("synthetic failure")):
            with self.assertRaises(RuntimeError):
                admin_businesses.decide_business(10, BusinessDecisionRequest(decision="approve"), Response(), self.db.get(User, 1), self.db)
        self.assertEqual(self.db.get(Business, 10).approval_status, "pending")
        for model in [SubscriptionTrialGrant, BusinessSubscription, BusinessApprovalAudit]:
            self.assertEqual(self.db.scalar(select(func.count()).select_from(model)), 0)

    def test_rejection_grants_no_trial(self):
        self.decide("reject")
        self.assertIsNone(self.db.get(SubscriptionTrialGrant, 10))

    def test_existing_approved_exclusion_and_audit_prevent_retroactive_grants(self):
        self.db.add(SubscriptionTrialGrant(business_id=10, grant_status="EXCLUDED", created_at=self.now))
        self.db.commit()
        self.decide()
        self.assertIsNone(self.db.get(BusinessSubscription, 10))
        self.assertEqual(self.db.get(SubscriptionTrialGrant, 10).grant_status, "EXCLUDED")
        self.db.add(BusinessApprovalAudit(business_id=20, admin_user_id=1, decision="approve", previous_status="pending", new_status="approved", created_at=self.now))
        self.db.commit()
        service.grant_first_approval_trial(self.db, self.db.get(Business, 20), self.now)
        self.db.commit()
        self.assertEqual(self.db.get(SubscriptionTrialGrant, 20).grant_status, "EXCLUDED")
        self.assertIsNone(self.db.get(BusinessSubscription, 20))

    def test_calendar_month_boundaries_use_sri_lanka_local_date(self):
        for start, expected in [
            (datetime(2027, 1, 31, 12), datetime(2027, 2, 28, 12)),
            (datetime(2028, 1, 31, 12), datetime(2028, 2, 29, 12)),
            (datetime(2028, 12, 31, 12), datetime(2029, 1, 31, 12)),
            # UTC Jan 30 is already Jan 31 in Sri Lanka; end is local Feb 29.
            (datetime(2028, 1, 30, 20), datetime(2028, 2, 28, 20)),
            (datetime(2028, 2, 29, 12, tzinfo=timezone.utc), datetime(2028, 3, 29, 12)),
        ]:
            with self.subTest(start=start):
                self.assertEqual(service.calendar_month_end(start), expected)

    def test_exact_expiry_is_free_without_writes_or_worker(self):
        self.decide()
        grant = self.db.get(SubscriptionTrialGrant, 10)
        subscription = self.db.get(BusinessSubscription, 10)
        result = service.evaluate(subscription, grant, grant.trial_ends_at)
        self.assertEqual(result["effective_plan"], "FREE")
        self.assertTrue(result["upgrade_required"])
        self.assertEqual(result["trial_remaining_seconds"], 0)
        self.assertEqual(subscription.status, "TRIALING")
        self.assertFalse(self.db.dirty)
        for feature in service.FEATURES:
            self.assertEqual(result["entitlements"][feature],service.ENTITLEMENTS['FREE'][feature])

    def test_paid_period_overrides_expired_trial_and_requires_bound_provider_ids(self):
        self.decide()
        subscription = self.db.get(BusinessSubscription, 10)
        grant = self.db.get(SubscriptionTrialGrant, 10)
        subscription.plan, subscription.status = "BUSINESS", "ACTIVE"
        subscription.started_at, subscription.paid_through = datetime(2028, 2, 1), datetime(2028, 4, 1)
        subscription.stripe_customer_id, subscription.stripe_subscription_id = "cus_synthetic", "sub_synthetic"
        self.assertEqual(service.evaluate(subscription, grant, datetime(2028, 3, 1))["effective_plan"], "BUSINESS")
        self.assertEqual(service.evaluate(subscription, grant, datetime(2028, 4, 1))["effective_plan"], "FREE")
        subscription.stripe_subscription_id = None
        self.assertEqual(service.evaluate(subscription, grant, datetime(2028, 3, 1))["effective_plan"], "FREE")

    def test_tenant_isolation_admin_read_only_and_membership_rules(self):
        owner = self.db.get(User, 2)
        for ident in [10, 30]:
            self.assertEqual(service.authorize_business(self.db, owner, ident).business_id, ident)
        for ident in [20, 999]:
            with self.assertRaises(HTTPException) as error:
                service.authorize_business(self.db, owner, ident)
            self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(service.authorize_business(self.db, self.db.get(User, 1), 20).business_id, 20)
        for actor in [1, 4, 5]:
            with self.assertRaises(HTTPException):
                service.authorize_business(self.db, self.db.get(User, actor), 10, manage=True)
        member = self.db.scalar(select(BusinessMember).where(BusinessMember.business_id == 10))
        member.membership_status = "inactive"
        self.db.commit()
        with self.assertRaises(HTTPException):
            service.authorize_business(self.db, owner, 10)
        owner.account_status = "suspended"
        with self.assertRaises(HTTPException) as error:
            service.authorize_business(self.db, owner, 30)
        self.assertEqual(error.exception.status_code, 403)

    def test_unknown_features_fail_closed_existing_features_remain_accessible(self):
        self.db.get(Business, 10).approval_status = "approved"
        self.db.commit()
        service.require_entitlement(self.db, self.db.get(User, 2), 10, "repayments")
        with self.assertRaises(HTTPException):
            service.require_entitlement(self.db, self.db.get(User, 2), 10, "unapproved_feature")

    def test_http_response_contract_and_payment_endpoints_fail_closed(self):
        app = FastAPI()
        app.include_router(subscriptions.router, prefix="/api/v1")
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: self.db.get(User, 2)
        self.db.get(Business, 10).approval_status = "approved"
        self.db.commit()
        with TestClient(app) as client:
            plans = client.get("/api/v1/subscriptions/plans")
            self.assertEqual(plans.status_code, 200)
            self.assertEqual([(p["monthly_minor"], p["yearly_minor"]) for p in plans.json()["plans"]], [(0, 0), (49900, 499000), (129900, 1299000)])
            self.assertFalse(plans.json()["payment_configured"])
            for endpoint in ["current", "entitlements", "trial"]:
                result = client.get(f"/api/v1/subscriptions/{endpoint}?business_id=10")
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()["effective_plan"], "FREE")
                self.assertEqual(result.headers["cache-control"], "no-store")
                self.assertNotIn("stripe_customer_id", result.json())
            self.assertEqual(client.get("/api/v1/subscriptions/current?business_id=20").status_code, 404)
            for endpoint, body in [("checkout", {"plan": "PRO", "billing_interval": "month", "request_id": "synthetic_request_1"}), ("portal", {})]:
                result = client.post(f"/api/v1/subscriptions/{endpoint}?business_id=10", json=body)
                self.assertEqual(result.status_code, 503)
                self.assertEqual(result.json()["detail"], "Payment integration not configured")
            result = client.post("/api/v1/subscriptions/checkout?business_id=10", json={"plan": "PRO", "billing_interval": "month", "request_id": "synthetic_request_1", "amount": 1})
            self.assertEqual(result.status_code, 422)
            for headers in [{}, {"Stripe-Signature": "forged"}]:
                self.assertEqual(client.post("/api/v1/subscriptions/webhook", json={"livemode": True}, headers=headers).status_code, 503)
            self.assertEqual(client.get("/api/v1/subscriptions/history?business_id=10").json()["invoices"], [])
        for table in [BusinessSubscription, SubscriptionPaymentEvent, SubscriptionTrialGrant]:
            self.assertEqual(self.db.scalar(select(func.count()).select_from(table)), 0)

    def test_database_constraints_reject_duplicate_grants_and_payment_events(self):
        self.decide()
        self.db.add(SubscriptionTrialGrant(business_id=10, grant_status="EXCLUDED", created_at=self.now))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()
        fields = dict(event_id="evt_synthetic", business_id=10, event_type="invoice.paid", provider_mode="sandbox", currency="lkr", amount_minor=49900, received_at=self.now)
        self.db.add(SubscriptionPaymentEvent(**fields)); self.db.commit()
        self.db.add(SubscriptionPaymentEvent(**fields))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()
        self.assertEqual(self.db.scalar(select(func.count()).select_from(SubscriptionPaymentEvent)), 1)

    def test_constraints_reject_null_trial_end_invalid_plans_and_live_mode(self):
        self.db.add(SubscriptionTrialGrant(business_id=10, grant_status="GRANTED", trial_started_at=self.now, created_at=self.now))
        with self.assertRaises(IntegrityError): self.db.commit()
        self.db.rollback()
        for plan, provider in [("UNKNOWN", "sandbox"), ("PRO", "live")]:
            self.db.add(BusinessSubscription(business_id=10, plan=plan, status="TRIALING", provider_mode=provider, created_at=self.now, updated_at=self.now))
            with self.assertRaises(IntegrityError): self.db.commit()
            self.db.rollback()

    def test_role_dependency_blocks_customer_driver_and_admin_billing_management(self):
        app = FastAPI()
        app.include_router(subscriptions.router, prefix="/api/v1")
        app.dependency_overrides[get_db] = lambda: self.db
        with TestClient(app) as client:
            for ident in [4, 5]:
                app.dependency_overrides[get_current_user] = lambda ident=ident: self.db.get(User, ident)
                self.assertEqual(client.get("/api/v1/subscriptions/plans").status_code, 403)
                self.assertEqual(client.get("/api/v1/subscriptions/current?business_id=10").status_code, 403)
            app.dependency_overrides[get_current_user] = lambda: self.db.get(User, 1)
            self.assertEqual(client.get("/api/v1/subscriptions/current?business_id=20").status_code, 200)
            self.assertEqual(client.post("/api/v1/subscriptions/portal?business_id=20").status_code, 403)

    def test_mysql_lock_and_migration_are_source_reviewed_without_execution(self):
        statement = str(select(Business).where(Business.business_id == 10).with_for_update().compile(dialect=mysql.dialect()))
        self.assertIn("FOR UPDATE", statement)
        source = (Path(__file__).resolve().parents[1] / "app/routers/admin_businesses.py").read_text()
        self.assertLess(source.index(".with_for_update().execution_options"), source.index("grant_first_approval_trial(db"))
        self.assertLess(source.index("grant_first_approval_trial(db"), source.index("db.commit()"))
        migration = (Path(__file__).resolve().parents[1] / "alembic/versions/8c0f5e3d9b26_business_subscriptions.py").read_text()
        self.assertIn('down_revision = "7b9e4d2c8a15"', migration)
        self.assertIn("b.approval_status = 'approved' OR EXISTS", migration)
        self.assertNotIn("op.drop", migration)

    def test_prepared_migration_runner_is_opt_in_and_revision_graph_is_single_chain(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        root = Path(__file__).resolve().parents[1]
        cfg = Config()
        cfg.set_main_option("script_location", str(root / "alembic"))
        graph = ScriptDirectory.from_config(cfg)
        self.assertEqual(graph.get_heads(), ["d15a8c902e64"])
        self.assertEqual(graph.get_revision("d15a8c902e64").down_revision, "c04d9e7a6201")
        self.assertEqual(graph.get_revision("c04d9e7a6201").down_revision, "bf38d2a90176")
        self.assertEqual(graph.get_revision("bf38d2a90176").down_revision, "ae2b7c5f1d48")
        self.assertEqual(graph.get_revision("ae2b7c5f1d48").down_revision, "9d1a6f4e0c37")
        self.assertEqual(graph.get_revision("9d1a6f4e0c37").down_revision, "8c0f5e3d9b26")
        self.assertEqual(graph.get_revision("8c0f5e3d9b26").down_revision, "7b9e4d2c8a15")
        self.assertEqual(len(list(graph.walk_revisions())), 22)
        spec = importlib.util.spec_from_file_location("offline_subscription_migration_runner", root / "scripts/migrate_viva_subscriptions.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with patch.object(sys, "argv", ["runner"]), self.assertRaises(RuntimeError):
            runner.main()
        self.assertEqual(runner.TARGET, "lankapex_viva_db")
        self.assertEqual(runner.NEW_HEAD, "8c0f5e3d9b26")

class ConcurrentGrantConstraintTests(TestCase):
    def test_two_concurrent_writers_cannot_insert_two_business_trial_records(self):
        # SQLite can test the unique constraint under concurrent writers. MySQL
        # FOR UPDATE serialization itself requires the separately authorized live test.
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'synthetic.db'}", connect_args={"timeout": 10})
            create_tables(engine)
            with Session(engine) as db:
                seed(db)
            barrier = threading.Barrier(2)
            results = []
            def writer():
                with Session(engine) as db:
                    barrier.wait()
                    db.add(SubscriptionTrialGrant(business_id=10, grant_status="GRANTED", created_at=datetime(2028, 1, 1), trial_started_at=datetime(2028, 1, 1), trial_ends_at=datetime(2028, 2, 1)))
                    try:
                        db.commit(); results.append("committed")
                    except IntegrityError:
                        db.rollback(); results.append("duplicate")
            threads = [threading.Thread(target=writer) for _ in range(2)]
            for thread in threads: thread.start()
            for thread in threads: thread.join(15)
            self.assertEqual(sorted(results), ["committed", "duplicate"])
            engine.dispose()

if __name__ == "__main__":
    main(verbosity=2)

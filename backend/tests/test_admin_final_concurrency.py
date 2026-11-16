"""Day 16 release checks: two distinct Administrators, real MySQL row locks."""
from uuid import uuid4
import pytest
from fastapi import Response
from sqlalchemy import delete, select, func, text, update
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import engine
from app.models import User, DriverProfile, AdminAudit, Business, BusinessApprovalAudit, Notification
from app.schemas.admin import DriverDecision, AccountDecision
from app.schemas.admin_business import BusinessDecisionRequest
from app.services import admin_service
from app.routers.admin_businesses import decide_business
from test_admin_concurrency import context, overlap, race_data


@pytest.fixture
def two_admins(context):
    ctx = context.copy()
    assert settings.MYSQL_DATABASE == engine.url.database == 'lankapex_test_db'
    extra = None
    try:
        with Session(engine) as db:
            assert db.scalar(text('SELECT DATABASE()')) == 'lankapex_test_db'
            actor = User(full_name='Admin final race fixture', email=f'admin-final-{uuid4().hex}@example.com',
                password_hash='test-only-not-for-login', platform_role='admin', account_status='active', preferred_language='en')
            db.add(actor); db.flush(); extra = actor.user_id; db.commit()
        ctx['admins'] = [ctx['admin'], extra]
        yield ctx
    finally:
        if extra is not None:
            with engine.begin() as db:
                assert db.scalar(text('SELECT DATABASE()')) == 'lankapex_test_db'
                # Exact disposable fixture IDs only. Restore references before deleting the extra actor.
                db.execute(update(DriverProfile).where(DriverProfile.user_id.in_(ctx['drivers']), DriverProfile.reviewed_by == extra).values(reviewed_by=ctx['admin']))
                db.execute(delete(AdminAudit).where(AdminAudit.admin_user_id == extra))
                db.execute(delete(BusinessApprovalAudit).where(BusinessApprovalAudit.admin_user_id == extra, BusinessApprovalAudit.business_id == ctx['business']))
                db.execute(delete(User).where(User.user_id == extra))


@pytest.mark.parametrize('decisions', [('approve', 'approve'), ('approve', 'reject')])
def test_two_distinct_administrators_review_one_driver_atomically(two_admins, decisions):
    ctx = two_admins; ident = ctx['drivers'][0]
    with Session(engine) as db:
        profile = db.get(DriverProfile, ident)
        profile.approval_status = 'pending'; profile.reviewed_by = None; profile.reviewed_at = None; db.commit()
    def review(db, actor, decision):
        result = admin_service.decide_driver(db, db.get(User, actor), ident, DriverDecision(decision=decision, review_note='Application reviewed'))
        return result['profile']['approval_status'], actor
    results = overlap(ctx, DriverProfile, ident, [lambda db, actor=actor, value=value: review(db, actor, value) for actor, value in zip(ctx['admins'], decisions)])
    assert sorted(code for code, _ in results) == [200, 409]
    state, actor = next(result for code, result in results if code == 200)
    with Session(engine) as db:
        profile = db.get(DriverProfile, ident)
        audits = list(db.scalars(select(AdminAudit).where(AdminAudit.target_type == 'driver', AdminAudit.target_id == ident)))
        alerts = list(db.scalars(select(Notification).where(Notification.recipient_user_id == ident, Notification.related_entity_type == 'admin_audit')))
        assert len(audits) == len(alerts) == 1
        audit = audits[0]
        assert profile.approval_status == audit.new_state == state
        assert profile.reviewed_by == audit.admin_user_id == actor
        assert audit.previous_state == 'pending' and audit.action == 'driver_' + state and audit.created_at is not None
        assert alerts[0].notification_type == audit.action and alerts[0].related_entity_id == audit.audit_id


@pytest.mark.parametrize('decisions', [('approve', 'approve'), ('approve', 'reject')])
def test_two_distinct_administrators_review_one_business_atomically(two_admins, decisions):
    ctx = two_admins; ident = ctx['business']
    with Session(engine) as db: db.get(Business, ident).approval_status = 'pending'; db.commit()
    def review(db, actor, decision):
        result = decide_business(ident, BusinessDecisionRequest(decision=decision), Response(), db.get(User, actor), db)
        return result['approval_status'], actor
    results = overlap(ctx, Business, ident, [lambda db, actor=actor, value=value: review(db, actor, value) for actor, value in zip(ctx['admins'], decisions)])
    assert sorted(code for code, _ in results) == [200, 409]
    state, actor = next(result for code, result in results if code == 200)
    with Session(engine) as db:
        audits = list(db.scalars(select(BusinessApprovalAudit).where(BusinessApprovalAudit.business_id == ident)))
        alerts = list(db.scalars(select(Notification).where(Notification.business_id == ident, Notification.related_entity_type == 'business_approval_audit')))
        assert len(audits) == len(alerts) == 1
        assert audits[0].admin_user_id == actor and audits[0].previous_status == 'pending'
        assert db.get(Business, ident).approval_status == audits[0].new_status == state
        assert alerts[0].notification_type == 'business_' + state and alerts[0].related_entity_id == audits[0].audit_id


@pytest.mark.parametrize('initial,requested', [
    ('active', ('suspended', 'suspended')),
    ('suspended', ('active', 'active')),
    ('active', ('suspended', 'active')),
])
def test_concurrent_account_changes_have_a_serial_audit_chain(two_admins, initial, requested):
    ctx = two_admins; ident = ctx['drivers'][0]
    with Session(engine) as db: db.get(User, ident).account_status = initial; db.commit()
    results = overlap(ctx, User, ident, [lambda db, actor=actor, value=value: admin_service.account_status(
        db, db.get(User, actor), ident, AccountDecision(account_status=value, reason='Operational review'))['account_status']
        for actor, value in zip(ctx['admins'], requested)])
    assert [code for code, _ in results] == [200, 200]
    with Session(engine) as db:
        audits = list(db.scalars(select(AdminAudit).where(AdminAudit.target_type == 'user', AdminAudit.target_id == ident).order_by(AdminAudit.audit_id)))
        if requested[0] == requested[1]: assert len(audits) == 1
        else: assert len(audits) in {1, 2}
        previous = initial
        for row in audits:
            assert row.admin_user_id in ctx['admins'] and row.previous_state == previous
            assert row.new_state != row.previous_state and row.created_at is not None
            assert row.action == ('account_suspended' if row.new_state == 'suspended' else 'account_reactivated')
            previous = row.new_state
        assert db.get(User, ident).account_status == previous
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.recipient_user_id == ident)) == 0

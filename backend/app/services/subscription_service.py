# Purpose: Evaluate business plans, trial dates, feature entitlements, and capacity limits before restricted operations.
"""Internal no-card trial and request-time entitlements. Caller owns transactions.

No Stripe API calls, automatic charges, expiry writes, or ledger mutations.
Approved package policy is evaluated without expiry writes or payment changes.
"""
import calendar
import math
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Business, BusinessApprovalAudit, BusinessMember, User
from app.models.subscription import BusinessSubscription, SubscriptionTrialGrant

# Sri Lanka has a fixed UTC+05:30 civil offset (no DST). No OS tzdata dependency.
COLOMBO = timezone(timedelta(hours=5, minutes=30), name="Asia/Colombo")
FEATURES = ("financial_history", "repayments", "credit_sales", "customers", "catalogue", "orders", "deliveries", "reports", "reminders")
FEATURES = (*FEATURES, 'ai_summaries', 'statement_exports', 'advanced_reports')
ENTITLEMENTS = {plan: {feature: (feature != 'advanced_reports' and
    (plan != 'FREE' or feature in {'financial_history','repayments','credit_sales','customers','reminders'}))
    for feature in FEATURES} for plan in ('FREE','PRO','BUSINESS')}
POLICY='packages_v1_existing_obligations_preserved'


# Resolve the feature and capacity limits configured for a supported plan.
def plan_limits(plan):
    return dict(customer_limit=30 if plan=='FREE' else None,ai_limit_multiplier=0 if plan=='FREE' else 2 if plan=='BUSINESS' else 1)
PLANS = (
    {"plan": "FREE", "currency": "LKR", "monthly_minor": 0, "yearly_minor": 0},
    {"plan": "PRO", "currency": "LKR", "monthly_minor": 49900, "yearly_minor": 499000},
    {"plan": "BUSINESS", "currency": "LKR", "monthly_minor": 129900, "yearly_minor": 1299000},
)


# Use timezone-aware UTC timestamps so application comparisons share one time reference.
def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Normalize stored timestamps to UTC before comparing subscription boundaries.
def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


# Calculate the calendar-based trial boundary rather than assuming every month has the same number of days.
def calendar_month_end(start):
    local = utc(start).astimezone(COLOMBO)
    year, month = (local.year + 1, 1) if local.month == 12 else (local.year, local.month + 1)
    return local.replace(year=year, month=month, day=min(local.day, calendar.monthrange(year, month)[1])).astimezone(timezone.utc).replace(tzinfo=None)


def grant_first_approval_trial(db, business, approved_at):
    """Called only with the Business FOR UPDATE lock, BEFORE the current audit.

The business PK in the grant table is the final uniqueness guard. Exclusion
markers protect businesses approved before deployment, including old records
without an audit. An earlier approval audit is a second defense. Never upsert
or reset an existing grant. Grant, approval, audit and notification commit once.
"""
    if db.get(SubscriptionTrialGrant, business.business_id) is not None:
        return
    previous = db.scalar(select(BusinessApprovalAudit.audit_id).where(
        BusinessApprovalAudit.business_id == business.business_id,
        BusinessApprovalAudit.decision == "approve").limit(1))
    if previous is not None:
        db.add(SubscriptionTrialGrant(business_id=business.business_id, grant_status="EXCLUDED", created_at=approved_at))
        return
    end = calendar_month_end(approved_at)
    db.add(SubscriptionTrialGrant(business_id=business.business_id, grant_status="GRANTED",
        trial_started_at=approved_at, trial_ends_at=end, created_at=approved_at))
    # Preserve any independently paid subscription; the one-time trial still
    # receives its immutable original dates and cannot later be re-granted.
    if db.get(BusinessSubscription, business.business_id) is None:
        db.add(BusinessSubscription(business_id=business.business_id, plan="PRO", status="TRIALING",
            started_at=approved_at, created_at=approved_at, updated_at=approved_at, provider_mode="sandbox"))


# Query authorize business data for the subscription workflow.
def authorize_business(db, user, business_id, manage=False):
    if user.account_status != "active" or user.platform_role not in {"shop_owner", "admin"}:
        raise HTTPException(403, "Subscription access is not permitted")
    if user.platform_role == "admin":
        if manage:
            raise HTTPException(403, "Only the business owner can manage billing")
        business = db.get(Business, business_id)
    else:
        business = db.scalar(select(Business).join(BusinessMember, BusinessMember.business_id == Business.business_id).join(
            User, User.user_id == BusinessMember.user_id).where(
            Business.business_id == business_id, User.user_id == user.user_id,
            User.account_status == "active", User.platform_role == "shop_owner",
            BusinessMember.business_role == "owner", BusinessMember.membership_status == "active"))
    if business is None:
        raise HTTPException(404, "Business not found")
    if manage and business.approval_status != "approved":
        raise HTTPException(403, "Business approval is required")
    return business


# Derive the effective subscription state and entitlements from stored plan and period information.
def evaluate(subscription, grant, now=None):
    now = utc(now or utc_now())
    trial_end = grant.trial_ends_at if grant and grant.grant_status == "GRANTED" else None
    trial_start = grant.trial_started_at if trial_end else None
    trial_active = bool(trial_end and utc(trial_start) <= now < utc(trial_end))
    paid = bool(subscription and subscription.plan in {"PRO", "BUSINESS"}
        and subscription.status == "ACTIVE" and subscription.provider_mode == "sandbox"
        and subscription.stripe_customer_id and subscription.stripe_subscription_id
        and subscription.started_at and utc(subscription.started_at) <= now
        and subscription.paid_through and now < utc(subscription.paid_through))
    effective = subscription.plan if paid else "PRO" if trial_active else "FREE"
    remaining = max(0, math.ceil((utc(trial_end) - now).total_seconds())) if trial_end else 0
    return dict(effective_plan=effective, status="ACTIVE" if paid else "TRIALING" if trial_active else "EXPIRED" if trial_end else "FREE",
        billing_interval=subscription.billing_interval if paid else None,
        trial_started_at=utc(trial_start) if trial_start else None,
        trial_ends_at=utc(trial_end) if trial_end else None,
        trial_remaining_seconds=remaining, trial_remaining_days=math.ceil(remaining / 86400),
        trial_active=trial_active and not paid, upgrade_required=bool(trial_end and not trial_active and not paid),
        paid_through=utc(subscription.paid_through) if paid else None,
        entitlements=dict(ENTITLEMENTS[effective]), entitlement_policy=POLICY, **plan_limits(effective),
        evaluated_at=now)


# Resolve subscription state using a row lock so the caller can coordinate concurrent changes.
def subscription_state(db, business_id, current=False):
    if current:
        # Resolve row using a row lock so the caller can coordinate concurrent changes.
        def row(model):
            return db.scalar(select(model).where(model.business_id==business_id).with_for_update(read=True).execution_options(populate_existing=True))
        return evaluate(row(BusinessSubscription),row(SubscriptionTrialGrant))
    return evaluate(db.get(BusinessSubscription, business_id), db.get(SubscriptionTrialGrant, business_id))


def require_entitlement(db, user, business_id, feature):
    """Server-side check; ownership always precedes feature evaluation.

Unknown features fail closed. Existing obligation views and completion paths
are preserved separately from gates on new restricted activity.
"""
    authorize_business(db, user, business_id, manage=True)
    require_business_feature(db,business_id,feature)


def require_business_feature(db,business_id,feature):
    """Call only after the role-specific business authorization boundary."""
    state=subscription_state(db,business_id,current=True)
    if not state['entitlements'].get(feature,False):
        raise HTTPException(403,'Upgrade to Pro to use this feature',headers={'Cache-Control':'no-store'})
    return state


def enforce_customer_capacity(db,business_id):
    """Existing Business PK serializes every profile-creation path on MySQL.

    Count persisted profiles (including those without an account); never remove
    customers after downgrade. Current locking reads avoid stale RR snapshots.
    """
    from app.models import CustomerProfile
    business=db.scalar(select(Business).where(Business.business_id==business_id).with_for_update().execution_options(populate_existing=True))
    if business is None:raise HTTPException(404,'Business not found')
    limit=subscription_state(db,business_id,current=True)['customer_limit']
    if limit is not None:
        rows=list(db.scalars(select(CustomerProfile.customer_id).where(CustomerProfile.business_id==business_id)
            .order_by(CustomerProfile.customer_id).limit(limit).with_for_update()))
        if len(rows)>=limit:raise HTTPException(403,'Free plan supports 30 credit customers. Upgrade to Pro.',headers={'Cache-Control':'no-store'})


# Check new credit account capacity and stop callers when the required conditions are not met.
def enforce_new_credit_account_capacity(db,business_id):
    from app.models import CreditAccount
    db.scalar(select(Business).where(Business.business_id==business_id).with_for_update())
    limit=subscription_state(db,business_id,current=True)['customer_limit']
    if limit is not None:
        ids=list(db.scalars(select(CreditAccount.customer_id).where(CreditAccount.creditor_business_id==business_id,
            CreditAccount.customer_id.is_not(None)).limit(limit).with_for_update()))
        if len(ids)>=limit:raise HTTPException(403,'Free plan supports 30 credit customers. Upgrade to Pro.')

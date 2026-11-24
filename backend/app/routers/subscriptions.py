# Purpose: Expose subscriptions HTTP endpoints and connect request validation and dependencies to the application services.
"""Tenant-scoped billing. Sandbox adapter stays disabled until configured."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.subscription import CheckoutRequest, PlansResponse, SubscriptionResponse
from app.services.subscription_service import ENTITLEMENTS, PLANS, POLICY, plan_limits, authorize_business, subscription_state
from app.services import subscription_billing as billing, stripe_sandbox

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])
Actor = Annotated[User, Depends(require_roles("shop_owner", "admin"))]
Database = Annotated[Session, Depends(get_db)]
BusinessId = Annotated[int, Query(gt=0, le=9223372036854775807)]


# Handle GET /plans through the declared request and dependency contract.
@router.get("/plans", response_model=PlansResponse)
def plans(response: Response, user: Actor):
    response.headers["Cache-Control"] = "no-store"
    return {"plans": [{**plan, "entitlements": ENTITLEMENTS[plan['plan']], **plan_limits(plan['plan'])} for plan in PLANS],
        'entitlement_policy': POLICY,
        "payment_configured": stripe_sandbox.enabled()}


# Handle GET /current through the declared request and dependency contract.
@router.get("/current", response_model=SubscriptionResponse)
def current(response: Response, user: Actor, db: Database, business_id: BusinessId):
    response.headers["Cache-Control"] = "no-store"
    authorize_business(db, user, business_id)
    state = subscription_state(db, business_id)
    sub = db.get(billing.BusinessSubscription, business_id)
    return {"business_id": business_id, **state, "payment_configured": stripe_sandbox.enabled(),
        "payment_failed": bool(sub and sub.status == 'PAST_DUE'),
        "checkout_available": bool(stripe_sandbox.enabled() and not state['trial_active']
            and (not sub or not sub.stripe_subscription_id or sub.status == 'CANCELLED')),
        "portal_available": bool(stripe_sandbox.enabled() and sub and sub.stripe_subscription_id)}


# Handle GET /entitlements through the declared request and dependency contract.
@router.get("/entitlements", response_model=SubscriptionResponse)
def entitlements(response: Response, user: Actor, db: Database, business_id: BusinessId):
    return current(response, user, db, business_id)


# Handle GET /trial through the declared request and dependency contract.
@router.get("/trial", response_model=SubscriptionResponse)
def trial(response: Response, user: Actor, db: Database, business_id: BusinessId):
    return current(response, user, db, business_id)


# Handle POST /checkout through the declared request and dependency contract.
@router.post("/checkout")
def checkout(response: Response, payload: CheckoutRequest, user: Actor, db: Database, business_id: BusinessId):
    response.headers["Cache-Control"] = "no-store"
    return billing.checkout(db, user, business_id, payload)


# Handle POST /portal through the declared request and dependency contract.
@router.post("/portal")
def portal(response: Response, user: Actor, db: Database, business_id: BusinessId):
    response.headers["Cache-Control"] = "no-store"
    return billing.portal(db, user, business_id)


# Handle POST /checkout/reconcile through the declared request and dependency contract.
@router.post("/checkout/reconcile")
def reconcile(response: Response, user: Actor, db: Database, business_id: BusinessId):
    response.headers['Cache-Control'] = 'no-store'
    return billing.recover(db, user, business_id)


# Handle GET /history through the declared request and dependency contract.
@router.get("/history")
def history(response: Response, user: Actor, db: Database, business_id: BusinessId):
    response.headers["Cache-Control"] = "no-store"
    authorize_business(db, user, business_id)
    # Hosted invoices are available in the Portal; never fabricate local invoices.
    return {"business_id": business_id, "invoices": [], "available": False,
        "message": "Hosted invoices are available in the billing portal" if stripe_sandbox.enabled() else "Payment integration not configured"}


# Handle POST /webhook through the declared request and dependency contract.
@router.post("/webhook")
async def webhook(request: Request, db: Database):
    stripe_sandbox.require_enabled()
    body = await request.body()
    if len(body) > 262144:
        raise HTTPException(413, 'Webhook too large')
    event = stripe_sandbox.signed_event(body, request.headers.get('Stripe-Signature'))
    return await run_in_threadpool(billing.webhook, db, event)

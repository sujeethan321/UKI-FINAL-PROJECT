# Purpose: Implement shop owner reminder operations behind the HTTP layer so related business rules are shared by their callers.
"""Business-scoped, account-serialized internal reminder recording."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services.notification_service import notify_event
from app.services.communication_service import latest_consent, normalize_whatsapp_phone

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.config import settings
from app.models import CustomerProfile, PaymentReminder
from app.schemas.payment_reminder import PaymentReminderResponse
from app.services.ledger_service import ZERO, account_balances, load_ledger_entries, lock_customer_credit_account


# Shape reminder fields for the response contract.
def reminder_response(row, replayed=False, db=None):
    fields = {key: getattr(row, key) for key in PaymentReminderResponse.model_fields
              if hasattr(PaymentReminder, key)}
    fields["outstanding_amount"] = f"{row.outstanding_amount:.2f}"
    for key in ("created_at", "updated_at"):
        fields[key] = fields[key].replace(tzinfo=timezone.utc)
    if db is not None:
        preference = latest_consent(db, row.business_id, row.customer_id)
        customer = db.get(CustomerProfile, row.customer_id)
        status = preference.consent_status if preference else "unknown"
        if status == "granted" and (customer is None or preference.phone != normalize_whatsapp_phone(customer.phone)):
            status = "unknown"
        fields["consent_status"] = status
    return PaymentReminderResponse(**fields, replayed=replayed)


# Record reminder for the shop owner reminder workflow.
def record_reminder(db, business, user_id, payload):
    account = lock_customer_credit_account(db, business.business_id, payload.customer_id)
    # Current locking reads avoid authorization's older MySQL repeatable-read snapshot.
    existing = db.scalar(select(PaymentReminder).where(
        PaymentReminder.business_id == business.business_id,
        PaymentReminder.idempotency_key == payload.idempotency_key,
    ).with_for_update().execution_options(populate_existing=True))
    if existing:
        if (existing.customer_id, existing.created_by, existing.channel, existing.language, existing.note) != (
                payload.customer_id, user_id, payload.channel, payload.language, payload.note):
            raise HTTPException(409, "Idempotency key is already used for a different reminder")
        return reminder_response(existing, True, db)
    entries = load_ledger_entries(db, [account.credit_account_id], lock=True)
    balance = account_balances(entries).get(account.credit_account_id, ZERO)
    if balance <= ZERO:
        raise HTTPException(409, "Customer has no outstanding balance")
    if balance >= Decimal("10000000000000000000000"):
        raise HTTPException(409, "Outstanding balance exceeds reminder snapshot capacity")
    if account.account_status != "active":
        raise HTTPException(409, "Credit account must be active to record a reminder")
    customer = db.scalar(select(CustomerProfile).where(
        CustomerProfile.customer_id == payload.customer_id,
        CustomerProfile.business_id == business.business_id,
    ).with_for_update().execution_options(populate_existing=True))
    if payload.channel != "internal" and not customer.phone:
        raise HTTPException(409, "Customer has no contact number; use an internal reminder")
    # Match MySQL DATETIME precision so the initial response equals a replay.
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    recent = db.scalar(select(PaymentReminder.reminder_id).where(
        PaymentReminder.business_id == business.business_id,
        PaymentReminder.customer_id == payload.customer_id,
        PaymentReminder.created_at > now - timedelta(seconds=settings.REMINDER_COOLDOWN_SECONDS),
    ).with_for_update().limit(1)) if settings.REMINDER_COOLDOWN_SECONDS > 0 else None
    if recent is not None:
        raise HTTPException(409, "Reminder cooldown is active for this customer")
    amount = f"LKR {balance:,.2f}"
    stamp = now.isoformat(timespec="seconds") + "Z"
    if payload.language == "ta":
        message = (f"{customer.customer_name}, {business.business_name} கடையில் {stamp} நிலவரப்படி "
                   f"உங்கள் நிலுவைத் தொகை {amount}. தயவுசெய்து பணம் செலுத்த ஏற்பாடு செய்யுங்கள். "
                   "அண்மையில் பணம் செலுத்தியிருந்தால், உறுதிப்படுத்த கடையைத் தொடர்புகொள்ளவும்.")
    else:
        message = (f"Hello {customer.customer_name}, your outstanding balance with {business.business_name} "
                   f"is {amount} as of {stamp}. Please arrange payment. "
                   "If you have recently paid, please contact the shop to confirm.")
    row = PaymentReminder(business_id=business.business_id, customer_id=payload.customer_id,
        credit_account_id=account.credit_account_id, created_by=user_id, outstanding_amount=balance,
        currency="LKR", channel=payload.channel, language=payload.language, template_version="outstanding-v1",
        message=message, note=payload.note, status="recorded", idempotency_key=payload.idempotency_key,
        created_at=now, updated_at=now)
    db.add(row)
    db.flush()
    notify_event(db, "payment_reminder_recorded", row.reminder_id)
    return reminder_response(row, db=db)


# Query reminder history data for the shop owner reminder workflow.
def reminder_history(db, business_id, customer_id, status, page, page_size, ordering):
    if customer_id is not None and db.scalar(select(CustomerProfile.customer_id).where(
            CustomerProfile.business_id == business_id, CustomerProfile.customer_id == customer_id)) is None:
        raise HTTPException(404, "Customer not found in this business")
    filters = [PaymentReminder.business_id == business_id]
    if customer_id is not None:
        filters.append(PaymentReminder.customer_id == customer_id)
    if status is not None:
        filters.append(PaymentReminder.status == status)
    total = db.scalar(select(func.count()).select_from(PaymentReminder).where(*filters))
    columns = (PaymentReminder.created_at, PaymentReminder.reminder_id)
    order = [column.desc() if ordering == "newest" else column.asc() for column in columns]
    rows = db.scalars(select(PaymentReminder).where(*filters).order_by(*order)
                      .offset((page - 1) * page_size).limit(page_size))
    return dict(business_id=business_id, page=page, page_size=page_size, total=total,
                reminders=[reminder_response(row, db=db) for row in rows])

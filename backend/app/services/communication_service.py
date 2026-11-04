"""Manual WhatsApp handoff only: no provider calls or financial writes."""
import re
from datetime import timezone
from urllib.parse import quote
from fastapi import HTTPException
from sqlalchemy import select
from app.models import CommunicationAttempt, CommunicationConsent, CustomerProfile, PaymentReminder
from app.schemas.communication import AttemptSummary, CommunicationPreview, ConsentResponse, HandoffResponse
from app.services.ledger_service import ZERO, account_balances, load_ledger_entries, lock_customer_credit_account
from app.services.notification_service import utc_now


def normalize_whatsapp_phone(value):
    if not isinstance(value, str) or not value.strip():
        return None
    value = re.sub(r"[ ()-]", "", value.strip())
    if re.fullmatch(r"07[0-9]{8}", value):
        return "94" + value[1:]
    if re.fullmatch(r"\+?947[0-9]{8}", value):
        return value.lstrip("+")
    return None


def customer_in_business(db, business_id, customer_id, lock=False):
    statement = select(CustomerProfile).where(CustomerProfile.business_id == business_id, CustomerProfile.customer_id == customer_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    customer = db.scalar(statement)
    if customer is None:
        raise HTTPException(404, "Customer not found in this business")
    return customer


def latest_consent(db, business_id, customer_id, lock=False):
    statement = select(CommunicationConsent).where(CommunicationConsent.business_id == business_id,
        CommunicationConsent.customer_id == customer_id, CommunicationConsent.channel == "whatsapp").order_by(CommunicationConsent.consent_id.desc()).limit(1)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return db.scalar(statement)


def consent_response(row, replayed=False):
    return ConsentResponse(consent_id=row.consent_id, business_id=row.business_id, customer_id=row.customer_id,
        channel=row.channel, consent_status=row.consent_status, recorded_by=row.recorded_by,
        created_at=row.created_at.replace(tzinfo=timezone.utc), replayed=replayed)


def record_consent(db, business_id, customer_id, user_id, payload):
    customer = customer_in_business(db, business_id, customer_id, lock=True)
    existing = db.scalar(select(CommunicationConsent).where(CommunicationConsent.business_id == business_id,
        CommunicationConsent.idempotency_key == payload.idempotency_key).with_for_update())
    if existing:
        if (existing.customer_id, existing.recorded_by, existing.consent_status, existing.evidence) != (customer_id, user_id, payload.consent_status, payload.evidence):
            raise HTTPException(409, "Preference key conflicts with another operation")
        # Replaying an old grant never makes it the newest preference.
        return consent_response(existing, True)
    phone = normalize_whatsapp_phone(customer.phone)
    if payload.consent_status == "granted" and phone is None:
        raise HTTPException(409, "A valid Sri Lankan customer mobile number is required")
    row = CommunicationConsent(business_id=business_id, customer_id=customer_id, recorded_by=user_id,
        channel="whatsapp", consent_status=payload.consent_status, phone=phone, evidence=payload.evidence,
        idempotency_key=payload.idempotency_key, created_at=utc_now())
    db.add(row)
    db.flush()
    return consent_response(row)


def scoped_reminder(db, business_id, customer_id, reminder_id):
    row = db.scalar(select(PaymentReminder).where(PaymentReminder.reminder_id == reminder_id,
        PaymentReminder.business_id == business_id, PaymentReminder.customer_id == customer_id))
    if row is None:
        raise HTTPException(404, "Reminder not found for this business and customer")
    return row


def eligibility(db, business_id, customer_id, reminder_id, lock=False):
    reminder = scoped_reminder(db, business_id, customer_id, reminder_id)
    # Same account-before-customer lock order as the existing reminder writer.
    account = lock_customer_credit_account(db, business_id, customer_id)
    customer = customer_in_business(db, business_id, customer_id, lock=lock)
    phone = normalize_whatsapp_phone(customer.phone)
    consent = latest_consent(db, business_id, customer_id, lock=lock)
    status = consent.consent_status if consent else "unknown"
    if status == "granted" and (phone is None or consent.phone != phone):
        status = "unknown"
    balance = account_balances(load_ledger_entries(db, [account.credit_account_id], lock=lock)).get(account.credit_account_id, ZERO)
    reason = None
    if status == "opted_out":
        reason = "Customer opted out of WhatsApp communication."
    elif phone is None:
        reason = "A valid Sri Lankan customer mobile number is required."
    elif status != "granted":
        reason = "WhatsApp permission is unknown for this number. Record the customer's actual stated preference first."
    elif account.credit_account_id != reminder.credit_account_id or account.account_status != "active" or balance <= ZERO or balance != reminder.outstanding_amount:
        reason = "The credit account or outstanding balance changed. Review the account and record a new reminder when allowed."
    elif reminder.status != "recorded" or reminder.template_version != "outstanding-v1" or not reminder.message.strip() or re.search(r"https?://|www\.|bearer\s", reminder.message, re.I):
        reason = "Saved reminder content is unavailable or unsafe for handoff."
    return reminder, consent, phone, status, reason


def communication_preview(db, business_id, customer_id, reminder_id):
    reminder, consent, phone, status, reason = eligibility(db, business_id, customer_id, reminder_id)
    rows = db.scalars(select(CommunicationAttempt).where(CommunicationAttempt.business_id == business_id,
        CommunicationAttempt.reminder_id == reminder_id).order_by(CommunicationAttempt.created_at.desc(), CommunicationAttempt.attempt_id.desc()).limit(20))
    return CommunicationPreview(business_id=business_id, customer_id=customer_id, reminder_id=reminder_id,
        message=reminder.message, language=reminder.language, outstanding_amount=f"{reminder.outstanding_amount:.2f}",
        consent_status=status, consent_source="owner_recorded_customer_statement" if consent else None,
        normalized_phone=phone, eligible=reason is None, blocked_reason=reason,
        attempts=[AttemptSummary(attempt_id=row.attempt_id, status=row.status, created_at=row.created_at.replace(tzinfo=timezone.utc)) for row in rows])


def handoff_response(row, reminder, replayed=False):
    # Official WhatsApp click-to-chat format. Encode the unmodified saved message.
    url = "https://wa.me/" + row.phone + "?text=" + quote(reminder.message, safe="")
    return HandoffResponse(attempt_id=row.attempt_id, business_id=row.business_id, customer_id=row.customer_id,
        reminder_id=row.reminder_id, channel="whatsapp", normalized_phone=row.phone, message=reminder.message,
        handoff_url=url, status=row.status, created_at=row.created_at.replace(tzinfo=timezone.utc), replayed=replayed)


def request_handoff(db, business_id, reminder_id, user_id, payload):
    reminder, consent, phone, status, reason = eligibility(db, business_id, payload.customer_id, reminder_id, lock=True)
    # Always recheck current permission and balance, even on an idempotent replay.
    if reason:
        raise HTTPException(409, reason)
    existing = db.scalar(select(CommunicationAttempt).where(CommunicationAttempt.business_id == business_id,
        CommunicationAttempt.idempotency_key == payload.idempotency_key).with_for_update())
    if existing:
        if (existing.reminder_id, existing.customer_id, existing.requested_by, existing.phone) != (reminder_id, payload.customer_id, user_id, phone):
            raise HTTPException(409, "Handoff key conflicts with another operation")
        return handoff_response(existing, reminder, True)
    row = CommunicationAttempt(business_id=business_id, customer_id=payload.customer_id, reminder_id=reminder_id,
        consent_id=consent.consent_id, requested_by=user_id, channel="whatsapp", phone=phone,
        status="handoff_requested", idempotency_key=payload.idempotency_key, created_at=utc_now())
    db.add(row)
    db.flush()
    return handoff_response(row, reminder)

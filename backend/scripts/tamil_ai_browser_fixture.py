"""Exact-ID fixture lifecycle for the isolated Tamil AI browser test.

Live modes are invoked only by manage_tamil_ai_browser_fixture.ps1.  Importing
this module is database-free, which lets guard behavior be tested offline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

TARGET = "lankapex_ai_snapshot_test_db"
REVISION = "7b9e4d2c8a15"
RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SALE = Decimal("100.20")
REPAYMENT = Decimal("30.10")
OUTSTANDING = Decimal("70.10")
FIXTURE_COUNTS = {
    "users": 2, "businesses": 1, "business_members": 1,
    "customer_profiles": 1, "credit_accounts": 1, "ledger_entries": 2,
}


def require_run_id(value: str) -> str:
    if not isinstance(value, str) or not RUN_ID_RE.fullmatch(value):
        raise ValueError("exact lowercase 128-bit run ID required")
    return value


def reservation_document(run_id: str) -> dict:
    run_id = require_run_id(run_id)
    return {
        "version": 1,
        "kind": "tamil_ai_browser_fixture_reservation",
        "state": "reserved",
        "run_id": run_id,
        "database": TARGET,
        "owner_email": f"tamil-ai-owner-{run_id}@lankapex-test.example.com",
        "customer_email": f"tamil-ai-customer-{run_id}@lankapex-test.example.com",
        "business_name": f"Tamil AI Test Shop {run_id[:8]}",
        "registration_number": f"TAI-{run_id.upper()}",
        "expected_amounts": {"sale": "100.20", "repayment": "30.10", "outstanding": "70.10"},
    }


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("private document is not an object")
    return value


def validate_reservation(value: dict, run_id: str | None = None) -> dict:
    expected = reservation_document(run_id or value.get("run_id"))
    if value != expected:
        raise ValueError("fixture reservation differs")
    return value


def exclusive_json(path: Path, value: dict) -> None:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(payload)


def fixture_fingerprint(ids: dict, run_id: str) -> str:
    allowed = {key: int(ids[key]) for key in (
        "owner_user_id", "customer_user_id", "business_id", "membership_id",
        "customer_id", "credit_account_id", "sale_entry_id", "repayment_entry_id",
    )}
    payload = {"run_id": require_run_id(run_id), "ids": allowed,
               "amounts": ["100.20", "30.10", "70.10"]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def inventory_fingerprint(counts: dict[str, int]) -> str:
    normalized = {str(name): int(count) for name, count in sorted(counts.items())}
    if any(count < 0 for count in normalized.values()):
        raise ValueError("invalid inventory count")
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def expected_counts(all_tables: set[str]) -> dict[str, int]:
    counts = {name: 0 for name in all_tables if name != "alembic_version"}
    if not set(FIXTURE_COUNTS).issubset(counts):
        raise ValueError("required fixture tables missing")
    counts.update(FIXTURE_COUNTS)
    return counts


def _identity_and_counts(connection, *, require_empty: bool):
    from sqlalchemy import text
    from scripts.check_ai_snapshot_test_runtime import (
        EXPECTED_TABLES, TARGET as CHECK_TARGET, USER, REVISION as CHECK_REVISION, validate_grants,
    )
    if (CHECK_TARGET, CHECK_REVISION) != (TARGET, REVISION):
        raise ValueError("shared preflight constants differ")
    actual = connection.execute(text("SELECT DATABASE(), CURRENT_USER()" )).one()
    if actual != (TARGET, USER + "@localhost"):
        raise ValueError("actual database or account differs")
    revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    tables = {row[0] for row in connection.execute(text(
        "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()"))}
    grants = [row[0] for row in connection.execute(text("SHOW GRANTS"))]
    if revision != REVISION or tables != EXPECTED_TABLES:
        raise ValueError("revision or table inventory differs")
    validate_grants(grants)
    counts = {table: int(connection.scalar(text(f"SELECT COUNT(*) FROM `{table}`")))
              for table in tables if table != "alembic_version"}
    wanted = ({name: 0 for name in counts} if require_empty else expected_counts(tables))
    if counts != wanted:
        raise ValueError("application inventory differs")
    return tables, counts


def _verify_fixture(session, reservation: dict, evidence: dict) -> dict:
    from sqlalchemy import select
    from app.models import User, Business, BusinessMember, CustomerProfile, CreditAccount, LedgerEntry
    run_id = reservation["run_id"]
    if (evidence.get("version") != 1 or evidence.get("kind") != "tamil_ai_browser_fixture_evidence"
            or evidence.get("state") != "committed" or evidence.get("database") != TARGET
            or evidence.get("run_id") != run_id or not isinstance(evidence.get("ids"), dict)):
        raise ValueError("fixture evidence differs")
    from scripts.check_ai_snapshot_test_runtime import EXPECTED_TABLES
    empty_counts = {name: 0 for name in EXPECTED_TABLES if name != "alembic_version"}
    if evidence.get("before_inventory_fingerprint") != inventory_fingerprint(empty_counts):
        raise ValueError("empty baseline fingerprint differs")
    ids = evidence["ids"]
    owner = session.get(User, ids.get("owner_user_id")); customer = session.get(User, ids.get("customer_user_id"))
    business = session.get(Business, ids.get("business_id")); member = session.get(BusinessMember, ids.get("membership_id"))
    profile = session.get(CustomerProfile, ids.get("customer_id")); account = session.get(CreditAccount, ids.get("credit_account_id"))
    sale = session.get(LedgerEntry, ids.get("sale_entry_id")); repayment = session.get(LedgerEntry, ids.get("repayment_entry_id"))
    if not owner or (owner.email, owner.platform_role, owner.account_status) != (reservation["owner_email"], "shop_owner", "active"):
        raise ValueError("owner identity differs")
    if not customer or (customer.email, customer.platform_role, customer.account_status) != (reservation["customer_email"], "customer", "active"):
        raise ValueError("customer identity differs")
    if not business or (business.business_name, business.registration_number, business.approval_status) != (reservation["business_name"], reservation["registration_number"], "approved"):
        raise ValueError("business identity differs")
    if not member or (member.business_id, member.user_id, member.business_role, member.membership_status) != (business.business_id, owner.user_id, "owner", "active"):
        raise ValueError("ownership differs")
    if not profile or (profile.business_id, profile.user_id) != (business.business_id, customer.user_id):
        raise ValueError("customer relationship differs")
    if not account or (account.creditor_business_id, account.customer_id, account.account_status) != (business.business_id, profile.customer_id, "active"):
        raise ValueError("credit account differs")
    for entry, kind, amount in ((sale, "credit_sale", SALE), (repayment, "repayment", REPAYMENT)):
        if not entry or (entry.credit_account_id, entry.created_by, entry.entry_type, Decimal(entry.amount), entry.reverses_entry_id) != (account.credit_account_id, owner.user_id, kind, amount, None):
            raise ValueError("ledger fixture differs")
    entries = list(session.scalars(select(LedgerEntry).where(LedgerEntry.credit_account_id == account.credit_account_id)))
    from app.services.ledger_service import account_balances
    if len(entries) != 2 or account_balances(entries).get(account.credit_account_id) != OUTSTANDING:
        raise ValueError("authoritative ledger total differs")
    if evidence.get("fingerprint") != fixture_fingerprint(ids, run_id):
        raise ValueError("fixture fingerprint differs")
    return ids


def reserve(args):
    exclusive_json(Path(args.reservation), reservation_document(args.run_id))
    print("PASS: immutable Tamil AI browser fixture reservation created privately")


def create(args):
    reservation = validate_reservation(load_json(Path(args.reservation)), args.run_id)
    password = os.environ.get("TAMIL_AI_FIXTURE_OWNER_PASSWORD", "")
    if len(password) < 20:
        raise ValueError("private owner credential missing")
    from app.core.database import SessionLocal
    from app.core.security import hash_password
    from app.models import User, Business, BusinessMember, CustomerProfile, CreditAccount, LedgerEntry
    session = SessionLocal()
    try:
        tables, before_counts = _identity_and_counts(session.connection(), require_empty=True)
        owner = User(full_name="Tamil AI Test Owner", email=reservation["owner_email"], password_hash=hash_password(password), platform_role="shop_owner", account_status="active")
        customer = User(full_name="Tamil AI Test Customer", email=reservation["customer_email"], password_hash=hash_password(secrets.token_urlsafe(36)), platform_role="customer", account_status="active")
        session.add_all([owner, customer]); session.flush()
        business = Business(business_name=reservation["business_name"], business_type="Grocery", registration_number=reservation["registration_number"], approval_status="approved")
        session.add(business); session.flush()
        member = BusinessMember(business_id=business.business_id, user_id=owner.user_id, business_role="owner", membership_status="active")
        profile = CustomerProfile(business_id=business.business_id, user_id=customer.user_id, customer_name="Tamil AI Test Customer")
        session.add_all([member, profile]); session.flush()
        account = CreditAccount(creditor_business_id=business.business_id, customer_id=profile.customer_id, credit_limit=Decimal("500.00"), payment_term_days=30, account_status="active")
        session.add(account); session.flush()
        sale = LedgerEntry(credit_account_id=account.credit_account_id, created_by=owner.user_id, entry_type="credit_sale", amount=SALE, idempotency_key=f"tamil-ai-{args.run_id}-sale", receipt_number=f"TAI-CS-{args.run_id}")
        repayment = LedgerEntry(credit_account_id=account.credit_account_id, created_by=owner.user_id, entry_type="repayment", amount=REPAYMENT, payment_method="cash", idempotency_key=f"tamil-ai-{args.run_id}-repayment", receipt_number=f"TAI-RP-{args.run_id}")
        session.add_all([sale, repayment]); session.flush()
        ids = {"owner_user_id": owner.user_id, "customer_user_id": customer.user_id, "business_id": business.business_id,
               "membership_id": member.membership_id, "customer_id": profile.customer_id, "credit_account_id": account.credit_account_id,
               "sale_entry_id": sale.entry_id, "repayment_entry_id": repayment.entry_id}
        pending = {"version": 1, "kind": "tamil_ai_browser_fixture_evidence", "state": "pending_commit", "database": TARGET,
                   "run_id": args.run_id, "ids": ids, "fingerprint": fixture_fingerprint(ids, args.run_id),
                   "before_inventory_fingerprint": inventory_fingerprint(before_counts)}
        exclusive_json(Path(args.pending), pending)
        session.commit()
    except Exception:
        session.rollback(); raise
    finally:
        session.close()
    # A new transaction proves the commit before immutable committed evidence is written.
    verify_doc = dict(pending, state="committed", verified_utc=datetime.now(timezone.utc).isoformat())
    session = SessionLocal()
    try:
        _identity_and_counts(session.connection(), require_empty=False)
        _verify_fixture(session, reservation, verify_doc)
    finally:
        session.rollback(); session.close()
    exclusive_json(Path(args.evidence), verify_doc)
    print("PASS: exact synthetic Tamil AI browser fixture committed and verified")


def verify(args):
    reservation = validate_reservation(load_json(Path(args.reservation)), args.run_id)
    evidence = load_json(Path(args.evidence))
    from app.core.database import SessionLocal
    session = SessionLocal()
    try:
        session.connection().exec_driver_sql("SET TRANSACTION READ ONLY")
        _identity_and_counts(session.connection(), require_empty=False)
        ids = _verify_fixture(session, reservation, evidence)
    finally:
        session.rollback(); session.close()
    print("PASS: exact fixture ownership, authoritative LKR 70.10 balance and zero unrelated records")
    return ids


def cleanup(args):
    verify(args)
    reservation = validate_reservation(load_json(Path(args.reservation)), args.run_id)
    evidence = load_json(Path(args.evidence)); ids = evidence["ids"]
    pending = {"version": 1, "kind": "tamil_ai_browser_fixture_cleanup", "state": "pending_commit",
               "database": TARGET, "run_id": args.run_id, "source_fingerprint": evidence["fingerprint"]}
    exclusive_json(Path(args.cleanup_pending), pending)
    from sqlalchemy import delete
    from app.core.database import SessionLocal
    from app.models import LedgerEntry, CreditAccount, CustomerProfile, BusinessMember, Business, User
    session = SessionLocal()
    try:
        _identity_and_counts(session.connection(), require_empty=False)
        _verify_fixture(session, reservation, evidence)
        deletes = ((LedgerEntry, [ids["sale_entry_id"], ids["repayment_entry_id"]]), (CreditAccount, [ids["credit_account_id"]]),
                   (CustomerProfile, [ids["customer_id"]]), (BusinessMember, [ids["membership_id"]]),
                   (Business, [ids["business_id"]]), (User, [ids["owner_user_id"], ids["customer_user_id"]]))
        for model, primary_keys in deletes:
            key = list(model.__table__.primary_key.columns)[0]
            result = session.execute(delete(model).where(key.in_(primary_keys)))
            if result.rowcount != len(primary_keys):
                raise ValueError("exact cleanup row count differs")
        session.commit()
    except Exception:
        session.rollback(); raise
    finally:
        session.close()
    from app.core.database import engine
    with engine.connect() as connection:
        _, after_counts = _identity_and_counts(connection, require_empty=True)
    exclusive_json(Path(args.cleanup_evidence), dict(
        pending, state="committed", verified_utc=datetime.now(timezone.utc).isoformat(),
        after_inventory_fingerprint=inventory_fingerprint(after_counts),
    ))
    print("PASS: exact fixture IDs removed; isolated schema is empty")


def parser():
    result = argparse.ArgumentParser()
    sub = result.add_subparsers(dest="command", required=True)
    reserve_p = sub.add_parser("reserve"); reserve_p.add_argument("--run-id", required=True); reserve_p.add_argument("--reservation", required=True)
    for name in ("create", "verify", "cleanup-review", "cleanup"):
        item = sub.add_parser(name); item.add_argument("--run-id", required=True); item.add_argument("--reservation", required=True)
        item.add_argument("--evidence", required=True)
        if name == "create": item.add_argument("--pending", required=True)
        if name == "cleanup": item.add_argument("--cleanup-pending", required=True); item.add_argument("--cleanup-evidence", required=True)
    return result


def main(argv=None):
    args = parser().parse_args(argv); require_run_id(args.run_id)
    if args.command == "reserve": reserve(args)
    elif args.command == "create": create(args)
    elif args.command in ("verify", "cleanup-review"): verify(args)
    else: cleanup(args)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("STOP: Tamil AI browser fixture gate failed; preserve private evidence and database state") from None

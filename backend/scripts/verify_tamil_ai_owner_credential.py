"""Operator-only credential comparison; imports are offline until --execute."""
import argparse
import os
from pathlib import Path

import tamil_ai_browser_fixture as fixture

RUN_ID = "14405b71b0504036a35ff55c7a9da132"
PRIVATE = Path(__file__).resolve().parents[2] / ".server-logs/private-ai-tests"


class Stop(Exception):
    pass


def require(condition, category):
    if not condition:
        raise Stop(category)


def documents(run_id):
    require(run_id == RUN_ID, "confirmation")
    reservation = fixture.validate_reservation(fixture.load_json(
        PRIVATE / f"tamil-ai-browser-fixture-{run_id}.json"), run_id)
    evidence = fixture.load_json(PRIVATE / f"tamil-ai-browser-fixture-{run_id}-created.json")
    ids = evidence.get("ids", {})
    require(evidence.get("state") == "committed" and evidence.get("database") == fixture.TARGET
            and evidence.get("run_id") == run_id
            and type(ids.get("owner_user_id")) is int and ids["owner_user_id"] > 0,
            "evidence")
    require(evidence.get("fingerprint") == fixture.fixture_fingerprint(ids, run_id), "evidence")
    return reservation, evidence


def compare(owner, expected_id, email, password, verifier):
    require(owner is not None and (owner.user_id, owner.email, owner.platform_role,
            owner.account_status) == (expected_id, email, "shop_owner", "active"), "owner_identity")
    require(bool(password) and verifier(password, owner.password_hash), "credential_mismatch")


def execute(reservation, evidence):
    from app.core.config import settings
    from app.core.database import engine
    from app.core.security import verify_password
    from app.models import User
    from sqlalchemy.orm import Session
    from check_tamil_ai_browser_config import validate_config

    validate_config(settings, engine.url, os.environ)
    session = Session(engine, autoflush=False)
    try:
        session.connection().exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        fixture._identity_and_counts(session.connection(), require_empty=False)
        fixture._verify_fixture(session, reservation, evidence)
        owner = session.get(User, evidence["ids"]["owner_user_id"])
        compare(owner, evidence["ids"]["owner_user_id"], reservation["owner_email"],
                os.environ.get("TAMIL_AI_OWNER_VERIFY_PASSWORD", ""), verify_password)
    finally:
        session.rollback()
        session.close()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-target", default="")
    args = parser.parse_args(argv)
    require(args.run_id == RUN_ID, "confirmation")
    if not args.execute:
        print("PASS: Owner credential verifier preparation; no credentials decrypted or database connected")
        return
    require(args.confirm_target == fixture.TARGET, "confirmation")
    reservation, evidence = documents(args.run_id)
    execute(reservation, evidence)
    print("PASS: reserved Owner credential matches committed fixture")


if __name__ == "__main__":
    try:
        main()
    except Stop as error:
        raise SystemExit(f"STOP: Owner credential verification category={error}") from None
    except Exception:
        raise SystemExit("STOP: Owner credential verification category=evidence_or_infrastructure") from None

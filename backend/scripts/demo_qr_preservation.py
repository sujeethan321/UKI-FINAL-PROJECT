"""Pure comparisons for sanitized demo QR inventory reports. No DB/file access."""
import hashlib
import re

TARGET = "lankapex_demo_db"
ACCOUNT = "lankapex_demo_app@localhost"
START = "6e3f2c1a9b04"
END = "7b9e4d2c8a15"
QR = {"business_join_links", "customer_join_requests"}
ORIGINAL = set("""
users businesses business_members customer_profiles credit_accounts ledger_entries
business_approval_audits payment_reminders notifications communication_consents
communication_attempts driver_profiles delivery_requests delivery_assignments
delivery_status_events product_categories products orders order_items admin_audits
customer_addresses user_preferences business_settings vehicles vehicle_documents
customer_link_invitations
""".split())
PROJECTIONS = {
    "credit_accounts", "ledger_entries", "customer_profiles", "business_members",
    "orders", "order_items", "delivery_requests", "delivery_assignments",
    "delivery_status_events", "payment_reminders",
}
NEW_FK_KEYS = {
    table + ":" + hashlib.sha256(name.encode()).hexdigest()
    for table, name in (
        ("business_join_links", "fk_business_join_business"),
        ("customer_join_requests", "fk_customer_join_business"),
        ("customer_join_requests", "fk_customer_join_user"),
        ("customer_join_requests", "fk_customer_join_decider"),
    )
}
MINIMUM_MIGRATOR_RIGHTS = frozenset({
    "SELECT", "INSERT", "UPDATE", "CREATE", "ALTER", "INDEX", "REFERENCES",
})


class PreservationStop(ValueError):
    """Fixed labels only, never report contents or financial values."""


def require(condition, category):
    if not condition:
        raise PreservationStop(category)


def _fingerprint(value, expected_rows=None):
    require(isinstance(value, dict) and set(value) == {"rows", "sha256"},
            "fingerprint_format")
    require(type(value["rows"]) is int and value["rows"] >= 0
            and isinstance(value["sha256"], str)
            and re.fullmatch("[0-9a-f]{64}", value["sha256"]), "fingerprint_format")
    if expected_rows is not None:
        require(value["rows"] == expected_rows, "fingerprint_row_count")


def validate(snapshot, *, after=False):
    require(isinstance(snapshot, dict), "report_format")
    require((snapshot.get("database"), snapshot.get("account"), snapshot.get("host"),
             snapshot.get("port")) == (TARGET, ACCOUNT, "localhost", 3306), "identity")
    expected = ORIGINAL | QR if after else ORIGINAL
    require(snapshot.get("revision") == (END if after else START), "revision")
    require(snapshot.get("application_tables") == len(expected)
            and snapshot.get("total_tables") == len(expected) + 1
            and set(snapshot.get("tables", [])) == expected | {"alembic_version"},
            "inventory")
    require(snapshot.get("privileges") == ["DELETE", "INSERT", "SELECT", "UPDATE"]
            and snapshot.get("global_usage_only") is True
            and snapshot.get("active_roles") == "NONE", "runtime_grants")
    require(snapshot.get("duplicate_profile_pair_count") == 0, "duplicate_profiles")
    require(snapshot.get("database_changed") is False
            and snapshot.get("evidence_file_created") is False, "inventory_side_effect")
    require(snapshot.get("fingerprint_unavailable") == [], "incomplete_fingerprints")
    counts = snapshot.get("row_counts")
    require(isinstance(counts, dict) and set(counts) == expected
            and all(type(c) is int and c >= 0 for c in counts.values()), "row_counts")
    hashes = snapshot.get("preservation_fingerprints")
    require(isinstance(hashes, dict) and set(hashes) == PROJECTIONS,
            "fingerprint_inventory")
    for table, value in hashes.items():
        _fingerprint(value, counts[table])
    _fingerprint(snapshot.get("signed_account_balance_fingerprint"),
                 counts["credit_accounts"])
    _fingerprint(snapshot.get("ledger_type_totals_fingerprint"))
    orphans = snapshot.get("foreign_key_orphan_counts")
    require(isinstance(orphans, dict) and orphans
            and all(type(c) is int and c == 0 for c in orphans.values()), "foreign_keys")
    if after:
        require(snapshot.get("current_schema_compatible") is True
                and snapshot.get("qr_structure_complete") is True
                and snapshot.get("qr_schema_state") == "complete", "qr_schema")
        require(all(counts[t] == 0 for t in QR), "new_qr_rows")
    else:
        require(snapshot.get("qr_schema_state") == "absent"
                and snapshot.get("missing_current_tables") == sorted(QR), "partial_start")
        require(snapshot.get("qr_metadata", {}).get("customer_profiles", {})
                .get("required_unique_constraint_present") is False, "partial_start")


def compare(before, after):
    """Require unchanged counts/projections/balances and exactly four new FKs."""
    validate(before)
    validate(after, after=True)
    require(all(before["row_counts"][t] == after["row_counts"][t] for t in ORIGINAL),
            "existing_row_counts_changed")
    for field in ("preservation_fingerprints", "signed_account_balance_fingerprint",
                  "ledger_type_totals_fingerprint"):
        require(before[field] == after[field], "preservation_fingerprint_changed")
    old_fks = before["foreign_key_orphan_counts"]
    new_fks = after["foreign_key_orphan_counts"]
    require(set(new_fks) == set(old_fks) | NEW_FK_KEYS
            and not set(old_fks) & NEW_FK_KEYS, "foreign_key_inventory_changed")
    return {
        "existing_application_tables_preserved": 26,
        "new_empty_qr_tables": 2,
        "financial_relationship_projections_preserved": True,
        "signed_balances_preserved": True,
        "foreign_key_orphans": 0,
        "full_row_preservation_proven": False,
    }

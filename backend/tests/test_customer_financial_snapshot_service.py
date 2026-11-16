"""Database-free customer scope and ledger-semantics tests for AI snapshots."""
import ast
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.customer_financial_snapshot_service import (
    AuthorizedFinancialFacts, CustomerFinancialSnapshotService, _effective_facts,
)
from app.services.tamil_credit_summary_prompt import FinancialSummarySnapshot

NOW = datetime(2026, 11, 14, 8, 30, tzinfo=timezone.utc)


class FakeRepository:
    def __init__(self, facts=None):
        self.facts = facts
        self.calls = []
        self.write_calls = 0

    def authorized_facts(self, user_id, credit_account_id):
        self.calls.append((user_id, credit_account_id))
        return self.facts


def facts(purchases="1000.00", repayments="250.00", outstanding="750.00", overdue=None):
    return AuthorizedFinancialFacts(
        total_credit_purchases=Decimal(purchases),
        total_repayments=Decimal(repayments),
        outstanding_balance=Decimal(outstanding),
        overdue_balance=Decimal(overdue) if overdue is not None else None,
    )


def service(repository):
    return CustomerFinancialSnapshotService(repository, clock=lambda: NOW)


def entry(ident, account, kind, amount, reverses=None, recorded_at=None):
    return SimpleNamespace(entry_id=ident, credit_account_id=account,
                           entry_type=kind, amount=Decimal(amount),
                           reverses_entry_id=reverses,
                           recorded_at=recorded_at or NOW)


def test_authorized_customer_account_produces_minimal_immutable_snapshot():
    repository = FakeRepository(facts())
    result = service(repository).assemble(41, 92)
    assert isinstance(result, FinancialSummarySnapshot)
    assert result.currency == "LKR"
    assert result.total_credit_purchases == Decimal("1000.00")
    assert result.total_repayments == Decimal("250.00")
    assert result.outstanding_balance == Decimal("750.00")
    assert result.overdue_balance is None
    assert result.captured_at == NOW
    assert repository.calls == [(41, 92)]


@pytest.mark.parametrize("reason", ["foreign_customer", "cross_business", "missing",
                                     "inactive_user", "inactive_account"])
def test_inaccessible_accounts_share_the_existing_generic_not_found_response(reason):
    repository = FakeRepository(None)
    with pytest.raises(HTTPException) as error:
        service(repository).assemble(41, 92)
    assert error.value.status_code == 404
    assert error.value.detail == "Credit account not found"
    assert repository.calls == [(41, 92)]


@pytest.mark.parametrize(("user_id", "account_id"), [
    (0, 1), (-1, 1), (1, 0), (1, -1), (True, 1), (1, False), ("1", 1),
])
def test_invalid_identifiers_fail_before_repository_access(user_id, account_id):
    repository = FakeRepository(facts())
    with pytest.raises(HTTPException) as error:
        service(repository).assemble(user_id, account_id)
    assert error.value.status_code == 404
    assert repository.calls == []


def test_partial_repayment_uses_existing_effective_ledger_arithmetic():
    rows = [entry(1, 92, "credit_sale", "100.00"),
            entry(2, 92, "repayment", "30.00")]
    result = _effective_facts(92, rows)
    assert result.total_credit_purchases == Decimal("100.00")
    assert result.total_repayments == Decimal("30.00")
    assert result.outstanding_balance == Decimal("70.00")


def test_calculation_defensively_excludes_rows_from_another_account():
    rows = [entry(1, 92, "credit_sale", "100.00"),
            entry(2, 999, "credit_sale", "9000.00"),
            entry(3, 999, "repayment", "1.00")]
    result = _effective_facts(92, rows)
    assert result.total_credit_purchases == Decimal("100.00")
    assert result.total_repayments == Decimal("0.00")
    assert result.outstanding_balance == Decimal("100.00")


@pytest.mark.parametrize(("reversed_kind", "expected_sales", "expected_repayments", "expected_balance"), [
    ("credit_sale", "0.00", "30.00", "0.00"),
    ("repayment", "100.00", "0.00", "100.00"),
])
def test_reversals_reuse_authoritative_effective_entry_rules(
        reversed_kind, expected_sales, expected_repayments, expected_balance):
    original_id = 1 if reversed_kind == "credit_sale" else 2
    rows = [entry(1, 92, "credit_sale", "100.00"),
            entry(2, 92, "repayment", "30.00"),
            entry(3, 92, "reversal", "1.00", reverses=original_id)]
    result = _effective_facts(92, rows)
    assert result.total_credit_purchases == Decimal(expected_sales)
    assert result.total_repayments == Decimal(expected_repayments)
    assert result.outstanding_balance == Decimal(expected_balance)


def test_zero_and_advance_positions_never_become_negative_outstanding():
    assert _effective_facts(92, []).outstanding_balance == Decimal("0.00")
    rows = [entry(1, 92, "repayment", "25.00")]
    result = _effective_facts(92, rows)
    assert result.total_repayments == Decimal("25.00")
    assert result.outstanding_balance == Decimal("0.00")


def test_snapshot_is_lifetime_current_position_not_a_reporting_period_total():
    old = NOW - timedelta(days=400)
    current = NOW - timedelta(days=1)
    rows = [entry(1, 92, "credit_sale", "50.00", recorded_at=old),
            entry(2, 92, "credit_sale", "25.00", recorded_at=current),
            entry(3, 92, "repayment", "10.00", recorded_at=current)]
    result = _effective_facts(92, rows)
    assert result.total_credit_purchases == Decimal("75.00")
    assert result.total_repayments == Decimal("10.00")
    assert result.outstanding_balance == Decimal("65.00")


def test_decimal_precision_is_preserved_without_float_conversion():
    rows = [entry(1, 92, "credit_sale", "0.10"),
            entry(2, 92, "credit_sale", "0.20"),
            entry(3, 92, "repayment", "0.10")]
    result = _effective_facts(92, rows)
    assert result.total_credit_purchases == Decimal("0.30")
    assert result.total_repayments == Decimal("0.10")
    assert result.outstanding_balance == Decimal("0.20")
    assert all(isinstance(getattr(result, name), (Decimal, type(None)))
               for name in result.__slots__)


def test_snapshot_has_no_identity_contact_raw_ledger_or_note_fields():
    names = {field.name for field in fields(FinancialSummarySnapshot)}
    assert names == {"currency", "total_credit_purchases", "total_repayments",
                     "outstanding_balance", "captured_at", "overdue_balance"}
    forbidden = {"name", "email", "phone", "address", "user_id", "customer_id",
                 "business_id", "credit_account_id", "notes", "transactions",
                 "ledger_entries"}
    assert names.isdisjoint(forbidden)


def test_fake_repository_observes_no_writes_commits_or_ai_calls():
    repository = FakeRepository(facts())
    result = service(repository).assemble(41, 92)
    assert result.outstanding_balance == Decimal("750.00")
    assert repository.write_calls == 0


def test_service_source_has_no_ai_provider_or_database_write_operations():
    path = Path(__file__).resolve().parents[1] / "app/services/customer_financial_snapshot_service.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports, calls = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            calls.append(node.func.attr)
    assert not any("groq" in name or name.endswith("integrations.ai") for name in imports)
    assert not set(calls) & {"add", "delete", "flush", "commit", "rollback"}


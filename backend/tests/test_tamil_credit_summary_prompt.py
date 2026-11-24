"""Database-free privacy and validation tests for Tamil summary prompts."""
import ast
from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.integrations.ai.base import GenerationRequest, MAX_GENERATION_INPUT_BYTES
from app.services.tamil_credit_summary_prompt import (
    FinancialSummarySnapshot, build_tamil_credit_summary_request,
)

NOW = datetime(2026, 11, 14, 8, 30, tzinfo=timezone.utc)


def snapshot(**updates):
    values = dict(
        currency="LKR",
        total_credit_purchases=Decimal("1000.00"),
        total_repayments=Decimal("250.00"),
        outstanding_balance=Decimal("750.00"),
        captured_at=NOW,
    )
    return FinancialSummarySnapshot(**(values | updates))


def test_valid_lkr_snapshot_is_immutable_and_builds_bounded_tamil_request():
    source = snapshot()
    with pytest.raises(FrozenInstanceError):
        source.outstanding_balance = Decimal("0.00")
    result = build_tamil_credit_summary_request(source)
    assert isinstance(result, GenerationRequest)
    assert "LKR" in result.user_prompt
    assert "1000.00" in result.user_prompt
    assert "250.00" in result.user_prompt
    assert "750.00" in result.user_prompt
    assert "captured_at" not in result.user_prompt
    assert result.response_schema is not None
    assert sum(len(x.encode("utf-8")) for x in
               (result.system_prompt, result.user_prompt)) <= MAX_GENERATION_INPUT_BYTES


def test_zero_balance_and_no_overdue_fact_are_explicit_without_invention():
    result = build_tamil_credit_summary_request(snapshot(
        total_credit_purchases=Decimal("0"), total_repayments=Decimal("0.0"),
        outstanding_balance=Decimal("0.00")))
    assert result.user_prompt.count("0.00") == 4
    assert "overdue_unavailable" in result.user_prompt


def test_partial_repayment_does_not_require_an_arithmetic_identity():
    # Reversals and advances mean the authoritative outstanding value need not
    # equal these two period aggregates. The builder must not recalculate it.
    source = snapshot(total_credit_purchases=Decimal("100.00"),
                      total_repayments=Decimal("30.00"),
                      outstanding_balance=Decimal("80.00"))
    result = build_tamil_credit_summary_request(source)
    assert all(value in result.user_prompt for value in ("100.00", "30.00", "80.00"))
    assert source.outstanding_balance == Decimal("80.00")


def test_optional_overdue_is_distinct_and_cannot_exceed_outstanding():
    result = build_tamil_credit_summary_request(snapshot(overdue_balance=Decimal("50.25")))
    assert '"overdue":"50.25"' in result.user_prompt
    assert '"current_outstanding":"750.00"' in result.user_prompt
    with pytest.raises(ValueError, match="cannot exceed"):
        snapshot(outstanding_balance=Decimal("10.00"), overdue_balance=Decimal("10.01"))


@pytest.mark.parametrize("value", [
    Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), Decimal("-0.01"),
    Decimal("1.001"), Decimal("10000000000000000000000.00"),
])
def test_invalid_decimal_values_are_rejected(value):
    with pytest.raises(ValueError):
        snapshot(outstanding_balance=value)


def test_float_and_missing_required_facts_are_rejected():
    with pytest.raises(TypeError, match="must be Decimal"):
        snapshot(total_repayments=1.5)
    with pytest.raises(TypeError):
        FinancialSummarySnapshot(currency="LKR", total_credit_purchases=Decimal("1"),
                                 total_repayments=Decimal("0"), captured_at=NOW)


@pytest.mark.parametrize("currency", ["USD", "lkr", "LKR ", ""])
def test_unsupported_or_noncanonical_currency_is_rejected(currency):
    with pytest.raises(ValueError, match="Unsupported currency"):
        snapshot(currency=currency)


@pytest.mark.parametrize("captured", [
    datetime(2026, 11, 14, 8, 30), "2026-11-14T08:30:00Z", None,
])
def test_invalid_or_timezone_naive_timestamps_are_rejected(captured):
    with pytest.raises((TypeError, ValueError)):
        snapshot(captured_at=captured)


def test_timestamp_is_normalized_to_utc_without_losing_the_instant():
    local = datetime(2026, 11, 14, 14, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    source = snapshot(captured_at=local)
    assert source.captured_at == datetime(2026, 11, 14, 8, 30, tzinfo=timezone.utc)


def test_snapshot_and_prompts_exclude_identity_raw_rows_and_sensitive_values():
    field_names = {field.name for field in fields(FinancialSummarySnapshot)}
    forbidden_fields = {"customer_name", "email", "phone", "address", "user_id",
                        "customer_id", "business_id", "credit_account_id",
                        "transactions", "notes", "ledger_entries"}
    assert field_names.isdisjoint(forbidden_fields)
    result = build_tamil_credit_summary_request(snapshot())
    for sentinel in ("private@example.test", "0771234567", "Private address",
                     "internal-note", "customer-id-42"):
        assert sentinel not in result.system_prompt
        assert sentinel not in result.user_prompt


def test_prompt_instructions_forbid_authoritative_calculation_and_decisions():
    result = build_tamil_credit_summary_request(snapshot())
    assert "மறுகணக்கிட்டு" in result.system_prompt
    assert "கடன் அனுமதி" in result.system_prompt
    assert "தனிப்பட்ட தகவலைக் கேட்காதீர்கள்" in result.system_prompt
    assert "fact_ids" in result.user_prompt


def test_assembled_prompt_limit_fails_closed(monkeypatch):
    import app.services.tamil_credit_summary_prompt as builder
    monkeypatch.setattr(builder, "SYSTEM_PROMPT", "அ" * MAX_GENERATION_INPUT_BYTES)
    with pytest.raises(ValueError, match="exceeds"):
        builder.build_tamil_credit_summary_request(snapshot())


def test_module_has_no_database_or_orm_dependencies():
    path = Path(__file__).resolve().parents[1] / "app/services/tamil_credit_summary_prompt.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any(name == "sqlalchemy" or name.startswith("sqlalchemy.") for name in imports)
    assert not any(name == "app.models" or name.startswith("app.models.") for name in imports)
    assert not any(name == "app.core.database" for name in imports)

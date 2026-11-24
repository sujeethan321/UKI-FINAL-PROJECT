"""Database-free orchestration and conservative generated-text checks."""
import asyncio
import ast
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.integrations.ai.base import (
    AIClientError, AIFailureCategory, GenerationResult,
)
from app.services.tamil_credit_summary_prompt import FinancialSummarySnapshot
from app.services.tamil_credit_summary_service import (
    ProviderAvailability, SummarySource, TamilCreditSummaryService,
    deterministic_tamil_fallback,
)

NOW = datetime(2026, 11, 14, 8, 30, tzinfo=timezone.utc)


def snapshot(**updates):
    values = dict(currency="LKR", total_credit_purchases=Decimal("1000.00"),
                  total_repayments=Decimal("250.00"),
                  outstanding_balance=Decimal("750.00"), captured_at=NOW)
    return FinancialSummarySnapshot(**(values | updates))


def valid_text(source=None):
    source = source or snapshot()
    overdue = (f"தவணை கடந்த தொகை {source.overdue_balance:.2f} LKR"
               if source.overdue_balance is not None
               else "தவணை கடந்த தொகை அதிகாரப்பூர்வமாகக் கணக்கிடப்படவில்லை")
    return (f"LKR மொத்த கடன் கொள்முதல் {source.total_credit_purchases:.2f}, "
            f"மொத்த திருப்பிச் செலுத்தல் {source.total_repayments:.2f}. "
            f"தற்போதைய நிலுவை {source.outstanding_balance:.2f}; {overdue}.")


class ResultClient:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    async def generate(self, request):
        self.calls += 1
        return GenerationResult(text=self.text, model="openai/gpt-oss-120b", finish_reason="stop")


class ErrorClient:
    def __init__(self, category):
        self.category = category
        self.calls = 0

    async def generate(self, request):
        self.calls += 1
        raise AIClientError(self.category)


class UnexpectedClient:
    async def generate(self, request):
        raise RuntimeError("private provider response and secret material")


def run(client, source=None):
    return asyncio.run(TamilCreditSummaryService(client).summarize(source or snapshot()))


def assert_fallback(result, source, category=None):
    assert result.source is SummarySource.FALLBACK
    assert result.provider_status is ProviderAvailability.UNAVAILABLE
    assert result.failure_category is category
    assert result.text == deterministic_tamil_fallback(source)


def test_successful_generation_returns_only_validated_text():
    import json
    from app.services.tamil_credit_summary_prompt import account_bundle
    client = ResultClient(json.dumps(dict(language="ta",sections=account_bundle(snapshot())[1])))
    result = run(client)
    assert result.source is SummarySource.GENERATED
    assert result.provider_status is ProviderAvailability.AVAILABLE
    assert result.failure_category is None
    assert result.text == deterministic_tamil_fallback(snapshot())
    assert client.calls == 1


@pytest.mark.parametrize("category", list(AIFailureCategory))
def test_every_client_failure_category_uses_exact_deterministic_fallback(category):
    source = snapshot()
    client = ErrorClient(category)
    result = run(client, source)
    assert_fallback(result, source, category)
    assert client.calls == 1


def test_unexpected_exception_is_generic_and_does_not_leak_text():
    source = snapshot()
    result = run(UnexpectedClient(), source)
    assert_fallback(result, source, AIFailureCategory.INVALID_RESPONSE)
    assert "private provider" not in result.text
    assert "secret" not in result.text


@pytest.mark.parametrize("text", [
    "", "   ", "LKR English only 1000.00 250.00 750.00",
    "<p>LKR கடன் 1000.00 250.00 750.00</p>",
    "**LKR கடன் 1000.00 250.00 750.00**",
    "LKR கடன் 1000.00 250.00 750.00\x00",
    "LKR கடன் 1000.00 250.00 750.00 " + "அ" * 2100,
    "LKR கடன் 1000.00 250.00 750.00 private@example.test",
    "LKR கடன் 1000.00 250.00 750.00 customer_id",
    "LKR கடன் 1000.00 250.00 750.00 நாளை செலுத்த வேண்டும்",
])
def test_invalid_oversized_markup_sensitive_or_prescriptive_text_falls_back(text):
    source = snapshot()
    assert_fallback(run(ResultClient(text), source), source,
                    AIFailureCategory.INVALID_RESPONSE)


@pytest.mark.parametrize("text", [
    # Missing an authoritative purchase total.
    "LKR திருப்பிச் செலுத்தல் 250.00; நிலுவை 750.00; தவணை கடந்த தொகை கணக்கிடப்படவில்லை.",
    # Invented amount.
    "LKR கொள்முதல் 1000.00; திருப்பிச் செலுத்தல் 250.00; நிலுவை 750.00; கூடுதல் 99.00; தவணை கடந்த தொகை கணக்கிடப்படவில்லை.",
    # Invented date.
    "LKR கொள்முதல் 1000.00; திருப்பிச் செலுத்தல் 250.00; நிலுவை 750.00; தவணை கடந்த தொகை கணக்கிடப்படவில்லை; 2026-12-01.",
    # Does not disclose overdue unavailability.
    "LKR கொள்முதல் 1000.00; திருப்பிச் செலுத்தல் 250.00; நிலுவை 750.00.",
])
def test_missing_or_invented_financial_facts_and_dates_fall_back(text):
    source = snapshot()
    assert_fallback(run(ResultClient(text), source), source,
                    AIFailureCategory.INVALID_RESPONSE)


def test_zero_balance_fallback_preserves_all_exact_values_without_recalculation():
    source = snapshot(total_credit_purchases=Decimal("0.00"),
                      total_repayments=Decimal("0.00"),
                      outstanding_balance=Decimal("0.00"))
    result = run(ErrorClient(AIFailureCategory.TIMEOUT), source)
    assert_fallback(result, source, AIFailureCategory.TIMEOUT)
    assert result.text.count("0.00") == 4


def test_partial_repayment_fallback_keeps_inconsistent_authoritative_outstanding():
    source = snapshot(total_credit_purchases=Decimal("100.00"),
                      total_repayments=Decimal("30.00"),
                      outstanding_balance=Decimal("80.00"))
    result = run(ErrorClient(AIFailureCategory.CONNECTION), source)
    assert all(value in result.text for value in ("100.00", "30.00", "80.00"))
    assert "70.00" not in result.text


def test_overdue_unavailable_and_supplied_are_distinct():
    absent = deterministic_tamil_fallback(snapshot())
    assert "கிடைக்கவில்லை" in absent
    source = snapshot(overdue_balance=Decimal("50.25"))
    supplied = deterministic_tamil_fallback(source)
    assert "காலம் கடந்த தொகை: LKR 50.25." in supplied
    import json
    from app.services.tamil_credit_summary_prompt import account_bundle
    result = run(ResultClient(json.dumps(dict(language="ta",sections=account_bundle(source)[1]))), source)
    assert result.source is SummarySource.GENERATED


def test_snapshot_is_not_mutated_and_wrong_input_is_rejected_before_client():
    source = snapshot()
    original = tuple(getattr(source, name) for name in source.__slots__)
    run(ResultClient(valid_text(source)), source)
    assert tuple(getattr(source, name) for name in source.__slots__) == original
    with pytest.raises(TypeError):
        asyncio.run(TamilCreditSummaryService(ResultClient(valid_text())).summarize({}))


def test_service_has_no_database_orm_logging_or_financial_writer_dependencies():
    path = Path(__file__).resolve().parents[1] / "app/services/tamil_credit_summary_service.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.append(node.func.attr)
    assert not any(name == "sqlalchemy" or name.startswith("sqlalchemy.") for name in imports)
    assert not any(name in {"app.models", "app.core.database", "logging"} for name in imports)
    assert not set(calls) & {"commit", "flush", "delete", "print"}

"""Side-effect-free orchestration for generated or deterministic Tamil summaries."""
from dataclasses import dataclass
from enum import Enum
import re
import unicodedata

from app.integrations.ai.base import (
    AIClient, AIClientError, AIFailureCategory, GenerationResult,
)
from app.services.tamil_credit_summary_prompt import (
    FinancialSummarySnapshot, build_tamil_credit_summary_request,
)

MAX_SUMMARY_CHARACTERS = 2_000
MAX_SUMMARY_BYTES = 8_000
# Match complete numeric facts while allowing an ordinary sentence-ending dot
# immediately after a two-decimal amount (for example, ``250.00.``).
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d{1,2})?(?!\d)(?!\.\d)")
DATE = re.compile(r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b")
EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.IGNORECASE)
PHONE = re.compile(r"(?<!\d)(?:\+?94|0)7\d{8}(?!\d)")
MARKUP = re.compile(r"<[^>]*>|(?:^|\n)\s*#{1,6}\s|\[[^\]]*\]\([^)]*\)|[`*_]{1,3}")
SENSITIVE_TERMS = re.compile(
    r"\b(?:user_id|customer_id|business_id|credit_account_id|email|phone|address|token)\b",
    re.IGNORECASE,
)
UNSAFE_CLAIMS = (
    "செலுத்த வேண்டும்", "நாளை செலுத்த", "கடன் அனுமதிக்கப்பட்ட", "கடன் அங்கீகரிக்கப்பட்ட",
    "financial advice", "credit approved", "must pay", "due date", "promise to pay",
    "new transaction",
)


class SummarySource(str, Enum):
    GENERATED = "generated"
    FALLBACK = "fallback"


class ProviderAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class TamilCreditSummaryResult:
    text: str
    source: SummarySource
    provider_status: ProviderAvailability
    failure_category: AIFailureCategory | None = None


def _money(value) -> str:
    return format(value, ".2f")


def deterministic_tamil_fallback(snapshot: FinancialSummarySnapshot) -> str:
    if not isinstance(snapshot, FinancialSummarySnapshot):
        raise TypeError("snapshot must be FinancialSummarySnapshot")
    overdue = (f"தவணை கடந்த தொகை {_money(snapshot.overdue_balance)} LKR"
               if snapshot.overdue_balance is not None
               else "தவணை கடந்த தொகை அதிகாரப்பூர்வமாகக் கணக்கிடப்படவில்லை")
    return (
        f"சரிபார்க்கப்பட்ட பதிவுகளின்படி, மொத்த கடன் கொள்முதல் "
        f"{_money(snapshot.total_credit_purchases)} LKR மற்றும் மொத்த திருப்பிச் செலுத்தல் "
        f"{_money(snapshot.total_repayments)} LKR. தற்போதைய நிலுவைத் தொகை "
        f"{_money(snapshot.outstanding_balance)} LKR; {overdue}. "
        "இது வழங்கப்பட்ட அதிகாரப்பூர்வத் தொகைகளின் விளக்கம் மட்டும்; புதிய கணக்கீடு, "
        "கடன் முடிவு அல்லது நிதி ஆலோசனை அல்ல."
    )


def _expected_amounts(snapshot: FinancialSummarySnapshot) -> set[str]:
    values = {
        _money(snapshot.total_credit_purchases),
        _money(snapshot.total_repayments),
        _money(snapshot.outstanding_balance),
    }
    if snapshot.overdue_balance is not None:
        values.add(_money(snapshot.overdue_balance))
    return values


def _valid_generated_text(text: object, snapshot: FinancialSummarySnapshot) -> bool:
    if not isinstance(text, str):
        return False
    candidate = text.strip()
    if (not candidate or len(candidate) > MAX_SUMMARY_CHARACTERS
            or len(candidate.encode("utf-8")) > MAX_SUMMARY_BYTES
            or "LKR" not in candidate
            or not any("\u0b80" <= char <= "\u0bff" for char in candidate)
            or DATE.search(candidate) or EMAIL.search(candidate) or PHONE.search(candidate)
            or MARKUP.search(candidate) or SENSITIVE_TERMS.search(candidate)
            or any(phrase.casefold() in candidate.casefold() for phrase in UNSAFE_CLAIMS)):
        return False
    if any(unicodedata.category(char) == "Cc" and char not in "\n\t" for char in candidate):
        return False
    expected = _expected_amounts(snapshot)
    found = set(NUMBER.findall(candidate))
    if not expected.issubset(found) or not found.issubset(expected):
        return False
    if snapshot.overdue_balance is None:
        if not any(phrase in candidate for phrase in
                   ("கணக்கிடப்படவில்லை", "கிடைக்கவில்லை", "வழங்கப்படவில்லை")):
            return False
    elif _money(snapshot.overdue_balance) not in candidate:
        return False
    return True


class TamilCreditSummaryService:
    def __init__(self, ai_client: AIClient):
        self._ai_client = ai_client

    async def summarize(self, snapshot: FinancialSummarySnapshot) -> TamilCreditSummaryResult:
        if not isinstance(snapshot, FinancialSummarySnapshot):
            raise TypeError("snapshot must be FinancialSummarySnapshot")
        fallback = deterministic_tamil_fallback(snapshot)
        try:
            generated = await self._ai_client.generate(
                build_tamil_credit_summary_request(snapshot))
        except AIClientError as error:
            return TamilCreditSummaryResult(
                text=fallback, source=SummarySource.FALLBACK,
                provider_status=ProviderAvailability.UNAVAILABLE,
                failure_category=error.category,
            )
        except Exception:
            # Do not expose unexpected exception text, provider data or prompts.
            return TamilCreditSummaryResult(
                text=fallback, source=SummarySource.FALLBACK,
                provider_status=ProviderAvailability.UNAVAILABLE,
            )
        if (not isinstance(generated, GenerationResult)
                or not _valid_generated_text(generated.text, snapshot)):
            return TamilCreditSummaryResult(
                text=fallback, source=SummarySource.FALLBACK,
                provider_status=ProviderAvailability.UNAVAILABLE,
                failure_category=AIFailureCategory.INVALID_RESPONSE,
            )
        return TamilCreditSummaryResult(
            text=generated.text.strip(), source=SummarySource.GENERATED,
            provider_status=ProviderAvailability.AVAILABLE,
        )


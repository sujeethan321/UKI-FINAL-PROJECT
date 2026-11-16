"""Privacy-minimized prompt construction from authoritative financial facts."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from app.integrations.ai.base import GenerationRequest, MAX_GENERATION_INPUT_BYTES

MONEY_QUANTUM = Decimal("0.01")
MAX_SUMMARY_AMOUNT = Decimal("9999999999999999999999.99")
SUPPORTED_CURRENCIES = frozenset({"LKR"})

SYSTEM_PROMPT = """நீங்கள் LankaPex வாடிக்கையாளருக்கான சுருக்கமான தமிழ் விளக்கத்தை எழுதுகிறீர்கள்.
வழங்கப்பட்ட, ஏற்கனவே சரிபார்க்கப்பட்ட நிதித் தொகைகளை மட்டும் விளக்குங்கள்.
புதிய பரிவர்த்தனை, கட்டணம், செலுத்த வேண்டிய நாள், வாக்குறுதி அல்லது காரணத்தை உருவாக்காதீர்கள்.
நிலுவைத் தொகையையும் தவணை கடந்த தொகையையும் ஒன்றாகக் கருதாதீர்கள்; தவணை கடந்த தொகை வழங்கப்படாதபோது அதை ஊகிக்காதீர்கள்.
தொகைகளை மறுகணக்கிட்டு அதிகாரப்பூர்வ முடிவாக அறிவிக்காதீர்கள்.
கடன் அனுமதி, கடன் வரம்பு மாற்றம் அல்லது நிதி ஆலோசனை வழங்காதீர்கள்.
பெயர், மின்னஞ்சல், தொலைபேசி, முகவரி அல்லது வேறு தனிப்பட்ட தகவலைக் கேட்காதீர்கள்.
எளிய இலங்கைத் தமிழில் இரண்டு அல்லது மூன்று குறுகிய வாக்கியங்களில் பதிலளிக்கவும்."""


def _validated_money(name: str, value: Decimal) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal")
    if not value.is_finite() or value < 0 or value > MAX_SUMMARY_AMOUNT:
        raise ValueError(f"{name} is outside the supported range")
    quantized = value.quantize(MONEY_QUANTUM)
    if value != quantized:
        raise ValueError(f"{name} must have at most two decimal places")
    return quantized


@dataclass(frozen=True, slots=True)
class FinancialSummarySnapshot:
    """Precomputed facts only; deliberately contains no identity or raw rows."""

    currency: str
    total_credit_purchases: Decimal
    total_repayments: Decimal
    outstanding_balance: Decimal
    captured_at: datetime
    overdue_balance: Decimal | None = None

    def __post_init__(self):
        if self.currency not in SUPPORTED_CURRENCIES:
            raise ValueError("Unsupported currency")
        for name in ("total_credit_purchases", "total_repayments", "outstanding_balance"):
            object.__setattr__(self, name, _validated_money(name, getattr(self, name)))
        if self.overdue_balance is not None:
            overdue = _validated_money("overdue_balance", self.overdue_balance)
            if overdue > self.outstanding_balance:
                raise ValueError("Overdue balance cannot exceed outstanding balance")
            object.__setattr__(self, "overdue_balance", overdue)
        if not isinstance(self.captured_at, datetime):
            raise TypeError("captured_at must be datetime")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("captured_at must include a timezone")
        object.__setattr__(self, "captured_at", self.captured_at.astimezone(timezone.utc))


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def build_tamil_credit_summary_request(snapshot: FinancialSummarySnapshot) -> GenerationRequest:
    if not isinstance(snapshot, FinancialSummarySnapshot):
        raise TypeError("snapshot must be FinancialSummarySnapshot")
    overdue = (_money(snapshot.overdue_balance)
               if snapshot.overdue_balance is not None
               else "அதிகாரப்பூர்வமாகக் கணக்கிடப்படவில்லை")
    captured = snapshot.captured_at.isoformat(timespec="seconds").replace("+00:00", "Z")
    user_prompt = "\n".join((
        "சரிபார்க்கப்பட்ட நிதிச் சுருக்கம்:",
        f"நாணயம்: {snapshot.currency}",
        f"மொத்த கடன் கொள்முதல்: {_money(snapshot.total_credit_purchases)}",
        f"மொத்த திருப்பிச் செலுத்தல்கள்: {_money(snapshot.total_repayments)}",
        f"தற்போதைய நிலுவைத் தொகை: {_money(snapshot.outstanding_balance)}",
        f"தவணை கடந்த தொகை: {overdue}",
        f"தகவல் எடுத்த நேரம் (UTC): {captured}",
        "இந்தத் தொகைகளுக்கு இடையில் புதிய கணக்கீடு செய்யாமல் விளக்கவும்.",
    ))
    result = GenerationRequest(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
    size = sum(len(value.encode("utf-8"))
               for value in (result.system_prompt, result.user_prompt))
    if size > MAX_GENERATION_INPUT_BYTES:
        raise ValueError("Tamil credit summary prompt exceeds the provider input limit")
    return result


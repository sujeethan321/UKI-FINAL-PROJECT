# Purpose: Build a constrained Tamil summary request from validated financial facts rather than arbitrary customer text.
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


# Reject unsupported monetary values before they enter the AI prompt snapshot.
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
    advance_balance: Decimal = Decimal('0.00')

    # Validate snapshot currency and financial values immediately after the dataclass is constructed.
    def __post_init__(self):
        if self.currency not in SUPPORTED_CURRENCIES:
            raise ValueError("Unsupported currency")
        for name in ("total_credit_purchases", "total_repayments", "outstanding_balance", "advance_balance"):
            object.__setattr__(self, name, _validated_money(name, getattr(self, name)))
        if self.outstanding_balance and self.advance_balance:
            raise ValueError('One account cannot have debt and advance simultaneously')
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


# Convert a financial value to the decimal representation required by this module.
def _money(value: Decimal) -> str:
    return format(value, ".2f")


# Build tamil credit summary request for the tamil credit summary prompt workflow.
def account_bundle(snapshot):
    facts=dict(account_credit_purchases=_money(snapshot.total_credit_purchases),account_repayments=_money(snapshot.total_repayments),
        current_outstanding=_money(snapshot.outstanding_balance),current_advances=_money(snapshot.advance_balance),
        overdue=_money(snapshot.overdue_balance) if snapshot.overdue_balance is not None else None)
    sections=[dict(section_id='account',fact_ids=list(facts),observation='overdue_unavailable' if snapshot.overdue_balance is None else 'provided_overdue')]
    return facts,sections

# Build tamil credit summary request for the tamil credit summary prompt workflow.
def build_tamil_credit_summary_request(snapshot: FinancialSummarySnapshot) -> GenerationRequest:
    if not isinstance(snapshot,FinancialSummarySnapshot):raise TypeError('snapshot must be FinancialSummarySnapshot')
    from app.services.financial_explanation import request
    from dataclasses import replace
    import json
    facts,sections=account_bundle(snapshot)
    result=request(dict(currency='LKR',facts=facts),sections,'ta')
    result=replace(result,system_prompt=SYSTEM_PROMPT+'\n'+result.system_prompt)
    size=sum(len(value.encode('utf-8')) for value in (result.system_prompt,result.user_prompt,json.dumps(result.response_schema)))
    if size>MAX_GENERATION_INPUT_BYTES:raise ValueError('Tamil credit summary prompt exceeds the provider input limit')
    return result

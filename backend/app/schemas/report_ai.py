"""No user-controlled prose crosses the provider boundary."""
from datetime import date
from typing import Literal,Annotated
from pydantic import BaseModel,ConfigDict,Field,model_validator

Question=Literal['credit_overview','sales_and_repayments','outstanding_and_advances','aging_and_coverage']
Money=Annotated[str,Field(pattern=r'^-?(?:0|[1-9]\d{0,23})\.\d{2}$')]
PositiveMoney=Annotated[str,Field(pattern=r'^(?:0|[1-9]\d{0,23})\.\d{2}$')]
Language=Literal['en','ta','si']

class Strict(BaseModel):model_config=ConfigDict(extra='forbid')

class ReportAIRequest(Strict):
    question_id: Question='credit_overview'
    language: Language='en'
    start_date: date
    end_date: date

class PeriodFacts(Strict):
    start: date
    end: date

class MovementFacts(Strict):
    credit_sales: Money
    repayments: Money

class CurrentFacts(Strict):
    total_outstanding: PositiveMoney
    customer_advances: PositiveMoney
    collected_today: Money | None
    overdue_amount: PositiveMoney | None

class Coverage(Strict):
    effective_sales: int=Field(ge=0)
    missing_due_dates: int=Field(ge=0)
    invalid_due_dates: int=Field(ge=0)
    unpaid_debt_fully_classified: bool

class AgingFacts(Strict):
    status: Literal['complete','incomplete','unavailable']
    reconciliation: Literal['matched','unavailable']
    coverage: Coverage | None
    buckets: dict[str,PositiveMoney] | None
    unclassified: PositiveMoney | None

class TrendFacts(MovementFacts):
    start: date
    end: date

class ReportFinancialFacts(Strict):
    currency: Literal['LKR']='LKR'
    period: PeriodFacts
    reporting_clock: Literal['database_wall_clock']='database_wall_clock'
    database_today: date
    period_totals: MovementFacts
    current: CurrentFacts
    aging: AgingFacts
    trends: list[TrendFacts]=Field(min_length=1,max_length=12)

    @model_validator(mode='after')
    def integrity(self):
        from decimal import Decimal
        if not 0<=(self.period.end-self.period.start).days<366:raise ValueError('Invalid report period')
        a=self.aging
        if a.status=='unavailable':
            if a.reconciliation!='unavailable' or a.buckets is not None or a.unclassified is not None or a.coverage is not None or self.current.overdue_amount is not None:raise ValueError('Invalid unavailable aging')
        else:
            if a.reconciliation!='matched' or a.coverage is None or a.buckets is None or a.unclassified is None:raise ValueError('Incomplete reconciliation')
            if a.coverage.missing_due_dates+a.coverage.invalid_due_dates>a.coverage.effective_sales:raise ValueError('Invalid coverage counts')
            if set(a.buckets)!={'current','days_1_30','days_31_60','days_61_90','days_91_plus'}:raise ValueError('Invalid aging buckets')
            total=sum((Decimal(v) for v in a.buckets.values()),Decimal(a.unclassified))
            if total!=Decimal(self.current.total_outstanding):raise ValueError('Aging reconciliation mismatch')
            complete=Decimal(a.unclassified)==0
            if complete!=(a.status=='complete') or a.coverage.unpaid_debt_fully_classified!=complete:raise ValueError('Invalid aging coverage')
            expected=sum((Decimal(v) for k,v in a.buckets.items() if k!='current'),Decimal('0.00')) if complete else None
            if (Decimal(self.current.overdue_amount) if self.current.overdue_amount is not None else None)!=expected:raise ValueError('Invalid overdue amount')
        for key in ('credit_sales','repayments'):
            if sum((Decimal(getattr(t,key)) for t in self.trends),Decimal('0.00'))!=Decimal(getattr(self.period_totals,key)):raise ValueError('Trend reconciliation mismatch')
        if self.trends[0].start!=self.period.start or self.trends[-1].end!=self.period.end:raise ValueError('Trend period mismatch')
        from datetime import timedelta
        previous=None
        for trend in self.trends:
            if trend.start>trend.end or previous is not None and trend.start!=previous+timedelta(days=1):raise ValueError('Invalid trend intervals')
            previous=trend.end
        return self

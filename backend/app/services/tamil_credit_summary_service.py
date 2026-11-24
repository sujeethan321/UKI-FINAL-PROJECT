"""Tamil account contract retained; no model prose or numeric pools accepted."""
import asyncio
from dataclasses import dataclass
from enum import Enum
from app.integrations.ai.base import AIClient,AIClientError,AIFailureCategory
from app.services.tamil_credit_summary_prompt import FinancialSummarySnapshot,account_bundle,build_tamil_credit_summary_request
from app.services import financial_explanation as explanation

MAX_SUMMARY_CHARACTERS=2000
MAX_SUMMARY_BYTES=8000

class SummarySource(str,Enum):
    GENERATED='generated'
    FALLBACK='fallback'

class ProviderAvailability(str,Enum):
    AVAILABLE='available'
    UNAVAILABLE='unavailable'

@dataclass(frozen=True,slots=True)
class TamilCreditSummaryResult:
    text:str
    source:SummarySource
    provider_status:ProviderAvailability
    failure_category:AIFailureCategory | None=None

def deterministic_tamil_fallback(snapshot):
    if not isinstance(snapshot,FinancialSummarySnapshot):raise TypeError('snapshot must be FinancialSummarySnapshot')
    facts,_=account_bundle(snapshot)
    text=' '.join(explanation.render_fact(key,value,'ta') for key,value in facts.items())+' '+explanation.phrase('current','ta')
    if snapshot.overdue_balance is None:text+=' '+explanation.phrase('account','ta')
    if len(text)>MAX_SUMMARY_CHARACTERS or len(text.encode())>MAX_SUMMARY_BYTES:raise ValueError('Summary exceeds bound')
    return text

class TamilCreditSummaryService:
    def __init__(self,ai_client:AIClient):self._ai_client=ai_client

    async def summarize(self,snapshot):
        # Invalid financial snapshots never become a fabricated fallback.
        fallback=deterministic_tamil_fallback(snapshot)
        _,sections=account_bundle(snapshot)
        try:
            generated=await asyncio.wait_for(self._ai_client.generate(build_tamil_credit_summary_request(snapshot)),timeout=30)
            explanation.validate(generated,sections,'ta')
        except AIClientError as error:
            return TamilCreditSummaryResult(fallback,SummarySource.FALLBACK,ProviderAvailability.UNAVAILABLE,error.category)
        except TimeoutError:
            return TamilCreditSummaryResult(fallback,SummarySource.FALLBACK,ProviderAvailability.UNAVAILABLE,AIFailureCategory.TIMEOUT)
        except Exception:
            return TamilCreditSummaryResult(fallback,SummarySource.FALLBACK,ProviderAvailability.UNAVAILABLE,AIFailureCategory.INVALID_RESPONSE)
        # All output text is backend-rendered, including the AI-assisted path.
        return TamilCreditSummaryResult(fallback,SummarySource.GENERATED,ProviderAvailability.AVAILABLE)

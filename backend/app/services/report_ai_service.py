"""Read-only verified facts; provider selects templates, never supplies amounts."""
import asyncio
from datetime import datetime,timezone
from decimal import Decimal
from math import ceil
from fastapi import HTTPException
from pydantic import ValidationError
from app.core.config import settings
from app.integrations.ai.base import AIClientError
from app.schemas.report_ai import ReportFinancialFacts
from app.services.shop_owner_reports_service import report
from app.services import financial_explanation as explanation

MODEL=explanation.MODEL

async def get_report_ai_client():
    secret=getattr(settings,'GROQ_API_KEY',None)
    if not getattr(settings,'AI_ENABLED',False) or secret is None or not secret.get_secret_value().strip() or getattr(settings,'GROQ_MODEL',None)!=MODEL:
        yield None;return
    import httpx
    from app.integrations.ai.groq_client import GroqAIClient
    async with httpx.AsyncClient(follow_redirects=False,trust_env=False) as transport:yield GroqAIClient(settings,transport)

def build_context(db,business_id,payload):
    data=report(db,business_id,payload.start_date,payload.end_date)
    days=data['daily'];width=max(1,ceil(len(days)/12));trends=[]
    for start in range(0,len(days),width):
        chunk=days[start:start+width]
        trends.append(dict(start=chunk[0]['date'],end=chunk[-1]['date'],**{
            key:format(sum((Decimal(row[key]) for row in chunk),Decimal('0.00')),'.2f') for key in ('credit_sales','repayments')}))
    aging=data['aging']
    values=dict(currency='LKR',period=dict(start=data['start_date'],end=data['end_date']),reporting_clock='database_wall_clock',database_today=data['database_today'],
        period_totals={key:data['totals'][key] for key in ('credit_sales','repayments')},
        current={key:data['summary'][key] for key in ('total_outstanding','customer_advances','collected_today','overdue_amount')},
        aging={key:aging[key] for key in ('status','buckets','unclassified','coverage','reconciliation')},trends=trends)
    try:return ReportFinancialFacts.model_validate(values).model_dump(mode='json')
    except ValidationError:raise HTTPException(409,'Financial summary facts could not be verified. Review the financial report.') from None

def facts_and_sections(context,question_id):
    # Revalidate even when called outside the router. No arbitrary/raw context.
    context=ReportFinancialFacts.model_validate(context).model_dump(mode='json')
    c=context['current'];a=context['aging'];totals=context['period_totals']
    facts=dict(period_credit_sales=totals['credit_sales'],period_repayments=totals['repayments'],
        current_outstanding=c['total_outstanding'],current_advances=c['customer_advances'],collected_today=c['collected_today'],overdue=c['overdue_amount'],unclassified=a['unclassified'])
    for key in ('current','days_1_30','days_31_60','days_61_90','days_91_plus'):facts['aging_'+key]=(a['buckets'] or {}).get(key)
    first,last=context['trends'][0],context['trends'][-1]
    for label,interval in (('first',first),('last',last)):
        for key in ('credit_sales','repayments'):facts['trend_'+label+'_'+key]=interval[key]
    plans={'credit_overview':['period','current','aging','trends'],'sales_and_repayments':['period','trends'],
        'outstanding_and_advances':['current'],'aging_and_coverage':['aging']}
    specs={
        'period':dict(section_id='period',fact_ids=['period_credit_sales','period_repayments'],observation='negative_movements' if any(Decimal(v)<0 for v in totals.values()) else 'period_movements'),
        'current':dict(section_id='current',fact_ids=['current_outstanding','current_advances','collected_today'],observation='debt_and_advances_separate'),
        'aging':dict(section_id='aging',fact_ids=['overdue','aging_current','aging_days_1_30','aging_days_31_60','aging_days_61_90','aging_days_91_plus','unclassified'],observation='aging_'+a['status']),
        'trends':dict(section_id='trends',fact_ids=['trend_first_credit_sales','trend_first_repayments','trend_last_credit_sales','trend_last_repayments'],observation='interval_totals'),
    }
    return facts,[specs[name] for name in plans[question_id]]

def render(context,sections,language,question_id):
    facts,_=facts_and_sections(context,question_id);output=[]
    # Dates and amounts below are backend facts, never model-returned values.
    output.append(context['period']['start']+' — '+context['period']['end']+'; LKR; '+context['reporting_clock']+'; '+context['database_today'])
    output.append(explanation.phrase('scope',language))
    for section in sections:
        ident=section['section_id']
        if ident=='trends':
            output.append(explanation.phrase('intervals',language))
            for index in (0,-1):
                interval=context['trends'][index]
                output.append(interval['start']+' — '+interval['end']+'; '+explanation.render_fact('period_credit_sales',interval['credit_sales'],language)+' '+explanation.render_fact('period_repayments',interval['repayments'],language))
        else:
            output.extend(explanation.render_fact(key,facts[key],language) for key in section['fact_ids'])
            if ident in ('period','current'):output.append(explanation.phrase(ident,language))
            else:
                output.append(explanation.phrase('fifo',language));output.append(explanation.phrase('aging_unavailable' if context['aging']['status']=='unavailable' else context['aging']['status'],language))
                coverage=context['aging']['coverage']
                if coverage:output.append(explanation.phrase('coverage_counts',language).format(sales=coverage['effective_sales'],missing=coverage['missing_due_dates'],invalid=coverage['invalid_due_dates']))
    text='\n'.join(output)
    if len(text)>6000:raise ValueError('Explanation exceeds bound')
    return text

def validate_output(result,context,language,question_id='credit_overview'):
    _,sections=facts_and_sections(context,question_id)
    verified=explanation.validate(result,sections,language)
    return render(context,verified,language,question_id)

async def generate(context,payload,client):
    # Integrity/validation failures occur OUTSIDE provider fallback handling.
    _,sections=facts_and_sections(context,payload.question_id)
    fallback=render(context,sections,payload.language,payload.question_id)
    source='fallback';status='disabled' if not getattr(settings,'AI_ENABLED',False) else 'unavailable';failure='configuration';text=fallback
    if client is not None and getattr(settings,'AI_ENABLED',False):
        try:
            req=explanation.request(context,sections,payload.language)
            result=await asyncio.wait_for(client.generate(req),timeout=min(30,float(settings.GROQ_TIMEOUT_SECONDS)+1))
            text=validate_output(result,context,payload.language,payload.question_id)
            source='generated';status='available';failure=None
        except AIClientError as error:failure=error.category.value
        except TimeoutError:failure='timeout'
        except Exception:failure='invalid_response'
    return dict(summary=text,source=source,provider_status=status,failure_category=failure,model=MODEL if source=='generated' else None,
        generated_at=datetime.now(timezone.utc),facts=context)

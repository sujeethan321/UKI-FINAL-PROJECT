"""Active-Admin-only aggregate reports. No commit, financial locks or writes."""
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.auth_dependencies import require_admin
from app.core.database import get_db
from app.core.rate_limit import _consume
from app.models import User
from app.schemas.admin_reports import Filters, Overview, Comparisons
from app.services.admin_reports_service import capture, MAX_EXPORT_ROWS

HEADERS={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
router=APIRouter(prefix='/admin/reports',tags=['Admin reports'])


def budget(request:Request,user:Annotated[User,Depends(require_admin)]):
    if hasattr(request.app.state,'rate_limit_config'):
        export=request.url.path.endswith(('.csv','.pdf'))
        _consume(request,[('admin-report-export' if export else 'admin-report-read',str(user.user_id),
            request.app.state.rate_limit_config.RATE_LIMIT_EXPORT if export else 20)])
    return user


router.dependencies=[Depends(budget)]


def dataset(db,filters):
    try: return capture(db,filters)
    except HTTPException as error:
        error.headers={**(error.headers or {}),**HEADERS}; raise
    except SQLAlchemyError:
        raise HTTPException(503,'Admin report unavailable; required schema or database connection could not be verified',headers=HEADERS) from None


Database=Annotated[Session,Depends(get_db)]
Selection=Annotated[Filters,Depends()]
Language=Annotated[Literal['en','ta','si'],Query()]


@router.get('/overview',response_model=Overview)
def overview(response:Response,db:Database,filters:Selection):
    response.headers.update(HEADERS)
    return dataset(db,filters)[0]


@router.get('/businesses',response_model=Comparisons)
def businesses(response:Response,db:Database,filters:Selection,limit:Annotated[int,Query(ge=1,le=100)]=20,offset:Annotated[int,Query(ge=0,le=1000)]=0):
    response.headers.update(HEADERS)
    report,rows=dataset(db,filters)
    return Comparisons(report=report,total=len(rows),limit=limit,offset=offset,sort=filters.sort,direction=filters.direction,rows=rows[offset:offset+limit])


def export(db,filters,language,format):
    report,rows=dataset(db,filters)
    if len(rows)>MAX_EXPORT_ROWS: raise HTTPException(422,'Export exceeds business limit',headers=HEADERS)
    if format=='csv':
        from app.services.admin_reports_csv import render_report_csv
        content=render_report_csv(report,rows,language); media='text/csv; charset=utf-8'
    else:
        from app.services.admin_reports_pdf import render_report_pdf,ReportPDFUnavailable
        try: content=render_report_pdf(report,rows,language)
        except ReportPDFUnavailable:
            raise HTTPException(503,'Admin PDF unavailable; check report size and installed language fonts',headers=HEADERS) from None
        media='application/pdf'
    filename=f'LankaPex-admin-{report.start_date.isoformat()}-{report.end_date.isoformat()}-{language}.{format}'
    return Response(content,media_type=media,headers={**HEADERS,'Content-Disposition':f'attachment; filename="{filename}"'})


@router.get('/export.csv')
def csv_export(db:Database,filters:Selection,language:Language='en'): return export(db,filters,language,'csv')


@router.get('/export.pdf')
def pdf_export(db:Database,filters:Selection,language:Language='en'): return export(db,filters,language,'pdf')

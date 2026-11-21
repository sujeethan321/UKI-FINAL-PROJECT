"""Step 380: one read-only business-1 comparison; no retries or saved reports.

Credentials are hidden terminal input. No production application/service imports.
Independent SQL window allocation, not the Reports aging implementation.
"""
import argparse
import csv
from decimal import Decimal
import getpass
import importlib.util
from io import StringIO
import logging
from pathlib import Path
import re
import sys
import unicodedata
import warnings

ZERO = Decimal('0.00')
KEYS = ('current','days_1_30','days_31_60','days_61_90','days_91_plus')
BASE = '''WITH scoped AS (
 SELECT e.* FROM ledger_entries e JOIN credit_accounts a USING(credit_account_id)
 WHERE a.creditor_business_id=1 AND a.customer_id IS NOT NULL
), effective AS (
 SELECT e.* FROM scoped e WHERE e.entry_type IN ('credit_sale','repayment')
 AND NOT EXISTS(SELECT 1 FROM scoped r WHERE r.entry_type='reversal' AND r.reverses_entry_id=e.entry_id
 AND r.credit_account_id=e.credit_account_id)
) '''
FIFO = BASE + ''', payments AS (
 SELECT credit_account_id,SUM(amount) paid FROM effective WHERE entry_type='repayment' GROUP BY credit_account_id
), sales AS (
 SELECT e.*,SUM(amount) OVER(PARTITION BY credit_account_id ORDER BY recorded_at,entry_id ROWS UNBOUNDED PRECEDING) cumulative
 FROM effective e WHERE entry_type='credit_sale'
)
SELECT s.credit_account_id,s.amount,s.recorded_at,s.due_at,
 LEAST(s.amount,GREATEST(s.cumulative-COALESCE(p.paid,0),0)) residual
FROM sales s LEFT JOIN payments p USING(credit_account_id)'''


def require(ok):
    if not ok:
        raise ValueError('Mismatch or insufficient evidence')


def normalize(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text).replace('\u2010','-').replace('\u2011','-').replace('\u2013','-')).strip()


def compare(data, rows, balances, now):
    require(data['business_id']==1 and data['summary']['business_id']==1)
    require(data['reporting_clock']=='database_wall_clock' and data['database_today']==now.date().isoformat())
    a=data['aging']
    require(a['as_of']==now.date().isoformat() and a['reconciliation']=='matched')
    buckets=dict.fromkeys(KEYS,ZERO); unknown=ZERO
    per_account={}; missing=invalid=0
    for account, amount, recorded, due, residual in rows:
        require(recorded<=now)
        residual=Decimal(residual)
        require(ZERO<=residual<=Decimal(amount))
        per_account[account]=per_account.get(account,ZERO)+residual
        if due is None or not hasattr(due,'date') or due<recorded:
            missing+=due is None; invalid+=due is not None
            unknown+=residual
        else:
            days=(now.date()-due.date()).days
            key=KEYS[0 if days<=0 else 1 if days<=30 else 2 if days<=60 else 3 if days<=90 else 4]
            buckets[key]+=residual
    for account,balance in balances:
        require(per_account.get(account,ZERO)==max(Decimal(balance),ZERO))
    total=sum((max(Decimal(balance),ZERO) for _,balance in balances),ZERO)
    require(sum(buckets.values(),ZERO)+unknown==total==Decimal(data['summary']['total_outstanding']))
    require(a['status']==('complete' if unknown==ZERO else 'incomplete'))
    require(a['coverage']==dict(effective_sales=len(rows),missing_due_dates=missing,invalid_due_dates=invalid,unpaid_debt_fully_classified=unknown==ZERO))
    require(set(a['buckets'])==set(KEYS))
    require(all(Decimal(a['buckets'][k])==v for k,v in buckets.items()))
    require(Decimal(a['unclassified'])==unknown)
    overdue=sum((buckets[k] for k in KEYS[1:]),ZERO) if unknown==ZERO else None
    require((Decimal(a['overdue_amount']) if a['overdue_amount'] is not None else None)==overdue)
    require((Decimal(data['summary']['overdue_amount']) if data['summary']['overdue_amount'] is not None else None)==overdue)
    return buckets,unknown,overdue


def check_exports(data, csv_bytes, pdf_bytes):
    import pymupdf
    a=data['aging']
    rows=list(csv.reader(StringIO(csv_bytes.decode('utf-8-sig'))))
    def row(label,value): require([label,value] in rows)
    row('Aging coverage',a['status']); row('Aging reconciliation',a['reconciliation'])
    require(any(r and r[0]=='Current aging policy' and 'Reporting-only FIFO' in r[1] for r in rows))
    for key,value in a['buckets'].items(): row('Current aging '+key+' (LKR)',f'{Decimal(value):.2f}')
    row('Unclassified current debt (LKR)',f"{Decimal(a['unclassified']):.2f}")
    row('Current overdue (LKR; exact only under disclosed FIFO policy)',
        f"{Decimal(a['overdue_amount']):.2f}" if a['overdue_amount'] is not None else 'Unavailable; incomplete or invalid coverage')
    with pymupdf.open(stream=pdf_bytes,filetype='pdf') as pdf:
        text=normalize(' '.join(page.get_text() for page in pdf))
    require('VIVA-BUSINESS-1' in text and 'Reporting-only FIFO' in text and 'database wall clock' in text)
    for key,label in zip(KEYS,('Current','1-30 days overdue','31-60 days overdue','61-90 days overdue','91+ days overdue')):
        require(re.search(re.escape(label)+r'\s+'+re.escape(f"{Decimal(a['buckets'][key]):,.2f}")+r'(?![\d.])',text))
    require(re.search('Unclassified'+r'\s+'+re.escape(f"{Decimal(a['unclassified']):,.2f}")+r'(?![\d.])',text))
    if a['overdue_amount'] is not None:
        require(re.search('Overdue Amount'+r'\s+'+re.escape(f"{Decimal(a['overdue_amount']):,.2f}")+r'(?![\d.])',text))
    else:
        require('Exact overdue amount is unavailable' in text)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read-only',required=True,action='store_true'); parser.parse_args()
    logging.disable(logging.CRITICAL)
    stage='PRIVATE_INPUT'
    try:
        require(sys.stdin.isatty())
        warnings.simplefilter('error',getpass.GetPassWarning)
        token=getpass.getpass('Existing synthetic Shop Owner access token (hidden): ')
        password=getpass.getpass('Existing viva runtime password (hidden): ')
        require(bool(token) and bool(password))
        import httpx
        import pymysql
        stage='AUTHENTICATED_REPORT_FIELDS'
        with httpx.Client(timeout=30,trust_env=False,follow_redirects=False,transport=httpx.HTTPTransport(retries=0)) as client:
            headers={'Authorization':'Bearer '+token}
            response=client.get('http://127.0.0.1:8001/api/v1/shop-owner/reports/financial',params={'business_id':1},headers=headers)
            require(response.status_code==200 and response.headers.get('cache-control')=='no-store')
            data=response.json(); require('aging' in data)
            stage='READ_ONLY_INDEPENDENT_FIFO'
            path=Path(__file__).resolve().parents[2]/'output/step322/guarded_viva_setup.py'
            spec=importlib.util.spec_from_file_location('step380_guards',path)
            guards=importlib.util.module_from_spec(spec); spec.loader.exec_module(guards)
            conn=pymysql.connect(host='127.0.0.1',port=3306,database='lankapex_viva_db',user=guards.RUNTIME,
                password=password,ssl=guards.tls_context(),autocommit=False,connect_timeout=5,read_timeout=30,write_timeout=15)
            try:
                guards.rows(conn,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                guards.rows(conn,'START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
                guards.identity(conn,guards.RUNTIME,'lankapex_viva_db')
                require(guards.scalar(conn,'SELECT version_num FROM alembic_version')=='9d1a6f4e0c37')
                require(guards.scalar(conn,BASE+'SELECT COUNT(*) FROM scoped')<=100000)
                require(guards.scalar(conn,'''SELECT COUNT(*) FROM credit_accounts a LEFT JOIN customer_profiles c ON c.customer_id=a.customer_id
                    WHERE a.creditor_business_id=1 AND a.customer_id IS NOT NULL AND (c.customer_id IS NULL OR c.business_id<>1)''')==0)
                require(guards.scalar(conn,BASE+"SELECT COUNT(*) FROM scoped WHERE recorded_at IS NULL OR amount<=0 OR entry_type NOT IN ('credit_sale','repayment','reversal')")==0)
                now=guards.scalar(conn,'SELECT NOW()')
                # Validate every reference, including references outside this business.
                invalid=guards.scalar(conn,BASE+'''SELECT COUNT(*) FROM scoped e LEFT JOIN ledger_entries o ON o.entry_id=e.reverses_entry_id
                  WHERE (e.entry_type='reversal' AND (o.entry_id IS NULL OR o.credit_account_id<>e.credit_account_id
                  OR o.entry_type NOT IN ('credit_sale','repayment') OR o.recorded_at>e.recorded_at
                  OR (o.recorded_at=e.recorded_at AND o.entry_id>=e.entry_id)))
                  OR (e.entry_type<>'reversal' AND e.reverses_entry_id IS NOT NULL)''')
                require(invalid==0)
                require(guards.scalar(conn,BASE+"SELECT COUNT(*) FROM (SELECT reverses_entry_id FROM scoped WHERE entry_type='reversal' GROUP BY reverses_entry_id HAVING COUNT(*)>1) d")==0)
                require(guards.scalar(conn,BASE+'SELECT COUNT(*) FROM scoped WHERE recorded_at>%s',(now,))==0)
                reversals=guards.scalar(conn,BASE+"SELECT COUNT(*) FROM scoped WHERE entry_type='reversal'")
                rows=guards.rows(conn,FIFO)
                balances=guards.rows(conn,BASE+"SELECT credit_account_id,SUM(CASE WHEN entry_type='credit_sale' THEN amount ELSE -amount END) FROM effective GROUP BY credit_account_id")
                _,unknown,overdue=compare(data,rows,balances,now)
            finally:
                conn.close()
            stage='CSV_PDF_COMPARISON'
            params={'business_id':1,'start_date':data['start_date'],'end_date':data['end_date']}
            exports=[]
            for extension,kind in (('csv','text/csv'),('pdf','application/pdf')):
                r=client.get('http://127.0.0.1:8001/api/v1/shop-owner/reports/financial.'+extension,params=params,headers=headers)
                require(r.status_code==200 and r.headers.get('cache-control')=='no-store' and kind in r.headers.get('content-type',''))
                require('attachment;' in r.headers.get('content-disposition',''))
                exports.append(r.content)
            check_exports(data,*exports)
        print('STEP380_API_DATABASE_EXPORTS=PASS')
        print('BUSINESS=VIVA-BUSINESS-1')
        print('OVERDUE_AMOUNT=MATCH'); print('AGING_BUCKETS=MATCH_ALL_SIX'); print('FIFO_RECONCILIATION=MATCH_EVERY_ACCOUNT_AND_AGGREGATE')
        print('CSV_CONSISTENCY=MATCH'); print('PDF_CONSISTENCY=MATCH_ENGLISH; OTHER_LANGUAGES_OFFLINE_TESTED')
        print('LIVE_EDGE_CASE_COVERAGE=OVERDUE_'+('PRESENT' if overdue and overdue>ZERO else 'NOT_EXERCISED')+'; REVERSALS_'+('PRESENT' if reversals else 'NOT_EXERCISED')+'; UNCLASSIFIED_'+('PRESENT' if unknown else 'NOT_EXERCISED'))
        print('FRONTEND_DISPLAY=MANUAL_CHECK_PENDING')
        return 0
    except (Exception,KeyboardInterrupt):
        print('STEP380_API_DATABASE_EXPORTS=BLOCKED'); print('DIAGNOSTIC_STAGE='+stage)
        print('NEXT_ACTION=STOP; no retry; missing aging fields may require a separately authorized restart; concurrent changes require review')
        return 1


if __name__=='__main__': sys.exit(main())

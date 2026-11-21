"""Step 372: existing business 1, authenticated report GET and independent SELECTs.

No login POST, data writes, Stripe, reports saved, retries or application imports.
The existing browser access token and runtime password are hidden-input only.
"""
import argparse
from datetime import date, timedelta
from decimal import Decimal
import getpass
import importlib.util
import logging
from pathlib import Path
import sys
import warnings

import httpx
import pymysql

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ('TOTAL_OUTSTANDING', 'COLLECTED_TODAY', 'CREDIT_SALES', 'REPAYMENTS', 'DAILY_TRENDS', 'REVERSAL_HANDLING')
# Reversals negate the original's full amount on the reversal date, matching
# statements even if a legacy reversal's descriptive amount differs.
FROM = ''' FROM ledger_entries e
JOIN credit_accounts a ON a.credit_account_id=e.credit_account_id
JOIN customer_profiles c ON c.customer_id=a.customer_id AND c.business_id=1
LEFT JOIN ledger_entries o ON o.entry_id=e.reverses_entry_id AND o.credit_account_id=e.credit_account_id
WHERE a.creditor_business_id=1 '''
SALES = "CASE WHEN e.entry_type='credit_sale' THEN e.amount WHEN e.entry_type='reversal' AND o.entry_type='credit_sale' THEN -o.amount ELSE 0 END"
REPAYMENTS = "CASE WHEN e.entry_type='repayment' THEN e.amount WHEN e.entry_type='reversal' AND o.entry_type='repayment' THEN -o.amount ELSE 0 END"
OUTSTANDING = '''WITH balances AS (
 SELECT a.credit_account_id,COALESCE(SUM(CASE WHEN e.entry_type='credit_sale' THEN e.amount WHEN e.entry_type='repayment' THEN -e.amount ELSE 0 END),0) AS balance
 FROM credit_accounts a LEFT JOIN ledger_entries e ON e.credit_account_id=a.credit_account_id
 AND e.entry_type IN ('credit_sale','repayment') AND NOT EXISTS (
 SELECT 1 FROM ledger_entries r WHERE r.credit_account_id=e.credit_account_id
 AND r.entry_type='reversal' AND r.reverses_entry_id=e.entry_id)
 WHERE a.creditor_business_id=1 AND a.customer_id IS NOT NULL GROUP BY a.credit_account_id
) SELECT COALESCE(SUM(GREATEST(balance,0)),0) FROM balances'''


def require(condition):
    if not condition:
        raise RuntimeError('Comparison incomplete or mismatched')


def compare(data, outstanding, collected, daily):
    start, end = date.fromisoformat(data['start_date']), date.fromisoformat(data['end_date'])
    require(start <= end and (end-start).days < 366 and end < date.max)
    expected = {start+timedelta(days=i): (Decimal(0), Decimal(0)) for i in range((end-start).days+1)}
    for day, sales, repayments in daily:
        require(day in expected)
        expected[day] = (Decimal(sales), Decimal(repayments))
    points = data['daily']
    require(len(points) == len(expected))
    require([(point['date'], Decimal(point['credit_sales']), Decimal(point['repayments'])) for point in points]
        == [(day.isoformat(), sales, repayments) for day,(sales,repayments) in expected.items()])
    require(Decimal(data['summary']['total_outstanding']) == Decimal(outstanding))
    require(Decimal(data['summary']['collected_today']) == Decimal(collected))
    require(Decimal(data['totals']['credit_sales']) == sum((row[0] for row in expected.values()), Decimal(0)))
    require(Decimal(data['totals']['repayments']) == sum((row[1] for row in expected.values()), Decimal(0)))
    require(data['summary']['overdue_amount'] is None)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read-only',required=True,action='store_true')
    parser.add_argument('--start-date',type=date.fromisoformat)
    parser.add_argument('--end-date',type=date.fromisoformat)
    args=parser.parse_args()
    status='BLOCKED'; result={key:'UNVERIFIED' for key in FIELDS}; phase='LOCAL_INPUT'
    logging.disable(logging.CRITICAL)
    try:
        require(sys.stdin.isatty() and bool(args.start_date)==bool(args.end_date))
        if args.start_date:
            require(args.start_date<=args.end_date<date.max and (args.end_date-args.start_date).days<366)
        warnings.simplefilter('error',getpass.GetPassWarning)
        token=getpass.getpass('Existing signed-in synthetic Shop Owner access token (hidden; never paste in chat): ')
        password=getpass.getpass('Existing viva runtime password (hidden): ')
        require(bool(token) and bool(password))
        phase='AUTHENTICATED_REPORT_GET'
        params={'business_id':1}
        if args.start_date:
            params.update(start_date=args.start_date.isoformat(),end_date=args.end_date.isoformat())
        with httpx.Client(timeout=20,trust_env=False,follow_redirects=False,transport=httpx.HTTPTransport(retries=0)) as client:
            response=client.get('http://127.0.0.1:8001/api/v1/shop-owner/reports/financial',params=params,
                headers={'Authorization':'Bearer '+token})
        require(response.status_code==200 and response.headers.get('cache-control')=='no-store')
        data=response.json()
        require(data['business_id']==1 and data['summary']['business_id']==1 and data['currency']=='LKR'
            and data['reporting_clock']=='database_wall_clock')
        start,end=date.fromisoformat(data['start_date']),date.fromisoformat(data['end_date'])
        today=date.fromisoformat(data['database_today'])
        require(start<=end<date.max and (end-start).days<366)
        if args.start_date:
            require((start,end)==(args.start_date,args.end_date))
        else:
            require(end==today and start==today-timedelta(days=29))
        phase='INDEPENDENT_MYSQL_SELECTS'
        spec=importlib.util.spec_from_file_location('step372_guards',ROOT/'output/step322/guarded_viva_setup.py')
        guards=importlib.util.module_from_spec(spec); spec.loader.exec_module(guards)
        conn=pymysql.connect(host='127.0.0.1',port=3306,database='lankapex_viva_db',user=guards.RUNTIME,
            password=password,ssl=guards.tls_context(),autocommit=False,connect_timeout=5,read_timeout=30,write_timeout=15)
        try:
            with conn.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                cursor.execute('SET TRANSACTION READ ONLY')
            guards.identity(conn,guards.RUNTIME,'lankapex_viva_db')
            require(guards.rows(conn,'SELECT version_num FROM alembic_version')==(('9d1a6f4e0c37',),))
            require(guards.scalar(conn,'SELECT CURRENT_DATE()')==today)
            outstanding=guards.scalar(conn,OUTSTANDING)
            collected=guards.scalar(conn,'SELECT COALESCE(SUM('+REPAYMENTS+'),0)'+FROM+
                ' AND e.recorded_at >= %s AND e.recorded_at < %s',(today,today+timedelta(days=1)))
            daily=guards.rows(conn,'SELECT DATE(e.recorded_at),SUM('+SALES+'),SUM('+REPAYMENTS+')'+FROM+
                ' AND e.recorded_at >= %s AND e.recorded_at < %s GROUP BY DATE(e.recorded_at) ORDER BY DATE(e.recorded_at)',(start,end+timedelta(days=1)))
            invalid=guards.scalar(conn,'SELECT COUNT(*)'+FROM+''' AND e.entry_type='reversal'
 AND ((e.recorded_at >= %s AND e.recorded_at < %s) OR (e.recorded_at >= %s AND e.recorded_at < %s))
 AND (o.entry_id IS NULL OR o.entry_type NOT IN ('credit_sale','repayment')
 OR o.recorded_at>e.recorded_at OR (o.recorded_at=e.recorded_at AND o.entry_id>=e.entry_id))''',
                (start,end+timedelta(days=1),today,today+timedelta(days=1)))
            require(invalid==0)
            reversal_count=guards.scalar(conn,'SELECT COUNT(*)'+FROM+" AND e.entry_type='reversal' AND e.recorded_at >= %s AND e.recorded_at < %s",(start,end+timedelta(days=1)))
            compare(data,outstanding,collected,daily)
        finally:
            conn.close()
        result={key:'MATCH' for key in FIELDS}
        result['REVERSAL_HANDLING']='MATCH; REVERSAL_ROWS_PRESENT' if reversal_count else 'NO_LIVE_REVERSALS_IN_SELECTED_PERIOD; OFFLINE_COVERAGE_ONLY'
        status='PASS'; phase='COMPLETE'
    except (Exception,KeyboardInterrupt):
        pass  # No exception text, tokens, records, response bodies or monetary values.
    print('STEP372_COMPARISON='+status)
    print('BUSINESS=VIVA-BUSINESS-1')
    for key,value in result.items(): print(key+'='+value)
    print('BUSINESS_ISOLATION='+('BUSINESS_1_QUERY_SCOPE_AND_RESPONSE_CHECKED; CROSS_OWNER_LIVE_TEST_NOT_PERFORMED'
        if status=='PASS' else 'UNVERIFIED_LIVE; SOURCE_QUERIES_FIXED_TO_BUSINESS_1'))
    print('NEXT_ACTION='+('Review export plan; no export implemented' if status=='PASS' else 'STOP; '+phase+' incomplete/mismatched; no automatic retry; concurrent writes or clock differences require review'))
    return 0 if status=='PASS' else 1


if __name__=='__main__': sys.exit(main())

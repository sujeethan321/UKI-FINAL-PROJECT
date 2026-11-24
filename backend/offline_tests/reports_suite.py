"""SQLite-only Reports regressions; base suite forbids application networking."""
from datetime import date, datetime, timedelta
from decimal import Decimal
import csv
from io import StringIO
import unicodedata
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

import subscription_suite as base
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.models import CreditAccount, CustomerProfile, LedgerEntry
from app.services import shop_owner_reports_service as reports
from app.services.shop_owner_financial_documents_service import customer_statement
from app.services.shop_owner_reports_csv import render_report_csv, safe_text, money
from app.routers import shop_owner

base.TABLES.extend([CustomerProfile.__table__, CreditAccount.__table__, LedgerEntry.__table__])


class ReportsTests(TestCase):
    def setUp(self):
        self.options = patch.multiple(base.config.settings, create=True,
            MAX_INTERACTIVE_CUSTOMERS=100, MAX_READ_LEDGER_ENTRIES=1000)
        self.options.start()
        self.engine = create_engine('sqlite://', poolclass=base.StaticPool, connect_args={'check_same_thread': False})
        base.create_tables(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        base.seed(self.db)
        self.user = self.db.get(base.User, 2)
        for business_id in (10, 20):
            self.db.get(base.Business, business_id).approval_status = 'approved'
            # Report/export fixtures explicitly exercise an entitled Pro trial.
            from app.models.subscription import SubscriptionTrialGrant
            from app.services.subscription_service import utc_now, calendar_month_end
            stamp=utc_now()
            self.db.add(SubscriptionTrialGrant(business_id=business_id,grant_status='GRANTED',
                trial_started_at=stamp,trial_ends_at=calendar_month_end(stamp),created_at=stamp))
        for ident, business_id in ((1, 10), (2, 10), (3, 20)):
            self.db.add(CustomerProfile(customer_id=ident, business_id=business_id, customer_name='Synthetic'))
        self.db.flush()
        for ident, business_id in ((1, 10), (2, 10), (3, 20)):
            self.db.add(CreditAccount(credit_account_id=ident, creditor_business_id=business_id,
                customer_id=ident, credit_limit=1000, payment_term_days=30, account_status='active'))
        self.db.commit()

    def tearDown(self):
        self.db.close(); self.engine.dispose(); self.options.stop()

    def entry(self, ident, kind, amount, stamp, account=1, reverses=None):
        self.db.add(LedgerEntry(entry_id=ident, credit_account_id=account, created_by=2,
            entry_type=kind, amount=Decimal(amount), recorded_at=datetime.fromisoformat(stamp),
            reverses_entry_id=reverses, idempotency_key='report-'+str(ident)))
        self.db.commit()

    def test_sale_partial_repayment_advances_and_business_isolation(self):
        self.entry(1, 'credit_sale', '100.10', '2026-11-01T23:59:59')
        self.entry(2, 'repayment', '30.05', '2026-11-02T00:00:00')
        self.entry(3, 'repayment', '50', '2026-11-02T01:00:00', account=2)
        self.entry(4, 'credit_sale', '900', '2026-11-02T02:00:00', account=3)
        result = reports.report(self.db, 10, date(2026,11,1), date(2026,11,2))
        self.assertEqual(result['totals'], dict(credit_sales='100.10', repayments='80.05'))
        self.assertEqual(result['summary']['total_outstanding'], '70.05')
        self.assertEqual(result['daily'][0]['repayments'], '0.00')
        self.assertEqual(result['daily'][1]['repayments'], '80.05')
        self.assertFalse(self.db.dirty)

    def test_dashboard_collections_aging_repayments_and_isolation(self):
        from app.services.shop_owner_dashboard_service import get_dashboard_summary
        now = self.db.scalar(select(base.func.now()))
        sale_at = now - timedelta(days=10)
        self.entry(1,'credit_sale','100.10',sale_at.isoformat())
        self.db.get(LedgerEntry,1).due_at = now - timedelta(days=1)
        self.db.commit()
        self.entry(2,'repayment','30.05',now.isoformat())
        self.entry(3,'repayment','500',now.isoformat(),account=2)
        self.entry(4,'credit_sale','900',sale_at.isoformat(),account=3)
        result = get_dashboard_summary(self.db,10)
        self.assertEqual(result['collected_today'],'530.05')
        self.assertEqual(result['overdue_amount'],'70.05')
        self.assertEqual(result['total_outstanding'],Decimal('70.05'))
        self.entry(5,'reversal','1',now.isoformat(),reverses=2)
        result = get_dashboard_summary(self.db,10)
        self.assertEqual(result['collected_today'],'500.00')
        self.assertEqual(result['overdue_amount'],'100.10')
        self.entry(6,'repayment','100.10',now.isoformat())
        self.assertEqual(get_dashboard_summary(self.db,10)['overdue_amount'],'0.00')
        self.assertFalse(self.db.dirty)

    def test_dashboard_empty_future_due_and_missing_due(self):
        from app.services.shop_owner_dashboard_service import get_dashboard_summary
        empty = get_dashboard_summary(self.db,10)
        self.assertEqual(empty['collected_today'],'0.00')
        self.assertEqual(empty['overdue_amount'],'0.00')
        now = self.db.scalar(select(base.func.now()))
        self.entry(1,'credit_sale','100', (now-timedelta(days=1)).isoformat())
        missing = get_dashboard_summary(self.db,10)
        self.assertIsNone(missing['overdue_amount'])
        self.assertEqual(missing['due_totals_status'],'incomplete')
        self.db.get(LedgerEntry,1).due_at = now + timedelta(days=2)
        self.db.commit()
        self.assertEqual(get_dashboard_summary(self.db,10)['overdue_amount'],'0.00')

    def test_reversal_is_adjustment_on_its_own_day_using_full_original(self):
        self.entry(1, 'credit_sale', '100', '2026-11-01T10:00:00')
        self.entry(2, 'repayment', '30', '2026-11-02T10:00:00')
        self.entry(3, 'reversal', '1', '2026-11-03T10:00:00', reverses=2)
        result = reports.report(self.db, 10, date(2026,11,1), date(2026,11,3))
        self.assertEqual([r['repayments'] for r in result['daily']], ['0.00','30.00','-30.00'])
        old = reports.report(self.db, 10, date(2026,11,2), date(2026,11,2))
        self.assertEqual(old['totals']['repayments'], '30.00')
        statement = customer_statement(self.db, self.db.get(base.Business,10), 1, date(2026,11,1), date(2026,11,3))
        self.assertEqual(statement['closing_balance'], '100.00')
        self.assertEqual(statement['reversal_impact'], '30.00')
        self.assertEqual(result['summary']['total_outstanding'], '100.00')
        self.entry(4, 'reversal', '1', '2026-11-04T10:00:00', reverses=1)
        result = reports.report(self.db,10,date(2026,11,4),date(2026,11,4))
        self.assertEqual(result['totals']['credit_sales'], '-100.00')
        entries = self.db.scalars(select(LedgerEntry)).all()
        self.assertEqual(reports.trends(entries,date(2026,11,3),date(2026,11,3),date(2026,11,3))[1], '-30.00')

    def test_today_uses_database_clock_and_inclusive_end_excludes_next_midnight(self):
        self.entry(1,'repayment','12.25','2026-11-02T23:59:59')
        self.entry(2,'repayment','5','2026-11-03T00:00:00')
        entries = self.db.scalars(select(LedgerEntry)).all()
        daily, collected = reports.trends(entries,date(2026,11,2),date(2026,11,2),date(2026,11,3))
        self.assertEqual(daily[0]['repayments'],'12.25')
        self.assertEqual(collected,'5.00')
        actual = reports.report(self.db,10)
        database_today = self.db.scalar(select(base.func.now())).date()
        self.assertEqual(actual['database_today'],database_today)
        self.assertEqual(actual['end_date'],database_today)

    def test_empty_invalid_and_bounded_ranges(self):
        self.assertEqual(reports.report(self.db,10,date(2026,1,1),date(2026,1,1))['totals'],
            dict(credit_sales='0.00',repayments='0.00'))
        for start,end in ((date(2026,2,1),date(2026,1,1)),(date(2024,1,1),date(2025,1,1)),(date.max,date.max)):
            with self.assertRaises(HTTPException): reports.period(start,end,date.today())
        self.assertEqual(reports.period(date(2024,1,1),date(2024,12,31),date.today())[1],date(2024,12,31))
        with patch.object(base.config.settings,'MAX_INTERACTIVE_CUSTOMERS',1), self.assertRaises(HTTPException):
            reports.report(self.db,10)

    def test_invalid_reversal_chronology_is_rejected(self):
        fake = SimpleNamespace(entry_id=1, credit_account_id=1, entry_type='reversal',
            reverses_entry_id=99, amount=Decimal(1),recorded_at=datetime(2026,11,1))
        with self.assertRaises(HTTPException): reports.trends([fake],date(2026,11,1),date(2026,11,1),date(2026,11,1))

    def test_http_authorization_cache_and_validation(self):
        app=FastAPI(); app.include_router(shop_owner.router,prefix='/api/v1')
        app.dependency_overrides[base.get_db]=lambda:self.db
        app.dependency_overrides[base.get_current_user]=lambda:self.user
        with TestClient(app) as client:
            response=client.get('/api/v1/shop-owner/reports/financial?business_id=10&start_date=2026-11-01&end_date=2026-11-02')
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.headers['cache-control'],'no-store')
            for business_id in (20,30):
                denied=client.get('/api/v1/shop-owner/reports/financial',params={'business_id':business_id})
                self.assertEqual(denied.status_code,403)
                self.assertEqual(denied.headers['cache-control'],'no-store')
            for role,status in (('shop_owner','suspended'),('customer','active')):
                self.user.platform_role=role; self.user.account_status=status
                self.assertEqual(client.get('/api/v1/shop-owner/reports/financial?business_id=10').status_code,403)
            self.user.platform_role='shop_owner'; self.user.account_status='active'
            member=self.db.scalar(select(base.BusinessMember).where(base.BusinessMember.business_id==10))
            member.membership_status='inactive'; self.db.flush()
            self.assertEqual(client.get('/api/v1/shop-owner/reports/financial?business_id=10').status_code,403)
            self.assertEqual(client.get('/api/v1/shop-owner/reports/financial?business_id=10&start_date=invalid').status_code,422)

    def test_dashboard_http_authorization_and_cache(self):
        with self.csv_client() as client:
            url='/api/v1/shop-owner/dashboard/summary'
            result=client.get(url,params={'business_id':10})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.headers['cache-control'],'no-store')
            self.assertEqual(result.json()['collected_today'],'0.00')
            self.assertEqual(result.json()['overdue_amount'],'0.00')
            self.assertEqual(client.get(url,params={'business_id':20}).status_code,403)
            self.user.platform_role='customer'
            self.assertEqual(client.get(url,params={'business_id':10}).status_code,403)
            self.user.platform_role='shop_owner'
            member=self.db.scalar(select(base.BusinessMember).where(base.BusinessMember.business_id==10))
            member.membership_status='inactive';self.db.flush()
            self.assertEqual(client.get(url,params={'business_id':10}).status_code,403)

    def csv_client(self):
        app=FastAPI(); app.include_router(shop_owner.router,prefix='/api/v1')
        app.dependency_overrides[base.get_db]=lambda:self.db
        app.dependency_overrides[base.get_current_user]=lambda:self.user
        return TestClient(app)

    def test_csv_matches_json_including_dates_reversals_headers_and_current_overview(self):
        self.entry(1,'credit_sale','100.10','2026-11-01T23:59:59')
        self.entry(2,'repayment','30.05','2026-11-02T00:00:00')
        self.entry(3,'reversal','1','2026-11-03T12:00:00',reverses=2)
        statements=[]
        def capture(conn,cursor,sql,params,context,many): statements.append(sql.strip().split()[0].upper())
        base.event.listen(self.engine,'before_cursor_execute',capture)
        params=dict(business_id=10,start_date='2026-11-01',end_date='2026-11-03')
        with self.csv_client() as client:
            data=client.get('/api/v1/shop-owner/reports/financial',params=params).json()
            response=client.get('/api/v1/shop-owner/reports/financial.csv',params=params)
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(response.content.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(response.headers['x-content-type-options'],'nosniff')
        self.assertEqual(response.headers['content-type'],'text/csv; charset=utf-8')
        self.assertEqual(response.headers['content-disposition'],
            'attachment; filename="LankaPex-financial-10-2026-11-01-2026-11-03.csv"')
        rows=list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))
        values={row[0]:row[1:] for row in rows if len(row)>1}
        self.assertEqual(values['Period net credit sales (LKR)'],[data['totals']['credit_sales']])
        self.assertEqual(values['Period net repayments (LKR)'],[data['totals']['repayments']])
        self.assertEqual(values['Current outstanding (LKR; not a historical period-end balance)'],[data['summary']['total_outstanding']])
        self.assertEqual(values['Collected today (LKR; database reporting day, independent of selected period)'],[data['summary']['collected_today']])
        self.assertEqual(values['Reporting clock'],['database_wall_clock'])
        for day in data['daily']:
            self.assertEqual(values[day['date']],[day['credit_sales'],day['repayments']])
        self.assertEqual(values['2026-11-03'],['0.00','-30.05'])
        self.assertFalse(set(statements)&{'INSERT','UPDATE','DELETE','CREATE','ALTER','DROP'})

    def test_csv_security_date_bounds_and_owner_approval_checks(self):
        with self.csv_client() as client:
            def get(**extra):
                return client.get('/api/v1/shop-owner/reports/financial.csv',params={
                    'business_id':10,'start_date':'2026-11-01','end_date':'2026-11-03',**extra})
            self.assertEqual(get(business_id=20).status_code,403)
            self.assertEqual(get(business_id=30).status_code,403)
            self.assertEqual(get(end_date='2028-01-01').status_code,422)
            self.assertEqual(get(start_date='2027-01-01').status_code,422)
            self.assertEqual(get(start_date='bad\r\nfilename').status_code,422)
            for role,status in [('admin','active'),('customer','active'),('shop_owner','suspended')]:
                self.user.platform_role=role; self.user.account_status=status
                self.assertEqual(get().status_code,403)
            self.user.platform_role='shop_owner'; self.user.account_status='active'
            member=self.db.scalar(select(base.BusinessMember).where(base.BusinessMember.business_id==10))
            member.membership_status='inactive'; self.db.flush()
            denied=get(); self.assertEqual(denied.status_code,403)
            self.assertEqual(denied.headers['cache-control'],'no-store')

    def test_csv_formula_safety_quoting_precision_and_empty_period(self):
        for text in ['=1+1','+cmd','-1+2','@SUM(A1)',' \t=HYPERLINK("evil")','\ttext','\rtext']:
            self.assertTrue(safe_text(text).startswith("'"))
        self.assertEqual(f'{money("-99999999999999.01"):.2f}','-99999999999999.01')
        for invalid in ['NaN','Infinity','1.001','=1+1']:
            with self.assertRaises(Exception): money(invalid)
        data=reports.report(self.db,10,date(2026,1,1),date(2026,1,1))
        data['reporting_clock']='=SUM(1,2)\n"quoted"'
        rows=list(csv.reader(StringIO(render_report_csv(data).decode('utf-8-sig'))))
        self.assertIn(['Reporting clock',"'=SUM(1,2)\n\"quoted\""],rows)
        self.assertIn(['2026-01-01','0.00','0.00'],rows)

    def test_pdf_reuses_report_amounts_and_secure_download_headers(self):
        import pymupdf
        self.entry(1,'credit_sale','100.10','2026-11-01T10:00:00')
        self.entry(2,'repayment','30.05','2026-11-02T10:00:00')
        self.entry(3,'reversal','1','2026-11-03T10:00:00',reverses=2)
        params=dict(business_id=10,start_date='2026-11-01',end_date='2026-11-03',language='en')
        with self.csv_client() as client:
            data=client.get('/api/v1/shop-owner/reports/financial',params=params).json()
            response=client.get('/api/v1/shop-owner/reports/financial.pdf',params=params)
        self.assertEqual(response.status_code,200,response.text[:100])
        self.assertEqual(response.headers['content-type'],'application/pdf')
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(response.headers['x-content-type-options'],'nosniff')
        self.assertEqual(response.headers['content-disposition'],
            'attachment; filename="LankaPex-financial-10-2026-11-01-2026-11-03-en.pdf"')
        with pymupdf.open(stream=response.content,filetype='pdf') as pdf:
            text=unicodedata.normalize('NFKC',''.join(page.get_text() for page in pdf)).replace('\u2010','-')
            self.assertIn('100.10',text); self.assertIn('-30.05',text)
            self.assertIn('Current outstanding',text)
            self.assertIn('not a historical period-end balance',text)
            self.assertIn('geographical timezone is not verified',text)
            self.assertIn('2026-11-03',text)
        self.assertEqual(data['totals']['repayments'],'0.00')
        self.assertFalse(self.db.dirty)

    def test_pdf_multilingual_font_embedding_and_long_report_pagination(self):
        import pymupdf
        from app.services.shop_owner_reports_pdf import render_report_pdf, report_font, LABELS
        data=reports.report(self.db,10,date(2024,1,1),date(2024,12,31))
        for language in ('en','ta','si'):
            self.assertTrue(report_font(language).is_file())
            with pymupdf.open(stream=render_report_pdf(data,language),filetype='pdf') as pdf:
                self.assertGreater(len(pdf),1); self.assertLessEqual(len(pdf),40)
                text=unicodedata.normalize('NFKC',''.join(page.get_text() for page in pdf)).replace('\u2010','-')
                self.assertIn('2024-12-31',text)
                self.assertNotIn('\ufffd',text)
                if language!='en':
                    low,high=(0x0b80,0x0bff) if language=='ta' else (0x0d80,0x0dff)
                    self.assertGreater(sum(low<=ord(c)<=high for c in text),30)
                embedded=[pdf.extract_font(font[0])[3] for font in pdf[0].get_fonts() if font[1] not in ('n/a','')]
                self.assertTrue(any(embedded))
                for page in pdf:
                    self.assertIn(f'{page.number+1} / {len(pdf)}',page.get_text())
        for language in LABELS:
            self.assertTrue(LABELS[language]['clock'])

    def test_pdf_authorization_bounds_language_and_missing_font_fail_closed(self):
        from app.services import shop_owner_reports_pdf as pdf_service
        with self.csv_client() as client:
            def get(**extra):
                return client.get('/api/v1/shop-owner/reports/financial.pdf',params={
                    'business_id':10,'start_date':'2026-11-01','end_date':'2026-11-03',**extra})
            for business in (20,30): self.assertEqual(get(business_id=business).status_code,403)
            self.assertEqual(get(language='other').status_code,422)
            self.assertEqual(get(end_date='2028-01-01').status_code,422)
            self.user.account_status='suspended'
            self.assertEqual(get().status_code,403)
            self.user.account_status='active'
            self.user.platform_role='customer'
            self.assertEqual(get().status_code,403)
            self.user.platform_role='shop_owner'
            with patch.object(pdf_service,'report_font',side_effect=pdf_service.ReportPDFUnavailable()):
                response=get(language='ta')
                self.assertEqual(response.status_code,503)
                self.assertEqual(response.headers['cache-control'],'no-store')


if __name__ == '__main__': main(verbosity=2)

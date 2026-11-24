"""AR-02: fictional SQLite fixtures only; imported harness blocks all networking."""
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from unittest import TestCase,main
from unittest.mock import patch,MagicMock
import csv
from io import StringIO
import jwt
import delivery_estimate_suite as fixture
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event,select,func
from app.schemas.admin_reports import Filters
from app.services import admin_reports_service as service
from app.services.admin_reports_csv import render_report_csv
from app.services.admin_reports_pdf import render_report_pdf,ReportPDFUnavailable
from app.routers import admin_reports
from app.models import User,Business,BusinessApprovalAudit,Order,LedgerEntry,DeliveryRequest,DeliveryAssignment,DeliveryStatusEvent


class AdminReportsTests(TestCase):
    setUp=fixture.IntegrationTests.setUp
    tearDown=fixture.IntegrationTests.tearDown

    def filters(self,**changes):return Filters(start_date=date(2026,11,1),end_date=date(2026,11,3),**changes)

    def ledger(self,ident,kind,amount,account=1,reverses=None,stamp='2026-11-01T12:00:00'):
        self.db.add(LedgerEntry(entry_id=ident,credit_account_id=account,created_by=2,entry_type=kind,amount=Decimal(amount),
            recorded_at=datetime.fromisoformat(stamp),reverses_entry_id=reverses,idempotency_key='admin-report-'+str(ident)))
        self.db.commit()

    def order(self,ident,status='processing',business=10,amount='100.00'):
        self.db.add(Order(order_id=ident,reference='AR-'+str(ident),business_id=business,customer_user_id=4,request_key='ar-'+str(ident),request_hash='a'*64,
            status=status,payment_method='cash',payment_status='unpaid',subtotal=Decimal(amount),total=Decimal(amount),created_at=datetime(2026,11,2)))
        self.db.commit()

    def client(self):
        app=FastAPI();app.include_router(admin_reports.router,prefix='/api/v1')
        app.dependency_overrides[fixture.fixtures.base.get_db]=lambda:self.db
        return TestClient(app)

    def headers(self,ident=1):
        now=datetime.now(timezone.utc)
        token=jwt.encode({'sub':str(ident),'type':'access','iat':now,'exp':now+timedelta(minutes=10)},fixture.fixtures.base.config.settings.JWT_SECRET_KEY,algorithm='HS256')
        return {'Authorization':'Bearer '+token}

    def test_empty_and_finance_disabled_no_optional_tables_or_writes(self):
        statements=[]
        event.listen(self.engine,'before_cursor_execute',lambda conn,cursor,statement,parameters,context,many:statements.append(statement.lower()))
        report,rows=service.capture(self.db,self.filters())
        self.assertEqual(report.orders.counts['created_in_period'],0)
        self.assertEqual(report.credit.amounts['current_outstanding'],'0.00')
        self.assertEqual(report.unavailable['driver_finance'],'not_enabled')
        self.assertEqual(len(rows),3)
        for statement in statements:
            self.assertTrue(statement.lstrip().startswith(('select','pragma')))
            for forbidden in ('driver_earnings','driver_financial','driver_verification','legacy_document_exempt','order_fulfilment_charges'):
                self.assertNotIn(forbidden,statement)
        self.assertFalse(self.db.dirty);self.assertFalse(self.db.new)

    def test_reversals_current_debt_and_advances_separate(self):
        self.ledger(1,'credit_sale','100.10');self.ledger(2,'repayment','30.05')
        self.ledger(3,'repayment','50',account=2)
        self.ledger(4,'credit_sale','900',account=3)
        self.ledger(5,'reversal','1',reverses=2,stamp='2026-11-02T12:00:00')
        report,rows=service.capture(self.db,self.filters())
        self.assertEqual(report.credit.amounts,dict(credit_sales='1000.10',repayments='50.00',current_outstanding='1000.10',current_advances='50.00'))
        self.assertEqual(report.credit.daily[1]['repayments'],'-30.05')
        own=next(row for row in rows if row.business_id==10)
        self.assertEqual((own.outstanding,own.advances),('100.10','50.00'))
        report,_=service.capture(self.db,self.filters(business_id=20))
        self.assertEqual(report.credit.amounts['current_outstanding'],'900.00')

    def test_sale_reversal_on_its_recorded_day_and_original_outside_period(self):
        self.ledger(1,'credit_sale','123.45',stamp='2026-10-01T00:00:00')
        self.ledger(2,'reversal','1',reverses=1)
        report,_=service.capture(self.db,self.filters())
        self.assertEqual(report.credit.amounts['credit_sales'],'-123.45')
        self.assertEqual(report.credit.amounts['current_outstanding'],'0.00')

    def test_invalid_and_future_ledger_fail_without_zero(self):
        self.ledger(1,'credit_sale','10',stamp='2099-01-01T00:00:00')
        with self.assertRaises(HTTPException) as error:service.capture(self.db,self.filters())
        self.assertEqual(error.exception.status_code,409)

    def test_orders_status_filters_cancellation_and_no_cash_claim(self):
        for ident,status in enumerate(['processing','rejected','cancelled'],1):self.order(ident,status)
        report,_=service.capture(self.db,self.filters())
        self.assertEqual(report.orders.amounts['product_order_total'],'300.00')
        self.assertEqual(report.orders.amounts['non_cancelled_product_total'],'100.00')
        self.assertEqual(report.orders.amounts['cancelled_rejected_product_total'],'200.00')
        self.assertIn('cash_collected',report.unavailable)
        selected,_=service.capture(self.db,self.filters(order_status='cancelled'))
        self.assertEqual(selected.orders.counts['created_in_period'],1)

    def test_delivery_events_not_joined_to_order_or_request_cohort(self):
        self.db.add(DeliveryRequest(delivery_request_id=1,business_id=10,created_by=2,reference='AR-DEL',pickup_area='Fictional',delivery_area='Fictional',status='delivered',created_at=datetime(2026,10,1)))
        self.db.flush();self.db.add(DeliveryAssignment(delivery_request_id=1,driver_user_id=5,assigned_at=datetime(2026,11,1)))
        for ident,status in enumerate(['picked_up','in_transit','delivered'],1):
            self.db.add(DeliveryStatusEvent(event_id=ident,delivery_request_id=1,actor_user_id=5,status=status,occurred_at=datetime(2026,11,2)))
        self.db.commit()
        report,_=service.capture(self.db,self.filters())
        self.assertEqual(report.deliveries.counts['created_in_period'],0)
        self.assertEqual(report.deliveries.counts['assigned_in_period'],1)
        self.assertEqual(report.deliveries.counts['completed_in_period'],1)
        self.assertEqual(report.orders.counts['created_in_period'],0)

    def test_registration_decisions_profiles_not_unique_users(self):
        for user in self.db.scalars(select(User)):user.created_at=datetime(2026,11,2)
        self.db.get(Business,10).created_at=datetime(2026,11,1)
        self.db.add(BusinessApprovalAudit(business_id=10,admin_user_id=1,decision='approve',previous_status='pending',new_status='approved',created_at=datetime(2026,11,3)))
        self.db.commit()
        report,_=service.capture(self.db,self.filters())
        self.assertEqual(report.users.counts['registered_in_period'],4)
        self.assertEqual(report.users.counts['customer'],1)
        self.assertEqual(report.businesses.counts['approved_in_period'],1)
        self.assertEqual(report.businesses.counts['registered_in_period'],1)

    def test_date_end_exclusive_and_range_bounds(self):
        self.order(1);self.db.get(Order,1).created_at=datetime(2026,11,4);self.db.commit()
        report,_=service.capture(self.db,self.filters())
        self.assertEqual(report.orders.counts['created_in_period'],0)
        self.assertEqual(report.reporting_clocks,{'registrations_approvals_credit':'database_wall_clock','orders_deliveries':'UTC'})
        for start,end in [(date(2026,11,4),date(2026,11,3)),(date(2025,1,1),date(2026,1,2))]:
            with self.assertRaises(HTTPException):service.capture(self.db,Filters(start_date=start,end_date=end))
        report,_=service.capture(self.db,Filters())
        self.assertEqual((report.end_date-report.start_date).days,29)

    def test_limits_unknown_business_and_stable_sort(self):
        with patch.object(service,'MAX_BUSINESSES',1):
            with self.assertRaises(HTTPException):service.capture(self.db,self.filters())
        with self.assertRaises(HTTPException) as error:service.capture(self.db,self.filters(business_id=999))
        self.assertEqual(error.exception.status_code,404)
        _,rows=service.capture(self.db,self.filters(sort='outstanding',direction='desc'))
        self.assertEqual([row.business_id for row in rows],[10,20,30])

    def test_bounded_domain_reads_and_snapshot_policy(self):
        database=MagicMock();database.execute.return_value.mappings.return_value=[{} for _ in range(service.MAX_ROWS+1)]
        with self.assertRaises(HTTPException) as error:service.bounded(database,select(User.user_id))
        self.assertEqual(error.exception.status_code,422)
        database=MagicMock();connection=database.connection.return_value;connection.dialect.name='mysql';connection.get_isolation_level.return_value='READ COMMITTED'
        with self.assertRaises(HTTPException) as error:service.capture(database,self.filters())
        self.assertEqual(error.exception.status_code,503);database.execute.assert_not_called()

    def test_finance_flag_never_auto_enables_optional_metrics(self):
        with patch.object(fixture.fixtures.base.config.settings,'DRIVER_FINANCE_ENABLED',True,create=True):
            report,_=service.capture(self.db,self.filters())
        self.assertEqual(report.unavailable['driver_finance'],'not_included_in_core_reports')

    def test_export_numeric_negative_and_untrusted_text_are_distinct(self):
        self.ledger(1,'credit_sale','12.34',stamp='2026-10-01T00:00:00');self.ledger(2,'reversal','1',reverses=1)
        report,rows=service.capture(self.db,self.filters())
        data=render_report_csv(report,rows).decode('utf-8-sig')
        self.assertIn('"-12.34"',data);self.assertNotIn("'-12.34",data)

    def test_expensive_reports_consume_existing_local_budget(self):
        from app.core.rate_limit import LocalLimiter
        from types import SimpleNamespace
        with self.client() as client:
            client.app.state.rate_limit_config=SimpleNamespace(JWT_SECRET_KEY='offline-report-budget',RATE_LIMIT_EXPORT=1)
            client.app.state.rate_limiter=LocalLimiter(60,100)
            first=client.get('/api/v1/admin/reports/export.csv',headers=self.headers())
            self.assertEqual(first.status_code,200)
            self.assertEqual(client.get('/api/v1/admin/reports/export.csv',headers=self.headers()).status_code,429)

    def test_admin_authorization_all_routes_inactive_and_pagination(self):
        paths=['overview','businesses','export.csv','export.pdf']
        with self.client() as client:
            for path in paths:
                url='/api/v1/admin/reports/'+path
                self.assertEqual(client.get(url).status_code,401)
                for ident in (2,4,5):self.assertEqual(client.get(url,headers=self.headers(ident)).status_code,403)
            self.db.get(User,1).account_status='suspended';self.db.commit()
            self.assertEqual(client.get('/api/v1/admin/reports/overview',headers=self.headers()).status_code,403)
            self.db.get(User,1).account_status='active';self.db.commit()
            response=client.get('/api/v1/admin/reports/businesses',params={'limit':1,'offset':1},headers=self.headers())
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['rows'][0]['business_id'],20)
            self.assertEqual(response.headers['cache-control'],'no-store')
            for params in ({'limit':101},{'sort':'password_hash'},{'business_id':0},{'start_date':'bad'}):
                self.assertEqual(client.get('/api/v1/admin/reports/businesses',params=params,headers=self.headers()).status_code,422)

    def test_csv_pdf_consistency_and_formula_safety(self):
        self.ledger(1,'credit_sale','123.45')
        self.db.get(Business,10).business_name='=HYPERLINK("unsafe")';self.db.commit()
        report,rows=service.capture(self.db,self.filters())
        content=render_report_csv(report,rows)
        self.assertTrue(content.startswith(b'\xef\xbb\xbf'))
        parsed=list(csv.reader(StringIO(content.decode('utf-8-sig'))))
        self.assertTrue(any("'=HYPERLINK" in cell for row in parsed for cell in row))
        self.assertTrue(any('123.45' in row for row in parsed))
        import pymupdf
        for language in ('en','ta','si'):
            with pymupdf.open(stream=render_report_pdf(report,rows,language),filetype='pdf') as pdf:
                text=''.join(page.get_text() for page in pdf)
                self.assertIn('123.45',text);self.assertNotIn('VIVA-BUSINESS',text)
                self.assertNotIn('\ufffd',text)

    def test_exports_headers_and_missing_fonts_fail_closed(self):
        with self.client() as client:
            for extension in ('csv','pdf'):
                response=client.get('/api/v1/admin/reports/export.'+extension,params={'start_date':'2026-11-01','end_date':'2026-11-03'},headers=self.headers())
                self.assertEqual(response.status_code,200,response.text[:200])
                self.assertEqual(response.headers['cache-control'],'no-store');self.assertEqual(response.headers['x-content-type-options'],'nosniff')
                self.assertIn('attachment;',response.headers['content-disposition'])
            with patch('app.services.admin_reports_pdf.report_font',side_effect=ReportPDFUnavailable('synthetic')):
                response=client.get('/api/v1/admin/reports/export.pdf',headers=self.headers())
                self.assertEqual(response.status_code,503)


if __name__=='__main__':main(verbosity=2)

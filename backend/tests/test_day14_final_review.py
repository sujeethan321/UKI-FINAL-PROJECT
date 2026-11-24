"""Final shopping/ledger/notification isolation checks on guarded MySQL fixtures."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import func,select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.models import LedgerEntry,Notification,Order,DeliveryRequest,DeliveryAssignment,DeliveryStatusEvent,CreditAccount
from app.services.ledger_service import account_balances,load_ledger_entries
from test_catalogue import shop,api,db,request,product,patch_product
from test_orders import submit,decision
from test_customer_dashboard import entry

def position(s,a):
    return account_balances(load_ledger_entries(s['db'],[a.credit_account_id])).get(a.credit_account_id,Decimal('0.00'))

def test_approved_order_agrees_with_owner_customer_statements_and_existing_repayments(shop):
    profile,account=shop['profile'](shop['business'])
    entry(shop,account,'credit_sale','100.00');entry(shop,account,'repayment','30.00')
    before=[tuple(row) for row in shop['db'].execute(select(LedgerEntry.__table__).where(LedgerEntry.entry_type=='repayment'))]
    order=submit(shop,'credit').json();approved=decision(shop,order['order_id'],'approve')
    assert approved.status_code==200,approved.text
    sale=shop['db'].get(LedgerEntry,approved.json()['credit_sale_id'])
    assert sale.amount==Decimal('250.50') and sale.receipt_number.startswith('CS-') and sale.order_id==order['order_id']
    now=datetime.now(timezone.utc).date();period=dict(start_date=str(now-timedelta(days=1)),end_date=str(now+timedelta(days=1)))
    owner=request(shop,f'/shop-owner/customers/{profile.customer_id}/statement',business_id=shop['business'],**period)
    customer=request(shop,f'/customer/credit-accounts/{account.credit_account_id}/statement',actor='user',**period)
    assert owner.status_code==customer.status_code==200,(owner.text,customer.text)
    assert owner.json()['closing_balance']==customer.json()['closing_balance']=='320.50'
    assert customer.json()['total_credit_sales']=='350.50' and customer.json()['total_repayments']=='30.00'
    for statement in [owner.json(),customer.json()]:
        assert next(t for t in statement['transactions'] if t['entry_id']==sale.entry_id)['reference']==sale.receipt_number
    owned=request(shop,f'/shop-owner/customers/{profile.customer_id}',business_id=shop['business'])
    linked=request(shop,f'/customer/credit-accounts/{account.credit_account_id}',actor='user')
    assert owned.status_code==linked.status_code==200
    assert owned.json()['outstanding_balance']==linked.json()['account']['outstanding_balance']=='320.50'
    assert [tuple(row) for row in shop['db'].execute(select(LedgerEntry.__table__).where(LedgerEntry.entry_type=='repayment'))]==before
    patch_product(shop,shop['pid'],unit_price='999.99',publication_status='archived')
    assert request(shop,f'/customer/orders/{order["order_id"]}',actor='user').json()['total']=='250.50'
    assert position(shop,account)==Decimal('320.50')

@pytest.mark.parametrize('action',['approve','reject'])
def test_order_notifications_exact_recipients_replays_and_protected_reads(shop,action):
    shop['profile'](shop['business']);key=uuid4().hex;order=submit(shop,'credit',key).json()
    submitted=list(shop['db'].scalars(select(Notification).where(Notification.notification_type=='order_submitted')))
    assert len(submitted)==1 and submitted[0].recipient_user_id==shop['owner'].user_id
    assert submit(shop,'credit',key).json()['order_id']==order['order_id']
    assert decision(shop,order['order_id'],action).status_code==200
    count=shop['db'].scalar(select(func.count()).select_from(Notification))
    assert decision(shop,order['order_id'],action).status_code==200
    assert shop['db'].scalar(select(func.count()).select_from(Notification))==count
    event=shop['db'].scalar(select(Notification).where(Notification.notification_type=='order_'+('approved' if action=='approve' else 'rejected')))
    assert event.recipient_user_id==shop['user'].user_id and event.related_entity_id==order['order_id']
    assert request(shop,'/notifications',actor='other').json()['notifications']==[]
    denied=request(shop,f'/notifications/{event.notification_id}/read','patch',{},actor='other')
    assert denied.status_code==404
    owned=request(shop,'/notifications',actor='user').json()['notifications']
    assert any(n['notification_id']==event.notification_id and n['related_entity_type']=='order' for n in owned)
    if action=='reject':assert position(shop,shop['db'].scalar(select(CreditAccount)))==Decimal('0.00')

def test_cash_and_credit_order_events_do_not_create_or_modify_delivery_records(shop):
    _,account=shop['profile'](shop['business'])
    models=[DeliveryRequest,DeliveryAssignment,DeliveryStatusEvent]
    def snapshot():return [shop['db'].execute(select(m.__table__).order_by(*m.__table__.primary_key)).all() for m in models]
    before=snapshot();cash=submit(shop).json()
    assert decision(shop,cash['order_id'],'process').status_code==200
    assert decision(shop,cash['order_id'],'complete').status_code==200
    assert position(shop,account)==Decimal('0.00')
    credit=submit(shop,'credit').json();assert decision(shop,credit['order_id'],'approve').status_code==200
    assert snapshot()==before


def test_order_submission_commit_failure_leaves_no_order_items_or_notifications(shop,monkeypatch):
    def fail(*args,**kwargs):raise SQLAlchemyError('private commit diagnostics')
    pid=product(shop,publication_status='published')['product_id'];shop['pid']=pid
    models=[Order,Notification,LedgerEntry]
    before=[shop['db'].scalar(select(func.count()).select_from(m)) for m in models]
    monkeypatch.setattr(Session,'commit',fail)
    r=submit(shop);assert r.status_code==503 and 'private commit diagnostics' not in r.text
    assert [shop['db'].scalar(select(func.count()).select_from(m)) for m in models]==before

def test_existing_outstanding_balance_limits_submission_and_no_contact_only_linkage(shop):
    _,account=shop['profile'](shop['business']);entry(shop,account,'credit_sale','800.00')
    assert submit(shop,'credit').status_code==409
    assert position(shop,account)==Decimal('800.00')
    account.account_status='closed';shop['db'].flush()
    _,foreign=shop['profile'](shop['business'],owner=shop['other'])
    assert submit(shop,'credit').status_code==409
    assert position(shop,foreign)==Decimal('0.00')

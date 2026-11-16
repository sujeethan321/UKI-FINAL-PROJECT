"""Reproduce D11-T03 first, then T01/T02, against real scoped HTTP/MySQL reads.

Fixture transactions roll back; matching names/phones never establish ownership.
"""
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models import LedgerEntry
from test_customer_dashboard import api, db, make_business, entry

ROOT='/api/v1/customer'
PERIOD={'start_date':'2026-02-01','end_date':'2026-02-28'}


def read(s, user, path, **params):
    return s['client'].get(ROOT+path,params=params,
        headers={'Authorization':'Bearer '+create_access_token(user.user_id)})


def posted(s, account, kind, amount, stamp, author=None):
    ident=entry(s,account,kind,amount)
    row=s['db'].get(LedgerEntry,ident)
    row.recorded_at=datetime.fromisoformat(stamp)
    if author is not None:row.created_by=author.user_id
    s['db'].flush()
    return ident


@pytest.mark.parametrize('reverse',[False,True])
def test_D11_T03_customer_cannot_select_other_financial_records(api,reverse):
    s=api;business=make_business(s['db'])
    a_profile,a=s['profile'](business,s['user'])
    b_profile,b=s['profile'](business,s['other'])
    author=s['make_user']('shop_owner')
    posted(s,a,'credit_sale','100.25','2026-02-01T12:00:00',author)
    posted(s,b,'credit_sale','777.77','2026-02-01T12:00:00',author)
    # User identity, per-business CustomerProfile identity and ledger author
    # represent different concepts even when names/contact fields are identical.
    assert a_profile.customer_name==b_profile.customer_name
    assert a_profile.phone==b_profile.phone
    user,own,target=(s['other'],b,a) if reverse else (s['user'],a,b)
    own_amount='777.77' if reverse else '100.25'
    unknown=9223372036854775807
    for suffix,params in [('',{}),('/statement',PERIOD),('/statement.pdf',PERIOD)]:
        forbidden=read(s,user,f'/credit-accounts/{target.credit_account_id}{suffix}',**params)
        absent=read(s,user,f'/credit-accounts/{unknown}{suffix}',**params)
        assert forbidden.status_code==absent.status_code==404
        assert forbidden.json()==absent.json()=={'detail':'Credit account not found'}
        assert forbidden.headers['cache-control']=='no-store'
    for ident in [target.credit_account_id,unknown]:
        history=read(s,user,'/transactions',credit_account_id=ident,**PERIOD)
        assert history.status_code==404 and history.json()=={'detail':'Credit account not found'}
    # Undeclared identity selectors are ignored, never trusted as authorization.
    forged={'user_id':s['user'].user_id if reverse else s['other'].user_id,
            'customer_id':a_profile.customer_id if reverse else b_profile.customer_id}
    summary=read(s,user,'/dashboard/summary',**forged)
    assert summary.status_code==200 and summary.json()['total_outstanding_balance']==own_amount
    body=s['client'].request('GET',ROOT+'/dashboard/summary',json=forged,
        headers={'Authorization':'Bearer '+create_access_token(user.user_id)})
    assert body.status_code==200 and body.json()==summary.json()
    history=read(s,user,'/transactions',**forged)
    assert history.status_code==200 and history.json()['total']==1
    assert {row['credit_account_id'] for row in history.json()['transactions']}=={own.credit_account_id}
    assert read(s,user,f'/credit-accounts/{own.credit_account_id}').status_code==200
    assert s['client'].post(ROOT+'/transactions',json=forged,
        headers={'Authorization':'Bearer '+create_access_token(user.user_id)}).status_code==405


@pytest.mark.parametrize('repayment,expected',[('0.00','100.25'),('25.10','75.15'),('100.25','0.00')])
def test_D11_T01_exact_balance_opening_closing_and_repayments(api,repayment,expected):
    s=api;business=make_business(s['db']);_,account=s['profile'](business)
    posted(s,account,'credit_sale','40.10','2026-01-31T23:59:59')
    posted(s,account,'credit_sale','60.15','2026-02-01T00:00:00')
    if Decimal(repayment):posted(s,account,'repayment',repayment,'2026-02-28T23:59:59')
    # An unlinked profile with identical contacts must neither inflate balance
    # nor become linked automatically as a financial "repair".
    _,unlinked=s['profile'](business,owner=None)
    posted(s,unlinked,'credit_sale','999.99','2026-02-01T12:00:00')
    summary=read(s,s['user'],'/dashboard/summary')
    detail=read(s,s['user'],f'/credit-accounts/{account.credit_account_id}')
    accounts=read(s,s['user'],'/credit-accounts',page_size=1)
    shops=read(s,s['user'],'/shops')
    statement=read(s,s['user'],f'/credit-accounts/{account.credit_account_id}/statement',**PERIOD)
    assert all(response.status_code==200 for response in [summary,detail,accounts,shops,statement])
    assert summary.json()['total_outstanding_balance']==expected
    assert detail.json()['account']['outstanding_balance']==expected
    assert accounts.json()['credit_accounts'][0]['outstanding_balance']==expected
    assert shops.json()['shops'][0]['outstanding_balance']==expected
    result=statement.json()
    assert result['opening_balance']=='40.10' and result['total_credit_sales']=='60.15'
    assert result['total_repayments']==repayment and result['closing_balance']==expected
    assert Decimal(result['opening_balance'])+Decimal(result['total_credit_sales'])-Decimal(result['total_repayments'])==Decimal(expected)
    assert result['outstanding_balance']==expected
    assert detail.json()['account']['available_credit']==f"{Decimal('1000.00')-Decimal(expected):.2f}"


def test_D11_T02_history_types_dates_and_stable_pages(api):
    s=api;business=make_business(s['db']);_,account=s['profile'](business)
    opening=posted(s,account,'credit_sale','40.10','2026-01-31T23:59:59')
    sale=posted(s,account,'credit_sale','60.15','2026-02-01T00:00:00')
    partial=posted(s,account,'repayment','25.10','2026-02-28T23:59:59')
    full=posted(s,account,'repayment','75.15','2026-02-28T23:59:59')
    before=s['db'].execute(select(LedgerEntry.__table__).order_by(LedgerEntry.entry_id)).all()
    rows=[]
    for page in range(1,4):
        response=read(s,s['user'],'/transactions',credit_account_id=account.credit_account_id,page=page,page_size=1,**PERIOD)
        assert response.status_code==200
        data=response.json()
        assert data['currency']=='LKR' and data['total']==3 and data['page']==page and data['page_size']==1
        rows.extend(data['transactions'])
    assert [row['entry_id'] for row in rows]==[full,partial,sale]
    assert [row['entry_type'] for row in rows]==['repayment','repayment','credit_sale']
    assert [row['amount'] for row in rows]==['75.15','25.10','60.15']
    assert [row['balance_delta'] for row in rows]==['-75.15','-25.10','60.15']
    assert opening not in {row['entry_id'] for row in rows}
    for kind,ids in [('credit_sale',[sale]),('repayment',[full,partial])]:
        response=read(s,s['user'],'/transactions',credit_account_id=account.credit_account_id,entry_type=kind,**PERIOD)
        assert response.status_code==200 and [row['entry_id'] for row in response.json()['transactions']]==ids
    assert read(s,s['user'],'/transactions',credit_account_id=account.credit_account_id,page=4,page_size=1,**PERIOD).json()['transactions']==[]
    assert read(s,s['user'],'/transactions',entry_type='payment').status_code==422
    assert read(s,s['user'],'/transactions',start_date='2026-03-01',end_date='2026-02-01').status_code==422
    assert s['db'].execute(select(LedgerEntry.__table__).order_by(LedgerEntry.entry_id)).all()==before

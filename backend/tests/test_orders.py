"""Real JWT, MySQL and Decimal assertions; rollback fixtures never touch development."""
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from sqlalchemy.exc import SQLAlchemyError
from app.models import Order,OrderItem,LedgerEntry,Notification,Product
from app.services.ledger_service import account_balances,load_ledger_entries
from test_catalogue import shop,api,db,product,category,patch_product,request

def submit(s,method='cash',key=None,**changes):
    if 'pid' not in s:s['pid']=product(s,publication_status='published')['product_id']
    payload=dict(business_id=s['business'],items=[dict(product_id=s['pid'],quantity=2)],payment_method=method,request_key=key or uuid4().hex)
    return request(s,'/customer/orders','post',{**payload,**changes},actor='user')
def decision(s,ident,action,actor='owner',business=None):
    return request(s,f'/shop-owner/orders/{ident}/decision','post',{'action':action},actor=actor,business_id=business or s['business'])
def ledger(s):return list(s['db'].scalars(select(LedgerEntry)))
def test_cash_snapshot_idempotency_and_lifecycle(shop):
    key=uuid4().hex;r=submit(shop,key=key);assert r.status_code==201,r.text
    order=r.json();ident=order['order_id']
    assert order['total']=='250.50' and order['payment_status']=='unpaid' and not ledger(shop)
    assert submit(shop,key=key).json()['order_id']==ident
    assert submit(shop,key=key,items=[dict(product_id=shop['pid'],quantity=1)]).status_code==409
    patch_product(shop,shop['pid'],unit_price='999.99',publication_status='archived')
    assert request(shop,f'/customer/orders/{ident}',actor='user').json()['total']=='250.50'
    assert decision(shop,ident,'approve').status_code==409
    assert decision(shop,ident,'process').json()['status']=='processing'
    assert decision(shop,ident,'process').status_code==200
    assert decision(shop,ident,'cancel').status_code==409
    assert decision(shop,ident,'complete').json()['payment_status']=='unpaid'
    assert decision(shop,ident,'reject').status_code==409
    assert not ledger(shop)
    assert shop['db'].scalar(select(func.count()).select_from(Notification))==3

def test_credit_approval_posts_once_and_statement_matches(shop):
    _,account=shop['profile'](shop['business'])
    r=submit(shop,'credit');assert r.status_code==201,r.text
    ident=r.json()['order_id'];assert not ledger(shop)
    r=decision(shop,ident,'approve');assert r.status_code==200,r.text
    sale=r.json()['credit_sale_id'];entries=ledger(shop)
    assert len(entries)==1 and entries[0].entry_id==sale and entries[0].order_id==ident
    assert entries[0].amount==Decimal('250.50')
    assert account_balances(load_ledger_entries(shop['db'],[account.credit_account_id]))[account.credit_account_id]==Decimal('250.50')
    assert decision(shop,ident,'approve').json()['credit_sale_id']==sale
    assert decision(shop,ident,'reject').status_code==409
    assert decision(shop,ident,'cancel').status_code==409
    assert decision(shop,ident,'process').status_code==200
    assert decision(shop,ident,'complete').status_code==200
    assert decision(shop,ident,'approve').json()['status']=='completed' and len(ledger(shop))==1
    history=request(shop,'/customer/transactions',actor='user').json()['transactions']
    assert history[0]['entry_id']==sale and history[0]['amount']=='250.50'

@pytest.mark.parametrize('action',['reject','cancel'])
def test_credit_rejection_and_submission_cancellation_never_post(shop,action):
    shop['profile'](shop['business']);ident=submit(shop,'credit').json()['order_id']
    assert decision(shop,ident,action).status_code==200
    assert decision(shop,ident,'approve').status_code==409 and not ledger(shop)

@pytest.mark.parametrize('change',['limit','inactive','unlink','suspend','foreign'])
def test_credit_revalidated_at_approval(shop,change):
    profile,account=shop['profile'](shop['business']);ident=submit(shop,'credit').json()['order_id']
    if change=='limit':account.credit_limit=Decimal('1.00')
    if change=='inactive':account.account_status='closed'
    if change=='unlink':profile.user_id=None
    if change=='suspend':shop['user'].account_status='suspended'
    if change=='foreign':account.creditor_business_id=shop['foreign']
    shop['db'].flush()
    assert decision(shop,ident,'approve').status_code in (403,409)
    assert not ledger(shop) and shop['db'].get(Order,ident).status=='submitted'

def test_unlinked_credit_and_ambiguous_accounts_cash_remains_supported(shop):
    assert submit(shop,'credit').status_code==409
    shop['profile'](shop['business']);shop['profile'](shop['business'])
    assert submit(shop,'credit').status_code==409
    assert submit(shop).status_code==201

@pytest.mark.parametrize('changes',[{'quantity':0},{'quantity':100},{'quantity':True},{'quantity':1.5},{'quantity':'2'},{'product_id':True}])
def test_item_validation(shop,changes):
    pid=product(shop,publication_status='published')['product_id']
    assert submit(shop,items=[dict(product_id=pid,quantity=1,**{})|changes]).status_code==422

@pytest.mark.parametrize('changes',[{'total':'0.01'},{'unit_price':'0.01'},{'customer_id':1},{'credit_account_id':1},{'payment_method':'card'},{'items':[]},{'request_key':'short'}])
def test_forbidden_client_authority(shop,changes):assert submit(shop,**changes).status_code==422

@pytest.mark.parametrize('state',['draft','archived','unavailable','category','foreign'])
def test_publication_availability_business_consistency(shop,state):
    changes={'publication_status':'published'}
    if state in ('draft','archived'):changes['publication_status']=state
    if state=='archived':changes['publication_status']='draft'
    if state=='unavailable':changes['availability_status']='unavailable'
    if state=='category':changes['category_id']=category(shop,is_active=False)['category_id'];changes['publication_status']='draft'
    row=product(shop,**changes);shop['pid']=row['product_id']
    if state=='archived':patch_product(shop,shop['pid'],publication_status='archived')
    if state=='category':
        p=shop['db'].get(Product,shop['pid']);p.publication_status='published';shop['db'].flush()
    if state=='foreign':
        assert submit(shop,business_id=shop['foreign']).status_code==409;return
    assert submit(shop).status_code==409

def test_order_isolation_roles_and_pagination(shop):
    ids=[submit(shop).json()['order_id'] for _ in range(3)]
    for actor in ['other','other_owner']:
        assert request(shop,f'/customer/orders/{ids[0]}',actor=actor).status_code in (403,404)
    assert request(shop,f'/shop-owner/orders/{ids[0]}',actor='other_owner',business_id=shop['foreign']).status_code==404
    assert decision(shop,ids[0],'process',actor='other_owner').status_code==404
    for role in ['shop_owner','driver','admin']:
        user=shop['make_user'](role)
        assert request(shop,'/customer/orders','post',{},actor=user).status_code==403
    for role in ['customer','driver','admin']:
        assert decision(shop,ids[0],'process',actor=shop['make_user'](role)).status_code==403
    r=request(shop,'/customer/orders',actor='user',page_size=2).json()
    assert r['total']==3 and len(r['orders'])==2
    assert request(shop,'/customer/orders',actor='other').json()['total']==0
    assert request(shop,'/customer/orders',actor='user',page=0).status_code==422
    assert request(shop,'/customer/orders',actor='user',status='completed').json()['total']==0
    assert shop['client'].get('/api/v1/customer/orders').status_code==401
    assert request(shop,f'/customer/orders/{ids[0]}/decision','post',{'action':'approve'},actor='user').status_code==403
    assert request(shop,f'/customer/orders/{ids[0]}/decision','post',{'action':'cancel'},actor='user').status_code==200
    for secret in ['request_key','request_hash','password_hash','credit_account_id','customer_user_id']:
        assert secret not in str(r)

def test_approval_failure_rolls_back_order_ledger_and_notifications(shop,monkeypatch):
    from app.services import order_service
    shop['profile'](shop['business']);ident=submit(shop,'credit').json()['order_id']
    before=shop['db'].scalar(select(func.count()).select_from(Notification))
    def fail(*args):raise SQLAlchemyError('private diagnostics')
    monkeypatch.setattr(order_service,'notify_event',fail)
    r=decision(shop,ident,'approve');assert r.status_code==503 and 'private diagnostics' not in r.text
    shop['db'].expire_all()
    assert shop['db'].get(Order,ident).status=='submitted' and not ledger(shop)
    assert shop['db'].scalar(select(func.count()).select_from(Notification))==before


def test_manual_sale_cannot_be_adopted_as_order_approval(shop):
    _,account=shop['profile'](shop['business']);order=submit(shop,'credit').json()
    r=request(shop,'/shop-owner/credit-sales','post',dict(customer_id=account.customer_id,amount=order['total'],
        notes='Shopping order '+order['reference'],idempotency_key='order-sale:'+order['reference']),business_id=shop['business'])
    assert r.status_code==201,r.text
    assert decision(shop,order['order_id'],'approve').status_code==409
    row=shop['db'].get(Order,order['order_id']);assert row.status=='submitted' and row.credit_sale_id is None
    assert len(ledger(shop))==1

def test_quote_authoritative_prices_credit_guidance_and_bounds(shop):
    pid=product(shop,publication_status='published')['product_id']
    payload=dict(business_id=shop['business'],items=[dict(product_id=pid,quantity=3)])
    r=request(shop,'/customer/orders/quote','post',payload,actor='user');assert r.status_code==200,r.text
    assert r.json()['total']=='375.75' and not r.json()['credit_available']
    assert 'Cash' in r.json()['credit_guidance']
    assert not ledger(shop)
    assert request(shop,'/customer/orders/quote','post',{**payload,'items':payload['items']*2},actor='user').status_code==422
    assert request(shop,'/customer/orders/quote','post',{**payload,'items':[dict(product_id=pid,quantity=1)]*51},actor='user').status_code==422

def test_expired_order_jwt_is_rejected(shop):
    from datetime import datetime,timedelta,timezone
    import jwt
    from app.core.config import settings
    now=datetime.now(timezone.utc)
    token=jwt.encode(dict(sub=str(shop['user'].user_id),type='access',iat=now-timedelta(hours=2),exp=now-timedelta(hours=1)),settings.JWT_SECRET_KEY,algorithm='HS256')
    r=shop['client'].get('/api/v1/customer/orders',headers={'Authorization':'Bearer '+token})
    assert r.status_code==401

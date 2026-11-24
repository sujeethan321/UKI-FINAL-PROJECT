"""Independent MySQL transactions, exact fixture cleanup and forced row-lock races."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event,Lock
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,delete,text,event
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import engine
from app.core.security import create_access_token
from app.main import app
from app.models import User,Business,BusinessMember,CustomerProfile,CreditAccount,Product,Order,OrderItem,LedgerEntry,Notification

@pytest.fixture
def committed_orders():
    if settings.MYSQL_DATABASE!=engine.url.database or engine.url.database!='lankapex_test_db':raise RuntimeError('Test database required')
    with engine.connect() as c:
        if c.scalar(text('SELECT DATABASE()'))!='lankapex_test_db':raise RuntimeError('Test database required')
    assert not app.dependency_overrides
    users=[];bid=None
    try:
        with Session(engine) as db:
            for role in ['shop_owner','customer']:
                row=User(full_name='Order concurrency fixture',email=uuid4().hex+'@example.com',password_hash='disabled-fixture',platform_role=role,account_status='active');db.add(row);db.flush();users.append(row.user_id)
            b=Business(business_name='Order race '+uuid4().hex,business_type='retail',approval_status='approved');db.add(b);db.flush();bid=b.business_id
            db.add(BusinessMember(business_id=bid,user_id=users[0],business_role='owner',membership_status='active'))
            p=CustomerProfile(business_id=bid,user_id=users[1],customer_name='Order fixture');db.add(p);db.flush()
            a=CreditAccount(customer_id=p.customer_id,creditor_business_id=bid,credit_limit=Decimal('1000.00'),payment_term_days=30,account_status='active');db.add(a)
            product=Product(business_id=bid,name='Race item',unit_price=Decimal('600.00'),publication_status='published',availability_status='available');db.add(product);db.flush();pid=product.product_id;db.commit()
        with TestClient(app) as client:
            yield dict(client=client,bid=bid,pid=pid,owner=users[0],customer=users[1])
    finally:
        with engine.begin() as c:
            if c.scalar(text('SELECT DATABASE()'))!='lankapex_test_db':raise RuntimeError('Test database required')
            if bid:
                orders=list(c.scalars(select(Order.order_id).where(Order.business_id==bid)))
                c.execute(delete(Notification).where(Notification.business_id==bid))
                c.execute(delete(OrderItem).where(OrderItem.order_id.in_(orders)))
                c.execute(delete(Order).where(Order.business_id==bid))
                accounts=list(c.scalars(select(CreditAccount.credit_account_id).where(CreditAccount.creditor_business_id==bid)))
                c.execute(delete(LedgerEntry).where(LedgerEntry.credit_account_id.in_(accounts)))
                c.execute(delete(CreditAccount).where(CreditAccount.creditor_business_id==bid))
                c.execute(delete(CustomerProfile).where(CustomerProfile.business_id==bid))
                c.execute(delete(Product).where(Product.business_id==bid))
                c.execute(delete(BusinessMember).where(BusinessMember.business_id==bid))
                c.execute(delete(Business).where(Business.business_id==bid))
            if users:c.execute(delete(User).where(User.user_id.in_(users)))

def post(ctx,path,payload,owner=False):
    return ctx['client'].post('/api/v1/'+path,params={'business_id':ctx['bid']} if owner else {},json=payload,
        headers={'Authorization':'Bearer '+create_access_token(ctx['owner' if owner else 'customer'])})
def create(ctx,key=None):
    return post(ctx,'customer/orders',dict(business_id=ctx['bid'],items=[dict(product_id=ctx['pid'],quantity=1)],payment_method='credit',request_key=key or uuid4().hex))
def race(ctx,ids,actions):
    ready=Event();mutex=Lock();attempts=0
    def observe(conn,cursor,statement,params,context,many):
        nonlocal attempts
        if 'FROM orders' in statement and 'FOR UPDATE' in statement:
            with mutex:
                attempts+=1
                if attempts>=2:ready.set()
    with engine.connect() as blocker:
        txn=blocker.begin();blocker.execute(select(Order.order_id).where(Order.order_id.in_(ids)).with_for_update()).all()
        event.listen(engine,'before_cursor_execute',observe)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(post,ctx,f'shop-owner/orders/{ident}/decision',{'action':action},True) for ident,action in zip(ids,actions)]
                try:assert ready.wait(20),'Both requests must reach locked orders'
                finally:txn.rollback()
                return [f.result(timeout=30) for f in futures]
        finally:event.remove(engine,'before_cursor_execute',observe)

def test_same_order_concurrent_approval_posts_once(committed_orders):
    c=committed_orders;ident=create(c).json()['order_id'];responses=race(c,[ident,ident],['approve','approve'])
    assert [r.status_code for r in responses]==[200,200]
    assert len({r.json()['credit_sale_id'] for r in responses})==1
    with Session(engine) as db:
        rows=list(db.scalars(select(LedgerEntry).where(LedgerEntry.order_id==ident)));assert len(rows)==1 and rows[0].amount==Decimal('600.00')

def test_two_orders_cannot_exceed_credit_together(committed_orders):
    c=committed_orders;ids=[create(c).json()['order_id'] for _ in range(2)]
    responses=race(c,ids,['approve','approve']);assert sorted(r.status_code for r in responses)==[200,409]

def test_approval_rejection_race_is_terminal(committed_orders):
    c=committed_orders;ident=create(c).json()['order_id'];responses=race(c,[ident,ident],['approve','reject'])
    assert sorted(r.status_code for r in responses)==[200,409]

def test_concurrent_submission_retry_creates_one_order(committed_orders):
    c=committed_orders;key=uuid4().hex
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(lambda _:create(c,key),range(2)))
    assert [r.status_code for r in responses]==[201,201]
    assert len({r.json()['order_id'] for r in responses})==1

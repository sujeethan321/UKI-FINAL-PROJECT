"""Caller owns transaction. No commit occurs before order and ledger both validate."""
from decimal import Decimal
from hashlib import sha256
import json
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select, func
from app.models import Business, User, Product, ProductCategory, CustomerProfile, CreditAccount, LedgerEntry, Order, OrderItem
from app.models.catalogue import utc_now
from app.services.catalogue_service import owner_business
from app.services.ledger_service import load_ledger_entries, account_balances, balance_position, ZERO
from app.services.shop_owner_credit_sale_service import record_credit_sale
from app.schemas.ledger import CreditSaleCreate
from app.services.notification_service import notify_event

MAX_TOTAL = Decimal('999999999999.99')
def current(db, query, shared=True):
    return db.scalar(query.with_for_update(read=shared).execution_options(populate_existing=True))
def actor(db, user_id, role, exclusive=False):
    user = current(db,select(User).where(User.user_id==user_id),not exclusive)
    if user is None or user.platform_role != role or user.account_status != 'active':
        raise HTTPException(403,'Active account with the required role is necessary')
    return user

def shop(db,business_id):
    business = current(db,select(Business).where(Business.business_id==business_id))
    if business is None or business.approval_status != 'approved':
        raise HTTPException(404,'Shop not found')
    return business

def credit(db,user_id,business_id,amount,account_id=None):
    # Link solely through persisted user_id. Multiple eligible accounts are
    # ambiguous; no account is selected from a client identifier or contact data.
    profiles = list(db.scalars(select(CustomerProfile).where(
        CustomerProfile.user_id==user_id,CustomerProfile.business_id==business_id
    ).order_by(CustomerProfile.customer_id).with_for_update(read=True).execution_options(populate_existing=True)))
    ids = [p.customer_id for p in profiles]
    accounts = list(db.scalars(select(CreditAccount).where(
        CreditAccount.customer_id.in_(ids),CreditAccount.creditor_business_id==business_id,
        CreditAccount.account_status=='active'
    ).order_by(CreditAccount.credit_account_id).with_for_update().execution_options(populate_existing=True))) if ids else []
    if account_id is not None:
        accounts = [a for a in accounts if a.credit_account_id==account_id]
    if len(accounts)!=1:
        raise HTTPException(409,'Credit checkout unavailable: ask the shop to verify your linked active account, or choose Cash')
    account=accounts[0]
    balance=account_balances(load_ledger_entries(db,[account.credit_account_id],lock=True)).get(account.credit_account_id,ZERO)
    if amount > balance_position(balance,account.credit_limit)['available_credit']:
        raise HTTPException(409,'Insufficient available credit. Choose Cash or contact the shop')
    return account

def priced_items(db,payload):
    lines=[]
    for item in sorted(payload.items,key=lambda i:i.product_id):
        row=current(db,select(Product).where(Product.product_id==item.product_id,Product.business_id==payload.business_id))
        if row is None or row.publication_status!='published' or row.availability_status!='available':
            raise HTTPException(409,'An item is no longer available from this shop. Review your cart')
        if row.category_id is not None:
            category=current(db,select(ProductCategory).where(ProductCategory.category_id==row.category_id,ProductCategory.business_id==payload.business_id))
            if category is None or not category.is_active:
                raise HTTPException(409,'An item is no longer available from this shop. Review your cart')
        lines.append(dict(product_id=row.product_id,product_name=row.name,quantity=item.quantity,
                          unit_price=row.unit_price,line_total=row.unit_price*item.quantity))
    total=sum((line['line_total'] for line in lines),ZERO)
    if total>MAX_TOTAL:
        raise HTTPException(422,'Order total exceeds the supported limit')
    return lines,total

def line_data(line):
    data={key:(line[key] if isinstance(line,dict) else getattr(line,key)) for key in ('product_id','product_name','quantity','unit_price','line_total')}
    for key in ('unit_price','line_total'): data[key]=f"{data[key]:.2f}"
    return data

def quote(db,user,payload):
    business=shop(db,payload.business_id)
    actor(db,user.user_id,'customer')
    lines,total=priced_items(db,payload)
    eligible=True;guidance='Credit requires Shop Owner approval; no debt is created by submission.'
    try: credit(db,user.user_id,payload.business_id,total)
    except HTTPException as error: eligible=False;guidance=error.detail
    return dict(business_id=business.business_id,business_name=business.business_name,
        items=[line_data(i) for i in lines],subtotal=f'{total:.2f}',total=f'{total:.2f}',
        credit_available=eligible,credit_guidance=guidance)

def response(db,row):
    business=db.get(Business,row.business_id);customer=db.get(User,row.customer_user_id)
    return dict(**{key:getattr(row,key) for key in ('order_id','reference','business_id','payment_method','payment_status','status','credit_sale_id','created_at','updated_at')},
        business_name=business.business_name,customer_name=customer.full_name,
        subtotal=f'{row.subtotal:.2f}',total=f'{row.total:.2f}',
        items=[line_data(i) for i in db.scalars(select(OrderItem).where(OrderItem.order_id==row.order_id).order_by(OrderItem.order_item_id))])

def create(db,user,payload):
    shop(db,payload.business_id)
    actor(db,user.user_id,'customer',exclusive=True) # serialize per-user retry keys
    canonical=dict(business_id=payload.business_id,payment_method=payload.payment_method,
        items=sorted([i.model_dump() for i in payload.items],key=lambda i:i['product_id']))
    digest=sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest()
    existing=current(db,select(Order).where(Order.customer_user_id==user.user_id,Order.request_key==payload.request_key))
    if existing:
        if existing.request_hash!=digest: raise HTTPException(409,'Request key already used for a different order')
        return response(db,existing)
    lines,total=priced_items(db,payload)
    account=credit(db,user.user_id,payload.business_id,total) if payload.payment_method=='credit' else None
    row=Order(reference='ORD-'+uuid4().hex,customer_user_id=user.user_id,business_id=payload.business_id,
        request_key=payload.request_key,request_hash=digest,payment_method=payload.payment_method,
        payment_status='pending' if account else 'unpaid',status='submitted',subtotal=total,total=total,
        credit_account_id=account.credit_account_id if account else None)
    db.add(row);db.flush()
    db.add_all([OrderItem(order_id=row.order_id,**line) for line in lines]);db.flush()
    notify_event(db,'order_submitted',row.order_id)
    return response(db,row)

def scoped(db,user,order_id,business_id=None,lock=False):
    if business_id is not None:
        owner_business(db,user,business_id)
    query=select(Order).where(Order.order_id==order_id)
    query=query.where(Order.business_id==business_id) if business_id is not None else query.where(Order.customer_user_id==user.user_id)
    row=current(db,query,False) if lock else db.scalar(query)
    if row is None: raise HTTPException(404,'Order not found')
    return row

def detail(db,user,order_id,business_id=None):
    return response(db,scoped(db,user,order_id,business_id))

def listing(db,user,page,size,status=None,business_id=None):
    if business_id is not None: owner_business(db,user,business_id)
    query=select(Order).where(Order.business_id==business_id) if business_id is not None else select(Order).where(Order.customer_user_id==user.user_id)
    if status is not None:query=query.where(Order.status==status)
    count=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.scalars(query.order_by(Order.order_id.desc()).offset((page-1)*size).limit(size))
    return dict(page=page,page_size=size,total=count,orders=[response(db,r) for r in rows])

def decide(db,user,order_id,action,business_id=None):
    preview=scoped(db,user,order_id,business_id)
    # Same lock order as submission: user before order before credit account.
    current(db,select(User).where(User.user_id==preview.customer_user_id))
    row=scoped(db,user,order_id,business_id,lock=True)
    if business_id is None and action!='cancel':raise HTTPException(403,'Customers may only cancel submitted orders')
    targets={'approve':'approved','reject':'rejected','process':'processing','complete':'completed','cancel':'cancelled'}
    target=targets[action]
    # Replays preserve history and never post again, including after processing.
    if row.status==target or (action=='approve' and row.credit_sale_id is not None):return response(db,row)
    allowed={'submitted':{'reject','cancel','approve'} if row.payment_method=='credit' else {'reject','cancel','process'},
             'approved':{'process'},'processing':{'complete'}}
    if action not in allowed.get(row.status,set()):raise HTTPException(409,'Order transition is not permitted')
    if action=='approve':
        actor(db,row.customer_user_id,'customer')
        account=credit(db,row.customer_user_id,row.business_id,row.total,row.credit_account_id)
        sale=record_credit_sale(db,row.business_id,user.user_id,CreditSaleCreate(
            customer_id=account.customer_id,amount=row.total,notes='Shopping order '+row.reference,
            idempotency_key='order-sale:'+row.reference))
        if sale.replayed:
            # A successful atomic order approval already has credit_sale_id.
            # Never adopt an unrelated manual sale using the reserved key.
            raise HTTPException(409,'Credit posting reference conflict; review the existing financial transaction')
        entry=db.get(LedgerEntry,sale.entry_id)
        if entry.order_id not in (None,row.order_id): raise HTTPException(409,'Order credit reference conflict')
        entry.order_id=row.order_id
        row.credit_sale_id=entry.entry_id;row.payment_status='posted'
    row.status=target;row.updated_at=utc_now();db.flush()
    notify_event(db,'order_'+target,row.order_id)
    return response(db,row)

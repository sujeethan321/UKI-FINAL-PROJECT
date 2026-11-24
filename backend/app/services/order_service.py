# Purpose: Implement order operations behind the HTTP layer so related business rules are shared by their callers.
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
from app.models.driver_finance import OrderFulfilmentCharge
from app.services.driver_fee_pricing import commitment, POLICY
from app.services.driver_finance_rollout import enabled as finance_enabled,require_ready

from app.services import order_address_service as destinations
from app.services import customer_address_rollout as address_rollout

MAX_TOTAL = Decimal('999999999999.99')

# Check new order plan and stop callers when the required conditions are not met.
def require_new_order_plan(db,business_id):
    from app.services.subscription_service import require_business_feature
    try:require_business_feature(db,business_id,'orders')
    except HTTPException as error:
        if error.status_code!=403:raise
        raise HTTPException(403,'This shop is not accepting new shopping orders on its current plan. Choose another shop or contact its owner.') from None
# Resolve current using a row lock so the caller can coordinate concurrent changes.
def current(db, query, shared=True):
    return db.scalar(query.with_for_update(read=shared).execution_options(populate_existing=True))
# Reload the user with the required role so the operation uses current account state.
def actor(db, user_id, role, exclusive=False):
    user = current(db,select(User).where(User.user_id==user_id),not exclusive)
    if user is None or user.platform_role != role or user.account_status != 'active':
        raise HTTPException(403,'Active account with the required role is necessary')
    return user

# Require an approved business before an order operation can use its catalogue.
def shop(db,business_id):
    business = current(db,select(Business).where(Business.business_id==business_id))
    if business is None or business.approval_status != 'approved':
        raise HTTPException(404,'Shop not found')
    return business

# Resolve credit using a row lock so the caller can coordinate concurrent changes.
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

# Load authoritative product prices and validate requested order quantities before computing totals.
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

# Shape line fields for the response contract.
def line_data(line):
    data={key:(line[key] if isinstance(line,dict) else getattr(line,key)) for key in ('product_id','product_name','quantity','unit_price','line_total')}
    for key in ('unit_price','line_total'): data[key]=f"{data[key]:.2f}"
    return data

# Price the order against current catalogue and credit state without recording a new order.
def quote(db,user,payload):
    from app.services.delivery_estimate_service import delivery_estimate
    actor(db,user.user_id,'customer',exclusive=address_rollout.enabled(True))
    accepted=destinations.acceptance(db,user,payload)
    business=shop(db,payload.business_id)
    require_new_order_plan(db,payload.business_id)
    lines,total=priced_items(db,payload)
    eligible=True;guidance='Credit requires Shop Owner approval; no debt is created by submission.'
    try: credit(db,user.user_id,payload.business_id,total)
    except HTTPException as error: eligible=False;guidance=error.detail
    extra={}
    if finance_enabled():require_ready(db)
    if finance_enabled() and payload.fulfilment_mode:
        extra,token=commitment(user.user_id,payload.business_id,lines,total,payload.fulfilment_mode,destination=accepted['binding'] if accepted else None)
        extra['quote_token']=token
    return dict(business_id=business.business_id,business_name=business.business_name,
        items=[line_data(i) for i in lines],subtotal=f'{total:.2f}',total=f'{total:.2f}',
        credit_available=eligible,credit_guidance=guidance,finance_enabled=finance_enabled(),
        address_checkout_enabled=address_rollout.enabled(True),
        address_id=accepted['binding'][0] if accepted else None,address_version=accepted['binding'][1] if accepted else None,
        destination=destinations.destination(accepted['row']) if accepted else None,**delivery_estimate(total),**extra)

# Shape order fields for the response contract.
def order_data(row,business_name,customer_name,items,charge=None):
    return dict(**{key:getattr(row,key) for key in ('order_id','reference','business_id','payment_method','payment_status','status','credit_sale_id','created_at','updated_at')},
        business_name=business_name,customer_name=customer_name,
        subtotal=f'{row.subtotal:.2f}',total=f'{row.total:.2f}',
        items=[line_data(i) for i in items],
        fulfilment_mode=charge.mode if charge else None,
        delivery_fee=f'{charge.delivery_fee:.2f}' if charge else None,
        customer_total=f'{charge.customer_total:.2f}' if charge else None,
        fee_policy=charge.policy_version if charge else None,finance_enabled=finance_enabled())

# Query response data for the order workflow.
def response(db,row):
    if finance_enabled():require_ready(db)
    business=db.get(Business,row.business_id);customer=db.get(User,row.customer_user_id)
    result=order_data(row,business.business_name,customer.full_name,
        db.scalars(select(OrderItem).where(OrderItem.order_id==row.order_id).order_by(OrderItem.order_item_id)),
        db.get(OrderFulfilmentCharge,row.order_id) if finance_enabled() else None)
    result['destination']=destinations.snapshot_projection(db,row.order_id)
    return result

# Create the scoped order or delivery through its validation, locking, and existing-record checks.
def create(db,user,payload):
    actor(db,user.user_id,'customer',exclusive=True) # serialize per-user retry keys
    canonical=dict(business_id=payload.business_id,payment_method=payload.payment_method,
        items=sorted([i.model_dump() for i in payload.items],key=lambda i:i['product_id']))
    if payload.fulfilment_mode is not None:
        canonical.update(fulfilment_mode=payload.fulfilment_mode,quote_token=payload.quote_token)
    if payload.address_id is not None or payload.address_version is not None:
        canonical.update(address_id=payload.address_id,address_version=payload.address_version)
    digest=sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest()
    existing=current(db,select(Order).where(Order.customer_user_id==user.user_id,Order.request_key==payload.request_key))
    if existing:
        if existing.request_hash!=digest: raise HTTPException(409,'Request key already used for a different order')
        return response(db,existing)
    accepted=destinations.acceptance(db,user,payload)
    shop(db,payload.business_id)
    require_new_order_plan(db,payload.business_id)
    lines,total=priced_items(db,payload)
    charge=None
    if finance_enabled():
        require_ready(db)
        if not payload.fulfilment_mode or not payload.quote_token:
            raise HTTPException(422,'Select Delivery or Pickup and confirm the current quote')
        charge,_=commitment(user.user_id,payload.business_id,lines,total,payload.fulfilment_mode,payload.quote_token,destination=accepted['binding'] if accepted else None)
    elif payload.fulfilment_mode or payload.quote_token:
        raise HTTPException(503,'Driver finance is not enabled; refresh checkout before confirming an order')
    account=credit(db,user.user_id,payload.business_id,total) if payload.payment_method=='credit' else None
    row=Order(reference='ORD-'+uuid4().hex,customer_user_id=user.user_id,business_id=payload.business_id,
        request_key=payload.request_key,request_hash=digest,payment_method=payload.payment_method,
        payment_status='pending' if account else 'unpaid',status='submitted',subtotal=total,total=total,
        credit_account_id=account.credit_account_id if account else None)
    db.add(row);db.flush()
    if charge is not None:
        db.add(OrderFulfilmentCharge(order_id=row.order_id,mode=payload.fulfilment_mode,
            product_subtotal=total,delivery_fee=Decimal(charge['delivery_fee']),customer_total=Decimal(charge['customer_total']),
            fee_rate=Decimal('0.03') if payload.fulfilment_mode=='delivery' else Decimal('0'),policy_version=POLICY))
    destinations.persist(db,row,accepted)
    db.add_all([OrderItem(order_id=row.order_id,**line) for line in lines]);db.flush()
    notify_event(db,'order_submitted',row.order_id)
    return response(db,row)

# Query scoped data for the order workflow.
def scoped(db,user,order_id,business_id=None,lock=False):
    if business_id is not None:
        owner_business(db,user,business_id)
    query=select(Order).where(Order.order_id==order_id)
    query=query.where(Order.business_id==business_id) if business_id is not None else query.where(Order.customer_user_id==user.user_id)
    row=current(db,query,False) if lock else db.scalar(query)
    if row is None: raise HTTPException(404,'Order not found')
    return row

# Return the requested order only after the service resolves its access scope.
def detail(db,user,order_id,business_id=None):
    return response(db,scoped(db,user,order_id,business_id))

# Query listing data for the order workflow.
def listing(db,user,page,size,status=None,business_id=None):
    if business_id is not None: owner_business(db,user,business_id)
    if finance_enabled():require_ready(db)
    query=select(Order).where(Order.business_id==business_id) if business_id is not None else select(Order).where(Order.customer_user_id==user.user_id)
    if status is not None:query=query.where(Order.status==status)
    count=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=db.execute(query.add_columns(Business.business_name,User.full_name).join(
        Business,Business.business_id==Order.business_id).join(User,User.user_id==Order.customer_user_id
        ).order_by(Order.order_id.desc()).offset((page-1)*size).limit(size)).all()
    items={row.order_id:[] for row,_,_ in rows}
    if items:
        for item in db.scalars(select(OrderItem).where(OrderItem.order_id.in_(items)).order_by(OrderItem.order_item_id)):
            items[item.order_id].append(item)
    charges={c.order_id:c for c in db.scalars(select(OrderFulfilmentCharge).where(OrderFulfilmentCharge.order_id.in_(items)))} if items and finance_enabled() else {}
    saved={}
    if items and address_rollout.enabled(True):
        address_rollout.require_ready(db,True)
        from app.models.order_address import OrderDeliveryAddress
        saved={r.order_id:destinations.destination(r) for r in db.scalars(select(OrderDeliveryAddress).where(OrderDeliveryAddress.order_id.in_(items)))}
    return dict(page=page,page_size=size,total=count,orders=[
        dict(**order_data(row,business_name,customer_name,items[row.order_id],charges.get(row.order_id)),destination=saved.get(row.order_id)) for row,business_name,customer_name in rows])

# Lock the scoped order before applying the requested order decision.
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
    if row.status=='submitted' and action in {'approve','process'}:
        from app.services.subscription_service import require_business_feature
        require_business_feature(db,row.business_id,'orders')
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

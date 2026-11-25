# Purpose: Accrue and report driver fees and append authorized collection or settlement events without a platform payout workflow.
"""Direct-to-Driver pilot. No platform payouts, credit postings or external calls."""
from decimal import Decimal
from datetime import timedelta
from app.models.delivery import utc_now
from hashlib import sha256
import json
from fastapi import HTTPException
from sqlalchemy import select
from app.models import Order, User
from app.models.driver_finance import OrderFulfilmentCharge, DriverEarning, DriverFeeCollection, DriverSettlementEvent, DriverFinancialAudit
from app.services.driver_service import actor
from app.services.driver_finance_rollout import enabled,require_ready
from app.services.driver_finance_states import check_transition

MAX_EVENTS=10000


# Limit the result set before building financial history so interactive requests cannot allocate unbounded records.
def bounded(db, query):
    rows=list(db.scalars(query.limit(MAX_EVENTS+1)))
    if len(rows)>MAX_EVENTS:raise HTTPException(422,'Financial history exceeds the interactive limit')
    return rows


# Append an audit record that associates the driver-finance action with its actor and originating event.
def audit(db,user_id,earning,action,reference):
    db.add(DriverFinancialAudit(actor_user_id=user_id,earning_id=earning.earning_id,action=action,
        accrual_driver_id=user_id if action=='accrued' else None,
        collection_id=reference if action in ('declared','exception') else None,
        settlement_event_id=reference if action not in ('accrued','declared','exception') else None))


# Create the immutable driver earning associated with the completed delivery through the service consistency checks.
def accrue(db,delivery,assignment,event):
    if not enabled():return
    require_ready(db)
    order=db.scalar(select(Order).where(Order.delivery_request_id==delivery.delivery_request_id,Order.business_id==delivery.business_id)
        .with_for_update(read=True).execution_options(populate_existing=True))
    if order is None:return  # Standalone and historical jobs are not repriced.
    charge=db.scalar(select(OrderFulfilmentCharge).where(OrderFulfilmentCharge.order_id==order.order_id)
        .with_for_update(read=True).execution_options(populate_existing=True))
    if charge is None:return
    if (charge.mode!='delivery' or charge.product_subtotal!=order.subtotal or order.total!=order.subtotal
            or assignment.driver_user_id!=event.actor_user_id or event.status!='delivered' or delivery.status!='delivered'
            or assignment.delivery_request_id!=delivery.delivery_request_id or event.delivery_request_id!=delivery.delivery_request_id):
        raise HTTPException(409,'Delivery charge and completion cannot be reconciled')
    if db.scalar(select(DriverEarning).where(DriverEarning.delivery_request_id==delivery.delivery_request_id)):
        raise HTTPException(409,'Delivery already has an earning; refresh recorded history')
    earning=DriverEarning(order_id=order.order_id,delivery_request_id=delivery.delivery_request_id,
        assignment_id=assignment.assignment_id,completion_event_id=event.event_id,
        driver_user_id=assignment.driver_user_id,amount=charge.delivery_fee)
    db.add(earning);db.flush();audit(db,assignment.driver_user_id,earning,'accrued',earning.earning_id)


# Derive financial status from ordered immutable events and expose private evidence only for the administrative view.
def view(earning,collections,settlements,private=False):
    status='pending'
    if any(c.kind=='declared' for c in collections):status='collection_declared'
    if any(c.kind=='exception' for c in collections):status='exception_review'
    settlements=sorted(settlements,key=lambda e:e.sequence_no)
    if [e.sequence_no for e in settlements]!=list(range(1,len(settlements)+1)):
        raise HTTPException(409,'Financial event sequence is inconsistent; operator review required')
    verified=False
    for entry in settlements:
        check_transition(status,entry.kind,verified)
        status={'direct_settled':'directly_settled','disputed':'disputed','reversed':'refund_pending','refund_confirmed':'refund_confirmed'}[entry.kind]
        verified=verified or entry.kind=='direct_settled'
    kinds={e.kind for e in settlements}
    if earning.amount==0:status='no_fee_due'
    data=dict(earning_id=earning.earning_id,driver_user_id=earning.driver_user_id,delivery_request_id=earning.delivery_request_id,
        order_id=earning.order_id,amount=f'{earning.amount:.2f}',currency='LKR',created_at=earning.created_at,
        status=status,collection_verified='direct_settled' in kinds,
        directly_settled='direct_settled' in kinds and not kinds.intersection({'disputed','reversed','refund_confirmed'}),
        platform_payout_supported=False,
        collections=[dict(collection_id=c.collection_id,kind=c.kind,amount=f'{c.amount:.2f}',created_at=c.created_at,
                          **({'evidence':c.evidence,'actor_user_id':c.actor_user_id} if private else {})) for c in collections],
        settlement_events=[dict(event_id=e.event_id,kind=e.kind,sequence_no=e.sequence_no,amount=f'{e.amount:.2f}',created_at=e.created_at,
                                **({'evidence':e.evidence,'actor_user_id':e.actor_user_id} if private else {})) for e in settlements])
    return data


# Query history data for the driver finance workflow.
def history(db,user,page=1,page_size=20,driver_id=None,period='month'):
    actor(db,user.user_id,'admin' if driver_id is not None else 'driver')
    require_ready(db)
    ident=driver_id if driver_id is not None else user.user_id
    if driver_id is not None and db.scalar(select(User.user_id).where(User.user_id==ident,User.platform_role=='driver')) is None:
        raise HTTPException(404,'Driver not found')
    earnings=bounded(db,select(DriverEarning).where(DriverEarning.driver_user_id==ident).order_by(DriverEarning.created_at.desc(),DriverEarning.earning_id))
    ids=[e.earning_id for e in earnings]
    collections=bounded(db,select(DriverFeeCollection).where(DriverFeeCollection.earning_id.in_(ids)).order_by(DriverFeeCollection.created_at,DriverFeeCollection.collection_id)) if ids else []
    settlements=bounded(db,select(DriverSettlementEvent).where(DriverSettlementEvent.earning_id.in_(ids)).order_by(DriverSettlementEvent.created_at,DriverSettlementEvent.event_id)) if ids else []
    by_collection={i:[] for i in ids};by_settlement={i:[] for i in ids}
    for row in collections:by_collection[row.earning_id].append(row)
    for row in settlements:by_settlement[row.earning_id].append(row)
    rows=[view(e,by_collection[e.earning_id],by_settlement[e.earning_id],private=driver_id is not None) for e in earnings]
    sums={key:Decimal('0.00') for key in ('pending','declared','directly_settled','review','total_earned')}
    for row in rows:
        amount=Decimal(row['amount']);sums['total_earned']+=amount
        sums['directly_settled' if row['directly_settled'] else 'pending' if row['status']=='pending' else
             'declared' if row['status']=='collection_declared' else 'review']+=amount
    today=utc_now().date();days={'day':1,'week':7,'month':30}[period]
    daily={today-timedelta(days=i):Decimal('0.00') for i in reversed(range(days))}
    for earning in earnings:
        if earning.created_at.date() in daily:daily[earning.created_at.date()]+=earning.amount
    return dict(driver_user_id=ident,currency='LKR',total=len(rows),page=page,page_size=page_size,
        period=period,reporting_clock='UTC',daily=[dict(date=d.isoformat(),earned=f'{v:.2f}') for d,v in daily.items()],
        summary={**{k:f'{v:.2f}' for k,v in sums.items()},'available':'0.00','platform_paid':'0.00',
                 'platform_payout_supported':False},earnings=rows[(page-1)*page_size:page*page_size])


# Resolve operation using a row lock so the caller can coordinate concurrent changes.
def operation(db,user,earning_id,payload,admin=False):
    actor(db,user.user_id,'admin' if admin else 'driver',lock=True)
    require_ready(db)
    query=select(DriverEarning).where(DriverEarning.earning_id==earning_id)
    if not admin:query=query.where(DriverEarning.driver_user_id==user.user_id)
    earning=db.scalar(query.with_for_update().execution_options(populate_existing=True))
    if earning is None:raise HTTPException(404,'Earning not found')
    if earning.amount==0:raise HTTPException(409,'No collection or payout is due for a zero fee')
    # Verification must come from a different actor than the earning's driver, even if the caller has an Admin role.
    if admin and user.user_id==earning.driver_user_id:raise HTTPException(403,'Independent Administrator verification is required')
    collections=bounded(db,select(DriverFeeCollection).where(DriverFeeCollection.earning_id==earning_id).with_for_update().execution_options(populate_existing=True))
    events=bounded(db,select(DriverSettlementEvent).where(DriverSettlementEvent.earning_id==earning_id).with_for_update().execution_options(populate_existing=True))
    cls=DriverSettlementEvent if admin else DriverFeeCollection
    digest=sha256(json.dumps([earning_id,payload.model_dump(mode='json')],sort_keys=True).encode()).hexdigest()
    previous=db.scalar(select(cls).where(cls.actor_user_id==user.user_id,cls.request_key==payload.request_key).with_for_update().execution_options(populate_existing=True))
    # Reusing a request key confirms the original operation only when every hashed input still matches.
    if previous:
        if previous.request_hash!=digest:raise HTTPException(409,'Request key conflicts with a different financial operation')
        return view(earning,collections,events,private=admin)
    # Rebuild the current state from locked events before checking whether this next transition is permitted.
    current=view(earning,collections,events)
    check_transition(current['status'],payload.kind,current['collection_verified'])
    if not admin:
        if current['status'] not in ('pending','collection_declared') or events:
            raise HTTPException(409,'Collection requires Administrator exception review')
        if payload.kind=='declared' and (payload.amount!=earning.amount or any(c.kind=='declared' for c in collections)):
            raise HTTPException(409,'Only one full collection declaration is supported; report an exception for partial or disputed collection')
        if payload.amount>earning.amount:raise HTTPException(422,'Collection exceeds the recorded fee')
        row=DriverFeeCollection(earning_id=earning_id,actor_user_id=user.user_id,kind=payload.kind,
            declaration_slot=1 if payload.kind=='declared' else None,declared_amount=payload.amount if payload.kind=='declared' else None,
            amount=payload.amount,evidence=payload.evidence,
            request_key=payload.request_key,request_hash=digest)
    else:
        if payload.kind=='direct_settled':
            declaration=next((c for c in collections if c.collection_id==str(payload.collection_id) and c.kind=='declared'),None)
            if current['status']!='collection_declared' or events or declaration is None or declaration.amount!=earning.amount or declaration.actor_user_id==user.user_id:
                raise HTTPException(409,'An undisputed full Driver declaration and independent evidence are required')
        else:
            if payload.kind=='refund_confirmed' and not any(e.kind=='direct_settled' for e in events):
                raise HTTPException(409,'No verified direct settlement exists to refund')
            if any(e.kind==payload.kind for e in events):raise HTTPException(409,'Adjustment already recorded; review existing history')
        row=DriverSettlementEvent(earning_id=earning_id,collection_id=str(payload.collection_id) if payload.kind=='direct_settled' else None,
            collection_kind='declared' if payload.kind=='direct_settled' else None,
            sequence_no=len(events)+1,previous_sequence_no=len(events) or None,
            actor_user_id=user.user_id,kind=payload.kind,settlement_slot=1 if payload.kind=='direct_settled' else None,
            amount=earning.amount,evidence=payload.evidence,request_key=payload.request_key,request_hash=digest)
    db.add(row);db.flush();audit(db,user.user_id,earning,row.kind,row.event_id if admin else row.collection_id)
    return view(earning,collections if admin else [*collections,row],[*events,row] if admin else events,private=admin)

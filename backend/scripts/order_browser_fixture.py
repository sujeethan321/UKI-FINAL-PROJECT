"""Guarded order-browser extension of the exact catalogue fixture lifecycle."""
import json
import sys
from decimal import Decimal
from pathlib import Path
from sqlalchemy import select,delete,text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import engine
from app.models import Business,User,CustomerProfile,CreditAccount,Order,OrderItem,LedgerEntry,Notification
from catalogue_browser_fixture import main as catalogue_main,require

def main():
    require(settings.MYSQL_DATABASE==engine.url.database=='lankapex_test_db','Test database required')
    with engine.connect() as c:require(c.scalar(text('SELECT DATABASE()'))=='lankapex_test_db','Actual test database required')
    target=Path(__file__).resolve().parents[2]/'.server-logs/day14-catalogue-fixture.json'
    action=sys.argv[1]
    if action=='seed':catalogue_main()
    data=json.loads(target.read_text())
    require(data.get('database')=='lankapex_test_db' and not data.get('cleaned'),'Active fixture required')
    with Session(engine) as db:
        for index,bid in enumerate(data['businesses']):
            require(db.get(Business,bid).business_name==f'Catalogue browser {index} '+data['nonce'],'Business mismatch')
        for uid in data['users']:require(db.get(User,uid).email.startswith('catalogue-browser-'+data['nonce']+'-'),'User mismatch')
        if action=='seed':
            p=CustomerProfile(business_id=data['businesses'][0],user_id=data['users'][1],customer_name='Order browser customer');db.add(p);db.flush()
            db.add(CreditAccount(creditor_business_id=p.business_id,customer_id=p.customer_id,credit_limit=Decimal('1000.00'),payment_term_days=30,account_status='active'));db.commit();print('Linked test-only browser credit account');return
        require(action=='cleanup','Unsupported action')
        bids=data['businesses'];ids=list(db.scalars(select(Order.order_id).where(Order.business_id.in_(bids))))
        db.execute(delete(Notification).where(Notification.business_id.in_(bids)))
        db.execute(delete(OrderItem).where(OrderItem.order_id.in_(ids)))
        db.execute(delete(Order).where(Order.business_id.in_(bids)))
        accounts=list(db.scalars(select(CreditAccount.credit_account_id).where(CreditAccount.creditor_business_id.in_(bids))))
        db.execute(delete(LedgerEntry).where(LedgerEntry.credit_account_id.in_(accounts)))
        db.execute(delete(CreditAccount).where(CreditAccount.credit_account_id.in_(accounts)))
        db.execute(delete(CustomerProfile).where(CustomerProfile.business_id.in_(bids)));db.commit()
    catalogue_main()
if __name__=='__main__':main()

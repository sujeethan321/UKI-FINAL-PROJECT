"""Exact test-only catalogue browser fixtures; never use development data."""
import argparse
import json
from pathlib import Path
from uuid import uuid4
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import engine
from app.core.security import create_access_token
from app.models import User, Business, BusinessMember, Product, ProductCategory


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['seed','cleanup'])
    action=parser.parse_args().action
    require(settings.MYSQL_DATABASE==engine.url.database=='lankapex_test_db','Catalogue browser fixtures require lankapex_test_db')
    with engine.connect() as c:
        require(c.scalar(text('SELECT DATABASE()'))=='lankapex_test_db','Actual database must be lankapex_test_db')
    target=Path(__file__).resolve().parents[2]/'.server-logs/day14-catalogue-fixture.json'
    target.parent.mkdir(exist_ok=True)
    if action=='seed':
        require(not target.exists() or json.loads(target.read_text()).get('cleaned') is True,'Clean the previous fixture first')
        nonce=uuid4().hex
        with Session(engine) as session:
            users=[];businesses=[]
            for index,role in enumerate(['shop_owner','customer','shop_owner']):
                user=User(full_name='Catalogue Browser '+role,email=f'catalogue-browser-{nonce}-{index}@example.com',
                    password_hash='test-only-disabled-login',platform_role=role,account_status='active',preferred_language='en')
                session.add(user);session.flush();users.append(user.user_id)
            for index in range(3):
                business=Business(business_name=f'Catalogue browser {index} {nonce}',business_type='retail',approval_status='approved')
                session.add(business);session.flush();businesses.append(business.business_id)
                session.add(BusinessMember(business_id=business.business_id,user_id=users[0] if index<2 else users[2],business_role='owner',membership_status='active'))
            session.flush()
            data=dict(database='lankapex_test_db',nonce=nonce,users=users,businesses=businesses,
                ownerToken=create_access_token(users[0]),customerToken=create_access_token(users[1]),foreignToken=create_access_token(users[2]))
            target.write_text(json.dumps(data),encoding='utf-8');session.commit()
        print('Created unique catalogue browser identities; no products seeded')
        return
    data=json.loads(target.read_text());require(data.get('database')=='lankapex_test_db' and not data.get('cleaned'),'No active catalogue fixture')
    with Session(engine) as session:
        for index,ident in enumerate(data['businesses']):
            row=session.get(Business,ident)
            require(row is not None and row.business_name==f'Catalogue browser {index} '+data['nonce'],'Business identity mismatch')
        for ident in data['users']:
            row=session.get(User,ident);require(row is not None and row.email.startswith('catalogue-browser-'+data['nonce']+'-'),'User identity mismatch')
        session.execute(delete(Product).where(Product.business_id.in_(data['businesses'])))
        session.execute(delete(ProductCategory).where(ProductCategory.business_id.in_(data['businesses'])))
        session.execute(delete(BusinessMember).where(BusinessMember.business_id.in_(data['businesses']),BusinessMember.user_id.in_(data['users'])))
        session.execute(delete(Business).where(Business.business_id.in_(data['businesses'])))
        session.execute(delete(User).where(User.user_id.in_(data['users'])));session.commit()
    target.write_text(json.dumps(dict(database='lankapex_test_db',cleaned=True)),encoding='utf-8')
    print('Cleaned exact catalogue fixtures and removed local tokens')


if __name__=='__main__':
    main()

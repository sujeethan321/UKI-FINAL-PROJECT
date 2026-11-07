"""Real JWT/HTTP/MySQL catalogue checks using the guarded rollback fixture."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models import (Business, BusinessMember, CreditAccount, LedgerEntry, Notification,
    PaymentReminder, Product, ProductCategory, DeliveryRequest, DeliveryAssignment, DeliveryStatusEvent)
from test_customer_dashboard import api, db, make_business, entry


@pytest.fixture
def shop(api):
    owner = api['make_user']('shop_owner')
    other = api['make_user']('shop_owner')
    business = make_business(api['db'])
    foreign = make_business(api['db'])
    for user, business_id in [(owner, business), (other, foreign)]:
        api['db'].add(BusinessMember(user_id=user.user_id, business_id=business_id,
            membership_status='active', business_role='owner'))
    api['db'].flush()
    api.update(owner=owner, other_owner=other, business=business, foreign=foreign)
    return api


def request(shop, path, method='get', payload=None, actor='owner', **params):
    user = shop[actor] if isinstance(actor, str) else actor
    return getattr(shop['client'], method)('/api/v1' + path,
        headers={'Authorization': 'Bearer ' + create_access_token(user.user_id)}, params=params,
        **({'json': payload} if payload is not None else {}))


def category(shop, name='Groceries', **overrides):
    result = request(shop, '/shop-owner/categories', 'post', {'name': name, **overrides}, business_id=shop['business'])
    assert result.status_code == 201, result.text
    return result.json()


def product(shop, **overrides):
    result = request(shop, '/shop-owner/products', 'post',
        {'name': 'Rice', 'unit_price': '125.25', **overrides}, business_id=shop['business'])
    assert result.status_code == 201, result.text
    return result.json()


def public(shop, suffix='/products', **params):
    return request(shop, f'/customer/catalogue/shops/{shop["business"]}' + suffix, actor='user', **params)


def patch_product(shop, ident, **changes):
    return request(shop, f'/shop-owner/products/{ident}', 'patch', changes, business_id=shop['business'])


def test_category_create_duplicate_update_deactivate_and_scoping(shop):
    first = category(shop, '  Groceries  ', description='Food')
    assert first['name'] == 'Groceries' and first['is_active']
    assert request(shop, '/shop-owner/categories', 'post', {'name': 'groceries'}, business_id=shop['business']).status_code == 409
    other = request(shop, '/shop-owner/categories', 'post', {'name': 'Groceries'},
        actor='other_owner', business_id=shop['foreign'])
    assert other.status_code == 201
    assert request(shop, f'/shop-owner/categories/{other.json()["category_id"]}', 'patch',
        {'name': 'Stolen'}, business_id=shop['business']).status_code == 404
    assert request(shop, f'/shop-owner/categories/{first["category_id"]}', 'patch',
        {'name': 'Renamed', 'description': None, 'is_active': False}, business_id=shop['business']).status_code == 200
    assert public(shop, '/categories').json()['categories'] == []
    own = request(shop, '/shop-owner/categories', business_id=shop['business']).json()
    assert own['total'] == 1 and own['categories'][0]['is_active'] is False


def test_product_decimal_publication_availability_and_archive(shop):
    created = product(shop, category_id=category(shop)['category_id'])
    ident = created['product_id']
    assert created['publication_status'] == 'draft' and created['currency'] == 'LKR'
    assert created['unit_price'] == '125.25'
    assert public(shop).json()['total'] == 0
    assert public(shop, f'/products/{ident}').status_code == 404
    changed = patch_product(shop, ident, unit_price='9999999999.99', publication_status='published')
    assert changed.status_code == 200 and changed.json()['unit_price'] == '9999999999.99'
    assert shop['db'].get(Product, ident).unit_price == Decimal('9999999999.99')
    row = public(shop, f'/products/{ident}').json()
    assert row['unit_price'] == '9999999999.99'
    assert set(row) == {'product_id','business_id','category_id','category_name','name','description','unit_price','currency','availability_status'}
    assert patch_product(shop, ident, availability_status='unavailable').status_code == 200
    assert public(shop, availability_status='available').json()['total'] == 0
    assert public(shop, availability_status='unavailable').json()['total'] == 1
    assert patch_product(shop, ident, publication_status='draft').status_code == 200
    assert public(shop, f'/products/{ident}').status_code == 404
    assert patch_product(shop, ident, publication_status='archived').status_code == 200
    assert patch_product(shop, ident, publication_status='published').status_code == 409
    assert patch_product(shop, ident, unit_price='5.00').status_code == 409
    assert public(shop).json()['total'] == 0
    assert request(shop, '/shop-owner/products', business_id=shop['business'], publication_status='archived').json()['total'] == 1


@pytest.mark.parametrize('price', ['0', '-1', 'NaN', 'Infinity', '1.001', '10000000000.00', True, 1.25, 'bad'])
def test_invalid_prices_do_not_create_or_modify_products(shop, price):
    assert request(shop, '/shop-owner/products', 'post', {'name':'Invalid','unit_price':price}, business_id=shop['business']).status_code == 422
    ident = product(shop)['product_id']
    assert patch_product(shop, ident, unit_price=price).status_code == 422
    assert shop['db'].get(Product, ident).unit_price == Decimal('125.25')


@pytest.mark.parametrize('changes', [
    {'name':''}, {'name':' '}, {'name':'x'*201}, {'name':'line\nbreak'}, {'description':'x'*4001},
    {'currency':'USD'}, {'business_id':999}, {'product_id':999}, {'stock_quantity':10},
    {'image_reference':'javascript:alert(1)'}, {'image_url':'../../private'},
    {'availability_status':'low_stock'}, {'publication_status':'archived'}, {'publication_status':'private'},
    {'category_id':True}, {'description':'<script>alert(1)</script>'}, {'name':'<img src=x onerror=alert(1)>'},
])
def test_creation_rejects_invalid_or_unstored_fields(shop, changes):
    response=request(shop, '/shop-owner/products', 'post', {'name':'Rice','unit_price':'1.00',**changes}, business_id=shop['business'])
    assert response.status_code == 422


@pytest.mark.parametrize('payload', [{}, {'name':None}, {'unit_price':None}, {'publication_status':None},
    {'business_id':1}, {'currency':'USD'}, {'availability_status':'sold_out'}])
def test_explicit_update_schema_rejects_unsafe_changes(shop, payload):
    ident=product(shop)['product_id']
    assert request(shop, f'/shop-owner/products/{ident}', 'patch', payload, business_id=shop['business']).status_code == 422


def test_category_relationship_is_enforced_in_api_and_database(shop):
    other = request(shop, '/shop-owner/categories', 'post', {'name':'Foreign'},
        actor='other_owner', business_id=shop['foreign']).json()['category_id']
    assert request(shop, '/shop-owner/products', 'post', {'name':'Rice','unit_price':'1.00','category_id':other}, business_id=shop['business']).status_code == 404
    ident=product(shop)['product_id']
    assert patch_product(shop, ident, category_id=other).status_code == 404
    with pytest.raises(IntegrityError):
        with shop['db'].begin_nested():
            shop['db'].add(Product(business_id=shop['business'], category_id=other, name='Wrong shop', unit_price=Decimal('1.00')))
            shop['db'].flush()


def test_inactive_category_hides_products_and_blocks_new_publication(shop):
    cat=category(shop);ident=product(shop,category_id=cat['category_id'],publication_status='published')['product_id']
    path=f'/shop-owner/categories/{cat["category_id"]}'
    assert request(shop,path,'patch',{'is_active':False},business_id=shop['business']).status_code == 200
    assert public(shop).json()['total'] == 0 and public(shop,f'/products/{ident}').status_code == 404
    assert request(shop,'/shop-owner/products','post',{'name':'Rice','unit_price':'1.00','category_id':cat['category_id'],'publication_status':'published'},business_id=shop['business']).status_code == 409
    assert patch_product(shop,ident,publication_status='published').status_code == 409
    # Explicitly remove the category to publish uncategorized.
    assert patch_product(shop,ident,category_id=None).status_code == 200
    assert public(shop).json()['total'] == 1


def test_business_specific_prices_discovery_search_filters_and_stable_pages(shop):
    cat=category(shop);othercat=category(shop,'Other')
    ids=[]
    for name, price, availability, category_id in [('Rice','10.10','available',cat['category_id']),
        ('Brown rice','20.20','unavailable',cat['category_id']),('100%_Rice','30.30','available',othercat['category_id'])]:
        ids.append(product(shop,name=name,unit_price=price,availability_status=availability,category_id=category_id,publication_status='published')['product_id'])
    product(shop,name='Hidden rice')
    foreign=request(shop,'/shop-owner/products','post',{'name':'Rice','unit_price':'999.99','publication_status':'published'},actor='other_owner',business_id=shop['foreign']).json()
    assert foreign['unit_price']=='999.99'
    assert public(shop,q='Rice',category_id=cat['category_id']).json()['total']==2
    assert public(shop,q='%_').json()['products'][0]['name']=='100%_Rice'
    assert public(shop,q="' OR 1=1 --").json()['total']==0
    for page, expected in [(1,ids[:2]),(2,ids[2:]),(3,[])]:
        result=public(shop,page=page,page_size=2).json()
        assert result['total']==3 and [p['product_id'] for p in result['products']]==expected
    assert public(shop,category_id=othercat['category_id'],availability_status='available').json()['total']==1
    assert public(shop,f'/products/{foreign["product_id"]}').status_code==404
    shops=request(shop,'/customer/catalogue/shops',actor='user',page_size=1).json()
    assert shops['total']==2 and len(shops['shops'])==1
    assert set(shops['shops'][0])=={'business_id','business_name','product_count'}
    assert public(shop,'/categories').json()['total']==2
    assert request(shop,'/customer/shops',actor='user').json()['total']==0  # Existing credit-linked discovery unchanged.


@pytest.mark.parametrize('approval', ['pending','rejected'])
def test_business_approval_restricts_management_and_publication(shop, approval):
    ident=product(shop,publication_status='published')['product_id']
    shop['db'].get(Business,shop['business']).approval_status=approval;shop['db'].flush()
    for path in ['/shop-owner/products','/shop-owner/categories']:
        assert request(shop,path,business_id=shop['business']).status_code==403
    assert patch_product(shop,ident,unit_price='2.00').status_code==403
    assert public(shop).status_code==404 and public(shop,f'/products/{ident}').status_code==404
    assert request(shop,'/customer/catalogue/shops',actor='user').json()['total']==0


@pytest.mark.parametrize('role', ['customer','driver','admin'])
def test_management_role_and_customer_read_only_policy(shop, role):
    actor=shop['make_user'](role)
    for path in ['/shop-owner/products','/shop-owner/categories']:
        assert request(shop,path,actor=actor,business_id=shop['business']).status_code==403
        assert request(shop,path,'post',{},actor=actor,business_id=shop['business']).status_code==403
    browse=request(shop,'/customer/catalogue/shops',actor=actor)
    assert browse.status_code==(200 if role=='customer' else 403)
    assert request(shop,'/customer/catalogue/shops','post',{},actor=actor).status_code==405


def test_wrong_owner_membership_account_and_jwt_denials(shop):
    ident=product(shop)['product_id']
    assert request(shop,f'/shop-owner/products/{ident}',actor='other_owner',business_id=shop['business']).status_code==404
    assert request(shop,f'/shop-owner/products/{ident}','patch',{'unit_price':'0.01'},business_id=shop['foreign']).status_code==404
    member=shop['db'].scalar(select(BusinessMember).where(BusinessMember.user_id==shop['owner'].user_id))
    for role,status in [('staff','active'),('owner','inactive')]:
        member.business_role=role;member.membership_status=status;shop['db'].flush()
        assert request(shop,'/shop-owner/products',business_id=shop['business']).status_code==404
    member.business_role='owner';member.membership_status='active'
    shop['owner'].account_status='suspended';shop['db'].flush()
    assert request(shop,'/shop-owner/products',business_id=shop['business']).status_code==403
    assert shop['client'].get('/api/v1/shop-owner/products',params={'business_id':shop['business']}).status_code==401
    now=datetime.now(timezone.utc)
    token=jwt.encode({'sub':str(shop['user'].user_id),'type':'access','iat':now-timedelta(hours=2),'exp':now-timedelta(hours=1)},settings.JWT_SECRET_KEY,algorithm='HS256')
    assert shop['client'].get('/api/v1/customer/catalogue/shops',headers={'Authorization':'Bearer '+token}).status_code==401


@pytest.mark.parametrize('params',[{'page':0},{'page_size':101},{'page':1000001},{'category_id':-1},
    {'q':'x'*201},{'availability_status':'maybe'}])
def test_browsing_bounds_and_filters(shop,params):
    assert public(shop,**params).status_code==422


def test_one_owner_can_select_multiple_businesses_but_not_mutate_identity(shop):
    shop['db'].add(BusinessMember(user_id=shop['owner'].user_id,business_id=shop['foreign'],membership_status='active',business_role='owner'));shop['db'].flush()
    created=request(shop,'/shop-owner/products','post',{'name':'Rice','unit_price':'0.01'},business_id=shop['foreign'])
    assert created.status_code==201 and created.json()['business_id']==shop['foreign']
    assert request(shop,'/shop-owner/products',business_id=shop['business']).json()['total']==0


def test_catalogue_writes_and_reads_preserve_financial_and_delivery_records(shop):
    _,account=shop['profile'](shop['business']);entry(shop,account,'credit_sale','200.00');entry(shop,account,'repayment','50.00')
    models=[CreditAccount,LedgerEntry,PaymentReminder,Notification,DeliveryRequest,DeliveryAssignment,DeliveryStatusEvent]
    def snapshot():
        return [shop['db'].execute(select(m.__table__).order_by(*m.__table__.primary_key)).all() for m in models]
    before=snapshot()
    cat=category(shop);ident=product(shop,category_id=cat['category_id'])['product_id']
    for changes in [{'unit_price':'100.10'},{'publication_status':'published'},{'availability_status':'unavailable'},{'publication_status':'archived'}]:
        assert patch_product(shop,ident,**changes).status_code==200
    assert public(shop).status_code==200
    assert snapshot()==before


def test_failed_commit_rolls_back_catalogue_and_sanitizes_diagnostics(shop,monkeypatch):
    def fail(*args,**kwargs):raise SQLAlchemyError('private database detail')
    monkeypatch.setattr(Session,'commit',fail)
    result=request(shop,'/shop-owner/products','post',{'name':'Rollback','unit_price':'1.00'},business_id=shop['business'])
    assert result.status_code==503 and 'private database detail' not in result.text
    assert request(shop,'/shop-owner/products',business_id=shop['business']).json()['total']==0


@pytest.mark.parametrize('changes',[{'name':''},{'name':'x'*101},{'name':'line\nbreak'},
    {'description':'x'*2001},{'description':'<svg onload=alert(1)></svg>'},
    {'is_active':'false'},{'is_active':None},{'business_id':1}])
def test_category_validation_is_explicit_for_create_and_update(shop,changes):
    assert request(shop,'/shop-owner/categories','post',{'name':'Invalid',**changes},business_id=shop['business']).status_code==422
    ident=category(shop)['category_id']
    assert request(shop,f'/shop-owner/categories/{ident}','patch',changes,business_id=shop['business']).status_code==422

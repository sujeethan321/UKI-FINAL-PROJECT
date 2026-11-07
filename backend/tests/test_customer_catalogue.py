"""Customer discovery/search and strictly public projections, real JWT/SQL."""
import pytest
from app.models import Business
from test_catalogue import shop, api, db, request, category, product, patch_product, public


def test_shop_name_search_is_server_side_bounded_escaped_and_paged(shop):
    row=shop['db'].get(Business,shop['business']);row.business_name='Local 100%_Market';shop['db'].flush()
    product(shop,publication_status='published')
    request(shop,'/shop-owner/products','post',{'name':'Foreign','unit_price':'1.00','publication_status':'published'},actor='other_owner',business_id=shop['foreign'])
    path='/customer/catalogue/shops'
    for query in ['Local','%_']:
        result=request(shop,path,actor='user',q=query,page_size=1).json()
        assert result['total']==1 and result['shops'][0]['business_id']==shop['business']
    assert request(shop,path,actor='user',q="' OR 1=1 --").json()['total']==0
    assert request(shop,path,actor='user',q='x'*201).status_code==422
    assert request(shop,path,actor='user',q='Local',page=2,page_size=1).json()['shops']==[]


def test_shop_detail_only_public_name_and_visible_product_count(shop):
    cat=category(shop)
    visible=product(shop,category_id=cat['category_id'],publication_status='published',availability_status='unavailable')
    product(shop)
    archived=product(shop)['product_id'];patch_product(shop,archived,publication_status='archived')
    detail=public(shop,'').json()
    assert set(detail)=={'business_id','business_name','product_count'} and detail['product_count']==1
    response=public(shop,f'/products/{visible["product_id"]}')
    assert response.json()['category_name']==cat['name']
    assert 'publication_status' not in response.json() and 'updated_at' not in response.json()
    assert public(shop,'/products').json()['products'][0]['category_name']==cat['name']
    # Approved empty shop is safe to open directly, but not a discovery result.
    assert request(shop,f'/customer/catalogue/shops/{shop["foreign"]}',actor='user').json()['product_count']==0
    shop['db'].get(Business,shop['business']).approval_status='pending';shop['db'].flush()
    assert public(shop,'').status_code==404


@pytest.mark.parametrize('role',['shop_owner','driver','admin'])
def test_new_shop_detail_preserves_customer_only_access(shop,role):
    assert request(shop,f'/customer/catalogue/shops/{shop["business"]}',actor=shop['make_user'](role)).status_code==403


def test_direct_detail_identifiers_do_not_cross_shop_scope_or_reveal_hidden_products(shop):
    published=product(shop,publication_status='published')['product_id']
    draft=product(shop)['product_id']
    assert request(shop,f'/customer/catalogue/shops/{shop["foreign"]}/products/{published}',actor='user').status_code==404
    assert public(shop,f'/products/{draft}').status_code==404
    assert shop['client'].get(f'/api/v1/customer/catalogue/shops/{shop["business"]}').status_code==401

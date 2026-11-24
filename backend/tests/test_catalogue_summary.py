"""Global owner counts and bounded category label projections."""
import pytest
from app.models import Business
from test_catalogue import shop, api, db, request, category, product, patch_product, public


def test_summary_uses_all_business_rows_not_filtered_page_and_no_other_business(shop):
    cat=category(shop)
    for index in range(23):
        product(shop,name=f'Item {index}',category_id=cat['category_id'])
    archived=product(shop)['product_id']
    assert patch_product(shop,archived,publication_status='archived').status_code==200
    product(shop,publication_status='published',availability_status='unavailable')
    request(shop,'/shop-owner/products','post',{'name':'Foreign','unit_price':'1.00'},actor='other_owner',business_id=shop['foreign'])
    result=request(shop,'/shop-owner/catalogue/summary',business_id=shop['business'])
    assert result.status_code==200 and result.headers['cache-control']=='no-store'
    assert result.json()==dict(business_id=shop['business'],total_products_count=25,available_products_count=23,
        categories_count=1,unpublished_products_count=23)
    page=request(shop,'/shop-owner/products',business_id=shop['business'],page_size=2,q='Item').json()
    assert len(page['products'])==2 and page['products'][0]['category_name']==cat['name']
    assert public(shop).json()['products'][0].get('category_name') is None


def test_summary_empty_and_foreign_scope(shop):
    assert request(shop,'/shop-owner/catalogue/summary',business_id=shop['business']).json()==dict(
        business_id=shop['business'],total_products_count=0,available_products_count=0,categories_count=0,unpublished_products_count=0)
    assert request(shop,'/shop-owner/catalogue/summary',business_id=shop['foreign']).status_code==404
    shop['db'].get(Business,shop['business']).approval_status='pending';shop['db'].flush()
    assert request(shop,'/shop-owner/catalogue/summary',business_id=shop['business']).status_code==403


@pytest.mark.parametrize('role',['customer','driver','admin'])
def test_summary_requires_owner_role(shop,role):
    assert request(shop,'/shop-owner/catalogue/summary',actor=shop['make_user'](role),business_id=shop['business']).status_code==403

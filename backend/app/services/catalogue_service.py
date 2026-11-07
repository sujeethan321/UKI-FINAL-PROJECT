"""Catalogue isolation and publication rules. Caller owns commit/rollback."""
from fastapi import HTTPException
from sqlalchemy import case, func, or_, select

from app.models import Business, BusinessMember, Product, ProductCategory, User
from app.models.catalogue import utc_now


def owner_business(db, user, business_id):
    # Current/shared reads keep approval, membership and account restrictions
    # authoritative throughout a write without modifying financial helpers.
    result = db.execute(select(Business, User).join(
        BusinessMember, BusinessMember.business_id == Business.business_id).join(
        User, User.user_id == BusinessMember.user_id).where(
        Business.business_id == business_id, User.user_id == user.user_id,
        BusinessMember.business_role == 'owner', BusinessMember.membership_status == 'active',
    ).with_for_update(read=True).execution_options(populate_existing=True)).one_or_none()
    if result is None:
        raise HTTPException(404, 'Business not found')
    business, actor = result
    if actor.platform_role != 'shop_owner' or actor.account_status != 'active':
        raise HTTPException(403, 'Catalogue management is not permitted')
    if business.approval_status != 'approved':
        raise HTTPException(403, 'Business approval is required for catalogue management')
    return business


def public_business(db, business_id):
    business = db.scalar(select(Business.business_id).where(
        Business.business_id == business_id, Business.approval_status == 'approved'))
    if business is None:
        raise HTTPException(404, 'Shop not found')


def category(db, business_id, category_id, write=False):
    query = select(ProductCategory).where(ProductCategory.business_id == business_id,
                                            ProductCategory.category_id == category_id)
    query = query.with_for_update(read=not write).execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, 'Category not found')
    return row


def product(db, business_id, product_id, write=False):
    query = select(Product).where(Product.business_id == business_id, Product.product_id == product_id)
    if write:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, 'Product not found')
    return row


def paged(db, query, page, page_size, key, order):
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = list(db.scalars(query.order_by(order).offset((page - 1) * page_size).limit(page_size)))
    return dict(page=page, page_size=page_size, total=total, **{key: rows})


def create_category(db, user, business_id, payload):
    owner_business(db, user, business_id)
    row = ProductCategory(business_id=business_id, **payload.model_dump())
    db.add(row)
    db.flush()
    return row


def update_category(db, user, business_id, category_id, payload):
    owner_business(db, user, business_id)
    row = category(db, business_id, category_id, write=True)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, 'Provide at least one category field')
    for key, value in changes.items():
        setattr(row, key, value)
    row.updated_at = utc_now()
    db.flush()
    return row


def list_categories(db, business_id, page, page_size, user=None):
    if user is not None:
        owner_business(db, user, business_id)
    else:
        public_business(db, business_id)
    query = select(ProductCategory).where(ProductCategory.business_id == business_id)
    if user is None:
        query = query.where(ProductCategory.is_active.is_(True))
    return paged(db, query, page, page_size, 'categories', ProductCategory.category_id)


def create_product(db, user, business_id, payload):
    owner_business(db, user, business_id)
    if payload.category_id is not None:
        linked = category(db, business_id, payload.category_id)
        if payload.publication_status == 'published' and not linked.is_active:
            raise HTTPException(409, 'Activate the category before publishing')
    row = Product(business_id=business_id, **payload.model_dump())
    db.add(row)
    db.flush()
    return product_data(db, [row], owner=True)[0]


def update_product(db, user, business_id, product_id, payload):
    owner_business(db, user, business_id)
    row = product(db, business_id, product_id, write=True)
    if row.publication_status == 'archived':
        raise HTTPException(409, 'Archived products cannot be changed')
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, 'Provide at least one product field')
    category_id = changes.get('category_id', row.category_id)
    publication = changes.get('publication_status', row.publication_status)
    if category_id is not None:
        linked = category(db, business_id, category_id)
        if publication == 'published' and not linked.is_active and (
            'category_id' in changes or 'publication_status' in changes):
            raise HTTPException(409, 'Activate the category before publishing')
    for key, value in changes.items():
        setattr(row, key, value)
    row.updated_at = utc_now()
    db.flush()
    return product_data(db, [row], owner=True)[0]


def product_data(db, rows, owner=False):
    """Resolve category labels in one bounded query, retaining shop scope."""
    ids = {row.category_id for row in rows if row.category_id is not None}
    names = dict(db.execute(select(ProductCategory.category_id, ProductCategory.name).where(
        ProductCategory.category_id.in_(ids),
        ProductCategory.business_id.in_({row.business_id for row in rows}))).all()) if ids else {}
    fields = ('product_id','business_id','category_id','name','description','unit_price','currency','availability_status')
    if owner:
        fields += ('publication_status','created_at','updated_at')
    return [dict(**{key: getattr(row, key) for key in fields}, category_name=names.get(row.category_id)) for row in rows]


def summary(db, user, business_id):
    owner_business(db, user, business_id)
    total, available, unpublished = db.execute(select(func.count(),
        func.coalesce(func.sum(case((
            (Product.availability_status == 'available') & (Product.publication_status != 'archived'), 1), else_=0)), 0),
        func.coalesce(func.sum(case((Product.publication_status == 'draft', 1), else_=0)), 0),
    ).where(Product.business_id == business_id)).one()
    categories = db.scalar(select(func.count()).select_from(ProductCategory).where(ProductCategory.business_id == business_id))
    return dict(business_id=business_id, total_products_count=total, available_products_count=available,
                categories_count=categories, unpublished_products_count=unpublished)


def visible_products():
    return select(Product).outerjoin(ProductCategory, ProductCategory.category_id == Product.category_id).where(
        Product.publication_status == 'published',
        or_(Product.category_id.is_(None), ProductCategory.is_active.is_(True)))


def list_products(db, business_id, page, page_size, q=None, category_id=None,
                  availability_status=None, publication_status=None, user=None):
    if user is not None:
        owner_business(db, user, business_id)
        query = select(Product)
    else:
        public_business(db, business_id)
        query = visible_products()
    query = query.where(Product.business_id == business_id)
    if q and q.strip():
        query = query.where(Product.name.contains(q.strip(), autoescape=True))
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
    if availability_status is not None:
        query = query.where(Product.availability_status == availability_status)
    if user is not None and publication_status is not None:
        query = query.where(Product.publication_status == publication_status)
    result = paged(db, query, page, page_size, 'products', Product.product_id)
    result['products'] = product_data(db, result['products'], owner=user is not None)
    return result


def product_detail(db, business_id, product_id, user=None):
    if user is not None:
        owner_business(db, user, business_id)
        return product_data(db, [product(db, business_id, product_id)], owner=True)[0]
    public_business(db, business_id)
    row = db.scalar(visible_products().where(Product.business_id == business_id, Product.product_id == product_id))
    if row is None:
        raise HTTPException(404, 'Product not found')
    return product_data(db, [row])[0]


def shops(db, page, page_size, q=None):
    counts = visible_products().with_only_columns(
        Product.business_id, func.count().label('product_count')).group_by(Product.business_id).subquery()
    query = select(Business.business_id, Business.business_name, counts.c.product_count).join(
        counts, counts.c.business_id == Business.business_id).where(Business.approval_status == 'approved')
    if q and q.strip():
        query = query.where(Business.business_name.contains(q.strip(), autoescape=True))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(Business.business_id).offset((page - 1) * page_size).limit(page_size)).mappings().all()
    return dict(page=page, page_size=page_size, total=total, shops=rows)


def shop_detail(db, business_id):
    public_business(db, business_id)
    name = db.scalar(select(Business.business_name).where(Business.business_id == business_id))
    count = db.scalar(select(func.count()).select_from(visible_products().where(Product.business_id == business_id).subquery()))
    return dict(business_id=business_id, business_name=name, product_count=count)

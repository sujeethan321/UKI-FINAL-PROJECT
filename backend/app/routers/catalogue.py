# Purpose: Expose catalogue HTTP endpoints and connect request validation and dependencies to the application services.
"""Owner catalogue management and distinct Customer shopping discovery."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.catalogue import (Availability, Publication, CategoryCreate, CategoryUpdate,
    ProductCreate, ProductUpdate, CategoryOwner, ProductOwner, ProductPublic, OwnerCategories,
    PublicCategories, OwnerProducts, PublicProducts, Shops, ShopPublic, CatalogueSummary)
from app.services import catalogue_service as service

owner_router = APIRouter(prefix='/shop-owner', tags=['Shop Owner Catalogue'])
customer_router = APIRouter(prefix='/customer/catalogue', tags=['Customer Catalogue'])
Owner = Annotated[User, Depends(require_roles('shop_owner'))]
Customer = Annotated[User, Depends(require_roles('customer'))]
Database = Annotated[Session, Depends(get_db)]
BusinessId = Annotated[int, Query(gt=0, le=9223372036854775807)]
Id = Annotated[int, Path(gt=0, le=9223372036854775807)]
Page = Annotated[int, Query(ge=1, le=1000000)]
Size = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str | None, Query(max_length=200)]
CategoryId = Annotated[int | None, Query(gt=0, le=9223372036854775807)]


# Check the business plan before allowing an operation that needs catalogue access.
def catalogue_entitlement(user: Owner,db: Database,business_id: BusinessId):
    from app.services.subscription_service import require_entitlement
    require_entitlement(db,user,business_id,'catalogue')

owner_router.dependencies.append(Depends(catalogue_entitlement))


# Wrap the service call at the HTTP boundary with cache policy and transaction/error handling.
def operation(db, response, action, schema, write=False):
    response.headers['Cache-Control'] = 'no-store'
    try:
        # Validate/project before commit, including every nested ORM object.
        result = schema.model_validate(action())
        if write:
            db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Catalogue conflict. Category names must be unique within a business.') from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, 'Catalogue operation could not be confirmed. Refresh before retrying.') from None


# Handle POST /categories through the declared request and dependency contract.
@owner_router.post('/categories', response_model=CategoryOwner, status_code=201)
def create_category(response: Response, user: Owner, db: Database, business_id: BusinessId, payload: CategoryCreate):
    return operation(db, response, lambda: service.create_category(db, user, business_id, payload), CategoryOwner, True)


# Handle GET /catalogue/summary through the declared request and dependency contract.
@owner_router.get('/catalogue/summary', response_model=CatalogueSummary)
def summary(response: Response, user: Owner, db: Database, business_id: BusinessId):
    return operation(db, response, lambda: service.summary(db, user, business_id), CatalogueSummary)


# Handle GET /categories through the declared request and dependency contract.
@owner_router.get('/categories', response_model=OwnerCategories)
def owner_categories(response: Response, user: Owner, db: Database, business_id: BusinessId, page: Page = 1, page_size: Size = 20):
    return operation(db, response, lambda: service.list_categories(db, business_id, page, page_size, user), OwnerCategories)


# Handle PATCH /categories/{category_id} through the declared request and dependency contract.
@owner_router.patch('/categories/{category_id}', response_model=CategoryOwner)
def update_category(response: Response, user: Owner, db: Database, business_id: BusinessId, category_id: Id, payload: CategoryUpdate):
    return operation(db, response, lambda: service.update_category(db, user, business_id, category_id, payload), CategoryOwner, True)


# Handle POST /products through the declared request and dependency contract.
@owner_router.post('/products', response_model=ProductOwner, status_code=201)
def create_product(response: Response, user: Owner, db: Database, business_id: BusinessId, payload: ProductCreate):
    return operation(db, response, lambda: service.create_product(db, user, business_id, payload), ProductOwner, True)


# Handle GET /products through the declared request and dependency contract.
@owner_router.get('/products', response_model=OwnerProducts)
def owner_products(response: Response, user: Owner, db: Database, business_id: BusinessId,
    page: Page = 1, page_size: Size = 20, q: Search = None, category_id: CategoryId = None,
    availability_status: Availability | None = None, publication_status: Publication | None = None):
    return operation(db, response, lambda: service.list_products(db, business_id, page, page_size,
        q, category_id, availability_status, publication_status, user), OwnerProducts)


# Handle GET /products/{product_id} through the declared request and dependency contract.
@owner_router.get('/products/{product_id}', response_model=ProductOwner)
def owner_product(response: Response, user: Owner, db: Database, business_id: BusinessId, product_id: Id):
    return operation(db, response, lambda: service.product_detail(db, business_id, product_id, user), ProductOwner)


# Handle PATCH /products/{product_id} through the declared request and dependency contract.
@owner_router.patch('/products/{product_id}', response_model=ProductOwner)
def update_product(response: Response, user: Owner, db: Database, business_id: BusinessId, product_id: Id, payload: ProductUpdate):
    return operation(db, response, lambda: service.update_product(db, user, business_id, product_id, payload), ProductOwner, True)


# Handle GET /shops through the declared request and dependency contract.
@customer_router.get('/shops', response_model=Shops)
def shops(response: Response, user: Customer, db: Database, page: Page = 1, page_size: Size = 20, q: Search = None):
    return operation(db, response, lambda: service.shops(db, page, page_size, q), Shops)


# Handle GET /shops/{business_id} through the declared request and dependency contract.
@customer_router.get('/shops/{business_id}', response_model=ShopPublic)
def shop(response: Response, user: Customer, db: Database, business_id: Id):
    return operation(db, response, lambda: service.shop_detail(db, business_id), ShopPublic)


# Handle GET /shops/{business_id}/categories through the declared request and dependency contract.
@customer_router.get('/shops/{business_id}/categories', response_model=PublicCategories)
def categories(response: Response, user: Customer, db: Database, business_id: Id, page: Page = 1, page_size: Size = 20):
    return operation(db, response, lambda: service.list_categories(db, business_id, page, page_size), PublicCategories)


# Handle GET /shops/{business_id}/products through the declared request and dependency contract.
@customer_router.get('/shops/{business_id}/products', response_model=PublicProducts)
def products(response: Response, user: Customer, db: Database, business_id: Id,
    page: Page = 1, page_size: Size = 20, q: Search = None, category_id: CategoryId = None,
    availability_status: Availability | None = None):
    return operation(db, response, lambda: service.list_products(db, business_id, page, page_size,
        q, category_id, availability_status), PublicProducts)


# Handle GET /shops/{business_id}/products/{product_id} through the declared request and dependency contract.
@customer_router.get('/shops/{business_id}/products/{product_id}', response_model=ProductPublic)
def detail(response: Response, user: Customer, db: Database, business_id: Id, product_id: Id):
    return operation(db, response, lambda: service.product_detail(db, business_id, product_id), ProductPublic)

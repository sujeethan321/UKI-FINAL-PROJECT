
from fastapi import FastAPI
from app.core.config import settings
from app.core.http_security import configure_http_security
from app.routers.subscriptions import router as subscription_router

from app.routers.notifications import router as notification_router
from app.routers.catalogue import owner_router as owner_catalogue_router, customer_router as customer_catalogue_router
from app.routers.shop_owner_communication import router as communication_router
from app.routers.health import router as health_router
from app.routers.shop_owner_reminders import router as reminder_router
from app.routers.driver import router as driver_router
from app.routers.shop_owner_deliveries import router as shop_owner_delivery_router
from app.routers.customer import router as customer_router
from app.routers.customer_link import owner_router as owner_customer_link_router, customer_router as customer_link_router
from app.routers.customer_join import public_router as public_customer_join_router, owner_router as owner_customer_join_router, customer_router as customer_join_router
from app.routers.auth import router as auth_router
from app.routers.role_access import router as role_access_router
from app.routers.shop_owner import router as shop_owner_router
from app.routers.shop_owner_ai import router as shop_owner_ai_router
from app.routers.admin_businesses import (
    router as admin_businesses_router,
)


# 1. Create the FastAPI application FIRST
app = FastAPI(
    title="LankaPex API",
    description="Backend API for LankaPex",
    version="1.0.0",
    debug=settings.APP_DEBUG,
)
app.include_router(subscription_router, prefix="/api/v1")
app.include_router(driver_router, prefix="/api/v1")
app.include_router(owner_catalogue_router, prefix="/api/v1")
app.include_router(customer_catalogue_router, prefix="/api/v1")
app.include_router(shop_owner_delivery_router, prefix="/api/v1")
app.include_router(customer_router, prefix="/api/v1")
app.include_router(owner_customer_link_router, prefix="/api/v1")
app.include_router(customer_link_router, prefix="/api/v1")
app.include_router(public_customer_join_router, prefix="/api/v1")
app.include_router(owner_customer_join_router, prefix="/api/v1")
app.include_router(customer_join_router, prefix="/api/v1")
app.include_router(reminder_router, prefix="/api/v1")
app.include_router(notification_router, prefix="/api/v1")
app.include_router(communication_router, prefix="/api/v1")

app.include_router(
    shop_owner_router,
    prefix="/api/v1",
)
app.include_router(shop_owner_ai_router, prefix="/api/v1")
app.include_router(
    admin_businesses_router,
    prefix="/api/v1",
)

# 2. Configure explicit CORS, production hosts and safe error responses.
configure_http_security(app, settings)


# 3. Register existing routers
app.include_router(
    health_router,
    prefix="/api/v1",
)

app.include_router(
    auth_router,
    prefix="/api/v1",
)

app.include_router(
    role_access_router,
    prefix="/api/v1",
)


# 5. Root endpoint
@app.get("/")
def root():
    return {
        "message": "Welcome to LankaPex API"
    }

from app.routers.orders import customer_router as customer_order_router, owner_router as owner_order_router
app.include_router(customer_order_router, prefix='/api/v1')
app.include_router(owner_order_router, prefix='/api/v1')

from app.routers.admin import router as admin_router
app.include_router(admin_router, prefix='/api/v1')

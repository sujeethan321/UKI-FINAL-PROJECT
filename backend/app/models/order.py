# Purpose: Map order records to database tables so SQLAlchemy can persist and relate application data.
"""Shopping snapshots; credit is posted exclusively through the existing ledger."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, String, DateTime, Numeric, ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.catalogue import utc_now

# Map order to the orders table for ORM queries and persistence.
class Order(Base):
    __tablename__ = 'orders'
    __table_args__ = (
        UniqueConstraint('order_id','total',name='uq_order_id_product_total'),
        UniqueConstraint('order_id','customer_user_id',name='uq_order_id_customer'),
        UniqueConstraint('order_id','delivery_request_id',name='uq_order_id_delivery'),
        UniqueConstraint('customer_user_id','request_key',name='uq_order_customer_request'),
        UniqueConstraint('reference',name='uq_order_reference'),
        UniqueConstraint('credit_sale_id',name='uq_order_credit_sale'),
        UniqueConstraint('delivery_request_id', name='uq_order_delivery_request'),
        ForeignKeyConstraint(['delivery_request_id', 'business_id'],
            ['delivery_requests.delivery_request_id', 'delivery_requests.business_id'],
            name='fk_order_delivery_business', ondelete='RESTRICT'),
        CheckConstraint("payment_method IN ('cash','credit')",name='ck_order_method'),
        CheckConstraint("status IN ('submitted','approved','rejected','processing','completed','cancelled')",name='ck_order_status'),
        CheckConstraint("(payment_method = 'cash' AND payment_status = 'unpaid' AND credit_sale_id IS NULL AND credit_account_id IS NULL) OR (payment_method = 'credit' AND credit_account_id IS NOT NULL AND ((payment_status = 'pending' AND credit_sale_id IS NULL AND status IN ('submitted','rejected','cancelled')) OR (payment_status = 'posted' AND credit_sale_id IS NOT NULL AND status IN ('approved','processing','completed'))))",name='ck_order_financial_state'),
        CheckConstraint('total > 0 AND subtotal = total',name='ck_order_total'),
        Index('ix_order_customer_created','customer_user_id','created_at','order_id'),
        Index('ix_order_business_status','business_id','status','order_id'),
    )
    # Use order id as the unique row identity for ORM lookups and related records.
    order_id: Mapped[int] = mapped_column(BigInteger,primary_key=True,autoincrement=True)
    reference: Mapped[str] = mapped_column(String(40))
    # Link customer user id to users.user_id so the database enforces the record relationship.
    customer_user_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('users.user_id',ondelete='RESTRICT'))
    # Link business id to businesses.business_id so the database enforces the record relationship.
    business_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('businesses.business_id',ondelete='RESTRICT'))
    request_key: Mapped[str] = mapped_column(String(100,collation='utf8mb4_bin'))
    # Retain the request hash fingerprint used to compare values without persisting the corresponding raw value here.
    request_hash: Mapped[str] = mapped_column(String(64))
    payment_method: Mapped[str] = mapped_column(String(10))
    # Retain payment status so workflow checks can decide which operations are currently allowed.
    payment_status: Mapped[str] = mapped_column(String(10))
    # Retain status so workflow checks can decide which operations are currently allowed.
    status: Mapped[str] = mapped_column(String(20),default='submitted')
    # Store subtotal as an exact decimal so persisted financial values avoid binary floating-point rounding.
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14,2))
    # Store total as an exact decimal so persisted financial values avoid binary floating-point rounding.
    total: Mapped[Decimal] = mapped_column(Numeric(14,2))
    # Link credit account id to credit_accounts.credit_account_id so the database enforces the record relationship.
    credit_account_id: Mapped[int | None] = mapped_column(BigInteger,ForeignKey('credit_accounts.credit_account_id',ondelete='RESTRICT'),nullable=True)
    # Link credit sale id to ledger_entries.entry_id so the database enforces the record relationship.
    credit_sale_id: Mapped[int | None] = mapped_column(BigInteger,ForeignKey('ledger_entries.entry_id',ondelete='RESTRICT'),nullable=True)
    delivery_request_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DateTime,default=utc_now)
    # Retain updated at for history, ordering, and time-based queries.
    updated_at: Mapped[datetime] = mapped_column(DateTime,default=utc_now)

# Map order item to the order_items table for ORM queries and persistence.
class OrderItem(Base):
    __tablename__ = 'order_items'
    __table_args__ = (
        UniqueConstraint('order_id','product_id',name='uq_order_product'),
        CheckConstraint('quantity BETWEEN 1 AND 99',name='ck_order_quantity'),
        CheckConstraint('unit_price > 0 AND line_total = unit_price * quantity',name='ck_order_line_total'),
    )
    # Use order item id as the unique row identity for ORM lookups and related records.
    order_item_id: Mapped[int] = mapped_column(BigInteger,primary_key=True,autoincrement=True)
    # Link order id to orders.order_id so the database enforces the record relationship.
    order_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('orders.order_id',ondelete='RESTRICT'))
    # Link product id to products.product_id so the database enforces the record relationship.
    product_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('products.product_id',ondelete='RESTRICT'))
    product_name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column()
    # Store unit price as an exact decimal so persisted financial values avoid binary floating-point rounding.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12,2))
    # Store line total as an exact decimal so persisted financial values avoid binary floating-point rounding.
    line_total: Mapped[Decimal] = mapped_column(Numeric(14,2))

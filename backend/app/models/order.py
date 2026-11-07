"""Shopping snapshots; credit is posted exclusively through the existing ledger."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, String, DateTime, Numeric, ForeignKey, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.catalogue import utc_now

class Order(Base):
    __tablename__ = 'orders'
    __table_args__ = (
        UniqueConstraint('customer_user_id','request_key',name='uq_order_customer_request'),
        UniqueConstraint('reference',name='uq_order_reference'),
        UniqueConstraint('credit_sale_id',name='uq_order_credit_sale'),
        CheckConstraint("payment_method IN ('cash','credit')",name='ck_order_method'),
        CheckConstraint("status IN ('submitted','approved','rejected','processing','completed','cancelled')",name='ck_order_status'),
        CheckConstraint("(payment_method = 'cash' AND payment_status = 'unpaid' AND credit_sale_id IS NULL AND credit_account_id IS NULL) OR (payment_method = 'credit' AND credit_account_id IS NOT NULL AND ((payment_status = 'pending' AND credit_sale_id IS NULL AND status IN ('submitted','rejected','cancelled')) OR (payment_status = 'posted' AND credit_sale_id IS NOT NULL AND status IN ('approved','processing','completed'))))",name='ck_order_financial_state'),
        CheckConstraint('total > 0 AND subtotal = total',name='ck_order_total'),
        Index('ix_order_customer_created','customer_user_id','created_at','order_id'),
        Index('ix_order_business_status','business_id','status','order_id'),
    )
    order_id: Mapped[int] = mapped_column(BigInteger,primary_key=True,autoincrement=True)
    reference: Mapped[str] = mapped_column(String(40))
    customer_user_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('users.user_id',ondelete='RESTRICT'))
    business_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('businesses.business_id',ondelete='RESTRICT'))
    request_key: Mapped[str] = mapped_column(String(100,collation='utf8mb4_bin'))
    request_hash: Mapped[str] = mapped_column(String(64))
    payment_method: Mapped[str] = mapped_column(String(10))
    payment_status: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20),default='submitted')
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14,2))
    total: Mapped[Decimal] = mapped_column(Numeric(14,2))
    credit_account_id: Mapped[int | None] = mapped_column(BigInteger,ForeignKey('credit_accounts.credit_account_id',ondelete='RESTRICT'),nullable=True)
    credit_sale_id: Mapped[int | None] = mapped_column(BigInteger,ForeignKey('ledger_entries.entry_id',ondelete='RESTRICT'),nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime,default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime,default=utc_now)

class OrderItem(Base):
    __tablename__ = 'order_items'
    __table_args__ = (
        UniqueConstraint('order_id','product_id',name='uq_order_product'),
        CheckConstraint('quantity BETWEEN 1 AND 99',name='ck_order_quantity'),
        CheckConstraint('unit_price > 0 AND line_total = unit_price * quantity',name='ck_order_line_total'),
    )
    order_item_id: Mapped[int] = mapped_column(BigInteger,primary_key=True,autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('orders.order_id',ondelete='RESTRICT'))
    product_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('products.product_id',ondelete='RESTRICT'))
    product_name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column()
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12,2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14,2))

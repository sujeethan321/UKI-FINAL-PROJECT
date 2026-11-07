"""Business-owned catalogue only: no stock, orders, payments or ledger writes."""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey,
                        ForeignKeyConstraint, Index, Numeric, String, UniqueConstraint, true)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


class ProductCategory(Base):
    __tablename__ = 'product_categories'
    __table_args__ = (
        UniqueConstraint('business_id', 'name', name='uq_category_business_name'),
        UniqueConstraint('category_id', 'business_id', name='uq_category_id_business'),
        CheckConstraint("CHAR_LENGTH(TRIM(name)) > 0", name='ck_category_name'),
        Index('ix_category_business_active', 'business_id', 'is_active', 'category_id'),
    )
    category_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('businesses.business_id', ondelete='RESTRICT'))
    name: Mapped[str] = mapped_column(String(100, collation='utf8mb4_unicode_ci'))
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Product(Base):
    __tablename__ = 'products'
    __table_args__ = (
        ForeignKeyConstraint(['category_id', 'business_id'],
            ['product_categories.category_id', 'product_categories.business_id'],
            name='fk_product_category_business', ondelete='RESTRICT'),
        CheckConstraint("CHAR_LENGTH(TRIM(name)) > 0", name='ck_product_name'),
        CheckConstraint('unit_price > 0', name='ck_product_price'),
        CheckConstraint("currency = 'LKR'", name='ck_product_currency'),
        CheckConstraint("availability_status IN ('available','unavailable')", name='ck_product_availability'),
        CheckConstraint("publication_status IN ('draft','published','archived')", name='ck_product_publication'),
        Index('ix_product_business_publication', 'business_id', 'publication_status', 'product_id'),
        Index('ix_product_business_category', 'category_id', 'business_id'),
    )
    product_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('businesses.business_id', ondelete='RESTRICT'))
    category_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default='LKR', server_default='LKR')
    availability_status: Mapped[str] = mapped_column(String(20), default='available', server_default='available')
    publication_status: Mapped[str] = mapped_column(String(20), default='draft', server_default='draft')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

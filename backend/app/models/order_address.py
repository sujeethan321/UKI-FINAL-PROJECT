# Purpose: Map order address records to database tables so SQLAlchemy can persist and relate application data.
"""Immutable accepted destination. Saved-address edits never rewrite history."""
from datetime import datetime
from sqlalchemy import BigInteger,Integer,String,DateTime,ForeignKeyConstraint,CheckConstraint,Index,event
from sqlalchemy.orm import Mapped,mapped_column,Session
from app.core.database import Base
from app.models.catalogue import utc_now

# Map order delivery address to the order_delivery_addresses table for ORM queries and persistence.
class OrderDeliveryAddress(Base):
    __tablename__='order_delivery_addresses'
    __table_args__=(
        ForeignKeyConstraint(['order_id','customer_user_id'],['orders.order_id','orders.customer_user_id'],name='fk_oda_order_customer',ondelete='RESTRICT',onupdate='RESTRICT'),
        ForeignKeyConstraint(['source_address_id','customer_user_id'],['customer_addresses.address_id','customer_addresses.user_id'],name='fk_oda_address_customer',ondelete='RESTRICT',onupdate='RESTRICT'),
        CheckConstraint('accepted_version>=1',name='ck_oda_version'),
        CheckConstraint('CHAR_LENGTH(TRIM(recipient_name))>0 AND CHAR_LENGTH(TRIM(address_line))>0',name='ck_oda_text'),
        Index('ix_oda_order_customer','order_id','customer_user_id'),
        Index('ix_oda_source_customer','source_address_id','customer_user_id'),
        {'mysql_engine':'InnoDB','mysql_charset':'utf8mb4','mysql_collate':'utf8mb4_unicode_ci'},
    )
    # Use order id as the unique row identity for ORM lookups and related records.
    order_id: Mapped[int]=mapped_column(BigInteger,primary_key=True,autoincrement=False)
    customer_user_id: Mapped[int]=mapped_column(BigInteger)
    source_address_id: Mapped[int]=mapped_column(BigInteger)
    recipient_name: Mapped[str]=mapped_column(String(150))
    phone: Mapped[str | None]=mapped_column(String(20),nullable=True)
    address_line: Mapped[str]=mapped_column(String(500))
    city: Mapped[str | None]=mapped_column(String(100),nullable=True)
    accepted_version: Mapped[int]=mapped_column(Integer)
    # Retain the address digest fingerprint used to compare values without persisting the corresponding raw value here.
    address_digest: Mapped[str]=mapped_column(String(64))
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime]=mapped_column(DateTime,default=utc_now)

# Reject mutation of the persisted order-address snapshot so later edits cannot change the recorded destination.
@event.listens_for(Session,'before_flush')
def protect_snapshot(session,context,instances):
    if any(isinstance(r,OrderDeliveryAddress) for r in session.deleted) or any(isinstance(r,OrderDeliveryAddress) and session.is_modified(r) for r in session.dirty):
        raise ValueError('Order destinations are immutable')

# Reject bulk operations that would bypass the order-address snapshot protection.
@event.listens_for(Session,'do_orm_execute')
def protect_bulk_snapshot(context):
    if (context.is_update or context.is_delete) and getattr(getattr(context.statement,'table',None),'name',None)=='order_delivery_addresses':
        raise ValueError('Order destinations are immutable')

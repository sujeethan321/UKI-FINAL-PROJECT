"""Prospective Customer-funded fees; append-only financial event records."""
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import String, BigInteger, Integer, Numeric, DateTime, ForeignKey, ForeignKeyConstraint, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import event
from sqlalchemy.orm import Session
from app.core.database import Base
from app.models.delivery import utc_now
MYSQL_OPTIONS=dict(mysql_engine='InnoDB',mysql_charset='utf8mb4',mysql_collate='utf8mb4_unicode_ci')


class OrderFulfilmentCharge(Base):
    __tablename__ = 'order_fulfilment_charges'
    __table_args__ = (
        ForeignKeyConstraint(['order_id','product_subtotal'],['orders.order_id','orders.total'],name='fk_ofc_product_total',ondelete='RESTRICT',onupdate='RESTRICT'),
        UniqueConstraint('order_id','delivery_fee','mode',name='uq_ofc_earning_basis'),
        CheckConstraint("mode IN ('delivery','pickup')", name='ck_ofc_mode'),
        CheckConstraint("currency='LKR' AND product_subtotal>0 AND delivery_fee>=0 AND customer_total=product_subtotal+delivery_fee", name='ck_ofc_amounts'),
        CheckConstraint("(mode='pickup' AND delivery_fee=0 AND fee_rate=0) OR (mode='delivery' AND fee_rate=0.030000 AND delivery_fee=ROUND(product_subtotal*fee_rate,2))", name='ck_ofc_rate'),
        MYSQL_OPTIONS,
    )
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('orders.order_id', ondelete='RESTRICT'), primary_key=True)
    mode: Mapped[str] = mapped_column(String(12))
    product_subtotal: Mapped[Decimal] = mapped_column(Numeric(14,2))
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(14,2))
    customer_total: Mapped[Decimal] = mapped_column(Numeric(14,2))
    fee_rate: Mapped[Decimal] = mapped_column(Numeric(7,6))
    currency: Mapped[str] = mapped_column(String(3), default='LKR')
    policy_version: Mapped[str] = mapped_column(String(40), default='direct-driver-3pct-v1')
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DriverEarning(Base):
    __tablename__ = 'driver_earnings'
    __table_args__ = (
        ForeignKeyConstraint(['order_id','delivery_request_id'],['orders.order_id','orders.delivery_request_id'],name='fk_de_order_delivery',ondelete='RESTRICT',onupdate='RESTRICT'),
        ForeignKeyConstraint(['order_id','amount','charge_mode'],['order_fulfilment_charges.order_id','order_fulfilment_charges.delivery_fee','order_fulfilment_charges.mode'],name='fk_de_charge_basis',ondelete='RESTRICT',onupdate='RESTRICT'),
        ForeignKeyConstraint(['assignment_id','delivery_request_id','driver_user_id'],['delivery_assignments.assignment_id','delivery_assignments.delivery_request_id','delivery_assignments.driver_user_id'],name='fk_de_assignment',ondelete='RESTRICT',onupdate='RESTRICT'),
        ForeignKeyConstraint(['completion_event_id','delivery_request_id','driver_user_id','completion_status'],['delivery_status_events.event_id','delivery_status_events.delivery_request_id','delivery_status_events.actor_user_id','delivery_status_events.status'],name='fk_de_completion',ondelete='RESTRICT',onupdate='RESTRICT'),
        ForeignKeyConstraint(['delivery_request_id','completion_status'],['delivery_requests.delivery_request_id','delivery_requests.status'],name='fk_de_delivered_state',ondelete='RESTRICT',onupdate='RESTRICT'),
        CheckConstraint("amount>=0 AND currency='LKR' AND charge_mode='delivery' AND completion_status='delivered'",name='ck_de_amount'),
        UniqueConstraint('earning_id','driver_user_id',name='uq_de_driver'),
        UniqueConstraint('earning_id','amount',name='uq_de_amount'),
        Index('ix_de_driver_date','driver_user_id','created_at','earning_id'),MYSQL_OPTIONS)
    earning_id: Mapped[str] = mapped_column(String(36),primary_key=True,default=lambda:str(uuid4()))
    order_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('order_fulfilment_charges.order_id',ondelete='RESTRICT'),unique=True)
    delivery_request_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('delivery_requests.delivery_request_id',ondelete='RESTRICT'),unique=True)
    assignment_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('delivery_assignments.assignment_id',ondelete='RESTRICT'),unique=True)
    completion_event_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('delivery_status_events.event_id',ondelete='RESTRICT'),unique=True)
    driver_user_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('driver_profiles.user_id',ondelete='RESTRICT'))
    amount: Mapped[Decimal] = mapped_column(Numeric(14,2))
    currency: Mapped[str] = mapped_column(String(3),default='LKR')
    charge_mode: Mapped[str] = mapped_column(String(12),default='delivery')
    completion_status: Mapped[str] = mapped_column(String(20),default='delivered')
    created_at: Mapped[datetime] = mapped_column(DateTime,default=utc_now)


class DriverFeeCollection(Base):
    __tablename__ = 'driver_fee_collections'
    __table_args__ = (
        ForeignKeyConstraint(['earning_id','actor_user_id'],['driver_earnings.earning_id','driver_earnings.driver_user_id'],name='fk_dfc_owner',ondelete='RESTRICT',onupdate='RESTRICT'),
        ForeignKeyConstraint(['earning_id','declared_amount'],['driver_earnings.earning_id','driver_earnings.amount'],name='fk_dfc_full_amount',ondelete='RESTRICT',onupdate='RESTRICT'),
        UniqueConstraint('collection_id','earning_id','kind',name='uq_dfc_identity'),
        UniqueConstraint('collection_id','earning_id','actor_user_id','kind',name='uq_dfc_audit_identity'),
        UniqueConstraint('actor_user_id','request_key',name='uq_dfc_request'),
        CheckConstraint("kind IN ('declared','exception') AND amount>=0",name='ck_dfc_kind'),
        CheckConstraint("(kind='exception' AND declaration_slot IS NULL AND declared_amount IS NULL) OR (kind='declared' AND declaration_slot IS NOT NULL AND declaration_slot=1 AND declared_amount IS NOT NULL AND declared_amount=amount)",name='ck_dfc_slot'),
        UniqueConstraint('earning_id','declaration_slot',name='uq_dfc_declaration'),
        Index('ix_dfc_earning','earning_id','created_at','collection_id'),
        MYSQL_OPTIONS,
    )
    collection_id: Mapped[str] = mapped_column(String(36),primary_key=True,default=lambda:str(uuid4()))
    earning_id: Mapped[str] = mapped_column(String(36),ForeignKey('driver_earnings.earning_id',ondelete='RESTRICT'))
    actor_user_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('users.user_id',ondelete='RESTRICT'))
    kind: Mapped[str] = mapped_column(String(16))
    declaration_slot: Mapped[int | None] = mapped_column(nullable=True)
    declared_amount: Mapped[Decimal | None] = mapped_column(Numeric(14,2),nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14,2))
    evidence: Mapped[str] = mapped_column(String(1000))
    request_key: Mapped[str] = mapped_column(String(100,collation='utf8mb4_bin'))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime,default=utc_now)


class DriverSettlementEvent(Base):
    __tablename__ = 'driver_settlement_events'
    __table_args__ = (
        UniqueConstraint('earning_id','sequence_no',name='uq_dse_sequence'),
        ForeignKeyConstraint(['earning_id','previous_sequence_no'],['driver_settlement_events.earning_id','driver_settlement_events.sequence_no'],name='fk_dse_previous_sequence',ondelete='RESTRICT',onupdate='RESTRICT'),
        CheckConstraint("(sequence_no=1 AND previous_sequence_no IS NULL) OR (sequence_no>1 AND previous_sequence_no IS NOT NULL AND previous_sequence_no=sequence_no-1)",name='ck_dse_sequence'),
        ForeignKeyConstraint(['collection_id','earning_id','collection_kind'],['driver_fee_collections.collection_id','driver_fee_collections.earning_id','driver_fee_collections.kind'],name='fk_dse_collection_identity',ondelete='RESTRICT',onupdate='RESTRICT'),
        ForeignKeyConstraint(['earning_id','amount'],['driver_earnings.earning_id','driver_earnings.amount'],name='fk_dse_amount',ondelete='RESTRICT',onupdate='RESTRICT'),
        UniqueConstraint('event_id','earning_id','actor_user_id','kind',name='uq_dse_audit_identity'),
        UniqueConstraint('actor_user_id','request_key',name='uq_dse_request'),
        UniqueConstraint('earning_id','settlement_slot',name='uq_dse_direct_settlement'),
        CheckConstraint("kind IN ('direct_settled','disputed','reversed','refund_confirmed') AND amount>=0",name='ck_dse_kind'),
        CheckConstraint("(kind<>'direct_settled' AND settlement_slot IS NULL AND collection_id IS NULL AND collection_kind IS NULL) OR (kind='direct_settled' AND settlement_slot IS NOT NULL AND settlement_slot=1 AND collection_id IS NOT NULL AND collection_kind IS NOT NULL AND collection_kind='declared')",name='ck_dse_slot'),
        Index('ix_dse_earning','earning_id','created_at','event_id'),
        MYSQL_OPTIONS,
    )
    event_id: Mapped[str] = mapped_column(String(36),primary_key=True,default=lambda:str(uuid4()))
    earning_id: Mapped[str] = mapped_column(String(36),ForeignKey('driver_earnings.earning_id',ondelete='RESTRICT'))
    collection_id: Mapped[str | None] = mapped_column(String(36),ForeignKey('driver_fee_collections.collection_id',ondelete='RESTRICT'),nullable=True)
    collection_kind: Mapped[str | None] = mapped_column(String(16),nullable=True)
    actor_user_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('users.user_id',ondelete='RESTRICT'))
    kind: Mapped[str] = mapped_column(String(24))
    sequence_no: Mapped[int] = mapped_column(Integer)
    previous_sequence_no: Mapped[int | None] = mapped_column(Integer,nullable=True)
    settlement_slot: Mapped[int | None] = mapped_column(nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14,2))
    evidence: Mapped[str] = mapped_column(String(1000))
    request_key: Mapped[str] = mapped_column(String(100,collation='utf8mb4_bin'))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime,default=utc_now)


class DriverFinancialAudit(Base):
    __tablename__ = 'driver_financial_audits'
    __table_args__=(CheckConstraint("action IN ('accrued','declared','exception','direct_settled','disputed','reversed','refund_confirmed')",name='ck_dfa_action'),
        UniqueConstraint('collection_id',name='uq_dfa_collection_event'),
        UniqueConstraint('settlement_event_id',name='uq_dfa_settlement_event'),
        UniqueConstraint('earning_id','accrual_driver_id',name='uq_dfa_accrual_event'),
        CheckConstraint("(action='accrued' AND collection_id IS NULL AND settlement_event_id IS NULL AND accrual_driver_id IS NOT NULL AND accrual_driver_id=actor_user_id) OR (action IN ('declared','exception') AND collection_id IS NOT NULL AND settlement_event_id IS NULL AND accrual_driver_id IS NULL) OR (action IN ('direct_settled','disputed','reversed','refund_confirmed') AND collection_id IS NULL AND settlement_event_id IS NOT NULL AND accrual_driver_id IS NULL)",name='ck_dfa_reference'),
        ForeignKeyConstraint(['collection_id','earning_id','actor_user_id','action'],['driver_fee_collections.collection_id','driver_fee_collections.earning_id','driver_fee_collections.actor_user_id','driver_fee_collections.kind'],name='fk_dfa_collection',ondelete='RESTRICT',onupdate='RESTRICT'),
        ForeignKeyConstraint(['settlement_event_id','earning_id','actor_user_id','action'],['driver_settlement_events.event_id','driver_settlement_events.earning_id','driver_settlement_events.actor_user_id','driver_settlement_events.kind'],name='fk_dfa_settlement',ondelete='RESTRICT',onupdate='RESTRICT'),
        ForeignKeyConstraint(['earning_id','accrual_driver_id'],['driver_earnings.earning_id','driver_earnings.driver_user_id'],name='fk_dfa_accrual_owner',ondelete='RESTRICT',onupdate='RESTRICT'),
        Index('ix_dfa_earning_date','earning_id','created_at','audit_id'),MYSQL_OPTIONS)
    audit_id: Mapped[str] = mapped_column(String(36),primary_key=True,default=lambda:str(uuid4()))
    actor_user_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('users.user_id',ondelete='RESTRICT'))
    earning_id: Mapped[str] = mapped_column(String(36),ForeignKey('driver_earnings.earning_id',ondelete='RESTRICT'))
    action: Mapped[str] = mapped_column(String(24))
    collection_id: Mapped[str | None] = mapped_column(String(36),nullable=True)
    settlement_event_id: Mapped[str | None] = mapped_column(String(36),nullable=True)
    accrual_driver_id: Mapped[int | None] = mapped_column(BigInteger,nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime,default=utc_now)


@event.listens_for(Session,'before_flush')
def immutable_financial_events(session,context,instances):
    types=(OrderFulfilmentCharge,DriverEarning,DriverFeeCollection,DriverSettlementEvent,DriverFinancialAudit)
    if any(isinstance(row,types) for row in session.deleted) or any(isinstance(row,types) and session.is_modified(row) for row in session.dirty):
        raise ValueError('Driver financial records are append-only; use an authorized adjustment event')


@event.listens_for(Session,'do_orm_execute')
def reject_bulk_financial_changes(context):
    if context.is_update or context.is_delete:
        table=getattr(context.statement,'table',None)
        if getattr(table,'name',None) in {'order_fulfilment_charges','driver_earnings','driver_fee_collections','driver_settlement_events','driver_financial_audits'}:
            raise ValueError('Driver financial history is append-only')

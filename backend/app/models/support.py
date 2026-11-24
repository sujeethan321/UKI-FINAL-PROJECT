"""Support evidence is separate from financial ledgers. No cascade deletion."""
from datetime import datetime
from sqlalchemy import BigInteger,Integer,String,Text,Boolean,DateTime,ForeignKey,ForeignKeyConstraint,CheckConstraint,UniqueConstraint,Index,event
from sqlalchemy.orm import Mapped,mapped_column,Session
from app.core.database import Base
from app.models.catalogue import utc_now

OPTIONS={'mysql_engine':'InnoDB','mysql_charset':'utf8mb4','mysql_collate':'utf8mb4_unicode_ci'}
STATUSES=('open','assigned','investigating','awaiting_user','resolved','closed')
CATEGORIES=('account','credit_sale','repayment','credit_balance','order','delivery','driver_fee','other')


class SupportCase(Base):
    __tablename__='support_cases'
    __table_args__=(UniqueConstraint('reference',name='uq_support_reference'),UniqueConstraint('creator_id','request_key',name='uq_support_create_request'),
        CheckConstraint("status IN ('open','assigned','investigating','awaiting_user','resolved','closed')",name='ck_support_status'),
        CheckConstraint("category IN ('account','credit_sale','repayment','credit_balance','order','delivery','driver_fee','other')",name='ck_support_category'),
        CheckConstraint("priority IN ('low','normal','high','urgent')",name='ck_support_priority'),
        CheckConstraint('version>=1 AND public_version>=1 AND public_version<=version',name='ck_support_version'),
        CheckConstraint('(business_shared=0 OR business_id IS NOT NULL)',name='ck_support_sharing'),
        CheckConstraint("status NOT IN ('resolved','closed') OR (resolved_at IS NOT NULL AND resolution IS NOT NULL)",name='ck_support_resolution'),
        Index('ix_support_creator','creator_id','created_at','case_id'),Index('ix_support_business','business_id','business_shared','created_at','case_id'),
        Index('ix_support_queue','status','priority','created_at','case_id'),Index('ix_support_assignee','assigned_admin_id','status','case_id'),OPTIONS)
    case_id:Mapped[int]=mapped_column(BigInteger,primary_key=True,autoincrement=True)
    reference:Mapped[str]=mapped_column(String(40,collation='utf8mb4_bin'))
    creator_id:Mapped[int]=mapped_column(BigInteger,ForeignKey('users.user_id',ondelete='RESTRICT'))
    business_id:Mapped[int|None]=mapped_column(BigInteger,ForeignKey('businesses.business_id',ondelete='RESTRICT'),nullable=True)
    business_shared:Mapped[bool]=mapped_column(Boolean,default=False)
    category:Mapped[str]=mapped_column(String(20))
    subject:Mapped[str]=mapped_column(String(120))
    description:Mapped[str]=mapped_column(Text)
    priority:Mapped[str]=mapped_column(String(10),default='normal')
    status:Mapped[str]=mapped_column(String(20),default='open')
    assigned_admin_id:Mapped[int|None]=mapped_column(BigInteger,ForeignKey('users.user_id',ondelete='RESTRICT'),nullable=True)
    version:Mapped[int]=mapped_column(Integer,default=1)
    public_version:Mapped[int]=mapped_column(Integer,default=1)
    resolution:Mapped[str|None]=mapped_column(String(2000),nullable=True)
    resolved_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utc_now)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=utc_now)
    public_updated_at:Mapped[datetime]=mapped_column(DateTime,default=utc_now)
    request_key:Mapped[str]=mapped_column(String(100,collation='utf8mb4_bin'))
    request_hash:Mapped[str]=mapped_column(String(64))


class SupportMessage(Base):
    __tablename__='support_case_messages'
    __table_args__=(CheckConstraint("visibility IN ('public','internal')",name='ck_support_message_visibility'),
        UniqueConstraint('message_id','case_id','actor_id','actor_role',name='uq_support_message_event_identity'),
        CheckConstraint("actor_role IN ('admin','customer','shop_owner','driver') AND (visibility!='internal' OR actor_role='admin')",name='ck_support_message_actor'),
        Index('ix_support_messages','case_id','message_id'),OPTIONS)
    message_id:Mapped[int]=mapped_column(BigInteger,primary_key=True,autoincrement=True)
    case_id:Mapped[int]=mapped_column(BigInteger,ForeignKey('support_cases.case_id',ondelete='RESTRICT'))
    actor_id:Mapped[int]=mapped_column(BigInteger,ForeignKey('users.user_id',ondelete='RESTRICT'))
    actor_role:Mapped[str]=mapped_column(String(20))
    visibility:Mapped[str]=mapped_column(String(10))
    body:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utc_now)


class SupportEvent(Base):
    __tablename__='support_case_events'
    __table_args__=(UniqueConstraint('actor_id','request_key',name='uq_support_event_request'),UniqueConstraint('case_id','sequence',name='uq_support_sequence'),
        ForeignKeyConstraint(['message_id','case_id','actor_id','actor_role'],['support_case_messages.message_id','support_case_messages.case_id','support_case_messages.actor_id','support_case_messages.actor_role'],name='fk_support_message_event_identity',ondelete='RESTRICT'),
        CheckConstraint("actor_role IN ('admin','customer','shop_owner','driver') AND (action NOT IN ('internal_note','assignment','priority','status') OR actor_role='admin')",name='ck_support_event_actor'),
        CheckConstraint("(action IN ('message','internal_note') AND message_id IS NOT NULL) OR (action NOT IN ('message','internal_note') AND message_id IS NULL)",name='ck_support_event_message'),
        CheckConstraint("(action IN ('internal_note','assignment') AND visibility='internal') OR (action NOT IN ('internal_note','assignment') AND visibility='public')",name='ck_support_event_audience'),
        CheckConstraint('sequence>=1',name='ck_support_sequence'),CheckConstraint("visibility IN ('public','internal')",name='ck_support_event_visibility'),
        CheckConstraint("action IN ('created','message','internal_note','assignment','priority','status','reopened')",name='ck_support_event_action'),
        Index('ix_support_events','case_id','event_id'),OPTIONS)
    event_id:Mapped[int]=mapped_column(BigInteger,primary_key=True,autoincrement=True)
    case_id:Mapped[int]=mapped_column(BigInteger,ForeignKey('support_cases.case_id',ondelete='RESTRICT'))
    actor_id:Mapped[int]=mapped_column(BigInteger,ForeignKey('users.user_id',ondelete='RESTRICT'))
    actor_role:Mapped[str]=mapped_column(String(20))
    sequence:Mapped[int]=mapped_column(Integer)
    action:Mapped[str]=mapped_column(String(20))
    visibility:Mapped[str]=mapped_column(String(10))
    previous_value:Mapped[str|None]=mapped_column(String(100),nullable=True)
    new_value:Mapped[str|None]=mapped_column(String(100),nullable=True)
    reason:Mapped[str|None]=mapped_column(String(2000),nullable=True)
    message_id:Mapped[int|None]=mapped_column(BigInteger,ForeignKey('support_case_messages.message_id',ondelete='RESTRICT'),nullable=True)
    request_key:Mapped[str]=mapped_column(String(100,collation='utf8mb4_bin'))
    request_hash:Mapped[str]=mapped_column(String(64))
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utc_now)


class SupportReference(Base):
    __tablename__='support_case_references'
    __table_args__=(UniqueConstraint('case_id',name='uq_support_primary_reference'),
        CheckConstraint('(order_id IS NOT NULL)+(delivery_id IS NOT NULL)+(credit_account_id IS NOT NULL)+(ledger_entry_id IS NOT NULL)+(earning_id IS NOT NULL)=1',name='ck_support_one_reference'),OPTIONS)
    reference_id:Mapped[int]=mapped_column(BigInteger,primary_key=True,autoincrement=True)
    case_id:Mapped[int]=mapped_column(BigInteger,ForeignKey('support_cases.case_id',ondelete='RESTRICT'))
    order_id:Mapped[int|None]=mapped_column(BigInteger,ForeignKey('orders.order_id',ondelete='RESTRICT'),nullable=True)
    delivery_id:Mapped[int|None]=mapped_column(BigInteger,ForeignKey('delivery_requests.delivery_request_id',ondelete='RESTRICT'),nullable=True)
    credit_account_id:Mapped[int|None]=mapped_column(BigInteger,ForeignKey('credit_accounts.credit_account_id',ondelete='RESTRICT'),nullable=True)
    ledger_entry_id:Mapped[int|None]=mapped_column(BigInteger,ForeignKey('ledger_entries.entry_id',ondelete='RESTRICT'),nullable=True)
    earning_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('driver_earnings.earning_id',ondelete='RESTRICT'),nullable=True)


IMMUTABLE=(SupportMessage,SupportEvent,SupportReference)
@event.listens_for(Session,'before_flush')
def immutable_support(session,context,instances):
    if any(isinstance(row,IMMUTABLE) for row in session.dirty|session.deleted):raise ValueError('Support history is append-only')


@event.listens_for(Session,'do_orm_execute')
def immutable_support_bulk(state):
    if (state.is_update or state.is_delete) and getattr(getattr(state.statement,'table',None),'name',None) in {model.__tablename__ for model in IMMUTABLE}:
        raise ValueError('Support history is append-only')

# Purpose: Map enhancements records to database tables so SQLAlchemy can persist and relate application data.
"""Phase 3.1 storage foundations only; no new API or approval behavior.

Role authorization, document supersession/review, archival and optimistic version
updates remain service responsibilities before any new write API is enabled.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, ForeignKeyConstraint, Index,
    Integer, Numeric, SmallInteger, String, UniqueConstraint, text,
)
from sqlalchemy.dialects.mysql import CHAR, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Map customer address to the customer_addresses table for ORM queries and persistence.
class CustomerAddress(Base):
    __tablename__ = 'customer_addresses'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['users.user_id'],
            name='fk_address_user', ondelete='RESTRICT', onupdate='RESTRICT'),
        UniqueConstraint('address_id', 'user_id', name='uq_address_id_user'),
        UniqueConstraint('user_id','create_request_key',name='uq_address_create_request'),
        CheckConstraint('(create_request_key IS NULL AND create_request_hash IS NULL) OR (create_request_key IS NOT NULL AND create_request_hash IS NOT NULL)',name='ck_address_create_request'),
        Index('ix_address_user_archived', 'user_id', 'archived_at', 'address_id'),
        CheckConstraint('CHAR_LENGTH(TRIM(label)) > 0', name='ck_address_label'),
        CheckConstraint('CHAR_LENGTH(TRIM(recipient_name)) > 0', name='ck_address_recipient'),
        CheckConstraint('CHAR_LENGTH(TRIM(address_line)) > 0', name='ck_address_line'),
        CheckConstraint('(latitude IS NULL AND longitude IS NULL) OR '
            '(latitude IS NOT NULL AND longitude IS NOT NULL AND '
            'latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)',
            name='ck_address_coordinates'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
         'mysql_collate': 'utf8mb4_unicode_ci'},
    )
    # Use address id as the unique row identity for ORM lookups and related records.
    address_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    create_request_key: Mapped[str | None] = mapped_column(String(100,collation='utf8mb4_bin'),nullable=True)
    create_request_hash: Mapped[str | None] = mapped_column(String(64),nullable=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address_line: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Store latitude as an exact decimal so persisted financial values avoid binary floating-point rounding.
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    # Store longitude as an exact decimal so persisted financial values avoid binary floating-point rounding.
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False,
        server_default=text('CURRENT_TIMESTAMP(6)'))
    # Retain updated at for history, ordering, and time-based queries.
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False,
        server_default=text('CURRENT_TIMESTAMP(6)'))


# Map user preference to the user_preferences table for ORM queries and persistence.
class UserPreference(Base):
    __tablename__ = 'user_preferences'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['users.user_id'],
            name='fk_preference_user', ondelete='RESTRICT', onupdate='RESTRICT'),
        ForeignKeyConstraint(['preferred_address_id', 'user_id'],
            ['customer_addresses.address_id', 'customer_addresses.user_id'],
            name='fk_preference_owned_address', ondelete='RESTRICT', onupdate='RESTRICT'),
        Index('ix_preference_address_user', 'preferred_address_id', 'user_id'),
        CheckConstraint("theme IN ('light','dark','system')", name='ck_preference_theme'),
        CheckConstraint('version >= 1', name='ck_preference_version'),
        CheckConstraint('in_app_notifications IN (0,1)', name='ck_preference_in_app'),
        CheckConstraint('email_notifications IS NULL OR email_notifications IN (0,1)',
            name='ck_preference_email'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
         'mysql_collate': 'utf8mb4_unicode_ci'},
    )
    # Use user id as the unique row identity for ORM lookups and related records.
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    theme: Mapped[str] = mapped_column(String(10), nullable=False, server_default='system')
    in_app_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False,
        server_default=text('1'))
    email_notifications: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    preferred_address_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    # Retain updated at for history, ordering, and time-based queries.
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False,
        server_default=text('CURRENT_TIMESTAMP(6)'))


# Map business setting to the business_settings table for ORM queries and persistence.
class BusinessSetting(Base):
    __tablename__ = 'business_settings'
    __table_args__ = (
        ForeignKeyConstraint(['business_id'], ['businesses.business_id'],
            name='fk_setting_business', ondelete='RESTRICT', onupdate='RESTRICT'),
        CheckConstraint('default_credit_limit IS NULL OR default_credit_limit >= 0',
            name='ck_setting_credit_limit'),
        CheckConstraint('default_payment_term_days IS NULL OR default_payment_term_days > 0',
            name='ck_setting_payment_term'),
        CheckConstraint('delivery_radius_km IS NULL OR delivery_radius_km > 0',
            name='ck_setting_delivery_radius'),
        CheckConstraint('delivery_enabled IN (0,1)', name='ck_setting_delivery_enabled'),
        CheckConstraint('version >= 1', name='ck_setting_version'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
         'mysql_collate': 'utf8mb4_unicode_ci'},
    )
    # Use business id as the unique row identity for ORM lookups and related records.
    business_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    # Store default credit limit as an exact decimal so persisted financial values avoid binary floating-point rounding.
    default_credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    default_payment_term_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False,
        server_default=text('0'))
    # Store delivery radius km as an exact decimal so persisted financial values avoid binary floating-point rounding.
    delivery_radius_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    # Retain updated at for history, ordering, and time-based queries.
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False,
        server_default=text('CURRENT_TIMESTAMP(6)'))


# Map vehicle to the vehicles table for ORM queries and persistence.
class Vehicle(Base):
    __tablename__ = 'vehicles'
    __table_args__ = (
        ForeignKeyConstraint(['driver_user_id'], ['driver_profiles.user_id'],
            name='fk_vehicle_driver', ondelete='RESTRICT', onupdate='RESTRICT'),
        UniqueConstraint('vehicle_id', 'driver_user_id', name='uq_vehicle_id_driver'),
        Index('ix_vehicle_driver_lifecycle', 'driver_user_id', 'lifecycle_status', 'vehicle_id'),
        CheckConstraint('CHAR_LENGTH(TRIM(vehicle_type)) > 0', name='ck_vehicle_type'),
        CheckConstraint('CHAR_LENGTH(TRIM(registration_reference)) > 0', name='ck_vehicle_registration'),
        CheckConstraint('model_year IS NULL OR model_year BETWEEN 1900 AND 2100',
            name='ck_vehicle_year'),
        CheckConstraint("lifecycle_status IN ('active','retired')", name='ck_vehicle_lifecycle'),
        CheckConstraint("source IN ('submitted','legacy')", name='ck_vehicle_source'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
         'mysql_collate': 'utf8mb4_unicode_ci'},
    )
    # Use vehicle id as the unique row identity for ORM lookups and related records.
    vehicle_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    driver_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(50), nullable=False)
    registration_reference: Mapped[str] = mapped_column(String(50), nullable=False)
    make: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    image_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Retain lifecycle status so workflow checks can decide which operations are currently allowed.
    lifecycle_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default='active')
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default='submitted')
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False,
        server_default=text('CURRENT_TIMESTAMP(6)'))
    # Retain updated at for history, ordering, and time-based queries.
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False,
        server_default=text('CURRENT_TIMESTAMP(6)'))


# Map vehicle document to the vehicle_documents table for ORM queries and persistence.
class VehicleDocument(Base):
    __tablename__ = 'vehicle_documents'
    __table_args__ = (
        ForeignKeyConstraint(['vehicle_id'], ['vehicles.vehicle_id'],
            name='fk_document_vehicle', ondelete='RESTRICT', onupdate='RESTRICT'),
        ForeignKeyConstraint(['reviewed_by'], ['users.user_id'],
            name='fk_document_reviewer', ondelete='RESTRICT', onupdate='RESTRICT'),
        ForeignKeyConstraint(['supersedes_document_id', 'vehicle_id'],
            ['vehicle_documents.document_id', 'vehicle_documents.vehicle_id'],
            name='fk_document_superseded_vehicle', ondelete='RESTRICT', onupdate='RESTRICT'),
        UniqueConstraint('document_id', 'vehicle_id', name='uq_document_id_vehicle'),
        UniqueConstraint('supersedes_document_id', name='uq_document_supersedes'),
        Index('ix_document_vehicle_type_created', 'vehicle_id', 'document_type', 'created_at', 'document_id'),
        Index('ix_document_review_expiry', 'review_status', 'expires_on', 'document_id'),
        Index('ix_document_reviewer', 'reviewed_by'),
        # The single-column unique cannot support the two-column FK by itself.
        Index('ix_document_supersedes_vehicle', 'supersedes_document_id', 'vehicle_id'),
        CheckConstraint("document_type IN ('registration','insurance','revenue_license')",
            name='ck_document_type'),
        CheckConstraint("review_status IN ('pending','approved','rejected')",
            name='ck_document_review_status'),
        CheckConstraint('size_bytes > 0', name='ck_document_size'),
        CheckConstraint('CHAR_LENGTH(TRIM(storage_key)) > 0', name='ck_document_storage'),
        # MySQL forbids CHECK expressions referencing AUTO_INCREMENT columns.
        # Reject self-supersession/cycles in the future authorized write service.
        CheckConstraint("(review_status = 'pending' AND reviewed_by IS NULL AND reviewed_at IS NULL "
            "AND rejection_reason IS NULL) OR (review_status = 'approved' AND reviewed_by IS NOT NULL "
            "AND reviewed_at IS NOT NULL AND rejection_reason IS NULL) OR (review_status = 'rejected' "
            "AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL AND rejection_reason IS NOT NULL "
            "AND CHAR_LENGTH(TRIM(rejection_reason)) > 0)", name='ck_document_review_state'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
         'mysql_collate': 'utf8mb4_unicode_ci'},
    )
    # Use document id as the unique row identity for ORM lookups and related records.
    document_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content_sha256: Mapped[str] = mapped_column(CHAR(64, charset='ascii'), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Retain review status so workflow checks can decide which operations are currently allowed.
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default='pending')
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_document_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Retain created at for history, ordering, and time-based queries.
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False,
        server_default=text('CURRENT_TIMESTAMP(6)'))

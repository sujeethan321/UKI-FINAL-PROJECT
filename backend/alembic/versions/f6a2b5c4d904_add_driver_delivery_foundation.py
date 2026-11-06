"""Add driver profiles and business-owned deliveries; no data backfill/approval.
Revision ID: f6a2b5c4d904
Revises: e5f1a4b3c803
"""
from alembic import op
import sqlalchemy as sa
revision = "f6a2b5c4d904"
down_revision = "e5f1a4b3c803"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("driver_profiles",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("vehicle_type", sa.String(50)), sa.Column("registration_reference", sa.String(50)),
        sa.Column("reviewed_by", sa.BigInteger(), sa.ForeignKey("users.user_id", ondelete="RESTRICT")),
        sa.Column("reviewed_at", sa.DateTime()), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("approval_status IN ('pending','approved','rejected','suspended')", name="ck_driver_approval_status"),
        sa.CheckConstraint("approval_status = 'pending' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)", name="ck_driver_review_required"),
        sa.CheckConstraint("(vehicle_type IS NULL AND registration_reference IS NULL) OR (vehicle_type IS NOT NULL AND registration_reference IS NOT NULL)", name="ck_driver_vehicle_pair"))
    op.create_table("delivery_requests",
        sa.Column("delivery_request_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("reference", sa.String(50), nullable=False, unique=True),
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey("businesses.business_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("pickup_area", sa.String(160), nullable=False), sa.Column("delivery_area", sa.String(160), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="available"),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('available','assigned','picked_up','in_transit','delivered','cancelled')", name="ck_delivery_status"))
    op.create_index("ix_delivery_status_created", "delivery_requests", ["status","created_at","delivery_request_id"])
    op.create_index("ix_delivery_business", "delivery_requests", ["business_id"])
    op.create_table("delivery_assignments",
        sa.Column("assignment_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("delivery_request_id", sa.BigInteger(), sa.ForeignKey("delivery_requests.delivery_request_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("driver_user_id", sa.BigInteger(), sa.ForeignKey("driver_profiles.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("delivery_request_id", name="uq_delivery_assignment_request"))
    op.create_index("ix_assignment_driver_date", "delivery_assignments", ["driver_user_id","assigned_at","assignment_id"])


def downgrade():
    raise RuntimeError("Delivery assignments and review records must be preserved; use an additive forward migration")

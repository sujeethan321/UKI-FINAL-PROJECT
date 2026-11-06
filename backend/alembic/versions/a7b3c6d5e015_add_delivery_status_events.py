"""Persist delivery progress without fabricating historical events."""
from alembic import op
import sqlalchemy as sa

revision = "a7b3c6d5e015"
down_revision = "f6a2b5c4d904"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("delivery_status_events",
        sa.Column("event_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("delivery_request_id", sa.BigInteger(), sa.ForeignKey("delivery_requests.delivery_request_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("delivery_request_id", "status", name="uq_delivery_event_status"),
        sa.CheckConstraint("status IN ('picked_up','in_transit','delivered','cancelled')", name="ck_delivery_event_status"))


def downgrade():
    raise RuntimeError("Preserve delivery audit events; use an additive forward migration")

"""Add QR join records without changing ledger or existing invitation data.

Duplicate audit before any DDL (read-only):
SELECT business_id, user_id, COUNT(*) AS copies FROM customer_profiles
WHERE user_id IS NOT NULL GROUP BY business_id, user_id HAVING COUNT(*) > 1;
Any rows returned block this migration for operator review.
"""
from alembic import op
import sqlalchemy as sa

revision = "7b9e4d2c8a15"
down_revision = "6e3f2c1a9b04"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    duplicate = connection.execute(sa.text(
        "SELECT 1 FROM customer_profiles WHERE user_id IS NOT NULL "
        "GROUP BY business_id, user_id HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if duplicate is not None:
        raise RuntimeError("Duplicate linked customer profiles block the QR join migration")
    op.create_table(
        "business_join_links",
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey("businesses.business_id", name="fk_business_join_business", ondelete="RESTRICT"), primary_key=True),
        sa.Column("public_code", sa.String(32, collation="utf8mb4_bin"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("public_code", name="uq_business_join_public_code"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_table(
        "customer_join_requests",
        sa.Column("request_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("business_id", sa.BigInteger(), sa.ForeignKey("businesses.business_id", name="fk_customer_join_business", ondelete="RESTRICT"), nullable=False),
        sa.Column("customer_user_id", sa.BigInteger(), sa.ForeignKey("users.user_id", name="fk_customer_join_user", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by", sa.BigInteger(), sa.ForeignKey("users.user_id", name="fk_customer_join_decider", ondelete="RESTRICT"), nullable=True),
        sa.UniqueConstraint("business_id", "customer_user_id", name="uq_customer_join_business_user"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')", name="ck_customer_join_status"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_customer_join_business_status_created", "customer_join_requests", ["business_id", "status", "created_at"])
    op.create_unique_constraint("uq_customer_profile_business_user", "customer_profiles", ["business_id", "user_id"])


def downgrade():
    raise RuntimeError("Downgrade would discard QR join requests; use reviewed backup recovery")

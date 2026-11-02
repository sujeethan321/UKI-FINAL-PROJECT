
"""Add business approval audit records.

Revision ID: b2a1c4d6e8f0
Revises: 79d8d51548c6
"""

from alembic import op
import sqlalchemy as sa


revision = "b2a1c4d6e8f0"
down_revision = "79d8d51548c6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "business_approval_audits",
        sa.Column(
            "audit_id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "business_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "businesses.business_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "admin_user_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "users.user_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "decision",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "previous_status",
            sa.String(30),
            nullable=False,
        ),
        sa.Column(
            "new_status",
            sa.String(30),
            nullable=False,
        ),
        sa.Column(
            "review_note",
            sa.String(500),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_business_approval_audits_business_id",
        "business_approval_audits",
        ["business_id"],
    )


def downgrade():
    op.drop_index(
        "ix_business_approval_audits_business_id",
        table_name="business_approval_audits",
    )

    op.drop_table("business_approval_audits")

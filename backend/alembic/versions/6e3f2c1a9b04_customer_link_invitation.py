"""Store hashed six-digit customer linking codes; no existing data is changed."""
from alembic import op
import sqlalchemy as sa

revision = "6e3f2c1a9b04"
down_revision = "14c0d3e2f782"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "customer_link_invitations",
        sa.Column("customer_id", sa.BigInteger(), primary_key=True),
        sa.Column("business_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_user_id", sa.BigInteger(), nullable=False),
        sa.Column("issuer_user_id", sa.BigInteger(), nullable=False),
        sa.Column("code_digest", sa.String(64, collation="utf8mb4_bin"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customer_profiles.customer_id"], name="fk_link_invitation_profile", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.business_id"], name="fk_link_invitation_business", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.user_id"], name="fk_link_invitation_recipient", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["issuer_user_id"], ["users.user_id"], name="fk_link_invitation_issuer", ondelete="RESTRICT"),
        sa.UniqueConstraint("code_digest", name="uq_link_invitation_code_digest"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_customer_link_recipient_expiry", "customer_link_invitations", ["recipient_user_id", "expires_at"])


def downgrade():
    raise RuntimeError("Downgrade would discard active invitations; use reviewed backup recovery")

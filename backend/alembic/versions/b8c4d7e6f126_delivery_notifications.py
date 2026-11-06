"""Expand notification checks for delivery events; preserve existing records."""
from alembic import op
revision = "b8c4d7e6f126"
down_revision = "a7b3c6d5e015"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("ALTER TABLE notifications DROP CHECK ck_notification_type, ADD CONSTRAINT ck_notification_type CHECK (notification_type IN ('credit_sale_recorded', 'repayment_recorded', 'payment_reminder_recorded', 'business_approved', 'business_rejected', 'delivery_assigned', 'delivery_picked_up', 'delivery_in_transit', 'delivery_delivered'))")
    op.execute("ALTER TABLE notifications DROP CHECK ck_notification_entity_type, ADD CONSTRAINT ck_notification_entity_type CHECK ((notification_type IN ('credit_sale_recorded', 'repayment_recorded') AND related_entity_type = 'ledger_entry') OR (notification_type = 'payment_reminder_recorded' AND related_entity_type = 'payment_reminder') OR (notification_type IN ('business_approved', 'business_rejected') AND related_entity_type = 'business_approval_audit') OR (notification_type IN ('delivery_assigned', 'delivery_picked_up', 'delivery_in_transit', 'delivery_delivered') AND related_entity_type = 'delivery_request'))")

def downgrade():
    raise RuntimeError("Preserve delivery notifications; use a forward migration")

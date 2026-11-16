"""Extend existing notifications for order-linked delivery coordination."""
from alembic import op

revision = 'f2a8b1c0d560'
down_revision = 'e1f7a0b9c459'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('ck_notification_type', 'notifications', type_='check')
    op.create_check_constraint('ck_notification_type', 'notifications', "notification_type IN ('credit_sale_recorded', 'repayment_recorded', 'payment_reminder_recorded', 'business_approved', 'business_rejected', 'delivery_requested', 'delivery_cancelled', 'delivery_assigned', 'delivery_picked_up', 'delivery_in_transit', 'delivery_delivered', 'order_submitted', 'order_approved', 'order_rejected', 'order_processing', 'order_completed', 'order_cancelled')")
    op.drop_constraint('ck_notification_entity_type', 'notifications', type_='check')
    op.create_check_constraint('ck_notification_entity_type', 'notifications', "(notification_type IN ('credit_sale_recorded', 'repayment_recorded') AND related_entity_type = 'ledger_entry') OR (notification_type = 'payment_reminder_recorded' AND related_entity_type = 'payment_reminder') OR (notification_type IN ('business_approved', 'business_rejected') AND related_entity_type = 'business_approval_audit') OR (notification_type IN ('delivery_requested', 'delivery_cancelled', 'delivery_assigned', 'delivery_picked_up', 'delivery_in_transit', 'delivery_delivered') AND related_entity_type IN ('delivery_request', 'order')) OR (notification_type IN ('order_submitted', 'order_approved', 'order_rejected', 'order_processing', 'order_completed', 'order_cancelled') AND related_entity_type = 'order')")


def downgrade():
    raise RuntimeError('Preserve notification history; use a forward migration')

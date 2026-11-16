"""Administrator audit records and Driver review notifications; no data deletion."""
from alembic import op
import sqlalchemy as sa
revision='03b9c2d1e671'
down_revision='f2a8b1c0d560'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('admin_audits',
        sa.Column('audit_id',sa.BigInteger(),primary_key=True,autoincrement=True),
        sa.Column('admin_user_id',sa.BigInteger(),sa.ForeignKey('users.user_id',ondelete='RESTRICT'),nullable=False),
        sa.Column('target_type',sa.String(20),nullable=False),
        sa.Column('target_id',sa.BigInteger(),nullable=False),
        sa.Column('action',sa.String(30),nullable=False),
        sa.Column('previous_state',sa.String(30),nullable=True),
        sa.Column('new_state',sa.String(30),nullable=False),
        sa.Column('reason',sa.String(500),nullable=True),
        sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.CheckConstraint("target_type IN ('user','driver')",name='ck_admin_audit_target'),
        sa.CheckConstraint("action IN ('driver_approved','driver_rejected','account_suspended','account_reactivated','admin_provisioned')",name='ck_admin_audit_action'),
        sa.CheckConstraint('target_id > 0',name='ck_admin_audit_target_id'))
    op.create_index('ix_admin_audit_created','admin_audits',['created_at','audit_id'])
    op.create_index('ix_admin_audit_target','admin_audits',['target_type','target_id','audit_id'])
    op.drop_constraint('ck_notification_type','notifications',type_='check')
    op.create_check_constraint('ck_notification_type','notifications',"notification_type IN ('driver_approved', 'driver_rejected', 'credit_sale_recorded', 'repayment_recorded', 'payment_reminder_recorded', 'business_approved', 'business_rejected', 'delivery_requested', 'delivery_cancelled', 'delivery_assigned', 'delivery_picked_up', 'delivery_in_transit', 'delivery_delivered', 'order_submitted', 'order_approved', 'order_rejected', 'order_processing', 'order_completed', 'order_cancelled')")
    op.drop_constraint('ck_notification_entity_type','notifications',type_='check')
    op.create_check_constraint('ck_notification_entity_type','notifications',"(notification_type IN ('driver_approved', 'driver_rejected') AND related_entity_type = 'admin_audit') OR (notification_type IN ('credit_sale_recorded', 'repayment_recorded') AND related_entity_type = 'ledger_entry') OR (notification_type = 'payment_reminder_recorded' AND related_entity_type = 'payment_reminder') OR (notification_type IN ('business_approved', 'business_rejected') AND related_entity_type = 'business_approval_audit') OR (notification_type IN ('delivery_requested', 'delivery_cancelled', 'delivery_assigned', 'delivery_picked_up', 'delivery_in_transit', 'delivery_delivered') AND related_entity_type IN ('delivery_request', 'order')) OR (notification_type IN ('order_submitted', 'order_approved', 'order_rejected', 'order_processing', 'order_completed', 'order_cancelled') AND related_entity_type = 'order')")

def downgrade():
    raise RuntimeError('Preserve administrative and notification history; use a forward migration')

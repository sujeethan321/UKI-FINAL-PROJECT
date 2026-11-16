"""Dedicated supplied-connection-only environment; no application engine fallback."""
from alembic import context
from demo_qr_migration_guard import MigrationPermit, Stop

config = context.config
permit = config.attributes.get("demo_qr_permit")
if context.is_offline_mode() or not isinstance(permit, MigrationPermit):
    raise Stop("alembic_permit")
connection = permit.enter(config)
context.configure(connection=connection, target_metadata=None, transactional_ddl=False)
with context.begin_transaction():
    context.run_migrations()

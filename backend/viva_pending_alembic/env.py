"""Dedicated exact-connection environment; never loads app settings/engine."""
from alembic import context
cfg=context.config
if context.is_offline_mode():raise RuntimeError('Offline SQL execution path refused')
conn=cfg.attributes.get('connection');database=cfg.attributes.get('viva_target');account=cfg.attributes.get('viva_account')
allowed={'lankapex_viva_db':'lankapex_viva_migrator','lankapex_migration_verify_viva20261124':'lankapex_viva_rehearsal'}
if database not in allowed or account!=allowed[database] or conn is None:raise RuntimeError('Exact VIVA workflow connection required')
url=conn.engine.url
if (url.host,url.port,url.database,url.username)!=('127.0.0.1',3306,database,account) or conn.in_transaction():raise RuntimeError('Target/transaction mismatch')
if cfg.attributes.get('viva_stage') not in ('bf38d2a90176','c04d9e7a6201','d15a8c902e64'):raise RuntimeError('Pinned stage required')
cfg.attributes['viva_identity'](conn.connection.driver_connection,database,account)
conn.connection.driver_connection.commit()
parents={'bf38d2a90176':'ae2b7c5f1d48','c04d9e7a6201':'bf38d2a90176','d15a8c902e64':'c04d9e7a6201'}
if cfg.attributes.get('viva_parent')!=parents[cfg.attributes['viva_stage']]:raise RuntimeError('Pinned parent required')
if list(conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars())!=[cfg.attributes['viva_parent']]:raise RuntimeError('Fresh parent revision differs')
conn.commit()
context.configure(connection=conn,compare_type=True)
with context.begin_transaction():context.run_migrations()

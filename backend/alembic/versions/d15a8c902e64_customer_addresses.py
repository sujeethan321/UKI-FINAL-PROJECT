"""CA-02 additive address idempotency and immutable order destinations.

No historical DML/backfill. MySQL DDL commits: preserve partial state on failure.
Runtime receives no DDL/TRIGGER privileges. Separate DBA deployment required.
"""
from alembic import op
import sqlalchemy as sa
revision='d15a8c902e64'
down_revision='c04d9e7a6201'
branch_labels=depends_on=None

def upgrade():
    conn=op.get_bind()
    if conn.dialect.name!='mysql':raise RuntimeError('MySQL 8 required')
    import re
    version=str(conn.scalar(sa.text('SELECT VERSION()')))
    parsed=re.match(r'^8\.(\d+)\.(\d+)',version)
    if not parsed or 'mariadb' in version.lower() or (int(parsed[1])==0 and int(parsed[2])<16):raise RuntimeError('Enforced CHECK constraints required')
    if list(conn.scalars(sa.text('SELECT version_num FROM alembic_version')))!=['c04d9e7a6201']:raise RuntimeError('Unexpected parent revision')
    inspector=sa.inspect(conn)
    if 'order_delivery_addresses' in inspector.get_table_names():raise RuntimeError('Existing destination table; preserve state')
    if {'create_request_key','create_request_hash'}.intersection(c['name'] for c in inspector.get_columns('customer_addresses')):raise RuntimeError('Partial migration; preserve state')
    enforcement=conn.execute(sa.text('SELECT @@SESSION.foreign_key_checks,@@SESSION.unique_checks,@@SESSION.sql_mode')).one()
    if enforcement[0]!=1 or enforcement[1]!=1 or not {'STRICT_TRANS_TABLES','STRICT_ALL_TABLES'}.intersection(str(enforcement[2]).split(',')):raise RuntimeError('Strict enforcement required')
    op.add_column('customer_addresses',sa.Column('create_request_key',sa.String(100,collation='utf8mb4_bin'),nullable=True))
    op.add_column('customer_addresses',sa.Column('create_request_hash',sa.String(64),nullable=True))
    op.create_unique_constraint('uq_address_create_request','customer_addresses',['user_id','create_request_key'])
    op.create_check_constraint('ck_address_create_request','customer_addresses','(create_request_key IS NULL AND create_request_hash IS NULL) OR (create_request_key IS NOT NULL AND create_request_hash IS NOT NULL)')
    op.create_unique_constraint('uq_order_id_customer','orders',['order_id','customer_user_id'])
    op.execute('CREATE TABLE order_delivery_addresses (\n\torder_id BIGINT NOT NULL, \n\tcustomer_user_id BIGINT NOT NULL, \n\tsource_address_id BIGINT NOT NULL, \n\trecipient_name VARCHAR(150) NOT NULL, \n\tphone VARCHAR(20), \n\taddress_line VARCHAR(500) NOT NULL, \n\tcity VARCHAR(100), \n\taccepted_version INTEGER NOT NULL, \n\taddress_digest VARCHAR(64) NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tPRIMARY KEY (order_id), \n\tCONSTRAINT fk_oda_order_customer FOREIGN KEY(order_id, customer_user_id) REFERENCES orders (order_id, customer_user_id) ON DELETE RESTRICT ON UPDATE RESTRICT, \n\tCONSTRAINT fk_oda_address_customer FOREIGN KEY(source_address_id, customer_user_id) REFERENCES customer_addresses (address_id, user_id) ON DELETE RESTRICT ON UPDATE RESTRICT, \n\tCONSTRAINT ck_oda_version CHECK (accepted_version>=1), \n\tCONSTRAINT ck_oda_text CHECK (CHAR_LENGTH(TRIM(recipient_name))>0 AND CHAR_LENGTH(TRIM(address_line))>0)\n)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci')

    op.create_index('ix_oda_order_customer','order_delivery_addresses',['order_id','customer_user_id'])
    op.create_index('ix_oda_source_customer','order_delivery_addresses',['source_address_id','customer_user_id'])
    for action in ('UPDATE','DELETE'):
        op.execute("CREATE TRIGGER ca_order_destination_"+action.lower()+"_deny BEFORE "+action+" ON order_delivery_addresses FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Order destinations are immutable'")

def downgrade():
    raise RuntimeError('Destructive downgrade refused: preserve address and order history; use reviewed recovery')

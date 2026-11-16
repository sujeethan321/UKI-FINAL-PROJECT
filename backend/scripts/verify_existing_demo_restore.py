"""Exact existing-restore verification/rehearsal. Offline by default; no app imports."""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import demo_qr_recovery as recovery
import demo_qr_migration_guard as migration

SOURCE = recovery.SOURCE
RESTORE = recovery.EXISTING_RESTORE
START, END = recovery.REVISION, migration.END
MINIMUM = migration.preservation.MINIMUM_MIGRATOR_RIGHTS
require = recovery.require


@dataclass(frozen=True)
class RestorePolicy:
    account: str
    rights: frozenset

    def __post_init__(self):
        require(isinstance(self.account, str) and re.fullmatch(
            r'[A-Za-z0-9_]{1,32}@localhost', self.account) is not None, 'restore_account_contract')
        require(self.account.split('@')[0] not in ('root', 'mysql', 'lankapex_demo_app',
                'lankapex_demo_migrator', 'lankapex_demo_qr_migrator'), 'restore_account_contract')
        require(self.rights in (frozenset({'SELECT'}), MINIMUM, MINIMUM | {'DELETE'}),
                'restore_grant_contract')


def source_hashes():
    values = recovery.LiveRecoveryAdapter.current_source_hashes(None)
    values.update(migration.source_hashes())
    path = Path(__file__).resolve()
    values[str(path.relative_to(recovery.ROOT)).replace('\\', '/')] = hashlib.sha256(path.read_bytes()).hexdigest()
    return values


class ExistingRestoreAdapter(recovery.LiveRecoveryAdapter):
    def __init__(self, policy, tls_ca, *, connector=None, prompt=None):
        super().__init__(None, connector or recovery.connect_verified_mysql,
                         prompt or recovery.secure_password, tls_ca)
        self.policy = policy
        self.after = False
        self.secrets = {}

    def capture_policy(self, database):
        require(database in (SOURCE, RESTORE), 'target')
        if database == SOURCE:
            return recovery.SOURCE_ACCOUNT, {'SELECT','INSERT','UPDATE','DELETE'}, START, recovery.TABLES
        return (self.policy.account, self.policy.rights, END if self.after else START,
                recovery.TABLES | (recovery.QR_TABLES if self.after else set()))

    def _connection(self, database):
        account, _rights, _revision, _tables = self.capture_policy(database)
        if database not in self.secrets:
            # Fixed label only. Never echo password, URL or provider exception.
            print('INFO: hidden password required for ' + ('source_runtime' if database == SOURCE else 'approved_restore_account'))
            self.secrets[database] = self.password()
            require(isinstance(self.secrets[database], str) and self.secrets[database], 'credential_unavailable')
        return self.connect(database, account.split('@')[0], self.secrets[database], self.tls_ca)

    def _identity(self, conn, database, empty=False):
        require(not empty, 'existing_restore_not_empty_contract')
        account, rights, _revision, _tables = self.capture_policy(database)
        with conn.cursor() as cursor:
            cursor.execute('SELECT DATABASE(), CURRENT_USER(), @@port, CURRENT_ROLE(), @@GLOBAL.partial_revokes, @@SESSION.sql_mode, @@SESSION.foreign_key_checks')
            db, current, port, roles, partial, mode, checks = cursor.fetchone()
            require((db,current,port,roles,partial,checks) == (database,account,3306,'NONE',0,1), 'actual_identity')
            require('STRICT_TRANS_TABLES' in mode.split(',') and not
                    {'ANSI_QUOTES','NO_BACKSLASH_ESCAPES'} & set(mode.split(',')), 'mysql_settings')
            cursor.execute('SHOW GRANTS FOR CURRENT_USER()')
            actual = set()
            for row in cursor.fetchall():
                grant = row[0]
                if re.fullmatch(r'GRANT USAGE ON \*\.\* TO [^ ]+', grant):
                    continue
                match = re.fullmatch(r'GRANT ([A-Z, ]+) ON `([^`]+)`\.\* TO [^ ]+', grant)
                require(match is not None and match[2] == database.replace('_', '\\_'), 'grant_scope')
                actual.update(match[1].split(', '))
            require(actual == rights, 'exact_grants')
            return sorted(actual)

    def validate_capture(self, result, database):
        recovery.validate_inventory_snapshot(result, database, *self.capture_policy(database))

    def enrich_capture(self, connection, inspector, result, records, database):
        # Include columns/defaults, indexes, constraints, FK actions and checks
        # using the existing expanded metadata queries, in this same snapshot.
        data = {key: [tuple(row) for row in connection.exec_driver_sql(query)]
                for key,query in migration.META.items()}
        require(all([tuple(row) for row in connection.exec_driver_sql(query)] == data[key]
                    for key,query in migration.META.items()), 'metadata_drift')
        normalized = dict(data)
        normalized['keys'] = []
        for row in data['keys']:
            values = list(row)
            if values[5] is not None:
                require(values[4] in (None,database), 'foreign_key_scope')
                values[4] = '<verified-self-schema>'
            normalized['keys'].append(tuple(values))
        result['comparison_schema_sha256'] = migration.schema_digest(normalized)
        result['comparison_original_schema_sha256'] = migration.schema_digest(normalized, original_only=True)
        unique = inspector.get_unique_constraints('customer_profiles')
        if database == RESTORE and self.after:
            from check_demo_backend import validate_schema
            validate_schema(inspector, [END], migration.preservation.ORIGINAL | recovery.QR_TABLES)
            migration.validate_qr_columns(data)
            result['qr_structure_complete'] = True
        else:
            require(not any(c.get('name') == 'uq_customer_profile_business_user'
                    or set(c.get('column_names', [])) == {'business_id','user_id'}
                    for c in unique), 'partial_qr_schema')
            result['qr_structure_complete'] = False


def compare_existing(source, restored, policy):
    recovery.validate_snapshot(source)
    recovery.validate_inventory_snapshot(restored, RESTORE, policy.account, policy.rights,
                                         START, recovery.TABLES)
    for key in ('revision','tables','financial_fingerprints','inventory_fingerprints',
                'foreign_key_orphans','duplicate_profiles','database_defaults','versions',
                'source_hashes','comparison_schema_sha256'):
        require(key in source and key in restored and source[key] == restored[key], 'preservation_mismatch')
    require(not source.get('qr_structure_complete') and not restored.get('qr_structure_complete'), 'partial_qr_schema')


def compare_rehearsal(before, after, policy):
    recovery.validate_inventory_snapshot(before, RESTORE, policy.account, policy.rights, START, recovery.TABLES)
    recovery.validate_inventory_snapshot(after, RESTORE, policy.account, policy.rights,
                                         END, recovery.TABLES | recovery.QR_TABLES)
    for name in recovery.TABLES - {'alembic_version'}:
        for key in ('rows','sha256'):
            require(before['tables'][name][key] == after['tables'][name][key], 'full_row_preservation')
    require(after['tables']['alembic_version']['rows'] == 1, 'revision')
    require(all(after['tables'][name]['rows'] == 0 for name in recovery.QR_TABLES), 'new_qr_rows')
    for key in ('financial_fingerprints','inventory_fingerprints','database_defaults','source_hashes','versions'):
        require(before[key] == after[key], 'financial_or_source_preservation')
    require(before['comparison_schema_sha256'] == after['comparison_original_schema_sha256']
            and after.get('qr_structure_complete') is True, 'schema_preservation')
    new_names = {table+':'+name for table,name in (
        ('business_join_links','fk_business_join_business'),
        ('customer_join_requests','fk_customer_join_business'),
        ('customer_join_requests','fk_customer_join_user'),
        ('customer_join_requests','fk_customer_join_decider'))}
    require(set(after['foreign_key_orphans']) == set(before['foreign_key_orphans']) | new_names,
            'foreign_key_inventory')


class RehearsalGate(migration.SQLGate):
    """Reuse the exact five-write sequence; never bind the source connection."""
    def __init__(self, connection, policy):
        super().__init__()
        self.connection = connection
        self.policy = policy

    def before_cursor(self, conn, cursor, statement, params, context, many):
        url = conn.engine.url
        require(conn is self.connection and (url.host,url.port,url.database,url.username) ==
                ('127.0.0.1',3306,RESTORE,self.policy.account.split('@')[0]), 'rehearsal_connection')
        super().before_cursor(conn,cursor,statement,params,context,many)


def rehearse_once(adapter):
    """Only reached after full comparison, explicit authorization and exact grants."""
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    require(adapter.policy.rights in (MINIMUM, MINIMUM | {'DELETE'}), 'rehearsal_grants')
    account = adapter.policy.account.split('@')[0]
    url = sa.engine.URL.create('mysql+pymysql',host='127.0.0.1',port=3306,
                              database=RESTORE,username=account)
    engine = sa.create_engine(url, creator=lambda:adapter._connection(RESTORE),
                             poolclass=sa.pool.NullPool,echo=False,hide_parameters=True)
    try:
        with engine.connect() as conn:
            native = conn.connection.driver_connection
            adapter._identity(native,RESTORE)
            require(conn.exec_driver_sql('SELECT version_num FROM alembic_version').scalars().all() == [START], 'revision')
            lock = RESTORE + '_qr_rehearsal'
            locked = False
            gate = None
            try:
                require(conn.exec_driver_sql('SELECT GET_LOCK(%s,0)',(lock,)).scalar_one() == 1, 'rehearsal_lock')
                locked = True
                conn.rollback()
                conn.exec_driver_sql('SET SESSION lock_wait_timeout = 15')
                conn.rollback()
                gate = RehearsalGate(conn,adapter.policy)
                gate.executing = True
                sa.event.listen(engine,'before_cursor_execute',gate.before_cursor)
                require(conn.exec_driver_sql(migration.AUDIT).first() is None, 'duplicate_profiles')
                conn.rollback()
                gate.writes_enabled = True
                migration.source_hashes()  # Verify exact reviewed migration bytes/chain.
                upgrade = runpy.run_path(str(migration.MIGRATION))['upgrade']
                with Operations.context(MigrationContext.configure(conn,opts={'transactional_ddl':False})):
                    upgrade()
                changed = conn.exec_driver_sql("UPDATE alembic_version SET version_num='7b9e4d2c8a15' WHERE alembic_version.version_num = '6e3f2c1a9b04'")
                require(changed.rowcount == 1 and gate.position == len(gate.writes), 'migration_sequence')
                conn.commit()
            finally:
                if gate is not None:
                    gate.writes_enabled = False
                    sa.event.remove(engine,'before_cursor_execute',gate.before_cursor)
                if locked:
                    conn.rollback()
                    require(conn.exec_driver_sql('SELECT RELEASE_LOCK(%s)',(lock,)).scalar_one() == 1, 'rehearsal_lock_release')
                    conn.rollback()
    finally:
        engine.dispose()


def verify(adapter, *, execute=False, confirm_source=None, confirm_restore=None,
           writer_ddl_pause=False, target_administration_pause=False, rehearsal=False,
           confirm_revision=None, approved_rehearsal=False):
    if not execute:
        return {'status':'OFFLINE_PREPARATION'}
    require(confirm_source == SOURCE and confirm_restore == RESTORE, 'target_confirmation')
    require(writer_ddl_pause and target_administration_pause, 'consistent_read_boundary')
    require(not rehearsal or (approved_rehearsal and confirm_revision == END), 'rehearsal_confirmation')
    hashes = source_hashes()
    source = adapter.snapshot(SOURCE)
    before = adapter.snapshot(RESTORE)
    compare_existing(source,before,adapter.policy)
    require(source_hashes() == hashes, 'source_binding')
    if rehearsal:
        rehearse_once(adapter)
        adapter.after = True
        after = adapter.snapshot(RESTORE)
        compare_rehearsal(before,after,adapter.policy)
    # Source is checked again; target comparison alone cannot prove source preservation.
    source_after = adapter.snapshot(SOURCE)
    require(source_after == source and source_hashes() == hashes, 'source_drift')
    return dict(format='existing-demo-restore-review-v1',source_database=SOURCE,
                restore_database=RESTORE,restore_account=adapter.policy.account,
                start_revision=START,end_revision=END if rehearsal else START,
                full_row_preservation_verified=True,financial_preservation_verified=True,
                foreign_keys_verified=True,migration_verified=rehearsal,
                backup_binding_verified=False,demo_migration_evidence_compatible=False,
                production_migration_evidence_compatible=False,
                source_hashes=hashes,source_snapshot=source,restored_snapshot=after if rehearsal else before,
                verified_utc=datetime.now(timezone.utc).isoformat())


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute',action='store_true')
    p.add_argument('--rehearse',action='store_true')
    p.add_argument('--confirm-rehearsal',action='store_true')
    for name in ('confirm-source','confirm-restore','approved-restore-account',
                 'approved-restore-grants','confirm-revision','evidence-id'):
        p.add_argument('--'+name)
    p.add_argument('--tls-ca',type=Path)
    p.add_argument('--confirm-writer-ddl-pause',action='store_true')
    p.add_argument('--confirm-target-administration-pause',action='store_true')
    p.add_argument('--confirm-private-console',action='store_true')
    p.add_argument('--confirm-dba-object-review',action='store_true')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if not args.execute:
        print('PASS: offline preparation; no credentials, files or database accessed')
        return 0
    adapter = None
    stage = 'confirmation'
    try:
        require(args.confirm_source == SOURCE and args.confirm_restore == RESTORE, 'target_confirmation')
        require(args.confirm_private_console and args.confirm_dba_object_review
                and args.confirm_writer_ddl_pause and args.confirm_target_administration_pause, 'operator_confirmation')
        require(not args.rehearse or (args.confirm_rehearsal and args.confirm_revision == END), 'rehearsal_confirmation')
        policy = RestorePolicy(args.approved_restore_account,
                               frozenset((args.approved_restore_grants or '').split(',')))
        require(not args.rehearse or policy.rights in (MINIMUM,MINIMUM | {'DELETE'}), 'rehearsal_grants')
        stage = 'tls_prerequisite'
        require(args.tls_ca is not None and args.tls_ca.is_absolute() and args.tls_ca.is_file(), 'tls_ca')
        migration.no_reparse(args.tls_ca)
        require(isinstance(args.evidence_id,str) and re.fullmatch('[0-9a-f]{32}',args.evidence_id), 'evidence_id')
        path = recovery.PRIVATE / ('existing-restore-' + ('rehearsal-' if args.rehearse else 'comparison-') + args.evidence_id + '.json')
        stage = 'protected_evidence_prerequisite'
        with recovery.WindowsPrivateStore() as store:
            store.check(path,absent=True)
            adapter = ExistingRestoreAdapter(policy,args.tls_ca)
            stage = 'isolated_rehearsal_and_verification' if args.rehearse else 'readonly_comparison'
            report = verify(adapter,execute=True,confirm_source=args.confirm_source,
                confirm_restore=args.confirm_restore,writer_ddl_pause=args.confirm_writer_ddl_pause,
                target_administration_pause=args.confirm_target_administration_pause,
                rehearsal=args.rehearse,confirm_revision=args.confirm_revision,
                approved_rehearsal=args.confirm_rehearsal)
            stage = 'exclusive_evidence_creation'
            store.write(path,report)
        print('PASS: existing restore '+('QR rehearsal' if args.rehearse else 'read-only comparison')+
              ' verified; populated-demo migration remains unauthorized')
        return 0
    except Exception:
        # Do not expose exceptions, SQL, account values, paths or request data.
        print('STOP: existing restore verification stage='+stage+'; preserve state and artifacts; no retry')
        return 1
    finally:
        if adapter is not None:
            adapter.secrets.clear()  # Python/connector immutable copies cannot be guaranteed erased.


if __name__ == '__main__':
    raise SystemExit(main())

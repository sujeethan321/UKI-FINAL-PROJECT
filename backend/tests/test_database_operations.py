"""Maintenance checks never dump, reset or restore an existing database."""
import io
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, Numeric, create_engine, inspect, select, update

from app.core.database import Base, engine
from app.core.db_maintenance import (MaintenanceSafetyError, require_empty,
                                     validate_target, verify_identity)
from app.models import CreditAccount, CustomerProfile, LedgerEntry, Order
from app.services.backup_manifest import backup_command, checksum, read_manifest, restore_command, validate_manifest
from app.services.database_integrity import domain_counts, integrity_report, relational_counts
from app.services.ledger_service import account_balances
from test_catalogue import shop, api, db, request
from test_order_delivery import ready, create, finance

ROOT = Path(__file__).resolve().parents[1]


def alembic_config(output=None):
    cfg = Config(str(ROOT / 'alembic.ini'), output_buffer=output)
    cfg.set_main_option('script_location', str(ROOT / 'alembic'))
    return cfg


def test_revision_chain_and_registered_metadata():
    scripts = ScriptDirectory.from_config(alembic_config())
    revisions = list(scripts.walk_revisions())
    assert scripts.get_heads() == ['03b9c2d1e671']
    assert len(revisions) == len({r.revision for r in revisions}) == 13
    assert len(scripts.get_bases()) == 1
    assert len(Base.metadata.tables) == 20
    for revision in revisions:
        if revision.down_revision:
            assert scripts.get_revision(revision.down_revision)


@pytest.mark.parametrize('revision', ['head', 'b8c4d7e6f126:head'])
def test_offline_clean_and_legacy_upgrade_sql(revision):
    output = io.StringIO()
    command.upgrade(alembic_config(output), revision, sql=True)
    sql = output.getvalue()
    assert 'CREATE TABLE orders' in sql and 'CREATE TABLE admin_audits' in sql
    assert 'fk_order_delivery_business' in sql and 'NUMERIC(14, 2)' in sql
    assert 'DROP DATABASE' not in sql and 'TRUNCATE' not in sql


def test_current_test_schema_matches_metadata():
    with engine.connect() as connection:
        verify_identity(connection, 'lankapex_test_db')
        assert compare_metadata(MigrationContext.configure(connection, opts={'compare_type': True}), Base.metadata) == []
        inspector = inspect(connection)
        for table in Base.metadata.sorted_tables:
            expected = {item.name for item in table.constraints if isinstance(item, CheckConstraint)}
            actual = {item['name'] for item in inspector.get_check_constraints(table.name)}
            assert expected.issubset(actual), table.name


def test_clean_isolated_upgrade_when_operator_provides_empty_target():
    target = os.environ.get('LANKAPEX_MIGRATION_VERIFY_DATABASE')
    if not target:
        pytest.skip('No operator-designated empty migration verification database; existing databases are never reset')
    validate_target('testing', target, 'migration')
    isolated = create_engine(engine.url.set(database=target), hide_parameters=True)
    try:
        with isolated.connect() as connection:
            verify_identity(connection, target)
            require_empty(connection)
            connection.commit()
            cfg = alembic_config()
            cfg.attributes['connection'] = connection
            # MySQL DDL is not transactional; only this designated empty schema is used.
            command.upgrade(cfg, 'b8c4d7e6f126')
            connection.commit()
            command.upgrade(cfg, 'head')
            connection.commit()
            assert compare_metadata(MigrationContext.configure(connection, opts={'compare_type': True}), Base.metadata) == []
    finally:
        isolated.dispose()


@pytest.mark.parametrize(('mode', 'database', 'purpose'), [
    ('production', 'release', 'inspect'), ('development', 'lankapex_db', 'restore'),
    ('testing', 'lankapex_test_db', 'restore'), ('testing', 'lankapex_db', 'migration'),
    ('testing', '', 'inspect'), ('testing', '*', 'restore'),
    ('testing', 'lankapex_restore_verify_*', 'restore'),
    ('testing', 'lankapex_restore_verify_x;drop', 'restore'),
    ('testing', 'release_database', 'restore'), ('', 'lankapex_db', 'inspect'),
])
def test_unsafe_target_rejected(mode, database, purpose):
    with pytest.raises(MaintenanceSafetyError):
        validate_target(mode, database, purpose)


def test_exact_isolated_targets_and_actual_identity():
    for purpose in ['restore', 'migration']:
        name = f'lankapex_{purpose}_verify_20261107'
        assert validate_target('testing', name, purpose) == name
    fake = SimpleNamespace(engine=SimpleNamespace(url=SimpleNamespace(database='lankapex_test_db')),
                           scalar=lambda _: 'lankapex_db')
    with pytest.raises(MaintenanceSafetyError):
        verify_identity(fake, 'lankapex_test_db')
    with engine.connect() as connection:
        with pytest.raises(MaintenanceSafetyError):
            require_empty(connection)


def test_backup_restore_command_plans_do_not_embed_secrets_or_change_targets():
    plan = backup_command(option_file='private/mysql.cnf', database='lankapex_db', output='private/backup.sql')
    assert plan[1] == '--defaults-file=private\\mysql.cnf' if os.name == 'nt' else plan[1] == '--defaults-file=private/mysql.cnf'
    assert '--single-transaction' in plan and '--no-tablespaces' in plan
    assert not any('--password' in arg or '--databases' == arg or '--all-databases' == arg for arg in plan)
    assert plan[-1] == 'lankapex_db'
    restored = restore_command(option_file='private/mysql.cnf', environment='testing',
                               database='lankapex_restore_verify_20261107')
    assert '--database=lankapex_restore_verify_20261107' in restored
    with pytest.raises(MaintenanceSafetyError):
        backup_command(option_file='private/mysql.cnf', database='lankapex_db', output='x', transactional=False)


@pytest.fixture
def artifact(tmp_path):
    dump = tmp_path / 'fixture.sql'
    dump.write_bytes(b'-- MySQL dump 10.13\n-- Synthetic fixture only\nSELECT 1;\n')
    manifest = dict(format_version=1, format='mysql-logical-sql',
        created_at='2026-01-01T00:00:00Z', source_environment='testing',
        source_database='lankapex_test_db', mysql_version='8.0.46', schema_revision='03b9c2d1e671',
        sha256=checksum(dump), size_bytes=dump.stat().st_size)
    return dump, manifest


def test_backup_metadata_and_checksum(artifact):
    dump, manifest = artifact
    assert validate_manifest(manifest, dump) == manifest
    dump.write_bytes(dump.read_bytes() + b'-- tampered\n')
    with pytest.raises(MaintenanceSafetyError):
        validate_manifest(manifest, dump)


@pytest.mark.parametrize(('key', 'value'), [('created_at', 'not-a-date'),
    ('created_at', '2999-01-01T00:00:00Z'), ('created_at', '2026-01-01'),
    ('sha256', 'bad'), ('size_bytes', 0), ('format', 'unknown'),
    ('mysql_version', '5.7.1'), ('schema_revision', ''), ('source_database', '*'),
    ('password', 'private-sentinel')])
def test_invalid_metadata_fails_without_echoing_values(artifact, key, value):
    dump, manifest = artifact
    with pytest.raises(MaintenanceSafetyError) as error:
        validate_manifest(manifest | {key: value}, dump)
    assert 'private-sentinel' not in str(error.value)


def test_unreadable_empty_unrecognized_and_same_size_tampering(artifact, tmp_path):
    dump, manifest = artifact
    with pytest.raises(MaintenanceSafetyError):
        read_manifest(tmp_path / 'absent.json', dump)
    dump.write_bytes(b'')
    with pytest.raises(MaintenanceSafetyError):
        validate_manifest(manifest, dump)
    dump.write_bytes(b'-- MySQL dump fixture changed')
    wrong = manifest | {'size_bytes': dump.stat().st_size}
    with pytest.raises(MaintenanceSafetyError):
        validate_manifest(wrong, dump)
    dump.write_bytes(b'not a mysql logical dump')
    with pytest.raises(MaintenanceSafetyError):
        validate_manifest(manifest | {'sha256': checksum(dump), 'size_bytes': dump.stat().st_size}, dump)


def test_financial_precision_and_reference_constraints():
    expected = {'products': ['unit_price'], 'orders': ['subtotal', 'total'],
                'order_items': ['unit_price', 'line_total'], 'ledger_entries': ['amount'],
                'credit_accounts': ['credit_limit'], 'payment_reminders': ['outstanding_amount']}
    for name, columns in expected.items():
        for column in columns:
            numeric = Base.metadata.tables[name].c[column].type
            assert isinstance(numeric, Numeric) and numeric.asdecimal and numeric.scale == 2
    assert 'fk_order_delivery_business' in {fk.name for fk in Order.__table__.foreign_key_constraints}
    assert any(fk.target_fullname == 'ledger_entries.entry_id' for fk in Order.__table__.c.credit_sale_id.foreign_keys)


def test_integrity_checks_with_real_credit_order_idempotency_and_delivery_isolation(shop):
    s = shop
    ident = ready(s, 'credit', 'approved')
    before = finance(s)
    result = create(s, ident)
    assert result.status_code == 201
    assert create(s, ident).status_code == 201
    assert finance(s) == before
    connection = s['db'].connection()
    assert not any(relational_counts(connection).values())
    assert not any(domain_counts(s['db']).values())
    report = integrity_report(connection)
    assert not any(report['violations'].values())
    assert report['ledger_entry_count'] == 1
    assert len(report['ledger_sha256']) == len(report['effective_balances_sha256']) == 64
    assert integrity_report(connection)['effective_balances_sha256'] == report['effective_balances_sha256']
    assert s['db'].scalar(select(Order.total).where(Order.order_id == ident)) > Decimal('0')


def test_domain_checker_detects_cross_business_account_without_repairing(shop):
    s = shop
    _, account = s['profile'](s['business'])
    s['db'].execute(update(CreditAccount).where(CreditAccount.credit_account_id == account.credit_account_id).values(creditor_business_id=s['foreign']))
    s['db'].flush()
    assert domain_counts(s['db'])['account_business_ownership'] == 1
    assert s['db'].get(CreditAccount, account.credit_account_id).creditor_business_id == s['foreign']


def test_authoritative_repayment_reversal_reconciliation():
    rows = [SimpleNamespace(entry_id=1, credit_account_id=9, entry_type='credit_sale', amount=Decimal('100.10'), reverses_entry_id=None),
            SimpleNamespace(entry_id=2, credit_account_id=9, entry_type='repayment', amount=Decimal('20.05'), reverses_entry_id=None)]
    assert account_balances(rows)[9] == Decimal('80.05')
    rows.append(SimpleNamespace(entry_id=3, credit_account_id=9, entry_type='reversal', amount=Decimal('20.05'), reverses_entry_id=2))
    assert account_balances(rows)[9] == Decimal('100.10')

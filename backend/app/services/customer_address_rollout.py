
# Purpose: Implement customer address rollout operations behind the HTTP
# layer so related business rules are shared by their callers.

"""Independent fail-closed gates. Disabled paths never inspect optional tables.

Exact DBA attestation covers immutable triggers, enforced CHECKs and restricted
runtime grants. It is an operator trust boundary, never automatic activation.
"""

import logging

from fastapi import HTTPException
from sqlalchemy import inspect, text, CheckConstraint, UniqueConstraint
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.services.schema_integrity import (
    verify_checks,
    reviewed_boolean_storage,
)

logger = logging.getLogger(__name__)

REVISION = 'd15a8c902e64'

HEADERS = {
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
}


def enabled(checkout=False):
    return getattr(
        settings,
        'ADDRESS_CHECKOUT_ENABLED'
        if checkout
        else 'ADDRESS_BOOK_ENABLED',
        False,
    ) is True


def require_ready(db, checkout=False):

    def unavailable(reason):
        logger.warning('Address readiness rejected: %s', reason)

        raise HTTPException(
            status_code=503,
            detail={
                'code': 'ADDRESS_UNAVAILABLE',
                'message': (
                    'Address management requires '
                    'verified server configuration.'
                ),
            },
            headers=HEADERS,
        )

    # Verify feature activation.
    if not enabled() or (checkout and not enabled(True)):
        unavailable('FEATURE_DISABLED')

    # Verify DBA attestation.
    if getattr(
        settings,
        'ADDRESS_DBA_ATTESTED_REVISION',
        None,
    ) != REVISION:
        unavailable('ATTESTATION_MISMATCH')

    from app.models import CustomerAddress, UserPreference
    from app.models.order_address import OrderDeliveryAddress

    models = (
        (CustomerAddress, UserPreference, OrderDeliveryAddress)
        if checkout
        else (CustomerAddress, UserPreference)
    )

    try:
        inspector = inspect(db.connection())

        # Verify the actual database migration revision.
        if list(
            db.scalars(text('SELECT version_num FROM alembic_version'))
        ) != [REVISION]:
            unavailable('DATABASE_REVISION_MISMATCH')

        for model in models:
            table = model.__table__

            actual = {
                c['name']: c
                for c in inspector.get_columns(table.name)
            }

            # Verify column inventory.
            if set(actual) != set(table.c.keys()):
                unavailable(f'COLUMN_INVENTORY:{table.name}')

            for column in table.c:
                found = actual[column.name]

                # Recognize MySQL's valid Boolean storage.
                boolean_storage = reviewed_boolean_storage(
                    column.type,
                    found['type'],
                    inspector.dialect.name,
                )

                # Verify column nullability.
                if found['nullable'] != column.nullable:
                    unavailable(
                        f'NULLABILITY:{table.name}.{column.name}'
                    )

                # Verify column type compatibility.
                if (
                    not boolean_storage
                    and found['type']._type_affinity
                    != column.type._type_affinity
                ):
                    unavailable(
                        f'TYPE_FAMILY:{table.name}.{column.name}'
                    )

                # Reject unexpected unsigned columns.
                if getattr(found['type'], 'unsigned', False):
                    unavailable(f'SIGNEDNESS:{table.name}')

                # Verify column type attributes.
                for attr in ('length', 'precision', 'scale', 'fsp'):

                    if (
                        attr == 'fsp'
                        and inspector.dialect.name != 'mysql'
                    ):
                        continue

                    if (
                        getattr(column.type, attr, None) is not None
                        and getattr(found['type'], attr, None)
                        != getattr(column.type, attr)
                    ):
                        unavailable(f'TYPE_ATTRIBUTE:{table.name}')

            # Verify primary keys.
            if (
                inspector.get_pk_constraint(
                    table.name
                )['constrained_columns']
                != [c.name for c in table.primary_key]
            ):
                unavailable(f'PRIMARY_KEY:{table.name}')

            # Verify unique constraints.
            uniques = {
                tuple(c.name for c in u.columns)
                for u in table.constraints
                if isinstance(u, UniqueConstraint)
            }

            actual_uniques = {
                tuple(u['column_names'])
                for u in inspector.get_unique_constraints(table.name)
            }

            if not uniques.issubset(actual_uniques):
                unavailable(f'UNIQUENESS:{table.name}')

            # Verify indexes.
            indexes = {
                (i['name'], tuple(i['column_names']))
                for i in inspector.get_indexes(table.name)
            }

            expected_indexes = {
                (i.name, tuple(c.name for c in i.columns))
                for i in table.indexes
            }

            if not expected_indexes.issubset(indexes):
                unavailable(f'INDEX:{table.name}')

            # Verify foreign keys.
            expected = {
                (
                    tuple(f.parent.name for f in fk.elements),
                    tuple(f.column.name for f in fk.elements),
                    next(iter(fk.elements)).column.table.name,
                )
                for fk in table.foreign_key_constraints
            }

            actual_fks = inspector.get_foreign_keys(table.name)

            reflected_fks = {
                (
                    tuple(f['constrained_columns']),
                    tuple(f['referred_columns']),
                    f['referred_table'],
                )
                for f in actual_fks
            }

            if expected != reflected_fks:
                unavailable(f'FOREIGN_KEY:{table.name}')

            for fk in actual_fks:

                if fk.get('referred_schema') not in (
                    None,
                    inspector.default_schema_name,
                ):
                    unavailable(f'FOREIGN_SCHEMA:{table.name}')

                if any(
                    fk.get('options', {})
                    .get(action, 'RESTRICT')
                    .upper()
                    not in ('RESTRICT', 'NO ACTION')
                    for action in ('ondelete', 'onupdate')
                ):
                    unavailable(f'FOREIGN_ACTION:{table.name}')

            # Verify database CHECK constraints.
            verify_checks(db, inspector, table)

            if inspector.dialect.name == 'mysql':

                options = inspector.get_table_options(table.name)

                # Verify storage engine and collation.
                if (
                    str(options.get('mysql_engine', '')).lower()
                    != 'innodb'
                    or options.get('mysql_collate')
                    != 'utf8mb4_unicode_ci'
                ):
                    unavailable(f'ENGINE_COLLATION:{table.name}')

                # Verify integer storage width.
                for col in table.c:
                    if (
                        col.type._type_affinity.__name__ == 'Integer'
                        and actual[col.name]['type'].__visit_name__.upper()
                        != (
                            'INTEGER'
                            if col.name in ('version', 'accepted_version')
                            else 'BIGINT'
                        )
                    ):
                        unavailable(f'INTEGER_WIDTH:{table.name}')

        # Checkout also requires verified Driver Finance readiness.
        if checkout:
            from app.services.driver_finance_rollout import (
                require_ready as finance_ready,
            )

            finance_ready(db)

    except (SQLAlchemyError, ValueError, KeyError) as exc:
        unavailable(f'INSPECTION:{type(exc).__name__}')

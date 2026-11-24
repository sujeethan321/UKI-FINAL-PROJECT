"""Disabled by default; no new-table queries on legacy paths while disabled.

Enable only after an operator verifies the migration (including ten immutable
UPDATE/DELETE triggers) and exact runtime grants. The app must not receive DDL
or TRIGGER privileges. Revision/structural verification below is read-only;
privileged DBA tampering after approval is outside this application boundary.
Only explicitly reviewed revisions are accepted. SD-02 changes no finance
tables; its revision requires fresh matching DBA attestation. Later migrations
still need review. No auto-enable, repair, stamping or missing-table fallback.
"""
from fastapi import HTTPException
from sqlalchemy import inspect,text
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.services.schema_integrity import verify_checks

REVISION='bf38d2a90176'
REVIEWED_REVISIONS=frozenset({REVISION,'c04d9e7a6201','d15a8c902e64'})


def enabled():
    return getattr(settings,'DRIVER_FINANCE_ENABLED',False) is True


def require_ready(db):
    if not enabled():
        raise HTTPException(503,detail={'code':'DRIVER_FINANCE_NOT_ENABLED','message':'Driver finance is not enabled.'},headers={'Cache-Control':'no-store'})
    # Explicit operator attestation is required because the restricted runtime
    # must not be granted TRIGGER privileges just to inspect trigger metadata.
    # This is a configuration trust boundary, not a cryptographic certificate.
    attested=getattr(settings,'DRIVER_FINANCE_DBA_ATTESTED_REVISION',None)
    if attested not in REVIEWED_REVISIONS:
        raise HTTPException(503,detail={'code':'DRIVER_FINANCE_SCHEMA_NOT_READY','message':'Driver finance requires DBA verification of schema, triggers and runtime grants.'},headers={'Cache-Control':'no-store'})
    from app.models.driver_finance import OrderFulfilmentCharge,DriverEarning,DriverFeeCollection,DriverSettlementEvent,DriverFinancialAudit
    from sqlalchemy import UniqueConstraint,CheckConstraint,Integer,Numeric,String,DateTime
    tables=[c.__table__ for c in (OrderFulfilmentCharge,DriverEarning,DriverFeeCollection,DriverSettlementEvent,DriverFinancialAudit)]
    try:
        inspector=inspect(db.connection())
        if not {t.name for t in tables}.union({'alembic_version'}).issubset(inspector.get_table_names()):raise ValueError('Missing schema')
        if list(db.scalars(text('SELECT version_num FROM alembic_version')))!=[attested]:raise ValueError('Unverified revision')
        for table in tables:
            if inspector.dialect.name=='mysql':
                options=inspector.get_table_options(table.name)
                if str(options.get('mysql_engine','')).lower()!='innodb' or options.get('mysql_collate')!='utf8mb4_unicode_ci':
                    raise ValueError('Unverified table engine/collation')
            columns={c['name']:c for c in inspector.get_columns(table.name)}
            if set(columns)!=set(table.c.keys()):raise ValueError('Column drift')
            for column in table.c:
                actual=columns[column.name]
                if bool(actual['nullable'])!=column.nullable:raise ValueError('Nullability drift')
                if not any(isinstance(column.type,kind) and isinstance(actual['type'],kind) for kind in (Integer,Numeric,String,DateTime)):
                    raise ValueError('Type family drift')
                if inspector.dialect.name=='mysql' and isinstance(column.type,Integer) and actual['type'].__visit_name__.upper()!='BIGINT' and column.name not in ('declaration_slot','settlement_slot','sequence_no','previous_sequence_no'):
                    raise ValueError('Integer width drift')
                for attr in ('length','precision','scale'):
                    expected=getattr(column.type,attr,None)
                    if expected is not None and getattr(actual['type'],attr,None)!=expected:raise ValueError('Type drift')
                if getattr(actual['type'],'unsigned',False):raise ValueError('Signedness drift')
            expected_fks={(tuple(f.parent.name for f in fk.elements),tuple(f.column.name for f in fk.elements),next(iter(fk.elements)).column.table.name) for fk in table.foreign_key_constraints}
            actual_fks={(tuple(f['constrained_columns']),tuple(f['referred_columns']),f['referred_table']) for f in inspector.get_foreign_keys(table.name)}
            if expected_fks!=actual_fks:raise ValueError('Relationship drift')
            for foreign_key in inspector.get_foreign_keys(table.name):
                if foreign_key.get('referred_schema') not in (None,inspector.default_schema_name):raise ValueError('Cross-schema financial reference')
                for action in ('ondelete','onupdate'):
                    if foreign_key.get('options',{}).get(action,'RESTRICT').upper() not in ('RESTRICT','NO ACTION'):
                        raise ValueError('Unsafe cascading relationship')
            expected_unique={tuple(c.name for c in constraint.columns) for constraint in table.constraints if isinstance(constraint,UniqueConstraint)}
            actual_unique={tuple(c['column_names']) for c in inspector.get_unique_constraints(table.name)}
            if not expected_unique.issubset(actual_unique):raise ValueError('Uniqueness drift')
            verify_checks(db,inspector,table)
            if set(inspector.get_pk_constraint(table.name)['constrained_columns'])!={c.name for c in table.primary_key}:raise ValueError('Primary key drift')
    except (SQLAlchemyError,ValueError):
        raise HTTPException(503,detail={'code':'DRIVER_FINANCE_SCHEMA_NOT_READY','message':'Driver finance requires verified schema readiness.'},headers={'Cache-Control':'no-store'}) from None

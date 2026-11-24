"""Independent fail-closed gates. Disabled paths never inspect optional tables.

Exact DBA attestation covers immutable triggers, enforced CHECKs and restricted
runtime grants. It is an operator trust boundary, never automatic activation.
"""
from fastapi import HTTPException
from sqlalchemy import inspect,text,CheckConstraint,UniqueConstraint
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.services.schema_integrity import verify_checks

REVISION='d15a8c902e64'
HEADERS={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}

def enabled(checkout=False):return getattr(settings,'ADDRESS_CHECKOUT_ENABLED' if checkout else 'ADDRESS_BOOK_ENABLED',False) is True

def require_ready(db,checkout=False):
    def unavailable():raise HTTPException(503,detail={'code':'ADDRESS_UNAVAILABLE','message':'Address management requires verified server configuration.'},headers=HEADERS)
    if not enabled() or (checkout and not enabled(True)):unavailable()
    if getattr(settings,'ADDRESS_DBA_ATTESTED_REVISION',None)!=REVISION:unavailable()
    from app.models import CustomerAddress,UserPreference
    from app.models.order_address import OrderDeliveryAddress
    models=(CustomerAddress,UserPreference,OrderDeliveryAddress) if checkout else (CustomerAddress,UserPreference)
    try:
        inspector=inspect(db.connection())
        if list(db.scalars(text('SELECT version_num FROM alembic_version')))!=[REVISION]:unavailable()
        for model in models:
            table=model.__table__
            actual={c['name']:c for c in inspector.get_columns(table.name)}
            if set(actual)!=set(table.c.keys()):unavailable()
            for column in table.c:
                found=actual[column.name]
                if found['nullable']!=column.nullable or found['type']._type_affinity!=column.type._type_affinity:unavailable()
                if getattr(found['type'],'unsigned',False):unavailable()
                for attr in ('length','precision','scale','fsp'):
                    if attr=='fsp' and inspector.dialect.name!='mysql':continue
                    if getattr(column.type,attr,None) is not None and getattr(found['type'],attr,None)!=getattr(column.type,attr):unavailable()
            if inspector.get_pk_constraint(table.name)['constrained_columns']!=[c.name for c in table.primary_key]:unavailable()
            uniques={tuple(c.name for c in u.columns) for u in table.constraints if isinstance(u,UniqueConstraint)}
            if not uniques.issubset({tuple(u['column_names']) for u in inspector.get_unique_constraints(table.name)}):unavailable()
            indexes={(i['name'],tuple(i['column_names'])) for i in inspector.get_indexes(table.name)}
            if not {(i.name,tuple(c.name for c in i.columns)) for i in table.indexes}.issubset(indexes):unavailable()
            expected={(tuple(f.parent.name for f in fk.elements),tuple(f.column.name for f in fk.elements),next(iter(fk.elements)).column.table.name) for fk in table.foreign_key_constraints}
            actual_fks=inspector.get_foreign_keys(table.name)
            if expected!={(tuple(f['constrained_columns']),tuple(f['referred_columns']),f['referred_table']) for f in actual_fks}:unavailable()
            for fk in actual_fks:
                if fk.get('referred_schema') not in (None,inspector.default_schema_name):unavailable()
                if any(fk.get('options',{}).get(a,'RESTRICT').upper() not in ('RESTRICT','NO ACTION') for a in ('ondelete','onupdate')):unavailable()
            verify_checks(db,inspector,table)
            if inspector.dialect.name=='mysql':
                options=inspector.get_table_options(table.name)
                if str(options.get('mysql_engine','')).lower()!='innodb' or options.get('mysql_collate')!='utf8mb4_unicode_ci':unavailable()
                for col in table.c:
                    if col.type._type_affinity.__name__=='Integer' and actual[col.name]['type'].__visit_name__.upper()!=('INTEGER' if col.name in ('version','accepted_version') else 'BIGINT'):unavailable()
        if checkout:
            from app.services.driver_finance_rollout import require_ready as finance_ready
            finance_ready(db)
    except (SQLAlchemyError,ValueError,KeyError):unavailable()

"""Fail-closed rollout. DBA attestation covers triggers and restricted runtime grants.

Attestation is an explicit operator trust boundary, not a cryptographic proof.
The runtime is not granted TRIGGER/DDL just to inspect privileged metadata.
"""
from fastapi import HTTPException
from sqlalchemy import inspect,text,CheckConstraint,UniqueConstraint,Integer,String,DateTime,Boolean,Text
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from app.services.schema_integrity import verify_checks

REVISION='c04d9e7a6201'
REVIEWED_REVISIONS=frozenset({REVISION,'d15a8c902e64'})
HEADERS={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}

def require_ready(db):
    if not getattr(settings,'SUPPORT_ENABLED',False):
        raise HTTPException(503,detail={'code':'SUPPORT_DISABLED','message':'Support is not enabled on this server.'},headers=HEADERS)
    attested=getattr(settings,'SUPPORT_DBA_ATTESTED_REVISION',None)
    if attested not in REVIEWED_REVISIONS:
        raise HTTPException(503,detail={'code':'SUPPORT_SCHEMA_NOT_READY','message':'Support schema requires operator verification.'},headers=HEADERS)
    from app.models.support import SupportCase,SupportMessage,SupportEvent,SupportReference
    try:
        inspector=inspect(db.connection())
        if not {m.__tablename__ for m in (SupportCase,SupportMessage,SupportEvent,SupportReference)}.issubset(inspector.get_table_names()):raise ValueError()
        if list(db.scalars(text('SELECT version_num FROM alembic_version')))!=[attested]:raise ValueError()
        for model in (SupportCase,SupportMessage,SupportEvent,SupportReference):
            table=model.__table__;actual={c['name']:c for c in inspector.get_columns(table.name)}
            if inspector.dialect.name=='mysql':
                options=inspector.get_table_options(table.name)
                if str(options.get('mysql_engine','')).lower()!='innodb' or options.get('mysql_collate')!='utf8mb4_unicode_ci':raise ValueError()
            if set(actual)!=set(table.c.keys()):raise ValueError()
            for column in table.c:
                if actual[column.name]['nullable']!=column.nullable:raise ValueError()
                if not any(isinstance(column.type,kind) and isinstance(actual[column.name]['type'],kind) for kind in (Integer,String,DateTime,Boolean,Text)):raise ValueError()
                if getattr(actual[column.name]['type'],'unsigned',False):raise ValueError()
                for attr in ('length','precision','scale'):
                    if getattr(column.type,attr,None) is not None and getattr(actual[column.name]['type'],attr,None)!=getattr(column.type,attr):raise ValueError()
            verify_checks(db,inspector,table)
            uniques={tuple(col.name for col in c.columns) for c in table.constraints if isinstance(c,UniqueConstraint)}
            if not uniques.issubset({tuple(c['column_names']) for c in inspector.get_unique_constraints(table.name)}):raise ValueError()
            expected={(tuple(f.parent.name for f in fk.elements),tuple(f.column.name for f in fk.elements),next(iter(fk.elements)).column.table.name) for fk in table.foreign_key_constraints}
            found={(tuple(f['constrained_columns']),tuple(f['referred_columns']),f['referred_table']) for f in inspector.get_foreign_keys(table.name)}
            if found!=expected:raise ValueError()
            if inspector.get_pk_constraint(table.name)['constrained_columns']!=[c.name for c in table.primary_key]:raise ValueError()
            for fk in inspector.get_foreign_keys(table.name):
                if fk.get('referred_schema') not in (None,inspector.default_schema_name):raise ValueError()
                if fk.get('options',{}).get('ondelete','RESTRICT').upper() not in ('RESTRICT','NO ACTION'):raise ValueError()
        from app.models import Notification
        verify_checks(db,inspector,Notification.__table__)
    except (SQLAlchemyError,ValueError):
        raise HTTPException(503,detail={'code':'SUPPORT_SCHEMA_NOT_READY','message':'Support schema is unavailable or unverified.'},headers=HEADERS) from None

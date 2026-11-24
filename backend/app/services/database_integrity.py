# Purpose: Report relational and domain consistency counts for database inspection without repairing records.
"""Read-only relational and financial checks; reports counts, never private rows."""
from decimal import Decimal
import hashlib
import json
from sqlalchemy import and_, func, select, inspect
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import (AdminAudit, CreditAccount, CustomerProfile, DeliveryRequest,
                        LedgerEntry, Order, OrderItem, Product, User)
from app.services.ledger_service import account_balances


# Query relational counts data for the database integrity workflow.
def relational_counts(connection):
    findings = {}
    for table in Base.metadata.sorted_tables:
        for index, constraint in enumerate(sorted(table.foreign_key_constraints,
                key=lambda fk: tuple(fk.column_keys))):
            elements = list(constraint.elements)
            parent = elements[0].column.table
            alias = parent.alias()
            present = and_(*(element.parent.is_not(None) for element in elements))
            linked = and_(*(element.parent == alias.c[element.column.name] for element in elements))
            query = select(func.count()).select_from(table).where(present, ~select(1).select_from(alias).where(linked).exists())
            findings[f'fk:{table.name}:{constraint.name or index}'] = connection.scalar(query)
        from sqlalchemy import UniqueConstraint
        groups = [list(c.columns) for c in table.constraints if isinstance(c, UniqueConstraint)]
        groups += [list(i.columns) for i in table.indexes if i.unique]
        for index, columns in enumerate(groups):
            duplicates = select(*columns).where(and_(*(c.is_not(None) for c in columns))).group_by(*columns).having(func.count() > 1).subquery()
            findings[f'unique:{table.name}:{index}'] = connection.scalar(select(func.count()).select_from(duplicates))
    return findings


# Query domain counts data for the database integrity workflow.
def domain_counts(db):
    # Query count data for the database integrity workflow.
    def count(statement):
        return db.scalar(select(func.count()).select_from(statement.subquery()))
    accounts = select(CreditAccount.credit_account_id).join(CustomerProfile).where(
        CreditAccount.creditor_business_id != CustomerProfile.business_id)
    sales = select(Order.order_id).join(LedgerEntry, Order.credit_sale_id == LedgerEntry.entry_id).where(
        (LedgerEntry.entry_type != 'credit_sale') | (LedgerEntry.order_id != Order.order_id)
        | LedgerEntry.order_id.is_(None) | (LedgerEntry.credit_account_id != Order.credit_account_id)
        | (LedgerEntry.amount != Order.total))
    debt = select(LedgerEntry.entry_id).outerjoin(Order, LedgerEntry.order_id == Order.order_id).where(
        LedgerEntry.order_id.is_not(None), (Order.order_id.is_(None)) |
        (LedgerEntry.entry_type != 'credit_sale') | (Order.credit_sale_id != LedgerEntry.entry_id)
        | Order.credit_sale_id.is_(None) | (Order.payment_status != 'posted'))
    delivery = select(Order.order_id).join(DeliveryRequest, Order.delivery_request_id == DeliveryRequest.delivery_request_id).where(
        Order.business_id != DeliveryRequest.business_id)
    ownership = select(Order.order_id).join(CreditAccount, Order.credit_account_id == CreditAccount.credit_account_id).outerjoin(
        CustomerProfile, CreditAccount.customer_id == CustomerProfile.customer_id).where(
        (Order.business_id != CreditAccount.creditor_business_id) | CustomerProfile.user_id.is_(None)
        | (CustomerProfile.user_id != Order.customer_user_id))
    items = select(OrderItem.order_item_id).join(Order).join(Product, OrderItem.product_id == Product.product_id).where(Order.business_id != Product.business_id)
    original = LedgerEntry.__table__.alias('original')
    reversal = select(LedgerEntry.entry_id).outerjoin(original, LedgerEntry.reverses_entry_id == original.c.entry_id).where(
        LedgerEntry.entry_type == 'reversal',
        original.c.entry_id.is_(None) | (original.c.entry_type == 'reversal')
        | (original.c.credit_account_id != LedgerEntry.credit_account_id) | (original.c.amount != LedgerEntry.amount))
    audit = select(AdminAudit.audit_id).join(User, AdminAudit.admin_user_id == User.user_id).where(User.platform_role != 'admin')
    totals = select(OrderItem.order_id, func.sum(OrderItem.line_total).label('total')).group_by(OrderItem.order_id).subquery()
    mismatched_totals = select(Order.order_id).outerjoin(totals, Order.order_id == totals.c.order_id).where(
        totals.c.total.is_(None) | (Order.total != totals.c.total))
    return {name: count(query) for name, query in {
        'account_business_ownership': accounts, 'order_credit_sale_consistency': sales,
        'linked_ledger_debt': debt, 'order_delivery_business': delivery,
        'order_account_owner': ownership, 'order_item_business': items,
        'reversal_consistency': reversal, 'audit_actor_role': audit,
        'order_snapshot_total': mismatched_totals,
    }.items()}


def integrity_report(connection):
    """Caller verifies identity and starts a consistent READ ONLY transaction."""
    inspector = inspect(connection)
    missing = sorted(set(Base.metadata.tables) - set(inspector.get_table_names()))
    if missing:
        return {'violations': {'schema_incomplete': len(missing)}, 'missing_tables': missing}
    missing_columns = {name: sorted(set(table.c.keys()) - {
        column['name'] for column in inspector.get_columns(name)})
        for name, table in Base.metadata.tables.items()}
    missing_columns = {name: columns for name, columns in missing_columns.items() if columns}
    if missing_columns:
        return {'violations': {'schema_incomplete': len(missing_columns)}, 'missing_columns': missing_columns}
    foreign_and_unique = relational_counts(connection)
    with Session(bind=connection, join_transaction_mode='rollback_only') as db:
        domains = domain_counts(db)
        entries = list(db.scalars(select(LedgerEntry).order_by(LedgerEntry.entry_id)))
        # Reuse authoritative arithmetic; never write a derived balance.
        balances = account_balances(entries)
        if any(not isinstance(value, Decimal) for value in balances.values()):
            raise ValueError('Ledger arithmetic must remain Decimal')
        ledger_digest = hashlib.sha256(json.dumps([
            [row.entry_id, row.credit_account_id, row.entry_type, format(row.amount, '.2f'),
             row.reverses_entry_id, row.order_id, row.idempotency_key, row.receipt_number]
            for row in entries], separators=(',', ':')).encode()).hexdigest()
        balance_digest = hashlib.sha256(json.dumps([
            [key, format(value, '.2f')] for key, value in sorted(balances.items())
        ], separators=(',', ':')).encode()).hexdigest()
    return {'violations': foreign_and_unique | domains,
            'ledger_sha256': ledger_digest, 'effective_balances_sha256': balance_digest,
            'ledger_entry_count': len(entries), 'ledger_account_count': len(balances),
            'table_counts': {t.name: connection.scalar(select(func.count()).select_from(t))
                             for t in Base.metadata.sorted_tables}}

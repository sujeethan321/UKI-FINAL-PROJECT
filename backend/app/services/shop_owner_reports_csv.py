"""In-memory CSV rendering of the validated financial report, never new totals."""
import csv
from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO


def safe_text(value):
    text = str(value)
    # Quoting alone does not stop spreadsheet formulas. Only text is escaped;
    # monetary cells use validated Decimal instances, including negative values.
    if text.lstrip(' \t\r\n\v\f\ufeff').startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n', '\v', '\f')):
        return "'" + text
    return text


def money(value):
    amount = Decimal(value)
    if not amount.is_finite() or amount != amount.quantize(Decimal('0.01')):
        raise ValueError('Invalid report amount')
    return amount


def render_report_csv(data):
    output = StringIO(newline='')
    writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator='\r\n')

    def row(*values):
        writer.writerow([f'{value:.2f}' if isinstance(value, Decimal) else safe_text(value) for value in values])

    row('LankaPex financial report', 'LKR')
    row('Business ID', data['business_id'])
    row('Period start (inclusive, database wall clock)', data['start_date'])
    row('Period end (inclusive, database wall clock)', data['end_date'])
    row('Reporting clock', data['reporting_clock'])
    row('Clock limitation', 'Stored database wall clock; geographical timezone unverified; no timestamp conversion')
    row('Generated at (UTC; not ledger clock)', datetime.now(timezone.utc).isoformat())
    row('Database reporting day', data['database_today'])
    row('Period net credit sales (LKR)', money(data['totals']['credit_sales']))
    row('Period net repayments (LKR)', money(data['totals']['repayments']))
    row('Current outstanding (LKR; not a historical period-end balance)', money(data['summary']['total_outstanding']))
    row('Collected today (LKR; database reporting day, independent of selected period)', money(data['summary']['collected_today']))
    row('Reversal policy', 'Full original amount negated on reversal recorded date; negative net daily amounts are valid')
    row('Snapshot limitation', 'Fresh read at export; values may differ from an earlier screen view if records changed')
    aging = data.get('aging')
    if aging:
        row('Current aging policy', 'Reporting-only FIFO by recorded_at then entry_id per account; due-today is Current; database wall clock; independent of selected period')
        row('Aging coverage', aging['status'])
        row('Aging reconciliation', aging['reconciliation'])
        row('Current overdue (LKR; exact only under disclosed FIFO policy)', money(aging['overdue_amount']) if aging['overdue_amount'] is not None else 'Unavailable; incomplete or invalid coverage')
        if aging['buckets'] is not None:
            for key, value in aging['buckets'].items():
                row('Current aging ' + key + ' (LKR)', money(value))
            row('Unclassified current debt (LKR)', money(aging['unclassified']))
        row('Aging limitation', 'Classified buckets exclude Unclassified debt; incomplete coverage is not an exact total overdue')
    else:
        row('Overdue amount and aging', 'Unavailable; aging dataset absent')
    row('')
    row('Daily date (database wall clock)', 'Net credit sales (LKR)', 'Net repayments (LKR)')
    for day in data['daily']:
        row(day['date'], money(day['credit_sales']), money(day['repayments']))
    return output.getvalue().encode('utf-8-sig')

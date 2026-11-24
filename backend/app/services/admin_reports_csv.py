"""Export the same validated report and bounded comparisons; never recalculate money."""
import csv
from io import StringIO
from decimal import Decimal
from app.services.shop_owner_reports_csv import safe_text, money

LABELS = {
 'en':dict(title='Platform Reports',period='Selected period',generated='Generated at UTC',businesses='Businesses',users='Users',orders='Orders',deliveries='Deliveries',credit='Credit',comparisons='Business comparisons',unavailable='Unavailable metrics',limitations='Limitations',clocks='Reporting clocks',coverage='Coverage',snapshot='Snapshot'),
 'ta':dict(title='தள அறிக்கைகள்',period='தேர்ந்தெடுத்த காலம்',generated='உருவாக்க நேரம் UTC',businesses='வணிகங்கள்',users='பயனர்கள்',orders='ஆர்டர்கள்',deliveries='விநியோகங்கள்',credit='கடன்',comparisons='வணிக ஒப்பீடு',unavailable='கிடைக்காத அளவீடுகள்',limitations='வரம்புகள்',clocks='அறிக்கை நேர முறை',coverage='தரவு உள்ளடக்கம்',snapshot='தரவு நிலை'),
 'si':dict(title='වේදිකා වාර්තා',period='තෝරාගත් කාලය',generated='සෑදූ වේලාව UTC',businesses='ව්‍යාපාර',users='පරිශීලකයන්',orders='ඇණවුම්',deliveries='බෙදාහැරීම්',credit='ණය',comparisons='ව්‍යාපාර සැසඳීම',unavailable='නොලැබෙන දර්ශක',limitations='සීමා',clocks='වාර්තා කාල ක්‍රමය',coverage='දත්ත ආවරණය',snapshot='දත්ත තත්ත්වය'),
}


def export_rows(report, comparisons, language='en'):
    labels=LABELS[language]
    data=report.model_dump(mode='json')
    yield [labels['title'],'LKR']
    yield [labels['period'],data['start_date'],data['end_date']]
    yield [labels['generated'],data['generated_at']]
    for key in ('business_id','approval_status','order_status','database_today'): yield [key, data[key] if data[key] is not None else 'All']
    yield [labels['snapshot'],data['snapshot']]
    for section in ('reporting_clocks','coverage','unavailable'):
        yield [labels[{'reporting_clocks':'clocks'}.get(section,section)]]
        for key,value in data[section].items(): yield [key,value]
    for value in data['limitations']: yield [labels['limitations'],value]
    for section in ('businesses','users','orders','deliveries','credit'):
        yield [labels[section]]
        for category in ('counts','amounts'):
            for key,value in data[section][category].items(): yield [category,key,money(value) if category=='amounts' else value]
        daily=data[section]['daily']
        if daily: yield ['daily',*daily[0].keys()]
        for day in daily:
            yield ['daily',day['date'],*[money(value) if key in ('credit_sales','repayments') else value for key,value in day.items() if key!='date']]
    yield [labels['comparisons'],'All filtered rows; bounded to 1000 businesses']
    fields=['business_id','business_name','approval_status','orders','product_order_total','credit_sales','repayments','outstanding','advances']
    yield fields
    for row in comparisons: yield [money(getattr(row,key)) if key in ('product_order_total','credit_sales','repayments','outstanding','advances') else getattr(row,key) for key in fields]


def render_report_csv(report, comparisons, language='en'):
    output=StringIO(newline='')
    writer=csv.writer(output,quoting=csv.QUOTE_ALL,lineterminator='\r\n')
    for row in export_rows(report,comparisons,language): writer.writerow([f'{value:.2f}' if isinstance(value,Decimal) else safe_text(value) for value in row])
    return output.getvalue().encode('utf-8-sig')

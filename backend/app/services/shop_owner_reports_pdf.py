"""In-memory, shaped multilingual PDF from the existing validated report.

MuPDF Story handles Indic shaping; plain ReportLab glyph placement is not a
substitute. Fonts are embedded from existing installed/licensed fonts, not
downloaded at request time. No financial calculations or file output here.
"""
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path
import os
import json
import re
from threading import Lock

import pymupdf
import reportlab
from app.services.shop_owner_reports_csv import money

_render_lock = Lock()
AGING_LABELS = json.loads(Path(__file__).with_name('aging_labels.json').read_text(encoding='utf-8'))

LABELS = {
    'en': {
        'title': 'Business Financial Report', 'business': 'Business reference',
        'period': 'Selected period (inclusive)', 'generated': 'Generated at (UTC)',
        'clock': 'Dates use the stored database wall clock. A geographical timezone is not verified.',
        'current': 'Current overview', 'day': 'Database reporting day',
        'outstanding': 'Current outstanding', 'collected': 'Collected today (net)',
        'current_note': 'Current figures are independent of the selected period; outstanding is not a historical period-end balance.',
        'totals': 'Selected-period net totals', 'sales': 'Credit sales', 'repayments': 'Repayments',
        'daily': 'Daily financial trends', 'date': 'Recorded date',
        'reversal': 'Reversals negate the full original amount on their recorded day. Negative net values are valid.',
        'limits': 'Overdue amounts and credit aging remain unavailable. No estimates are included.',
        'fresh': 'Fresh read at export. Values may differ from an earlier screen view if records changed.',
        'currency': 'All amounts in LKR',
    },
    'ta': {
        'title': 'வணிக நிதி அறிக்கை', 'business': 'வணிகக் குறிப்பு',
        'period': 'தேர்ந்தெடுத்த காலம் (இரு தேதிகளும் உட்பட)', 'generated': 'உருவாக்கப்பட்ட நேரம் (UTC)',
        'clock': 'தேதிகள் தரவுத்தளத்தில் பதிவான கடிகாரத்தைப் பயன்படுத்துகின்றன. புவியியல் நேர மண்டலம் உறுதிப்படுத்தப்படவில்லை.',
        'current': 'தற்போதைய கண்ணோட்டம்', 'day': 'தரவுத்தள அறிக்கை நாள்',
        'outstanding': 'தற்போதைய நிலுவை', 'collected': 'இன்றைய நிகர வசூல்',
        'current_note': 'தற்போதைய தொகைகள் தேர்ந்தெடுத்த காலத்தைச் சாராதவை; நிலுவை என்பது வரலாற்றுக் கால இறுதி நிலுவை அல்ல.',
        'totals': 'தேர்ந்தெடுத்த காலத்தின் நிகர மொத்தங்கள்', 'sales': 'கடன் விற்பனை', 'repayments': 'திருப்பிச் செலுத்தல்கள்',
        'daily': 'தினசரி நிதிப் போக்குகள்', 'date': 'பதிவான தேதி',
        'reversal': 'எதிர்ப்பதிவுகள் பதிவான நாளில் அசல் தொகையை முழுமையாகக் கழிக்கும். எதிர்மறை நிகரத் தொகைகள் செல்லுபடியாகும்.',
        'limits': 'காலங்கடந்த கடன் தொகைகளும் கடன் காலப்பிரிவுகளும் கிடைக்கவில்லை. மதிப்பீடுகள் சேர்க்கப்படவில்லை.',
        'fresh': 'ஏற்றுமதியின் போது புதிதாக வாசிக்கப்பட்டது. பதிவுகள் மாறியிருந்தால் முந்தைய திரைக் காட்சியிலிருந்து தொகைகள் மாறலாம்.',
        'currency': 'அனைத்துத் தொகைகளும் LKR இல்',
    },
    'si': {
        'title': 'ව්‍යාපාර මූල්‍ය වාර්තාව', 'business': 'ව්‍යාපාර යොමුව',
        'period': 'තෝරාගත් කාලය (දින දෙකම ඇතුළුව)', 'generated': 'සාදන ලද වේලාව (UTC)',
        'clock': 'දින සඳහා භාවිත වන්නේ දත්තගබඩාවේ සටහන් කළ ඔරලෝසුවයි. භූගෝලීය වේලා කලාපයක් තහවුරු කර නැත.',
        'current': 'වත්මන් දළ විශ්ලේෂණය', 'day': 'දත්තගබඩා වාර්තා දිනය',
        'outstanding': 'වත්මන් හිඟ ශේෂය', 'collected': 'අද ශුද්ධ එකතු කිරීම්',
        'current_note': 'වත්මන් අගයන් තෝරාගත් කාලයෙන් ස්වාධීනයි; හිඟ ශේෂය ඓතිහාසික කාලය අවසානයේ ශේෂයක් නොවේ.',
        'totals': 'තෝරාගත් කාලයේ ශුද්ධ එකතුව', 'sales': 'ණය විකුණුම්', 'repayments': 'ආපසු ගෙවීම්',
        'daily': 'දෛනික මූල්‍ය ප්‍රවණතා', 'date': 'සටහන් කළ දිනය',
        'reversal': 'ආපසු හැරවීම් සටහන් කළ දිනයේ මුල් සම්පූර්ණ මුදල අඩු කරයි. ඍණ ශුද්ධ අගයන් වලංගුය.',
        'limits': 'කල් ඉකුත් වූ මුදල් සහ ණය කාල විශ්ලේෂණය ලබා ගත නොහැක. ඇස්තමේන්තු ඇතුළත් කර නැත.',
        'fresh': 'අපනයනය කරන විට නව කියවීමකි. වාර්තා වෙනස් වී ඇත්නම් පෙර තිරයේ අගයන්ගෙන් වෙනස් විය හැක.',
        'currency': 'සියලු මුදල් LKR වලින්',
    },
}


class ReportPDFUnavailable(Exception):
    pass


def report_font(language):
    candidates = [Path(__file__).parents[1] / 'assets/fonts' / {'en':'Vera.ttf','ta':'NotoSansTamil-Regular.ttf','si':'NotoSansSinhala-Regular.ttf'}[language]]
    if language == 'en':
        candidates.append(Path(reportlab.__file__).parent / 'fonts/Vera.ttf')
    else:
        candidates.append(Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts/Nirmala.ttf')
    for path in candidates:
        if path.is_file():
            font = pymupdf.Font(fontfile=str(path))
            text = ''.join(LABELS[language].values()) + ''.join(AGING_LABELS[language].values())
            if all(font.has_glyph(ord(char)) for char in text if not char.isspace() and char not in '\u200c\u200d'):
                return path
    raise ReportPDFUnavailable('Required report font is unavailable')


def report_html(data, language):
    labels = LABELS[language]
    def e(value): return escape(str(value), quote=True)
    def cash(value): return f'{money(value):,.2f}'
    def pair(label, value): return f'<tr><td style="width:68%">{e(label)}</td><td style="width:32%" class="amount">{e(cash(value))}</td></tr>'
    body = f'''<div class="brand">LankaPex</div><div class="tagline">Business Connects Everyone</div>
<h1>{e(labels['title'])}</h1>
<p>{e(labels['business'])}: VIVA-BUSINESS-{int(data['business_id'])}<br>
{e(labels['period'])}: {e(data['start_date'])} - {e(data['end_date'])}<br>
{e(labels['generated'])}: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
<p class="note">{e(labels['clock'])}</p>
<h2>{e(labels['current'])}</h2><p class="small">{e(labels['day'])}: {e(data['database_today'])} | {e(labels['currency'])}</p>
<table class="summary">{pair(labels['outstanding'],data['summary']['total_outstanding'])}{pair(labels['collected'],data['summary']['collected_today'])}</table>
<p class="note">{e(labels['current_note'])}</p>
<h2>{e(labels['totals'])}</h2><table class="summary">{pair(labels['sales'],data['totals']['credit_sales'])}{pair(labels['repayments'],data['totals']['repayments'])}</table>
<p class="note">{e(labels['reversal'])}</p><h2>{e(labels['daily'])}</h2>
<p class="small">{e(labels['currency'])}</p><table><tr><th style="width:30%">{e(labels['date'])}</th><th style="width:35%">{e(labels['sales'])}</th><th style="width:35%">{e(labels['repayments'])}</th></tr></table><table class="daily"><tbody>'''
    body += ''.join(f'<tr><td style="width:30%">{e(day["date"])}</td><td style="width:35%" class="amount">{e(cash(day["credit_sales"]))}</td><td style="width:35%" class="amount">{e(cash(day["repayments"]))}</td></tr>' for day in data['daily'])
    body += '</tbody></table>'
    aging = data.get('aging')
    if aging:
        a = AGING_LABELS[language]
        body += f'<h2>{e(a["title"])}</h2><p class="note">{e(a["policy"])}</p>'
        body += f'<p class="note">{e(a[aging["status"]])}</p>'
        if aging['buckets'] is not None:
            body += '<table>' + ''.join(pair(a[key], value) for key, value in aging['buckets'].items())
            body += pair(a['unclassified'], aging['unclassified'])
            if aging['overdue_amount'] is not None:
                body += pair(a['overdue'], aging['overdue_amount'])
            body += '</table>'
    else:
        body += f'<p class="note">{e(labels["limits"])}</p>'
    body += f'<p class="note">{e(labels["fresh"])}</p>'
    return f'<html lang="{language}"><body>{body}</body></html>'


def render_report_pdf(data, language='en'):
    if language not in LABELS or not _render_lock.acquire(timeout=5):
        raise ReportPDFUnavailable('PDF export unavailable')
    try:
        font = report_font(language)
        css = f'''@font-face {{font-family: ReportFont; src: url("{font.name}");}}
body {{font-family: ReportFont; font-size: 10pt; color: #10243e;}}
.brand {{font-size: 23pt; color: #10243e;}} .tagline {{font-size: 9pt; color: #087d78;}}
h1 {{font-size: 19pt; margin: 12pt 0 9pt; font-weight: normal;}}
h2 {{font-size: 13pt; color: #087d78; margin: 13pt 0 7pt; font-weight: normal;}}
p {{margin: 6pt 0;}} .note {{font-size: 8.5pt; color: #52698a;}} .small {{font-size: 9pt;}}
table {{width: 100%; border-collapse: collapse; margin: 5pt 0;}}
th {{color: #087d78; text-align: left; font-weight: normal;}}
td, th {{padding: 6pt; border-bottom: 0.5pt solid #d4e2ee;}}
.amount {{text-align: right; white-space: nowrap;}}
'''
        output = BytesIO()
        writer = pymupdf.DocumentWriter(output)
        try:
            story = pymupdf.Story(report_html(data, language), user_css=css,
                archive=pymupdf.Archive(str(font.parent)))
            pages = 0
            more = True
            while more:
                pages += 1
                if pages > 40:
                    raise ReportPDFUnavailable('Report exceeds PDF page limit')
                device = writer.begin_page(pymupdf.Rect(0,0,595,842))
                more, _ = story.place(pymupdf.Rect(40,35 if pages == 1 else 100,555,787))
                story.draw(device)
                writer.end_page()
        finally:
            writer.close()
        with pymupdf.open(stream=output.getvalue(),filetype='pdf') as document:
            document.set_metadata({'title':'LankaPex Financial Report','author':'LankaPex'})
            for page in document:
                if page.number:
                    labels = LABELS[language]
                    has_daily_dates = bool(re.search(r'\d{4}[-\u2010\u2011]\d{2}[-\u2010\u2011]\d{2}', page.get_text()))
                    header = (f'<p>LankaPex | {escape(labels["daily"])}</p>'
                        f'<table><tr><th style="width:30%">{escape(labels["date"])}</th>'
                        f'<th style="width:35%">{escape(labels["sales"])} (LKR)</th>'
                        f'<th style="width:35%">{escape(labels["repayments"])} (LKR)</th></tr></table>' if has_daily_dates else
                        f'<p>LankaPex | {escape(AGING_LABELS[language]["title"] if data.get("aging") else labels["title"])}</p><p>{escape(labels["currency"])}</p>')
                    remaining, _ = page.insert_htmlbox(pymupdf.Rect(40,30,555,95), header,
                        css=css, archive=pymupdf.Archive(str(font.parent)), scale_low=1)
                    if remaining < 0:
                        raise ReportPDFUnavailable('PDF continuation header does not fit')
                page.insert_text((40,815),'LankaPex | Financial Report',fontsize=8,color=(0.06,0.14,0.24))
                page.insert_text((490,815),f'{page.number+1} / {len(document)}',fontsize=8,color=(0.06,0.14,0.24))
            return document.tobytes(garbage=4,deflate=True)
    except ReportPDFUnavailable:
        raise
    except Exception:
        raise ReportPDFUnavailable('PDF rendering unavailable') from None
    finally:
        _render_lock.release()

"""Bounded multilingual Admin PDF. Reuses vetted font/shaping infrastructure."""
from html import escape
from io import BytesIO
import pymupdf
from app.services.admin_reports_csv import export_rows, LABELS
from app.services.shop_owner_reports_pdf import report_font, ReportPDFUnavailable, _render_lock


def render_report_pdf(report,comparisons,language='en'):
    if language not in LABELS: raise ReportPDFUnavailable('Unsupported report language')
    if not _render_lock.acquire(blocking=False): raise ReportPDFUnavailable('PDF renderer busy')
    try:
        font=report_font(language)
        rows=list(export_rows(report,comparisons,language))
        # Row keys remain stable English machine labels; section headings are localized.
        # Business names may contain any script: fail closed if the selected font cannot render them.
        chosen=pymupdf.Font(fontfile=str(font))
        if any(not chosen.has_glyph(ord(c)) for row in rows for value in row for c in str(value) if not c.isspace() and c not in '\u200c\u200d'):
            raise ReportPDFUnavailable('Report font cannot render this dataset')
        e=lambda value:escape(str(value),quote=True)
        labels=LABELS[language];data=report.model_dump(mode='json')
        html='<h1>LankaPex - '+e(labels['title'])+'</h1><p>Business Connects Everyone | LKR</p>'
        html+=f'<p>{e(labels["period"])}: {e(data["start_date"])} - {e(data["end_date"])}<br>{e(labels["generated"])}: {e(data["generated_at"])}</p>'
        def pairs(values):
            return '<table>'+''.join(f'<tr><td style="width:70%">{e(key)}</td><td style="width:30%">{e(value)}</td></tr>' for key,value in values.items())+'</table>'
        html+=pairs({key:data[key] if data[key] is not None else 'All' for key in ('business_id','approval_status','order_status','database_today','snapshot')})
        for key,title in [('reporting_clocks','clocks'),('coverage','coverage'),('unavailable','unavailable')]:
            html+='<h2>'+e(labels[title])+'</h2>'+pairs(data[key])
        html+='<h2>'+e(labels['limitations'])+'</h2><ul>'+''.join('<li>'+e(value)+'</li>' for value in data['limitations'])+'</ul>'
        for section in ('businesses','users','orders','deliveries','credit'):
            html+='<div style="page-break-before:always"><h2>'+e(labels[section])+'</h2>'+pairs({**data[section]['counts'],**data[section]['amounts']})+'</div>'
            daily=data[section]['daily']
            if daily:
                fields=list(daily[0]);html+='<table><tr>'+''.join('<th>'+e(key)+'</th>' for key in fields)+'</tr>'
                html+=''.join('<tr>'+''.join('<td>'+e(day[key])+'</td>' for key in fields)+'</tr>' for day in daily)+'</table>'
        html+='<div style="page-break-before:always"><h2>'+e(labels['comparisons'])+'</h2><p>All filtered rows; bounded to 1000 businesses</p>'
        fields=['business_id','business_name','approval_status','orders','product_order_total','credit_sales','repayments','outstanding','advances']
        html+='<table class="comparisons"><tr>'+''.join('<th>'+e(key.replace('_',' '))+'</th>' for key in fields)+'</tr>'
        html+=''.join('<tr>'+''.join('<td>'+e(getattr(row,key))+'</td>' for key in fields)+'</tr>' for row in comparisons)+'</table></div>'
        css=f'@font-face {{font-family: ReportFont; src: url("{font.name}");}} body {{font-family:ReportFont;font-size:9pt;color:#10243e;}} h1 {{font-size:19pt;color:#087d78;}} h2 {{font-size:13pt;color:#087d78;page-break-after:avoid;}} table {{width:100%;border-collapse:collapse;}} td,th {{padding:4pt;border-bottom:0.5pt solid #d4e2ee;overflow-wrap:anywhere;}} th {{text-align:left;color:#087d78;}} .comparisons {{font-size:8pt;}} li {{margin-bottom:4pt;}}'
        output=BytesIO(); writer=pymupdf.DocumentWriter(output)
        try:
            story=pymupdf.Story(html,user_css=css,archive=pymupdf.Archive(str(font.parent)))
            more=True; pages=0
            while more:
                pages+=1
                if pages>40: raise ReportPDFUnavailable('Report exceeds PDF page limit')
                device=writer.begin_page(pymupdf.Rect(0,0,842,595))
                more,_=story.place(pymupdf.Rect(30,35,812,555)); story.draw(device); writer.end_page()
        finally: writer.close()
        with pymupdf.open(stream=output.getvalue(),filetype='pdf') as document:
            document.set_metadata({'title':'LankaPex Platform Reports','author':'LankaPex'})
            for page in document:
                page.insert_text((30,580),f'LankaPex | Platform Reports | {page.number+1}/{len(document)}',fontsize=8)
            return document.tobytes(garbage=4,deflate=True)
    except ReportPDFUnavailable: raise
    except Exception:
        raise ReportPDFUnavailable('Admin PDF unavailable') from None
    finally: _render_lock.release()

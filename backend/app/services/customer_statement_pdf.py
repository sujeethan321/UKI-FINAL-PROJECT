"""Customer-authorized statement snapshots rendered with no client totals."""
from datetime import datetime, timezone
from io import BytesIO
from functools import lru_cache
from pathlib import Path
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle


@lru_cache(maxsize=1)
def statement_font():
    # Bundle-provided embedded font: portable, searchable, no missing-glyph
    # substitution. Unsupported scripts fail safely instead of corrupting names.
    font = TTFont("LankaPexVera", str(Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"))
    pdfmetrics.registerFont(font)
    return font


def render_statement_pdf(data):
    output = BytesIO()
    navy = colors.HexColor("#10243E")
    teal = colors.HexColor("#12B8A6")
    font = statement_font()
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = font.fontName
    styles.add(ParagraphStyle(name="Cell", fontName=font.fontName, fontSize=8, leading=11, wordWrap="CJK"))
    styles["Title"].textColor = navy
    styles["Heading2"].textColor = navy
    def para(value, style="Cell"):
        value = str(value)
        if any(ord(char) not in font.face.charToGlyph for char in value if not char.isspace()):
            raise ValueError("Statement contains unsupported font characters")
        return Paragraph(escape(value), styles[style])
    def cash(value):
        whole, fraction = value.split(".")
        sign = "-" if whole.startswith("-") else ""
        return f"LKR {sign}{int(whole.lstrip(chr(45))):,}.{fraction}"
    story = [para("LankaPex", "Title"), para("Business Connects Everyone"), Spacer(1, 12),
             para("Customer Credit Statement", "Heading2"), para(data["business_name"]),
             para("Customer: " + data["customer_name"]),
             para(f"Period: {data['start_date']} to {data['end_date']} (inclusive)"),
             para("Generated: " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")), Spacer(1, 14)]
    for label, key in [("Opening balance", "opening_balance"), ("Credit sales", "total_credit_sales"),
                       ("Repayment records", "total_repayments"), ("Reversal impact", "reversal_impact"),
                       ("Closing balance", "closing_balance")]:
        story.append(para(label + ": " + cash(data[key])))
    story.append(Spacer(1, 14))
    rows = [[para(x) for x in ["Recorded date / reference", "Type / status", "Debit (LKR)", "Credit (LKR)", "Balance (LKR)"]]]
    for row in data["transactions"]:
        rows.append([para(str(row["recorded_at"]).replace("T", " ") + " / " + row["reference"]),
                     para(row["entry_type"].replace("_", " ") + " / " + row["status"]),
                     para(cash(row["debit"])), para(cash(row["credit"])), para(cash(row["running_balance"]))])
    if len(rows) == 1:
        story.append(para("No activity in this period."))
    else:
        table = LongTable(rows, colWidths=[160, 95, 80, 80, 100], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F8F6")),
                                  ("LINEBELOW", (0, 0), (-1, 0), 1, teal),
                                  ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                  ("TOPPADDING", (0, 0), (-1, -1), 7),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                                  ("LINEBELOW", (0, 1), (-1, -1), .3, colors.HexColor("#D4E2EE"))]))
        story.append(table)
    story.append(Spacer(1, 14))
    for key in ["reversal_policy", "time_basis", "historical_limitations"]:
        story.extend([para(data[key]), Spacer(1, 6)])
    story.append(para("Repayment records do not independently verify bank or card settlement."))
    def footer(canvas, document):
        canvas.setFillColor(navy)
        canvas.setFont(font.fontName, 8)
        canvas.drawString(40, 25, "LankaPex - Customer Credit Statement")
        canvas.drawRightString(A4[0] - 40, 25, f"Page {document.page}")
    SimpleDocTemplate(output, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=35,
                      bottomMargin=45, title="LankaPex Customer Credit Statement", author="LankaPex").build(
                          story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()

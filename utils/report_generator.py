from io import BytesIO
from datetime import datetime
import os
from typing import Any, Dict, Optional, Union

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    Flowable,
)

# PUBLIC_INTERFACE
def generate_pdf(
    results: Dict[str, Any],
    pie_chart_buffer: Optional[Union[BytesIO, bytes]] = None,
    user_name: Optional[str] = None,
    city: Optional[str] = None,
    logo_path: Optional[str] = "assets/logo.png",
) -> BytesIO:
    """
    Generate a FinMate PDF report with header, summary tables, optional logo,
    expense breakdown and embedded chart, and footer with page numbers.

    Backward-compatible signature: generate_pdf(results, pie_chart_buffer=None)

    Parameters:
    - results: dict with numeric fields and optional 'breakdown' and 'investment_advice'
      Expected keys (numeric): 'income', 'total_expenses', 'savings', 'suggested_sip' (optional)
      Optional:
        - 'breakdown': dict of category->amount
        - 'investment_advice': list[str]
        - 'goal_progress': float or str (optional)
    - pie_chart_buffer: optional in-memory PNG bytes or BytesIO for the expense pie chart.
    - user_name: optional user display name for header.
    - city: optional city name for header.
    - logo_path: optional path to a logo image; if present it will be displayed in header.

    Returns:
    - BytesIO positioned at 0 containing the generated PDF bytes.
    """
    buffer = BytesIO()

    # Document with margins to accommodate header/footer
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="FinMate Financial Report",
        author="FinMate",
        subject="Personal Finance Analysis and Investment Advice",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SmallMuted", fontSize=8, textColor=colors.grey))
    styles.add(ParagraphStyle(name="TableHeader", fontSize=10, textColor=colors.white, backColor=colors.HexColor("#4B8BBE"), alignment=1, spaceAfter=4))
    styles.add(ParagraphStyle(name="Section", fontSize=14, spaceAfter=6, leading=16))
    normal = styles["Normal"]

    # Prepare header/footer draw functions
    def _header_footer(canvas, doc_):
        # Header
        canvas.saveState()
        header_y = doc_.pagesize[1] - 0.5 * inch
        # Logo if available
        if logo_path and os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)), logo_path) if not os.path.isabs(logo_path) else logo_path):
            lp = logo_path
            if not os.path.isabs(lp):
                lp = os.path.join(os.path.dirname(os.path.dirname(__file__)), lp)
            try:
                canvas.drawImage(lp, x=doc_.leftMargin, y=header_y - 18, width=36, height=36, preserveAspectRatio=True, mask='auto')
                text_x = doc_.leftMargin + 42
            except Exception:
                text_x = doc_.leftMargin
        else:
            text_x = doc_.leftMargin

        # Header text lines
        header_title = "FinMate Financial Report"
        subtitle_parts = []
        if user_name:
            subtitle_parts.append(user_name)
        if city:
            subtitle_parts.append(city)
        subtitle = " | ".join(subtitle_parts) if subtitle_parts else ""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")

        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(text_x, header_y, header_title)
        canvas.setFont("Helvetica", 9)
        if subtitle:
            canvas.drawString(text_x, header_y - 12, subtitle)
        canvas.setFont("Helvetica-Oblique", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(doc_.pagesize[0] - doc_.rightMargin, header_y, f"Generated: {ts}")
        canvas.setFillColor(colors.black)

        # Footer
        footer_y = 0.5 * inch - 20
        canvas.setStrokeColor(colors.lightgrey)
        canvas.line(doc_.leftMargin, footer_y + 14, doc_.pagesize[0] - doc_.rightMargin, footer_y + 14)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(doc_.leftMargin, footer_y, "FinMate • Personal Finance & Investment Buddy")
        canvas.drawRightString(doc_.pagesize[0] - doc_.rightMargin, footer_y, f"Page {doc_.page}")
        canvas.setFillColor(colors.black)
        canvas.restoreState()

    elements = []

    # Summary section
    elements.append(Paragraph("Summary", styles["Heading2"]))
    elements.append(Spacer(1, 6))

    income = float(results.get("income", 0) or 0)
    expenses = float(results.get("total_expenses", results.get("Total Expenses", 0)) or 0)
    savings = float(results.get("savings", results.get("Estimated Savings", 0)) or 0)
    suggested_sip = float(results.get("suggested_sip", results.get("Suggested SIP Investment", 0)) or 0)
    goal_progress = results.get("goal_progress", None)

    summary_data = [
        ["Income", f"₹{income:,.2f}"],
        ["Expenses", f"₹{expenses:,.2f}"],
        ["Savings", f"₹{savings:,.2f}"],
        ["Suggested SIP", f"₹{suggested_sip:,.2f}"],
    ]
    if goal_progress is not None:
        try:
            gp = float(goal_progress)
            summary_data.append(["Goal Progress", f"{gp:,.1f}%"])
        except Exception:
            summary_data.append(["Goal Progress", str(goal_progress)])

    summary_table = Table(summary_data, colWidths=[160, 160])
    summary_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4B8BBE")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))

    # Expense breakdown table
    breakdown = {}
    bd = results.get("breakdown") or results.get("Breakdown") or {}
    if isinstance(bd, dict):
        breakdown = bd

    if breakdown:
        elements.append(Paragraph("Expense Breakdown", styles["Heading2"]))
        elements.append(Spacer(1, 6))
        bd_rows = [["Category", "Amount (₹)"]]
        # normalize keys/values
        for cat, amt in breakdown.items():
            try:
                val = float(amt)
            except Exception:
                # Attempt to parse currency-like strings
                try:
                    val = float(str(amt).replace("₹", "").replace(",", "").strip())
                except Exception:
                    val = 0.0
            bd_rows.append([str(cat).title(), f"{val:,.2f}"])
        bd_table = Table(bd_rows, colWidths=[220, 120])
        bd_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4B8BBE")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        ]))
        elements.append(bd_table)
        elements.append(Spacer(1, 12))

    # Chart image
    if pie_chart_buffer:
        # Support raw bytes or BytesIO
        img_stream = pie_chart_buffer
        if isinstance(pie_chart_buffer, bytes):
            img_stream = BytesIO(pie_chart_buffer)
            img_stream.seek(0)
        elements.append(Paragraph("Expense Breakdown Chart", styles["Heading3"]))
        elements.append(Spacer(1, 6))
        try:
            pie_chart_image = Image(img_stream, width=5.5 * inch, height=3.5 * inch)
            elements.append(pie_chart_image)
            elements.append(Spacer(1, 12))
        except Exception:
            # If image fails to render, skip silently
            pass

    # Investment advice bullets
    advice_list = results.get("investment_advice") or results.get("advice") or []
    if advice_list:
        elements.append(Paragraph("Investment Advice", styles["Heading2"]))
        elements.append(Spacer(1, 6))
        for tip in advice_list:
            elements.append(Paragraph(f"• {tip}", normal))
            elements.append(Spacer(1, 2))

    # Build with header/footer on each page
    doc.build(elements, onFirstPage=_header_footer, onLaterPages=_header_footer)

    buffer.seek(0)
    return buffer
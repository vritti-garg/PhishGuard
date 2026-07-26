"""
pdf_generator.py
----------------
Stage 4: turns one stored EmailAnalysis record into a clean, client-
ready PDF incident report -- the kind of document IT/security teams
can save, forward, or attach to a ticket.

Uses reportlab's Platypus layer (not raw canvas) because we need
multi-paragraph flowing text -- reasoning and coaching messages vary
in length, and Platypus handles that wrapping automatically.
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

# Where generated PDFs get saved by default
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_reports")

# Color coding by severity -- makes the report scannable at a glance
SEVERITY_COLORS = {
    "low": colors.HexColor("#2e7d32"),
    "medium": colors.HexColor("#f9a825"),
    "high": colors.HexColor("#ef6c00"),
    "critical": colors.HexColor("#c62828"),
}


def generate_incident_pdf(analysis: dict, output_path: str = None) -> str:
    """
    Builds a one-page PDF report from a single analysis dict
    (same shape as EmailAnalysis.to_dict() from database/models.py).

    Returns the file path of the generated PDF.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if output_path is None:
        safe_id = analysis.get("id", "unknown")
        output_path = os.path.join(OUTPUT_DIR, f"incident_report_{safe_id}.pdf")

    doc = SimpleDocTemplate(output_path, pagesize=letter, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()

    # Custom style for the title block
    title_style = ParagraphStyle(
        "TitleStyle", parent=styles["Title"], alignment=TA_CENTER, fontSize=20
    )
    section_style = ParagraphStyle(
        "SectionStyle", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6
    )
    body_style = styles["Normal"]

    story = []

    # --- Header ---
    story.append(Paragraph("PhishGuard Incident Report", title_style))
    story.append(Spacer(1, 4))
    generated_on = datetime.now().strftime("%B %d, %Y at %H:%M")
    story.append(Paragraph(f"Generated on {generated_on}", body_style))
    story.append(Spacer(1, 16))

    # --- Summary table ---
    severity = analysis.get("severity", "unknown").lower()
    severity_color = SEVERITY_COLORS.get(severity, colors.grey)

    summary_data = [
        ["Field", "Value"],
        ["Sender", analysis.get("sender", "Unknown")],
        ["Subject", analysis.get("subject", "Unknown")],
        ["Verdict", analysis.get("verdict", "unknown").upper()],
        ["Technique", analysis.get("technique", "none_detected").replace("_", " ").title()],
        ["Severity", severity.upper()],
        ["Confidence", f"{float(analysis.get('confidence', 0)) * 100:.0f}%"],
        ["Analyzed At", str(analysis.get("analyzed_at", "Unknown"))],
    ]

    table = Table(summary_data, colWidths=[130, 350])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 3), (1, 3), severity_color),  # highlight verdict row
        ("TEXTCOLOR", (0, 3), (1, 3), colors.white),
        ("FONTNAME", (0, 3), (1, 3), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    story.append(table)
    story.append(Spacer(1, 16))

    # --- Reasoning section ---
    story.append(Paragraph("Analysis Reasoning", section_style))
    story.append(Paragraph(analysis.get("reasoning", "No reasoning provided."), body_style))

    # --- Manual review flag, if applicable ---
    if analysis.get("manual_review_required"):
        story.append(Spacer(1, 10))
        warning_style = ParagraphStyle(
            "Warning", parent=body_style, textColor=colors.red, fontName="Helvetica-Bold"
        )
        story.append(Paragraph(
            "⚠ Automated analysis was inconclusive. This email requires manual review.",
            warning_style
        ))

    # --- Coaching message section ---
    if analysis.get("coaching_message"):
        story.append(Spacer(1, 10))
        story.append(Paragraph("Employee Coaching Note", section_style))
        story.append(Paragraph(analysis["coaching_message"], body_style))

    doc.build(story)
    return output_path


# Quick manual test: builds a PDF from a dummy record
if __name__ == "__main__":
    dummy_analysis = {
        "id": 1,
        "sender": "IT Support <it-support@company-alerts-secure.com>",
        "subject": "Action Required: Password Expiring Today",
        "verdict": "phishing",
        "technique": "urgency_pressure",
        "severity": "high",
        "confidence": 0.88,
        "reasoning": "The email failed SPF, DKIM, and DMARC checks, used a shortened URL "
                     "(bit.ly) to hide the real destination, and applied urgency language "
                     "('2 hours', 'account lockout') to pressure a quick click.",
        "manual_review_required": False,
        "coaching_message": "This email used urgency to rush you into clicking without "
                             "checking. Next time, look for pressure language like tight "
                             "deadlines or threats of account loss -- and verify directly "
                             "with IT before clicking any link.",
        "analyzed_at": "2026-07-24T18:00:00",
    }

    path = generate_incident_pdf(dummy_analysis)
    print(f"PDF generated at: {path}")
"""
PDF Report Generator

Generates branded PDF reports for tenant gap analysis and tenant matching results.
Uses ReportLab for PDF generation.
"""

import io
import logging
import re
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

logger = logging.getLogger(__name__)

# Brand colors
ACCENT_GREEN = colors.HexColor("#10b981")
DARK_TEXT = colors.HexColor("#1a1a1a")
MUTED_TEXT = colors.HexColor("#6b7280")
LIGHT_BG = colors.HexColor("#f9fafb")
BORDER_COLOR = colors.HexColor("#e5e7eb")


def _build_styles() -> dict:
    """Build custom paragraph styles for the report."""
    base = getSampleStyleSheet()

    styles = {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontSize=22,
            textColor=DARK_TEXT,
            spaceAfter=6,
            fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontSize=11,
            textColor=MUTED_TEXT,
            spaceAfter=20,
        ),
        "section": ParagraphStyle(
            "SectionHeader",
            parent=base["Heading2"],
            fontSize=14,
            textColor=DARK_TEXT,
            spaceBefore=16,
            spaceAfter=8,
            fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "BodyText",
            parent=base["Normal"],
            fontSize=10,
            textColor=DARK_TEXT,
            leading=14,
        ),
        "muted": ParagraphStyle(
            "MutedText",
            parent=base["Normal"],
            fontSize=9,
            textColor=MUTED_TEXT,
        ),
        "accent": ParagraphStyle(
            "AccentText",
            parent=base["Normal"],
            fontSize=10,
            textColor=ACCENT_GREEN,
            fontName="Helvetica-Bold",
        ),
    }
    return styles


def generate_tenant_gap_report(
    property_name: str,
    property_address: str,
    trade_area_miles: float,
    current_tenants: list[dict] | None = None,
    tenant_gaps: list[dict] | None = None,
    recommended_tenants: list[dict] | None = None,
    demographics: dict | None = None,
) -> bytes:
    """
    Generate a branded PDF report for tenant gap analysis results.

    Args:
        property_name: Name of the property
        property_address: Full address
        trade_area_miles: Trade area radius used
        current_tenants: List of current tenant dicts with name, category
        tenant_gaps: List of gap dicts with category, priority
        recommended_tenants: List of recommended tenant dicts with name, category, match_score
        demographics: Demographics summary dict

    Returns:
        PDF file as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    styles = _build_styles()
    elements = []

    # Header
    elements.append(Paragraph("Space Goose", styles["muted"]))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"Tenant Gap Analysis Report", styles["title"]))
    elements.append(
        Paragraph(
            f"{property_name or 'Property'} &mdash; {property_address}",
            styles["subtitle"],
        )
    )
    elements.append(
        Paragraph(
            f"Trade area: {trade_area_miles}-mile radius &bull; "
            f"Generated {datetime.now().strftime('%B %d, %Y')}",
            styles["muted"],
        )
    )
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR))
    elements.append(Spacer(1, 12))

    # Demographics summary
    if demographics:
        elements.append(Paragraph("Trade area demographics", styles["section"]))
        demo_data = [
            ["Population", "Median income", "Median age", "Households"],
            [
                f"{demographics.get('population', 'N/A'):,}" if isinstance(demographics.get('population'), (int, float)) else str(demographics.get('population', 'N/A')),
                f"${demographics.get('median_income', 0):,.0f}" if demographics.get('median_income') else 'N/A',
                str(demographics.get('median_age', 'N/A')),
                f"{demographics.get('households', 'N/A'):,}" if isinstance(demographics.get('households'), (int, float)) else str(demographics.get('households', 'N/A')),
            ],
        ]
        demo_table = Table(demo_data, colWidths=[1.5 * inch] * 4)
        demo_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), MUTED_TEXT),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTSIZE", (0, 1), (-1, 1), 11),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ])
        )
        elements.append(demo_table)
        elements.append(Spacer(1, 16))

    # Current tenant strengths
    if current_tenants:
        elements.append(Paragraph("Current tenant mix", styles["section"]))

        # Group by category
        categories: dict[str, list[str]] = {}
        for t in current_tenants:
            cat = t.get("category", "Other")
            categories.setdefault(cat, []).append(t.get("name", "Unknown"))

        for cat, names in sorted(categories.items()):
            elements.append(
                Paragraph(
                    f"<b>{cat}</b> ({len(names)}): {', '.join(names[:8])}"
                    + (f" +{len(names) - 8} more" if len(names) > 8 else ""),
                    styles["body"],
                )
            )
        elements.append(Spacer(1, 12))

    # Tenant gaps
    if tenant_gaps:
        elements.append(Paragraph("Identified tenant gaps", styles["section"]))
        elements.append(
            Paragraph(
                "Categories with missing or underrepresented tenants in the trade area:",
                styles["muted"],
            )
        )
        elements.append(Spacer(1, 6))

        gap_data = [["Category", "Priority", "Notes"]]
        for gap in tenant_gaps:
            gap_data.append([
                gap.get("category", "Unknown"),
                gap.get("priority", "Medium"),
                gap.get("notes", ""),
            ])

        gap_table = Table(gap_data, colWidths=[2 * inch, 1.2 * inch, 3.3 * inch])
        gap_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), MUTED_TEXT),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, 0), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
            ])
        )
        elements.append(gap_table)
        elements.append(Spacer(1, 16))

    # Recommended tenants
    if recommended_tenants:
        elements.append(Paragraph("Recommended tenants", styles["section"]))
        elements.append(
            Paragraph(
                "Tenants that match this trade area based on demographics, gap analysis, and expansion criteria:",
                styles["muted"],
            )
        )
        elements.append(Spacer(1, 6))

        rec_data = [["Tenant", "Category", "Match score", "Distance"]]
        for t in recommended_tenants:
            score = t.get("match_score")
            score_str = f"{score}%" if score is not None else "N/A"
            dist = t.get("distance_miles")
            dist_str = f"{dist:.1f} mi" if dist is not None else "N/A"
            rec_data.append([
                t.get("name", "Unknown"),
                t.get("category", ""),
                score_str,
                dist_str,
            ])

        rec_table = Table(rec_data, colWidths=[2.2 * inch, 1.8 * inch, 1.2 * inch, 1.3 * inch])
        rec_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), MUTED_TEXT),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (2, 0), (3, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
            ])
        )
        elements.append(rec_table)
        elements.append(Spacer(1, 16))

    # Footer
    elements.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR))
    elements.append(Spacer(1, 8))
    elements.append(
        Paragraph(
            f"Generated by Space Goose &mdash; {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            styles["muted"],
        )
    )

    doc.build(elements)
    return buffer.getvalue()


def generate_session_report(
    title: str,
    sections: list[dict[str, str]],
    report_type: str = "comprehensive",
) -> bytes:
    """
    Generate a PDF report from chat session analysis sections.

    Args:
        title: Report title
        sections: List of dicts with 'type' and 'content' keys (markdown content)
        report_type: Type of report for filtering
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = _build_styles()
    elements = []

    # Header
    elements.append(Paragraph(title, styles["title"]))
    elements.append(
        Paragraph(
            f"Generated {datetime.now().strftime('%B %d, %Y')}",
            styles["subtitle"],
        )
    )
    elements.append(HRFlowable(width="100%", thickness=2, color=ACCENT_GREEN))
    elements.append(Spacer(1, 12))

    # Convert markdown sections to PDF elements
    for section in sections:
        content = section.get("content", "")
        section_type = section.get("type", "analysis")

        for line in content.split("\n"):
            line = line.strip()
            if not line:
                elements.append(Spacer(1, 4))
                continue

            # Headers
            if line.startswith("## "):
                elements.append(Paragraph(line[3:], styles["section"]))
            elif line.startswith("### "):
                elements.append(Paragraph(line[4:], styles.get("subsection", styles["section"])))
            # Bullet points
            elif line.startswith("- ") or line.startswith("* "):
                text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line[2:])
                elements.append(Paragraph(f"&bull; {text}", styles["body"]))
            # Source badges
            elif line.startswith("> **Source:**"):
                source_text = line.replace("> **Source:**", "Source:").strip()
                elements.append(Spacer(1, 4))
                elements.append(Paragraph(f"<i>{source_text}</i>", styles["muted"]))
            # Regular text
            elif not line.startswith("#"):
                text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
                elements.append(Paragraph(text, styles["body"]))

    # Methodology footer
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Data Sources &amp; Methodology", styles["section"]))
    elements.append(
        Paragraph(
            "This report may include data from the following sources: "
            "U.S. Census Bureau (ACS 5-Year Estimates), Google Places API, "
            "CoStar Group, Placer.ai, and SiteUSA. "
            "Trade area demographics are based on the specified mile radius from the property address. "
            "Business data reflects conditions at the time of query.",
            styles["muted"],
        )
    )

    # Footer
    elements.append(Spacer(1, 12))
    elements.append(
        Paragraph(
            f"Generated by Space Goose &mdash; {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            styles["muted"],
        )
    )

    doc.build(elements)
    return buffer.getvalue()

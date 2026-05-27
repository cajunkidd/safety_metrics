import csv
import io
from datetime import date

import matplotlib

matplotlib.use("Agg")  # noqa: E402 — must precede pyplot import

import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import LETTER  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import inch  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session  # noqa: E402

from app.metrics import compute_metrics  # noqa: E402
from app.models import Incident  # noqa: E402

PALETTE = [
    "#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed",
    "#0891b2", "#db2777", "#65a30d", "#9333ea", "#0d9488",
]

CSV_COLUMNS = [
    "incident_date", "incident_time", "store_location", "incident_type",
    "recordable", "reporter", "reporter_position", "summary",
    "body_part", "body_side", "injury_cause",
    "customer_name", "employee_name",
    "customer_statement", "employee_statement",
    "video_available", "drug_screen", "photos_info", "witnesses_info",
]


def generate_csv(db: Session) -> bytes:
    incidents = (
        db.query(Incident).order_by(Incident.incident_date, Incident.id).all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for i in incidents:
        writer.writerow(
            [
                i.incident_date.isoformat() if i.incident_date else "",
                i.incident_time or "",
                i.store_location or "",
                i.incident_type or "",
                "Yes" if i.recordable else "No",
                i.reporter or "",
                i.reporter_position or "",
                i.summary or "",
                i.body_part or "",
                i.body_side or "",
                i.injury_cause or "",
                i.customer_name or "",
                i.employee_name or "",
                i.customer_statement or "",
                i.employee_statement or "",
                i.video_available or "",
                i.drug_screen or "",
                i.photos_info or "",
                i.witnesses_info or "",
            ]
        )
    return buf.getvalue().encode("utf-8")


def _chart_png(plot_fn, width: float, height: float) -> bytes:
    fig = plt.figure(figsize=(width, height))
    try:
        plot_fn(fig)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        return buf.getvalue()
    finally:
        plt.close(fig)


def _no_data(ax, title: str) -> None:
    ax.text(0.5, 0.5, "No data", ha="center", va="center", color="#94a3b8")
    ax.set_axis_off()
    ax.set_title(title)


def _stacked_trend(fig, monthly):
    ax = fig.add_subplot(111)
    if not monthly["labels"]:
        _no_data(ax, "Monthly Trend")
        return
    labels = monthly["labels"]
    rec = monthly["recordable"]
    non_rec = monthly["non_recordable"]
    ax.bar(labels, non_rec, label="Non-recordable", color=PALETTE[0])
    ax.bar(labels, rec, bottom=non_rec, label="Recordable", color=PALETTE[2])
    ax.set_title("Monthly Trend (recordable vs non-recordable)")
    ax.set_ylabel("Incidents")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="upper left", fontsize=8)


def _hbar(fig, title, chart):
    ax = fig.add_subplot(111)
    labels, counts = chart["labels"], chart["counts"]
    if not labels:
        _no_data(ax, title)
        return
    bar_colors = [PALETTE[i % len(PALETTE)] for i in range(len(labels))]
    ax.barh(labels, counts, color=bar_colors)
    ax.set_title(title)
    ax.invert_yaxis()
    ax.grid(True, axis="x", alpha=0.3)


def _pie(fig, title, chart):
    ax = fig.add_subplot(111)
    if not chart["labels"]:
        _no_data(ax, title)
        return
    ax.pie(
        chart["counts"], labels=chart["labels"], autopct="%1.0f%%",
        colors=PALETTE[: len(chart["labels"])],
    )
    ax.set_title(title)


def _compliance_bar(fig, compliance):
    ax = fig.add_subplot(111)
    if not compliance["labels"]:
        _no_data(ax, "Documentation Compliance")
        return
    ax.bar(compliance["labels"], compliance["percentages"], color=PALETTE[1])
    ax.set_title("Documentation Compliance")
    ax.set_ylabel("%")
    ax.set_ylim(0, 100)
    ax.grid(True, axis="y", alpha=0.3)


def _kpi_table(metrics: dict) -> Table:
    days_last = metrics["days_since_last_incident"]
    days_rec = metrics["days_since_last_recordable"]
    kpis = [
        ("Total Incidents", str(metrics["total_incidents"])),
        ("Recordable Incidents", str(metrics["recordable_count"])),
        ("Recordable Rate", f"{metrics['recordable_rate_pct']}%"),
        (
            "Days Since Last Incident",
            "—" if days_last is None else str(days_last),
        ),
        (
            "Days Since Last Recordable",
            "—" if days_rec is None else str(days_rec),
        ),
        ("Injury Reports", str(metrics["injury_total"])),
    ]
    rows = []
    for i in range(0, len(kpis), 2):
        left = kpis[i]
        right = kpis[i + 1] if i + 1 < len(kpis) else ("", "")
        rows.append([left[0], left[1], right[0], right[1]])

    table = Table(
        rows, colWidths=[2.1 * inch, 1.2 * inch, 2.1 * inch, 1.2 * inch]
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#eff6ff")),
                ("BACKGROUND", (3, 0), (3, -1), colors.HexColor("#eff6ff")),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("ALIGN", (3, 0), (3, -1), "CENTER"),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def generate_pdf(db: Session) -> bytes:
    metrics = compute_metrics(db)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        title="Safety Metrics Report",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "report_title", parent=styles["Title"], fontSize=20, alignment=1
    )
    subtitle_style = ParagraphStyle(
        "report_subtitle", parent=styles["Normal"], alignment=1,
        textColor=colors.grey,
    )
    section_style = ParagraphStyle(
        "section", parent=styles["Heading2"], spaceBefore=12, spaceAfter=6
    )

    story = [
        Paragraph("Safety Metrics Report", title_style),
        Paragraph(f"Generated {date.today().isoformat()}", subtitle_style),
        Spacer(1, 16),
        Paragraph("Key Performance Indicators", section_style),
        _kpi_table(metrics),
        Spacer(1, 16),
        Paragraph("Trends and Breakdowns", section_style),
    ]

    trend_png = _chart_png(
        lambda f: _stacked_trend(f, metrics["monthly_trend"]),
        width=7.5, height=3,
    )
    story.append(RLImage(io.BytesIO(trend_png), width=7.5 * inch, height=3 * inch))
    story.append(Spacer(1, 12))

    store_png = _chart_png(
        lambda f: _hbar(f, "By Store Location", metrics["by_store"]),
        width=3.7, height=2.8,
    )
    type_png = _chart_png(
        lambda f: _pie(f, "Customer vs Employee", metrics["by_type"]),
        width=3.7, height=2.8,
    )
    body_png = _chart_png(
        lambda f: _hbar(f, "Top Body Parts Injured", metrics["by_body_part"]),
        width=3.7, height=2.8,
    )
    cause_png = _chart_png(
        lambda f: _hbar(f, "Top Primary Causes of Injury", metrics["by_injury_cause"]),
        width=3.7, height=2.8,
    )

    img_table = Table(
        [
            [
                RLImage(io.BytesIO(store_png), width=3.7 * inch, height=2.8 * inch),
                RLImage(io.BytesIO(type_png), width=3.7 * inch, height=2.8 * inch),
            ],
            [
                RLImage(io.BytesIO(body_png), width=3.7 * inch, height=2.8 * inch),
                RLImage(io.BytesIO(cause_png), width=3.7 * inch, height=2.8 * inch),
            ],
        ],
        colWidths=[3.8 * inch, 3.8 * inch],
    )
    img_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    story.append(img_table)
    story.append(Spacer(1, 12))

    compliance_png = _chart_png(
        lambda f: _compliance_bar(f, metrics["compliance"]),
        width=7.5, height=2.5,
    )
    story.append(
        RLImage(io.BytesIO(compliance_png), width=7.5 * inch, height=2.5 * inch)
    )

    doc.build(story)
    return buf.getvalue()

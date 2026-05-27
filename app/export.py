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
    "date", "department", "incident_type", "severity",
    "description", "days_lost", "status",
]


def generate_csv(db: Session) -> bytes:
    incidents = (
        db.query(Incident).order_by(Incident.date, Incident.id).all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for i in incidents:
        writer.writerow(
            [
                i.date.isoformat() if i.date else "",
                i.department or "",
                i.incident_type or "",
                i.severity or "",
                i.description or "",
                "" if i.days_lost is None else i.days_lost,
                i.status or "",
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


def _line_trend(fig, monthly):
    ax = fig.add_subplot(111)
    if not monthly["labels"]:
        _no_data(ax, "Monthly Incident Trend")
        return
    ax.plot(
        monthly["labels"], monthly["counts"],
        color=PALETTE[0], marker="o", linewidth=2,
    )
    ax.fill_between(monthly["labels"], monthly["counts"], alpha=0.15, color=PALETTE[0])
    ax.set_title("Monthly Incident Trend")
    ax.set_ylabel("Incidents")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0)


def _bar_chart(fig, title, chart):
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


def _pie_chart(fig, title, chart):
    ax = fig.add_subplot(111)
    if not chart["labels"]:
        _no_data(ax, title)
        return
    ax.pie(
        chart["counts"],
        labels=chart["labels"],
        autopct="%1.0f%%",
        colors=PALETTE[: len(chart["labels"])],
    )
    ax.set_title(title)


def _kpi_table(metrics: dict) -> Table:
    kpis = [
        ("Total Incidents", str(metrics["total_incidents"])),
        ("Last 30 Days", str(metrics["incidents_last_30_days"])),
        (
            "Days Since Last Incident",
            "—" if metrics["days_since_last_incident"] is None
            else str(metrics["days_since_last_incident"]),
        ),
        ("Lost-Time Incidents", str(metrics["lost_time_count"])),
        ("Total Lost Workdays", f"{metrics['total_lost_days']:.1f}"),
        ("Open Corrective Actions", str(metrics["open_corrective_actions"])),
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
        "report_subtitle",
        parent=styles["Normal"],
        alignment=1,
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
        lambda f: _line_trend(f, metrics["monthly_trend"]),
        width=7.5, height=3,
    )
    story.append(RLImage(io.BytesIO(trend_png), width=7.5 * inch, height=3 * inch))
    story.append(Spacer(1, 12))

    type_png = _chart_png(
        lambda f: _bar_chart(f, "Incidents by Type", metrics["by_type"]),
        width=3.7, height=2.8,
    )
    sev_png = _chart_png(
        lambda f: _pie_chart(f, "Incidents by Severity", metrics["by_severity"]),
        width=3.7, height=2.8,
    )
    dept_png = _chart_png(
        lambda f: _bar_chart(f, "Incidents by Department", metrics["by_department"]),
        width=3.7, height=2.8,
    )

    img_table = Table(
        [
            [
                RLImage(io.BytesIO(type_png), width=3.7 * inch, height=2.8 * inch),
                RLImage(io.BytesIO(sev_png), width=3.7 * inch, height=2.8 * inch),
            ],
            [
                RLImage(io.BytesIO(dept_png), width=3.7 * inch, height=2.8 * inch),
                "",
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

    doc.build(story)
    return buf.getvalue()

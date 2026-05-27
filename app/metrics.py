from collections import Counter
from datetime import date

from sqlalchemy.orm import Session

from app.models import Incident

LOST_TIME_LABEL = "lost time"
OPEN_STATUS = "open"


def _empty_metrics() -> dict:
    empty_chart = {"labels": [], "counts": []}
    return {
        "total_incidents": 0,
        "incidents_last_30_days": 0,
        "days_since_last_incident": None,
        "total_lost_days": 0,
        "lost_time_count": 0,
        "open_corrective_actions": 0,
        "monthly_trend": dict(empty_chart),
        "by_type": dict(empty_chart),
        "by_severity": dict(empty_chart),
        "by_department": dict(empty_chart),
    }


def _counter_to_chart(counter: Counter) -> dict:
    items = counter.most_common()
    return {
        "labels": [label for label, _ in items],
        "counts": [count for _, count in items],
    }


def _monthly_trend(dates) -> dict:
    if not dates:
        return {"labels": [], "counts": []}

    counts = Counter((d.year, d.month) for d in dates)
    start, end = min(dates), max(dates)

    labels, values = [], []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        labels.append(f"{year:04d}-{month:02d}")
        values.append(counts.get((year, month), 0))
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return {"labels": labels, "counts": values}


def compute_metrics(db: Session) -> dict:
    incidents = db.query(Incident).all()
    if not incidents:
        return _empty_metrics()

    today = date.today()
    dates = [i.date for i in incidents if i.date]

    incidents_last_30 = sum(1 for d in dates if 0 <= (today - d).days <= 30)
    last_incident = max(dates) if dates else None

    return {
        "total_incidents": len(incidents),
        "incidents_last_30_days": incidents_last_30,
        "days_since_last_incident": (
            (today - last_incident).days if last_incident else None
        ),
        "total_lost_days": sum(i.days_lost or 0 for i in incidents),
        "lost_time_count": sum(
            1
            for i in incidents
            if (i.severity or "").strip().lower() == LOST_TIME_LABEL
        ),
        "open_corrective_actions": sum(
            1 for i in incidents if (i.status or "").strip().lower() == OPEN_STATUS
        ),
        "monthly_trend": _monthly_trend(dates),
        "by_type": _counter_to_chart(
            Counter((i.incident_type or "Unknown").strip() for i in incidents)
        ),
        "by_severity": _counter_to_chart(
            Counter((i.severity or "Unknown").strip() for i in incidents)
        ),
        "by_department": _counter_to_chart(
            Counter((i.department or "Unknown").strip() for i in incidents)
        ),
    }

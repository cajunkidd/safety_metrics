from collections import Counter
from datetime import date
from typing import Iterable, List

from sqlalchemy.orm import Session

from app.models import Incident

TOP_N = 8  # how many entries to show on "top N" bar charts


def _empty_chart() -> dict:
    return {"labels": [], "counts": []}


def _empty_metrics() -> dict:
    return {
        "total_incidents": 0,
        "recordable_count": 0,
        "non_recordable_count": 0,
        "recordable_rate_pct": 0,
        "days_since_last_incident": None,
        "days_since_last_recordable": None,
        "monthly_trend": {
            "labels": [],
            "recordable": [],
            "non_recordable": [],
        },
        "by_store": _empty_chart(),
        "by_type": _empty_chart(),
        "injury_total": 0,
        "by_body_part": _empty_chart(),
        "by_injury_cause": _empty_chart(),
        "compliance": {
            "labels": [],
            "percentages": [],
        },
    }


def _counter_to_chart(counter: Counter, limit: int = TOP_N) -> dict:
    items = counter.most_common(limit)
    return {
        "labels": [label for label, _ in items],
        "counts": [count for _, count in items],
    }


def _monthly_trend(incidents: Iterable[Incident]) -> dict:
    rec = Counter()
    non_rec = Counter()
    dates: List[date] = []
    for inc in incidents:
        if not inc.incident_date:
            continue
        key = (inc.incident_date.year, inc.incident_date.month)
        if inc.recordable:
            rec[key] += 1
        else:
            non_rec[key] += 1
        dates.append(inc.incident_date)

    if not dates:
        return {"labels": [], "recordable": [], "non_recordable": []}

    start, end = min(dates), max(dates)
    labels, rec_counts, non_rec_counts = [], [], []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        labels.append(f"{y:04d}-{m:02d}")
        rec_counts.append(rec.get((y, m), 0))
        non_rec_counts.append(non_rec.get((y, m), 0))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return {
        "labels": labels,
        "recordable": rec_counts,
        "non_recordable": non_rec_counts,
    }


def _compliance(incidents: List[Incident]) -> dict:
    """Percent of incidents where a documentation step was confirmed.

    For Yes/No fields the rate is yes / (yes + no), ignoring rows where
    the question wasn't asked (different form branch). For free-text
    fields, we count rows where the value is non-empty.
    """

    def _yes_no_rate(values):
        yes = sum(1 for v in values if (v or "").strip().lower() == "yes")
        no = sum(1 for v in values if (v or "").strip().lower() == "no")
        denom = yes + no
        return int(round(yes * 100 / denom)) if denom else 0

    def _filled_rate(values):
        filled = sum(1 for v in values if v and str(v).strip())
        denom = sum(1 for v in values if v is not None and str(v).strip())
        # "Filled" and "denom" are the same here — keep as a percent of
        # total incidents so it can be compared with the others.
        return (
            int(round(filled * 100 / len(values))) if values else 0
        )

    written_statement_values = [
        (i.customer_statement or "")
        if i.customer_statement
        else (i.employee_statement or "")
        for i in incidents
    ]

    return {
        "labels": [
            "Photos taken",
            "Video available",
            "Drug screen",
            "Written statement",
        ],
        "percentages": [
            _filled_rate([i.photos_info for i in incidents]),
            _yes_no_rate([i.video_available for i in incidents]),
            _yes_no_rate([i.drug_screen for i in incidents]),
            _yes_no_rate(written_statement_values),
        ],
    }


def compute_metrics(db: Session) -> dict:
    incidents = db.query(Incident).all()
    if not incidents:
        return _empty_metrics()

    total = len(incidents)
    recordable = [i for i in incidents if i.recordable]
    recordable_count = len(recordable)
    non_recordable_count = total - recordable_count

    today = date.today()
    all_dates = [i.incident_date for i in incidents if i.incident_date]
    rec_dates = [i.incident_date for i in recordable if i.incident_date]

    days_since_last = (
        (today - max(all_dates)).days if all_dates else None
    )
    days_since_recordable = (
        (today - max(rec_dates)).days if rec_dates else None
    )

    by_store = _counter_to_chart(
        Counter(
            (i.store_location or "Unknown").strip() for i in incidents
        )
    )
    by_type = _counter_to_chart(
        Counter(
            (i.incident_type or "Unknown").strip() for i in incidents
        ),
        limit=10,
    )

    injuries = [
        i for i in incidents if i.body_part or i.injury_cause
    ]
    by_body_part = _counter_to_chart(
        Counter(
            (i.body_part or "Unknown").strip() for i in injuries if i.body_part
        )
    )
    by_injury_cause = _counter_to_chart(
        Counter(
            (i.injury_cause or "Unknown").strip()
            for i in injuries
            if i.injury_cause
        )
    )

    return {
        "total_incidents": total,
        "recordable_count": recordable_count,
        "non_recordable_count": non_recordable_count,
        "recordable_rate_pct": (
            int(round(recordable_count * 100 / total)) if total else 0
        ),
        "days_since_last_incident": days_since_last,
        "days_since_last_recordable": days_since_recordable,
        "monthly_trend": _monthly_trend(incidents),
        "by_store": by_store,
        "by_type": by_type,
        "injury_total": len(injuries),
        "by_body_part": by_body_part,
        "by_injury_cause": by_injury_cause,
        "compliance": _compliance(incidents),
    }

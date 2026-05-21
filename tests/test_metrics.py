from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.metrics import compute_metrics
from app.models import Incident, Upload


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_empty_metrics():
    db = _make_session()
    metrics = compute_metrics(db)

    assert metrics["total_incidents"] == 0
    assert metrics["days_since_last_incident"] is None
    assert metrics["monthly_trend"] == {"labels": [], "counts": []}


def test_metrics_computation():
    db = _make_session()
    upload = Upload(filename="t.csv", row_count=3)
    db.add(upload)
    db.flush()

    today = date.today()
    db.add_all(
        [
            Incident(
                upload_id=upload.id,
                date=today - timedelta(days=5),
                department="A",
                incident_type="Injury",
                severity="Lost Time",
                days_lost=4,
                status="Open",
            ),
            Incident(
                upload_id=upload.id,
                date=today - timedelta(days=40),
                department="B",
                incident_type="Near Miss",
                severity="First Aid",
                days_lost=0,
                status="Closed",
            ),
            Incident(
                upload_id=upload.id,
                date=today - timedelta(days=2),
                department="A",
                incident_type="Injury",
                severity="Recordable",
                days_lost=1,
                status="Open",
            ),
        ]
    )
    db.commit()

    metrics = compute_metrics(db)

    assert metrics["total_incidents"] == 3
    assert metrics["incidents_last_30_days"] == 2
    assert metrics["days_since_last_incident"] == 2
    assert metrics["lost_time_count"] == 1
    assert metrics["total_lost_days"] == 5
    assert metrics["open_corrective_actions"] == 2

    by_dept = dict(
        zip(metrics["by_department"]["labels"], metrics["by_department"]["counts"])
    )
    assert by_dept["A"] == 2
    assert by_dept["B"] == 1

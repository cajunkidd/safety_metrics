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
    m = compute_metrics(db)
    assert m["total_incidents"] == 0
    assert m["recordable_count"] == 0
    assert m["recordable_rate_pct"] == 0
    assert m["days_since_last_incident"] is None
    assert m["days_since_last_recordable"] is None
    assert m["monthly_trend"] == {"labels": [], "recordable": [], "non_recordable": []}


def test_metrics_with_data():
    db = _make_session()
    upload = Upload(filename="t.xlsx", row_count=4)
    db.add(upload)
    db.flush()

    today = date.today()
    incidents = [
        Incident(
            upload_id=upload.id,
            incident_date=today - timedelta(days=2),
            store_location="11 - Sulphur",
            incident_type="Employee Incident",
            recordable=True,
            body_part="Back",
            injury_cause="Exertion - Lifting",
            video_available="Yes",
            drug_screen="Yes",
            photos_info="3 by manager",
            employee_statement="Yes",
        ),
        Incident(
            upload_id=upload.id,
            incident_date=today - timedelta(days=10),
            store_location="13 - Lake Charles",
            incident_type="Customer Incident",
            recordable=False,
            customer_statement="Yes",
        ),
        Incident(
            upload_id=upload.id,
            incident_date=today - timedelta(days=400),
            store_location="11 - Sulphur",
            incident_type="Employee Incident",
            recordable=True,
            body_part="Knee",
            injury_cause="Slip, Trip or Fall - Same Level",
            video_available="No",
            drug_screen="No",
            photos_info="",
            employee_statement="No",
        ),
        Incident(
            upload_id=upload.id,
            incident_date=today - timedelta(days=5),
            store_location="22 - Walker",
            incident_type="Employee Incident",
            recordable=False,
            body_part="Back",
            injury_cause="Exertion - Lifting",
            video_available="Yes",
            drug_screen="No",
            photos_info="1 by associate",
            employee_statement="Yes",
        ),
    ]
    db.add_all(incidents)
    db.commit()

    m = compute_metrics(db)
    assert m["total_incidents"] == 4
    assert m["recordable_count"] == 2
    assert m["non_recordable_count"] == 2
    assert m["recordable_rate_pct"] == 50
    assert m["days_since_last_incident"] == 2
    assert m["days_since_last_recordable"] == 2
    assert m["injury_total"] == 3

    by_store = dict(zip(m["by_store"]["labels"], m["by_store"]["counts"]))
    assert by_store["11 - Sulphur"] == 2

    by_body = dict(
        zip(m["by_body_part"]["labels"], m["by_body_part"]["counts"])
    )
    assert by_body["Back"] == 2

    by_type = dict(zip(m["by_type"]["labels"], m["by_type"]["counts"]))
    assert by_type["Employee Incident"] == 3
    assert by_type["Customer Incident"] == 1

    # Video Yes/No → 2 yes / 1 no = 67%
    pcts = dict(zip(m["compliance"]["labels"], m["compliance"]["percentages"]))
    assert pcts["Video available"] == 67
    # Drug screen: 1 yes / 2 no = 33%
    assert pcts["Drug screen"] == 33

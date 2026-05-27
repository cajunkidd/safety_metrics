import io

import pandas as pd
import pytest

from app.ingest import IngestError, parse_spreadsheet


def _csv(text: str) -> bytes:
    return text.encode("utf-8")


def test_parse_valid_csv():
    csv = (
        "date,department,incident_type,severity,days_lost,status\n"
        "2026-01-05,Warehouse,Injury,Recordable,2,Closed\n"
    )
    records, errors = parse_spreadsheet(_csv(csv), "data.csv")

    assert errors == []
    assert len(records) == 1
    record = records[0]
    assert record["department"] == "Warehouse"
    assert record["days_lost"] == 2.0
    assert str(record["date"]) == "2026-01-05"


def test_missing_required_column_raises():
    csv = "date,department,incident_type\n2026-01-05,Warehouse,Injury\n"
    with pytest.raises(IngestError):
        parse_spreadsheet(_csv(csv), "data.csv")


def test_invalid_rows_are_reported():
    csv = (
        "date,department,incident_type,severity\n"
        "not-a-date,Warehouse,Injury,Recordable\n"
        "2026-02-01,,Injury,Recordable\n"
        "2026-03-01,Shipping,Near Miss,First Aid\n"
    )
    records, errors = parse_spreadsheet(_csv(csv), "data.csv")

    assert len(records) == 1
    assert len(errors) == 2
    assert errors[0]["row"] == 2
    assert errors[1]["row"] == 3


def test_unsupported_file_type_raises():
    with pytest.raises(IngestError):
        parse_spreadsheet(b"anything", "data.txt")


def test_negative_days_lost_is_an_error():
    csv = (
        "date,department,incident_type,severity,days_lost\n"
        "2026-01-05,Warehouse,Injury,Recordable,-3\n"
    )
    records, errors = parse_spreadsheet(_csv(csv), "data.csv")
    assert records == []
    assert len(errors) == 1


def test_column_names_are_normalized():
    csv = (
        " Date , Department , Incident Type , Severity \n"
        "2026-01-05,Warehouse,Injury,Recordable\n"
    )
    records, errors = parse_spreadsheet(_csv(csv), "data.csv")
    assert errors == []
    assert len(records) == 1


def test_parse_excel_file():
    df = pd.DataFrame(
        {
            "date": ["2026-01-05"],
            "department": ["Assembly"],
            "incident_type": ["Spill"],
            "severity": ["First Aid"],
        }
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False)

    records, errors = parse_spreadsheet(buf.getvalue(), "data.xlsx")
    assert errors == []
    assert records[0]["incident_type"] == "Spill"

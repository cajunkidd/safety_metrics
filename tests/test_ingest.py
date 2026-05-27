import io

import pandas as pd
import pytest

from app.ingest import IngestError, parse_spreadsheet


def _df_to_xlsx(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def _df_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def _valid_form_row(**overrides):
    base = {
        "Recordable": "Yes",
        "When did this incident take place?": "2024-05-01",
        "At approximately what time?": "13:30",
        "Store Location": "12 - Lafayette",
        "What type of incident is this?": "Employee Incident",
        "Who is completing this form?": "Jane Doe",
        "What is your position with the company?": "HR",
        "Summarize the Incident:": "Slipped on wet floor.",
        "What part of the body was most severely injured?": "Knee",
        "Side of Body?": "Right",
        "What was the primary cause of the injury?": "Slip, Trip or Fall - Same Level",
        "Is there video footage of the incident available?": "Yes",
        "Was a drug screen complete by associate involved?": "No",
        "How many photos were taken and by whom?": "5 by manager",
        "How many witness statements have been received, total?": "2",
        "Did employee involved give written statement?": "Yes",
    }
    base.update(overrides)
    return base


def test_parse_valid_xlsx():
    df = pd.DataFrame([_valid_form_row()])
    records, errors = parse_spreadsheet(_df_to_xlsx(df), "form.xlsx")

    assert errors == []
    assert len(records) == 1
    r = records[0]
    assert str(r["incident_date"]) == "2024-05-01"
    assert r["store_location"] == "12 - Lafayette"
    assert r["incident_type"] == "Employee Incident"
    assert r["recordable"] is True
    assert r["body_part"] == "Knee"
    assert r["video_available"] == "Yes"


def test_parse_valid_csv():
    df = pd.DataFrame([_valid_form_row(Recordable="No")])
    records, errors = parse_spreadsheet(_df_to_csv(df), "form.csv")
    assert errors == []
    assert records[0]["recordable"] is False


def test_missing_required_column_raises():
    df = pd.DataFrame(
        [
            {
                "Recordable": "Yes",
                "When did this incident take place?": "2024-05-01",
                # Store Location and incident type missing on purpose
            }
        ]
    )
    with pytest.raises(IngestError) as exc:
        parse_spreadsheet(_df_to_xlsx(df), "form.xlsx")
    assert "Store Location" in str(exc.value)


def test_unsupported_file_type_raises():
    with pytest.raises(IngestError):
        parse_spreadsheet(b"x", "data.txt")


def test_bad_recordable_value_reported():
    df = pd.DataFrame(
        [
            _valid_form_row(Recordable="MAYBE"),
            _valid_form_row(),
        ]
    )
    records, errors = parse_spreadsheet(_df_to_xlsx(df), "form.xlsx")
    assert len(records) == 1
    assert len(errors) == 1
    assert "Recordable" in errors[0]["messages"][0]


def test_invalid_date_reported():
    df = pd.DataFrame(
        [_valid_form_row(**{"When did this incident take place?": "not-a-date"})]
    )
    records, errors = parse_spreadsheet(_df_to_xlsx(df), "form.xlsx")
    assert records == []
    assert len(errors) == 1


def test_duplicate_branch_columns_coalesce():
    # The form repeats some questions per branch; pandas appends ".1".
    row = _valid_form_row()
    # Remove first occurrence; only the ".1" suffix copy has the answer.
    row.pop("Is there video footage of the incident available?")
    df = pd.DataFrame(
        [
            {
                **row,
                "Is there video footage of the incident available?": None,
                "Is there video footage of the incident available?.1": "Yes",
            }
        ]
    )
    records, errors = parse_spreadsheet(_df_to_xlsx(df), "form.xlsx")
    assert errors == []
    assert records[0]["video_available"] == "Yes"


def test_uploaded_sample_template_parses():
    with open("sample_data/incidents_template.xlsx", "rb") as f:
        records, errors = parse_spreadsheet(f.read(), "incidents_template.xlsx")
    assert errors == []
    assert len(records) == 30
    # Spot-check a couple of fields are populated.
    assert any(r["body_part"] for r in records)
    assert any(r["recordable"] for r in records)
    assert any(not r["recordable"] for r in records)

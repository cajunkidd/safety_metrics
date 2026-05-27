import io
import re
from typing import Dict, List

import pandas as pd

# Mapping: logical_field -> list of source column header(s) from the form.
# Multiple sources are tried in order; the first non-empty value wins
# (the form repeats the same question across conditional branches, so the
# same data appears in different columns depending on the incident type).
FIELD_SOURCES: Dict[str, List[str]] = {
    "incident_date": ["When did this incident take place?"],
    "incident_time": ["At approximately what time?"],
    "store_location": ["Store Location"],
    "incident_type": ["What type of incident is this?"],
    "recordable": ["Recordable"],
    "reporter": ["Who is completing this form?"],
    "reporter_position": ["What is your position with the company?"],
    "summary": ["Summarize the Incident:"],
    "body_part": ["What part of the body was most severely injured?"],
    "body_side": ["Side of Body?"],
    "injury_cause": ["What was the primary cause of the injury?"],
    "customer_name": ["Customer Name"],
    "employee_name": [
        "Employee Name",
        "Name of primary employee involved.",
    ],
    "customer_statement": ["Did customer give written statement?"],
    "employee_statement": ["Did employee involved give written statement?"],
    "video_available": ["Is there video footage of the incident available?"],
    "drug_screen": ["Was a drug screen complete by associate involved?"],
    "photos_info": ["How many photos were taken and by whom?"],
    "witnesses_info": [
        "How many witness statements have been received, total?"
    ],
}

REQUIRED_FIELDS = [
    "incident_date",
    "store_location",
    "incident_type",
    "recordable",
]

REQUIRED_HEADERS_HUMAN = [
    FIELD_SOURCES[f][0] for f in REQUIRED_FIELDS
]


class IngestError(Exception):
    """Raised when an uploaded file cannot be processed at all."""


def _read_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    name = (filename or "").lower()
    buf = io.BytesIO(file_bytes)
    try:
        if name.endswith(".csv"):
            return pd.read_csv(buf, dtype=object)
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(buf, dtype=object)
    except IngestError:
        raise
    except Exception as exc:
        raise IngestError(f"Could not read the file: {exc}")
    raise IngestError("Unsupported file type. Please upload a .csv or .xlsx file.")


_SUFFIX_RE = re.compile(r"\.\d+$")  # pandas dedup suffix: ".1", ".2", ...


def _normalize(header) -> str:
    text = str(header).strip()
    text = _SUFFIX_RE.sub("", text)
    return text.rstrip(":").strip().lower()


def _build_column_index(df: pd.DataFrame) -> Dict[str, List]:
    """For each logical field, list the actual DataFrame columns that match
    one of its source headers (case/colon/suffix-insensitive)."""
    columns_by_norm: Dict[str, List] = {}
    for col in df.columns:
        columns_by_norm.setdefault(_normalize(col), []).append(col)

    index: Dict[str, List] = {}
    for field, sources in FIELD_SOURCES.items():
        matches: List = []
        seen = set()
        for src in sources:
            for col in columns_by_norm.get(_normalize(src), []):
                if col not in seen:
                    seen.add(col)
                    matches.append(col)
        index[field] = matches
    return index


def _first_value(row, columns):
    for col in columns:
        if col in row:
            val = row[col]
            if pd.notna(val):
                if isinstance(val, str):
                    stripped = val.strip()
                    if stripped:
                        return stripped
                else:
                    return val
    return None


def _parse_date(value):
    if value is None:
        return None
    if hasattr(value, "date") and not isinstance(value, str):
        return value.date() if hasattr(value, "year") else None
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.date()


def _parse_time(value):
    if value is None:
        return None
    if hasattr(value, "strftime") and hasattr(value, "hour"):
        try:
            return value.strftime("%H:%M")
        except Exception:
            return str(value)
    return str(value).strip() or None


def _parse_yes_no(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("yes", "y", "true", "1"):
        return True
    if text in ("no", "n", "false", "0"):
        return False
    return None


def _parse_row(row, index):
    errors = []

    raw_date = _first_value(row, index["incident_date"])
    incident_date = _parse_date(raw_date)
    if incident_date is None:
        errors.append("missing or invalid incident date")

    store_location = _first_value(row, index["store_location"])
    if not store_location:
        errors.append("missing store location")

    incident_type = _first_value(row, index["incident_type"])
    if not incident_type:
        errors.append("missing incident type")

    recordable_raw = _first_value(row, index["recordable"])
    recordable = _parse_yes_no(recordable_raw)
    if recordable is None:
        errors.append(
            "missing or unparseable 'Recordable' value "
            f"(got {recordable_raw!r}; expected Yes or No)"
        )

    if errors:
        return None, errors

    def _str(field):
        v = _first_value(row, index[field])
        return None if v is None else str(v).strip() or None

    return {
        "incident_date": incident_date,
        "incident_time": _parse_time(_first_value(row, index["incident_time"])),
        "store_location": str(store_location).strip(),
        "incident_type": str(incident_type).strip(),
        "recordable": recordable,
        "reporter": _str("reporter"),
        "reporter_position": _str("reporter_position"),
        "summary": _str("summary"),
        "body_part": _str("body_part"),
        "body_side": _str("body_side"),
        "injury_cause": _str("injury_cause"),
        "customer_name": _str("customer_name"),
        "employee_name": _str("employee_name"),
        "customer_statement": _str("customer_statement"),
        "employee_statement": _str("employee_statement"),
        "video_available": _str("video_available"),
        "drug_screen": _str("drug_screen"),
        "photos_info": _str("photos_info"),
        "witnesses_info": _str("witnesses_info"),
    }, []


def parse_spreadsheet(file_bytes: bytes, filename: str):
    """Parse a safety incident form export into incident records.

    Returns (records, row_errors). Raises IngestError when the file itself
    is unreadable or missing required columns.
    """
    df = _read_dataframe(file_bytes, filename)
    index = _build_column_index(df)

    missing = [
        FIELD_SOURCES[field][0] for field in REQUIRED_FIELDS if not index[field]
    ]
    if missing:
        raise IngestError(
            "The file is missing required column(s): "
            + ", ".join(repr(m) for m in missing)
            + "."
        )

    records = []
    row_errors = []
    for idx, row in df.iterrows():
        # Skip rows that are entirely blank.
        if row.isna().all():
            continue
        record, errors = _parse_row(row, index)
        if errors:
            row_errors.append({"row": int(idx) + 2, "messages": errors})
        else:
            records.append(record)

    return records, row_errors

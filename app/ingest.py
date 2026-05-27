import io

import pandas as pd

REQUIRED_COLUMNS = ["date", "department", "incident_type", "severity"]
OPTIONAL_COLUMNS = ["description", "days_lost", "status"]
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


class IngestError(Exception):
    """Raised when an uploaded file cannot be processed at all."""


def _read_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    name = (filename or "").lower()
    buf = io.BytesIO(file_bytes)
    try:
        if name.endswith(".csv"):
            return pd.read_csv(buf, dtype=str)
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(buf, dtype=str)
    except IngestError:
        raise
    except Exception as exc:  # malformed file content
        raise IngestError(f"Could not read the file: {exc}")
    raise IngestError("Unsupported file type. Please upload a .csv or .xlsx file.")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _cell(row, col):
    if col not in row:
        return None
    val = row[col]
    if pd.isna(val):
        return None
    text = str(val).strip()
    return text or None


def _parse_row(row):
    errors = []

    date_raw = _cell(row, "date")
    parsed_date = None
    if date_raw is None:
        errors.append("missing 'date'")
    else:
        dt = pd.to_datetime(date_raw, errors="coerce")
        if pd.isna(dt):
            errors.append(f"invalid date '{date_raw}'")
        else:
            parsed_date = dt.date()

    department = _cell(row, "department")
    if department is None:
        errors.append("missing 'department'")

    incident_type = _cell(row, "incident_type")
    if incident_type is None:
        errors.append("missing 'incident_type'")

    severity = _cell(row, "severity")
    if severity is None:
        errors.append("missing 'severity'")

    days_lost_raw = _cell(row, "days_lost")
    days_lost = 0.0
    if days_lost_raw is not None:
        try:
            days_lost = float(days_lost_raw)
            if days_lost < 0:
                errors.append(f"'days_lost' cannot be negative ({days_lost_raw})")
                days_lost = 0.0
        except ValueError:
            errors.append(f"invalid 'days_lost' value '{days_lost_raw}'")

    if errors:
        return None, errors

    return {
        "date": parsed_date,
        "department": department,
        "incident_type": incident_type,
        "severity": severity,
        "description": _cell(row, "description"),
        "days_lost": days_lost,
        "status": _cell(row, "status"),
    }, []


def parse_spreadsheet(file_bytes: bytes, filename: str):
    """Parse a CSV/Excel file into incident records.

    Returns (records, row_errors). Raises IngestError when the file itself is
    unreadable or missing required columns.
    """
    df = _normalize_columns(_read_dataframe(file_bytes, filename))

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise IngestError(
            "The file is missing required column(s): "
            + ", ".join(missing)
            + ". Expected columns: "
            + ", ".join(ALL_COLUMNS)
            + "."
        )

    records = []
    row_errors = []
    for idx, row in df.iterrows():
        record, errors = _parse_row(row)
        if errors:
            # +2: spreadsheet rows are 1-indexed and row 1 is the header.
            row_errors.append({"row": int(idx) + 2, "messages": errors})
        else:
            records.append(record)

    return records, row_errors

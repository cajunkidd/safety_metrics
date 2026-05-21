# Safety Metrics Dashboard

A web application for the safety department to upload incident data
(CSV or Excel) and visualize key safety KPIs and trends.

## Features

- Upload incident records from a CSV or Excel spreadsheet
- Automatic validation with clear, per-row error reporting
- KPI summary: total incidents, last 30 days, days since last incident,
  lost-time incidents, total lost workdays, open corrective actions
- Charts: monthly incident trend, incidents by type / severity / department
- Upload history with the ability to remove a previous upload

## Tech stack

- FastAPI + Uvicorn
- SQLAlchemy + SQLite
- pandas + openpyxl (spreadsheet parsing)
- Jinja2 templates + Chart.js

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000

## Spreadsheet format

Uploads must include these columns (column names are matched
case-insensitively, spaces are allowed):

| Column          | Required | Notes                                   |
|-----------------|----------|-----------------------------------------|
| `date`          | yes      | Incident date                           |
| `department`    | yes      | Site or department                      |
| `incident_type` | yes      | e.g. Injury, Near Miss, Property Damage |
| `severity`      | yes      | e.g. First Aid, Recordable, Lost Time   |
| `description`   | no       | Free text                               |
| `days_lost`     | no       | Lost workdays (number)                  |
| `status`        | no       | `Open` / `Closed` (corrective action)   |

Download a ready-to-use template from the **Upload Data** page, or see
`sample_data/incidents_template.csv`.

## Tests

```bash
pytest
```

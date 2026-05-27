# Safety Metrics Dashboard

A web application for the safety department to upload incident data
(CSV or Excel) and visualize key safety KPIs and trends.

## Features

- Username/password login with role-based access (admin / viewer)
- One-time in-app setup wizard for the first admin user
- Upload incident records from a CSV or Excel spreadsheet (admin only)
- Automatic validation with clear, per-row error reporting
- KPI summary: total incidents, last 30 days, days since last incident,
  lost-time incidents, total lost workdays, open corrective actions
- Charts: monthly incident trend, incidents by type / severity / department
- Upload history with the ability to remove a previous upload
- Admin-only user management screen

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
export SAFETY_METRICS_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000 — on first run you'll be redirected to
`/setup` to create the initial admin account. Subsequent users can be
added from the **Users** page once logged in as admin.

If `SAFETY_METRICS_SECRET_KEY` is not set, a random key is generated at
startup; this works but invalidates all sessions on every restart.

## Roles

- **Admin** — full access: view dashboard, upload data, delete uploads,
  manage users.
- **Viewer** — read-only: view dashboard and `/api/metrics`.

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

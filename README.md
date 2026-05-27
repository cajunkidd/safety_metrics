# Safety Metrics Dashboard

A web application for the safety department to upload incident data
(CSV or Excel) and visualize key safety KPIs and trends.

## Features

- Username/password login with role-based access (admin / viewer)
- One-time in-app setup wizard for the first admin user
- Upload incident-form exports (Excel or CSV, admin only) with
  automatic validation and per-row error reporting
- KPI summary: total incidents, recordable count, recordable rate %,
  days since last incident, days since last recordable incident
- Charts: stacked monthly trend (recordable vs non-recordable),
  by store location, customer vs employee, top body parts injured,
  top primary causes of injury, documentation compliance bars
- CSV and PDF report exports (date-stamped filenames)
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

Uploads should be exports of the safety manager's incident form
(Google Forms / Microsoft Forms style). Required columns:

| Column                                  | Notes                                |
|-----------------------------------------|--------------------------------------|
| `When did this incident take place?`    | Incident date                        |
| `Store Location`                        | e.g. `11 - Sulphur`                  |
| `What type of incident is this?`        | Customer Incident / Employee Incident |
| `Recordable`                            | `Yes` / `No`                         |

Other form fields are imported automatically when present and used
where available — body part, primary cause of injury, video/drug-screen
status, photo and witness statement counts, etc. The form repeats some
questions across conditional branches; the parser coalesces those into
one logical field per row.

A sample spreadsheet is bundled at
`sample_data/incidents_template.xlsx` and can be downloaded from the
**Upload Data** page in-app.

## Tests

```bash
pytest
```

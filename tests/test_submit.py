def _setup_admin(client):
    client.post(
        "/setup",
        data={"username": "admin", "password": "adminpass1"},
        follow_redirects=False,
    )


def _valid_submission():
    return {
        "When did this incident take place?": "2026-05-20",
        "At approximately what time?": "10:15",
        "Store Location": "11 - Sulphur",
        "What type of incident is this?": "Employee Incident",
        "Recordable": "Yes",
        "Summarize the Incident:": "Slipped on wet floor near checkout.",
        "Who is completing this form?": "Jane Doe",
        "What is your position with the company?": "Store Manager",
        "What part of the body was most severely injured?": "Knee",
        "What was the primary cause of the injury?": "Slip, Trip or Fall - Same Level",
        "What are you reporting": "Injury",
        "Is there video footage of the incident available?": "Yes",
        "Was a drug screen complete by associate involved?": "Yes",
    }


def test_submit_page_requires_login(client):
    resp = client.get("/submit", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/setup"


def test_submit_form_renders(client):
    _setup_admin(client)
    resp = client.get("/submit")
    assert resp.status_code == 200
    html = resp.text
    # Section headers
    assert "Incident Details" in html
    assert "Reporter Information" in html
    assert "Customer Information" in html
    assert "Employee Information" in html
    assert "Auto Accident Details" in html
    assert "Documentation" in html
    # A few field labels
    assert "Date of incident" in html
    assert "OSHA Recordable?" in html


def test_submit_creates_incident(client):
    _setup_admin(client)

    resp = client.post(
        "/submit", data=_valid_submission(), follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/submit?success=1"

    # The new incident should show up in the dashboard metrics.
    metrics = client.get("/api/metrics").json()
    assert metrics["total_incidents"] == 1
    assert metrics["recordable_count"] == 1
    assert metrics["recordable_rate_pct"] == 100
    assert metrics["injury_total"] == 1
    by_store = dict(
        zip(metrics["by_store"]["labels"], metrics["by_store"]["counts"])
    )
    assert by_store["11 - Sulphur"] == 1


def test_submit_missing_required_fields(client):
    _setup_admin(client)

    resp = client.post(
        "/submit",
        data={
            # All required fields blank
            "When did this incident take place?": "",
            "Store Location": "",
            "What type of incident is this?": "",
            "Recordable": "",
            "Summarize the Incident:": "",
            "Who is completing this form?": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "Please fix the highlighted fields" in resp.text


def test_submit_invalid_date(client):
    _setup_admin(client)

    data = _valid_submission()
    data["When did this incident take place?"] = "not-a-date"
    resp = client.post("/submit", data=data, follow_redirects=False)
    assert resp.status_code == 400
    assert "Use YYYY-MM-DD" in resp.text


def test_submit_stores_raw_data(client):
    _setup_admin(client)

    data = _valid_submission()
    # An optional field that isn't a typed column on Incident, but should
    # still be preserved in raw_data.
    data["Where were witness reports submitted?"] = "HR inbox"
    resp = client.post("/submit", data=data, follow_redirects=False)
    assert resp.status_code == 303

    # Fetch the CSV to confirm the typed fields landed where expected.
    csv = client.get("/export/csv").content.decode("utf-8")
    assert "11 - Sulphur" in csv
    assert "Employee Incident" in csv
    assert "Knee" in csv

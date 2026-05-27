from datetime import date

CSV_TEMPLATE_PATH = "sample_data/incidents_template.csv"


def _setup_admin_and_upload(client):
    client.post(
        "/setup",
        data={"username": "admin", "password": "adminpass1"},
        follow_redirects=False,
    )
    with open(CSV_TEMPLATE_PATH, "rb") as f:
        client.post(
            "/upload",
            files={"file": ("incidents.csv", f.read(), "text/csv")},
            follow_redirects=False,
        )


def test_csv_export_requires_login(client):
    resp = client.get("/export/csv", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/setup"


def test_csv_export_with_data(client):
    _setup_admin_and_upload(client)

    resp = client.get("/export/csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert f"safety_metrics_incidents_{date.today().isoformat()}.csv" in (
        resp.headers["content-disposition"]
    )

    body = resp.content.decode("utf-8")
    lines = body.strip().splitlines()
    assert lines[0] == (
        "date,department,incident_type,severity,description,days_lost,status"
    )
    # Template has 10 records → 1 header + 10 data lines
    assert len(lines) == 11


def test_csv_export_with_no_data(client):
    client.post(
        "/setup",
        data={"username": "admin", "password": "adminpass1"},
        follow_redirects=False,
    )

    resp = client.get("/export/csv")
    assert resp.status_code == 200
    body = resp.content.decode("utf-8").strip().splitlines()
    assert len(body) == 1  # header only


def test_pdf_export_with_data(client):
    _setup_admin_and_upload(client)

    resp = client.get("/export/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert f"safety_metrics_report_{date.today().isoformat()}.pdf" in (
        resp.headers["content-disposition"]
    )
    assert resp.content.startswith(b"%PDF-")
    assert len(resp.content) > 5000  # contains charts → nontrivial size


def test_pdf_export_with_no_data(client):
    client.post(
        "/setup",
        data={"username": "admin", "password": "adminpass1"},
        follow_redirects=False,
    )

    resp = client.get("/export/pdf")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF-")

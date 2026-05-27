def _setup_admin(client):
    client.post(
        "/setup",
        data={"username": "admin", "password": "adminpass1"},
        follow_redirects=False,
    )


def _submit_one(client, **overrides):
    data = {
        "When did this incident take place?": "2026-05-20",
        "At approximately what time?": "10:15",
        "Store Location": "11 - Sulphur",
        "What type of incident is this?": "Employee Incident",
        "Recordable": "Yes",
        "Summarize the Incident:": "Slipped on wet floor near checkout.",
        "Who is completing this form?": "Jane Doe",
        "What part of the body was most severely injured?": "Knee",
        "Where were witness reports submitted?": "HR inbox",
    }
    data.update(overrides)
    client.post("/submit", data=data, follow_redirects=False)


def test_incidents_list_requires_login(client):
    resp = client.get("/incidents", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/setup"


def test_incidents_list_empty(client):
    _setup_admin(client)
    resp = client.get("/incidents")
    assert resp.status_code == 200
    assert "No incidents recorded yet" in resp.text


def test_incidents_list_shows_rows(client):
    _setup_admin(client)
    _submit_one(client)
    _submit_one(client, **{"Store Location": "13 - Lake Charles"})

    resp = client.get("/incidents")
    assert resp.status_code == 200
    assert "11 - Sulphur" in resp.text
    assert "13 - Lake Charles" in resp.text
    assert "Slipped on wet floor" in resp.text


def test_incident_detail_renders_all_fields(client):
    _setup_admin(client)
    _submit_one(client)

    # Find the newly created incident id by following the link from the list page.
    list_html = client.get("/incidents").text
    import re

    match = re.search(r'href="/incidents/(\d+)"', list_html)
    assert match is not None
    incident_id = int(match.group(1))

    resp = client.get(f"/incidents/{incident_id}")
    assert resp.status_code == 200
    html = resp.text
    # Section headers from the form definition
    assert "Incident Details" in html
    assert "Reporter Information" in html
    assert "Injury Details" in html
    # Values rendered
    assert "11 - Sulphur" in html
    assert "Jane Doe" in html
    assert "Knee" in html
    # raw_data field that isn't a typed column
    assert "HR inbox" in html


def test_incident_detail_missing_returns_404(client):
    _setup_admin(client)
    resp = client.get("/incidents/9999")
    assert resp.status_code == 404


def test_delete_incident_admin(client):
    _setup_admin(client)
    _submit_one(client)
    metrics_before = client.get("/api/metrics").json()
    assert metrics_before["total_incidents"] == 1

    import re

    incident_id = int(
        re.search(r'href="/incidents/(\d+)"', client.get("/incidents").text).group(1)
    )

    resp = client.post(f"/incidents/{incident_id}/delete", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/incidents"

    metrics_after = client.get("/api/metrics").json()
    assert metrics_after["total_incidents"] == 0


def test_viewer_cannot_delete_incident(client):
    _setup_admin(client)
    _submit_one(client)
    # Create a viewer and switch to them
    client.post(
        "/users",
        data={"username": "viewer1", "password": "viewerpw1", "role": "viewer"},
        follow_redirects=False,
    )
    client.post("/logout", follow_redirects=False)
    client.post(
        "/login",
        data={"username": "viewer1", "password": "viewerpw1"},
        follow_redirects=False,
    )

    import re

    incident_id = int(
        re.search(r'href="/incidents/(\d+)"', client.get("/incidents").text).group(1)
    )
    resp = client.post(f"/incidents/{incident_id}/delete", follow_redirects=False)
    assert resp.status_code == 403

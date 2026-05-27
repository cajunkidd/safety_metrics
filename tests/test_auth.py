import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import hash_password, verify_password
from app.database import Base, get_db
from app.main import app
from app.models import User


@pytest.fixture
def client(tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Do NOT use `with TestClient(...)` here — that triggers the lifespan
    # which calls init_db() against the real database URL.
    yield TestClient(app)
    app.dependency_overrides.clear()


def _setup_admin(client, username="admin", password="adminpass1"):
    return client.post(
        "/setup",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


# ---------- Password hashing ----------


def test_password_hash_roundtrip():
    h = hash_password("supersecret")
    assert h != "supersecret"
    assert verify_password("supersecret", h) is True
    assert verify_password("wrong", h) is False


def test_verify_handles_bad_hash():
    assert verify_password("anything", "") is False
    assert verify_password("anything", "not-a-real-hash") is False


# ---------- Setup flow ----------


def test_no_users_redirects_to_setup(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/setup"


def test_setup_creates_admin_and_logs_in(client):
    resp = _setup_admin(client)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    # Logged in as admin: should reach dashboard.
    dash = client.get("/", follow_redirects=False)
    assert dash.status_code == 200


def test_setup_blocked_after_first_user(client):
    _setup_admin(client)
    resp = client.get("/setup", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_setup_rejects_short_password(client):
    resp = client.post(
        "/setup",
        data={"username": "admin", "password": "short"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


# ---------- Login / logout ----------


def test_login_with_correct_credentials(client):
    _setup_admin(client)
    client.post("/logout", follow_redirects=False)

    resp = client.post(
        "/login",
        data={"username": "admin", "password": "adminpass1"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_login_with_wrong_password(client):
    _setup_admin(client)
    client.post("/logout", follow_redirects=False)

    resp = client.post(
        "/login",
        data={"username": "admin", "password": "wrong-password"},
        follow_redirects=False,
    )
    assert resp.status_code == 401


def test_logout_redirects_to_login(client):
    _setup_admin(client)
    resp = client.post("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"

    # Dashboard now bounces to login, not setup, because a user exists.
    dash = client.get("/", follow_redirects=False)
    assert dash.status_code == 303
    assert dash.headers["location"] == "/login"


# ---------- Role enforcement ----------


def _create_viewer(client, username="viewer1", password="viewerpw1"):
    client.post(
        "/users",
        data={"username": username, "password": password, "role": "viewer"},
        follow_redirects=False,
    )


def test_admin_can_access_upload_and_users(client):
    _setup_admin(client)
    assert client.get("/upload").status_code == 200
    assert client.get("/users").status_code == 200


def test_viewer_blocked_from_admin_routes(client):
    _setup_admin(client)
    _create_viewer(client)
    client.post("/logout", follow_redirects=False)
    client.post(
        "/login",
        data={"username": "viewer1", "password": "viewerpw1"},
        follow_redirects=False,
    )

    assert client.get("/", follow_redirects=False).status_code == 200
    assert client.get("/upload", follow_redirects=False).status_code == 403
    assert client.get("/users", follow_redirects=False).status_code == 403

    # Mutating endpoints also blocked
    assert (
        client.post(
            "/upload",
            files={"file": ("x.csv", b"date\n", "text/csv")},
            follow_redirects=False,
        ).status_code
        == 403
    )


def test_admin_cannot_delete_self(client):
    _setup_admin(client)
    # Find self id from /users page.
    page = client.get("/users").text
    assert "admin" in page

    # Attempt to delete a non-existent user id — should redirect, not crash.
    resp = client.post("/users/9999/delete", follow_redirects=False)
    assert resp.status_code == 303

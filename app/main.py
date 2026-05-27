import os
import secrets
import warnings
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.auth import (
    AuthRedirect,
    SetupRequired,
    get_current_user,
    hash_password,
    require_admin,
    require_user,
    verify_password,
)
from app.database import get_db, init_db
from app.export import generate_csv, generate_pdf
from app.incident_form import (
    INCIDENT_FORM_SECTIONS,
    all_field_names,
    required_field_names,
)
from app.ingest import REQUIRED_HEADERS_HUMAN, IngestError, parse_spreadsheet
from app.metrics import compute_metrics
from app.models import ROLE_ADMIN, VALID_ROLES, Incident, Upload, User

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_FILE = BASE_DIR.parent / "sample_data" / "incidents_template.xlsx"

SECRET_KEY = os.environ.get("SAFETY_METRICS_SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(32)
    warnings.warn(
        "SAFETY_METRICS_SECRET_KEY is not set. Using a random key; "
        "sessions will not persist across restarts.",
        RuntimeWarning,
        stacklevel=2,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Safety Metrics Dashboard", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.exception_handler(AuthRedirect)
async def _auth_redirect_handler(request: Request, exc: AuthRedirect):
    return RedirectResponse(url="/login", status_code=303)


@app.exception_handler(SetupRequired)
async def _setup_required_handler(request: Request, exc: SetupRequired):
    return RedirectResponse(url="/setup", status_code=303)


def _render(request: Request, name: str, context: dict, status_code: int = 200):
    return templates.TemplateResponse(request, name, context, status_code=status_code)


# ---------- Setup (one-time, creates first admin) ----------


@app.get("/setup", response_class=HTMLResponse)
def setup_form(request: Request, db: Session = Depends(get_db)):
    if db.query(User).first() is not None:
        return RedirectResponse("/login", status_code=303)
    return _render(request, "setup.html", {"user": None})


@app.post("/setup", response_class=HTMLResponse)
async def setup_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if db.query(User).first() is not None:
        return RedirectResponse("/login", status_code=303)

    username = username.strip()
    if not username:
        return _render(
            request,
            "setup.html",
            {"user": None, "error": "Username is required."},
            status_code=400,
        )
    if len(password) < 8:
        return _render(
            request,
            "setup.html",
            {"user": None, "error": "Password must be at least 8 characters."},
            status_code=400,
        )

    user = User(
        username=username, password_hash=hash_password(password), role=ROLE_ADMIN
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


# ---------- Login / logout ----------


@app.get("/login", response_class=HTMLResponse)
def login_form(
    request: Request, user: Optional[User] = Depends(get_current_user)
):
    if user is not None:
        return RedirectResponse("/", status_code=303)
    return _render(request, "login.html", {"user": None})


@app.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user is not None:
        return RedirectResponse("/", status_code=303)

    db_user = db.query(User).filter(User.username == username.strip()).first()
    if db_user is None or not verify_password(password, db_user.password_hash):
        return _render(
            request,
            "login.html",
            {"user": None, "error": "Invalid username or password."},
            status_code=401,
        )

    request.session["user_id"] = db_user.id
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
def logout(request: Request, _user: User = Depends(require_user)):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ---------- Dashboard / metrics ----------


@app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    metrics = compute_metrics(db)
    return _render(
        request,
        "dashboard.html",
        {
            "user": user,
            "metrics": metrics,
            "has_data": metrics["total_incidents"] > 0,
        },
    )


@app.get("/api/metrics", response_class=JSONResponse)
def api_metrics(
    _user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    return compute_metrics(db)


# ---------- Incidents list + detail ----------


@app.get("/incidents", response_class=HTMLResponse)
def incidents_list(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    incidents = (
        db.query(Incident)
        .order_by(Incident.incident_date.desc(), Incident.id.desc())
        .all()
    )
    return _render(
        request,
        "incidents.html",
        {"user": user, "incidents": incidents},
    )


@app.get("/incidents/{incident_id}", response_class=HTMLResponse)
def incident_detail(
    incident_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    incident = db.get(Incident, incident_id)
    if incident is None:
        return _render(
            request,
            "incident_detail.html",
            {"user": user, "incident": None, "sections_with_values": [], "extra": []},
            status_code=404,
        )

    raw = incident.raw_data or {}

    # Group values using the same section structure as the submit form.
    sections_with_values = []
    used_keys = set()
    for section in INCIDENT_FORM_SECTIONS:
        rows = []
        for field in section["fields"]:
            value = raw.get(field["name"])
            if value:
                rows.append({"label": field["label"], "value": value})
                used_keys.add(field["name"])
        if rows:
            sections_with_values.append({"title": section["title"], "rows": rows})

    # Anything else stored in raw_data that isn't in the form definition
    # (e.g., extra columns from an uploaded spreadsheet).
    extra = [
        {"label": k, "value": v}
        for k, v in raw.items()
        if k not in used_keys
    ]

    return _render(
        request,
        "incident_detail.html",
        {
            "user": user,
            "incident": incident,
            "sections_with_values": sections_with_values,
            "extra": extra,
        },
    )


@app.post("/incidents/{incident_id}/delete")
def delete_incident(
    incident_id: int,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    incident = db.get(Incident, incident_id)
    if incident is not None:
        db.delete(incident)
        db.commit()
    return RedirectResponse("/incidents", status_code=303)


# ---------- Submit a single incident ----------


# Fields the submission form fills directly into the typed Incident columns.
_TYPED_FIELDS_FROM_FORM = {
    "incident_date": "When did this incident take place?",
    "incident_time": "At approximately what time?",
    "store_location": "Store Location",
    "incident_type": "What type of incident is this?",
    "reporter": "Who is completing this form?",
    "reporter_position": "What is your position with the company?",
    "summary": "Summarize the Incident:",
    "body_part": "What part of the body was most severely injured?",
    "body_side": "Side of Body?",
    "injury_cause": "What was the primary cause of the injury?",
    "customer_name": "Customer Name",
    "employee_name": "Employee Name",
    "customer_statement": "Did customer give written statement?",
    "employee_statement": "Did employee involved give written statement?",
    "video_available": "Is there video footage of the incident available?",
    "drug_screen": "Was a drug screen complete by associate involved?",
    "photos_info": "How many photos were taken and by whom?",
    "witnesses_info": "How many witness statements have been received, total?",
}


@app.get("/submit", response_class=HTMLResponse)
def submit_form(
    request: Request,
    user: User = Depends(require_user),
):
    success = request.query_params.get("success") == "1"
    return _render(
        request,
        "submit.html",
        {
            "user": user,
            "sections": INCIDENT_FORM_SECTIONS,
            "values": {},
            "errors": {},
            "success": success,
            "form_error": None,
        },
    )


@app.post("/submit", response_class=HTMLResponse)
async def submit_incident(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    form = await request.form()
    values = {name: (form.get(name, "") or "").strip() for name in all_field_names()}

    errors = {
        name: "This field is required."
        for name in required_field_names()
        if not values[name]
    }

    incident_date = None
    if values["When did this incident take place?"] and not errors.get(
        "When did this incident take place?"
    ):
        try:
            incident_date = date.fromisoformat(
                values["When did this incident take place?"]
            )
        except ValueError:
            errors["When did this incident take place?"] = "Use YYYY-MM-DD."

    recordable_raw = values["Recordable"]
    if recordable_raw and recordable_raw not in ("Yes", "No"):
        errors["Recordable"] = "Choose Yes or No."

    if errors:
        return _render(
            request,
            "submit.html",
            {
                "user": user,
                "sections": INCIDENT_FORM_SECTIONS,
                "values": values,
                "errors": errors,
                "success": False,
                "form_error": "Please fix the highlighted fields.",
            },
            status_code=400,
        )

    raw_data = {k: v for k, v in values.items() if v}

    upload = Upload(
        filename=f"Manual entry — {user.username}", row_count=1
    )
    db.add(upload)
    db.flush()

    typed = {
        attr: (values[header] or None)
        for attr, header in _TYPED_FIELDS_FROM_FORM.items()
    }
    db.add(
        Incident(
            upload_id=upload.id,
            incident_date=incident_date,
            store_location=typed["store_location"],
            incident_type=typed["incident_type"],
            recordable=(recordable_raw == "Yes"),
            reporter=typed["reporter"],
            reporter_position=typed["reporter_position"],
            summary=typed["summary"],
            incident_time=typed["incident_time"],
            body_part=typed["body_part"],
            body_side=typed["body_side"],
            injury_cause=typed["injury_cause"],
            customer_name=typed["customer_name"],
            employee_name=typed["employee_name"],
            customer_statement=typed["customer_statement"],
            employee_statement=typed["employee_statement"],
            video_available=typed["video_available"],
            drug_screen=typed["drug_screen"],
            photos_info=typed["photos_info"],
            witnesses_info=typed["witnesses_info"],
            raw_data=raw_data,
        )
    )
    db.commit()

    return RedirectResponse("/submit?success=1", status_code=303)


# ---------- Upload (admin only) ----------


@app.get("/upload", response_class=HTMLResponse)
def upload_form(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    uploads = db.query(Upload).order_by(Upload.uploaded_at.desc()).all()
    return _render(
        request,
        "upload.html",
        {"user": user, "uploads": uploads, "required_columns": REQUIRED_HEADERS_HUMAN},
    )


@app.post("/upload", response_class=HTMLResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    content = await file.read()
    context = {"user": user, "required_columns": REQUIRED_HEADERS_HUMAN}

    if not content:
        context["error"] = "The uploaded file is empty."
    else:
        try:
            records, row_errors = parse_spreadsheet(content, file.filename)
        except IngestError as exc:
            context["error"] = str(exc)
        else:
            context["row_errors"] = row_errors
            if not records:
                context["error"] = "No valid rows were found in the file."
            else:
                upload = Upload(
                    filename=file.filename or "upload", row_count=len(records)
                )
                db.add(upload)
                db.flush()
                db.add_all(
                    Incident(upload_id=upload.id, **record) for record in records
                )
                db.commit()
                context["success"] = (
                    f"Imported {len(records)} incident record(s) "
                    f"from '{file.filename}'."
                )

    context["uploads"] = (
        db.query(Upload).order_by(Upload.uploaded_at.desc()).all()
    )
    return _render(request, "upload.html", context)


@app.post("/uploads/{upload_id}/delete")
def delete_upload(
    upload_id: int,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    upload = db.get(Upload, upload_id)
    if upload:
        db.delete(upload)
        db.commit()
    return RedirectResponse(url="/upload", status_code=303)


@app.get("/template")
def download_template(_user: User = Depends(require_user)):
    return FileResponse(
        TEMPLATE_FILE,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        filename="incidents_template.xlsx",
    )


# ---------- Exports ----------


@app.get("/export/csv")
def export_csv(
    _user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    data = generate_csv(db)
    filename = f"safety_metrics_incidents_{date.today().isoformat()}.csv"
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/export/pdf")
def export_pdf(
    _user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    data = generate_pdf(db)
    filename = f"safety_metrics_report_{date.today().isoformat()}.pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- User management (admin only) ----------


@app.get("/users", response_class=HTMLResponse)
def users_page(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.username).all()
    return _render(request, "users.html", {"user": user, "users": users})


@app.post("/users", response_class=HTMLResponse)
async def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    username = username.strip()
    error = None
    if not username:
        error = "Username is required."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif role not in VALID_ROLES:
        error = "Invalid role."
    elif db.query(User).filter(User.username == username).first() is not None:
        error = f"Username '{username}' is already taken."

    if error:
        users = db.query(User).order_by(User.username).all()
        return _render(
            request,
            "users.html",
            {"user": user, "users": users, "error": error},
            status_code=400,
        )

    db.add(
        User(username=username, password_hash=hash_password(password), role=role)
    )
    db.commit()
    return RedirectResponse("/users", status_code=303)


@app.post("/users/{user_id}/delete")
def delete_user(
    user_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id != user.id:
        target = db.get(User, user_id)
        if target is not None:
            db.delete(target)
            db.commit()
    return RedirectResponse("/users", status_code=303)

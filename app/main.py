from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.ingest import ALL_COLUMNS, IngestError, parse_spreadsheet
from app.metrics import compute_metrics
from app.models import Incident, Upload

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_FILE = BASE_DIR.parent / "sample_data" / "incidents_template.csv"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Safety Metrics Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    metrics = compute_metrics(db)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "metrics": metrics,
            "has_data": metrics["total_incidents"] > 0,
        },
    )


@app.get("/api/metrics", response_class=JSONResponse)
def api_metrics(db: Session = Depends(get_db)):
    return compute_metrics(db)


@app.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request, db: Session = Depends(get_db)):
    uploads = db.query(Upload).order_by(Upload.uploaded_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "upload.html",
        {"uploads": uploads, "expected_columns": ALL_COLUMNS},
    )


@app.post("/upload", response_class=HTMLResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    context = {"expected_columns": ALL_COLUMNS}

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
    return templates.TemplateResponse(request, "upload.html", context)


@app.post("/uploads/{upload_id}/delete")
def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.get(Upload, upload_id)
    if upload:
        db.delete(upload)
        db.commit()
    return RedirectResponse(url="/upload", status_code=303)


@app.get("/template")
def download_template():
    return FileResponse(
        TEMPLATE_FILE,
        media_type="text/csv",
        filename="incidents_template.csv",
    )

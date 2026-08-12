import os
import uuid
import shutil

from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import Base, engine, get_db
import models
import schemas
from services.ocr import extract_badge_data
from services.transcribe import transcribe_audio
from services.email_service import send_folder_email
from services.whatsapp_service import notify_lead

Base.metadata.create_all(bind=engine)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="ForExperts / Epiq - Captura de Leads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def save_upload(file: UploadFile, prefix: str) -> str:
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    filename = f"{prefix}_{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return f"/uploads/{filename}"


# ---------- Funcionários ----------

@app.get("/api/employees", response_model=list[schemas.EmployeeOut])
def list_employees(db: Session = Depends(get_db)):
    return db.query(models.Employee).order_by(models.Employee.name).all()


@app.get("/api/employees/{employee_id}", response_model=schemas.EmployeeOut)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    emp = db.query(models.Employee).get(employee_id)
    if not emp:
        raise HTTPException(404, "Funcionário não encontrado")
    return emp


@app.put("/api/employees/{employee_id}", response_model=schemas.EmployeeOut)
def update_employee(employee_id: int, data: schemas.EmployeeUpdate, db: Session = Depends(get_db)):
    emp = db.query(models.Employee).get(employee_id)
    if not emp:
        raise HTTPException(404, "Funcionário não encontrado")
    if data.name:
        emp.name = data.name
    if data.phone:
        emp.phone = data.phone
    if data.email:
        emp.email = data.email
    db.commit()
    db.refresh(emp)
    return emp


@app.post("/api/employees/{employee_id}/photo", response_model=schemas.EmployeeOut)
def upload_employee_photo(employee_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    emp = db.query(models.Employee).get(employee_id)
    if not emp:
        raise HTTPException(404, "Funcionário não encontrado")
    emp.photo_url = save_upload(file, f"employee{employee_id}")
    db.commit()
    db.refresh(emp)
    return emp


# ---------- OCR do crachá ----------

@app.post("/api/ocr")
async def ocr_badge(file: UploadFile = File(...)):
    image_bytes = await file.read()
    data = extract_badge_data(image_bytes, file.content_type or "image/jpeg")
    return data


# ---------- Transcrição de voz ----------

@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    tmp_path = os.path.join(UPLOAD_DIR, f"audio_{uuid.uuid4().hex}.webm")
    with open(tmp_path, "wb") as f:
        f.write(await file.read())
    try:
        text = transcribe_audio(tmp_path)
    finally:
        os.remove(tmp_path)
    return {"text": text}


# ---------- Upload da foto do crachá (armazenar só, sem OCR) ----------

@app.post("/api/badge-photo")
async def upload_badge_photo(file: UploadFile = File(...)):
    url = save_upload(file, "badge")
    return {"url": url}


# ---------- Criação de lead ----------

def _dispatch_notifications(lead_id: int, db_url_dep):
    pass  # placeholder não usado (mantido simples com BackgroundTasks abaixo)


@app.post("/api/leads")
def create_lead(lead: schemas.LeadCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    employee = db.query(models.Employee).get(lead.employee_id)
    if not employee:
        raise HTTPException(404, "Funcionário não encontrado")

    db_lead = models.Lead(**lead.dict())
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)

    def _send():
        full_name = f"{lead.first_name} {lead.last_name}".strip()
        email_ok = True
        wpp_ok = True
        if lead.email:
            email_ok = send_folder_email(lead.email, full_name, employee.name, employee.email)
        if lead.phone:
            wpp_ok = notify_lead(lead.phone, employee.name, employee.phone, employee.email)

        local_db = next(get_db())
        db_lead_local = local_db.query(models.Lead).get(db_lead.id)
        db_lead_local.email_sent = "sent" if email_ok else "failed"
        db_lead_local.whatsapp_sent = "sent" if wpp_ok else "failed"
        local_db.commit()

    background_tasks.add_task(_send)

    return {"id": db_lead.id, "status": "created"}


@app.get("/api/leads")
def list_leads(db: Session = Depends(get_db)):
    leads = db.query(models.Lead).order_by(models.Lead.created_at.desc()).all()
    result = []
    for l in leads:
        result.append({
            "id": l.id,
            "employee": l.employee.name if l.employee else None,
            "first_name": l.first_name,
            "last_name": l.last_name,
            "company": l.company,
            "position": l.position,
            "phone": l.phone,
            "email": l.email,
            "interests": l.interests,
            "notes": l.notes,
            "classification": l.classification,
            "email_sent": l.email_sent,
            "whatsapp_sent": l.whatsapp_sent,
            "created_at": l.created_at.isoformat(),
        })
    return result


# ---------- Servir o frontend ----------
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

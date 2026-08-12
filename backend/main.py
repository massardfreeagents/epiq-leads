import os
import uuid
import shutil
import csv
import io

from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from database import Base, engine, get_db, SessionLocal
import models
import schemas
from services.ocr import extract_badge_data
from services.transcribe import transcribe_audio
from services.email_service import send_folder_email, send_report_email
from services.whatsapp_service import notify_lead
from services.report import build_leads_xlsx

Base.metadata.create_all(bind=engine)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------- Relatório diário automático (18-20/08/2026, 20h Brasília) ----------

REPORT_RECIPIENTS = ["bruno.massard@epiqglobal.com", "yuri.medeiros@epiqglobal.com"]
REPORT_SENDER = "bruno.massard@epiqglobal.com"  # precisa estar verificado como Single Sender no Brevo
EXPORT_TOKEN = os.environ.get("EXPORT_TOKEN", "")  # senha simples pro link manual de exportação


def send_daily_report():
    db = SessionLocal()
    try:
        leads = db.query(models.Lead).order_by(models.Lead.created_at.desc()).all()
        xlsx_bytes = build_leads_xlsx(leads)
        send_report_email(REPORT_RECIPIENTS, xlsx_bytes, REPORT_SENDER)
    finally:
        db.close()


scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
scheduler.add_job(
    send_daily_report,
    CronTrigger(
        hour=20, minute=0,
        start_date="2026-08-18 00:00:00",
        end_date="2026-08-20 23:59:59",
        timezone="America/Sao_Paulo",
    ),
    id="daily_leads_report",
)
scheduler.start()

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


@app.get("/api/leads/export")
def export_leads_csv(token: str = Query(...), db: Session = Depends(get_db)):
    if not EXPORT_TOKEN or token != EXPORT_TOKEN:
        raise HTTPException(403, "Acesso negado")

    leads = db.query(models.Lead).order_by(models.Lead.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")  # ; funciona melhor no Excel em pt-BR
    writer.writerow([
        "Data", "Funcionário", "Nome", "Sobrenome", "Empresa", "Cargo",
        "Telefone", "Email", "Interesses", "Observações", "Classificação",
        "Email Enviado", "WhatsApp Enviado",
    ])
    for l in leads:
        writer.writerow([
            l.created_at.strftime("%d/%m/%Y %H:%M") if l.created_at else "",
            l.employee.name if l.employee else "",
            l.first_name, l.last_name, l.company, l.position,
            l.phone, l.email,
            ", ".join(l.interests or []),
            l.notes,
            l.classification,
            l.email_sent, l.whatsapp_sent,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_epiq.csv"},
    )


@app.get("/api/leads/report-now")
def trigger_report_now(token: str = Query(...)):
    if not EXPORT_TOKEN or token != EXPORT_TOKEN:
        raise HTTPException(403, "Acesso negado")
    send_daily_report()
    return {"status": "relatório disparado, confira o e-mail em alguns instantes"}


# ---------- Servir o frontend ----------
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

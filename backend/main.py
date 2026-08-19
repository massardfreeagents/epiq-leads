import os
import uuid
import shutil

from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from database import Base, engine, get_db, SessionLocal
import models
import schemas
import hashlib
import time
from services.ocr import extract_badge_data
from services.transcribe import transcribe_audio
from services.email_service import send_folder_email, send_report_email
from services.whatsapp_service import notify_lead, notify_hot_lead
from services.report import build_leads_xlsx

YURI_PHONE = "5521993119964"  # telefone do Yuri Medeiros, para alertas de leads A/B
WHATSAPP_ENABLED = os.environ.get("WHATSAPP_ENABLED", "true").strip().lower() != "false"

# guarda impressões digitais de envios recentes pra evitar duplicidade
# (proteção extra contra duplo clique/toque, além da trava do frontend)
_RECENT_SUBMISSIONS = {}
_DEDUPE_WINDOW_SECONDS = 15


def _submission_fingerprint(lead: "schemas.LeadCreate") -> str:
    raw = f"{lead.employee_id}|{lead.first_name}|{lead.last_name}|{lead.phone}|{','.join(sorted(lead.emails))}|{lead.classification}"
    return hashlib.sha256(raw.encode()).hexdigest()

Base.metadata.create_all(bind=engine)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------- Relatório diário automático (18-20/08/2026, 20h Brasília) ----------

REPORT_RECIPIENTS = ["bruno.massard@epiqglobal.com", "yuri.medeiros@epiqglobal.com"]
REPORT_SENDER = "bruno.massard@epiqglobal.com"  # precisa estar verificado como Single Sender no Brevo
EXPORT_TOKEN = os.environ.get("EXPORT_TOKEN", "").strip()  # senha simples pro link manual de exportação


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
    # proteção contra duplo clique/toque: ignora reenvio idêntico dentro de 15s
    fingerprint = _submission_fingerprint(lead)
    now = time.time()
    last_seen = _RECENT_SUBMISSIONS.get(fingerprint)
    if last_seen and (now - last_seen) < _DEDUPE_WINDOW_SECONDS:
        raise HTTPException(409, "Envio duplicado detectado, ignorado.")
    _RECENT_SUBMISSIONS[fingerprint] = now
    # limpeza simples de entradas antigas
    for fp, ts in list(_RECENT_SUBMISSIONS.items()):
        if (now - ts) > _DEDUPE_WINDOW_SECONDS:
            del _RECENT_SUBMISSIONS[fp]

    employee = db.query(models.Employee).get(lead.employee_id)
    if not employee:
        raise HTTPException(404, "Funcionário não encontrado")

    # captura os dados ANTES de sair da sessão, pra evitar DetachedInstanceError
    employee_name = employee.name
    employee_email = employee.email
    employee_phone = employee.phone

    emails = [e.strip() for e in lead.emails if e.strip()] or [""]

    lead_ids = []
    for email in emails:
        db_lead = models.Lead(
            employee_id=lead.employee_id,
            first_name=lead.first_name,
            last_name=lead.last_name,
            company=lead.company,
            position=lead.position,
            phone=lead.phone,
            email=email,
            interests=lead.interests,
            notes=lead.notes,
            classification=lead.classification,
            badge_photo_url=lead.badge_photo_url,
        )
        db.add(db_lead)
        db.commit()
        db.refresh(db_lead)
        lead_ids.append(db_lead.id)

    full_name = f"{lead.first_name} {lead.last_name}".strip()
    lead_phone = lead.phone

    def _send():
        # ---- Canal 1: E-MAIL (independente dos outros dois) ----
        for lid, email in zip(lead_ids, emails):
            if not email:
                continue
            try:
                ok = send_folder_email(email, full_name, employee_name, employee_email, employee_phone)
            except Exception as e:
                print(f"[LEAD SEND EXCEPTION] e-mail falhou para lead {lid}: {e}")
                ok = False
            local_db = SessionLocal()
            try:
                db_lead_local = local_db.query(models.Lead).get(lid)
                db_lead_local.email_sent = "sent" if ok else "failed"
                local_db.commit()
            finally:
                local_db.close()

        # ---- Canal 2: WHATSAPP (independente do e-mail e do alerta) ----
        # Enviado UMA ÚNICA VEZ, independente de quantos e-mails foram informados
        wpp_ok = True
        if not WHATSAPP_ENABLED:
            wpp_status = "disabled"
        elif lead_phone:
            try:
                wpp_ok = notify_lead(lead_phone, employee_name, employee_phone, employee_email)
            except Exception as e:
                print(f"[LEAD SEND EXCEPTION] WhatsApp falhou: {e}")
                wpp_ok = False
            wpp_status = "sent" if wpp_ok else "failed"
        else:
            wpp_status = "sent"  # não tinha telefone, não é uma falha

        local_db = SessionLocal()
        try:
            for lid in lead_ids:
                db_lead_local = local_db.query(models.Lead).get(lid)
                db_lead_local.whatsapp_sent = wpp_status
            local_db.commit()
        finally:
            local_db.close()

        # ---- Canal 3: ALERTA PRO YURI (independente do e-mail e do WhatsApp do lead) ----
        if WHATSAPP_ENABLED and lead.classification in ("A", "B"):
            try:
                interests_text = ", ".join(lead.interests) if lead.interests else "-"
                notes_text = lead.notes if lead.notes else "-"
                summary = (
                    f"Empresa: {lead.company or '-'} | "
                    f"Interesse em: {interests_text} | "
                    f"Observação: {notes_text} | "
                    f"Lead classificado como: {lead.classification} | "
                    f"Lead levantado por: {employee_name}"
                )
                notify_hot_lead(
                    YURI_PHONE, summary, full_name,
                    lead.company, lead.position, lead_phone,
                    emails[0] if emails and emails[0] else "",
                )
            except Exception as e:
                print(f"[LEAD SEND EXCEPTION] Alerta pro Yuri falhou: {e}")

    background_tasks.add_task(_send)

    return {"ids": lead_ids, "status": "created"}


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
def export_leads_xlsx(x_export_token: str = Header(None), db: Session = Depends(get_db)):
    if not EXPORT_TOKEN or (x_export_token or "").strip() != EXPORT_TOKEN:
        raise HTTPException(403, "Acesso negado")

    leads = db.query(models.Lead).order_by(models.Lead.created_at.desc()).all()
    xlsx_bytes = build_leads_xlsx(leads)

    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=leads_epiq.xlsx"},
    )


@app.get("/api/leads/report-now")
def trigger_report_now(x_export_token: str = Header(None)):
    if not EXPORT_TOKEN or (x_export_token or "").strip() != EXPORT_TOKEN:
        raise HTTPException(403, "Acesso negado")
    send_daily_report()
    return {"status": "relatório disparado, confira o e-mail em alguns instantes"}


# ---------- Servir o frontend ----------
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

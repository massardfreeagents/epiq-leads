import os
import base64
import requests

BREVO_API_KEY = os.environ["BREVO_API_KEY"]
FOLDER_PDF_PATH = os.environ.get("FOLDER_PDF_PATH", "folder_temp.pdf")

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def send_folder_email(to_email: str, to_name: str, employee_name: str, employee_email: str) -> bool:
    """
    Envia o PDF do folder por e-mail.
    O remetente (from) é o e-mail real do funcionário — precisa estar
    verificado como 'Single Sender' na conta Brevo antes de funcionar.
    """
    with open(FOLDER_PDF_PATH, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "sender": {"name": employee_name, "email": employee_email},
        "to": [{"email": to_email, "name": to_name}],
        "replyTo": {"email": employee_email, "name": employee_name},
        "subject": f"Foi um prazer falar com você! — {employee_name} / Epiq",
        "htmlContent": f"""
            <p>Olá {to_name},</p>
            <p>Foi um prazer conversar com você em nosso estande. Segue em anexo nosso folder
            institucional com mais informações.</p>
            <p>Qualquer dúvida, pode responder diretamente este e-mail.</p>
            <p>Abraço,<br>{employee_name}<br>Epiq</p>
        """,
        "attachment": [{"content": pdf_b64, "name": "Folder-Epiq.pdf"}],
    }

    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json",
        "accept": "application/json",
    }

    resp = requests.post(BREVO_URL, json=payload, headers=headers, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"[BREVO ERROR] status={resp.status_code} body={resp.text}")
    return resp.status_code in (200, 201)


def send_report_email(to_emails: list, xlsx_bytes: bytes, sender_email: str, filename: str = "leads_epiq.xlsx") -> bool:
    """
    Envia a planilha de leads por e-mail para uma lista de destinatários.
    O remetente precisa ser um e-mail já verificado como 'Single Sender' no Brevo.
    """
    xlsx_b64 = base64.b64encode(xlsx_bytes).decode()

    payload = {
        "sender": {"name": "Captura de Leads - Epiq", "email": sender_email},
        "to": [{"email": e} for e in to_emails],
        "subject": "Relatório diário de leads — Feira Epiq",
        "htmlContent": """
            <p>Olá,</p>
            <p>Segue em anexo a planilha atualizada com todos os leads capturados até o momento
            na feira.</p>
        """,
        "attachment": [{"content": xlsx_b64, "name": filename}],
    }

    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json",
        "accept": "application/json",
    }

    resp = requests.post(BREVO_URL, json=payload, headers=headers, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"[BREVO REPORT ERROR] status={resp.status_code} body={resp.text}")
    return resp.status_code in (200, 201)

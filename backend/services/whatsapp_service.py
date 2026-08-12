import os
import base64
import requests

EVOLUTION_BASE_URL = os.environ["EVOLUTION_BASE_URL"]  # ex: https://evolution-api-xxx.up.railway.app
EVOLUTION_INSTANCE = os.environ["EVOLUTION_INSTANCE"]
EVOLUTION_API_KEY = os.environ["EVOLUTION_API_KEY"]
FOLDER_PDF_PATH = os.environ.get("FOLDER_PDF_PATH", "Epiq - Apresentacao.pdf")

HEADERS = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}


def _normalize_number(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if not digits.startswith("55"):
        digits = "55" + digits
    return digits


def send_folder_document(to_phone: str) -> bool:
    number = _normalize_number(to_phone)
    with open(FOLDER_PDF_PATH, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode()

    url = f"{EVOLUTION_BASE_URL}/message/sendMedia/{EVOLUTION_INSTANCE}"
    payload = {
        "number": number,
        "mediatype": "document",
        "mimetype": "application/pdf",
        "media": pdf_b64,
        "fileName": "Folder-Epiq.pdf",
        "caption": "Foi um prazer falar com você! Segue nosso folder institucional.",
    }
    resp = requests.post(url, json=payload, headers=HEADERS, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"[EVOLUTION sendMedia ERROR] status={resp.status_code} body={resp.text} url={url}")
    return resp.status_code in (200, 201)


def send_employee_contact(to_phone: str, employee_name: str, employee_phone: str, employee_email: str) -> bool:
    number = _normalize_number(to_phone)
    url = f"{EVOLUTION_BASE_URL}/message/sendContact/{EVOLUTION_INSTANCE}"
    payload = {
        "number": number,
        "contact": [
            {
                "fullName": f"{employee_name} - Epiq",
                "wuid": _normalize_number(employee_phone),
                "phoneNumber": employee_phone,
                "email": employee_email,
                "organization": "Epiq",
            }
        ],
    }
    resp = requests.post(url, json=payload, headers=HEADERS, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"[EVOLUTION sendContact ERROR] status={resp.status_code} body={resp.text} url={url}")
    return resp.status_code in (200, 201)


def notify_lead(to_phone: str, employee_name: str, employee_phone: str, employee_email: str) -> bool:
    ok1 = send_folder_document(to_phone)
    ok2 = send_employee_contact(to_phone, employee_name, employee_phone, employee_email)
    return ok1 and ok2

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
    """Nunca levanta exceção: qualquer erro é registrado no log e retorna False."""
    try:
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
            "caption": "Foi um prazer falar com você em nosso estande. Segue nosso folder institucional e meus contatos (telefone e email) para você gravar aí! CONTE COM A GENTE!",
        }
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        if resp.status_code not in (200, 201):
            print(f"[EVOLUTION sendMedia ERROR] status={resp.status_code} body={resp.text} url={url}")
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[EVOLUTION EXCEPTION] send_folder_document falhou: {e}")
        return False


def send_contact(to_phone: str, full_name: str, contact_phone: str, contact_email: str, organization: str = "") -> bool:
    """Nunca levanta exceção: qualquer erro é registrado no log e retorna False."""
    try:
        number = _normalize_number(to_phone)
        url = f"{EVOLUTION_BASE_URL}/message/sendContact/{EVOLUTION_INSTANCE}"
        payload = {
            "number": number,
            "contact": [
                {
                    "fullName": full_name,
                    "wuid": _normalize_number(contact_phone) if contact_phone else number,
                    "phoneNumber": contact_phone,
                    "email": contact_email,
                    "organization": organization,
                }
            ],
        }
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        if resp.status_code not in (200, 201):
            print(f"[EVOLUTION sendContact ERROR] status={resp.status_code} body={resp.text} url={url}")
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[EVOLUTION EXCEPTION] send_contact falhou: {e}")
        return False


def send_employee_contact(to_phone: str, employee_name: str, employee_phone: str, employee_email: str) -> bool:
    return send_contact(to_phone, f"{employee_name} - Epiq", employee_phone, employee_email, "Epiq")


def send_text_message(to_phone: str, text: str) -> bool:
    """Nunca levanta exceção: qualquer erro é registrado no log e retorna False."""
    try:
        number = _normalize_number(to_phone)
        url = f"{EVOLUTION_BASE_URL}/message/sendText/{EVOLUTION_INSTANCE}"
        payload = {"number": number, "text": text}
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        if resp.status_code not in (200, 201):
            print(f"[EVOLUTION sendText ERROR] status={resp.status_code} body={resp.text} url={url}")
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[EVOLUTION EXCEPTION] send_text_message falhou: {e}")
        return False


def notify_hot_lead(yuri_phone: str, summary_text: str, lead_name: str, lead_company: str,
                     lead_position: str, lead_phone: str, lead_email: str) -> bool:
    """Envia resumo em texto + cartão de contato do lead para o Yuri, quando classificado A ou B.
    Envolve o bloco com separadores de asterisco pra facilitar identificar qual contato pertence
    a qual mensagem, já que várias chegam seguidas.
    Cada etapa é independente: se uma falhar, as outras ainda são tentadas."""
    separator = "**************"
    message_with_header = f"{separator}\n{summary_text}"

    ok1 = send_text_message(yuri_phone, message_with_header)
    organization = f"{lead_company} - {lead_position}" if lead_position else lead_company
    ok2 = send_contact(yuri_phone, lead_name, lead_phone, lead_email, organization)
    ok3 = send_text_message(yuri_phone, separator)
    return ok1 and ok2 and ok3


def notify_lead(to_phone: str, employee_name: str, employee_phone: str, employee_email: str) -> bool:
    """Cada etapa é independente: se uma falhar, a outra ainda é tentada."""
    ok1 = send_folder_document(to_phone)
    ok2 = send_employee_contact(to_phone, employee_name, employee_phone, employee_email)
    return ok1 and ok2

import io
from openpyxl import Workbook
from openpyxl.styles import Font

HEADERS = [
    "Data", "Funcionário", "Nome", "Sobrenome", "Empresa", "Cargo",
    "Telefone", "Email", "Interesses", "Observações", "Classificação",
    "Email Enviado", "WhatsApp Enviado",
]


def build_leads_xlsx(leads) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for l in leads:
        ws.append([
            l.created_at.strftime("%d/%m/%Y %H:%M") if l.created_at else "",
            l.employee.name if l.employee else "",
            l.first_name, l.last_name, l.company, l.position,
            l.phone, l.email,
            ", ".join(l.interests or []),
            l.notes,
            l.classification,
            l.email_sent, l.whatsapp_sent,
        ])

    for col in ws.columns:
        max_len = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 45)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()

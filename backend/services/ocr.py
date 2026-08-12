import os
import json
import base64
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Mesmo modelo usado no expense-agent (gratuito, suporta imagem)
MODEL_NAME = "gemini-3.1-flash-lite"

PROMPT = """
Você está vendo a foto de um crachá de participante de um evento/congresso.

Extraia as informações e devolva APENAS um JSON válido, sem markdown, sem texto
adicional, no seguinte formato exato:

{
  "first_name": "",
  "last_name": "",
  "company": "",
  "position": "",
  "phone": "",
  "email": ""
}

Atenção especial ao campo "position" (cargo):
- Muitos crachás de evento têm uma "categoria de credenciamento" impressa, como
  Congressista, Palestrante, Expositor, Visitante, Imprensa, Convidado, VIP, Staff.
  ISSO NÃO É O CARGO DA PESSOA — é apenas o tipo de credencial dela no evento.
  NUNCA coloque esse tipo de palavra no campo "position".
- O campo "position" deve conter apenas o cargo profissional da pessoa na empresa
  dela (ex: "Gerente de Compliance", "Diretor Jurídico", "Analista de Auditoria").
- Se o crachá não mostrar claramente o cargo profissional da pessoa (só mostrar a
  categoria do evento), devolva "position": "" (vazio) — não tente adivinhar.

Se algum campo não estiver visível no crachá, devolva string vazia "" para ele.
Não invente informações que não estejam na imagem.
"""


def extract_badge_data(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(
        [
            {"mime_type": mime_type, "data": image_bytes},
            PROMPT,
        ]
    )
    text = response.text.strip()
    # remove eventuais blocos de código ```json ... ```
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "first_name": "", "last_name": "", "company": "",
            "position": "", "phone": "", "email": "",
        }

import os
import json
import base64
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Mesmo modelo usado no expense-agent (gratuito, suporta imagem)
MODEL_NAME = "gemini-3.1-flash-lite"

PROMPT = """
Você está vendo a foto de um crachá de visitante/participante de uma feira de negócios.
Extraia as informações visíveis e devolva APENAS um JSON válido, sem markdown, sem texto
adicional, no seguinte formato exato:

{
  "first_name": "",
  "last_name": "",
  "company": "",
  "position": "",
  "phone": "",
  "email": ""
}

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

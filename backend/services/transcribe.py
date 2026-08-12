import os
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])


def transcribe_audio(file_path: str) -> str:
    with open(file_path, "rb") as f:
        result = client.audio.transcriptions.create(
            file=(os.path.basename(file_path), f.read()),
            model="whisper-large-v3-turbo",
            language="pt",
            response_format="text",
        )
    return str(result).strip()

import os
import base64
import json
import httpx
from dotenv import load_dotenv

load_dotenv()


def transcribe_audio_bytes(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    """
    Transcribe audio bytes (Telegram voice message OGG/Opus or MP3/WAV) to text.
    1. Tries Groq Whisper Large v3 if GROQ_API_KEY is configured.
    2. Falls back to Gemini Flash multimodal if GEMINI_API_KEY is configured.
    """
    # 1. Try Groq Whisper (blazing fast ~200ms)
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            files = {"file": ("voice.ogg", audio_bytes, mime_type)}
            data = {"model": "whisper-large-v3", "response_format": "json"}
            r = httpx.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {groq_key}"},
                files=files,
                data=data,
                timeout=25,
            )
            if r.status_code == 200:
                text = r.json().get("text", "").strip()
                if text:
                    return text
            else:
                print(f"[Audio STT] Groq error ({r.status_code}): {r.text}")
        except Exception as e:
            print(f"[Audio STT] Groq exception: {e}")

    # 2. Try Gemini Flash Multimodal (using existing GEMINI_API_KEY)
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        try:
            b64_data = base64.b64encode(audio_bytes).decode("utf-8")
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": b64_data,
                                }
                            },
                            {
                                "text": (
                                    "Transcribe the spoken words in this audio verbatim. "
                                    "Do not add any preamble, explanation, or notes. "
                                    "If no speech is detected, output nothing."
                                )
                            },
                        ]
                    }
                ]
            }

            for model in ["gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-flash-latest"]:
                r = httpx.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}",
                    json=payload,
                    timeout=30,
                )
                if r.status_code == 200:
                    data = r.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            text = parts[0].get("text", "").strip()
                            if text:
                                return text
                elif r.status_code == 404:
                    continue
                else:
                    print(f"[Audio STT] Gemini model {model} returned {r.status_code}: {r.text}")
        except Exception as e:
            print(f"[Audio STT] Gemini exception: {e}")

    return ""

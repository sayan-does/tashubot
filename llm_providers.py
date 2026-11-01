import httpx, os
from dotenv import load_dotenv

load_dotenv()


class ProviderError(Exception):
    pass


def call_openrouter_free(messages, tools=None):
    """Primary Cloud: OpenRouter free models ($0/token)."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise ProviderError("OPENROUTER_API_KEY not configured")
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "openrouter/free", "messages": messages, "tools": tools},
        timeout=30,
    )
    if r.status_code != 200:
        raise ProviderError(f"OpenRouter status {r.status_code}: {r.text}")
    return r.json()["choices"][0]["message"]


def call_gemini_free(messages, tools=None):
    """Fallback Cloud: Gemini Flash Lite via Google AI Studio free tier."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ProviderError("GEMINI_API_KEY not configured")
    r = httpx.post(
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "gemini-3.5-flash-lite", "messages": messages, "tools": tools},
        timeout=30,
    )
    if r.status_code != 200:
        raise ProviderError(f"Gemini status {r.status_code}: {r.text}")
    return r.json()["choices"][0]["message"]


PROVIDERS = [
    ("openrouter_free", call_openrouter_free),
    ("gemini_free", call_gemini_free),
]


def cascade_call(messages, tools=None):
    """Try each provider in order. Return the first successful response."""
    errors = []
    for name, fn in PROVIDERS:
        try:
            return fn(messages, tools=tools), name
        except Exception as e:
            errors.append(f"{name}: {e}")
            continue
    raise RuntimeError("All providers failed:\n" + "\n".join(errors))

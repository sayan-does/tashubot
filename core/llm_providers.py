import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()


class ProviderError(Exception):
    pass


# ---------------------------------------------------------------------------
# Individual LLM Providers
# ---------------------------------------------------------------------------

def call_groq(messages, tools=None, model="openai/gpt-oss-120b"):
    """Groq ultra-fast LPU inference (500-800 tokens/sec, 14,400 free requests/day)."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise ProviderError("GROQ_API_KEY not configured")

    payload = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools

    r = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json=payload,
        timeout=25,
    )
    if r.status_code != 200:
        # Fallback to Qwen on Groq if model unavailable
        if model != "qwen/qwen3.8-27b":
            return call_groq(messages, tools=tools, model="qwen/qwen3.8-27b")
        raise ProviderError(f"Groq status {r.status_code}: {r.text}")
    return r.json()["choices"][0]["message"]


def call_github_models(messages, tools=None, model="gpt-4o-mini"):
    """GitHub Models (Azure inference with free GPT-4o-mini & DeepSeek-R1 via GitHub token)."""
    token = (
        os.environ.get("GITHUB_MODELS_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN", "")
    ).strip()
    if not token:
        raise ProviderError("GITHUB_TOKEN or GITHUB_MODELS_TOKEN not configured")

    payload = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools

    endpoints = [
        "https://models.github.ai/inference/chat/completions",
        "https://models.inference.ai.azure.com/chat/completions",
    ]
    last_err = None
    for url in endpoints:
        try:
            r = httpx.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
                timeout=30,
            )
            if r.status_code == 200:
                try:
                    data = r.json()
                    if isinstance(data, dict) and "choices" in data:
                        return data["choices"][0]["message"]
                except Exception:
                    pass
            last_err = f"GitHub Models ({url}) returned status {r.status_code}: {r.text[:100]}"
        except Exception as e:
            last_err = f"GitHub Models ({url}) error: {e}"

    raise ProviderError(last_err or "GitHub Models call failed")


def call_mistral(messages, tools=None, model="mistral-small-latest"):
    """Mistral AI free experimentation tier (expert coding & reasoning)."""
    key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not key:
        raise ProviderError("MISTRAL_API_KEY not configured")

    payload = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools

    r = httpx.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json=payload,
        timeout=30,
    )
    if r.status_code != 200:
        raise ProviderError(f"Mistral AI status {r.status_code}: {r.text}")
    return r.json()["choices"][0]["message"]


def call_gemini_free(messages, tools=None):
    """Google Gemini 3.5 Flash Lite via Google AI Studio free tier."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise ProviderError("GEMINI_API_KEY not configured")

    payload = {"model": "gemini-3.5-flash-lite", "messages": messages}
    if tools:
        payload["tools"] = tools

    r = httpx.post(
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json=payload,
        timeout=30,
    )
    if r.status_code != 200:
        raise ProviderError(f"Gemini status {r.status_code}: {r.text}")
    return r.json()["choices"][0]["message"]


def call_openrouter_free(messages, tools=None):
    """OpenRouter free models tier ($0/token universal safety net)."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ProviderError("OPENROUTER_API_KEY not configured")

    payload = {"model": "openrouter/free", "messages": messages}
    if tools:
        payload["tools"] = tools

    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json=payload,
        timeout=30,
    )
    if r.status_code != 200:
        raise ProviderError(f"OpenRouter status {r.status_code}: {r.text}")
    return r.json()["choices"][0]["message"]


# ---------------------------------------------------------------------------
# Option 2: Tiny Model-Inferred Prompt Router
# ---------------------------------------------------------------------------

ROUTER_PROMPT = (
    "You are an ultra-fast query classification router for an AI agent. "
    "Classify the following user prompt into EXACTLY ONE of these 5 categories:\n"
    "- CODE (programming, script, python, bugs, SQL, regex, syntax, HTML/CSS, github, git, repo)\n"
    "- MATH_LOGIC (complex math, step-by-step algorithms, puzzles, proof, reasoning)\n"
    "- GOOGLE_WORKSPACE (calendar, reminders, tasks, to-do list, drive files, email)\n"
    "- SEARCH_FACTS (current news, live scores, facts, weather, latest updates)\n"
    "- FAST_CHAT (casual greeting, short definition, creative writing, advice, general Q&A)\n\n"
    "Respond with ONLY the category name. Example: CODE"
)


def classify_prompt_intent(user_text: str) -> tuple[str, str]:
    """
    Invokes an ultra-lightweight, high-speed model to infer the category in ~80-120ms.
    1. Tries Groq tiny fast router (Qwen 27B @ 800 t/s).
    2. Falls back to Gemini Flash Lite.
    3. Falls back to heuristic keywords.
    Returns: (category, router_model_name)
    """
    clean_text = user_text.strip()[:400]
    router_msgs = [
        {"role": "system", "content": ROUTER_PROMPT},
        {"role": "user", "content": clean_text},
    ]

    # 1. Try Groq tiny fast router (Qwen 27B @ 800 t/s)
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            r = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}"},
                json={
                    "model": "qwen/qwen3.8-27b",
                    "messages": router_msgs,
                    "max_tokens": 15,
                    "temperature": 0.0,
                },
                timeout=4,
            )
            if r.status_code == 200:
                raw_cat = r.json()["choices"][0]["message"]["content"].strip().upper()
                for valid in ["CODE", "MATH_LOGIC", "GOOGLE_WORKSPACE", "SEARCH_FACTS", "FAST_CHAT"]:
                    if valid in raw_cat:
                        return valid, "Groq (Qwen-Router)"
        except Exception as e:
            print(f"[Router] Groq router error: {e}")

    # 2. Try Gemini Flash Lite
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        try:
            r = httpx.post(
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                headers={"Authorization": f"Bearer {gemini_key}"},
                json={
                    "model": "gemini-3.5-flash-lite",
                    "messages": router_msgs,
                    "max_tokens": 10,
                    "temperature": 0.0,
                },
                timeout=4,
            )
            if r.status_code == 200:
                raw_cat = r.json()["choices"][0]["message"]["content"].strip().upper()
                for valid in ["CODE", "MATH_LOGIC", "GOOGLE_WORKSPACE", "SEARCH_FACTS", "FAST_CHAT"]:
                    if valid in raw_cat:
                        return valid, "Gemini Flash Lite (Router)"
        except Exception as e:
            print(f"[Router] Gemini router error: {e}")

    # 3. Fast Heuristic Fallback (<0.1ms)
    lower = clean_text.lower()
    if any(k in lower for k in ["calendar", "schedule", "task", "todo", "to-do", "drive", "email", "gmail"]):
        return "GOOGLE_WORKSPACE", "Heuristic Intent Router"
    if any(k in lower for k in ["github", "repo", "git ", "def ", "class ", "function", "import ", "sql", "bug", "python", "code", "regex", "javascript"]):
        return "CODE", "Heuristic Intent Router"
    if any(k in lower for k in ["calculate", "math", "proof", "logic", "puzzle", "algorithm", "derive"]):
        return "MATH_LOGIC", "Heuristic Intent Router"
    if any(k in lower for k in ["today", "news", "score", "match", "latest", "current", "weather", "who won"]):
        return "SEARCH_FACTS", "Heuristic Intent Router"

    return "FAST_CHAT", "Heuristic Intent Router"


# ---------------------------------------------------------------------------
# Dynamic Orchestrated Cascade
# ---------------------------------------------------------------------------

def get_orchestrated_providers(intent: str) -> list:
    """Return ordered list of providers based on inferred prompt intent."""
    if intent == "CODE":
        return [
            ("Groq (GPT-OSS-120B)", call_groq),
            ("Gemini Flash Lite", call_gemini_free),
            ("OpenRouter Free", call_openrouter_free),
            ("Mistral (Codestral)", call_mistral),
            ("GitHub Models (GPT-4o-mini)", call_github_models),
        ]
    elif intent == "MATH_LOGIC":
        return [
            ("Groq (GPT-OSS-120B)", call_groq),
            ("Gemini Flash Lite", call_gemini_free),
            ("OpenRouter Free", call_openrouter_free),
            ("GitHub Models (GPT-4o-mini/DeepSeek)", call_github_models),
            ("Mistral AI", call_mistral),
        ]
    elif intent == "GOOGLE_WORKSPACE":
        return [
            ("Gemini Flash Lite (Tools Master)", call_gemini_free),
            ("Groq (GPT-OSS-120B)", call_groq),
            ("OpenRouter Free", call_openrouter_free),
            ("GitHub Models (GPT-4o-mini)", call_github_models),
            ("Mistral AI", call_mistral),
        ]
    elif intent == "SEARCH_FACTS":
        return [
            ("Groq (GPT-OSS-120B)", call_groq),
            ("Gemini Flash Lite", call_gemini_free),
            ("OpenRouter Free", call_openrouter_free),
            ("GitHub Models (GPT-4o-mini)", call_github_models),
            ("Mistral AI", call_mistral),
        ]
    else:  # FAST_CHAT or default
        return [
            ("Groq (GPT-OSS-120B)", call_groq),
            ("Gemini Flash Lite", call_gemini_free),
            ("OpenRouter Free", call_openrouter_free),
            ("GitHub Models (GPT-4o-mini)", call_github_models),
            ("Mistral AI", call_mistral),
        ]


def cascade_call(messages, tools=None):
    """
    1. Extracts user message and uses Tiny Model Router to infer intent.
    2. Dynamically orders the provider cascade according to the classification.
    3. Tries each provider, gracefully falling back on errors/rate-limits.
    Returns: (reply_message, executed_provider_name, router_info)
    """
    # Extract latest user message
    user_text = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_text = m.get("content", "")
            break

    intent, router_source = classify_prompt_intent(user_text)
    providers = get_orchestrated_providers(intent)

    router_info = {
        "intent": intent,
        "router": router_source,
    }

    errors = []
    for name, fn in providers:
        try:
            reply = fn(messages, tools=tools)
            return reply, name, router_info
        except Exception as e:
            errors.append(f"{name}: {e}")
            continue

    raise RuntimeError("All configured providers in orchestrated cascade failed:\n" + "\n".join(errors))

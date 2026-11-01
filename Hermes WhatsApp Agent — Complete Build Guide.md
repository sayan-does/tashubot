# Hermes WhatsApp Agent — Complete Build Guide

A self-hosted agent that runs on your own WhatsApp number, with web search, local-document RAG, and a multi-provider LLM cascade (Hermes → Grok → OpenRouter → Gemini).

---

## Architecture

```
WhatsApp message
   → Evolution API (Baileys bridge, Docker)
   → Webhook → Orchestrator (FastAPI, Python)
        ├─ Tool: search_docs()   → local vector store (RAG)
        ├─ Tool: web_search()    → Tavily/Brave/SearXNG
        └─ LLM cascade: Hermes (local) → Grok → OpenRouter → Gemini
   → Orchestrator calls Evolution API send endpoint
   → Reply appears in WhatsApp
```

Everything runs on your own machine except the hosted LLM/search calls. Your documents never leave your machine unless you choose a hosted embedding model.

---

## Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Node.js 20+ (only if you run Evolution API outside Docker)
- Ollama installed (for local Hermes + local embeddings): https://ollama.com
- API keys: xAI (Grok), OpenRouter, Google AI Studio (Gemini), and a search API (Tavily or Brave)
- A spare WhatsApp number (recommended — don't risk your main number; unofficial bridges can get banned)

---

## Part 1 — WhatsApp bridge (Evolution API)

Evolution API wraps Baileys (the unofficial WhatsApp Web protocol library) in a REST API + webhooks, so your orchestrator never touches the WhatsApp protocol directly.

**docker-compose.yml**

```yaml
version: "3.8"
services:
  evolution-api:
    image: evoapicloud/evolution-api:latest
    restart: always
    ports:
      - "8080:8080"
    environment:
      - AUTHENTICATION_API_KEY=change-me-to-a-long-random-string
      - DATABASE_ENABLED=false
      - WEBHOOK_GLOBAL_URL=http://host.docker.internal:8000/webhook
      - WEBHOOK_GLOBAL_ENABLED=true
      - WEBHOOK_EVENTS_MESSAGES_UPSERT=true
    volumes:
      - evolution_store:/evolution/instances
volumes:
  evolution_store:
```

```bash
docker compose up -d
```

Create an instance and get the pairing QR:

```bash
curl -X POST http://localhost:8080/instance/create \
  -H "apikey: change-me-to-a-long-random-string" \
  -H "Content-Type: application/json" \
  -d '{"instanceName": "hermes-bot", "qrcode": true}'

curl http://localhost:8080/instance/connect/hermes-bot \
  -H "apikey: change-me-to-a-long-random-string"
```

Scan the returned QR from WhatsApp → **Linked Devices** on the spare number.

Sending a message later looks like:

```bash
POST http://localhost:8080/message/sendText/hermes-bot
Headers: apikey: ...
Body: {"number": "<whatsapp_id>", "text": "..."}
```

> If you'd rather go the sanctioned route, Evolution API also supports the official Meta Cloud API as a backend — same REST interface, just needs business verification. Swap later without touching your orchestrator code.

---

## Part 2 — LLM cascade

Normalize all four providers behind one OpenAI-compatible-ish client so the cascade function stays simple.

**requirements.txt**

```
fastapi
uvicorn
httpx
chromadb
ollama
pydantic
```

**llm\_providers.py**

```python
import httpx, os

XAI_KEY = os.environ["XAI_API_KEY"]
OPENROUTER_KEY = os.environ["OPENROUTER_API_KEY"]
GEMINI_KEY = os.environ["GEMINI_API_KEY"]

class ProviderError(Exception): pass

def call_hermes_local(messages, tools=None):
    import ollama
    resp = ollama.chat(model="hermes3", messages=messages, tools=tools)
    return resp["message"]

def call_grok(messages, tools=None):
    r = httpx.post(
        "https://api.x.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {XAI_KEY}"},
        json={"model": "grok-4", "messages": messages, "tools": tools},
        timeout=30,
    )
    if r.status_code != 200:
        raise ProviderError(r.text)
    return r.json()["choices"][0]["message"]

def call_openrouter(messages, tools=None):
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
        json={"model": "nousresearch/hermes-4-70b", "messages": messages, "tools": tools},
        timeout=30,
    )
    if r.status_code != 200:
        raise ProviderError(r.text)
    return r.json()["choices"][0]["message"]

def call_gemini(messages, tools=None):
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        headers={"Authorization": f"Bearer {GEMINI_KEY}"},
        json={"model": "gemini-2.5-flash", "messages": messages, "tools": tools},
        timeout=30,
    )
    if r.status_code != 200:
        raise ProviderError(r.text)
    return r.json()["choices"][0]["message"]

PROVIDERS = [
    ("hermes_local", call_hermes_local),
    ("grok", call_grok),
    ("openrouter", call_openrouter),
    ("gemini", call_gemini),
]

def cascade_call(messages, tools=None):
    errors = []
    for name, fn in PROVIDERS:
        try:
            return fn(messages, tools=tools), name
        except Exception as e:
            errors.append(f"{name}: {e}")
            continue
    raise RuntimeError("All providers failed:\n" + "\n".join(errors))
```

Pull Hermes locally once:

```bash
ollama pull hermes3
```

(Check Ollama's library or OpenRouter's model list for the exact current Hermes tag — these naming strings do change, so verify before relying on them.)

---

## Part 3 — Web search tool

**tools\_search.py**

```python
import httpx, os
TAVILY_KEY = os.environ["TAVILY_API_KEY"]

def web_search(query: str, max_results: int = 5):
    r = httpx.post(
        "https://api.tavily.com/search",
        json={"api_key": TAVILY_KEY, "query": query, "max_results": max_results},
        timeout=15,
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    return [{"title": x["title"], "url": x["url"], "snippet": x["content"]} for x in results]
```

Swap in Brave Search API or a self-hosted SearXNG instance if you'd rather not pay per call — same function shape.

---

## Part 4 — RAG over your local documents

**rag\_index.py** (run manually or on a schedule to (re)index a folder)

```python
import chromadb, ollama, os, pathlib

DOCS_DIR = "/path/to/your/documents"
client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_or_create_collection("personal_docs")

def chunk(text, size=800, overlap=100):
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i+size])
        i += size - overlap
    return chunks

def embed(text):
    return ollama.embeddings(model="nomic-embed-text", prompt=text)["embedding"]

def index_folder():
    doc_id = 0
    for path in pathlib.Path(DOCS_DIR).rglob("*"):
        if path.suffix.lower() not in (".txt", ".md"):
            continue  # extend with pdf/docx extraction as needed
        text = path.read_text(errors="ignore")
        for c in chunk(text):
            collection.add(
                ids=[f"doc-{doc_id}"],
                embeddings=[embed(c)],
                documents=[c],
                metadatas=[{"source": str(path)}],
            )
            doc_id += 1

if __name__ == "__main__":
    index_folder()
    print("Indexed.")
```

```bash
ollama pull nomic-embed-text
python rag_index.py
```

For PDFs/DOCX, add extraction with `pypdf` or `python-docx` before chunking.

**tools\_rag.py**

```python
import chromadb, ollama
client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_or_create_collection("personal_docs")

def search_docs(query: str, n_results: int = 4):
    q_emb = ollama.embeddings(model="nomic-embed-text", prompt=query)["embedding"]
    res = collection.query(query_embeddings=[q_emb], n_results=n_results)
    return [
        {"text": doc, "source": meta["source"]}
        for doc, meta in zip(res["documents"][0], res["metadatas"][0])
    ]
```

---

## Part 5 — The agent loop (orchestrator)

**agent.py**

```python
from llm_providers import cascade_call
from tools_search import web_search
from tools_rag import search_docs
import json

TOOLS = [
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the live web for current information.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "search_docs",
        "description": "Search the user's personal documents.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}}},
]

FUNCS = {"web_search": web_search, "search_docs": search_docs}

SYSTEM_PROMPT = (
    "You are a helpful personal WhatsApp assistant. Use search_docs for "
    "questions about the user's own files/notes, and web_search for current "
    "events or anything outside your knowledge. Keep replies concise — this is WhatsApp."
)

def run_agent(user_message: str, history: list):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [
        {"role": "user", "content": user_message}
    ]

    for _ in range(4):  # max tool-call hops
        reply, provider = cascade_call(messages, tools=TOOLS)
        messages.append(reply)

        tool_calls = reply.get("tool_calls") if isinstance(reply, dict) else None
        if not tool_calls:
            return reply.get("content", "") if isinstance(reply, dict) else reply

        for call in tool_calls:
            fn_name = call["function"]["name"]
            args = json.loads(call["function"]["arguments"])
            result = FUNCS[fn_name](**args)
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result),
            })

    return "Sorry, I couldn't finish that — try rephrasing."
```

---

## Part 6 — Webhook server + sending replies

**server.py**

```python
from fastapi import FastAPI, Request
import httpx, os
from agent import run_agent

app = FastAPI()
EVOLUTION_URL = "http://localhost:8080"
EVOLUTION_KEY = os.environ["EVOLUTION_API_KEY"]
INSTANCE = "hermes-bot"

HISTORY = {}  # chat_id -> list of messages (swap for Redis/sqlite for persistence)

@app.post("/webhook")
async def webhook(req: Request):
    body = await req.json()
    try:
        msg_data = body["data"]["message"]
        chat_id = body["data"]["key"]["remoteJid"]
        text = msg_data.get("conversation") or msg_data.get("extendedTextMessage", {}).get("text")
        if not text or body["data"]["key"].get("fromMe"):
            return {"ok": True}
    except (KeyError, TypeError):
        return {"ok": True}

    history = HISTORY.get(chat_id, [])
    reply_text = run_agent(text, history)
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": reply_text})
    HISTORY[chat_id] = history[-20:]  # trim

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{EVOLUTION_URL}/message/sendText/{INSTANCE}",
            headers={"apikey": EVOLUTION_KEY},
            json={"number": chat_id, "text": reply_text},
        )
    return {"ok": True}
```

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

---

## Part 7 — Run order

1. `ollama serve` (background), `ollama pull hermes3`, `ollama pull nomic-embed-text`
2. `docker compose up -d` (Evolution API)
3. Create + pair the WhatsApp instance (Part 1)
4. `python rag_index.py` to index your docs
5. `uvicorn server:app --port 8000`
6. Export all required env vars: `XAI_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `TAVILY_API_KEY`, `EVOLUTION_API_KEY`
7. Text the bot's number from your own phone

---

## Notes & gotchas

- **Ban risk**: Baileys-based bridges violate WhatsApp's ToS. Use a spare number, keep message volume human-like, and expect occasional disconnects requiring re-pairing.
- **Provider model names drift**: `grok-4`, `gemini-2.5-flash`, and the exact Hermes tag on Ollama/OpenRouter change over time — check each provider's current model list before deploying, the names above are a snapshot.
- **Re-indexing**: re-run `rag_index.py` whenever your docs folder changes, or wrap it in a file-watcher (`watchdog` package) for live updates.
- **History persistence**: the in-memory `HISTORY` dict resets on restart — swap in SQLite or Redis for anything long-running.
- **Cost control**: Hermes-local is free; Grok/OpenRouter/Gemini are pay-per-call fallbacks only hit when the previous step errors, so normal operation should rarely leave your machine.
- **Security**: keep all API keys in environment variables / a `.env` file excluded from version control, and set a long random `AUTHENTICATION_API_KEY` on Evolution API since it's reachable on your LAN.

---
title: Tashubot Hermes Agent
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 5.20.0
app_file: app.py
pinned: false
---

# ☤ TashuBot — Autonomous Hermes Agent & Observability Cockpit

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Gradio](https://img.shields.io/badge/Gradio-5.20.0-orange.svg)](https://gradio.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A production-ready, autonomous 24/7 AI agent connected to Telegram with dynamic multi-hop tool execution, speech-to-text audio note transcription, Google Workspace MCP integration, GitHub exploration, persistent bucket storage, context-window auto-compaction, and a live Gradio observability dashboard.

---

## 🌟 Key Features

- **📱 24/7 Telegram Gateway**: Resilient background daemon polling messages on Telegram ([@dhurbaalBot](https://t.me/dhurbaalBot)).
- **🎙️ Voice Note Transcription**: Instant audio transcription via Groq Whisper Large v3 (with fallback to Gemini Flash Multimodal).
- **🧠 Prompt-Aware Intent Router & LLM Cascade**: Cascading inference across Groq (LPU), GitHub Models (GPT-4o-mini / DeepSeek-R1), Mistral, Gemini 2.5 Flash, and OpenRouter.
- **🌐 Google Workspace MCP Bridge**: Complete personal assistant toolset for Google Drive, Calendar, Gmail, and Google Tasks.
- **💻 GitHub Developer Tools**: Inspect repositories, review code files, and explore user GitHub profiles on command.
- **🔍 DuckDuckGo Live Search**: Real-time web retrieval via `ddgs` with zero API fees.
- **🎯 Dynamic Domain Skills**: Extensible Markdown prompt injection (`skills/`) for domain-specific behaviors (e.g., `concise-accurate`, `time-date-awareness`).
- **💾 Persistent Storage & Auto-Compaction**: Automatic `/data` cloud bucket detection (with local fallback), tracking session histories and auto-pruning turns when nearing limits.
- **📊 Gradio Mission Control Cockpit**: Real-time execution traces, KPI telemetry, session context inspectors, and diagnostic testing.

---

## 📁 Repository Structure

```
tashu/
├── .github/
│   └── workflows/
│       └── sync_to_hf.yml        # CI/CD action syncing repository to Hugging Face Spaces
├── core/                         # Core agent engine & orchestration logic
│   ├── __init__.py               # Core package exports
│   ├── agent.py                  # Multi-hop autonomous tool execution loop & schemas
│   ├── llm_providers.py          # Cascading LLM providers & prompt intent router
│   ├── skills_manager.py         # Dynamic skill discovery & frontmatter loader
│   └── telemetry.py              # Metrics, trace logging, and session context manager
├── tools/                        # Autonomous agent tools & integrations
│   ├── __init__.py               # Tool exports
│   ├── audio.py                  # Voice note STT (Groq Whisper / Gemini Flash)
│   ├── github.py                 # GitHub repository & code browsing
│   ├── google_mcp.py             # Google Apps OAuth & MCP integration (Drive, Cal, Gmail, Tasks)
│   ├── rag.py                    # ChromaDB document vector search
│   └── search.py                 # DuckDuckGo live web search
├── skills/                       # Domain skill definitions (prompts + metadata)
│   ├── concise-accurate/         # Concise response skill
│   │   └── SKILL.md
│   └── time-date-awareness/      # Temporal awareness skill
│       └── SKILL.md
├── scripts/                      # Setup and utility scripts
│   ├── __init__.py
│   ├── setup_google_mcp.py       # Interactive local OAuth setup for Google Apps
│   └── rag_index.py              # Document chunker & vector indexer for ChromaDB
├── documents/                    # Place personal documents here for RAG indexing
│   └── README.md
├── docs/                         # Architecture & historical guides
│   ├── ARCHITECTURE.md           # System design & execution flow
│   └── HERMES_WHATSAPP_GUIDE.md  # Reference WhatsApp build guide
├── tests/                        # Automated unit tests
│   ├── test_imports.py           # Import verification
│   ├── test_tools_schema.py      # Tool JSON schema validation
│   ├── test_skills.py            # Skill registry & parsing tests
│   └── test_telemetry.py         # KPI & trace logging tests
├── app.py                        # Gradio Cockpit UI + Telegram Daemon entry point
├── server.py                     # Standalone CLI Telegram bot runner
├── requirements.txt              # Production dependencies
├── .env.example                  # Environment variable template
└── .gitignore                    # Git exclusions
```

---

## 🚀 Quickstart & Local Setup

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/sayan-does/tashubot.git
cd tashu
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and provide your keys:

```bash
cp .env.example .env
```

Key variables to configure:
- `TELEGRAM_BOT_TOKEN`: From [@BotFather](https://t.me/BotFather)
- `GROQ_API_KEY`: From [Groq Console](https://console.groq.com/keys) (recommended for fastest responses)
- `GEMINI_API_KEY`: From [Google AI Studio](https://aistudio.google.com/apikey)
- `GITHUB_TOKEN`: From GitHub Personal Access Tokens (for GitHub Models & tools)

### 3. Google Workspace Setup (Optional)

To enable Google Calendar, Drive, Tasks, and Gmail:

```bash
python scripts/setup_google_mcp.py
```

Follow the browser prompt to grant consent and save the output tokens to your `.env` or Hugging Face Space secrets.

### 4. Run the Agent

**Option A — Gradio Cockpit & Telegram Daemon (Default):**
```bash
python app.py
```
Open [http://localhost:7860](http://localhost:7860) to view the telemetry cockpit while the Telegram bot runs in the background.

**Option B — Standalone Telegram Bot:**
```bash
python server.py
```

### 5. Run Automated Tests

```bash
python -m unittest discover tests
```

---

## ☁️ Hugging Face Space Deployment

1. Create a Hugging Face Space with the **Gradio** SDK.
2. In Space **Settings ➔ Variables and secrets**, add:
   - `TELEGRAM_BOT_TOKEN`
   - `GROQ_API_KEY`
   - `GEMINI_API_KEY`
   - `GITHUB_TOKEN`
   - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` (optional)
3. Connect your GitHub repository with GitHub Actions using the `.github/workflows/sync_to_hf.yml` workflow, or push directly to the Space remote.

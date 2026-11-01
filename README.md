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

# ☤ Tashubot (Hermes Agent 24/7)

A 24/7 cloud deployment of the Hermes Agent connected to Telegram with web search, persistent memory, and automatic context clearing.

## Features
- **📱 24/7 Telegram Gateway**: Handles messages on [@dhurbaalBot](https://t.me/dhurbaalBot).
- **🔍 Live Web Search**: DuckDuckGo live search via `ddgs`.
- **💾 Storage Bucket Support**: Automatically detects and uses `/data` persistent storage bucket for chat history and document storage.
- **🧹 Context Auto-Clear**: Automatically detects when context window is reached, clears older turns, and notifies the user.
- **🛠️ Response Transparency**: Detailed footer on every response showing which tools were used.

## Configuration Secrets
Set these in your Hugging Face Space under **Settings ➔ Variables and secrets ➔ New secret**:
- `TELEGRAM_BOT_TOKEN`
- `OPENROUTER_API_KEY`
- `GEMINI_API_KEY`

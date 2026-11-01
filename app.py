import os
import sys
import json
import asyncio
import threading
import gradio as gr
from dotenv import load_dotenv

load_dotenv()

from agent import run_agent

# Use persistent storage bucket if mounted at /data, otherwise fallback to local ./data
DATA_DIR = "/data" if os.path.exists("/data") else os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
HISTORY_FILE = os.path.join(DATA_DIR, "chat_history.json")

# In-memory history cache: chat_id -> list of {"role": str, "content": str}
CHATS = {}


def load_persistent_history():
    global CHATS
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                CHATS = json.load(f)
        except Exception as e:
            print(f"Error loading persistent history: {e}")


def save_persistent_history():
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(CHATS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving persistent history: {e}")


load_persistent_history()

# ---------------------------------------------------------------------------
# Telegram Bot Background Runner
# ---------------------------------------------------------------------------

async def telegram_main(token: str):
    from telegram import Update
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

    async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👋 **Hey! I'm Tashu (Hermes Agent)**.\n\n"
            "I'm running 24/7 on the cloud with autonomous tools:\n"
            "• 🔍 Live web search (DuckDuckGo)\n"
            "• 📚 Document search\n"
            "• 🧹 Auto-clearing memory when context window is reached\n"
            "• 🛠️ Tool transparency in every reply\n\n"
            "Just ask me anything!"
        )

    async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.message.chat_id)
        CHATS.pop(chat_id, None)
        save_persistent_history()
        await update.message.reply_text("🧹 Chat memory cleared!")

    async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return

        chat_id = str(update.message.chat_id)
        user_text = update.message.text

        await update.message.chat.send_action("typing")

        history = CHATS.setdefault(chat_id, [])
        loop = asyncio.get_event_loop()
        reply_text = await loop.run_in_executor(None, run_agent, user_text, history)

        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply_text})
        CHATS[chat_id] = history[-20:]
        save_persistent_history()

        await update.message.reply_text(reply_text)

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("🤖 Telegram Bot initialized and starting polling...")
    async with app:
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        while True:
            await asyncio.sleep(3600)


def start_telegram_thread():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("⚠️ TELEGRAM_BOT_TOKEN not found. Telegram polling is disabled.")
        return

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(telegram_main(token))
        except Exception as e:
            print(f"Telegram polling error: {e}")

    t = threading.Thread(target=run, daemon=True)
    t.start()
    print("✓ Telegram background daemon thread launched.")


start_telegram_thread()

# ---------------------------------------------------------------------------
# Gradio Web Dashboard & Interface
# ---------------------------------------------------------------------------

def web_chat_response(message, history):
    web_history = []
    for user_msg, bot_msg in history:
        web_history.append({"role": "user", "content": user_msg})
        web_history.append({"role": "assistant", "content": bot_msg})

    reply = run_agent(message, web_history)
    return reply


with gr.Blocks(title="TashuBot — Hermes Agent", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # ☤ TashuBot (Hermes Agent)
        ### 24/7 Cloud Assistant with Web Search, Document Search & Auto-Memory Management
        """
    )

    with gr.Row():
        telegram_status = "🟢 Connected" if os.environ.get("TELEGRAM_BOT_TOKEN") else "⚪ No Token"
        storage_status = "🟢 Connected (/data bucket)" if os.path.exists("/data") else "🟡 Local Storage"
        gr.Textbox(label="Telegram Bot Status", value=f"{telegram_status} (@dhurbaalBot)", interactive=False)
        gr.Textbox(label="Persistent Storage", value=storage_status, interactive=False)
        gr.Textbox(label="Inference Engines", value="OpenRouter Free + Gemini Flash Lite", interactive=False)

    with gr.Tab("💬 Web Chat"):
        gr.ChatInterface(
            fn=web_chat_response,
            examples=[
                "Who won the latest cricket match?",
                "What can you do?",
                "Explain quantum computing in simple terms",
            ],
            type="messages"
        )

    with gr.Tab("ℹ️ Connected Channels & Settings"):
        gr.Markdown(
            f"""
            ### 📱 Telegram Integration
            - **Bot Link**: [@dhurbaalBot](https://t.me/dhurbaalBot)
            - **Features Enabled**:
              - 🔍 **Web Search**: DuckDuckGo live search with error handling.
              - 🧹 **Auto-Clear Memory**: When conversation reaches context window limit, old turns are automatically cleared and user is notified.
              - 🛠️ **Tool Transparency**: Every response explicitly includes a footer showing tools used.
              - 💾 **Persistent Storage**: Bucket mounted at `{DATA_DIR}` saving state across restarts.
            """
        )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)

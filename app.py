import os
import sys
import json
import asyncio
import threading
import time
from datetime import datetime
import gradio as gr
from dotenv import load_dotenv

try:
    import spaces

    @spaces.GPU
    def dummy_gpu_fn():
        return True
except Exception:
    pass

load_dotenv()

from agent import run_agent
import telemetry
from tools_google_mcp import is_google_configured
from skills_manager import get_skills_registry
from tools_audio import transcribe_audio_bytes

# Persistent storage directory
DATA_DIR = telemetry.DATA_DIR
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
# Telegram Bot Background Daemon
# ---------------------------------------------------------------------------

async def telegram_main(token: str):
    from telegram import Update
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

    async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👋 **Hey! I'm Tashu (Hermes Agent)**.\n\n"
            "I'm running 24/7 on Hugging Face with autonomous tools:\n"
            "• 🎙️ Voice message & audio note support\n"
            "• 📅 Google Calendar & Tasks management\n"
            "• 📁 Google Drive & Gmail integration\n"
            "• 🔍 Live web search (DuckDuckGo)\n"
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
        reply_text = await loop.run_in_executor(None, run_agent, user_text, history, chat_id)

        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply_text})
        CHATS[chat_id] = history[-20:]
        save_persistent_history()

        await update.message.reply_text(reply_text)

    async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return
        voice = update.message.voice or update.message.audio
        if not voice:
            return

        chat_id = str(update.message.chat_id)
        await update.message.chat.send_action("typing")

        try:
            tg_file = await context.bot.get_file(voice.file_id)
            audio_bytes = await tg_file.download_as_bytearray()
            mime = getattr(voice, "mime_type", "audio/ogg") or "audio/ogg"

            loop = asyncio.get_event_loop()
            transcribed = await loop.run_in_executor(None, transcribe_audio_bytes, bytes(audio_bytes), mime)

            if not transcribed or not transcribed.strip():
                await update.message.reply_text("⚠️ Could not detect speech in that voice note. Please speak clearly or send text.")
                return

            await update.message.chat.send_action("typing")
            history = CHATS.setdefault(chat_id, [])
            reply_text = await loop.run_in_executor(None, run_agent, transcribed, history, chat_id)

            history.append({"role": "user", "content": f"[Voice Note]: {transcribed}"})
            history.append({"role": "assistant", "content": reply_text})
            CHATS[chat_id] = history[-20:]
            save_persistent_history()

            full_reply = f"🎤 *\"{transcribed}\"*\n\n{reply_text}"
            try:
                await update.message.reply_text(full_reply, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(full_reply)
        except Exception as e:
            print(f"[Telegram Voice] Error processing voice note: {e}")
            await update.message.reply_text(f"⚠️ Error processing voice message: {e}")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_handler))

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
# Gradio Observability & Mission Control Dashboard
# ---------------------------------------------------------------------------

def format_kpi_markdown():
    kpis = telemetry.get_kpis()
    return f"""
### 📊 Live Performance Telemetry
| Metric | Value | Status |
| :--- | :--- | :--- |
| **System Uptime** | `{kpis['uptime']}` | 🟢 Stable |
| **Total Invocations** | `{kpis['total_messages']}` requests | ⚡ Live |
| **Autonomous Tool Calls** | `{kpis['total_tool_calls']}` executions | 🛠️ Multi-hop Active |
| **Context Window Resets** | `{kpis['total_prunes']}` compactions | 🧹 Auto-Prune (Max 16) |
| **Average End-to-End Latency** | `{kpis['avg_latency']}` | ⏱️ Fast |
| **Active Telegram Users** | `{kpis['active_sessions']}` sessions | 📱 [@dhurbaalBot](https://t.me/dhurbaalBot) |
| **Errors Encountered** | `{kpis['error_count']}` errors | {'🟢 Zero Errors' if kpis['error_count'] == 0 else '⚠️ Needs Attention'} |
"""


def get_dashboard_data():
    kpi_md = format_kpi_markdown()
    traces = telemetry.get_traces_table_data()
    sessions = telemetry.get_sessions_table_data()
    trace_ids = telemetry.get_trace_ids()
    prov_md, tool_md = telemetry.get_analytics_summary()
    storage_info = telemetry.get_storage_info()

    storage_md = f"""
### 💾 Storage Bucket Architecture
- **Mount Path**: `{storage_info['mount_path']}`
- **Storage Type**: {'🟢 Hugging Face Cloud Bucket (/data)' if storage_info['is_hf_bucket'] else '🟡 Local Disk Emulation'}
- **Total Tracked Data Size**: `{storage_info['total_size_kb']} KB`
- **Files Stored**:
"""
    for f in storage_info.get("files", []):
        storage_md += f"  - `{f}`\n"

    default_trace_id = trace_ids[0] if trace_ids else None
    trace_detail = telemetry.get_trace_detail(default_trace_id) if default_trace_id else {"status": "No traces yet"}

    return (
        kpi_md,
        traces,
        sessions,
        gr.update(choices=trace_ids, value=default_trace_id),
        trace_detail,
        prov_md,
        tool_md,
        storage_md,
    )


def on_select_trace(trace_id):
    if not trace_id:
        return {"notice": "Please select a trace"}
    return telemetry.get_trace_detail(trace_id)


def on_clear_session(chat_id_to_clear):
    cid = str(chat_id_to_clear).strip()
    if not cid:
        return "⚠️ Please enter a valid Chat ID"
    if cid in CHATS:
        CHATS.pop(cid, None)
        save_persistent_history()
        return f"✅ Successfully cleared memory for Chat ID `{cid}` from persistent bucket!"
    return f"ℹ️ Chat ID `{cid}` had no active memory in store."


def run_diagnostic_prompt(prompt_text):
    if not prompt_text:
        return "Please enter a test prompt."
    t0 = time.time()
    resp = run_agent(prompt_text, [], chat_id="web_diagnostic")
    dur = round((time.time() - t0) * 1000, 1)
    return f"⏱️ Completed in {dur} ms\n\n{resp}"


with gr.Blocks(title="TashuBot Observability Cockpit", theme=gr.themes.Soft(primary_hue="blue", secondary_hue="indigo")) as demo:
    gr.Markdown(
        """
        # ☤ TashuBot Observability & Mission Control
        ### Autonomous Hermes Telegram Agent • Live Telemetry, Multi-Hop Traces & Bucket Health
        """
    )

    with gr.Row():
        telegram_status = "🟢 Connected (@dhurbaalBot)" if os.environ.get("TELEGRAM_BOT_TOKEN") else "⚪ No Token"
        storage_status = "🟢 Attached (/data bucket)" if os.path.exists("/data") else "🟡 Local Storage"
        google_status = "🟢 Connected (Drive, Cal, Gmail)" if is_google_configured() else "⚪ Needs Refresh Token"
        skills_count = len(get_skills_registry())
        skills_status = f"🟢 {skills_count} Skills Loaded" if skills_count > 0 else "⚪ No Skills"

        gr.Textbox(label="Telegram Polling Gateway", value=telegram_status, interactive=False)
        gr.Textbox(label="Persistent Bucket Storage", value=storage_status, interactive=False)
        gr.Textbox(label="Google Apps MCP Bridge", value=google_status, interactive=False)
        gr.Textbox(label="Domain Skills Active", value=skills_status, interactive=False)

    with gr.Row():
        btn_refresh = gr.Button("🔄 Refresh Live Telemetry", variant="primary", scale=1)

    kpi_box = gr.Markdown(value=format_kpi_markdown())

    with gr.Tabs():
        with gr.Tab("📜 Live Execution Traces"):
            gr.Markdown("#### Real-time Feed of Incoming Telegram Requests & Multi-Hop Tool Chains")
            traces_table = gr.Dataframe(
                headers=["Trace ID", "Time", "User ID", "Prompt Preview", "Tools Used", "LLM Provider", "Latency", "Memory Pruned", "Status"],
                value=telemetry.get_traces_table_data(),
                datatype=["str", "str", "str", "str", "str", "str", "str", "str", "str"],
                interactive=False,
                wrap=True,
            )

            gr.Markdown("---")
            gr.Markdown("#### 🔍 Trace Deep Dive Inspector")
            with gr.Row():
                trace_dropdown = gr.Dropdown(
                    label="Select Trace ID to Inspect",
                    choices=telemetry.get_trace_ids(),
                    value=telemetry.get_trace_ids()[0] if telemetry.get_trace_ids() else None,
                    interactive=True,
                    scale=2,
                )
                btn_inspect = gr.Button("Inspect Trace", scale=1)

            trace_json = gr.JSON(
                label="Trace Payload & Multi-Hop Tool Calls",
                value=telemetry.get_trace_detail(telemetry.get_trace_ids()[0]) if telemetry.get_trace_ids() else {"notice": "No traces yet"},
            )

        with gr.Tab("🧠 Memory & Sessions"):
            gr.Markdown("#### Active Telegram User Sessions & Context Window Utilization (Threshold: 16 turns)")
            sessions_table = gr.Dataframe(
                headers=["Chat ID", "Total Messages", "Context Load (Max 16)", "Compaction Count", "Last Active"],
                value=telemetry.get_sessions_table_data(),
                datatype=["str", "number", "str", "number", "str"],
                interactive=False,
            )

            with gr.Row():
                session_input = gr.Textbox(label="Target Telegram Chat ID", placeholder="e.g. 9132492382", scale=2)
                btn_clear_mem = gr.Button("🧹 Wipe Session Memory", variant="stop", scale=1)
            session_action_status = gr.Markdown()

        with gr.Tab("📊 Model & Tool Analytics"):
            with gr.Row():
                with gr.Column():
                    analytics_prov = gr.Markdown(value=telemetry.get_analytics_summary()[0])
                with gr.Column():
                    analytics_tools = gr.Markdown(value=telemetry.get_analytics_summary()[1])

        with gr.Tab("🛠️ Google MCP & Skills"):
            gr.Markdown(
                """
                ### 🎯 Specialized Domain Skills
                Skills placed under the `skills/` directory (or uploaded to `/data/skills/`) are automatically discovered and invokable via `load_skill`:
                - **`concise-accurate`**: Trims filler and corporate boilerplate; keeps responses short, dense, and factually accurate.
                - **`time-date-awareness`**: Injects live temporal awareness for news, deadlines, reminders, and scheduling.

                ---
                ### 🌐 Google Workspace MCP Bridge
                Connects TashuBot to your personal Google Apps:
                - **Google Drive**: `gdrive_search_files` & `gdrive_read_file` (searches your docs folder).
                - **Google Calendar**: `gcalendar_list_events` & `gcalendar_create_event` (schedule reminders & meetings).
                - **Google Tasks**: `gtasks_list_tasks`, `gtasks_create_task`, `gtasks_complete_task` (manage to-dos & checklists).
                - **Gmail**: `gmail_search_emails` & `gmail_send_email` (search messages & send drafts).

                **To activate Google Apps**:
                1. Run `python setup_google_mcp.py` on your computer.
                2. Grant consent in your browser once.
                3. The script will output `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN`.
                4. Add them to your Space Settings ➔ Variables and secrets!
                """
            )

        with gr.Tab("💾 Storage Bucket & System"):
            storage_box = gr.Markdown(value="Loading storage details...")
            gr.Markdown(
                """
                ---
                ### 🚀 Live Diagnostic Prompt Tester
                Execute a test prompt to benchmark latency and verify tools right now without sending a Telegram message.
                """
            )
            with gr.Row():
                diagnostic_input = gr.Textbox(label="Diagnostic Test Query", placeholder="e.g. Who won the ICC World Cup?", scale=3)
                btn_run_diag = gr.Button("Run Diagnostic", variant="secondary", scale=1)
            diagnostic_output = gr.Markdown()

    # Event Handlers
    btn_refresh.click(
        fn=get_dashboard_data,
        inputs=[],
        outputs=[kpi_box, traces_table, sessions_table, trace_dropdown, trace_json, analytics_prov, analytics_tools, storage_box],
    )

    trace_dropdown.change(
        fn=on_select_trace,
        inputs=[trace_dropdown],
        outputs=[trace_json],
    )

    btn_inspect.click(
        fn=on_select_trace,
        inputs=[trace_dropdown],
        outputs=[trace_json],
    )

    btn_clear_mem.click(
        fn=on_clear_session,
        inputs=[session_input],
        outputs=[session_action_status],
    )

    btn_run_diag.click(
        fn=run_diagnostic_prompt,
        inputs=[diagnostic_input],
        outputs=[diagnostic_output],
    )

    # Auto-refresh using Gradio 5 Timer if supported
    try:
        timer = gr.Timer(value=5)
        timer.tick(
            fn=get_dashboard_data,
            inputs=[],
            outputs=[kpi_box, traces_table, sessions_table, trace_dropdown, trace_json, analytics_prov, analytics_tools, storage_box],
        )
    except Exception:
        pass

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)

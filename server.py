import os
import sys
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from agent import run_agent

load_dotenv()

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# In-memory chat history (swap for SQLite/Redis for persistence across restarts)
HISTORY = {}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "👋 Hey! I'm your personal AI assistant.\n\n"
        "I can:\n"
        "• Answer questions using AI\n"
        "• Search the web for current info\n"
        "• Search your personal documents\n\n"
        "Just send me a message!"
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command to reset chat history."""
    chat_id = str(update.message.chat_id)
    HISTORY.pop(chat_id, None)
    await update.message.reply_text("🧹 Chat history cleared!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    if not update.message or not update.message.text:
        return

    chat_id = str(update.message.chat_id)
    text = update.message.text

    # Send "typing..." indicator while processing
    await update.message.chat.send_action("typing")

    # Run the agent (synchronous) in a thread to avoid blocking
    history = HISTORY.get(chat_id, [])
    loop = asyncio.get_event_loop()
    reply_text = await loop.run_in_executor(None, run_agent, text, history)

    # Update history
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": reply_text})
    HISTORY[chat_id] = history[-20:]  # keep last 20 messages per chat

    await update.message.reply_text(reply_text)


def main():
    if not BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN is not set.")
        print("👉 Please create a .env file with your token from @BotFather:")
        print("   TELEGRAM_BOT_TOKEN=your_token_here")
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot is running... Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

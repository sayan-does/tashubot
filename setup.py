#!/usr/bin/env python3
"""
☤ TashuBot Open-Source Interactive Setup Wizard & Environment Configurator
Run this script to configure all required and optional API keys, tokens,
and integrations with step-by-step guidance and instant live validation.

Usage:
    python setup.py
    python setup.py --check       # Verify health of current .env
    python setup.py --help        # Display usage options
"""

import os
import sys
import json
import time
import shutil
import urllib.parse
from pathlib import Path

# Enforce UTF-8 on Windows consoles to prevent unicode encoding crashes
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
DOCUMENTS_DIR = PROJECT_ROOT / "documents"

# ANSI Terminal Colors
class Colors:
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def supports_color() -> bool:
    """Check if the current terminal supports ANSI color escapes."""
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


USE_COLOR = supports_color()


def style(text: str, color_code: str) -> str:
    return f"{color_code}{text}{Colors.RESET}" if USE_COLOR else text


def banner():
    print(style("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                      ☤  TASHUBOT OPEN-SOURCE SETUP WIZARD                 ║
║       Autonomous 24/7 Hermes Agent • Multi-Provider Cascade • Tools       ║
╚═══════════════════════════════════════════════════════════════════════════╝
""", Colors.CYAN + Colors.BOLD))
    print(style("Welcome! This interactive guide will configure your TashuBot environment.", Colors.DIM))
    print(style("Press [Enter] at any prompt to keep the existing value (or leave blank to skip).\n", Colors.DIM))


def mask_key(val: str) -> str:
    """Mask a sensitive token for display: gsk_123456789 -> gsk_...6789"""
    if not val:
        return ""
    if len(val) <= 8:
        return "****"
    return f"{val[:4]}...{val[-4:]}"


def load_existing_env() -> dict:
    """Load existing .env file into a dictionary without modifying os.environ."""
    env_vars = {}
    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        # Strip inline comments and outer quotes
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        env_vars[k] = v
        except Exception as e:
            print(style(f"Notice: Could not parse existing .env file: {e}", Colors.YELLOW))
    return env_vars


def prompt_var(
    key: str,
    title: str,
    description: str,
    docs_url: str,
    current_val: str = "",
    required: bool = False,
    validator_fn=None,
) -> str:
    """Display an interactive step with guidance and validate user input."""
    print("─" * 75)
    req_badge = style("[REQUIRED]", Colors.RED + Colors.BOLD) if required else style("[OPTIONAL]", Colors.DIM)
    print(f"👉 {style(title, Colors.BOLD)} {req_badge}")
    print(f"   {style(description, Colors.RESET)}")
    if docs_url:
        print(f"   🔗 {style(docs_url, Colors.BLUE)}")

    display_current = mask_key(current_val)
    prompt_str = f"   Enter {key}"
    if current_val:
        prompt_str += f" [{style(display_current, Colors.GREEN)}]"
    prompt_str += ": "

    while True:
        try:
            user_input = input(prompt_str).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nSetup aborted by user.")
            sys.exit(0)

        # User pressed enter without typing -> keep current value
        if not user_input:
            chosen = current_val
        else:
            chosen = user_input

        if required and not chosen:
            print(style(f"   ❌ {key} is required. Please provide a valid value or press Ctrl+C to exit.", Colors.RED))
            continue

        if chosen and validator_fn:
            print(style("   Verifying credential...", Colors.DIM), end="", flush=True)
            ok, msg = validator_fn(chosen)
            if ok:
                print(f"\r   {style('✓ ' + msg, Colors.GREEN)}")
                return chosen
            else:
                print(f"\r   {style('⚠️  ' + msg, Colors.YELLOW)}")
                retry = input("   Continue with this value anyway? (y/N): ").strip().lower()
                if retry == "y":
                    return chosen
                continue

        if chosen:
            print(f"   {style('✓ Saved', Colors.GREEN)}")
        else:
            print(f"   {style('○ Skipped', Colors.DIM)}")
        return chosen


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------

def validate_telegram(token: str) -> tuple[bool, str]:
    try:
        import httpx
        r = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=8)
        if r.status_code == 200 and r.json().get("ok"):
            res = r.json()["result"]
            return True, f"Telegram Bot verified: @{res.get('username')} ({res.get('first_name')})"
        return False, f"Telegram API error: {r.text[:80]}"
    except Exception as e:
        return False, f"Connection failed: {e}"


def validate_groq(key: str) -> tuple[bool, str]:
    try:
        import httpx
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5},
            timeout=8,
        )
        if r.status_code == 200:
            return True, "Groq LPU API key valid and working!"
        return False, f"Groq status {r.status_code}: {r.text[:80]}"
    except Exception as e:
        return False, f"Connection failed: {e}"


def validate_gemini(key: str) -> tuple[bool, str]:
    try:
        import httpx
        r = httpx.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "gemini-3.5-flash-lite", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5},
            timeout=8,
        )
        if r.status_code == 200:
            return True, "Gemini API key verified successfully!"
        return False, f"Gemini status {r.status_code}: {r.text[:80]}"
    except Exception as e:
        return False, f"Connection failed: {e}"


def validate_github(token: str) -> tuple[bool, str]:
    try:
        import httpx
        r = httpx.get("https://api.github.com/user", headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, timeout=8)
        if r.status_code == 200:
            user = r.json().get("login", "Authenticated User")
            return True, f"GitHub Personal Access Token valid: @{user}"
        return False, f"GitHub status {r.status_code}: {r.text[:80]}"
    except Exception as e:
        return False, f"Connection failed: {e}"


def validate_mistral(key: str) -> tuple[bool, str]:
    try:
        import httpx
        r = httpx.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": "mistral-small-latest", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5},
            timeout=8,
        )
        if r.status_code == 200:
            return True, "Mistral API key verified successfully!"
        return False, f"Mistral status {r.status_code}: {r.text[:80]}"
    except Exception as e:
        return False, f"Connection failed: {e}"


def validate_openrouter(key: str) -> tuple[bool, str]:
    try:
        import httpx
        r = httpx.get("https://openrouter.ai/api/v1/auth/key", headers={"Authorization": f"Bearer {key}"}, timeout=8)
        if r.status_code == 200:
            return True, "OpenRouter API key verified successfully!"
        return False, f"OpenRouter status {r.status_code}: {r.text[:80]}"
    except Exception as e:
        return False, f"Connection failed: {e}"


def validate_google_oauth(client_id: str, client_secret: str, refresh_token: str) -> tuple[bool, str]:
    try:
        import httpx
        r = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        if r.status_code == 200 and "access_token" in r.json():
            return True, "Google Workspace OAuth2 refresh token verified!"
        return False, f"OAuth token exchange failed ({r.status_code}): {r.text[:80]}"
    except Exception as e:
        return False, f"Google OAuth failed: {e}"


# ---------------------------------------------------------------------------
# Interactive Google OAuth Subflow
# ---------------------------------------------------------------------------

def run_google_oauth_subflow(client_id: str, client_secret: str) -> str:
    """Launch local browser OAuth flow to acquire a Google refresh token."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import webbrowser

    SCOPES = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/tasks",
    ]

    auth_code_holder = []

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if "favicon.ico" in self.path:
                self.send_response(204)
                self.end_headers()
                return
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            if "code" in params:
                auth_code_holder.append(params["code"][0])
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h2>Authentication successful!</h2><p>You can close this tab and return to the terminal.</p>")
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    redirect_uri = "http://localhost:8088/callback"
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        + urllib.parse.urlencode({
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        })
    )

    print("\n   Opening your default web browser to authorize Google Workspace permissions...")
    print(f"   If it doesn't open automatically, visit:\n   {style(auth_url, Colors.BLUE)}")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 8088), CallbackHandler)
    print("   Waiting for browser callback on http://localhost:8088/callback...")
    while not auth_code_holder:
        server.handle_request()

    auth_code = auth_code_holder[0]
    print(style("   Exchanging authorization code for Google Refresh Token...", Colors.DIM))

    import httpx
    token_res = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=15,
    )
    if token_res.status_code == 200:
        refresh_token = token_res.json().get("refresh_token", "")
        if refresh_token:
            print(style("   ✓ Successfully generated Google Refresh Token!", Colors.GREEN))
            return refresh_token
    print(style(f"   ✗ Could not obtain refresh token: {token_res.text}", Colors.RED))
    return ""


# ---------------------------------------------------------------------------
# Setup Execution Flow
# ---------------------------------------------------------------------------

def run_wizard():
    banner()
    env = load_existing_env()

    # 1. Telegram Bot Gateway
    print(style("\n📱 STEP 1: TELEGRAM BOT GATEWAY", Colors.BOLD + Colors.CYAN))
    telegram_token = prompt_var(
        key="TELEGRAM_BOT_TOKEN",
        title="Telegram Bot Token",
        description="The bot token that allows TashuBot to receive and reply to messages on Telegram.",
        docs_url="https://t.me/BotFather (Send /newbot to create one)",
        current_val=env.get("TELEGRAM_BOT_TOKEN", ""),
        required=True,
        validator_fn=validate_telegram,
    )

    # 2. LLM Inference Providers
    print(style("\n🧠 STEP 2: LLM INFERENCE PROVIDERS & ROUTING", Colors.BOLD + Colors.CYAN))
    print(style("TashuBot uses a multi-provider cascade with prompt-aware routing.", Colors.DIM))
    print(style("Configure at least one provider (Groq or Gemini recommended):", Colors.DIM))

    groq_key = prompt_var(
        key="GROQ_API_KEY",
        title="Groq LPU API Key (Recommended - Fastest)",
        description="Powers ultra-fast inference (500-800 tok/sec, 14,400 free requests/day) via GPT-OSS-120B / Qwen.",
        docs_url="https://console.groq.com/keys (Free sign up, no credit card)",
        current_val=env.get("GROQ_API_KEY", ""),
        required=False,
        validator_fn=validate_groq,
    )

    gemini_key = prompt_var(
        key="GEMINI_API_KEY",
        title="Google AI Studio Gemini API Key (Recommended)",
        description="Powers Gemini 2.5 Flash reasoning and handles voice note speech-to-text audio processing.",
        docs_url="https://aistudio.google.com/apikey (Free Google AI Studio key)",
        current_val=env.get("GEMINI_API_KEY", ""),
        required=False,
        validator_fn=validate_gemini,
    )

    github_token = prompt_var(
        key="GITHUB_TOKEN",
        title="GitHub Personal Access Token (Optional)",
        description="Enables GitHub Models (GPT-4o-mini inference) AND GitHub repository/code inspection tools.",
        docs_url="https://github.com/settings/tokens (Create PAT with repo/models scope)",
        current_val=env.get("GITHUB_TOKEN", "") or env.get("GITHUB_MODELS_TOKEN", ""),
        required=False,
        validator_fn=validate_github,
    )

    mistral_key = prompt_var(
        key="MISTRAL_API_KEY",
        title="Mistral AI API Key (Optional)",
        description="Powers creative and synthesis tasks via Mistral-Small in the cascade.",
        docs_url="https://console.mistral.ai/api-keys",
        current_val=env.get("MISTRAL_API_KEY", ""),
        required=False,
        validator_fn=validate_mistral,
    )

    openrouter_key = prompt_var(
        key="OPENROUTER_API_KEY",
        title="OpenRouter API Key (Optional)",
        description="Provides access to free-tier open models across Hermes, Llama, and Qwen.",
        docs_url="https://openrouter.ai/settings/keys",
        current_val=env.get("OPENROUTER_API_KEY", ""),
        required=False,
        validator_fn=validate_openrouter,
    )

    if not any([groq_key, gemini_key, github_token, mistral_key, openrouter_key]):
        print(style("\n⚠️ Warning: No LLM provider configured! The bot needs at least one provider to respond.", Colors.RED))

    # 3. Google Workspace MCP Bridge
    print(style("\n🌐 STEP 3: GOOGLE WORKSPACE MCP (DRIVE, CALENDAR, GMAIL, TASKS)", Colors.BOLD + Colors.CYAN))
    print(style("Connect TashuBot to Google Calendar, Google Tasks, Drive docs, and Gmail.", Colors.DIM))

    g_client_id = env.get("GOOGLE_CLIENT_ID", "")
    g_client_secret = env.get("GOOGLE_CLIENT_SECRET", "")
    g_refresh_token = env.get("GOOGLE_REFRESH_TOKEN", "")
    g_folder_id = env.get("GDRIVE_FOLDER_ID", "")

    configure_google = input("Would you like to configure Google Workspace tools? (y/N): ").strip().lower() == "y"
    if configure_google:
        print("\n   Google Cloud Setup Steps:")
        print("   1. Open https://console.cloud.google.com and create a project.")
        print("   2. Enable APIs: Google Drive API, Google Calendar API, Gmail API, Tasks API.")
        print("   3. Go to APIs & Services ➔ Credentials ➔ Create OAuth Client ID (Desktop app).")
        print("   4. Enter your Client ID and Client Secret below:")

        g_client_id = prompt_var(
            key="GOOGLE_CLIENT_ID",
            title="Google OAuth Client ID",
            description="Client ID from Google Cloud Console Credentials.",
            docs_url="https://console.cloud.google.com/apis/credentials",
            current_val=g_client_id,
            required=False,
        )

        g_client_secret = prompt_var(
            key="GOOGLE_CLIENT_SECRET",
            title="Google OAuth Client Secret",
            description="Client Secret from Google Cloud Console Credentials.",
            docs_url="",
            current_val=g_client_secret,
            required=False,
        )

        if g_client_id and g_client_secret:
            if not g_refresh_token:
                run_oauth = input("\n   Run local browser authorization now to generate refresh token? (Y/n): ").strip().lower() != "n"
                if run_oauth:
                    g_refresh_token = run_google_oauth_subflow(g_client_id, g_client_secret)

            if not g_refresh_token:
                g_refresh_token = prompt_var(
                    key="GOOGLE_REFRESH_TOKEN",
                    title="Google OAuth Refresh Token",
                    description="Paste your Google OAuth2 refresh token manually if already generated.",
                    docs_url="",
                    current_val=g_refresh_token,
                    required=False,
                )

            if g_refresh_token:
                ok, msg = validate_google_oauth(g_client_id, g_client_secret, g_refresh_token)
                if ok:
                    print(f"   {style('✓ ' + msg, Colors.GREEN)}")
                else:
                    print(f"   {style('⚠️ ' + msg, Colors.YELLOW)}")

        g_folder_id = prompt_var(
            key="GDRIVE_FOLDER_ID",
            title="Google Drive Target Folder ID (Optional)",
            description="Specific Drive folder ID to search (leave blank to search entire Drive).",
            docs_url="",
            current_val=g_folder_id,
            required=False,
        )

    # 4. Hugging Face Spaces Deployment
    print(style("\n☁️ STEP 4: HUGGING FACE SPACES CI/CD (OPTIONAL)", Colors.BOLD + Colors.CYAN))
    print(style("Allows GitHub Actions to automatically deploy your bot to Hugging Face Spaces 24/7.", Colors.DIM))

    hf_token = prompt_var(
        key="HF_TOKEN",
        title="Hugging Face Write Token",
        description="Personal access token with 'Write' permissions for deploying spaces.",
        docs_url="https://huggingface.co/settings/tokens",
        current_val=env.get("HF_TOKEN", ""),
        required=False,
    )

    hf_username = prompt_var(
        key="HF_USERNAME",
        title="Hugging Face Username",
        description="Your Hugging Face profile username.",
        docs_url="",
        current_val=env.get("HF_USERNAME", ""),
        required=False,
    )

    hf_space_name = prompt_var(
        key="HF_SPACE_NAME",
        title="Hugging Face Space Name",
        description="Target Space repository name (e.g. TashuBot).",
        docs_url="",
        current_val=env.get("HF_SPACE_NAME", "TashuBot"),
        required=False,
    )

    # -----------------------------------------------------------------------
    # Write .env File
    # -----------------------------------------------------------------------
    print(style("\n💾 SAVING CONFIGURATION", Colors.BOLD + Colors.CYAN))

    if ENV_FILE.exists():
        backup_path = PROJECT_ROOT / f".env.bak"
        try:
            shutil.copy2(ENV_FILE, backup_path)
            print(f"   {style('✓ Backed up existing .env to .env.bak', Colors.DIM)}")
        except Exception:
            pass

    content = f"""# =============================================================================
# TashuBot Environment Configuration
# Generated by `python setup.py` on {time.strftime("%Y-%m-%d %H:%M:%S")}
# =============================================================================

# 1. Telegram Bot Gateway
TELEGRAM_BOT_TOKEN={telegram_token}

# 2. LLM Inference Providers & Cascading Routers
GROQ_API_KEY={groq_key}
GEMINI_API_KEY={gemini_key}
GITHUB_TOKEN={github_token}
GITHUB_MODELS_TOKEN={github_token}
MISTRAL_API_KEY={mistral_key}
OPENROUTER_API_KEY={openrouter_key}

# 3. Google Workspace MCP Integration
GOOGLE_CLIENT_ID={g_client_id}
GOOGLE_CLIENT_SECRET={g_client_secret}
GOOGLE_REFRESH_TOKEN={g_refresh_token}
GDRIVE_FOLDER_ID={g_folder_id}

# 4. Hugging Face Spaces Cloud Deployment
HF_TOKEN={hf_token}
HF_USERNAME={hf_username}
HF_SPACE_NAME={hf_space_name}
"""
    try:
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print(style(f"   ✓ Successfully written configuration to {ENV_FILE.name}!", Colors.GREEN + Colors.BOLD))
    except Exception as e:
        print(style(f"   ❌ Error writing .env file: {e}", Colors.RED))
        return

    # -----------------------------------------------------------------------
    # Post-Setup Verification & Next Steps
    # -----------------------------------------------------------------------
    print("─" * 75)
    print(style("🎉 SETUP COMPLETE!", Colors.GREEN + Colors.BOLD))
    print("\nNext recommended steps:")
    print(f"  1. Run automated test suite:       {style('python setup.py --test', Colors.CYAN)}")
    print(f"  2. Check health of all components: {style('python setup.py --check', Colors.CYAN)}")
    print(f"  3. Launch Gradio Cockpit + Bot:    {style('python app.py', Colors.CYAN)}")
    print(f"  4. Launch CLI Telegram Bot:        {style('python server.py', Colors.CYAN)}")

    action = input("\nWould you like to run automated tests now? (Y/n): ").strip().lower()
    if action != "n":
        run_tests()


def run_tests():
    """Execute unit test suite."""
    print(style("\n🧪 Running automated test suite...", Colors.BOLD))
    import unittest
    loader = unittest.TestLoader()
    suite = loader.discover(str(PROJECT_ROOT / "tests"))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print(style("✓ All tests passed!", Colors.GREEN + Colors.BOLD))
    else:
        print(style("⚠️ Some tests had errors or failures.", Colors.YELLOW))


def run_health_check():
    """Verify health of all configured services in .env."""
    banner()
    env = load_existing_env()
    print(style("🔍 DIAGNOSTIC SUBSYSTEM HEALTH CHECK", Colors.BOLD + Colors.CYAN))
    print("─" * 75)

    # Telegram
    tg = env.get("TELEGRAM_BOT_TOKEN")
    if tg:
        ok, msg = validate_telegram(tg)
        print(f"  📱 Telegram Gateway : {style('✓ ' + msg, Colors.GREEN) if ok else style('✗ ' + msg, Colors.RED)}")
    else:
        print(f"  📱 Telegram Gateway : {style('○ Not configured', Colors.DIM)}")

    # Groq
    groq = env.get("GROQ_API_KEY")
    if groq:
        ok, msg = validate_groq(groq)
        print(f"  ⚡ Groq LPU API     : {style('✓ ' + msg, Colors.GREEN) if ok else style('✗ ' + msg, Colors.RED)}")
    else:
        print(f"  ⚡ Groq LPU API     : {style('○ Not configured', Colors.DIM)}")

    # Gemini
    gemini = env.get("GEMINI_API_KEY")
    if gemini:
        ok, msg = validate_gemini(gemini)
        print(f"  🧠 Gemini 2.5 Flash : {style('✓ ' + msg, Colors.GREEN) if ok else style('✗ ' + msg, Colors.RED)}")
    else:
        print(f"  🧠 Gemini 2.5 Flash : {style('○ Not configured', Colors.DIM)}")

    # GitHub
    gh = env.get("GITHUB_TOKEN") or env.get("GITHUB_MODELS_TOKEN")
    if gh:
        ok, msg = validate_github(gh)
        print(f"  💻 GitHub Tools/LLM : {style('✓ ' + msg, Colors.GREEN) if ok else style('✗ ' + msg, Colors.RED)}")
    else:
        print(f"  💻 GitHub Tools/LLM : {style('○ Not configured', Colors.DIM)}")

    # Google Workspace
    cid = env.get("GOOGLE_CLIENT_ID")
    csec = env.get("GOOGLE_CLIENT_SECRET")
    rt = env.get("GOOGLE_REFRESH_TOKEN")
    if cid and csec and rt:
        ok, msg = validate_google_oauth(cid, csec, rt)
        print(f"  🌐 Google Apps MCP  : {style('✓ ' + msg, Colors.GREEN) if ok else style('✗ ' + msg, Colors.RED)}")
    else:
        print(f"  🌐 Google Apps MCP  : {style('○ Not fully configured', Colors.DIM)}")

    # DuckDuckGo Search
    try:
        from tools.search import web_search
        res = web_search("Python 3.13", max_results=1)
        if res and "title" in res[0]:
            print(f"  🔍 DuckDuckGo Search: {style('✓ Live web search working', Colors.GREEN)}")
        else:
            print(f"  🔍 DuckDuckGo Search: {style('⚠️ Web search returned empty or format error', Colors.YELLOW)}")
    except Exception as e:
        print(f"  🔍 DuckDuckGo Search: {style('✗ Failed: ' + str(e), Colors.RED)}")

    # ChromaDB
    try:
        from tools.rag import search_docs
        res = search_docs("test query", n_results=1)
        print(f"  📚 ChromaDB RAG     : {style('✓ Vector client initialized', Colors.GREEN)}")
    except Exception as e:
        print(f"  📚 ChromaDB RAG     : {style('✗ Failed: ' + str(e), Colors.RED)}")

    # Skills Registry
    try:
        from core.skills_manager import get_skills_registry
        reg = get_skills_registry()
        print(f"  🎯 Domain Skills    : {style(f'✓ {len(reg)} skills active ({list(reg.keys())})', Colors.GREEN)}")
    except Exception as e:
        print(f"  🎯 Domain Skills    : {style('✗ Failed: ' + str(e), Colors.RED)}")

    print("─" * 75)
    print(style("Diagnostics complete. Run `python setup.py` to reconfigure any settings.", Colors.DIM))


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower().strip()
        if arg in ("--check", "-c", "check", "health"):
            run_health_check()
            return
        elif arg in ("--test", "-t", "test"):
            run_tests()
            return
        elif arg in ("--help", "-h", "help"):
            print("""
TashuBot Setup Wizard & CLI Assistant

Commands:
  python setup.py              Start interactive setup wizard
  python setup.py --check      Run diagnostic health check on all services
  python setup.py --test       Run automated unit test suite
  python setup.py --help       Show this help message
""")
            return
        # Support standard build triggers without failing
        elif arg in ("egg_info", "dist_info", "install", "develop"):
            print("Notice: TashuBot uses requirements.txt for dependencies.")
            return

    run_wizard()


if __name__ == "__main__":
    main()

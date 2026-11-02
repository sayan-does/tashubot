"""
Google Apps MCP Setup Helper for TashuBot
Run this script locally on Windows to generate your Google OAuth Refresh Token:
    uv run python setup_google_mcp.py

Steps:
1. Go to Google Cloud Console (https://console.cloud.google.com).
2. Create a project and enable:
   - Google Drive API
   - Google Calendar API
   - Gmail API
3. Go to APIs & Services ➔ Credentials ➔ Create Credentials ➔ OAuth Client ID:
   - Application type: "Desktop app" (or "Web application" with redirect URI http://localhost:8088/callback)
4. Download the JSON or copy the Client ID and Client Secret.
5. Run this script! It will open your browser once to grant permission and print the secrets.
"""

import os
import sys
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser
import httpx
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/tasks",
]

AUTH_CODE = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global AUTH_CODE
        if "favicon.ico" in self.path:
            self.send_response(204)
            self.end_headers()
            return

        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        if "code" in params:
            AUTH_CODE = params["code"][0]
            body = (
                b"<html><head><title>Auth Success</title></head>"
                b"<body style='font-family:sans-serif;text-align:center;padding:50px;background:#111;color:#eee;'>"
                b"<h1 style='color:#4ade80;'>&#10004; Authentication Successful!</h1>"
                b"<p style='font-size:18px;'>Google Tasks & Workspace permissions have been granted.</p>"
                b"<p style='color:#888;'>You can now close this tab and return to your terminal.</p>"
                b"</body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        else:
            body = b"Failed to capture authorization code. Please return to the terminal."
            self.send_response(400)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Quiet HTTP server logs


def main():
    print("=" * 65)
    print("   ☤ TashuBot Google Apps MCP Setup (Drive, Calendar, Gmail, Tasks)")
    print("=" * 65)

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    # Check for downloaded credentials.json in current directory
    for f in os.listdir("."):
        if f.startswith("client_secret") and f.endswith(".json") or f == "credentials.json":
            try:
                with open(f, "r") as fp:
                    data = json.load(fp)
                    c_info = data.get("installed") or data.get("web")
                    if c_info:
                        client_id = c_info.get("client_id")
                        client_secret = c_info.get("client_secret")
                        print(f"✓ Found credentials file: {f}")
                        break
            except Exception:
                pass

    if not client_id:
        client_id = input("\nEnter your Google OAuth Client ID: ").strip()
    if not client_secret:
        client_secret = input("Enter your Google OAuth Client Secret: ").strip()

    if not (client_id and client_secret):
        print("❌ Client ID and Client Secret are required.")
        return

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

    print("\nOpening your browser to authenticate with Google...")
    print("If it doesn't open automatically, visit this URL:")
    print(auth_url)
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 8088), OAuthCallbackHandler)
    print("\nWaiting for authorization in browser...")
    while not AUTH_CODE:
        server.handle_request()

    print("\nExchanging authorization code for refresh token...")
    token_res = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": AUTH_CODE,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
    )

    if token_res.status_code != 200:
        print(f"❌ Error obtaining refresh token: {token_res.text}")
        return

    token_data = token_res.json()
    refresh_token = token_data.get("refresh_token")

    if not refresh_token:
        print("⚠️ No refresh token returned. Did you include prompt=consent?")
        print(token_data)
        return

    # Automatically save GOOGLE_REFRESH_TOKEN to local .env
    try:
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as fp:
                env_content = fp.read()
            import re
            if "GOOGLE_REFRESH_TOKEN=" in env_content:
                env_content = re.sub(r"GOOGLE_REFRESH_TOKEN=.*", f"GOOGLE_REFRESH_TOKEN={refresh_token}", env_content)
            else:
                env_content += f"\nGOOGLE_REFRESH_TOKEN={refresh_token}\n"
            with open(env_path, "w", encoding="utf-8") as fp:
                fp.write(env_content)
            print("✓ Updated GOOGLE_REFRESH_TOKEN in local .env!")
    except Exception as e:
        print(f"Could not auto-write to .env: {e}")

    print("\n" + "=" * 65)
    print("🎉 SUCCESS! Add these secrets to your Hugging Face Space:")
    print("=" * 65)
    print(f"GOOGLE_CLIENT_ID: {client_id}")
    print(f"GOOGLE_CLIENT_SECRET: {client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN: {refresh_token}")
    print("GDRIVE_FOLDER_ID: (Optional: open your folder in drive.google.com, copy ID from URL)")
    print("=" * 65)

    # Optional auto-upload to Hugging Face
    hf_token = os.environ.get("HF_TOKEN", "")
    if not hf_token:
        hf_token = input("\nEnter your Hugging Face Write Token to auto-upload secrets (press Enter to skip): ").strip()
    if hf_token:
        ans = input("\nWould you like to auto-upload these secrets to Hugging Face Space 'Sayan0978/TashuBot'? (y/N): ").strip().lower()
        if ans == "y":
            try:
                from huggingface_hub import HfApi
                api = HfApi(token=hf_token)
                api.add_space_secret("Sayan0978/TashuBot", "GOOGLE_CLIENT_ID", client_id)
                api.add_space_secret("Sayan0978/TashuBot", "GOOGLE_CLIENT_SECRET", client_secret)
                api.add_space_secret("Sayan0978/TashuBot", "GOOGLE_REFRESH_TOKEN", refresh_token)
                print("✓ Successfully saved Google credentials to Hugging Face Space secrets!")
                api.restart_space("Sayan0978/TashuBot")
                print("✓ Hugging Face Space restarted with Google Apps MCP active!")
            except Exception as e:
                print(f"Could not auto-upload to Space: {e}")


if __name__ == "__main__":
    main()

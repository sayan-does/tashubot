import os
import json
import base64
import time
from datetime import datetime, timezone
import httpx

# ---------------------------------------------------------------------------
# Google Workspace OAuth & Token Management
# ---------------------------------------------------------------------------

_TOKEN_CACHE = {
    "access_token": None,
    "expires_at": 0,
}


def _get_access_token():
    """Retrieve or refresh Google OAuth2 access token using refresh_token."""
    global _TOKEN_CACHE

    now = time.time()
    if _TOKEN_CACHE["access_token"] and _TOKEN_CACHE["expires_at"] > now + 60:
        return _TOKEN_CACHE["access_token"]

    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()

    if not (client_id and client_secret and refresh_token):
        # Check if service account JSON is provided instead
        sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        if sa_json:
            return _get_service_account_token(sa_json)
        return None

    try:
        r = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            _TOKEN_CACHE["access_token"] = data["access_token"]
            _TOKEN_CACHE["expires_at"] = now + data.get("expires_in", 3600)
            return _TOKEN_CACHE["access_token"]
        else:
            print(f"[Google MCP] Token refresh failed ({r.status_code}): {r.text}")
            return None
    except Exception as e:
        print(f"[Google MCP] Token refresh exception: {e}")
        return None


def _get_service_account_token(sa_json_str: str):
    """Fallback: Obtain access token using Google Cloud service account JSON."""
    # Useful when user shares a single Google Drive folder with a service account email
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request

        sa_info = json.loads(sa_json_str)
        scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/gmail.modify",
        ]
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=scopes)
        creds.refresh(Request())
        return creds.token
    except Exception as e:
        print(f"[Google MCP] Service account auth error: {e}")
        return None


def is_google_configured() -> bool:
    """Check if credentials are configured in environment variables."""
    return bool(
        (os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_REFRESH_TOKEN"))
        or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    )


# ---------------------------------------------------------------------------
# 1. Google Drive MCP Tools
# ---------------------------------------------------------------------------

def gdrive_search_files(query: str, folder_id: str = None) -> list:
    """
    Search for files and documents in Google Drive.
    If folder_id or GDRIVE_FOLDER_ID is set, limits search to that specific folder.
    """
    token = _get_access_token()
    if not token:
        return [{"error": "Google Drive MCP is not configured. Add GOOGLE_REFRESH_TOKEN to Space Secrets."}]

    target_folder = folder_id or os.environ.get("GDRIVE_FOLDER_ID", "").strip()

    q_parts = ["trashed = false"]
    if target_folder:
        q_parts.append(f"'{target_folder}' in parents")
    if query:
        # Search file name or full text content
        escaped = query.replace("'", "\\'")
        q_parts.append(f"(name contains '{escaped}' or fullText contains '{escaped}')")

    q = " and ".join(q_parts)

    try:
        r = httpx.get(
            "https://www.googleapis.com/drive/v3/files",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "q": q,
                "fields": "files(id, name, mimeType, modifiedTime, size)",
                "pageSize": 10,
            },
            timeout=15,
        )
        if r.status_code == 200:
            files = r.json().get("files", [])
            if not files:
                return [{"message": f"No files found matching '{query}' in Google Drive."}]
            return files
        return [{"error": f"Drive API returned {r.status_code}: {r.text}"}]
    except Exception as e:
        return [{"error": f"Drive search error: {e}"}]


def gdrive_read_file(file_name_or_id: str) -> dict:
    """
    Read the text content of a Google Drive file or Google Doc.
    Accepts either the exact file ID or searches by file name.
    """
    token = _get_access_token()
    if not token:
        return {"error": "Google Drive MCP is not configured."}

    file_id = file_name_or_id.strip()

    # If it's a name rather than an ID, search for it first
    if " " in file_id or "." in file_id:
        found = gdrive_search_files(file_id)
        if found and isinstance(found, list) and "id" in found[0]:
            file_id = found[0]["id"]
        else:
            return {"error": f"Could not locate file named '{file_name_or_id}' in Google Drive."}

    try:
        # First inspect metadata to determine MIME type
        meta_res = httpx.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"fields": "id, name, mimeType"},
            timeout=15,
        )
        if meta_res.status_code != 200:
            return {"error": f"File lookup failed: {meta_res.text}"}

        meta = meta_res.json()
        mime = meta.get("mimeType", "")
        name = meta.get("name", "Document")

        # Google Docs need to be exported as plain text
        if "google-apps.document" in mime:
            export_url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
            content_res = httpx.get(
                export_url,
                headers={"Authorization": f"Bearer {token}"},
                params={"mimeType": "text/plain"},
                timeout=20,
            )
            content = content_res.text[:4000]
        else:
            # Direct binary or text file download
            down_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
            content_res = httpx.get(
                down_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=20,
            )
            content = content_res.text[:4000]

        return {
            "file_name": name,
            "mime_type": mime,
            "content": content,
            "truncated": len(content_res.text) > 4000,
        }
    except Exception as e:
        return {"error": f"Error reading Drive file: {e}"}


# ---------------------------------------------------------------------------
# 2. Google Calendar MCP Tools
# ---------------------------------------------------------------------------

def gcalendar_list_events(max_results: int = 5, query: str = None) -> list:
    """List upcoming Google Calendar events and reminders starting from today."""
    token = _get_access_token()
    if not token:
        return [{"error": "Google Calendar MCP is not configured. Add GOOGLE_REFRESH_TOKEN to Space Secrets."}]

    now_iso = datetime.now(timezone.utc).isoformat()
    params = {
        "calendarId": "primary",
        "timeMin": now_iso,
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": max_results,
    }
    if query:
        params["q"] = query

    try:
        r = httpx.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=15,
        )
        if r.status_code == 200:
            items = r.json().get("items", [])
            if not items:
                return [{"message": "No upcoming calendar events or reminders found."}]
            return [
                {
                    "summary": item.get("summary", "Untitled"),
                    "start": item.get("start", {}).get("dateTime") or item.get("start", {}).get("date"),
                    "end": item.get("end", {}).get("dateTime") or item.get("end", {}).get("date"),
                    "description": item.get("description", ""),
                }
                for item in items
            ]
        return [{"error": f"Calendar API returned {r.status_code}: {r.text}"}]
    except Exception as e:
        return [{"error": f"Calendar lookup error: {e}"}]


def gcalendar_create_event(summary: str, start_time: str, end_time: str = None, description: str = None) -> dict:
    """
    Create a new event or reminder in Google Calendar.
    start_time: ISO string (e.g. '2026-11-03T10:00:00+05:30' or '2026-11-03')
    """
    token = _get_access_token()
    if not token:
        return {"error": "Google Calendar MCP is not configured."}

    # If end_time not provided, default to 1 hour after start
    if not end_time:
        try:
            # Check if dateTime or date
            if "T" in start_time:
                st_clean = start_time.replace("Z", "+00:00")
                dt = datetime.fromisoformat(st_clean)
                end_time = dt.replace(hour=(dt.hour + 1) % 24).isoformat()
            else:
                end_time = start_time
        except Exception:
            end_time = start_time

    body = {
        "summary": summary,
        "description": description or f"Created via TashuBot Hermes Agent at {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    }

    if "T" in start_time:
        body["start"] = {"dateTime": start_time}
        body["end"] = {"dateTime": end_time}
    else:
        body["start"] = {"date": start_time}
        body["end"] = {"date": end_time}

    try:
        r = httpx.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
            timeout=15,
        )
        if r.status_code in (200, 201):
            created = r.json()
            return {
                "status": "success",
                "message": f"Event '{summary}' scheduled successfully!",
                "htmlLink": created.get("htmlLink"),
                "start": body["start"],
                "end": body["end"],
            }
        return {"error": f"Calendar create error ({r.status_code}): {r.text}"}
    except Exception as e:
        return {"error": f"Failed to create calendar event: {e}"}


# ---------------------------------------------------------------------------
# 3. Gmail MCP Tools
# ---------------------------------------------------------------------------

def gmail_search_emails(query: str, max_results: int = 5) -> list:
    """Search emails in Gmail (e.g. 'from:sayan', 'is:unread', 'subject:meeting')."""
    token = _get_access_token()
    if not token:
        return [{"error": "Gmail MCP is not configured. Add GOOGLE_REFRESH_TOKEN to Space Secrets."}]

    try:
        r = httpx.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": query, "maxResults": max_results},
            timeout=15,
        )
        if r.status_code != 200:
            return [{"error": f"Gmail search error ({r.status_code}): {r.text}"}]

        msgs = r.json().get("messages", [])
        if not msgs:
            return [{"message": f"No emails found matching query '{query}'."}]

        results = []
        for m in msgs[:max_results]:
            detail_res = httpx.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{m['id']}",
                headers={"Authorization": f"Bearer {token}"},
                params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                timeout=15,
            )
            if detail_res.status_code == 200:
                p = detail_res.json()
                headers = {h["name"]: h["value"] for h in p.get("payload", {}).get("headers", [])}
                results.append({
                    "id": m["id"],
                    "snippet": p.get("snippet", ""),
                    "from": headers.get("From", "Unknown"),
                    "subject": headers.get("Subject", "No Subject"),
                    "date": headers.get("Date", ""),
                })
        return results
    except Exception as e:
        return [{"error": f"Gmail search error: {e}"}]


def gmail_send_email(to: str, subject: str, body: str) -> dict:
    """Send an email via Gmail from the user's authenticated account."""
    token = _get_access_token()
    if not token:
        return {"error": "Gmail MCP is not configured."}

    message_str = f"To: {to}\r\nSubject: {subject}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body}"
    raw = base64.urlsafe_b64encode(message_str.encode("utf-8")).decode("utf-8")

    try:
        r = httpx.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"raw": raw},
            timeout=15,
        )
        if r.status_code in (200, 201):
            return {"status": "success", "message": f"Email successfully sent to {to}!"}
        return {"error": f"Gmail send error ({r.status_code}): {r.text}"}
    except Exception as e:
        return {"error": f"Failed to send email: {e}"}

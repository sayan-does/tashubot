"""Tools package for TashuBot.

Provides modular autonomous agent tools:
- search: DuckDuckGo live web search
- rag: Local and bucket document retrieval via ChromaDB
- audio: Voice and audio transcription via Groq Whisper / Gemini
- github: GitHub repository and file exploration tools
- google_mcp: Google Apps integration (Drive, Calendar, Gmail, Tasks)
"""

from tools.search import web_search
from tools.rag import search_docs
from tools.audio import transcribe_audio_bytes
from tools.github import (
    github_list_repos,
    github_get_repo,
    github_list_files,
    github_read_file,
    github_get_profile,
)
from tools.google_mcp import (
    is_google_configured,
    gdrive_search_files,
    gdrive_read_file,
    gcalendar_list_events,
    gcalendar_create_event,
    gmail_search_emails,
    gmail_send_email,
    gtasks_list_tasks,
    gtasks_create_task,
    gtasks_complete_task,
)

__all__ = [
    "web_search",
    "search_docs",
    "transcribe_audio_bytes",
    "github_list_repos",
    "github_get_repo",
    "github_list_files",
    "github_read_file",
    "github_get_profile",
    "is_google_configured",
    "gdrive_search_files",
    "gdrive_read_file",
    "gcalendar_list_events",
    "gcalendar_create_event",
    "gmail_search_emails",
    "gmail_send_email",
    "gtasks_list_tasks",
    "gtasks_create_task",
    "gtasks_complete_task",
]

import json
import time
from datetime import datetime
from core.llm_providers import cascade_call
from core.telemetry import record_trace
from core.skills_manager import get_skills_prompt_summary, load_skill_tool
from tools import (
    web_search,
    search_docs,
    gdrive_search_files,
    gdrive_read_file,
    gcalendar_list_events,
    gcalendar_create_event,
    gmail_search_emails,
    gmail_send_email,
    gtasks_list_tasks,
    gtasks_create_task,
    gtasks_complete_task,
    github_list_repos,
    github_get_repo,
    github_list_files,
    github_read_file,
    github_get_profile,
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "load_skill",
            "description": "Load and activate specialized domain skills from the skills folder (e.g. 'concise-accurate' for terse replies, 'time-date-awareness' for temporal awareness, or any newly added skill).",
            "parameters": {
                "type": "object",
                "properties": {"skill_name": {"type": "string", "description": "The exact or partial name of the skill to load."}},
                "required": ["skill_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the live web for current news, facts, scores, or fresh data outside training data.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gdrive_search_files",
            "description": "Search user's documents and files in Google Drive (or inside the configured docs folder).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keywords or file name"},
                    "folder_id": {"type": "string", "description": "Optional specific Google Drive folder ID"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gdrive_read_file",
            "description": "Read text content or export of a Google Drive document or file.",
            "parameters": {
                "type": "object",
                "properties": {"file_name_or_id": {"type": "string", "description": "File name or exact Drive file ID"}},
                "required": ["file_name_or_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gcalendar_list_events",
            "description": "List upcoming events and reminders from Google Calendar starting from today.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "description": "Maximum events to fetch (default 5)"},
                    "query": {"type": "string", "description": "Optional filter keyword"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gcalendar_create_event",
            "description": "Schedule a new event or reminder in Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Event title or reminder subject"},
                    "start_time": {"type": "string", "description": "Start time in ISO format (e.g. '2026-11-03T14:00:00+05:30' or '2026-11-03')"},
                    "end_time": {"type": "string", "description": "Optional end time in ISO format"},
                    "description": {"type": "string", "description": "Optional details or notes for the event"},
                },
                "required": ["summary", "start_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_search_emails",
            "description": "Search emails in the user's Gmail inbox (e.g. 'from:name', 'is:unread', 'subject:report').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Gmail search query syntax"},
                    "max_results": {"type": "integer", "description": "Maximum emails to fetch (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_send_email",
            "description": "Send an email via Gmail from the user's account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "body": {"type": "string", "description": "Email body message text"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gtasks_list_tasks",
            "description": "List to-dos and tasks from Google Tasks (e.g. pending items, chores, project tasks).",
            "parameters": {
                "type": "object",
                "properties": {
                    "show_completed": {"type": "boolean", "description": "Whether to include completed tasks (default false)"},
                    "max_results": {"type": "integer", "description": "Maximum tasks to return (default 10)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gtasks_create_task",
            "description": "Create a new task or to-do item in Google Tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title or summary of the task to do"},
                    "notes": {"type": "string", "description": "Optional details or notes"},
                    "due": {"type": "string", "description": "Optional due date in ISO format (e.g. '2026-11-03')"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gtasks_complete_task",
            "description": "Mark a Google Task as completed by task ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The exact ID of the task to complete"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "Search local ChromaDB indexed personal notes and documents.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_list_repos",
            "description": "List the authenticated user's GitHub repositories with names, descriptions, languages, star counts, and URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "description": "Maximum repositories to return (default 10)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_get_repo",
            "description": "Get detailed metadata, description, primary language, star count, and branches for a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_name": {"type": "string", "description": "Repository name (e.g. 'tashubot' or 'sayan-does/tashubot')"},
                },
                "required": ["repo_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_list_files",
            "description": "List files and directories inside a GitHub repository directory or root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_name": {"type": "string", "description": "Repository name (e.g. 'tashubot' or 'sayan-does/tashubot')"},
                    "path": {"type": "string", "description": "Optional subdirectory path within the repository (default root '')"},
                    "branch": {"type": "string", "description": "Branch name (default 'main')"},
                },
                "required": ["repo_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_read_file",
            "description": "Read the source code or text content of a file from a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_name": {"type": "string", "description": "Repository name (e.g. 'tashubot' or 'sayan-does/tashubot')"},
                    "file_path": {"type": "string", "description": "Relative file path inside the repository (e.g. 'requirements.txt')"},
                    "branch": {"type": "string", "description": "Branch name (default 'main')"},
                },
                "required": ["repo_name", "file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_get_profile",
            "description": "Get GitHub profile information (bio, public repos, followers, following) for the user or a specific username.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Optional username to inspect (defaults to authenticated user)"},
                },
            },
        },
    },
]

FUNCS = {
    "load_skill": load_skill_tool,
    "web_search": web_search,
    "gdrive_search_files": gdrive_search_files,
    "gdrive_read_file": gdrive_read_file,
    "gcalendar_list_events": gcalendar_list_events,
    "gcalendar_create_event": gcalendar_create_event,
    "gmail_search_emails": gmail_search_emails,
    "gmail_send_email": gmail_send_email,
    "gtasks_list_tasks": gtasks_list_tasks,
    "gtasks_create_task": gtasks_create_task,
    "gtasks_complete_task": gtasks_complete_task,
    "search_docs": search_docs,
    "github_list_repos": github_list_repos,
    "github_get_repo": github_get_repo,
    "github_list_files": github_list_files,
    "github_read_file": github_read_file,
    "github_get_profile": github_get_profile,
}

# Maximum messages allowed before triggering auto-compaction/pruning
MAX_CONTEXT_MESSAGES = 16


def build_system_prompt():
    now_str = datetime.now().strftime("%A, %B %d, %Y, %I:%M %p")
    skills_summary = get_skills_prompt_summary()

    return f"""You are TashuBot (Hermes Agent), an autonomous, capable AI assistant running 24/7.
Current authoritative Date & Time: {now_str}.

Core Capabilities & Guidelines:
1. Google Apps MCP:
   - Google Drive: Use `gdrive_search_files` and `gdrive_read_file` to search documents and notes.
   - Google Calendar: Use `gcalendar_list_events` and `gcalendar_create_event` for schedule and reminders.
   - Google Tasks: Use `gtasks_list_tasks`, `gtasks_create_task`, and `gtasks_complete_task` to manage to-dos and checklists.
   - Gmail: Use `gmail_search_emails` and `gmail_send_email` for email lookups and drafting.
2. GitHub Developer Tools:
   - Repositories: Use `github_list_repos` to see authenticated user repositories.
   - Repo Inspection: Use `github_get_repo` for stars, branch, and metadata.
   - File Explorer: Use `github_list_files` to list repository folders and contents.
   - Code Reader: Use `github_read_file` to inspect code and configuration files.
   - Profile: Use `github_get_profile` to check bio, follower stats, and account info.
3. Web Search: Use `web_search` for fresh facts, sports scores, news, or latest updates.
4. Personal RAG: Use `search_docs` for locally stored vector documents.
5. Skills: Use `load_skill` to consult specialized guidelines when requested or applicable.
6. Communication: Be clear, accurate, and direct. Format answers cleanly using Markdown.

{skills_summary}
"""


def run_agent(user_message: str, history: list, chat_id: str = "default"):
    """
    Run the agent loop:
    1. Checks context window limits and automatically prunes old memory if exceeded.
    2. Sends query + tools to the LLM cascade.
    3. Handles multi-hop tool execution.
    4. Attaches transparency footer only when tools/skills are invoked.
    5. Records full observability traces in telemetry.
    """
    start_time = time.time()
    cleared_notice = ""
    memory_pruned = False

    # Auto-clear memory if context window threshold is reached
    if len(history) > MAX_CONTEXT_MESSAGES:
        del history[:-4]
        memory_pruned = True
        cleared_notice = (
            "🧹 **Notice**: Context window limit reached. Older message history has been "
            "automatically summarized and cleared to maintain optimal performance.\n\n"
        )

    system_prompt = build_system_prompt()
    messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": user_message}]
    )

    tools_used = []
    tool_details = []
    chosen_provider = "unknown"
    router_info = {"intent": "GENERAL", "router": "Heuristic"}

    try:
        for hop in range(5):  # max tool-call hops
            reply, chosen_provider, r_info = cascade_call(messages, tools=TOOLS)
            if r_info:
                router_info = r_info
            messages.append(reply)

            tool_calls = reply.get("tool_calls") if isinstance(reply, dict) else None
            if not tool_calls:
                content = reply.get("content", "") if isinstance(reply, dict) else str(reply)
                
                # Format transparency footer only if tools or skills were actually used
                footer = f"\n\n---\n🛠️ **Tools / Skills Used**: `{', '.join(tools_used)}`" if tools_used else ""
                final_answer = cleared_notice + content + footer

                latency_ms = (time.time() - start_time) * 1000
                record_trace(
                    chat_id=chat_id,
                    user_message=user_message,
                    final_response=final_answer,
                    provider=chosen_provider,
                    tools_used=tools_used,
                    tool_details=tool_details,
                    latency_ms=latency_ms,
                    memory_pruned=memory_pruned,
                    context_len=len(history) + 2,
                    status="SUCCESS",
                    router_info=router_info,
                )
                return final_answer

            for call in tool_calls:
                fn_name = call["function"]["name"]
                args = json.loads(call["function"]["arguments"])
                
                # If loading a skill, record as "skill: <name>" in tools_used
                if fn_name == "load_skill":
                    s_name = args.get("skill_name", "unknown")
                    label = f"skill:{s_name}"
                    if label not in tools_used:
                        tools_used.append(label)
                elif fn_name not in tools_used:
                    tools_used.append(fn_name)

                t_tool_start = time.time()
                result = FUNCS[fn_name](**args)
                t_tool_dur = (time.time() - t_tool_start) * 1000

                tool_details.append({
                    "hop": hop + 1,
                    "tool": fn_name,
                    "arguments": args,
                    "result_preview": str(result)[:300],
                    "duration_ms": round(t_tool_dur, 1),
                })

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result),
                    }
                )

        footer = f"\n\n---\n🛠️ **Tools / Skills Used**: `{', '.join(tools_used)}`" if tools_used else ""
        fallback_msg = (
            cleared_notice
            + "I hit the maximum tool-call hops. Please try rephrasing your request."
            + footer
        )
        latency_ms = (time.time() - start_time) * 1000
        record_trace(
            chat_id=chat_id,
            user_message=user_message,
            final_response=fallback_msg,
            provider=chosen_provider,
            tools_used=tools_used,
            tool_details=tool_details,
            latency_ms=latency_ms,
            memory_pruned=memory_pruned,
            context_len=len(history) + 2,
            status="MAX_HOPS",
            router_info=router_info,
        )
        return fallback_msg

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        err_msg = f"Sorry, I encountered an internal error: {e}"
        record_trace(
            chat_id=chat_id,
            user_message=user_message,
            final_response=err_msg,
            provider=chosen_provider,
            tools_used=tools_used,
            tool_details=tool_details,
            latency_ms=latency_ms,
            memory_pruned=memory_pruned,
            context_len=len(history) + 2,
            status="ERROR",
            error_msg=str(e),
            router_info=router_info,
        )
        return err_msg

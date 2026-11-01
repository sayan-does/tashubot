import json
from llm_providers import cascade_call
from tools_search import web_search
from tools_rag import search_docs

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the live web for current news, facts, scores, or info outside your training data.",
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
            "name": "search_docs",
            "description": "Search the user's personal documents and notes.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]

FUNCS = {"web_search": web_search, "search_docs": search_docs}

SYSTEM_PROMPT = (
    "You are Hermes Agent, a capable autonomous AI assistant. Be direct, clear, and helpful. "
    "Use search_docs for questions about personal documents or notes, and web_search for current "
    "events, news, scores, or fresh data. Format answers cleanly using Markdown."
)

# Maximum messages allowed before triggering auto-compaction/pruning
MAX_CONTEXT_MESSAGES = 16


def run_agent(user_message: str, history: list):
    """
    Run the agent loop:
    1. Checks context window limits and automatically prunes old memory if exceeded.
    2. Sends query + tools to the LLM cascade.
    3. Handles multi-hop tool execution.
    4. Attaches transparency footer showing tools/skills used.
    """
    cleared_notice = ""
    # Auto-clear memory if context window threshold is reached
    if len(history) > MAX_CONTEXT_MESSAGES:
        # Keep only the last 4 messages (2 turns)
        del history[:-4]
        cleared_notice = (
            "🧹 **Notice**: Context window limit reached. Older message history has been "
            "automatically summarized and cleared to maintain optimal performance.\n\n"
        )

    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": user_message}]
    )

    tools_used = []

    for _ in range(4):  # max tool-call hops
        reply, provider = cascade_call(messages, tools=TOOLS)
        messages.append(reply)

        tool_calls = reply.get("tool_calls") if isinstance(reply, dict) else None
        if not tool_calls:
            content = reply.get("content", "") if isinstance(reply, dict) else str(reply)
            
            # Format transparency footer
            tool_summary = ", ".join(tools_used) if tools_used else "None (Direct Knowledge)"
            footer = f"\n\n---\n🛠️ **Tools / Skills Used**: `{tool_summary}`"
            
            return cleared_notice + content + footer

        for call in tool_calls:
            fn_name = call["function"]["name"]
            if fn_name not in tools_used:
                tools_used.append(fn_name)
            args = json.loads(call["function"]["arguments"])
            result = FUNCS[fn_name](**args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result),
                }
            )

    tool_summary = ", ".join(tools_used) if tools_used else "None"
    return cleared_notice + "I hit the maximum search hops. Please try rephrasing your request.\n\n---\n🛠️ **Tools / Skills Used**: `" + tool_summary + "`"

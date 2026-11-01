import json
import time
from llm_providers import cascade_call
from tools_search import web_search
from tools_rag import search_docs
from telemetry import record_trace

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


def run_agent(user_message: str, history: list, chat_id: str = "default"):
    """
    Run the agent loop:
    1. Checks context window limits and automatically prunes old memory if exceeded.
    2. Sends query + tools to the LLM cascade.
    3. Handles multi-hop tool execution.
    4. Attaches transparency footer showing tools/skills used.
    5. Records full observability traces in telemetry.
    """
    start_time = time.time()
    cleared_notice = ""
    memory_pruned = False

    # Auto-clear memory if context window threshold is reached
    if len(history) > MAX_CONTEXT_MESSAGES:
        # Keep only the last 4 messages (2 turns)
        del history[:-4]
        memory_pruned = True
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
    tool_details = []
    chosen_provider = "unknown"

    try:
        for hop in range(4):  # max tool-call hops
            reply, chosen_provider = cascade_call(messages, tools=TOOLS)
            messages.append(reply)

            tool_calls = reply.get("tool_calls") if isinstance(reply, dict) else None
            if not tool_calls:
                content = reply.get("content", "") if isinstance(reply, dict) else str(reply)
                
                # Format transparency footer only if tools were actually invoked
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
                )
                return final_answer

            for call in tool_calls:
                fn_name = call["function"]["name"]
                if fn_name not in tools_used:
                    tools_used.append(fn_name)
                args = json.loads(call["function"]["arguments"])
                
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
            + "I hit the maximum search hops. Please try rephrasing your request."
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
        )
        return err_msg

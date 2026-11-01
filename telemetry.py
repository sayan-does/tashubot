import os
import time
import json
import threading
from datetime import datetime

DATA_DIR = "/data" if os.path.exists("/data") else os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
TELEMETRY_FILE = os.path.join(DATA_DIR, "telemetry.json")

_LOCK = threading.Lock()

_START_TIME = time.time()

_STATE = {
    "metrics": {
        "total_messages": 0,
        "total_tool_calls": 0,
        "total_memory_prunes": 0,
        "total_errors": 0,
        "total_latency_ms": 0.0,
        "providers": {},
        "tools": {},
    },
    "sessions": {},
    "traces": [],
}


def load_telemetry():
    global _STATE
    if os.path.exists(TELEMETRY_FILE):
        try:
            with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    _STATE["metrics"].update(saved.get("metrics", {}))
                    _STATE["sessions"].update(saved.get("sessions", {}))
                    _STATE["traces"] = saved.get("traces", [])[-100:]
        except Exception as e:
            print(f"[Telemetry] Error loading telemetry: {e}")


def save_telemetry():
    try:
        with open(TELEMETRY_FILE, "w", encoding="utf-8") as f:
            json.dump(_STATE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Telemetry] Error saving telemetry: {e}")


load_telemetry()


def record_trace(
    chat_id: str,
    user_message: str,
    final_response: str,
    provider: str,
    tools_used: list,
    tool_details: list,
    latency_ms: float,
    memory_pruned: bool,
    context_len: int,
    status: str = "SUCCESS",
    error_msg: str = None,
):
    with _LOCK:
        m = _STATE["metrics"]
        m["total_messages"] += 1
        m["total_tool_calls"] += len(tool_details)
        if memory_pruned:
            m["total_memory_prunes"] += 1
        if status == "ERROR":
            m["total_errors"] += 1
        m["total_latency_ms"] += latency_ms

        # Provider stats
        m["providers"][provider] = m["providers"].get(provider, 0) + 1

        # Tool stats
        if not tools_used:
            m["tools"]["direct_knowledge"] = m["tools"].get("direct_knowledge", 0) + 1
        else:
            for t in tools_used:
                m["tools"][t] = m["tools"].get(t, 0) + 1

        # Session tracking
        s = _STATE["sessions"].setdefault(
            str(chat_id),
            {
                "chat_id": str(chat_id),
                "message_count": 0,
                "memory_prunes": 0,
                "context_length": 0,
                "last_active": "",
            },
        )
        s["message_count"] += 1
        s["context_length"] = context_len
        if memory_pruned:
            s["memory_prunes"] += 1
        s["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        trace_id = f"tr_{int(time.time() * 1000)}"
        trace_entry = {
            "trace_id": trace_id,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "chat_id": str(chat_id),
            "prompt": user_message[:120] + ("..." if len(user_message) > 120 else ""),
            "full_prompt": user_message,
            "provider": provider,
            "tools_used": tools_used if tools_used else ["None"],
            "tool_details": tool_details,
            "latency_ms": round(latency_ms, 1),
            "memory_pruned": "Yes" if memory_pruned else "No",
            "context_length": context_len,
            "status": status,
            "response_preview": final_response[:200] + ("..." if len(final_response) > 200 else ""),
            "full_response": final_response,
            "error_msg": error_msg,
        }

        _STATE["traces"].insert(0, trace_entry)
        if len(_STATE["traces"]) > 100:
            _STATE["traces"].pop()

        save_telemetry()
        return trace_id


def get_uptime_str():
    secs = int(time.time() - _START_TIME)
    hrs = secs // 3600
    mins = (secs % 3600) // 60
    return f"{hrs}h {mins}m {secs % 60}s"


def get_kpis():
    with _LOCK:
        m = _STATE["metrics"]
        total = m["total_messages"]
        avg_lat = round(m["total_latency_ms"] / total, 0) if total > 0 else 0
        return {
            "uptime": get_uptime_str(),
            "total_messages": total,
            "total_tool_calls": m["total_tool_calls"],
            "total_prunes": m["total_memory_prunes"],
            "avg_latency": f"{int(avg_lat)} ms",
            "active_sessions": len(_STATE["sessions"]),
            "error_count": m["total_errors"],
        }


def get_traces_table_data():
    with _LOCK:
        rows = []
        for t in _STATE["traces"][:30]:
            rows.append(
                [
                    t["trace_id"],
                    t["timestamp"],
                    t["chat_id"],
                    t["prompt"],
                    ", ".join(t["tools_used"]),
                    t["provider"],
                    f"{t['latency_ms']} ms",
                    t["memory_pruned"],
                    t["status"],
                ]
            )
        return rows


def get_trace_ids():
    with _LOCK:
        return [t["trace_id"] for t in _STATE["traces"][:50]]


def get_trace_detail(trace_id: str):
    with _LOCK:
        for t in _STATE["traces"]:
            if t["trace_id"] == trace_id:
                return t
        if _STATE["traces"]:
            return _STATE["traces"][0]
        return {"notice": "No traces recorded yet."}


def get_sessions_table_data():
    with _LOCK:
        rows = []
        for cid, s in _STATE["sessions"].items():
            pct = min(100, int((s["context_length"] / 16) * 100))
            meter = f"{s['context_length']}/16 ({pct}%)"
            rows.append(
                [
                    cid,
                    s["message_count"],
                    meter,
                    s["memory_prunes"],
                    s["last_active"],
                ]
            )
        return rows


def get_analytics_summary():
    with _LOCK:
        m = _STATE["metrics"]
        prov_md = "### 🤖 LLM Provider Cascade Routing\n\n"
        if not m["providers"]:
            prov_md += "_No LLM calls recorded yet._\n"
        else:
            for p, count in m["providers"].items():
                prov_md += f"- **{p}**: `{count}` calls\n"

        tool_md = "### 🛠️ Autonomous Tool Usage\n\n"
        if not m["tools"]:
            tool_md += "_No tools invoked yet._\n"
        else:
            for t, count in m["tools"].items():
                emoji = "🔍" if "search" in t else ("📚" if "doc" in t else "💡")
                tool_md += f"- {emoji} **{t}**: `{count}` invocations\n"

        return prov_md, tool_md


def get_storage_info():
    info = {
        "mount_path": DATA_DIR,
        "is_hf_bucket": os.path.exists("/data"),
        "files": [],
        "total_size_kb": 0,
    }
    if os.path.exists(DATA_DIR):
        try:
            total_b = 0
            for item in os.listdir(DATA_DIR):
                ipath = os.path.join(DATA_DIR, item)
                if os.path.isfile(ipath):
                    sz = os.path.getsize(ipath)
                    total_b += sz
                    info["files"].append(f"{item} ({round(sz / 1024, 1)} KB)")
                elif os.path.isdir(ipath):
                    info["files"].append(f"📁 {item}/")
            info["total_size_kb"] = round(total_b / 1024, 1)
        except Exception as e:
            info["error"] = str(e)
    return info

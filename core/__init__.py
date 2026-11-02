"""Core package for TashuBot.

Contains the agent loop, multi-provider LLM cascade, skills management,
and telemetry/observability engines.
"""

from core.agent import run_agent, TOOLS
from core.llm_providers import (
    cascade_call,
    classify_prompt_intent,
    get_orchestrated_providers,
    call_groq,
    call_github_models,
    call_mistral,
    call_gemini_free,
    call_openrouter_free,
    ProviderError,
)
from core.skills_manager import (
    get_skills_registry,
    get_skills_prompt_summary,
    load_skill_tool,
)
from core import telemetry

__all__ = [
    "run_agent",
    "TOOLS",
    "cascade_call",
    "classify_prompt_intent",
    "get_orchestrated_providers",
    "call_groq",
    "call_github_models",
    "call_mistral",
    "call_gemini_free",
    "call_openrouter_free",
    "ProviderError",
    "get_skills_registry",
    "get_skills_prompt_summary",
    "load_skill_tool",
    "telemetry",
]

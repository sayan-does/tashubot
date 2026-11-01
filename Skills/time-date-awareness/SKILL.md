---
name: time-date-awareness
description: Keeps the assistant aware of the current date and time at all times, and makes sure that awareness is actually used — in responses, in reasoning, and especially before calling any tool whose output depends on "now" (search, calendar, reminders, scheduling, file timestamps, expiry/deadline checks, etc). Always consult this skill at the start of a conversation turn and before any tool call that is time-sensitive, even if the user didn't explicitly ask about time or date. Trigger on words like "today", "now", "current", "latest", "this week", "upcoming", "how long until", "schedule", "remind me", "deadline", "expired", or any question whose correct answer depends on knowing today's date — not just on explicit requests like "what time is it".
---

# Time & Date Awareness

Many agent failures come from a model quietly assuming a stale date — it thinks "today" is whatever date it last trained on, or just skips checking entirely, and that assumption silently corrupts everything downstream: wrong search queries, wrong "latest version" answers, wrong deadline math, reminders scheduled against the wrong day. This skill makes checking the clock a reflex, not an afterthought.

## When to use this

Use this skill proactively, not just when the user asks "what's today's date":

- **At the start of any turn** where the answer could depend on the current date or time (news, "latest", "current", "still", status checks, anything in <search_instructions>-style territory)
- **Before every tool call** where the tool's behavior or correctness depends on "now": web search, calendar/reminder tools, scheduling, RAG freshness checks, cache/TTL logic, file timestamp comparisons, rate-limit windows
- **Before any date arithmetic**: "in 3 days", "next Monday", "how many weeks until X", age calculations, countdowns, deadline checks
- **When formatting a date/time into output**: logs, filenames, timestamps in generated documents, message footers

Skip it only for genuinely timeless requests (math, definitions, fixed historical facts, pure creative writing with no date reference).

## How to get the real current date/time

Never guess, and never rely on training data for "today." In order of preference:

1. **System-provided date/time context.** Most agent harnesses inject the current date somewhere in the system prompt or a context block (e.g. "Today's date is November 02, 2026", or a `current_date` / `current_time` field). Check there first — it's free and authoritative.
2. **A `now()`-style tool or shell command**, if available and no system date is provided:
   - Shell: `date -u` (UTC) or `date` (local) — but be explicit about which one you're using
   - Code execution: `datetime.now(timezone.utc)` in Python, or the host language's equivalent
   - An explicit clock/calendar tool if the environment exposes one
3. If neither is available, say so plainly rather than inventing a date — e.g. "I don't have a reliable source for today's date in this environment, so I can't confirm 'current' without it."

Always note the **timezone** you're using (UTC vs. user's local time) when it could matter — a deadline or "today" can flip depending on which one you pick.

## What "using" the date actually means in practice

Knowing the date isn't enough — it has to change what you do:

- **Search queries**: include the year/date when freshness matters (`"iPhone 2025"` when it's actually 2026 returns stale results — use `"latest iPhone"` or the correct year instead)
- **Relative language**: resolve "next Tuesday," "in two weeks," "by end of quarter" against the real current date before answering, and show your work if the math isn't trivial
- **Tool arguments**: when a tool takes a date/time parameter, pass the computed real value — don't let the tool default to its own idea of "now" if that default might be wrong (e.g. a stale session) or if the user means a different timezone
- **Sanity-checking results**: if a tool or search result returns something that implies a different "now" than what you've established (e.g. a cached response dated months ago presented as current), flag the discrepancy instead of silently reporting it as fresh
- **Don't over-mention it**: state the date/time only when it's relevant to the answer or the user asks — don't preface every reply with "Today is X" as a tic

## Quick self-check before responding or calling a tool

Ask: *does this answer, or this tool call, implicitly depend on what day or time it is right now?*
- If yes → resolve the real current date/time first (context → tool → explicit "I can't verify" fallback), then proceed using that value.
- If no → proceed normally, no need to mention the date at all.

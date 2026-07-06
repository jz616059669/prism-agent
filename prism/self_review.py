"""
PRISM - Self-improvement review
借鉴 Hermes background_review：每轮对话后静默复盘，
自动更新记忆 + 修补 Skill，并把摘要回传给桌面端。
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

from prism.memory import persistent_memory
from prism.skills import skills

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_MEMORY_REVIEW_PROMPT = (
    "Review the conversation above and consider saving to memory if appropriate.\n\n"
    "Focus on:\n"
    "1. Has the user revealed things about themselves — their persona, desires, "
    "preferences, or personal details worth remembering?\n"
    "2. Has the user expressed expectations about how you should behave, their work "
    "style, or ways they want you to operate?\n\n"
    "If something stands out, save it using the memory tool. "
    "If nothing is worth saving, just say 'Nothing to save.' and stop."
)

_SKILL_REVIEW_PROMPT = (
    "Review the conversation above and update the skill library. Be "
    "ACTIVE — most sessions produce at least one skill update, even if "
    "small.\n\n"
    "Target shape: CLASS-LEVEL skills, each with a rich SKILL.md body and a "
    "`references/` directory for detail. Not a long flat list of narrow entries.\n\n"
    "Signals to look for (any one warrants action):\n"
    "  • User corrected your style, tone, format, verbosity, or approach.\n"
    "  • User corrected your workflow or sequence of steps.\n"
    "  • Non-trivial technique, fix, workaround, or tool-usage pattern emerged.\n"
    "  • A skill that was loaded this session turned out wrong, missing, or outdated.\n\n"
    "Preference order — pick the earliest that fits:\n"
    "  1. UPDATE A CURRENTLY-LOADED SKILL (patch SKILL.md in-place).\n"
    "  2. UPDATE AN EXISTING UMBRELLA SKILL.\n"
    "  3. ADD A SUPPORT FILE under an existing umbrella: "
    "references/<topic>.md for detail, templates/ for starter files, "
    "scripts/ for re-runnable actions.\n"
    "  4. CREATE A NEW CLASS-LEVEL UMBRELLA SKILL when nothing exists.\n\n"
    "User-preference embedding: when the user complained about how you "
    "handled a task, update the skill that governs that task so the next "
    "session starts already knowing. Memory says 'who the user is'; skills "
    "say 'how to do this class of task for this user'.\n\n"
    "Protected skills (DO NOT edit): bundled skills shipped with PRISM.\n\n"
    "Do NOT capture as skills: environment-dependent failures, one-off task "
    "narratives, or transient errors that resolved before the session ended.\n\n"
    "If genuinely nothing stands out, say 'Nothing to save.' and stop. "
    "Otherwise, act."
)

_COMBINED_REVIEW_PROMPT = (
    "Review the conversation above and update two things:\n\n"
    "**Memory**: who the user is. Save durable facts and preferences.\n\n"
    "**Skills**: how to do this class of task. Be ACTIVE.\n\n"
    "Signals that warrant a skill update (any one is enough):\n"
    "  • User corrected your style, tone, format, verbosity, or approach. "
    "'stop doing X', 'don't format like this', 'I hate when you Y' — embed "
    "the lesson in the skill that governs that task.\n"
    "  • Non-trivial technique, fix, workaround, or debugging path emerged.\n"
    "  • A skill that was loaded turned out wrong, missing, or outdated.\n\n"
    "Preference order for skills:\n"
    "  1. UPDATE A CURRENTLY-LOADED SKILL.\n"
    "  2. UPDATE AN EXISTING UMBRELLA SKILL.\n"
    "  3. ADD A SUPPORT FILE under an existing umbrella.\n"
    "  4. CREATE A NEW CLASS-LEVEL UMBRELLA SKILL.\n\n"
    "User-preference embedding: when they complain about how you handled a "
    "task, update the governing skill — memory alone isn't enough.\n\n"
    "Do NOT capture as skills: environment-dependent failures, one-off task "
    "narratives, session-specific transient errors.\n\n"
    "Act on whichever dimension has real signal. If genuinely nothing stands "
    "out, say 'Nothing to save.' and stop — but don't reach for that as a default."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _msg_text(m: Dict) -> str:
    c = m.get("content")
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, list):
        return " ".join(b.get("text", "") for b in c if isinstance(b, dict)).strip()
    return ""


def _digest_history(messages_snapshot: List[Dict], tail: int = 24) -> List[Dict]:
    msgs = list(messages_snapshot or [])
    if len(msgs) <= tail:
        return msgs
    keep = msgs[-tail:]
    while keep and isinstance(keep[0], dict) and keep[0].get("role") == "tool":
        tail += 1
        if len(msgs) <= tail:
            return msgs
        keep = msgs[-tail:]
    old = msgs[:-len(keep)]
    lines: List[str] = []
    for m in old:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        text = _msg_text(m).replace("\n", " ")
        if role == "user" and text:
            lines.append(f"USER: {text[:300]}")
        elif role == "assistant":
            tcs = m.get("tool_calls") or []
            if tcs:
                names = [(tc.get("function") or {}).get("name", "?") for tc in tcs if isinstance(tc, dict)]
                lines.append(f"ASSISTANT[tools: {', '.join(names)}]")
            if text:
                lines.append(f"ASSISTANT: {text[:200]}")
    digest = {
        "role": "user",
        "content": (
            "[Earlier conversation digest — older turns summarised.]\n" + "\n".join(lines)
        ),
    }
    return [digest] + keep


def _run_review_in_thread(
    agent: Any,
    messages_snapshot: List[Dict],
    prompt: str,
) -> None:
    from prism.agent import create_agent

    review_agent = None
    review_messages: List[Dict] = []
    try:
        review_agent = create_agent(enable_auto_memory=True)
        review_agent.session_id = getattr(agent, "session_id", "") or ""
        review_agent._persist_disabled = True
        review_agent._session_json_enabled = False

        _review_history = _digest_history(messages_snapshot)
        result = review_agent.chat(
            user_message=prompt,
        )
        review_messages = [
            {"role": m.role, "content": getattr(m, "content", "") or ""}
            for m in getattr(review_agent, "messages", []) or []
        ]

        actions = _summarize_review_actions(review_messages, messages_snapshot)
        if actions:
            summary = " · ".join(dict.fromkeys(actions))
            _safe_emit(agent, f"[self-review] {summary}")
    except Exception as exc:
        logger.warning("background review failed: %s", exc)
    finally:
        if review_agent is not None:
            try:
                review_agent.close()
            except Exception:
                pass


def _safe_emit(agent: Any, text: str) -> None:
    cb = getattr(agent, "background_review_callback", None)
    if callable(cb):
        try:
            cb(text)
            return
        except Exception:
            pass
    try:
        print(text)
    except Exception:
        pass


def _summarize_review_actions(review_messages: List[Dict], prior_snapshot: List[Dict]) -> List[str]:
    existing_tool_call_ids = set()
    existing_tool_contents = set()
    for prior in prior_snapshot or []:
        if not isinstance(prior, dict) or prior.get("role") != "tool":
            continue
        tcid = prior.get("tool_call_id")
        if tcid:
            existing_tool_call_ids.add(tcid)
        else:
            c = prior.get("content")
            if isinstance(c, str):
                existing_tool_contents.add(c)

    actions: List[str] = []
    for msg in review_messages or []:
        if not isinstance(msg, dict) or msg.get("role") != "tool":
            continue
        tcid = msg.get("tool_call_id")
        if tcid and tcid in existing_tool_call_ids:
            continue
        if not tcid:
            c = msg.get("content")
            if isinstance(c, str) and c in existing_tool_contents:
                continue
        try:
            data = json.loads(msg.get("content", "{}"))
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict) or not data.get("success"):
            continue
        message = str(data.get("message", "") or "")
        message_lower = message.lower()
        if not message_lower:
            continue
        if any(k in message_lower for k in ("created", "updated", "patched", "added", "replaced", "removed", "applied", "entry added")):
            actions.append(message)
    return actions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def spawn_background_review(
    agent: Any,
    messages_snapshot: List[Dict],
    review_memory: bool = False,
    review_skills: bool = False,
) -> None:
    if not (review_memory or review_skills):
        return
    if review_memory and review_skills:
        prompt = _COMBINED_REVIEW_PROMPT
    elif review_memory:
        prompt = _MEMORY_REVIEW_PROMPT
    else:
        prompt = _SKILL_REVIEW_PROMPT

    t = threading.Thread(
        target=_run_review_in_thread,
        args=(agent, messages_snapshot, prompt),
        daemon=True,
    )
    t.start()


__all__ = [
    "spawn_background_review",
    "_MEMORY_REVIEW_PROMPT",
    "_SKILL_REVIEW_PROMPT",
    "_COMBINED_REVIEW_PROMPT",
]

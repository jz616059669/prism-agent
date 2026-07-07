"""
PRISM /learn — 从对话/工作流蒸馏可复用 Skill。
复刻 Hermes learn_prompt 理念，适配 prism 的 skill 目录和 SKILL.md 标准。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

from prism.config import config as prism_config


_AUTHORING_STANDARDS = """\
Follow the PRISM skill-authoring standards:

Frontmatter:
- name: lowercase-hyphenated, <=64 chars, no spaces.
- description: ONE sentence, <=60 characters, ends with a period. State the
  capability, not the implementation. No marketing words.
- version: 0.1.0
- author: PRISM

Body section order:
1. "# <Human Title>" then a 2-3 sentence intro.
2. "## When to Use" — bullet list of concrete trigger phrases.
3. "## Prerequisites" — exact env vars, install steps, credentials.
4. "## How to Run" — the canonical invocation.
5. "## Quick Reference" — a flat command/endpoint list.
6. "## Procedure" — numbered steps with copy-paste-exact commands.
7. "## Pitfalls" — known limits, rate limits, things that look broken but aren't.
8. "## Verification" — a single command/check that proves the skill worked.

Quality bar:
- Prefer exact commands, endpoint URLs, function signatures, and config keys
  that appear VERBATIM in the source. NEVER invent flags, paths, or APIs.
- Keep it tight and scannable: ~100 lines for a simple skill, ~200 for a
  complex one.
- Larger scripts/parsers belong in a `scripts/` file, referenced from SKILL.md
  by relative path — not inlined for the agent to re-type every run.
"""


def build_learn_prompt(user_request: str) -> str:
    """Build the agent prompt for a /learn request."""
    req = (user_request or "").strip()
    if not req:
        req = (
            "the workflow we just went through in this conversation — review "
            "the steps taken and distill them into a reusable skill"
        )

    return (
        "[/learn] The user wants you to learn a reusable skill from the "
        "request below, and save it.\n\n"
        f"THE REQUEST:\n{req}\n\n"
        "Do this:\n"
        "1. Gather every source the user named, using the tools you already "
        "have — `read_file`/`search_files` for local files or directories, "
        "`web_extract` for URLs, the current conversation history if they "
        "referred to something you just did, and the text they pasted as-is. "
        "If the request is ambiguous about scope, make a reasonable choice "
        "and note it; do not stall.\n"
        "1b. Apply every requirement, focus, and constraint in the request to "
        "the skill you author — these govern what the SKILL.md covers and "
        "emphasizes, not just which sources you read.\n"
        "2. Author ONE SKILL.md and save it with the `write_file` tool to "
        "~/.prism/skills/<skill-name>/SKILL.md. Pick a sensible lowercase-hyphenated "
        "name. If the procedure needs a non-trivial script, add it under the "
        "skill's `scripts/` with `write_file` and reference it by relative path.\n\n"
        f"{_AUTHORING_STANDARDS}\n\n"
        "When done, tell the user the skill name, its category, and a "
        "one-line summary of what it captured."
    )


def distill_from_conversation(
    conversation_text: str,
    skill_name: str,
    description: str,
    triggers: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """从对话文本蒸馏一个最小可用 skill 并写入 ~/.prism/skills/"""
    try:
        skills_dir = Path.home() / ".prism" / "skills" / skill_name
        skills_dir.mkdir(parents=True, exist_ok=True)

        # 写入 SKILL.md
        skill_md = f"""\
---
name: {skill_name}
description: {description}
version: 0.1.0
author: PRISM
---

# {skill_name.replace('-', ' ').title()}

Auto-distilled skill from conversation workflow.

## When to Use

{chr(10).join('- ' + t for t in (triggers or [skill_name]))}

## Prerequisites

- PRISM Agent with builtin skill loader.

## How to Run

Invoke through the PRISM skill system.

## Quick Reference

- Skill file: `~/.prism/skills/{skill_name}/SKILL.md`

## Procedure

1. Load the skill via PRISM skill registry.
2. Execute with the appropriate arguments.
3. Review the output.

## Pitfalls

- This is a distilled template. Extend the Procedure section with exact
  commands after real-world use.

## Verification

Run: `python -c "from prism.skills import skills; print(skills.get('{skill_name}'))"`
"""
        (skills_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

        return {
            "success": True,
            "skill_name": skill_name,
            "path": str(skills_dir / "SKILL.md"),
            "message": f"Skill {skill_name} distilled to {skills_dir}",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc), "skill_name": skill_name}

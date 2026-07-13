"""
PRISM Agent - Multi-Agent Orchestrator
自动任务分解、角色化子 Agent 调度、结果汇总
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from prism.agent import Agent, Message

logger = logging.getLogger("prism.orchestrator")


ROLE_PROMPTS: Dict[str, str] = {
    "researcher": "你是研究型子 Agent。你的任务是快速检索信息、整理要点、给出带来源的结论。输出要简洁、结构化。",
    "coder": "你是代码型子 Agent。你的任务是编写/修复代码，优先给出可运行实现，并附上关键改动说明。",
    "reviewer": "你是审阅型子 Agent。你的任务是检查交付物是否有逻辑漏洞、安全风险或明显错误，只输出问题清单，若无问题输出 OK。",
    "writer": "你是写作型子 Agent。你的任务是按主题生成清晰、连贯、符合中文表达习惯的文案或文档。",
    "planner": "你是规划型子 Agent。你的任务是把复杂需求拆成可执行步骤，输出严格的 JSON: {\"plan\": [\"步骤1\", \"步骤2\"]}。",
}


class RoleAgent:
    """带角色 prompt 的轻量子 Agent。"""

    def __init__(self, role: str, parent_context: Optional[str] = None) -> None:
        if role not in ROLE_PROMPTS:
            raise ValueError(f"Unknown role: {role}. Available: {list(ROLE_PROMPTS)}")
        system_prompt = ROLE_PROMPTS[role]
        if parent_context:
            system_prompt = system_prompt + f"\n\n【父级上下文摘要】\n{parent_context[:800]}"
        self.role = role
        self.agent = Agent(system_prompt=system_prompt)
        self.last_output: str = ""
        self.error: Optional[str] = None

    def run(self, task: str) -> str:
        try:
            self.last_output = self.agent.chat(task) or ""
            return self.last_output
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
            logger.warning("role agent %s failed: %s", self.role, exc)
            return f"[{self.role} error] {exc}"


class TaskOrchestrator:
    """任务编排器：自动选择单 Agent / 多 Agent / 并行执行。"""

    def __init__(self, max_parallel: int = 3) -> None:
        self.max_parallel = max_parallel

    def orchestrate(self, user_message: str, parent_agent: Agent) -> str:
        text = (user_message or "").strip()
        if not text:
            return "请告诉我你需要什么帮助。"

        # 1. 轻量判断是否值得拆分
        roles = self._detect_roles(text)
        if not roles:
            # 直接走父级单 Agent
            return parent_agent.chat(text)

        # 2. 单角色：直接委托
        if len(roles) == 1:
            return self._delegate_single(roles[0], text, parent_agent)

        # 3. 多角色：并行执行 + 汇总
        return self._delegate_multi(roles, text, parent_agent)

    def _detect_roles(self, text: str) -> List[str]:
        """根据任务文本推断需要的角色，避免过度拆分。"""
        lower = text.lower()
        hits: List[str] = []
        if any(k in lower for k in ["搜索", "研究", "调研", "查", "查找", "总结资料", "背景", "research", "调查"]):
            hits.append("researcher")
        if any(k in lower for k in ["写代码", "实现", "修复", "代码", "bug", "开发", "重构", "code", "python", "js", "ts"]):
            hits.append("coder")
        if any(k in lower for k in ["审阅", "检查", "review", "bug", "问题", "风险", "安全", "审计"]):
            hits.append("reviewer")
        if any(k in lower for k in ["写", "撰写", "润色", "文案", "文章", "大纲", "小说", "文档", "write", "draft"]):
            hits.append("writer")
        if any(k in lower for k in ["步骤", "规划", "计划", "步骤", "安排", "拆解", "plan"]):
            hits.append("planner")
        # 去重保序
        seen = set()
        ordered = []
        for r in hits:
            if r not in seen:
                seen.add(r)
                ordered.append(r)
        return ordered[: self.max_parallel]

    def _delegate_single(self, role: str, task: str, parent_agent: Agent) -> str:
        worker = RoleAgent(role=role, parent_context=self._context(parent_agent))
        output = worker.run(task)
        parent_agent.messages.append(Message(role="tool", content=f"[subagent:{role}] {output}"))
        return output

    def _delegate_multi(self, roles: List[str], task: str, parent_agent: Agent) -> str:
        context = self._context(parent_agent)
        workers = [RoleAgent(role=r, parent_context=context) for r in roles]

        # 并行执行
        results: Dict[str, str] = {}
        for w in workers:
            results[w.role] = w.run(task)

        # 汇总：优先由 planner 汇总，否则用父级
        synthesis = self._synthesize(task, results, parent_agent)
        parent_agent.messages.append(Message(role="tool", content=f"[orchestrator] {synthesis}"))
        return synthesis

    def _synthesize(self, task: str, results: Dict[str, str], parent_agent: Agent) -> str:
        parts = ["【多 Agent 执行结果】"]
        for role, out in results.items():
            parts.append(f"[{role}]\n{out}\n")
        combined = "\n".join(parts)
        prompt = (
            "请把下面多角色执行结果整合成一份最终回复。\n"
            "要求：只输出结果，不要解释你是如何汇总的。\n\n"
            f"任务：{task}\n\n{combined}"
        )
        try:
            final = parent_agent.chat(prompt)
            return final or combined
        except Exception as exc:  # noqa: BLE001
            logger.debug("synthesis failed: %s", exc)
            return combined

    @staticmethod
    def _context(agent: Agent) -> str:
        try:
            recent = agent.messages[-6:] if getattr(agent, "messages", []) else []
            return "\n".join(f"{m.role}: {m.content}" for m in recent)
        except Exception:
            return ""

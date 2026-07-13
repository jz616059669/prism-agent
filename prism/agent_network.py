"""
PRISM Agent - 多 Agent 协作网络
多个 Agent 互相委派：调研 → 写作 → 审校，支持循环反馈
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from prism.orchestrator import RoleAgent, TaskOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class CollaborationEdge:
    from_role: str
    to_role: str
    condition: str = ""  # 触发条件表达式


@dataclass
class AgentNetwork:
    name: str
    roles: List[str] = field(default_factory=list)
    edges: List[CollaborationEdge] = field(default_factory=list)
    max_rounds: int = 3
    context: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "roles": self.roles,
            "edges": [e.__dict__ for e in self.edges],
            "max_rounds": self.max_rounds,
            "context": self.context,
        }


class AgentNetworkRunner:
    def __init__(self, network: AgentNetwork) -> None:
        self.network = network
        self._orchestrator = TaskOrchestrator()

    def run(self, task: str) -> Dict[str, Any]:
        if not self.network.roles:
            return {"success": False, "error": "no roles configured"}
        outputs: Dict[str, str] = {}
        current_role = self.network.roles[0]
        context = self.network.context or task
        for round_idx in range(self.network.max_rounds):
            role_agent = RoleAgent(current_role, parent_context=context)
            result = role_agent.run(task)
            outputs[current_role] = result
            context = context + f"\n[{current_role} 输出]\n{result}\n"
            next_role = self._pick_next(current_role, result)
            if not next_role:
                break
            current_role = next_role
        return {
            "success": True,
            "network": self.network.name,
            "rounds": round_idx + 1,
            "outputs": outputs,
            "final": context,
        }

    def _pick_next(self, current: str, last_output: str) -> Optional[str]:
        for edge in self.network.edges:
            if edge.from_role == current:
                return edge.to_role
        # 默认线性流转
        idx = self.network.roles.index(current) if current in self.network.roles else -1
        if idx + 1 < len(self.network.roles):
            return self.network.roles[idx + 1]
        return None


# 预定义网络
NETWORKS: Dict[str, AgentNetwork] = {
    "research_writer_reviewer": AgentNetwork(
        name="research_writer_reviewer",
        roles=["researcher", "writer", "reviewer"],
        edges=[
            CollaborationEdge(from_role="researcher", to_role="writer"),
            CollaborationEdge(from_role="writer", to_role="reviewer"),
        ],
        max_rounds=3,
        context="这是一个协作网络：研究员先搜集信息，然后写作者生成文案，最后审校检查问题。",
    ),
    "code_review": AgentNetwork(
        name="code_review",
        roles=["coder", "reviewer"],
        edges=[CollaborationEdge(from_role="coder", to_role="reviewer")],
        max_rounds=2,
        context="这是一个代码协作网络：coder 先写代码，reviewer 再检查。",
    ),
}


def list_networks() -> List[Dict[str, Any]]:
    return [{"name": k, **v.to_dict()} for k, v in NETWORKS.items()]


def get_network(name: str) -> Optional[AgentNetwork]:
    return NETWORKS.get(name)


def run_network(name: str, task: str) -> Dict[str, Any]:
    network = get_network(name)
    if not network:
        return {"success": False, "error": f"network not found: {name}"}
    runner = AgentNetworkRunner(network)
    return runner.run(task)

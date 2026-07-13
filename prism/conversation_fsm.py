"""
PRISM Agent - 对话状态机
有限状态机控制对话流程，支持表单/向导模式
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class State:
    name: str
    on_enter: str = ""
    on_exit: str = ""
    transitions: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "on_enter": self.on_enter,
            "on_exit": self.on_exit,
            "transitions": list(self.transitions),
        }


@dataclass
class ConversationFSM:
    initial: str = "idle"
    current: str = "idle"
    states: List[State] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial": self.initial,
            "current": self.current,
            "states": [s.to_dict() for s in self.states],
            "context": dict(self.context),
        }


class ConversationStateMachine:
    def __init__(self) -> None:
        self._machines: Dict[str, ConversationFSM] = {}

    def create(self, session_id: str, fsm: ConversationFSM) -> ConversationFSM:
        self._machines[session_id] = fsm
        return fsm

    def get(self, session_id: str) -> Optional[ConversationFSM]:
        return self._machines.get(session_id)

    def transition(self, session_id: str, event: str) -> Optional[ConversationFSM]:
        fsm = self._machines.get(session_id)
        if not fsm:
            return None
        state = next((s for s in fsm.states if s.name == fsm.current), None)
        if not state:
            return None
        for trans in state.transitions:
            if trans.get("event") == event:
                fsm.current = trans.get("target", fsm.current)
                break
        return fsm


conversation_fsm = ConversationStateMachine()

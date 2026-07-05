"""
PRISM Agent - Workspace Manager
借鉴 OpenClaw 的工作区隔离机制，支持多工作区独立会话。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from prism.paths import workspaces_dir, sessions_dir

logger = logging.getLogger("prism.workspace")


@dataclass
class Workspace:
    name: str
    path: Path
    description: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkspaceManager:
    """管理多个工作区，每个工作区有独立的 Agent 和会话。"""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or workspaces_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._workspaces: Dict[str, Workspace] = {}
        self._agents: Dict[str, Agent] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._load_workspaces()

    def _load_workspaces(self) -> None:
        """从磁盘加载工作区配置。"""
        from prism.agent import Agent
        config_file = self.base_dir / "workspaces.json"
        if not config_file.exists():
            # 创建默认工作区
            self.create_workspace(
                name="default",
                path=sessions_dir(),
                description="Default workspace",
            )
            return
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            for ws in data.get("workspaces", []):
                workspace = Workspace(
                    name=ws["name"],
                    path=Path(ws["path"]),
                    description=ws.get("description", ""),
                    tags=ws.get("tags", []),
                    metadata=ws.get("metadata", {}),
                )
                self._workspaces[workspace.name] = workspace
        except Exception as exc:
            logger.warning("failed to load workspaces: %s", exc)

    def _save_workspaces(self) -> None:
        """保存工作区配置到磁盘。"""
        config_file = self.base_dir / "workspaces.json"
        data = {
            "workspaces": [
                {
                    "name": ws.name,
                    "path": str(ws.path),
                    "description": ws.description,
                    "tags": ws.tags,
                    "metadata": ws.metadata,
                }
                for ws in self._workspaces.values()
            ]
        }
        config_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def create_workspace(
        self,
        name: str,
        path: Path,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> Workspace:
        """创建新工作区。"""
        from prism.agent import Agent
        if name in self._workspaces:
            raise ValueError(f"Workspace '{name}' already exists")
        workspace = Workspace(
            name=name,
            path=path,
            description=description,
            tags=tags or [],
        )
        self._workspaces[name] = workspace
        self._agents[name] = Agent()
        path.mkdir(parents=True, exist_ok=True)
        self._save_workspaces()
        logger.info("workspace created: %s -> %s", name, path)
        return workspace

    def switch_workspace(self, name: str) -> Agent:
        """切换到指定工作区，返回该工作区的 Agent。"""
        if name not in self._workspaces:
            raise ValueError(f"Workspace '{name}' not found")
        if name not in self._agents:
            self._agents[name] = Agent()
        return self._agents[name]

    def get_agent(self, workspace_name: str) -> Agent:
        """获取工作区的 Agent，不存在则创建。"""
        if workspace_name not in self._agents:
            self._agents[workspace_name] = Agent()
        return self._agents[workspace_name]

    def list_workspaces(self) -> List[Dict[str, Any]]:
        """列出所有工作区。"""
        self._ensure_loaded()
        return [
            {
                "name": ws.name,
                "path": str(ws.path),
                "description": ws.description,
                "tags": ws.tags,
            }
            for ws in self._workspaces.values()
        ]

    def delete_workspace(self, name: str) -> None:
        """删除工作区。"""
        self._ensure_loaded()
        if name == "default":
            raise ValueError("Cannot delete default workspace")
        if name in self._workspaces:
            del self._workspaces[name]
            if name in self._agents:
                del self._agents[name]
            self._save_workspaces()
            logger.info("workspace deleted: %s", name)


# 全局工作区管理器实例
workspace_manager = WorkspaceManager()

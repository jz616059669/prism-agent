"""
PRISM Agent - 工作区快照与回滚
在改文件前自动打快照，支持 /rollback 回退到最近一次快照
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

from prism.paths import PRISM_HOME

CHECKPOINT_DIR = PRISM_HOME / "checkpoints"
MAX_CHECKPOINTS = 20


def _ensure_checkpoint_dir() -> None:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    # 清理过多旧快照
    try:
        files = sorted(CHECKPOINT_DIR.glob("*.json"), key=os.path.getmtime)
        if len(files) > MAX_CHECKPOINTS:
            for old in files[:-MAX_CHECKPOINTS]:
                try:
                    old.unlink()
                except OSError:
                    pass
    except OSError:
        pass


def save_checkpoint(agent, label: Optional[str] = None) -> Optional[Path]:
    """
    保存当前 agent 状态快照。
    返回快照文件路径，失败返回 None。
    """
    try:
        _ensure_checkpoint_dir()
        payload = {
            "ts": time.time(),
            "label": label or "",
            "session_id": getattr(agent, "session_id", "") or "",
            "messages": [
                {
                    "role": getattr(m, "role", ""),
                    "content": (getattr(m, "content", "") or ""),
                    "timestamp": getattr(m, "timestamp", None).isoformat() if getattr(m, "timestamp", None) else "",
                }
                for m in getattr(agent, "messages", []) or []
            ],
            "system_prompt": getattr(agent, "system_prompt", "") or "",
            "working_dir": os.getcwd(),
        }
        ts = int(time.time() * 1000)
        path = CHECKPOINT_DIR / f"{ts}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
    except OSError as exc:
        try:
            from prism.logging import logger
            logger.debug("save checkpoint failed: %s", exc)
        except OSError:
            pass
        return None


def load_latest_checkpoint() -> Optional[dict]:
    """加载最新快照"""
    try:
        if not CHECKPOINT_DIR.exists():
            return None
        files = sorted(CHECKPOINT_DIR.glob("*.json"), key=os.path.getmtime)
        if not files:
            return None
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def rollback(agent) -> dict:
    """
    回滚到最近一次快照。
    返回操作结果字典。
    """
    try:
        snapshot = load_latest_checkpoint()
        if not snapshot:
            return {"success": False, "error": "未找到可用快照"}
        messages = snapshot.get("messages", [])
        if not messages:
            return {"success": False, "error": "快照内容为空"}
        # 重建消息列表
        from prism.agent import Message
        from datetime import datetime
        restored = []
        for m in messages:
            ts = m.get("timestamp", "")
            try:
                parsed_ts = datetime.fromisoformat(ts) if ts else datetime.now()
            except Exception:
                parsed_ts = datetime.now()
            restored.append(Message(
                role=m.get("role", "user"),
                content=m.get("content", ""),
                timestamp=parsed_ts,
                metadata={},
            ))
        agent.messages = restored
        sp = snapshot.get("system_prompt") or ""
        if sp:
            agent.system_prompt = sp
            if agent.messages and agent.messages[0].role == "system":
                agent.messages[0].content = sp
        wd = snapshot.get("working_dir") or os.getcwd()
        try:
            os.chdir(wd)
        except Exception:
            pass
        return {
            "success": True,
            "restored_messages": len(restored),
            "checkpoint_label": snapshot.get("label") or "",
            "working_dir": wd,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


__all__ = ["save_checkpoint", "rollback", "load_latest_checkpoint"]

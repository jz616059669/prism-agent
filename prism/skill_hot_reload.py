"""
PRISM Agent - Skill Hot-Reload
监听技能目录变更，自动刷新 SkillRegistry
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent

from prism.skills import SkillRegistry

logger = logging.getLogger(__name__)


class _SkillChangeHandler(FileSystemEventHandler):
    def __init__(self, registry: SkillRegistry, cooldown: float = 1.0):
        self._registry = registry
        self._cooldown = cooldown
        self._last_reload = 0.0

    def _should_reload(self, event) -> bool:
        if not event.src_path.endswith(".py"):
            return False
        now = time.time()
        if now - self._last_reload < self._cooldown:
            return False
        self._last_reload = now
        return True

    def on_modified(self, event):
        if isinstance(event, (FileModifiedEvent,)) and self._should_reload(event):
            logger.info("skill file changed, reloading registry: %s", event.src_path)
            self._registry.reload()

    def on_created(self, event):
        if isinstance(event, (FileCreatedEvent,)) and self._should_reload(event):
            logger.info("new skill file detected, reloading registry: %s", event.src_path)
            self._registry.reload()

    def on_deleted(self, event):
        if isinstance(event, (FileDeletedEvent,)) and self._should_reload(event):
            logger.info("skill file removed, reloading registry: %s", event.src_path)
            self._registry.reload()


class SkillHotReloader:
    _instance: Optional["SkillHotReloader"] = None

    def __init__(self, registry: Optional[SkillRegistry] = None, watch_dir: Optional[str] = None) -> None:
        self._registry = registry or SkillRegistry()
        self._watch_dir = Path(watch_dir or Path.home() / ".prism" / "skills")
        self._observer = Observer()
        self._handler = _SkillChangeHandler(self._registry)
        self._started = False

    @classmethod
    def get_instance(cls) -> Optional["SkillHotReloader"]:
        return cls._instance

    def start(self) -> None:
        if self._started:
            return
        try:
            self._watch_dir.mkdir(parents=True, exist_ok=True)
            self._observer.schedule(self._handler, str(self._watch_dir), recursive=True)
            self._observer.start()
            self._started = True
            logger.info("skill hot-reload watching: %s", self._watch_dir)
        except Exception as exc:
            logger.warning("skill hot-reload start failed: %s", exc)

    def stop(self) -> None:
        if not self._started:
            return
        try:
            self._observer.stop()
            self._observer.join(timeout=3)
            self._started = False
        except Exception:
            pass

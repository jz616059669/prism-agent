"""
PRISM Agent - 定时任务可视化
cron 任务日历/时间线视图
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SCHED_DIR = Path.home() / ".prism" / "schedules"
_SCHED_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ScheduleEvent:
    name: str
    cron: str = ""
    next_ts: float = 0.0
    last_run: float = 0.0
    status: str = "enabled"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "cron": self.cron,
            "next_ts": self.next_ts,
            "last_run": self.last_run,
            "status": self.status,
        }


class ScheduleVisualizer:
    def __init__(self) -> None:
        self._events: Dict[str, ScheduleEvent] = {}
        self._load()
        self._load_cron()

    def _load(self) -> None:
        for event_file in _SCHED_DIR.glob("*.json"):
            try:
                data = json.loads(event_file.read_text(encoding="utf-8"))
                ev = ScheduleEvent(**data)
                self._events[ev.name] = ev
            except Exception:
                continue

    def _load_cron(self) -> None:
        try:
            from crontab import CronTab
            cron = CronTab(user=True)
            for job in cron:
                name = job.comment or job.command[:20]
                self._events[name] = ScheduleEvent(name=name, cron=str(job.slices), status="enabled")
        except Exception:
            try:
                import subprocess
                out = subprocess.check_output(["crontab", "-l"], text=True, timeout=5)
                for line in out.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(None, 5)
                    if len(parts) < 6:
                        continue
                    name = parts[-1][:20]
                    cron = " ".join(parts[:5])
                    self._events[name] = ScheduleEvent(name=name, cron=cron, status="enabled")
            except Exception:
                pass

    def add(self, event: ScheduleEvent) -> ScheduleEvent:
        self._events[event.name] = event
        self._save(event)
        return event

    def timeline(self, days: int = 7) -> List[Dict[str, Any]]:
        now = __import__("time").time()
        items = [ev.to_dict() for ev in self._events.values() if ev.next_ts and now <= ev.next_ts <= now + days * 24 * 3600]
        items.sort(key=lambda x: x.get("next_ts", 0))
        return items

    def calendar_grid(self) -> Dict[str, List[Dict[str, Any]]]:
        timeline = self.timeline(days=30)
        grid: Dict[str, List[Dict[str, Any]]] = {}
        for item in timeline:
            day = __import__("datetime").datetime.fromtimestamp(item.get("next_ts", 0)).strftime("%Y-%m-%d")
            grid.setdefault(day, []).append(item)
        return grid

    def sync_from_cron(self) -> int:
        self._events = {k: v for k, v in self._events.items() if not k.startswith("cron_auto_")}
        self._load_cron()
        return len(self._events)

    def next_run_estimate(self, cron_expr: str, base_ts: float = 0.0) -> float:
        base_ts = base_ts or __import__("time").time()
        try:
            from crontab import CronTab
            job = CronTab(line=f"0 {cron_expr} true")
            return float(job.schedule(base_ts).get_next())
        except Exception:
            return 0.0

    def to_timeline_widgets(self, days: int = 7) -> List[Dict[str, Any]]:
        items = self.timeline(days=days)
        widgets = []
        for item in items:
            dt = __import__("datetime").datetime.fromtimestamp(item.get("next_ts", 0))
            widgets.append({
                "title": item.get("name", ""),
                "subtitle": item.get("cron", ""),
                "time": dt.strftime("%m-%d %H:%M"),
                "status": item.get("status", "enabled"),
            })
        return widgets

    def _save(self, event: ScheduleEvent) -> None:
        try:
            (_SCHED_DIR / f"{event.name}.json").write_text(
                json.dumps(event.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


schedule_visualizer = ScheduleVisualizer()

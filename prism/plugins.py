"""
PRISM Agent - Plugin System
插件系统：支持第三方工具、hooks、memory provider 扩展。
"""

from __future__ import annotations

import importlib.util
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from prism.logging import logger
from prism.hooks import Hook, hook_manager


@dataclass
class PluginManifest:
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    entrypoint: str = ""
    hooks: List[Dict[str, Any]] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    memory_providers: List[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class Plugin:
    manifest: PluginManifest
    module: Any = None
    path: Path = field(default_factory=Path)


class PluginManager:
    """
    管理插件生命周期：发现、加载、启用/禁用、卸载。
    """

    def __init__(self, plugin_dir: Optional[Path] = None) -> None:
        self.plugin_dir = plugin_dir or (PRISM_PLUGINS_DIR if 'PRISM_PLUGINS_DIR' in globals() else Path.home() / ".prism" / "plugins")
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self._plugins: Dict[str, Plugin] = {}
        self._registry_file = self.plugin_dir / "registry.json"
        self._load_registry()

    def _load_registry(self) -> None:
        if not self._registry_file.exists():
            return
        try:
            data = json.loads(self._registry_file.read_text(encoding="utf-8"))
            for item in data.get("plugins", []):
                try:
                    manifest = PluginManifest(**item)
                    self._plugins[manifest.name] = Plugin(manifest=manifest)
                except Exception:
                    continue
        except Exception:
            pass

    def _save_registry(self) -> None:
        data = {
            "plugins": [
                {
                    "name": p.manifest.name,
                    "version": p.manifest.version,
                    "description": p.manifest.description,
                    "author": p.manifest.author,
                    "entrypoint": p.manifest.entrypoint,
                    "hooks": p.manifest.hooks,
                    "tools": p.manifest.tools,
                    "memory_providers": p.manifest.memory_providers,
                    "enabled": p.manifest.enabled,
                }
                for p in self._plugins.values()
            ]
        }
        self._registry_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def discover(self) -> List[PluginManifest]:
        """扫描插件目录，返回所有发现的 manifest"""
        found: List[PluginManifest] = []
        for pkg_dir in self.plugin_dir.iterdir():
            if not pkg_dir.is_dir():
                continue
            manifest_path = pkg_dir / "plugin.json"
            if not manifest_path.exists():
                continue
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest = PluginManifest(**data)
                found.append(manifest)
            except Exception:
                continue
        return found

    def install(self, source: str) -> Dict[str, Any]:
        """
        安装插件：source 为本地目录路径。
        目录下需包含 plugin.json + Python 包。
        """
        try:
            src = Path(source)
            if not src.exists() or not src.is_dir():
                return {"success": False, "error": f"插件源不存在: {source}"}
            manifest_path = src / "plugin.json"
            if not manifest_path.exists():
                return {"success": False, "error": "缺少 plugin.json"}
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest = PluginManifest(**data)
            except Exception as exc:
                return {"success": False, "error": f"plugin.json 无效: {exc}"}
            dest = self.plugin_dir / manifest.name
            if dest.exists():
                return {"success": False, "error": f"插件已存在: {manifest.name}"}
            try:
                import shutil
                shutil.copytree(src, dest)
            except Exception as exc:
                return {"success": False, "error": f"复制失败: {exc}"}
            self._plugins[manifest.name] = Plugin(manifest=manifest, path=dest)
            self._save_registry()
            return {"success": True, "plugin": manifest.name, "version": manifest.version}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def uninstall(self, name: str) -> Dict[str, Any]:
        """卸载插件"""
        if name not in self._plugins:
            return {"success": False, "error": f"插件未安装: {name}"}
        try:
            import shutil
            dest = self.plugin_dir / name
            if dest.exists():
                shutil.rmtree(dest)
            del self._plugins[name]
            self._save_registry()
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def enable(self, name: str) -> Dict[str, Any]:
        if name not in self._plugins:
            return {"success": False, "error": f"插件未安装: {name}"}
        self._plugins[name].manifest.enabled = True
        self._save_registry()
        return {"success": True}

    def disable(self, name: str) -> Dict[str, Any]:
        if name not in self._plugins:
            return {"success": False, "error": f"插件未安装: {name}"}
        self._plugins[name].manifest.enabled = False
        self._save_registry()
        return {"success": True}

    def load(self, name: str) -> Optional[Plugin]:
        """加载单个插件"""
        if name not in self._plugins:
            return None
        plugin = self._plugins[name]
        if not plugin.manifest.enabled:
            return None
        if plugin.module is not None:
            return plugin
        try:
            entrypoint = plugin.manifest.entrypoint or f"{name}.plugin:register"
            module_path, _, attr = entrypoint.partition(":")
            if not module_path or not attr:
                return None
            full_path = plugin.path / f"{module_path}.py"
            if not full_path.exists():
                return None
            spec = importlib.util.spec_from_file_location(f"prism_plugin_{name}", full_path)
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            register = getattr(module, attr, None)
            if callable(register):
                register(self._make_plugin_context(name))
            plugin.module = module
            return plugin
        except Exception as exc:
            logger.debug("load plugin %s failed: %s", name, exc)
            return None

    def _make_plugin_context(self, name: str) -> Dict[str, Any]:
        return {
            "name": name,
            "register_tool": self._register_plugin_tool,
            "register_hook": self._register_plugin_hook,
            "register_memory_provider": self._register_plugin_memory,
        }

    def _register_plugin_tool(self, tool: Any) -> None:
        try:
            from prism.tools.registry import registry
            registry.register(tool)
        except Exception as exc:
            logger.debug("plugin register tool failed: %s", exc)

    def _register_plugin_hook(self, hook: Hook) -> None:
        try:
            hook_manager.register(hook)
        except Exception as exc:
            logger.debug("plugin register hook failed: %s", exc)

    def _register_plugin_memory(self, provider: Any) -> None:
        try:
            from prism.memory_providers import memory_provider_registry
            memory_provider_registry.register(getattr(provider, "name", "plugin"), provider)
        except Exception as exc:
            logger.debug("plugin register memory failed: %s", exc)

    def load_all(self) -> List[Plugin]:
        loaded: List[Plugin] = []
        for name in list(self._plugins.keys()):
            plugin = self.load(name)
            if plugin is not None:
                loaded.append(plugin)
        return loaded

    def list_plugins(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": p.manifest.name,
                "version": p.manifest.version,
                "description": p.manifest.description,
                "author": p.manifest.author,
                "enabled": p.manifest.enabled,
                "loaded": p.module is not None,
            }
            for p in self._plugins.values()
        ]


# 插件目录
try:
    from prism.paths import PRISM_HOME
    PRISM_PLUGINS_DIR = PRISM_HOME / "plugins"
except Exception:
    PRISM_PLUGINS_DIR = Path.home() / ".prism" / "plugins"

plugin_manager = PluginManager()


__all__ = [
    "PluginManifest",
    "Plugin",
    "PluginManager",
    "plugin_manager",
]

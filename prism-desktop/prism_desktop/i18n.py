"""
PRISM Desktop - 国际化（i18n）
当前仅内置中文，后续可扩展英文/日文等
"""

from prism.logging import logger

zh_CN = {
    "app_title": "PRISM Desktop",
    "ready": "就绪",
    "prism_thinking": "PRISM 正在思考...",
    "copied": "已复制",
    "deleted": "已删除",
    "pinned": "已置顶",
    "stopped": "已停止",
    "config_missing": "配置缺失：{items}",
    "config_saved": "配置已保存",
    "save_failed": "保存失败：{error}",
    "session_saved": "会话已保存",
    "session_save_failed": "会话保存失败",
    "session_deleted": "会话已删除",
    "delete_failed": "删除失败",
    "open_main": "打开主窗口",
    "minimize_to_tray": "最小化到托盘",
    "exit_app": "退出",
    "refresh": "刷新",
    "refresh_mcp": "刷新 MCP 服务器",
    "no_mcp_servers": "未配置 MCP 服务器",
    "start": "启动",
    "started": "已启动",
    "stopped_label": "已停止",
    "no_tools": "暂无工具",
    "clear_mcp": "清空 MCP",
    "clear_terminal": "清空终端",
    "clear_chat": "清屏",
    "input_placeholder": "输入消息开始对话",
    "chat_tab": "对话",
    "session_tab": "会话",
    "settings_tab": "设置",
    "status_tab": "状态",
    "about": "关于",
    "default_model": "默认模型",
    "model_provider": "模型提供商",
    "base_url": "Base URL",
    "api_key": "API Key",
    "save_settings": "保存配置",
    "browser_control": "浏览器控制",
    "open_browser": "打开浏览器",
    "snapshot": "快照",
    "close_browser": "关闭浏览器",
    "control": "控制",
    "no_reply": "无回复",
    "request_timeout": "请求超时",
    "error_prefix": "Error:",
    "version": "版本",
    "preset": "预设",
    "preset_saved": "预设已保存：{name}",
    "preset_deleted": "预设已删除：{name}",
    "preset_switched": "已切换预设：{name}",
    "save_preset": "保存预设",
    "delete_preset": "删除预设",
    "skills_refresh": "skills refreshed: {count} 个",
    "skills_error": "skills error: {error}",
    "no_skills": "暂无 Skills",
    "install_skill": "安装 Skill",
    "install_skill_placeholder": "安装 Skill 名称或本地路径",
    "refresh_skills": "刷新 Skills",
    "skill_toggle": "切换启用/禁用",
    "skill_uninstall": "卸载",
    "skill_enabled": "启用",
    "skill_disabled": "禁用",
    "skill_search_placeholder": "搜索 Skills...",
    "skill_detail": "详情",
    "skill_hub_browse": "浏览技能库",
    "skill_hub_search": "搜索技能库",
    "skill_hub_install": "安装",
    "skill_hub_empty": "暂无远程技能库结果",
    "skill_hub_error": "技能库访问失败",
    "new_session": "新对话",
    "session_name": "会话名称",
    "save_session": "保存会话",
    "load_session": "加载会话",
    "delete_session": "删除会话",
    "export_session": "导出会话",
    "saved_sessions": "已保存会话",
    "search_sessions": "搜索会话...",
    "char_count": "{count} 字",
    "theme": "主题",
    "theme_light": "浅色",
    "theme_dark": "深色",
    "stream_start": "stream_start",
    "stream_complete": "stream_complete",
    "stream_stopped": "stream_stopped",
    "perf_tick": "perf_tick",
    "update_available": "发现新版本 {version}",
    "checking_update": "正在检查更新...",
    "validation_failed": "配置校验失败：{error}",
    "validation_ok": "配置校验通过",
    "restore_layout_defaults": "恢复默认布局",
}

_translations = {
    "zh_CN": zh_CN,
}


def gettext(key: str, **kwargs) -> str:
    """获取翻译文本，默认中文"""
    lang = "zh_CN"
    text = _translations.get(lang, {}).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError) as exc:
            logger.debug("gettext format failed for key=%s: %s", key, exc)
    return text

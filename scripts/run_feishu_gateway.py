"""
PRISM Feishu Gateway 自启动脚本
Windows 计划任务调用此脚本，后台常驻并写日志。
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

# 日志文件
_LOG_FILE = Path.home() / ".prism" / "gateway_autostart.log"


def _log(msg: str) -> None:
    try:
        with _LOG_FILE.open("a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


def main() -> int:
    try:
        _log("autostart begin")
        from prism.cli.gateway import setup_gateway_platform, _resolve_config_path, _load_config
        from prism.gateway import gateway as gw
        from prism.gateway.feishu import FeishuAdapter, FeishuConfig
        from prism.agent import create_agent
        import yaml

        cfg_path = _resolve_config_path()
        cfg = _load_config(cfg_path)
        gw_cfg = cfg.get("gateway") or {}
        feishu_cfg = gw_cfg.get("feishu") or {}
        app_id = feishu_cfg.get("app_id") or ""
        app_secret = feishu_cfg.get("app_secret") or ""
        if not app_id or not app_secret:
            _log("no feishu config, exit")
            return 1

        setup_gateway_platform(cfg, "feishu", {
            "app_id": app_id,
            "app_secret": app_secret,
            "encrypt_key": feishu_cfg.get("encrypt_key") or "",
            "verification_token": feishu_cfg.get("verification_token") or "",
        })
        cfg_path.write_text(yaml.dump(cfg, allow_unicode=True, default_flow_style=False), encoding="utf-8")

        adapter = FeishuAdapter(FeishuConfig(
            app_id=app_id,
            app_secret=app_secret,
            encrypt_key=feishu_cfg.get("encrypt_key") or "",
            verification_token=feishu_cfg.get("verification_token") or "",
        ))
        gw.register("feishu", adapter)
        agent = create_agent()
        sessions: dict = {}

        def handler(msg):
            text = getattr(msg, "text", "") or ""
            chat_id = getattr(msg, "chat_id", "") or ""
            message_type = getattr(msg, "message_type", "text") or "text"
            if not chat_id:
                return
            display = text or f"[{message_type}]"
            _log(f"received: {display}")
            if chat_id not in sessions:
                sessions[chat_id] = create_agent()
            if message_type == "text":
                thinking_msg_id = adapter.send_thinking(chat_id)
                try:
                    reply = sessions[chat_id].chat(text)
                except Exception as exc:
                    reply = f"抱歉，处理你的消息时出错了：{exc}"
                if reply:
                    if thinking_msg_id:
                        adapter.update_message(thinking_msg_id, reply)
                    else:
                        adapter.send(chat_id, reply)
            else:
                thinking_msg_id = adapter.send_thinking(chat_id, f"正在修炼中…… 收到{message_type}消息")
                reply = f"我收到了你的{message_type}消息，当前版本主要支持文字对话，这类消息暂不能深度处理。"
                if thinking_msg_id:
                    adapter.update_message(thinking_msg_id, reply)
                else:
                    adapter.send(chat_id, reply)

        gw.start(handler)
        _log("gateway started")
        import time
        while True:
            time.sleep(1)
    except Exception:
        _log(traceback.format_exc())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

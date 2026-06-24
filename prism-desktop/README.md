# PRISM Desktop

基于 **Flet** 的桌面客户端，提供比 Codex CLI 更现代的操作界面。

## 启动

```bash
cd prism-desktop
uv run flet run prism_desktop/main.py
```

或安装为命令：

```bash
uv tool install -e .
prism-desktop
```

## 功能

- 侧边栏配置模型、提供商、API Key
- 聊天界面
- 预留浏览器/终端/MCP 控制入口

## 说明

当前为最小可用版本，后续会逐步接入真实 agent、浏览器和 Gateway 控制。

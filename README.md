# PRISM Agent

**统一 AI Agent CLI — 整合 Hermes + Codex + OpenClaw 优势**

```
pip install -e .
prism chat
```

## 核心能力

| 能力 | 说明 |
|---|---|
| 统一模型接口 | 一个命令切换任意模型，自动降级 |
| 多Key轮转 | 凭证池自动轮转，不怕单Key失效 |
| 文件操作 | 读写、补丁、搜索 |
| 终端执行 | Shell命令、后台任务、超时控制 |
| 浏览器控制 | CDP/Playwright（后续扩展） |
| 代码执行 | Python沙箱（后续扩展） |
| MCP服务器 | 原生支持stdio/HTTP（后续扩展） |
| 跨平台Gateway | Telegram/Discord/飞书（后续扩展） |

## 快速开始

```bash
# 安装
cd C:\Users\zd\prism
pip install -e .

# 配置 API Key
prism config set model.api_key sk-xxx

# 启动聊天
prism chat
```

## 项目结构

```
prism/
├── prism/
│   ├── __init__.py
│   ├── cli.py          # CLI入口
│   ├── config.py       # 统一配置
│   ├── agent.py        # Agent核心
│   ├── providers/      # 模型提供商
│   │   └── manager.py
│   ├── tools/          # 工具系统
│   │   └── registry.py
│   ├── gateway/        # 跨平台Gateway（待实现）
│   └── skills/         # Skills系统（待实现）
├── pyproject.toml
└── README.md
```

## 对比

| 特性 | Hermes | Codex CLI | OpenClaw | PRISM |
|---|---|---|---|---|
| 模型无关 | ✅ | ❌ | ❌ | ✅ |
| 自动降级 | ✅ | ❌ | ❌ | ✅ |
| Skills系统 | ✅ | ❌ | ❌ | ✅ |
| 浏览器控制 | ✅ | ❌ | ✅ | 计划 |
| 跨平台Gateway | ✅ | ❌ | ❌ | 计划 |
| 单一CLI | ✅ | ✅ | ❌ | ✅ |

## License

MIT

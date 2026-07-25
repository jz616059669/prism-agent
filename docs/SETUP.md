# PRISM Agent 新手指南

## 项目简介

PRISM Agent 是一个模块化的 AI Agent 框架，支持多提供商、持久记忆、工具调用、浏览器控制、桌面端 UI 和 Gateway 集成。

## 环境要求

- **OS**: Windows 10+ / macOS 12+ / Linux (Ubuntu 22.04+)
- **Python**: 3.11+
- **Node.js**: 18+ (仅桌面端开发需要)
- **Git**: 用于克隆仓库

## 安装步骤

### 1. 克隆仓库

```bash
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
```

### 2. 创建核心 venv

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装核心依赖

```bash
pip install -e .
```

### 4. 安装桌面端依赖（可选）

```bash
cd prism-desktop
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e .
```

### 5. 安装 Playwright 浏览器（可选，用于浏览器工具）

```bash
playwright install chromium
```

## 配置说明

PRISM 有两层配置，优先级：`desktop_settings.json > config.yaml`

### 配置文件位置

- 核心配置：`~/.prism/config.yaml`
- 桌面端配置：`~/.prism/desktop_settings.json`

### 最小配置示例

创建 `~/.prism/config.yaml`：

```yaml
model:
  provider: openai
  base_url: https://api.openai.com/v1
  default: gpt-4o
  api_key: sk-xxx

gateway:
  platforms: []
```

### 桌面端配置

桌面端会读取 `~/.prism/desktop_settings.json` 覆盖核心配置：

```json
{
  "provider": "stepfun",
  "base_url": "https://api.stepfun.com/step_plan/v1",
  "model": "step-3.7-flash",
  "api_key": "your-api-key"
}
```

## 启动方式

### CLI 模式

```bash
cd C:\Users\zd\prism
.venv\Scripts\python.exe -m prism
```

### 桌面端模式

```bash
cd C:\Users\zd\prism\prism-desktop
.venv\Scripts\flet run .
```

### 作为库调用

```python
from prism.agent import create_agent

agent = create_agent()
reply = agent.chat("你好")
print(reply)
```

## 验证安装

```bash
# 1. 核心导入
.venv\Scripts\python.exe -c "from prism.agent import create_agent; print('ok')"

# 2. 桌面端导入
prism-desktop\.venv\Scripts\python.exe -c "from prism_desktop.main import PrismDesktop; print('ok')"

# 3. E2E 验证
.venv\Scripts\python.exe scripts/e2e_verify.py

# 4. 测试套件
.venv\Scripts\python.exe -m pytest tests/ -q
```

## 常见问题

**Q: 桌面端报 `ModuleNotFoundError: flet_desktop`？**  
A: 确保使用桌面端 venv 启动：`prism-desktop/.venv/Scripts/python.exe`

**Q: 浏览器工具报错？**  
A: 运行 `playwright install chromium` 安装浏览器内核

**Q: 如何切换模型提供商？**  
A: 修改 `~/.prism/desktop_settings.json` 中的 `provider`、`base_url`、`model`、`api_key`，然后重启桌面端

**Q: 记忆数据存储在哪里？**  
A: `~/.prism/memory/` 目录下，包括索引、向量和会话数据

**Q: 如何启用 Gateway？**  
A: 在 `~/.prism/config.yaml` 中配置 `gateway.platforms`，例如 `["feishu"]`，然后在桌面端点击"启动"

## 项目结构

```
prism-agent/
├── prism/                    # 核心库
│   ├── agent.py              # Agent 主逻辑
│   ├── config.py             # 配置系统
│   ├── memory.py             # 持久记忆
│   ├── providers/            # 模型提供商适配
│   ├── tools/                # 工具系统
│   ├── gateway/              # Gateway 适配器
│   └── mcp/                  # MCP 协议支持
├── prism-desktop/            # 桌面端 UI
│   └── prism_desktop/
│       ├── main.py           # 主入口
│       ├── chat.py           # 聊天 UI
│       ├── settings.py       # 设置面板
│       └── system.py         # 系统托盘
├── tests/                    # 测试套件
├── scripts/                  # 工具脚本
│   ├── e2e_verify.py         # E2E 验证
│   └── README_e2e_verify.md  # E2E 说明
└── docs/                     # 文档
    ├── CAPABILITIES.md       # 能力清单
    └── SETUP.md              # 本指南
```

## 下一步

- 阅读 `docs/CAPABILITIES.md` 了解已实现的功能
- 运行 `scripts/e2e_verify.py` 验证环境
- 启动桌面端开始对话

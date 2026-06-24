# PRISM Agent

**统一 AI Agent CLI + 桌面客户端 — 整合 Hermes + Codex + OpenClaw 能力**

## 一键安装

**Windows：**
```powershell
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
.\scripts\install.ps1
```

Windows 额外支持：
```powershell
# 打包桌面客户端
.\scripts\build-windows.cmd

# 或手动执行 PowerShell 脚本
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1

# 后台运行 Gateway（NSSM）
nssm install PrismGateway "C:\path\to\prism.exe" "gateway start"
nssm start PrismGateway
```

**macOS：**
```bash
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
bash scripts/install.sh
```

macOS 额外支持：
```bash
# 打包桌面客户端
bash scripts/build-macos.sh

# 安装 launchd 服务（后台运行 Gateway）
cp scripts/com.prism.gateway.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.prism.gateway.plist
launchctl list | grep prism
```

**Linux（Ubuntu/Debian/Fedora/Arch）：**
```bash
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
bash scripts/install.sh
```

Linux 额外支持：
```bash
# 打包桌面客户端
bash scripts/build-linux.sh

# 安装 systemd 服务（后台运行 Gateway）
sudo cp scripts/prism-gateway.service /etc/systemd/system/
sudo systemctl enable prism-gateway
sudo systemctl start prism-gateway
```

安装完成后：
```bash
prism --help           # CLI
prism-desktop          # 桌面客户端
```

## PyPI 安装

```bash
pip install prism-agent
prism --help
prism-desktop
```

> 注意：PyPI 正式包待上传，当前可先通过 `git clone` 或 `pip install .` 使用。

## 手动安装

见 [INSTALL.md](INSTALL.md)

## 当前能力

| 能力 | 状态 | 说明 |
|---|---|---|
| 统一模型接口 | ✅ | 一个命令切换任意模型，自动降级 |
| 多 Key 轮转 | ✅ | 凭证池自动轮转，不怕单 Key 失效 |
| 文件/终端工具 | ✅ | 读写、补丁、shell、后台任务 |
| 浏览器控制 | ✅ | Playwright 驱动，支持导航、快照、点击、输入、截图 |
| 代码执行沙箱 | ✅ | Python 代码执行，支持超时和输出捕获 |
| MCP 客户端 | ✅ | stdio / HTTP 双模式 |
| Skills 系统 | ✅ | 6 个内置 skill，支持安装/移除 |
| Gateway | ✅ | 飞书 / Telegram / Discord 适配器 |
| CLI 子命令 | ✅ | gateway / skill / browser / config / chat / ask / tools |

## 快速开始

```bash
# 查看版本
prism version

# 健康检查
prism doctor

# 列出工具
prism tools

# 列出 skills
prism skill list

# 打开网页
prism browser open https://example.com

# 单次提问
prism ask "用 Python 写一个快速排序"

# 交互聊天
prism chat

# 启动桌面客户端
prism-desktop
```

## Gateway

```bash
# 查看状态
prism gateway status

# 前台运行
prism gateway start --platform telegram --token <TOKEN>
prism gateway start --platform feishu --app-id <ID> --app-secret <SECRET>
prism gateway start --platform wechat --app-id <ID> --app-secret <SECRET>

# Linux 后台运行（systemd）
sudo cp scripts/prism-gateway.service /etc/systemd/system/
sudo systemctl enable prism-gateway
sudo systemctl start prism-gateway
sudo systemctl status prism-gateway

# macOS 后台运行（launchd）
cp scripts/com.prism.gateway.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.prism.gateway.plist
launchctl list | grep prism
```

## 配置

```bash
prism config set model.default step-3.7-flash
prism config get model.default
prism config get
```

### 外部用户首次配置

1. **获取 API Key**
   - StepFun：https://platform.stepfun.com
   - OpenAI：https://platform.openai.com
   - 其他兼容 OpenAI 的提供商

2. **配置模型**
```bash
# 方式1：CLI
prism config set model.provider stepfun
prism config set model.base_url https://api.stepfun.com/step_plan/v1
prism config set model.api_key YOUR_KEY

# 方式2：编辑配置文件
notepad %USERPROFILE%\.prism\config.yaml   # Windows
open ~/.prism/config.yaml                  # macOS/Linux
```

3. **安装桌面端（可选）**
```bash
# pip 安装时自带桌面依赖
pip install prism-agent[desktop]

# 或单独安装
pip install flet
```

4. **验证**
```bash
prism doctor
prism ask "你好"
```

## 本地发布 / 上传 PyPI

### 本地构建
```bash
# 构建分发包
uv run python -m build

# 校验
uv run twine check dist/*
```

产物：
- `dist/prism_agent-0.2.1.tar.gz`
- `dist/prism_agent-0.2.1-py3-none-any.whl`

### 上传到 PyPI
```bash
pip install twine
twine upload dist/*
```

> 需要 PyPI 账号 + token。未配置前可先用 `pip install .` 本地安装。

## 故障排查

- 浏览器失败：`playwright install --force chromium`
- 模型 401/403：检查 `model.api_key` 和 `model.base_url`
- Gateway 失败：检查 token/app_id，查看日志
- 桌面客户端失败：确认 `flet` 已安装，并重装 `prism-desktop`

## 快速诊断

```bash
prism doctor
```

## 开发

```bash
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
pip install -e .
pytest
```

## 路线图

- 飞书 / Telegram / Discord / 微信 真实连接验证
- MCP 服务器连接测试
- Skills 市场 / 一键安装
- 浏览器测试套件完善
- ACP 协议支持

## 本地教程

本地保留的教程不上传 GitHub：
- `INSTALL_FEISHU.md`
- `VIDEO_TUTORIAL.md`

## 贡献

PRISM 仍在快速迭代。欢迎提 issue / PR。

# PRISM Agent

**统一 AI Agent CLI + 桌面客户端 — 整合 Hermes + Codex + OpenClaw 能力**

## 一键安装

**Windows：**
```powershell
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
.\scripts\install.ps1
```

**macOS：**
```bash
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
bash scripts/install.sh
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

# Linux 后台运行（systemd）
sudo cp scripts/prism-gateway.service /etc/systemd/system/
sudo systemctl enable prism-gateway
sudo systemctl start prism-gateway
sudo systemctl status prism-gateway
```

## 配置

```bash
prism config set model.default step-3.7-flash
prism config get model.default
prism config get
```

## 开发

```bash
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
pip install -e .
pytest
```

## 路线图

- 飞书 / Telegram / Discord 真实连接验证
- MCP 服务器连接测试
- Skills 市场 / 一键安装
- 浏览器测试套件完善
- ACP 协议支持

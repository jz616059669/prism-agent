# PRISM Agent 安装使用说明

**统一 AI Agent CLI + 桌面客户端 — 整合 Hermes + Codex + OpenClaw 能力**

- 仓库：https://github.com/jz616059669/prism-agent
- 当前版本：v0.2.2
- 适用系统：Windows 10/11、macOS、Linux
- Python：3.11+ 推荐

---

## 1. 环境准备

### 1.1 所有平台通用

- Python 3.11 或更高版本
- Git
- 网络访问（GitHub、模型 API）

### 1.2 Windows

```powershell
# 检查 Python
python --version

# 如未安装，从 https://www.python.org/downloads/windows/ 下载安装
# 安装时勾选 "Add Python to PATH"
```

### 1.3 macOS

```bash
# 检查 Python
python3 --version

# 如未安装
brew install python@3.11
```

### 1.4 Linux

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install python3.11 python3.11-venv git

# Fedora
sudo dnf install python3.11 git

# Arch
sudo pacman -S python git
```

---

## 2. 安装方式

### 方式一：一键脚本安装（推荐）

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

# 验证打包结果
ls dist-windows\

# 查看产物大小
du -sh dist-windows\*

# 验证主程序可运行
.\dist-windows\prism-desktop.exe --help
.\dist-windows\prism.exe --help
```

> 如打包失败，请检查：
> 1. `flet` 是否已安装：`pip install flet`
> 2. 是否在项目根目录执行
> 3. 网络是否可访问（下载 Flet 依赖需要）

**macOS / Linux：**
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
sudo systemctl status prism-gateway
```

安装完成后：
```bash
prism --help           # CLI
prism-desktop          # 桌面客户端
```

### 方式二：PyPI 安装（普通用户推荐）

```bash
pip install prism-agent
prism --help
prism-desktop
```

> PyPI 地址：https://pypi.org/project/prism-agent/0.2.2/

### 方式三：源码安装（开发者推荐）

```bash
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
pip install -e .
playwright install chromium
```

验证安装：
```bash
prism --help
prism version
```

---

## 3. 配置说明

### 3.1 配置文件位置

- Windows：`%USERPROFILE%\.prism\config.yaml`
- macOS/Linux：`~/.prism/config.yaml`

### 3.2 最小配置

```yaml
model:
  default: step-3.7-flash
  provider: stepfun
  base_url: https://api.stepfun.com/step_plan/v1
  api_key: YOUR_API_KEY
```

### 3.3 完整配置示例

```yaml
model:
  default: step-3.7-flash
  provider: stepfun
  base_url: https://api.stepfun.com/step_plan/v1
  api_key: YOUR_API_KEY
  context_length: 128000
  max_tokens: 4096

fallback:
  enabled: true
  chain:
    - stepfun/step-3.7-flash
    - openai/gpt-4o

gateway:
  enabled: false
  platforms: []

mcp:
  auto_discover: true
  servers: []

skills:
  auto_update: true
```

### 3.4 通过命令配置

```bash
# 设置模型
prism config set model.default step-3.7-flash
prism config set model.provider stepfun
prism config set model.base_url https://api.stepfun.com/step_plan/v1

# 查看配置
prism config get model.default
prism config get
```

---

## 4. 所有命令

### 4.1 基础命令

```bash
# 查看版本
prism version

# 查看帮助
prism --help

# 健康检查
prism doctor

# 列出工具
prism tools
```

### 4.2 会话命令

```bash
# 列出已保存会话
prism session list

# 保存当前会话
prism session save 会话名称

# 加载会话
prism session load 会话名称

# 删除会话
prism session delete 会话名称
```

### 4.3 模型调用

```bash
# 单次提问
prism ask "用 Python 写一个快速排序"

# 交互聊天
prism chat
```

### 4.4 浏览器控制

```bash
# 打开网页
prism browser open https://example.com

# 获取页面快照
prism browser snapshot

# 关闭浏览器
prism browser close
```

### 4.5 Skills 管理

```bash
# 列出已安装 skills
prism skill list

# 搜索 skills
prism skill search 文件

# 安装 skill
prism skill install <名称或本地路径>

# 移除 skill
prism skill remove <名称>

# 浏览远程 hub
prism skill browse
```

### 4.6 Gateway 命令

```bash
# 查看状态
prism gateway status

# 启动平台（示例）
prism gateway start --platform telegram --token <TOKEN>
prism gateway start --platform feishu --app-id <ID> --app-secret <SECRET>
prism gateway start --platform feishu --webhook --host 127.0.0.1 --port 9000

# 停止平台
prism gateway stop <platform>
```

**Windows 后台运行 Gateway（NSSM）：**
```powershell
nssm install PrismGateway "C:\path\to\prism.exe" "gateway start --platform <platform>"
nssm start PrismGateway
nssm status PrismGateway
```

**macOS 后台运行 Gateway（launchd）：**
```bash
cp scripts/com.prism.gateway.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.prism.gateway.plist
launchctl list | grep prism
```

**Linux 后台运行 Gateway（systemd）：**
```bash
sudo cp scripts/prism-gateway.service /etc/systemd/system/
sudo systemctl enable prism-gateway
sudo systemctl start prism-gateway
sudo systemctl status prism-gateway
```

### 4.7 配置命令

```bash
# 设置配置
prism config set model.default step-3.7-flash

# 查看配置
prism config get model.default

# 查看全部配置
prism config get
```

### 4.8 ACP 命令

```bash
# 运行外部 ACP agent
prism acp run --command <命令>
```

---

## 5. 桌面客户端功能

### 5.1 启动

```bash
prism-desktop
```

### 5.2 主要功能

- 侧边栏配置模型、提供商、API Key
- 聊天界面
- 浏览器/终端/MCP 控制入口
- 主题切换
- 右键菜单：打开配置目录、打开终端、关于
- Skills 安装入口
- 会话保存/加载 UI
- 托盘最小化

### 5.3 会话持久化

会话保存在本地：

- Windows：`%USERPROFILE%\.prism\sessions\`
- macOS/Linux：`~/.prism/sessions/`

```bash
# 查看已保存会话
prism session list

# 保存当前会话
prism session save 会话名称

# 加载会话
prism session load 会话名称

# 删除会话
prism session delete 会话名称
```

桌面端侧边栏也提供会话保存/加载按钮。

---

## 6. 常见问题

**Q: 支持哪些模型？**

A: 当前支持所有兼容 OpenAI 格式的 API，包括：
- StepFun：step-3.7-flash
- OpenAI：gpt-4o、gpt-4o-mini
- Anthropic：claude-sonnet-4
- 其他 OpenAI 兼容服务

**Q: 桌面客户端和 CLI 有什么区别？**

A: 功能相同，桌面客户端提供图形界面，适合不熟悉命令行的用户。CLI 适合自动化和脚本使用。

**Q: 会话保存在哪里？**

A: 会话保存在本地 `~/.prism/sessions/`。

**Q: 如何备份配置？**

A: 直接备份 `~/.prism/` 目录即可：

```bash
# 备份
cp -r ~/.prism ~/.prism.backup

# 恢复
cp -r ~/.prism.backup ~/.prism
```

**Q: 如何更新 PRISM？**

A:

```bash
cd prism-agent
git pull origin master
pip install -e . --upgrade
```

**Q: 浏览器相关**

A: 如 `prism browser open` 失败，执行：
```bash
playwright install --force chromium
```

**Q: 模型调用失败，返回 401/403**

A:
- 检查 `~/.prism/config.yaml` 中的 `model.api_key`
- 检查 `model.base_url` 是否正确
- 确认 API Key 有效且有余额

**Q: Gateway 启动失败**

A:
- 检查平台 token/app_id 配置
- 查看日志
- 确认网络可达

**Q: 桌面客户端启动失败**

A:
- 确认 `flet` 已安装：`pip show flet`
- 重新安装桌面客户端：
  ```bash
  cd prism-desktop
  uv tool install -e .
  ```

---

## 7. 开发

### 7.1 克隆仓库

```bash
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
```

### 7.2 安装开发依赖

```bash
pip install -e .
uv add --dev pytest
playwright install chromium
```

### 7.3 运行测试

```bash
uv run pytest tests/ -q
```

### 7.4 提交代码

```bash
git add -A
git commit -m "feat: ..."
git push origin master
```

---

## 8. 日志位置

- Windows：`%USERPROFILE%\.prism\logs\prism.log`
- macOS/Linux：`~/.prism/logs/prism.log`

---

## 9. 联系与反馈

- GitHub Issues：https://github.com/jz616059669/prism-agent/issues
- 仓库地址：https://github.com/jz616059669/prism-agent

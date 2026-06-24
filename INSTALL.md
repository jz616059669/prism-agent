# PRISM Agent 安装使用说明

**统一 AI Agent CLI + 桌面客户端 — 整合 Hermes + Codex + OpenClaw 能力**

- 仓库：https://github.com/jz616059669/prism-agent
- 当前版本：v0.2.1
- 适用系统：Windows 10/11、macOS、Linux
- Python：3.11+ 推荐

---

## 1. 环境准备

### 所有平台通用

- Python 3.11 或更高版本
- Git
- 网络访问（GitHub、模型 API）

### Windows

```powershell
# 检查 Python
python --version

# 如未安装，从 https://www.python.org/downloads/windows/ 下载安装
# 安装时勾选 "Add Python to PATH"
```

### macOS

```bash
# 检查 Python
python3 --version

# 如未安装
brew install python@3.11
```

### Linux

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

## 2. 快速安装

### Windows

```powershell
# 克隆仓库
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent

# 一键安装
.\scripts\install.ps1
```

### macOS / Linux

```bash
# 克隆仓库
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent

# 一键安装
bash scripts/install.sh
```

一键安装脚本会自动完成：
1. 安装 PRISM CLI
2. 安装 Playwright + Chromium 浏览器引擎
3. 初始化配置文件 `~/.prism/config.yaml`
4. 安装桌面客户端 `prism-desktop`

### 2.3 PyPI 安装

```bash
pip install prism-agent
prism --help
prism-desktop
```

---

## 3. 手动安装

如果一键脚本失败，可按以下步骤手动安装：

### 3.1 安装 PRISM CLI

```bash
pip install -e .
```

验证安装：

```bash
prism --help
prism version
```

### 3.2 安装浏览器引擎

```bash
playwright install chromium
```

验证：

```bash
prism browser open https://example.com
prism browser close
```

### 3.3 安装桌面客户端

```bash
cd prism-desktop
uv tool install -e .
cd ..
```

验证：

```bash
prism-desktop --help
```

---

## 4. 配置说明

### 4.1 配置文件位置

- Windows：`%USERPROFILE%\.prism\config.yaml`
- macOS/Linux：`~/.prism/config.yaml`

### 4.2 最小配置

```yaml
model:
  default: step-3.7-flash
  provider: stepfun
  base_url: https://api.stepfun.com/step_plan/v1
  api_key: YOUR_API_KEY
```

### 4.3 完整配置示例

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

### 4.4 通过命令配置

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

## 5. 验证安装

```bash
# 查看版本
prism version

# 查看帮助
prism --help

# 列出工具
prism tools

# 列出技能
prism skill list

# 查看 Gateway 状态
prism gateway status

# 运行测试
uv run pytest tests/ -q
```

---

## 6. 基本使用

### 6.1 CLI 命令

```bash
# 单次提问
prism ask "用 Python 写一个快速排序"

# 交互聊天
prism chat

# 查看工具列表
prism tools

# 浏览器控制
prism browser open https://example.com
prism browser close
```

### 6.2 桌面客户端

```bash
# 启动桌面客户端
prism-desktop
```

桌面客户端功能：
- 侧边栏配置模型、提供商、API Key
- 聊天界面
- 浏览器/终端/MCP 控制入口（后续版本）

### 6.3 浏览器控制

```bash
# 打开网页
prism browser open https://example.com

# 获取页面快照
prism browser snapshot

# 关闭浏览器
prism browser close
```

---

## 7. 进阶使用

### 7.1 MCP 服务器配置

创建 `~/.prism/mcp.json`：

```json
{
  "filesystem": {
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/folder"],
    "enabled": true
  }
}
```

### 7.2 环境变量

```bash
# Windows PowerShell
$env:STEPFUN_API_KEY = "your-api-key"

# bash/zsh
export STEPFUN_API_KEY="your-api-key"

# 永久添加到 ~/.bashrc 或 ~/.zshrc
echo 'export STEPFUN_API_KEY="your-api-key"' >> ~/.bashrc
```

### 7.3 Gateway 配置

```bash
# 前台运行
prism gateway start --platform telegram --token <TOKEN>
prism gateway start --platform feishu --app-id <ID> --app-secret <SECRET>
```

---

## 8. 平台特有功能

### 8.1 Linux

#### 打包桌面客户端

```bash
bash scripts/build-linux.sh
```

#### 后台运行 Gateway（systemd）

```bash
sudo cp scripts/prism-gateway.service /etc/systemd/system/
sudo systemctl enable prism-gateway
sudo systemctl start prism-gateway
sudo systemctl status prism-gateway
```

查看日志：

```bash
sudo journalctl -u prism-gateway -f
```

### 8.2 macOS

#### 打包桌面客户端

```bash
bash scripts/build-macos.sh
```

#### 后台运行 Gateway（launchd）

```bash
cp scripts/com.prism.gateway.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.prism.gateway.plist
launchctl list | grep prism
```

查看日志：

```bash
tail -f /usr/local/var/prism/gateway.log
```

### 8.3 Windows

Windows 后台运行 Gateway 可通过任务计划程序或 NSSM 实现：

```powershell
# 使用 NSSM 安装服务
nssm install PrismGateway "C:\path\to\prism.exe" "gateway start"
nssm start PrismGateway
```

---

## 9. 故障排查

### 9.1 浏览器相关

- **问题**：`prism browser open` 失败
- **解决**：
  ```bash
  playwright install --force chromium
  ```

### 9.2 模型调用相关

- **问题**：模型调用失败，返回 401/403
- **解决**：
  - 检查 `~/.prism/config.yaml` 中的 `model.api_key`
  - 检查 `model.base_url` 是否正确
  - 确认 API Key 有效且有余额

### 9.3 Gateway 相关

- **问题**：Gateway 启动失败
- **解决**：
  - 检查平台 token/app_id 配置
  - 查看日志：Linux `journalctl`，macOS `tail /usr/local/var/prism/gateway.log`
  - 确认网络可达

### 9.4 桌面客户端相关

- **问题**：`prism-desktop` 启动失败
- **解决**：
  - 确认 `flet` 已安装：`pip show flet`
  - 重新安装桌面客户端：
    ```bash
    cd prism-desktop
    uv tool install -e .
    ```

---

## 10. 开发

### 10.1 克隆仓库

```bash
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
```

### 10.2 安装开发依赖

```bash
pip install -e .
uv add --dev pytest
playwright install chromium
```

### 10.3 运行测试

```bash
uv run pytest tests/ -q
```

### 10.4 提交代码

```bash
git add -A
git commit -m "feat: ..."
git push origin master
```

---

## 11. 常见问题

**Q: 支持哪些模型？**

A: 当前支持所有兼容 OpenAI 格式的 API，包括：
- StepFun：step-3.7-flash
- OpenAI：gpt-4o、gpt-4o-mini
- Anthropic：claude-sonnet-4
- 其他 OpenAI 兼容服务

**Q: 桌面客户端和 CLI 有什么区别？**

A: 功能相同，桌面客户端提供图形界面，适合不熟悉命令行的用户。CLI 适合自动化和脚本使用。

**Q: 会话保存在哪里？**

A: 会话保存在本地：

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

---

## 12. 获取帮助

- 项目仓库：https://github.com/jz616059669/prism-agent
- 问题反馈：https://github.com/jz616059669/prism-agent/issues

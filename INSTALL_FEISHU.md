# PRISM Agent 飞书安装教程

> **项目仓库**：https://github.com/jz616059669/prism-agent
> **适用系统**：Windows 10/11、macOS、Linux
> **Python**：3.11+ 推荐

---

## 一、环境准备

### 所有平台通用

- Python 3.11 或更高版本
- Git
- 网络访问（GitHub、模型 API）

### Windows

```powershell
# 检查 Python 是否安装
python --version

# 如未安装，请访问 https://www.python.org/downloads/windows/
# 安装时务必勾选 "Add Python to PATH"
```

### macOS

```bash
# 检查 Python
python3 --version

# 如未安装，使用 Homebrew 安装
brew install python@3.11
```

### Linux

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install python3.11 python3.11-venv git

# Fedora
sudo dnf install python3.11 git

# Arch Linux
sudo pacman -S python git
```

---

## 二、快速安装

### Windows 用户

```powershell
# 1. 克隆仓库
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent

# 2. 一键安装
.\scripts\install.ps1
```

### macOS / Linux 用户

```bash
# 1. 克隆仓库
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent

# 2. 一键安装
bash scripts/install.sh
```

**一键安装会自动完成以下 4 步：**
1. 安装 PRISM CLI
2. 安装 Playwright + Chromium 浏览器引擎
3. 初始化配置文件 `~/.prism/config.yaml`
4. 安装桌面客户端 `prism-desktop`

---

## 三、手动安装（如一键脚本失败）

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

## 四、配置说明

### 4.1 配置文件位置

| 平台 | 配置文件路径 |
|---|---|
| Windows | `%USERPROFILE%\.prism\config.yaml` |
| macOS | `~/.prism/config.yaml` |
| Linux | `~/.prism/config.yaml` |

### 4.2 最小配置示例

```yaml
model:
  default: step-3.7-flash
  provider: stepfun
  base_url: https://api.stepfun.com/step_plan/v1
  api_key: YOUR_API_KEY
```

### 4.3 通过命令配置（推荐）

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

## 五、验证安装

执行以下命令，确认安装成功：

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

## 六、基本使用

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

## 七、平台特有功能

### 7.1 Linux

```bash
# 打包桌面客户端
bash scripts/build-linux.sh

# 后台运行 Gateway（systemd）
sudo cp scripts/prism-gateway.service /etc/systemd/system/
sudo systemctl enable prism-gateway
sudo systemctl start prism-gateway
sudo systemctl status prism-gateway
```

### 7.2 macOS

```bash
# 打包桌面客户端
bash scripts/build-macos.sh

# 后台运行 Gateway（launchd）
cp scripts/com.prism.gateway.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.prism.gateway.plist
launchctl list | grep prism
```

### 7.3 Windows

Windows 后台运行 Gateway 可通过任务计划程序或 NSSM 实现：

```powershell
# 使用 NSSM 安装服务
nssm install PrismGateway "C:\path\to\prism.exe" "gateway start"
nssm start PrismGateway
```

---

## 八、故障排查

### 8.1 浏览器相关

**问题**：`prism browser open` 失败
**解决**：
```bash
playwright install --force chromium
```

### 8.2 模型调用相关

**问题**：模型调用失败，返回 401/403
**解决**：
- 检查 `~/.prism/config.yaml` 中的 `model.api_key`
- 检查 `model.base_url` 是否正确
- 确认 API Key 有效且有余额

### 8.3 Gateway 相关

**问题**：Gateway 启动失败
**解决**：
- 检查平台 token/app_id 配置
- 查看日志：Linux 用 `journalctl`，macOS 用 `tail /usr/local/var/prism/gateway.log`
- 确认网络可达

### 8.4 桌面客户端相关

**问题**：`prism-desktop` 启动失败
**解决**：
- 确认 `flet` 已安装：`pip show flet`
- 重新安装桌面客户端：
  ```bash
  cd prism-desktop
  uv tool install -e .
  ```

---

## 九、获取帮助

- **项目仓库**：https://github.com/jz616059669/prism-agent
- **问题反馈**：https://github.com/jz616059669/prism-agent/issues
- **安装文档**：见项目根目录 `INSTALL.md`

---

## 十、快速参考卡

| 命令 | 说明 |
|---|---|
| `prism --help` | 查看帮助 |
| `prism version` | 查看版本 |
| `prism tools` | 列出可用工具 |
| `prism skill list` | 列出已安装技能 |
| `prism ask "问题"` | 单次提问 |
| `prism chat` | 交互聊天 |
| `prism browser open <url>` | 打开网页 |
| `prism browser close` | 关闭浏览器 |
| `prism config set <key> <value>` | 设置配置 |
| `prism config get <key>` | 查看配置 |
| `prism gateway status` | 查看 Gateway 状态 |
| `prism-desktop` | 启动桌面客户端 |

---

**提示**：首次使用请先配置 API Key，否则模型调用会失败。配置方法见第四节。

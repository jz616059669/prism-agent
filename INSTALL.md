# PRISM Agent 安装使用说明

**统一 AI Agent CLI + 桌面客户端 — 整合 Hermes + Codex + OpenClaw 能力**

- 仓库：https://github.com/jz616059669/prism-agent
- 当前版本：v0.1.0
- 适用系统：Windows 10/11、macOS、Linux
- Python：3.11+ 推荐

## 1. 克隆项目

```bash
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
```

## 2. 一键安装

**Windows：**
```powershell
.\scripts\install.ps1
```

**macOS：**
```bash
bash scripts/install.sh
```

**Linux：**
```bash
bash scripts/install.sh
```

一键安装会自动完成：
- 安装 PRISM CLI
- 安装 Playwright + Chromium
- 初始化 `~/.prism/config.yaml`
- 安装桌面客户端 `prism-desktop`

## 3. 手动安装

如一键脚本失败，可手动执行：

```bash
# 安装 CLI
pip install -e .

# 安装浏览器引擎
playwright install chromium

# 初始化配置
mkdir -p ~/.prism
cp config.example.yaml ~/.prism/config.yaml

# 安装桌面客户端
cd prism-desktop
uv tool install -e .
cd ..
```

## 4. 配置说明

编辑 `~/.prism/config.yaml`，至少填写：

```yaml
model:
  default: step-3.7-flash
  provider: stepfun
  base_url: https://api.stepfun.com/step_plan/v1
  api_key: YOUR_API_KEY

gateway:
  telegram:
    token: ""
  feishu:
    app_id: ""
    app_secret: ""
```

也可通过命令配置：

```bash
prism config set model.default step-3.7-flash
prism config set model.provider stepfun
prism config set model.base_url https://api.stepfun.com/step_plan/v1
prism config get model.default
```

## 5. 验证安装

```bash
prism --help
prism version
prism tools
prism skill list
prism gateway status
```

运行测试：

```bash
uv run pytest tests/ -q
```

## 6. 基本使用

### 查看帮助

```bash
prism --help
prism tools
prism browser --help
prism config --help
```

### 列出可用工具

```bash
prism tools
```

### 浏览器控制

```bash
prism browser open https://example.com
prism browser close
```

### 配置管理

```bash
prism config set model.default step-3.7-flash
prism config get model.default
```

### 启动桌面客户端

```bash
prism-desktop
```

## 7. 进阶使用

### MCP 服务器配置

创建 `~/.prism/mcp.json`：

```json
{
  "filesystem": {
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/zd"],
    "enabled": true
  }
}
```

### 环境变量

```bash
# Windows PowerShell
$env:STEPFUN_API_KEY = "your-key"

# bash
export STEPFUN_API_KEY="your-key"
```

## 8. 平台特有功能

### Linux

```bash
# 打包桌面客户端
bash scripts/build-linux.sh

# 安装 systemd 服务（后台运行 Gateway）
sudo cp scripts/prism-gateway.service /etc/systemd/system/
sudo systemctl enable prism-gateway
sudo systemctl start prism-gateway
sudo systemctl status prism-gateway
```

### macOS

```bash
# 打包桌面客户端
bash scripts/build-macos.sh

# 安装 launchd 服务（后台运行 Gateway）
cp scripts/com.prism.gateway.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.prism.gateway.plist
launchctl list | grep prism
```

## 9. 故障排查

- 浏览器测试失败：确认 `playwright install chromium` 成功
- 模型调用失败：检查 `~/.prism/config.yaml` 的 `model.api_key` 和 `base_url`
- Gateway 连接失败：检查平台 token/app_id 配置
- 桌面客户端启动失败：确认 `flet` 已安装，`prism-desktop` 命令可用

## 10. 开发

```bash
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
pip install -e .
uv add --dev pytest
uv run pytest tests/ -q
```

提交代码：

```bash
git add -A
git commit -m "feat: ..."
git push origin master
```

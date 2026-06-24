# PRISM Agent 安装使用说明

**统一 AI Agent CLI — 整合 Hermes + Codex + OpenClaw 能力**

- 仓库：https://github.com/jz616059669/prism-agent
- 当前版本：v0.1.0
- 适用系统：Windows 10/11、macOS、Linux
- Python：3.11+ 推荐

## 1. 克隆项目

```bash
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
```

## 2. 安装依赖

推荐使用 `uv` 安装：

```bash
uv sync
```

安装浏览器引擎：

```bash
uv run playwright install chromium
```

## 3. 配置说明

推荐直接复制示例配置：

```bash
cp config.example.yaml ~/.prism/config.yaml
```

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

## 4. 验证安装

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

## 5. 基本使用

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

## 6. 进阶使用

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

## 7. 故障排查

- 浏览器测试失败：确认 `playwright install chromium` 成功
- 模型调用失败：检查 `~/.prism/config.yaml` 的 `model.api_key` 和 `base_url`
- Gateway 连接失败：检查平台 token/app_id 配置

## 8. 开发

```bash
uv add --dev pytest
uv run pytest tests/ -q
```

提交代码：

```bash
git add -A
git commit -m "feat: ..."
git push origin master
```

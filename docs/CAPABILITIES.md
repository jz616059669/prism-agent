# PRISM Agent 可交付能力清单 (v2.1.6)

## 已可用 ✅

### 核心 Agent 链路
- [x] 配置系统：`desktop_settings.json > config.yaml`，支持热重载
- [x] 多提供商适配：OpenAI / StepFun / 自定义 endpoint
- [x] Agent 创建与对话：`create_agent()` → `agent.chat()`
- [x] 流式输出：桌面端支持逐 token 显示
- [x] 自动规划：复杂任务拆解为 2-5 步执行
- [x] 自我校验：回复质量检查 + 修正
- [x] 前置澄清：模糊输入追问

### 记忆系统
- [x] 持久记忆：`PersistentMemory` 读写 + 语义召回
- [x] 动态注入：system prompt 自动注入相关记忆
- [x] 记忆去重：digest 相似度防重复
- [x] 多 scope：default / session / user_profile
- [x] 记忆压缩：`_summarize_messages` 自动压缩

### 工具系统
- [x] 浏览器控制：Playwright 异步 + 同步封装
- [x] 代码执行：sandbox 安全执行 Python
- [x] 终端工具：`TerminalTool` 统一封装
- [x] 多模态：图片描述 / 图片转 base64 / 语音转写 / TTS
- [x] Gateway 管理：启动/停止/状态查询

### 桌面端 (Flet)
- [x] 跨平台 UI：Windows / macOS / Linux
- [x] 系统托盘：最小化到托盘 + 右键菜单
- [x] 会话管理：创建 / 切换 / 重命名 / 删除 / 导出 / 压缩
- [x] 实时统计：调用次数 / 成功率 / 延迟 / Token / 成本
- [x] 主题切换：亮色 / 暗色 / 跟随系统
- [x] 角色人格：多 persona 独立记忆 + 系统提示词
- [x] 后台复盘：自动 review 对话质量
- [x] 配置同步：`desktop_settings.json` 覆盖 `config.yaml`

### Gateway 集成
- [x] 飞书 WebSocket：已配置并运行
- [x] Telegram Bot：polling / webhook
- [x] Discord Bot：gateway adapter
- [x] 企业微信：cli 集成
- [x] 统一 GatewayRegistry：懒加载单例

### 安全与鲁棒性
- [x] 危险命令拦截：rm -rf / format / shutdown 等
- [x] Sandbox 隔离：白名单模块 + 禁用危险 builtins
- [x] 工具去重：近期相同调用自动跳过
- [x] MCP stdio init 严格模式：握手成功才标记 initialized
- [x] 熔断器：连续失败阈值后短暂跳过
- [x] 日志脱敏：Sensitive key 自动掩码

## 可选 / 待增强 ⚙️

### 稳定性
- [ ] 浏览器无网时语义降级（当前 skip，可改为本地 fixture）
- [ ] 全部 `_run_on_ui` 统一到 Flet loop-compatible 写法
- [ ] config watcher 在 pytest 下完全静默（已修复大部分）

### 功能增强
- [ ] RAG 本地知识库：代码已支持，需用户配置索引目录
- [ ] 插件市场：外部 skill 热加载
- [ ] 工作流可视化：YAML → 图形化编辑
- [ ] Webhook 触发器：外部事件 → Agent 执行
- [ ] 定时任务 cron：已支持，需 UI 配置入口

### 性能
- [ ] 记忆召回缓存：减少重复 search
- [ ] 大上下文压缩：`max_messages` 自动截断优化
- [ ] Token 估算：成本计算精度提升

## 测试覆盖

### 已通过测试
- [x] `tests/test_real_model.py`：provider 无 key 场景
- [x] `tests/test_integration.py`：config → agent → browser
- [x] `tests/test_browser.py`：open / snapshot / screenshot / navigation
- [x] `tests/test_gateway.py`：adapter 基础逻辑
- [x] E2E 脚本：`scripts/e2e_verify.py`

### 测试策略
- 网络依赖测试：无网时自动 skip / 切本地 fixture
- 假 key 测试：断言 error 非空，不依赖英文/中文文案
- 浏览器测试：Playwright 连接错误后自动 disconnect

## 当前版本

- **核心库**: `2.1.6`
- **桌面端**: `2.1.6`
- **最新提交**: `73c6544`
- **CI 状态**: GitHub Actions 通过

## 快速验证

```bash
# 1. 核心导入
cd C:\Users\zd\prism
.venv\Scripts\python.exe -c "from prism.agent import create_agent; print('ok')"

# 2. 桌面端导入
prism-desktop\.venv\Scripts\python.exe -c "from prism_desktop.main import PrismDesktop; print('ok')"

# 3. E2E 验证
.venv\Scripts\python.exe scripts/e2e_verify.py --question "你好"

# 4. 测试套件
.venv\Scripts\python.exe -m pytest tests/ -q
```

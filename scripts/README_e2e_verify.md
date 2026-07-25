# PRISM Agent E2E 验证脚本

`scripts/e2e_verify.py` 用于在本地快速验证 PRISM Agent 的核心链路是否可用。

## 验证链路

```
读取 desktop_settings.json
    → 注入 prism.config
    → 创建 Agent
    → 写入/读取 PersistentMemory
    → 真实调用模型
    → 校验返回结果
```

## 前置要求

- Python 3.11+
- PRISM 核心 venv：`C:\Users\zd\prism\.venv`
- 配置文件：`C:\Users\zd\.prism\desktop_settings.json`
- 模型提供商已配置有效的 `api_key` / `base_url` / `model`

## 快速开始

```bash
cd C:\Users\zd\prism
.venv\Scripts\python.exe scripts/e2e_verify.py
```

默认问题：`请用一句话回复：请只回复 E2E_OK。`

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--settings` | `desktop_settings.json` 路径 | `~/.prism/desktop_settings.json` |
| `--question` | 发送给 Agent 的问题 | `请用一句话回复：请只回复 E2E_OK。` |
| `--quiet` | 抑制 stdout，仅写入日志 | `False` |
| `--log-path` | 日志文件路径 | `<repo>/e2e_verify.log` |

## 示例

```bash
# 基础验证
.venv\Scripts\python.exe scripts/e2e_verify.py

# 自定义问题
.venv\Scripts\python.exe scripts/e2e_verify.py --question "你好，请简单回复"

# 静默模式（仅写日志）
.venv\Scripts\python.exe scripts/e2e_verify.py --quiet --log-path C:\tmp\e2e.log

# 指定其他配置文件
.venv\Scripts\python.exe scripts/e2e_verify.py --settings D:\prism\desktop_settings.json
```

## 作为模块调用

```python
from scripts.e2e_verify import run

exit_code = run(
    settings_path=r"C:\Users\zd\.prism\desktop_settings.json",
    question="请只回复 E2E_OK。",
    quiet=False,
)
```

## 日志说明

日志会同时输出到 stdout 和 `e2e_verify.log`。敏感信息（如 `api_key`）会自动脱敏：

```
[21:01:05] desktop_settings={'provider': 'stepfun', 'model': 'step****lash', 'base_url': 'http****n/v1', 'api_key': '6u7l****rh8W'}
[21:01:39] agent created memory_scope=default
[21:01:44] chat result type=str len=6 time=5.54s
[21:01:44] E2E verification passed
```

## 常见问题

**Q: 返回空结果或报错？**  
A: 检查 `desktop_settings.json` 里的 `provider` / `base_url` / `api_key` / `model` 是否正确。StepFun 的 `base_url` 必须是 `https://api.stepfun.com/step_plan/v1`。

**Q: 内存 warmup 报 `importance` 参数错误？**  
A: 这是已知的非关键警告，不影响验证。当前 `PersistentMemory.remember()` 不支持 `importance` 参数，脚本已忽略该警告。

**Q: 如何在 CI 中使用？**  
A: 建议配合 `--quiet` 使用，并通过退出码判断结果：`0` 成功，`2` 配置缺失，`3` 模型返回空，`4` 未预期错误。

## 退出码

| 退出码 | 含义 |
|--------|------|
| `0` | 验证通过 |
| `2` | 配置文件缺失或解析失败 |
| `3` | Agent 返回空结果 |
| `4` | 未预期的异常 |

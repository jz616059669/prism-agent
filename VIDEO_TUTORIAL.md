# PRISM Agent 视频教程脚本

**视频标题**：PRISM Agent 安装与使用全流程教程
**时长**：约 8-10 分钟
**适合平台**：Bilibili / YouTube / 飞书
**录制方式**：屏幕录制 + 旁白 + 字幕

---

## 视频脚本总览

| 序号 | 章节 | 时长 | 画面 | 旁白 |
|---|---|---|---|---|
| 1 | 开场介绍 | 0:30 | 项目主页 + 三端截图 | 介绍 PRISM 是什么 |
| 2 | 环境准备 | 1:00 | 终端检查 Python/Git | 各平台环境检查 |
| 3 | Windows 安装 | 1:30 | Windows 终端操作 | 克隆仓库 + 一键安装 |
| 4 | macOS 安装 | 1:00 | macOS 终端操作 | 克隆仓库 + 一键安装 |
| 5 | Linux 安装 | 1:00 | Linux 终端操作 | 克隆仓库 + 一键安装 |
| 6 | 配置说明 | 1:30 | 编辑器打开 config.yaml | 填写 API Key |
| 7 | 验证安装 | 1:00 | 终端运行 prism 命令 | 验证 CLI + 桌面客户端 |
| 8 | 基本使用 | 1:30 | 实际演示 chat/browser | 演示核心功能 |
| 9 | 平台特有功能 | 1:00 | systemd/launchd 配置 | Linux/macOS 后台服务 |
| 10 | 故障排查 | 0:30 | 错误场景 + 解决 | 常见问题快速解决 |
| 11 | 总结 | 0:30 | 项目主页 + 感谢 | 总结 + 社区链接 |

---

## 详细分镜脚本

### 第1章：开场介绍（0:00 - 0:30）

**画面**：
- 0:00-0:05：黑屏 + PRISM Agent Logo（可做简单动画）
- 0:05-0:15：展示项目主页 https://github.com/jz616059669/prism-agent
- 0:15-0:25：三端界面快速切换：Windows PowerShell、macOS Terminal、Linux Terminal
- 0:25-0:30：桌面客户端界面截图

**旁白**：
> "大家好，今天给大家介绍 PRISM Agent —— 一个整合了 Hermes、Codex、OpenClaw 优势的统一 AI Agent 平台。它支持 Windows、macOS、Linux 三端，提供命令行和桌面客户端两种使用方式。这个视频将手把手教你从零安装到上手使用。"

**字幕**：
```
PRISM Agent 安装与使用全流程教程
统一 AI Agent CLI + 桌面客户端
```

---

### 第2章：环境准备（0:30 - 1:30）

**画面**：
- 0:30-0:45（Windows）：PowerShell 输入 `python --version` 和 `git --version`
- 0:45-1:00（macOS）：Terminal 输入 `python3 --version` 和 `git --version`
- 1:00-1:15（Linux）：Terminal 输入 `python3 --version` 和 `git --version`
- 1:15-1:30：显示各平台安装链接

**旁白**：
> "在开始之前，请确保你的电脑已经安装了 Python 3.11 或更高版本，以及 Git。Windows 用户可以在 python.org 下载安装，记得勾选 Add Python to PATH。macOS 用户可以使用 Homebrew 安装。Linux 用户使用系统包管理器即可。如果你已经有这些环境，可以直接跳到下一节。"

**字幕**：
```
环境要求：Python 3.11+、Git
```

---

### 第3章：Windows 安装（1:30 - 3:00）

**画面**：
- 1:30-1:40：PowerShell 输入 `git clone https://github.com/jz616059669/prism-agent.git`
- 1:40-1:50：`cd prism-agent`
- 1:50-2:10：运行 `.\scripts\install.ps1`，展示安装过程
- 2:10-2:30：展示 `prism --help` 和 `prism-desktop` 启动
- 2:30-3:00：快速展示桌面客户端界面

**旁白**：
> "首先演示 Windows 平台的安装。打开 PowerShell，克隆项目仓库，进入目录，然后运行一键安装脚本。脚本会自动安装 CLI、浏览器引擎、配置文件，以及桌面客户端。安装完成后，我们输入 prism --help 验证，然后启动桌面客户端。"

**字幕**：
```
Windows 安装：
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
.\scripts\install.ps1
```

---

### 第4章：macOS 安装（3:00 - 4:00）

**画面**：
- 3:00-3:10：Terminal 输入 `git clone https://github.com/jz616059669/prism-agent.git`
- 3:10-3:20：`cd prism-agent`
- 3:20-3:35：运行 `bash scripts/install.sh`
- 3:35-3:50：验证 `prism --help` 和 `prism-desktop`
- 3:50-4:00：桌面客户端界面

**旁白**：
> "接下来是 macOS 和 Linux 平台，操作方式基本相同。打开终端，克隆仓库，进入目录，运行 bash 安装脚本即可。整个过程大概需要 2-3 分钟，取决于你的网络速度。"

**字幕**：
```
macOS / Linux 安装：
git clone https://github.com/jz616059669/prism-agent.git
cd prism-agent
bash scripts/install.sh
```

---

### 第5章：Linux 安装（4:00 - 5:00）

**画面**：
- 4:00-4:10：Ubuntu Terminal 输入克隆命令
- 4:10-4:25：运行 `bash scripts/install.sh`
- 4:25-4:40：验证安装
- 4:40-5:00：展示桌面客户端在 Linux 上运行

**旁白**：
> "Linux 用户同样使用这个 bash 脚本。脚本会自动检测并使用系统的 pip 和 Python。如果你的网络环境需要代理，请确保终端已经配置了代理设置。"

**字幕**：
```
Linux 额外支持：
bash scripts/build-linux.sh        # 打包桌面客户端
sudo systemctl enable prism-gateway # 后台服务
```

---

### 第6章：配置说明（5:00 - 6:30）

**画面**：
- 5:00-5:20：使用代码编辑器打开 `~/.prism/config.yaml`
- 5:20-5:50：逐行讲解配置项，重点标注 `model.api_key`
- 5:50-6:10：演示 `prism config set` 命令配置
- 6:10-6:30：展示配置后的效果

**旁白**：
> "安装完成后，你需要配置模型 API Key。配置文件位于用户目录下的 .prism 文件夹中。你可以直接编辑 YAML 文件，也可以使用 prism config set 命令来配置。最关键的是填写 model.api_key 和 model.base_url，这是模型调用的必要条件。"

**字幕**：
```
配置路径：~/.prism/config.yaml
关键配置：model.api_key、model.base_url
```

**配置示例**：
```yaml
model:
  default: step-3.7-flash
  provider: stepfun
  base_url: https://api.stepfun.com/step_plan/v1
  api_key: YOUR_API_KEY
```

---

### 第7章：验证安装（6:30 - 7:30）

**画面**：
- 6:30-6:45：终端运行 `prism version`
- 6:45-7:00：`prism tools` 列出所有工具
- 7:00-7:15：`prism browser open https://example.com`
- 7:15-7:30：桌面客户端启动

**旁白**：
> "现在让我们验证安装是否成功。首先查看版本，然后列出可用工具，再测试浏览器功能。最后启动桌面客户端，确认图形界面正常。如果你的所有命令都能正常运行，说明安装已经成功。"

**字幕**：
```
验证命令：
prism version
prism tools
prism browser open https://example.com
prism-desktop
```

---

### 第8章：基本使用（7:30 - 9:00）

**画面**：
- 7:30-7:50：`prism ask "用 Python 写一个快速排序"`
- 7:50-8:10：`prism chat` 交互式聊天演示
- 8:10-8:30：桌面客户端中发送消息
- 8:30-8:50：`prism browser open` 打开网页演示
- 8:50-9:00：快速总结核心功能

**旁白**：
> "现在让我们看看 PRISM 的基本使用方式。你可以使用 prism ask 进行单次提问，也可以使用 prism chat 进入交互式对话。桌面客户端提供了更友好的图形界面。此外，你还可以使用浏览器控制功能打开网页，以及使用 MCP 连接外部工具。"

**字幕**：
```
核心功能：
prism ask "问题"   # 单次提问
prism chat         # 交互聊天
prism browser open <url>  # 浏览器控制
prism-desktop      # 桌面客户端
```

---

### 第9章：平台特有功能（9:00 - 10:00）

**画面**：
- 9:00-9:15（Linux）：输入 systemd 命令，展示 `systemctl status prism-gateway`
- 9:15-9:30（macOS）：输入 launchd 命令，展示 `launchctl list | grep prism`
- 9:30-9:45（Windows）：展示 NSSM 安装服务界面
- 9:45-10:00：总结三端差异

**旁白**：
> "PRISM 还支持后台运行 Gateway 服务。Linux 用户可以使用 systemd，macOS 用户可以使用 launchd，Windows 用户可以使用 NSSM 或任务计划程序。这些功能可以让 PRISM 在后台持续运行，接收来自 Telegram、飞书或 Discord 的消息。"

**字幕**：
```
后台服务：
Linux   → systemd
macOS   → launchd
Windows → NSSM / 任务计划程序
```

---

### 第10章：故障排查（10:00 - 10:30）

**画面**：
- 10:00-10:10：展示浏览器失败的报错，然后输入 `playwright install --force chromium`
- 10:10-10:20：展示模型调用 401 错误，然后打开配置文件检查 API Key
- 10:20-10:30：展示 Gateway 启动失败，然后查看日志

**旁白**：
> "如果你在安装过程中遇到问题，这里有几个常见故障的解决方法。浏览器功能失败时，可以尝试重新安装 Chromium。模型调用返回 401 或 403 时，请检查 API Key 是否正确。Gateway 启动失败时，请查看平台日志。更多问题可以访问项目仓库的 Issues 页面。"

**字幕**：
```
常见问题：
浏览器失败 → playwright install --force chromium
模型 401/403 → 检查 api_key 和 base_url
Gateway 失败 → 查看日志
```

---

### 第11章：总结（10:30 - 11:00）

**画面**：
- 10:30-10:40：项目主页 + 三端截图快速轮播
- 10:40-10:50：展示 INSTALL.md 和 INSTALL_FEISHU.md
- 10:50-11:00：结束画面 + 项目链接 + 感谢

**旁白**：
> "以上就是 PRISM Agent 的完整安装和使用教程。PRISM 是一个开源项目，支持 Windows、macOS、Linux 三端，提供命令行和桌面客户端两种使用方式。如果你觉得这个视频有用，请点赞订阅。项目地址在屏幕下方，欢迎 Star 和贡献。感谢观看！"

**字幕**：
```
项目仓库：github.com/jz616059669/prism-agent
安装文档：见 INSTALL.md 和 INSTALL_FEISHU.md
```

---

## 制作建议

### 录制工具
- **OBS Studio**（免费，推荐）
- **Camtasia**（付费，功能强）
- **剪映**（国产，易用）

### 配音方案
- 使用剪映的 AI 配音，选择自然男声/女声
- 或自己录制， Audacity 免费音频编辑

### 字幕
- 剪映自动生成字幕
- 或使用 Arctime 手动调整

### 封面图建议
- 标题：PRISM Agent 安装与使用全流程教程
- 副标题：三端支持 | 桌面客户端 | 一键安装
- 背景：深色主题 + 代码片段

### 发布建议
- Bilibili：标签 `AI Agent` `Python` `开源项目` `教程`
- YouTube：标签 `AI Agent` `Python` `Open Source` `Tutorial`
- 飞书：直接发送视频文件或链接

---

## 配套素材清单

1. **项目截图**
   - GitHub 仓库主页
   - 三端终端操作截图
   - 桌面客户端界面

2. **代码片段**
   - 克隆命令
   - 安装脚本
   - 配置文件示例

3. **错误场景**
   - 浏览器失败报错
   - 模型 401 错误
   - Gateway 启动失败

4. **背景音乐**
   - 轻量、无版权、科技感

---

## 视频时长控制

- 开场介绍：30 秒
- 环境准备：1 分钟
- Windows 安装：1.5 分钟
- macOS 安装：1 分钟
- Linux 安装：1 分钟
- 配置说明：1.5 分钟
- 验证安装：1 分钟
- 基本使用：1.5 分钟
- 平台特有功能：1 分钟
- 故障排查：0.5 分钟
- 总结：0.5 分钟

**总计：约 10 分钟**

建议实际录制时控制在 8-12 分钟之间，节奏适中，重点突出。

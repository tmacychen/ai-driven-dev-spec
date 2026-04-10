# Hermes Agent 研究报告

> **项目地址**: https://github.com/NousResearch/hermes-agent  
> **文档站**: https://hermes-agent.nousresearch.com/docs/  
> **版本**: v0.8.0（截至 2026 年 4 月）  
> **许可证**: MIT License  
> **Stars**: 40.7k | **Forks**: 5.2k  
> **开发团队**: [Nous Research](https://nousresearch.com)

---

## 一、项目定位

Hermes Agent 是一个**自进化的 AI 智能体**，核心定位是"随使用不断成长的智能体"。与传统 AI 助手不同，Hermes 具备内置的学习循环——它能够从经验中创建技能、在使用中不断改进、自动保存知识、搜索过往对话，并在多次会话中逐步建立对用户的深度理解。

一句话概括：**The agent that grows with you**（与你共同成长的智能体）。

---

## 二、核心特性总览

### 2.1 自我学习与进化

这是 Hermes 最核心的差异化能力：

| 能力 | 说明 |
|------|------|
| **技能自动创建** | 完成复杂任务后自动生成可复用的技能文档（SKILL.md） |
| **技能自我改进** | 使用过程中持续优化已有技能的步骤和效果 |
| **持久化记忆** | 双文件架构（MEMORY.md + USER.md），跨会话持久保存关键信息 |
| **会话搜索** | 基于 FTS5 的全量会话记录搜索，回溯任意历史对话 |
| **用户建模** | 集成 Honcho 进行多轮用户画像构建，深度理解用户偏好 |
| **LLM 摘要回顾** | 对过往会话进行智能摘要，快速回顾关键决策 |

### 2.2 多平台通信

Hermes 不只是一个终端工具，而是一个跨平台通信中枢：

- **终端 CLI**：完整的 TUI 支持，多行编辑、命令自动补全、对话历史
- **消息网关**：统一接口支持 15+ 平台
  - 即时通讯：Telegram、Discord、Slack、WhatsApp、Signal
  - 邮件：Email 集成
  - 语音消息转录：支持语音消息自动转文字
- **跨平台会话同步**：在不同平台间保持对话连续性

### 2.3 灵活的模型支持

支持多种 LLM 提供商，可通过 `hermes model` 命令一键切换：

| 提供商 | 特点 |
|--------|------|
| Nous Portal | 官方端点 |
| OpenRouter | 200+ 模型可选 |
| z.ai/GLM | 中文友好 |
| Kimi/Moonshot | 长上下文 |
| MiniMax | 多模态 |
| OpenAI | GPT 系列 |
| 自定义端点 | 任意 OpenAI 兼容 API |

### 2.4 任务调度与自动化

- **内置 Cron 调度器**：支持自然语言描述的计划任务
- **自动报告**：每日报告、夜间备份、每周审计
- **多平台交付**：调度结果可发送到任意已配置的消息平台

### 2.5 并行处理与子代理

- **子代理生成**：创建独立的子代理并行处理多个工作流
- **Python 脚本集成**：通过 RPC 调用工具，将多步流程压缩为单次交互

---

## 三、工具系统

### 3.1 工具类别

Hermes 内置 40+ 工具，按功能分为以下类别：

| 类别 | 示例工具 | 描述 |
|------|----------|------|
| **网络** | `web_search`, `web_extract` | 网络搜索和网页内容提取 |
| **终端与文件** | `terminal`, `process`, `read_file`, `patch` | 命令执行和文件操作 |
| **浏览器** | `browser_navigate`, `browser_snapshot`, `browser_vision` | 交互式浏览器自动化（文本+视觉） |
| **多媒体** | `vision_analyze`, `image_generate`, `text_to_speech` | 多模态分析与生成 |
| **智能体协同** | `todo`, `clarify`, `execute_code`, `delegate_task` | 任务规划、问题澄清、代码执行和子代理委派 |
| **记忆与回顾** | `memory`, `session_search` | 持久化记忆和会话记录搜索 |
| **自动化与交付** | `cronjob`, `send_message` | 定时任务和跨平台消息发送 |
| **集成** | `ha_*`(Home Assistant), MCP 工具, `rl_*` | 智能家居、MCP 协议、强化学习 |

### 3.2 工具集（Toolsets）系统

工具被组织成逻辑上的**工具集**，可按需启用/禁用：

```bash
hermes chat --toolsets "web,terminal"   # 仅启用网络和终端工具
hermes tools                            # 交互式配置工具集
```

常见工具集：`web`, `terminal`, `file`, `browser`, `vision`, `image_gen`, `moa`, `skills`, `tts`, `todo`, `memory`, `session_search`, `cronjob`, `code_execution`, `delegation`, `clarify`, `homeassistant`, `rl`

### 3.3 六种终端后端

`terminal` 工具支持在不同环境中执行命令，实现灵活的安全隔离：

| 后端 | 描述 | 使用场景 |
|------|------|----------|
| **local** | 本地机器运行（默认） | 开发、可信任务 |
| **docker** | Docker 容器隔离 | 安全性、环境可复现 |
| **ssh** | 远程服务器 | 沙箱隔离，防止 Agent 修改自身 |
| **singularity** | HPC 容器 | 高性能计算集群 |
| **modal** | 云端无服务器 | 按需唤醒，闲置零成本 |
| **daytona** | 云端沙盒工作区 | 持久化远程开发环境 |

**容器安全加固**：
- 只读根文件系统（Docker）
- 丢弃所有 Linux 能力
- 禁止权限升级
- 进程数限制（256）
- 完整命名空间隔离

### 3.4 后台进程管理

支持长时间运行的后台进程：
- `terminal(command, background=true)` — 启动后台进程
- `process(action="list")` — 列出运行中进程
- `process(action="poll/wait/log/kill")` — 管理/查看进程

---

## 四、记忆系统

### 4.1 双文件架构

记忆系统由两个独立文件构成，存储在 `~/.hermes/memories/`：

| 文件 | 用途 | 容量限制 |
|------|------|----------|
| **MEMORY.md** | Agent 的个人笔记：环境事实、项目规范、经验教训 | 2,200 字符（~800 tokens） |
| **USER.md** | 用户配置文件：偏好、沟通风格、期望 | 1,375 字符（~500 tokens） |

### 4.2 工作流程

1. **会话启动注入**：两个文件内容作为"冻结快照"注入系统提示
2. **会话中持久化**：Agent 通过 `memory` 工具实时管理（增/删/改），立即保存到磁盘
3. **快照模式**：系统提示中的记忆内容在会话期间保持不变，修改下次会话生效

### 4.3 `memory` 工具操作

| 操作 | 说明 |
|------|------|
| `add` | 添加新记忆条目 |
| `replace` | 替换已存在条目（子字符串匹配） |
| `remove` | 移除不再相关的条目（子字符串匹配） |

### 4.4 会话搜索

- 基于 FTS5 的全量历史会话搜索，存储在 `~/.hermes/state.db`
- 适用于查找过去讨论的具体细节，即使未被收入永久记忆
- 与永久记忆协同工作，互补而非替代

### 4.5 外部记忆提供商

支持 Honcho、Mem0 等 8 种外部记忆提供商插件，提供知识图谱、语义搜索等增强能力。通过 `hermes memory setup` 配置。

---

## 五、技能系统

### 5.1 核心概念

技能（Skills）是 Hermes 可以按需加载的知识文档，遵循**渐进式披露**模式以最小化 Token 使用，并与 [agentskills.io](https://agentskills.io/specification) 开放标准兼容。

### 5.2 渐进式披露加载

| 层级 | 方法 | 加载内容 |
|------|------|----------|
| Level 0 | `skills_list()` | 仅名称、描述、类别 |
| Level 1 | `skill_view(name)` | 完整技能内容和元数据 |
| Level 2 | `skill_view(name, path)` | 特定参考文件 |

### 5.3 SKILL.md 格式

```markdown
---
name: my-skill
description: 技能描述
version: 1.0.0
platforms: [macos, linux]
metadata:
  hermes:
    tags: [python, automation]
    category: devops
---
# 技能标题
## 使用时机
触发条件说明
## 操作步骤
1. 第一步
2. 第二步
```

### 5.4 技能中心（Skills Hub）

支持从多个来源浏览、搜索、安装技能：
- **官方可选技能**：随 Hermes 发布
- **skills.sh**：Vercel 公共技能目录
- **Well-known 端点**：从网站直接发现
- **GitHub**：直接从仓库安装
- **第三方市场**：ClawHub、LobeHub 等

### 5.5 代理自管理技能

Agent 可通过 `skill_manage` 工具创建、更新、删除自己的技能，形成**程序性记忆**——这是 Hermes 自进化能力的核心实现路径。

---

## 六、个性化系统

- **SOUL.md**：定义 Hermes 的默认语音和人格特征
- **上下文文件**：塑造每个对话的项目上下文
- **个性设置**：通过 `/personality [name]` 命令切换

---

## 七、安全体系

### 7.1 命令批准机制
- 敏感操作需用户确认
- 支持 sudo 权限管理

### 7.2 容器隔离
- 六种终端后端提供不同级别的隔离
- Docker/Modal/Daytona 提供最强隔离

### 7.3 技能安全
- 所有从中心安装的技能经过安全扫描
- 信任等级分层：内置 > 官方 > 社区
- `--force` 可覆盖非危险策略阻止

---

## 八、研究支持

Hermes 不仅面向终端用户，还为 AI 研究提供支持：

- **批量轨迹生成**：适用于强化学习训练
- **Atropos RL 环境**：集成 Tinker-Atropos 进行 RL 训练
- **轨迹压缩**：优化工具调用模型的训练数据

---

## 九、安装与使用

### 快速安装

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

支持 Linux、macOS 和 WSL2。

### 核心命令

| 命令 | 功能 |
|------|------|
| `hermes` | 启动交互式 CLI 对话 |
| `hermes model` | 选择 LLM 提供商和模型 |
| `hermes tools` | 配置启用哪些工具 |
| `hermes config set` | 设置配置值 |
| `hermes gateway` | 启动消息网关 |
| `hermes setup` | 完整设置向导 |
| `hermes update` | 更新到最新版本 |
| `hermes doctor` | 诊断问题 |

### CLI 会话内命令

| 命令 | 功能 |
|------|------|
| `/new` 或 `/reset` | 新建会话 |
| `/model [provider:model]` | 切换模型 |
| `/personality [name]` | 设置个性 |
| `/retry` / `/undo` | 重试/撤销 |
| `Ctrl+C` | 中断当前任务 |

### 从 OpenClaw 迁移

```bash
hermes claw migrate              # 交互式迁移
hermes claw migrate --dry-run    # 预览
hermes claw migrate --preset user-data  # 仅迁移用户数据
```

---

## 十、技术栈

| 维度 | 技术 |
|------|------|
| **主要语言** | Python（93.8%） |
| **辅助语言** | TeX、Shell、Nix、JavaScript |
| **包管理** | uv（现代 Python 包管理器） |
| **容器** | Docker、Singularity |
| **无服务器** | Modal、Daytona |
| **配置格式** | YAML + 环境变量覆盖 |
| **扩展协议** | MCP（Model Context Protocol） |

---

## 十一、架构总览

Hermes 的架构围绕以下核心组件构建：

```
┌─────────────────────────────────────────────┐
│              消息网关（Gateway）              │
│   Telegram / Discord / Slack / WhatsApp...   │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              Agent 核心                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ 对话循环  │ │ 工具调度  │ │ 记忆管理  │    │
│  └──────────┘ └──────────┘ └──────────┘    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ 技能系统  │ │ 用户建模  │ │ Cron调度  │    │
│  └──────────┘ └──────────┘ └──────────┘    │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│            终端后端 / 工具执行                │
│  Local / Docker / SSH / Modal / Daytona...   │
└─────────────────────────────────────────────┘
```

---

## 十二、社区与生态

- **官方文档**：https://hermes-agent.nousresearch.com/docs/
- **Discord 社区**：https://discord.gg/NousResearch
- **技能中心**：https://agentskills.io
- **问题反馈**：GitHub Issues
- **讨论区**：GitHub Discussions

---

## 十三、总结评价

Hermes Agent 是一个**功能全面、高度可扩展的 AI 智能体框架**，其核心优势体现在三个维度：

1. **自进化能力**：通过技能系统 + 记忆系统 + 用户建模的三位一体设计，Hermes 能够真正从使用中学习并持续改进，这在同类产品中是罕见的。

2. **多平台通信**：不是一个孤立的终端工具，而是跨 15+ 平台的通信中枢，消息网关设计使它可以随时随地被触达。

3. **灵活部署**：六种终端后端从 $5 VPS 到无服务器架构全面覆盖，适合不同规模和预算的用户。

潜在不足：
- 记忆系统容量有限（MEMORY.md ~800 tokens, USER.md ~500 tokens），重度用户可能需要外部记忆提供商
- 主要语言为 Python，性能敏感场景可能受限
- 作为较新项目，生态和社区成熟度仍在建设中

---

*报告生成时间：2026 年 4 月 9 日*

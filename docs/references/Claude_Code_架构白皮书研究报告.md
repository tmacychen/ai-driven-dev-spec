# Claude Code 架构白皮书研究报告

> **文档来源**: https://ccb.agent-aura.top/docs/introduction/what-is-claude-code  
> **文档性质**: 技术白皮书 / 逆向工程分析文档  
> **分析对象**: Anthropic 官方 CLI 编码工具 Claude Code  
> **文档状态**: 持续更新中

---

## 一、文档定位与背景

本白皮书是对 Claude Code 进行的深度逆向工程分析，不是官方文档。它通过源码级解剖，揭示了 Claude Code 从用户输入到 API 交互的完整工作链路，是理解现代 AI 编码系统架构设计的宝贵参考资料。

---

## 二、Claude Code 是什么

### 2.1 一句话定义

Claude Code 是一个运行在本地终端中的 **agentic coding system（自主编码系统）**。它不是给建议的聊天机器人，而是直接在项目目录中读代码、改文件、跑命令、调试程序，拥有完整 shell 能力的 AI 编码助手。

### 2.2 三个核心定位

| 定位关键词 | 含义 |
|-----------|------|
| **Terminal-native** | 原生 CLI 应用，不是 IDE 插件、Web 界面或 API 包装器 |
| **Agentic** | AI 自主决策工具调用链，不是"一问一答"的聊天模式 |
| **Coding system** | 面向软件工程全流程，不是通用问答工具 |

### 2.3 与同类工具的架构差异

| 工具 | 架构模式 | 运行位置 | 工具执行 |
|------|----------|----------|----------|
| **Claude Code** | Terminal-native agentic loop | 本地进程 | 直接 shell 执行 |
| Cursor / Copilot | IDE-integrated autocomplete + chat | IDE 进程内 | LSP / IDE API |
| Aider | CLI chat → git patch | 本地进程 | 文件操作为主 |
| ChatGPT / Claude.ai | Cloud chat + artifacts | 浏览器/云端 | 沙箱容器 |

---

## 三、五层架构详解

Claude Code 采用清晰的五层架构，每层职责明确：

### 3.1 交互层（Interaction Layer）

- **入口源码**: `src/screens/REPL.tsx`
- **关键技术**: 基于 React/Ink 的终端界面
- **核心功能**:
  - 终端 UI 渲染、用户输入处理、消息展示
  - 支持斜杠命令、文件附件、图片等输入方式
  - `processUserInput()` 处理所有用户交互

### 3.2 编排层（Orchestration Layer）

- **入口源码**: `src/QueryEngine.ts`
- **核心功能**:
  - 会话状态管理（消息数组、工具权限上下文）
  - 成本累计（`accumulateUsage()` / `getTotalCost()`）
  - Transcript 持久化（支持 `--resume` 恢复对话）
  - 文件历史快照（支持撤销操作）

### 3.3 核心循环层（Agentic Loop Layer）

- **入口源码**: `src/query.ts`
- **流程步骤**:
  1. 上下文预处理管道（压缩、裁剪等优化）
  2. 流式 API 调用（`deps.callModel()` 返回事件流）
  3. 工具执行（并行或串行处理）
  4. 终止判定（根据 `needsFollowUp` 决定是否继续循环）

### 3.4 工具层（Tools Layer）

- **入口源码**: `src/tools.ts` → `src/Tool.ts`
- **工具组装**: `getAllBaseTools()` 整合 50+ 工具
- **工具接口**: `Tool<Input, Output, Progress>`
- **调用链**: `validateInput()` → `canUseTool()` → `checkPermissions()` → `call()` → `ToolResult`

### 3.5 通信层（Communication Layer）

- **入口源码**: `src/services/api/claude.ts`
- **支持提供商**:
  - Anthropic Direct（默认）
  - AWS Bedrock
  - Google Vertex
  - Azure（自定义 base URL）
  - OpenAI 兼容层
  - Gemini 兼容层
  - xAI Grok
- **流式特性**: `AsyncGenerator` 支持实时响应

---

## 四、Agentic Loop：核心循环机制

### 4.1 循环本质

位于 `src/query.ts` 的 `queryLoop()` 是一个 `while (true)` 无限循环，每次迭代代表一次"思考 → 行动 → 观察"周期。

### 4.2 四阶段迭代

#### 阶段 1：上下文预处理管道

在调用 API 前，依次执行 5 层压缩/优化：

| 步骤 | 作用 |
|------|------|
| `applyToolResultBudget()` | 对工具结果截断 |
| `snipCompactIfNeeded()` | 历史消息压缩 |
| `microcompact()` | 工具结果摘要 |
| `applyCollapsesIfNeeded()` | 上下文折叠 |
| `autocompact()` | 超 token 阈值时自动压缩 |

#### 阶段 2：流式 API 调用

- 使用 `deps.callModel()` 发起流式请求
- 在流式过程中：
  - 收集 `assistantMessages`
  - 提取 `tool_use` 块并标记 `needsFollowUp = true`
  - 通过 `StreamingToolExecutor` 并行执行工具
  - 对可恢复错误暂扣处理

#### 阶段 3：工具执行

- `needsFollowUp = true` 时执行工具
- 流式执行或批量执行
- 结果标准化后合并到消息中

#### 阶段 4：终止判定

**7 种终止条件**：

| 条件 | 触发机制 |
|------|----------|
| `completed` | AI 未发出 tool_use，通过 stop hooks 检查 |
| `blocking_limit` | Token 超硬限制 |
| `aborted_streaming` | 用户中止（ESC） |
| `model_error` | 模型调用异常 |
| `prompt_too_long` | 413 错误且恢复无效 |
| `image_error` | 图片错误 |
| `stop_hook_prevented` | Stop hook 阻止 |

**4 种继续条件**：
1. 正常工具循环
2. max_output_tokens 恢复（最多 3 次重试）
3. prompt-too-long 恢复（压缩后重试）
4. stop hook 阻塞重试

### 4.3 设计哲学

- **实时信息反馈**：每步工具结果动态影响后续决策
- **动态上下文管理**：每轮迭代前重新评估压缩需求
- **用户中断友好**：多个节点检测 `abortController.signal`
- **成本可控**：Token Budget 防止无效循环

---

## 五、工具系统设计

### 5.1 工具分类

| 类别 | 工具示例 | 说明 |
|------|----------|------|
| **文件操作** | Read, Write, Edit | 三大核心文件操作工具 |
| **命令执行** | BashTool | 安全设计，支持沙箱 |
| **搜索与导航** | Glob, Grep, LSP 工具 | 代码库精准定位 |
| **任务管理** | TodoWrite, Tasks | 双轨架构的任务系统 |

### 5.2 工具执行链

每个工具的执行都经过严格的安全检查链：

```
validateInput() → canUseTool() → checkPermissions() → call() → ToolResult
```

### 5.3 任务管理双轨架构

- **TodoWrite**：面向用户的待办事项系统
- **Tasks**：面向内部的任务编排系统

---

## 六、上下文工程

### 6.1 System Prompt 动态组装

System Prompt 不是一段写死的文本，而是 `string[]` 数组，经过三阶段管道处理：

```
getSystemPrompt()          → string[]       （组装内容）
buildEffectiveSystemPrompt() → SystemPrompt   （选择优先级路径）
buildSystemPromptBlocks()  → TextBlockParam[] （分块 + cache_control 标记）
```

#### 静态区 vs 动态区

| 区域 | 内容 | 缓存策略 |
|------|------|----------|
| **静态区** | Intro, Rules, Tone & Style 等 | 全局缓存（`scope: 'global'`） |
| **BOUNDARY** | `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` | 分界标记 |
| **动态区** | Session Guidance, Memory, MCP 等 | 组织级缓存（`scope: 'org'`）或无缓存 |

#### 五级优先级选择

| 优先级 | 条件 | 行为 |
|--------|------|------|
| Override | `overrideSystemPrompt` 非空 | 完全替换 |
| Coordinator | 协调者模式 | 专用提示词 |
| Agent | 代理定义存在 | 追加或替换 |
| Custom | `--system-prompt` 指定 | 替换默认 |
| Default | 无特殊条件 | 完整 `getSystemPrompt()` |

### 6.2 缓存分块策略

这是 Claude Code 在 token 成本优化上的核心设计：

**三种分块模式**：

| 模式 | 条件 | 缓存效率 |
|------|------|----------|
| 模式 1 | MCP 工具存在 | 降级为组织级 |
| 模式 2 | 1P + Boundary（最高效） | 静态区全局缓存 |
| 模式 3 | 3P 提供商或无 Boundary | 组织级缓存 |

> 一次典型 System Prompt 约 20K+ tokens，通过缓存分块可节省 30-50% 输入 token 费用。

### 6.3 项目记忆系统（CLAUDE.md）

CLAUDE.md 是 Claude Code 最巧妙的设计之一：

```
~/.claude/CLAUDE.md              ← 用户全局（个人偏好）
  └── /project/CLAUDE.md         ← 项目根目录（团队共享）
        └── /project/src/CLAUDE.md  ← 子目录（模块特定）
```

- 从 CWD 向上遍历目录树，合并所有 CLAUDE.md
- 注入项目概述、开发约定、常用命令、注意事项
- 通过 `prependUserContext()` 作为首条用户消息注入

### 6.4 上下文压缩（Compaction）

三层递进压缩策略：

| 层级 | 方法 | 触发条件 | 特点 |
|------|------|----------|------|
| **MicroCompact** | 清除旧工具输出 | 单个工具输出过长 | 无需 API 调用 |
| **Session Memory** | 使用已提取记忆 | feature flag 启用 | 无需摘要模型 |
| **API 摘要** | 调 AI 生成摘要 | 手动 `/compact` 或回退 | 最准确但最贵 |

**完整性保护**：
- 工具调用完整性（每个 tool_result 必须有对应 tool_use）
- 保留窗口计算（平衡深度与限制）
- 紧急处理机制（PTL 降级、截断重试）

### 6.5 Token 预算管理

- 动态计算上下文窗口
- 接近预算时提醒 AI 加速收尾
- 防止无效循环

---

## 七、多 Agent 协作

### 7.1 两种子 Agent 路径

| 维度 | 命名 Agent（如 Explore/Plan） | Fork 子进程 |
|------|------------------------------|-------------|
| **触发条件** | 指定 `subagent_type` | 未指定类型且启用 Fork |
| **系统提示** | 专用提示 | 继承父 Agent 完整提示 |
| **工具池** | 独立组装（受限） | 共享父工具池 |
| **上下文** | 仅任务描述 | 完整对话历史 |
| **核心目标** | 专业任务委派 | 优化 Prompt 缓存命中率 |

### 7.2 Worktree 隔离

- 通过 `isolation: "worktree"` 创建独立 Git 工作副本
- 文件操作自动重定向至 Worktree 路径
- 无变更时自动清理，有变更时保留

### 7.3 递归防护

- 检查 `querySource` 来源和 `<fork-boilerplate>` 标签
- 防止子 Agent 无限递归

### 7.4 生命周期管理

- **同步 Agent**：支持自动后台化（默认 120 秒无响应转后台）
- **异步 Agent**：立即返回 `async_launched`，独立 AbortController

---

## 八、安全与权限

### 8.1 三级权限体系

| 权限行为 | 说明 |
|----------|------|
| **Allow** | 自动放行，用户无感知 |
| **Ask** | 弹出确认对话框 |
| **Deny** | 直接拒绝执行 |

### 8.2 权限规则来源（优先级从高到低）

1. **会话层**：当前对话手动授权
2. **命令行参数**：`--allow/--deny`
3. **命令层**：Skill 工具白名单
4. **项目设置**：`.claude/settings.json`（团队共享）
5. **用户设置**：`~/.claude/settings.json`（跨项目）
6. **策略设置**：企业管理员下发

### 8.3 三维度匹配

1. **工具名匹配** — 精确匹配工具名称
2. **命令模式匹配** — 对 Bash 命令 AST 解析
3. **路径匹配** — 对文件操作 glob 模式匹配

### 8.4 权限模式

| 模式 | 说明 |
|------|------|
| **Default** | 敏感操作逐一确认 |
| **Plan Mode** | 只能读不能写（探索阶段） |
| **Auto Mode** | AI 分类器自动决策 |
| **Bypass** | 所有操作自动放行 |

### 8.5 死循环防护

- 同一工具连续拒绝上限：3 次
- 冷却期：30 秒
- 达到上限时强制 AI 改变策略

### 8.6 沙箱机制

权限系统之外的第二道防线，提供更底层的安全隔离。

---

## 九、可扩展性

### 9.1 MCP 协议集成

**架构链路**：配置 → 连接 → 工具发现 → 执行

- **配置层级**：user/project/local 三级合并
- **连接管理**：React Hook 管理生命周期
- **工具发现**：LRU 缓存（上限 20），工具名格式 `mcp__<serverName>__<toolName>`
- **7 种传输层**：stdio、sse、http、sse-ide、ws-ide、ws、claudeai-proxy

**安全设计**：
- OAuth 认证（远程传输）
- 请求级超时保护
- Session 过期自动重试
- 并发控制：本地 3 个、远程 20 个连接

### 9.2 Hooks 生命周期钩子

执行引擎与拦截协议：
- 预压缩 Hook
- 后压缩 Hook
- 会话启动 Hook

### 9.3 Skills 技能系统

"Prompt 即能力"的架构哲学——通过结构化的 Prompt 定义即可扩展 AI 的能力。

### 9.4 自定义 Agent

从 Markdown 到运行时的完整链路，支持用户创建专用代理。

---

## 十、隐藏功能与内部机制

### 10.1 三层门禁系统

功能可见性控制架构，控制功能的分层可见性。

### 10.2 88 个 Feature Flags

构建时特性门控，支持细粒度的功能开关控制。

### 10.3 GrowthBook A/B 测试

运行时功能发布控制，支持灰度发布和实验。

### 10.4 未公开功能

- **Debug 模式**：调试诊断
- **Buddy 宠物系统**：趣味性功能
- **Ant 特权世界**：Anthropic 员工专属功能
- **Tier3 stubs**：预留的未来功能

### 10.5 基础设施

- **Auto updater**：自动更新机制
- **LSP integration**：语言服务协议集成
- **External dependencies**：外部依赖管理
- **Telemetry remote config audit**：遥测与远程配置审计

---

## 十一、Provider 兼容层

### 11.1 OpenAI 兼容层

通过 `CLAUDE_CODE_USE_OPENAI=1` 启用，支持 Ollama、DeepSeek、vLLM 等：

```
src/services/api/openai/
├── client.ts           # 客户端配置
├── convertMessages.ts  # 消息格式转换
├── convertTools.ts     # 工具定义转换
├── streamAdapter.ts    # SSE 流适配
├── modelMapping.ts     # 模型名称映射
└── index.ts            # 入口函数
```

### 11.2 Gemini 兼容层

通过 `CLAUDE_CODE_USE_GEMINI=1` 启用，架构类似 OpenAI 兼容层。

### 11.3 兼容层限制

- 无精确 token 计数（退回近似估算）
- 无全局缓存（仅组织级）
- 部分 beta 功能不可用

---

## 十二、完整数据流示意

```
用户输入
  │
  ▼
REPL.tsx（交互层）── 处理输入、渲染输出
  │
  ▼
QueryEngine.ts（编排层）── 管理会话、持久化、成本追踪
  │
  ▼
query.ts（核心循环层）── Agentic Loop
  │  ┌───────────────────────────────┐
  │  │ 1. 上下文预处理（5层压缩管道） │
  │  │ 2. 流式 API 调用              │
  │  │ 3. 工具执行                   │
  │  │ 4. 终止/继续判定              │
  │  └───────────────────────────────┘
  │
  ▼
Tools Layer（工具层）── 50+ 工具，权限过滤
  │
  ▼
claude.ts（通信层）── 流式 HTTP，多云提供商
```

---

## 十三、设计亮点总结

1. **数组式 System Prompt**：不是单段文本，而是 `string[]`，配合缓存分块节省 30-50% token 费用——这是成本优化的核心设计。

2. **Agentic Loop**：`while(true)` 循环 + 7 种终止条件 + 4 种继续条件，实现真正的自主编码——AI 能连续执行多步操作直到任务完成。

3. **三层压缩策略**：MicroCompact → Session Memory → API 摘要，层层递进，在成本和效果间取得平衡。

4. **双路径子 Agent**：命名 Agent 做专业委派，Fork 做缓存优化——同一次设计解决了两个不同的问题。

5. **三级权限 + 死循环防护**：Allow/Ask/Deny + 3 次拒绝上限 + 30 秒冷却期，既给 AI 足够的自主空间，又守住安全底线。

6. **多 Provider 兼容层**：通过流适配器模式，让 Ollama、DeepSeek、Gemini 等非 Anthropic 端点也能驱动 Claude Code。

7. **CLAUDE.md 项目级知识注入**：从目录树向上合并多级配置文件，让 AI 无需额外说明就能"理解"项目——这是工程实用性的典范。

---

*报告生成时间：2026 年 4 月 9 日*

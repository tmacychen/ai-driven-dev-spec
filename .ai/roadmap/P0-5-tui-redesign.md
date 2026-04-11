# P0-5 TUI 重构设计说明

> 基于 Textual 框架重构 ADDS CLI 交互系统
> **核心设计理念**：标签页 = 独立工作区（Agent），分屏 = 工作区内多任务视图

---

## 1. 设计目标

### 1.1 核心需求

| 需求 | 当前问题 | 目标状态 |
|------|---------|---------|
| **多 Agent 工作区** | 单一会话 | 标签页 = 独立 Agent，每个标签页运行不同的角色和任务 |
| **分屏多任务** | 单一视图 | 分屏 = 工作区内多任务并行视图（可选） |
| 多行输入 | 需快捷键切换 | 原生多行编辑 |
| 输出渲染 | 纯文本流式 | Markdown + 代码高亮 |
| 权限确认 | 打断式弹窗 | 侧边栏非打断式 |

### 1.2 核心概念：工作区模型

```
┌─────────────────────────────────────────────────────────────────┐
│  整个应用 = Agent 工作区管理器                                    │
│                                                                 │
│  ┌─────────────┬─────────────┬─────────────┐                   │
│  │ 标签页 1    │  标签页 2   │  标签页 3   │  [+ 新建 Agent]   │
│  │ (PM Agent)  │ (Dev Agent) │(Reviewer)   │                   │
│  └──────┬──────┴──────┬──────┴──────┬──────┘                   │
│         │             │             │                           │
│         ▼             ▼             ▼                           │
│   工作区 1        工作区 2       工作区 3                        │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐                       │
│   │ Agent   │   │ Agent   │   │ Agent   │                       │
│   │ 独立运行 │   │ 独立运行 │   │ 独立运行 │                       │
│   └─────────┘   └─────────┘   └─────────┘                       │
│                                                                 │
│  每个标签页 = 独立的 Agent 实例                                   │
│  - 独立的角色 (PM/Developer/Reviewer/...)                        │
│  - 独立的任务上下文                                               │
│  - 独立的 Token 预算                                              │
│  - 独立的消息历史                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 技术选型

**Textual 框架**：
- 原生 TUI 组件：SplitView、TabbedContent、TextArea
- 异步架构：与现有 Agent Loop 无缝集成
- Rich 集成：保留现有皮肤系统
- 响应式布局：自适应终端尺寸

**新增依赖**：
```
textual >= 0.47.0
```

---

## 2. 整体架构

### 2.1 布局设计

```
┌─────────────────────────────────────────────────────────────┐
│  Header: ADDS [3 Agents] [model] [perm-mode]  Total: 45K/128K│
├─────────────────────────────────────────────────────────────┤
│ Tabs: [PM-需求分析*] [Dev-实现] [Reviewer-代码审查] [+]      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   TaskPanel A (当前任务)      │   TaskPanel B (参考资料)    │
│   (主工作区)                  │   (可选分屏)                │
│                              │                             │
│   👤 user: 实现登录功能       │   📄 参考: login.md         │
│   🤖 assistant: 好的，我...   │   - 用户名/密码验证         │
│                              │   - Session 管理            │
│   ┌─────────────────────┐    │   - 安全考虑                │
│   │ 代码实现...         │    │                             │
│   └─────────────────────┘    │                             │
│                              │                             │
├──────────────────────────────┴─────────────────────────────┤
│ InputArea (多行编辑)                                         │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 请输入消息...                                            │ │
│ └─────────────────────────────────────────────────────────┘ │
│ [Ctrl+Enter 发送] [Ctrl+N 新建Agent] [Ctrl+S 分屏]          │
├─────────────────────────────────────────────────────────────┤
│ Footer: [F1 Help] [F2 Keys] [F3 History] [F4 Perm] [Ctrl+Q] │
└─────────────────────────────────────────────────────────────┘
```

### 2.1.1 分屏的目的

分屏是**可选功能**，用于优化同一 Agent 内的多任务视图：

| 场景 | 分屏方式 | 用途 |
|------|---------|------|
| 单任务专注 | 无分屏 | 简单对话，专注当前任务 |
| 参考资料 | 左侧任务 + 右侧参考 | 编写代码时查看 API 文档 |
| 并行对比 | 左侧版本A + 右侧版本B | 代码审查、Diff 对比 |
| 多窗口监控 | 左侧输出 + 右侧日志 | 调试模式 |

**分屏快捷键**：
- `Ctrl+S` 切换分屏显示
- `Ctrl+\` 垂直分屏 / 水平分屏切换

### 2.2 组件层次

```
ADDSApp (主应用 = Agent 工作区管理器)
├── Header (顶部状态栏)
│   ├── 模型名称
│   ├── 活跃 Agent 数量
│   ├── 权限模式
│   └── 总 Token 使用量
│
├── TabbedContent (标签页容器 = Agent 列表)
│   └── WorkspaceTab (每个标签页 = 独立 Agent 工作区)
│       ├── SplitView (分屏容器 - 可选多任务视图)
│       │   ├── TaskPanel A (任务视图 A)
│       │   └── TaskPanel B (任务视图 B - 可选)
│       ├── InputArea (底部：输入区域)
│       └── AgentState (Agent 状态：角色、任务、预算)
│
├── PermissionSidebar (权限侧边栏 - 可隐藏)
│   └── 待确认权限请求列表（跨所有 Agent）
│
└── Footer (底部快捷键提示)
```

### 2.2.1 标签页 = 独立 Agent 工作区

每个标签页代表一个**独立的 Agent 实例**：

```
WorkspaceTab (Agent 工作区)
├── agent_role: str          # 角色：pm/architect/developer/reviewer/tester
├── task_context: str        # 当前任务描述
├── messages: List[Message]  # 对话历史（独立）
├── token_budget: Budget     # 独立 Token 预算
├── model: ModelInterface    # 模型实例（可共享）
├── status: active|waiting|paused  # 工作状态
└── split_view: SplitView    # 可选：分屏多任务视图
```

**创建新 Agent 的方式**：
1. 点击 `[+]` 标签 → 弹出角色选择器
2. 快捷键 `Ctrl+N` → 新建 Agent
3. 命令 `/new` 或 `/new <role>` → 指定角色创建

### 2.3 状态管理

```
AppState (全局状态 = Agent 工作区管理器)
├── workspaces: Dict[str, AgentState]   # 所有 Agent 工作区
├── active_workspace: str                # 当前激活的 Agent ID
├── permission_mode: PermissionMode      # 权限模式（全局）
├── skin: SkinConfig                     # 皮肤配置
├── total_tokens: int                    # 总 Token 使用量
└── shared_model: ModelInterface         # 共享的模型实例

AgentState (单个 Agent 状态)
├── workspace_id: str                    # 工作区 ID
├── agent_role: str                      # 角色
├── task_context: str                    # 任务描述
├── messages: List[Message]              # 对话历史（独立）
├── token_used: int                      # 已用 Token
├── token_budget: int                    # 预算上限
├── status: active|waiting|paused|completed|error
└── streaming: bool                      # 是否流式输出
```

**关键设计**：
- 每个 Agent 有独立的 Token 预算
- 模型实例可以共享（减少资源占用）
- 权限模式全局统一，但每个 Agent 独立确认

---

## 3. 核心组件设计

### 3.1 TaskPanel (任务面板)

**职责**：Agent 的主工作区，包含对话历史和响应渲染

**功能**：
- 消息列表渲染（用户/助手/系统/工具）
- 虚拟滚动（大量消息优化）
- 长消息折叠（> 500 字符）
- 搜索过滤
- Markdown 渲染 + 代码高亮
- 流式更新（100ms 节流刷新）

**消息结构**：
```
Message:
  - id: 唯一标识
  - role: user | assistant | system | tool
  - content: 消息内容
  - timestamp: 时间戳
  - tokens: Token 数量
  - collapsed: 是否折叠
```

**渲染模式**：
| 模式 | 触发条件 | 行为 |
|------|---------|------|
| 流式 | 模型响应中 | 增量追加，100ms 节流刷新 |
| Markdown | 响应完成 | 完整渲染，支持代码块、表格、链接 |
| 工具输出 | 工具调用 | 代码块 + 语法高亮 + 复制按钮 |
| 思考过程 | 有 thinking | 可折叠区块，默认折叠 |

### 3.2 ReferencePanel (参考资料面板)

**职责**：分屏模式下的辅助面板，用于显示参考资料

**功能**：
- 显示文件内容（只读）
- 显示 API 文档
- 显示代码片段
- 显示其他 Agent 的输出

**使用场景**：
| 场景 | 内容来源 |
|------|---------|
| 编码参考 | 项目文件、API 文档 |
| 代码审查 | 其他 Agent 的代码输出 |
| 调试 | 日志文件、错误信息 |

### 3.3 InputArea (输入区域)

**职责**：多行输入，支持 Markdown 编辑、历史记录、命令补全

**功能矩阵**：
| 功能 | 实现方式 | 快捷键 |
|------|---------|--------|
| 多行输入 | TextArea 原生 | 直接回车换行 |
| 发送 | 提交事件 | Ctrl+Enter |
| 清空 | 清除缓冲区 | Escape |
| 历史记录 | 历史栈 | ↑/↓ |
| 命令补全 | Completer | Tab |
| 编辑器打开 | $EDITOR | Ctrl+E |
| Markdown 预览 | 切换模式 | Ctrl+P |

**历史记录管理**：
- 最大保存 100 条
- 按时间倒序
- 支持前缀搜索

### 3.4 WorkspaceTab (Agent 工作区标签页)

**职责**：管理单个 Agent 的所有组件和状态，是**独立的工作单元**

**核心概念**：
- 每个 WorkspaceTab = 一个独立的 Agent 实例
- Agent 之间完全隔离，独立运行、独立 Token 预算
- 可以共享同一个模型实例（但消息历史独立）

**生命周期**：
```
创建 → 选择角色 → 初始化 Agent 状态
  ↓
激活 → 恢复焦点 → 刷新状态 → 继续任务
  ↓
停用 → 保存草稿 → 暂停流式（不丢失状态）
  ↓
关闭 → 归档 Agent → 保存 .mem 文件
```

**Agent 状态**：
```
AgentState:
  - workspace_id: str           # 工作区唯一 ID
  - agent_role: str             # 角色：pm/architect/developer/reviewer/tester
  - task_context: str           # 当前任务描述
  - status: active|waiting|paused|completed|error
  - messages: List[Message]     # 对话历史（独立）
  - token_used: int             # 已用 Token
  - token_budget: int           # 预算上限
  - streaming: bool             # 是否流式输出中
  - draft: str                  # 草稿内容
  - created_at: datetime        # 创建时间
  - last_active: datetime       # 最后活跃时间
```

**创建新 Agent 的交互流程**：

```
用户点击 [+] 或 Ctrl+N
    ↓
弹出角色选择器
┌─────────────────────────────┐
│  选择 Agent 角色            │
├─────────────────────────────┤
│  [PM] 项目经理              │
│  [Architect] 架构师         │
│  [Developer] 开发者         │
│  [Reviewer] 审查员          │
│  [Tester] 测试工程师        │
│  [自定义] 输入自定义提示词   │
└─────────────────────────────┘
    ↓
选择角色 → 创建 WorkspaceTab → 激活
```

**Agent 协同场景**：

| 场景 | Agent 配置 | 说明 |
|------|-----------|------|
| 需求分析 | PM Agent | 拆分功能、编写需求 |
| 设计评审 | Architect + PM | 架构设计 + 需求确认 |
| 编码实现 | Developer | 编写代码 |
| 代码审查 | Reviewer | 审查 Developer 的代码 |
| 测试验证 | Tester | 验证功能 |

### 3.5 Agent 间通信机制

**设计原则**：Agent 之间独立运行，通过**显式传递**实现协同

**通信方式**：

| 方式 | 场景 | 实现 |
|------|------|------|
| **复制粘贴** | 手动传递内容 | 用户从一个 Agent 复制，粘贴到另一个 Agent |
| **引用输出** | 引用其他 Agent 的输出 | `/ref <agent-id>` 命令，将目标 Agent 的最后输出插入当前对话 |
| **文件共享** | 通过项目文件协同 | Developer 写代码 → Reviewer 读取同一文件 |
| **任务委派** | 委派子任务 | `/delegate <agent-id> <task>` 命令，向目标 Agent 发送任务 |

**引用输出示例**：
```
# 在 Reviewer Agent 中
/ref dev-001

# 系统自动插入 Developer Agent 的最后输出：
> [引用自 Developer (dev-001)]
> ```python
> def login(username, password):
>     ...
> ```
```

**任务委派示例**：
```
# 在 PM Agent 中
/delegate dev-001 实现用户登录功能

# Developer Agent 收到消息：
> [PM (pm-001) 委派任务]
> 实现用户登录功能
```

**通信限制**：
- Agent 之间不能直接调用，必须通过用户或显式命令
- 防止 Agent 间无限循环调用
- 保持每个 Agent 的独立性和可控性

### 3.6 PermissionSidebar (权限侧边栏)

**职责**：非打断式权限确认

**布局**：
```
┌──────────────────────┐
│ 🔒 权限请求 (2)      │
├──────────────────────┤
│ [bash] rm -rf /tmp/* │
│ [允许] [拒绝]        │
│ [总是允许]           │
├──────────────────────┤
│ [write] config.yaml  │
│ [允许] [拒绝]        │
└──────────────────────┘
```

**交互流程**：
1. 工具请求 → 权限检查 → Ask 级别 → 添加到侧边栏
2. 用户点击 → 记录决策 → 执行/拒绝 → 移除请求
3. "总是允许" → 添加到 SessionOverrides

---

## 4. 交互设计

### 4.1 快捷键体系

**全局**：
| 快捷键 | 功能 |
|--------|------|
| Ctrl+Q | 退出应用 |
| F1 | 帮助面板 |
| F2 | 快捷键列表 |
| F3 | 历史面板 |
| F4 | 权限面板 |

**Agent 工作区（标签页）**：
| 快捷键 | 功能 |
|--------|------|
| **Ctrl+N** | **新建 Agent（创建新工作区）** |
| **Ctrl+W** | **关闭当前 Agent** |
| **Ctrl+Tab** | **切换到下一个 Agent** |
| **Ctrl+Shift+Tab** | **切换到上一个 Agent** |
| **Ctrl+1-9** | **跳转到第 N 个 Agent** |
| **Ctrl+Shift+K** | **关闭当前 Agent（确认）** |

**输入**：
| 快捷键 | 功能 |
|--------|------|
| Ctrl+Enter | 发送消息 |
| Escape | 清空输入 |
| ↑/↓ | 历史记录 |
| Tab | 命令补全 |
| Ctrl+E | 打开编辑器 |

**分屏（可选）**：
| 快捷键 | 功能 |
|--------|------|
| **Ctrl+S** | **切换分屏显示** |
| **Ctrl+\\** | **垂直/水平分屏切换** |
| Ctrl+H | 切换左侧焦点 |
| Ctrl+L | 切换右侧焦点 |

### 4.2 命令系统

**Agent 管理命令**：

| 命令 | 行为 |
|------|------|
| `/new` | 新建 Agent（弹出角色选择器） |
| `/new <role>` | 新建指定角色的 Agent |
| `/close` | 关闭当前 Agent |
| `/switch <n>` | 切换到第 N 个 Agent |
| `/list` | 列出所有 Agent |
| `/export` | 导出当前 Agent 对话为 Markdown |

**Agent 间通信命令**：

| 命令 | 行为 |
|------|------|
| `/ref <agent-id>` | 引用指定 Agent 的最后输出 |
| `/delegate <agent-id> <task>` | 向指定 Agent 委派任务 |
| `/share <file>` | 将文件路径分享给当前 Agent 作为上下文 |

**保留原有命令**：

| 命令 | 行为 |
|------|------|
| /help | 右侧面板显示帮助文档 |
| /quit | 退出应用 |
| /clear | 清空当前 Agent 历史 |
| /model | 右侧面板显示模型详情 |
| /perm | 打开权限侧边栏 |
| /lang | 切换语言 |

### 4.3 鼠标支持

- 点击标签页切换
- 拖拽分屏边界调整比例
- 点击代码块复制
- 点击链接打开
- 滚轮滚动历史

---

## 5. 数据流设计

### 5.1 多 Agent 工作流程

```
┌─────────────────────────────────────────────────────────────────┐
│  用户意图识别                                                    │
├─────────────────────────────────────────────────────────────────┤
│  新建 Agent？  →  创建 WorkspaceTab →  初始化 Agent             │
│  切换 Agent？  →  保存当前状态  →  激活目标 Agent                │
│  发送消息？    →  路由到当前 Agent →  处理请求                   │
│  关闭 Agent？  →  归档保存  →  清理资源                          │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 用户输入流程（单 Agent）

```
用户输入
    ↓
InputArea 提交
    ↓
命令判断
├─ /help → ResponsePanel 渲染
├─ /quit → App 退出
├─ /new → 创建新 Agent
├─ /close → 关闭当前 Agent
└─ 普通消息 → 继续
    ↓
当前 Agent 的 ChatHistory 添加用户消息
    ↓
AgentState 更新
    ↓
Model.chat_stream (异步)
    ↓
ResponsePanel 流式渲染 (节流)
    ↓
流式结束 → ChatHistory 添加助手消息
    ↓
TokenBudget 更新（当前 Agent 独立预算）
    ↓
检查阈值 → 触发压缩/归档（仅当前 Agent）
```

### 5.3 权限确认流程

```
工具调用请求
    ↓
PermissionManager.check
    ↓
权限级别判断
├─ Allow → 直接执行
├─ Deny → 直接拒绝
└─ Ask → 添加到侧边栏
    ↓
PermissionSidebar 显示请求
    ↓
用户点击按钮
    ↓
决策处理
├─ 允许 → 执行工具
├─ 拒绝 → 返回错误
└─ 总是允许 → 添加规则 + 执行
    ↓
移除请求
```

### 5.4 标签页切换流程

```
用户点击标签 / Ctrl+Tab
    ↓
当前 SessionTab 停用
├─ 保存草稿
├─ 暂停流式输出
└─ 更新时间戳
    ↓
目标 SessionTab 激活
├─ 恢复焦点
├─ 刷新 ChatHistory
└─ 恢复流式输出(如有)
    ↓
Header 更新状态显示
```

---

## 6. 性能优化策略

### 6.1 渲染优化

| 优化项 | 策略 | 预期效果 |
|--------|------|---------|
| 虚拟滚动 | 只渲染可见消息 | 内存降低 80% |
| 增量更新 | 新消息追加渲染 | 渲染时间 < 10ms |
| 流式节流 | 100ms 批量刷新 | CPU 降低 50% |
| Markdown 缓存 | 缓存渲染结果 | 重复渲染 < 1ms |

### 6.2 内存优化

- 最大保留 1000 条消息
- 单条消息最大 10KB
- 超出时自动归档到磁盘

### 6.3 异步架构

- 所有 I/O 操作异步化
- 模型调用加锁防止并发
- 流式渲染节流控制

---

## 7. 皮肤系统集成

### 7.1 Textual 主题映射

将现有 SkinConfig 转换为 Textual CSS：

```
SkinConfig.colors → Textual CSS variables
  banner_accent → $primary
  ui_accent → $accent
  banner_text → $text
  banner_dim → $dim
  ui_error → $error
  ui_ok → $success
```

### 7.2 皮肤 YAML 扩展

```yaml
# adds_cyberpunk.yaml
textual:
  header:
    background: "#6B1FB1"
    color: "#FF2975"
  input:
    border: "#FF2975"
    focus_border: "#00FFFF"
  response:
    code_theme: "monokai"
  tabs:
    active: "#FF2975"
    inactive: "#4400AA"
```

---

## 8. 迁移计划

### 8.1 阶段一：基础框架（1 周）

**目标**：搭建 Textual 应用骨架，支持多 Agent 工作区

**任务**：
- 创建 ADDSApp 主应用类（Agent 工作区管理器）
- 实现 AppState / AgentState 状态管理
- 实现基础布局（Header + TabbedContent + Footer）
- 集成现有皮肤系统
- 迁移 Agent Loop 到异步架构

**产出**：
- `scripts/tui/app.py`
- `scripts/tui/state.py`
- `scripts/tui/widgets/header.py`
- `scripts/tui/skin_adapter.py`

### 8.2 阶段二：Agent 工作区（1 周）

**目标**：实现独立 Agent 工作区（标签页）

**任务**：
- 实现 WorkspaceTab 组件（Agent 标签页）
- 实现 Agent 创建流程（角色选择器）
- 实现 Agent 状态管理（独立 Token 预算、消息历史）
- 实现标签页切换逻辑
- 实现 Agent 持久化（.mem 文件）

**产出**：
- `scripts/tui/widgets/workspace_tab.py`
- `scripts/tui/workspace_manager.py`
- `scripts/tui/widgets/task_panel.py`

### 8.3 阶段三：分屏与输入（1 周）

**目标**：实现分屏布局和增强输入

**任务**：
- 实现 SplitView 分屏组件（可选）
- 实现 TaskPanel 主任务面板
- 实现 ReferencePanel 参考资料面板
- 实现 InputArea 多行输入
- 集成 Markdown 渲染

**产出**：
- `scripts/tui/widgets/split_view.py`
- `scripts/tui/widgets/reference_panel.py`
- `scripts/tui/widgets/input_area.py`

### 8.4 阶段四：权限与优化（1 周）

**目标**：完善权限系统和性能优化

**任务**：
- 实现权限侧边栏（跨所有 Agent）
- 实现流式渲染优化
- 实现快捷键系统
- 性能测试与优化

**产出**：
- `scripts/tui/widgets/permission_sidebar.py`
- `scripts/tui/test_tui.py`

---

## 9. 文件结构

```
scripts/
├── adds.py                    # CLI 入口（保留）
├── adds_tui.py                # TUI 入口（新增）
└── tui/                       # TUI 模块（新增）
    ├── __init__.py
    ├── app.py                 # ADDSApp 主应用（Agent 工作区管理器）
    ├── state.py               # AppState / AgentState 状态管理
    ├── skin_adapter.py        # 皮肤适配器
    ├── workspace_manager.py   # Agent 工作区管理
    └── widgets/               # 组件目录
        ├── __init__.py
        ├── header.py          # 顶部状态栏
        ├── workspace_tab.py   # Agent 工作区标签页
        ├── task_panel.py      # 任务面板（主工作区）
        ├── reference_panel.py # 参考资料面板（分屏用）
        ├── input_area.py      # 输入区域
        ├── split_view.py      # 分屏容器
        └── permission_sidebar.py # 权限侧边栏
```

---

## 10. 兼容性考虑

### 10.1 向后兼容

- 保留 `adds.py` CLI 入口
- `adds start --tui` 启动 TUI 模式
- `adds start --classic` 启动经典模式
- 默认自动检测终端能力选择模式

### 10.2 终端要求

| 特性 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 终端 | 256 色 | True Color |
| 尺寸 | 80x24 | 120x36 |
| 字体 | 等宽字体 | Nerd Font |

### 10.3 降级策略

```
检测终端能力
├─ 非交互模式 → plain 模式
├─ 不支持 True Color → classic 模式
└─ 支持 → tui 模式
```

---

## 11. 验收标准

### 11.1 功能验收

**多 Agent 工作区**：
- [ ] 可以创建多个独立的 Agent（标签页）
- [ ] 每个 Agent 有独立的角色、任务、消息历史
- [ ] Agent 之间完全隔离，独立运行
- [ ] 可以切换不同 Agent
- [ ] 可以关闭 Agent
- [ ] Agent 间可以通过 `/ref` 引用输出
- [ ] Agent 间可以通过 `/delegate` 委派任务

**分屏功能（可选）**：
- [ ] 可以切换分屏显示
- [ ] 分屏可以用于参考资料、并行对比等场景

**基础功能**：
- [ ] 多行输入支持 Markdown 高亮
- [ ] 响应支持 Markdown 渲染
- [ ] 权限侧边栏非打断式确认
- [ ] 快捷键系统完整
- [ ] 皮肤主题正确应用

### 11.2 性能验收

- [ ] 启动时间 < 1 秒
- [ ] 流式输出延迟 < 100ms
- [ ] 1000 条消息滚动流畅
- [ ] 内存占用 < 200MB
- [ ] 5 个 Agent 并行时响应正常

### 11.3 兼容性验收

- [ ] macOS Terminal.app
- [ ] iTerm2
- [ ] VS Code 终端
- [ ] Windows Terminal
- [ ] Linux 终端

---

## 12. 设计变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.3 | 2026-04-11 | 术语统一：Session → Workspace，与 P0-2/P0-3 保持一致；新增多 Agent 并行设计；更新文件命名规则 |
| v1.2 | 2026-04-11 | 审查修复：统一组件命名（TaskPanel/ReferencePanel），添加 Agent 间通信机制，修复重复章节 |
| v1.1 | 2026-04-11 | 优化设计理念：标签页 = 独立 Agent 工作区，分屏 = 可选多任务视图 |
| v1.0 | 2026-04-11 | 初始版本 |

---

## 13. 术语统一说明

### 13.1 核心术语映射

| P0-5 术语 | P0-2/P0-3 术语 | 统一后术语 | 说明 |
|-----------|---------------|-----------|------|
| SessionTab | Session | **Workspace** | 一个独立的工作区，包含 Agent、消息历史、Token 预算 |
| SessionState | SessionState | **WorkspaceState** | 工作区的状态 |
| SessionManager | SessionManager | **WorkspaceManager** | 工作区管理器 |
| session_id | session_id | **workspace_id** | 工作区唯一标识 |
| .ses/.mem 文件 | .ses/.mem 文件 | 保持不变 | 文件格式不变，命名规则调整 |

### 13.2 文件命名规则调整

**原规则（P0-2）**：
```
.ai/sessions/
├── 20260409-153000.ses      # 时间戳命名
├── 20260409-153000.mem
```

**新规则（支持多 Agent 并行）**：
```
.ai/sessions/
├── index.mem                    # 全局记忆索引
├── staging.mem                  # P1: 记忆共振共享区
│
├── dev-001_20260409-153000.ses  # Dev Agent 的 Workspace
├── dev-001_20260409-153000.mem
├── dev-001_20260409-153000-ses1.log
│
├── pm-001_20260409-154000.ses   # PM Agent 的 Workspace
├── pm-001_20260409-154000.mem
│
└── reviewer-001_20260409-160000.ses  # Reviewer Agent 的 Workspace
```

**命名格式**：`{role}-{sequence}_{timestamp}.{ext}`

---

## 14. 多 Agent 并行设计

### 14.1 并行 Workspace 架构

```
┌─────────────────────────────────────────────────────────────────┐
│  AppState (全局状态)                                             │
│  ├── workspaces: Dict[workspace_id, WorkspaceState]             │
│  ├── active_workspace: workspace_id                              │
│  ├── shared_model: ModelInterface        # 共享模型实例           │
│  ├── permission_mode: PermissionMode     # 全局权限模式           │
│  └── global_token_budget: int            # 总 Token 使用量        │
└─────────────────────────────────────────────────────────────────┘
         │
         ├── Workspace 1 (PM Agent)
         │   ├── workspace_id: "pm-001"
         │   ├── agent_role: "pm"
         │   ├── token_budget: TokenBudget (独立)
         │   ├── memory_injector: RoleAwareMemoryInjector(role="pm")
         │   └── messages: List[Message]
         │
         ├── Workspace 2 (Dev Agent)
         │   ├── workspace_id: "dev-001"
         │   ├── agent_role: "dev"
         │   ├── token_budget: TokenBudget (独立)
         │   ├── memory_injector: RoleAwareMemoryInjector(role="dev")
         │   └── messages: List[Message]
         │
         └── Workspace 3 (Reviewer Agent)
             ├── workspace_id: "reviewer-001"
             ├── agent_role: "reviewer"
             ├── token_budget: TokenBudget (独立)
             ├── memory_injector: RoleAwareMemoryInjector(role="reviewer")
             └── messages: List[Message]
```

### 14.2 并行控制规则

| 规则 | 说明 |
|------|------|
| 模型共享 | 所有 Workspace 共享同一个 ModelInterface 实例，减少资源占用 |
| 预算独立 | 每个 Workspace 有独立的 TokenBudget，互不影响 |
| 记忆隔离 | 每个 Workspace 使用 RoleAwareMemoryInjector，只注入对应角色的记忆 |
| 权限全局 | 权限模式全局统一，但权限请求标记来源 Workspace |
| 流式互斥 | 同一时刻只有一个 Workspace 可以进行流式输出（模型调用加锁） |

### 14.3 Workspace 切换流程

```
用户切换 Workspace (Ctrl+Tab / 点击标签)
    │
    ▼
当前 Workspace 停用
├── 保存草稿到 workspace_state.draft
├── 暂停流式输出（如果正在输出）
├── 更新 last_active 时间戳
└── 释放模型调用锁
    │
    ▼
目标 Workspace 激活
├── 恢复焦点到 InputArea
├── 刷新 TaskPanel 显示
├── 恢复流式输出（如果有未完成的输出）
└── 获取模型调用锁
    │
    ▼
Header 更新状态显示
├── 当前 Agent 角色
├── 当前 Workspace 的 Token 使用量
└── 总 Token 使用量
```

### 14.4 与 P0-3 记忆系统的集成

**记忆注入时机**：

```
Workspace 创建时:
    │
    ▼
RoleAwareMemoryInjector.filter_memories_for_role(role=agent_role)
├── 从 index.mem 读取固定记忆
├── 过滤: role == "common" OR role == agent_role
└── 注入到 System Prompt
    │
    ▼
SystemPromptBuilder.build()
├── 静态部分（CORE_GUIDELINES.md）
├── 动态部分（角色提示词）
├── 角色化记忆（过滤后的固定记忆）
├── 上一个 Workspace 的摘要（如果有）
└── 强制复读区域（invalidation_count >= 2）
```

**记忆进化归属**：

```
Workspace 关闭时:
    │
    ▼
记忆进化评估
├── 反思协议: Agent 以 {role} 第一人称反思
├── 评估结果标记 role: {agent_role}
├── 写入 index.mem 时保留 role 字段
└── P1 阶段: 写入 index-{role}.mem
```

---

## 15. 与 P1/P2 路线图的关系

### 15.1 P1 阶段：记忆共振

**当前设计（P0）**：
- 每个 Workspace 独立运行，记忆隔离
- Agent 间通信通过显式命令（`/ref`, `/delegate`）

**P1 增强**：
- 引入 `staging.mem` 共享反思区
- Workspace 关闭时，反思结果写入 staging.mem
- 其他 Workspace 可以从 staging.mem 中"参考"协作习惯

```
P1 记忆共振流程:

Workspace 1 (Dev) 关闭
    │
    ▼
反思结果写入 staging.mem
├── "FFI 调用后需 Box::from_raw"
└── role: dev
    │
    ▼
Workspace 2 (Architect) 创建
    │
    ▼
从 staging.mem 读取 Dev 的反思
├── 形成"协作习惯": "Dev 会直接调用 FFI，我需要强制封装"
└── 写入 Architect 的记忆（role: architect）
```

### 15.2 P1 阶段：语义检索升级

**当前设计（P0）**：
- 使用 rg 关键词搜索
- 每个 Workspace 独立检索

**P1 增强**：
- 引入 VectorMemoryRetriever（LanceDB）
- 向量检索 + rg 检索混合
- 跨 Workspace 的语义检索（需要权限）

### 15.3 P2 阶段：Fork 子 Agent

**当前设计（P0）**：
- 用户手动创建新 Workspace
- Workspace 之间无继承关系

**P2 增强**：
- 支持 `/fork` 命令，从当前 Workspace 派生子 Workspace
- 子 Workspace 继承父 Workspace 的消息历史（可选）
- 子 Workspace 有独立的 Token 预算

```
P2 Fork 流程:

Workspace 1 (Dev) 运行中
    │
    ▼
用户执行 /fork --role reviewer
    │
    ▼
创建 Workspace 2 (Reviewer)
├── 继承 Workspace 1 的最近 N 条��息
├── 继承 Workspace 1 的当前代码上下文
├── 独立的 Token 预算
└── 标记 parent_workspace: "dev-001"
```

---

**文档版本**：v1.3  
**创建日期**：2026-04-11  
**状态**：设计阶段

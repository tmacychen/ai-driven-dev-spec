# Project Progress Logs

## Current Focus
TUI 菜单栏功能（tui-menubar）— 已完成

## Overall Status
- ✅ Completed: 9
- 🔄 In Progress: 0
- ⏳ Pending: 1 (P0-5 阶段二~四剩余：持久化、Markdown 渲染、流式优化)
- ⚠️ Blocked: 0
- 🔴 Regression: 0

## Next Step
P0-5 阶段二：Agent 工作区完善（WorkspaceTab 持久化集成、Markdown 渲染）

---

## 待办列表

### P0 实现状态总览

| 模块 | 设计文档 | 实现状态 | 测试状态 |
|------|---------|---------|---------|
| P0-1 模型调用层 | ✅ 完成 | ✅ 完成 | ✅ 通过 |
| P0-2 上下文压缩 | ✅ 完成 | ✅ 完成 | ✅ 通过 |
| P0-3 记忆系统 | ✅ 完成 | ✅ 完成 | ✅ 通过 |
| P0-4 权限系统 | ✅ 完成 | ✅ 完成 | ✅ 通过 |
| P0-5 TUI 重构 | ✅ 完成 | 🔄 进行中 | - |
| TUI 菜单栏 | ✅ 完成 | ✅ 完成 | ✅ 44 tests |
| P0 集成测试 | - | ✅ 完成 | ✅ 225 tests |

### P0-5 TUI 重构待办事项

#### 阶段一：基础框架（预估 1 周）

| 任务 | 文件 | 状态 |
|------|------|------|
| 创建 ADDSApp 主应用类 | `scripts/tui/app.py` | ✅ |
| 实现 AppState/WorkspaceState 状态管理 | `scripts/tui/state.py` | ✅ |
| 实现基础布局（Header + TabbedContent + Footer） | `scripts/tui/widgets/header.py` | ✅ |
| 集成现有皮肤系统 | `scripts/tui/skin_adapter.py` | ✅ |
| 迁移 Agent Loop 到异步架构 | `scripts/tui/app.py` | ✅ |

#### 阶段二：Agent 工作区（预估 1 周）

| 任务 | 文件 | 状态 |
|------|------|------|
| 实现 WorkspaceTab 组件 | `scripts/tui/widgets/workspace_tab.py` | ✅ |
| 实现 Agent 创建流程（角色选择器） | `scripts/tui/widgets/workspace_tab.py` | ✅ |
| 实现 Agent 状态管理（独立 Token 预算） | `scripts/tui/workspace_manager.py` | ✅ |
| 实现标签页切换逻辑 | `scripts/tui/widgets/workspace_tab.py` | ✅ |
| 实现 Agent 持久化（.mem 文件） | `scripts/tui/workspace_manager.py` | ⏳ |

#### 阶段三：分屏与输入（预估 1 周）

| 任务 | 文件 | 状态 |
|------|------|------|
| 实现 SplitView 分屏组件 | `scripts/tui/widgets/split_view.py` | ✅ |
| 实现 TaskPanel 主任务面板 | `scripts/tui/widgets/task_panel.py` | ✅ |
| 实现 ReferencePanel 参考资料面板 | `scripts/tui/widgets/reference_panel.py` | ✅ |
| 实现 InputArea 多行输入 | `scripts/tui/widgets/input_area.py` | ✅ |
| 集成 Markdown 渲染 | `scripts/tui/widgets/task_panel.py` | ⏳ |

#### 阶段四：权限与优化（预估 1 周）

| 任务 | 文件 | 状态 |
|------|------|------|
| 实现权限侧边栏 | `scripts/tui/widgets/permission_sidebar.py` | ✅ |
| 实现流式渲染优化 | `scripts/tui/widgets/task_panel.py` | ⏳ |
| 实现快捷键系统 | `scripts/tui/app.py` | ✅ |
| 性能测试与优化 | `scripts/tui/test_tui.py` | ⏳ |

### P1 待办事项（P0 完成后）

| 任务 | 说明 | 状态 |
|------|------|------|
| 技能渐进式披露 | Level 0-2 技能加载机制 | ⏳ |
| Agent Loop 韧性增强 | 7 种终止条件 + 5 种继续条件 | ⏳ |
| 记忆共振 | staging.mem 跨角色二次进化 | ⏳ |
| 语义检索升级 | VectorMemoryRetriever (LanceDB) | ⏳ |

### P2 待办事项（P1 完成后）

| 任务 | 说明 | 状态 |
|------|------|------|
| 执行后端隔离 | Docker/SSH/远程沙箱 | ⏳ |
| 多平台通信网关 | 多平台集成 | ⏳ |
| Fork 子 Agent 路径 | `/fork` 命令 | ⏳ |
| 定时调度系统 | 自动化任务 | ⏳ |

---

## 设计变更记录

### 2026-04-11 P0-5 TUI 重构设计 + 术语统一

**变更内容**：
1. 新增 P0-5 TUI 重构设计文档（~700 行）
2. 术语统一：Session → Workspace
3. 文件命名规则调整：`{role}-{sequence}_{timestamp}.{ext}`
4. 新增多 Agent 并行架构设计
5. 新增 Agent 间通信机制（`/ref`, `/delegate`）
6. 更新 P0-2、P0-3、P0-integration、P1-P2-outline 文档

**影响范围**：
- P0-2：文件命名规则、术语
- P0-3：多 Agent 支持、记忆注入时机
- P0-integration：数据流全景图、文件目录
- P1-P2：记忆共振与 Workspace 架构集成

---

## Session History

### [2026-04-14] Session — TUI 菜单栏功能实现

**Agent**: Developer (tui-menubar)

**Tasks Completed**:
- 新增 `scripts/tui/widgets/menubar.py` — 菜单栏完整实现
  - `MenuEntry` dataclass + `MENU_DEFINITIONS` + `SKIN_NAMES` 数据模型
  - `load_skin_setting` / `save_skin_setting` 皮肤持久化工具函数
  - `MenuBar` / `MenuBarItem` — 顶部菜单栏组件，支持 Tab/Alt 激活
  - `DropdownOverlay` (ModalScreen) — 下拉菜单覆盖层，支持左右键切换菜单、ESC 关闭
  - `DropdownMenu` / `DropdownItem` / `DropdownSeparator` — 菜单内容组件
  - `AgentStatusScreen` (ModalScreen) — Agent 状态居中对话框
  - `InfoScreen` (ModalScreen) — 通用可复制信息对话框（帮助/关于）
- 新增 `scripts/tui/widgets/shortcut_bar.py` — 底部快捷键提示栏（替代 Footer）
- 修改 `scripts/tui/app.py`
  - 集成 MenuBar + ShortcutBar
  - 新增 action: `action_switch_skin`, `action_list_roles`, `action_agent_status`, `action_about`, `action_toggle_split`, `action_focus_menubar`
  - 快捷键改为 Ctrl 系列（移除 F1/F4 功能键）：Ctrl+P 权限面板，Ctrl+H 帮助
  - `on_mount` 读取持久化皮肤并应用
  - `on_menu_bar_open_dropdown` 处理菜单展开消息
- 修改 `scripts/tui/widgets/input_area.py` — 移除 ESC 清空绑定
- 新增 `scripts/test_menubar.py` — 44 个测试全部通过
- 更新 `.gitignore` — 添加 Python 标准忽略规则，加入 `.kiro/`

**Bug 修复**:
- `call_action` 不存在 → 改为 `getattr(app, f"action_{action}")()`
- `quit` action 无效 → 特殊处理为 `self.app.exit()`
- AgentStatusScreen 不居中 → CSS `align` 移到 Screen 层
- 下拉菜单宽度撑满屏幕 → `DropdownItem` 改为 `width: auto`
- 下拉菜单键盘导航失效 → `DropdownMenu.can_focus=True` + `on_mount` 时 focus

**验证**:
- ✅ test_menubar.py: 44 个测试全部通过
- ✅ 实际运行验证：菜单点击、键盘导航、皮肤切换、退出功能均正常

**Handoff Notes for Next Session**:
> TUI 菜单栏功能完成。下一步：P0-5 阶段二剩余任务（Agent 持久化、Markdown 渲染、流式渲染优化）。



**Agent**: Developer (集成测试)

**Tasks Completed**:
- 编写 `scripts/test_p0_integration.py` — P0 四层协同集成测试
  - 场景 1: 四层模块初始化与数据流串联（3 tests）
  - 场景 2: 压缩触发与 Session 归档（5 tests）
  - 场景 3: 记忆注入与 SystemPromptBuilder（4 tests）
  - 场景 4: 权限拦截与决策流转（4 tests）
  - 场景 5: 完整会话生命周期（3 tests）
  - 场景 6: 跨层数据一致性（6 tests）
- 修复 `scripts/permission_manager.py` Bug:
  - plan 模式下 `_record_result()` 未被调用，导致死循环防护失效
  - 原因: plan 分支只调用了 `_log_decision()`，遗漏了 `_record_result()`
- 更新 `scripts/README.md` + `README-en.md` — 反映 P0 架构实现状态
- 删除过期文件 `CLEANUP_SUMMARY.md`

**验证**:
- ✅ test_p0_integration.py: 25 个集成测试全部通过
- ✅ test_p0_2 + test_p0_3 + test_p0_4 + test_p0_integration: 225 个测试全部通过
- ✅ 发现并修复 permission_manager.py plan 模式 cooldown Bug

**Handoff Notes for Next Session**:
> P0 集成测试完成，发现 1 个 Bug 并已修复（plan 模式死循环防护失效）。P0 四层模块全部验证通过，225 个测试。下一步：进入 P1 阶段。

---

### [2026-04-10 17:30] Session — P0-4 权限管理器实现

**Agent**: Developer (权限层实现)

**Tasks Completed**:
- 实现 `scripts/permission_manager.py` — 权限管理器
  - PermissionLevel 枚举: ALLOW / ASK / DENY
  - PermissionMode 枚举: DEFAULT / PLAN / AUTO / BYPASS
  - PermissionDecision 数据类: 决策结果 + 属性判断 + 格式化
  - match_rule() 规则匹配: tool(command_pattern) 格式 + fnmatch 通配符
  - CooldownState 死循环防护: 连续拒绝 3 次后冷却 30 秒
  - SessionOverrides 会话级覆盖: 运行时添加允许/拒绝规则
  - PermissionManager 核心逻辑:
    - default 模式: 按规则匹配（deny > ask > allow > 保守ask）
    - plan 模式: 只读放行，写操作拒绝
    - auto 模式: AI 分类器（内置高风险/低风险模式）
    - bypass 模式: 全部放行（危险）
  - 从 .ai/settings.json 和 ~/.adds/settings.json 加载规则
  - 交互式确认 confirm_action_with_session() + 会话级覆盖
  - parse_tool_command() 工具命令解析
  - create_permission_manager() 便捷函数
- 修改 `scripts/agent_loop.py` — 集成权限管理器
  - 导入 PermissionManager + confirm_action_with_session
  - 构造函数增加 permission_mode 参数
  - 新增 /perm 命令: 显示权限状态 + 模式切换
  - 命令补全增加 /perm
- 修改 `scripts/adds.py` — CLI 集成
  - start 命令增加 --perm 参数
  - 新增 perm 子命令: status/rules/mode
  - perm_command() 方法实现
- 更新 `.ai/settings.json` — 完善权限配置
  - 新增 bash(git branch*) 到 allow 列表
  - 修复 bash(su*) → bash(su *) 防止误匹配

**验证**:
- ✅ test_p0_4.py: 69 个测试全部通过
- ✅ test_p0_2 + test_p0_3 + test_p0_4: 200 个测试全部通过

**Handoff Notes for Next Session**:
> P0-4 权限管理器实现完成，P0 全部四层（模型/压缩/记忆/权限）已全部实现。下一步：P0 全流程集成测试，验证四层模块协同工作；然后进入 P1 阶段。

---

### [2026-04-10 15:27] Session — P0-2 上下文压缩层实现

**Agent**: Developer (压缩层实现)

**Tasks Completed**:
- 实现 `scripts/token_budget.py` — Token 预算管理器
  - TokenBudget 类：预算分配、追踪、触发判断
  - estimate_tokens() 混合中英文 Token 估算
  - load_budget_config() 从 settings.json 加载配置
  - Layer1/Layer2/Warn/HardLimit 触发阈值
  - 预算分配比例: SP 15% + Memory 10% + History 55% + Tool 15% + Reserve 5%
- 实现 `scripts/session_manager.py` — Session 文件管理
  - SessionManager 类：创建/读取/归档/恢复 Session
  - SessionHeader / MemoryHeader 数据结构
  - 链式 Session 结构（Prev/Next 指针）
  - .ses/.log/.mem 文件格式读写
  - reconstruct_full_session() 合并 .ses + .log
  - get_prev_session_summary() 获取上一个 session 摘要
  - 时间戳冲突处理（同一秒创建多个 session）
- 实现 `scripts/summary_decision_engine.py` — 摘要策略决策引擎
  - SummaryStrategy 枚举: KEEP_FULL / TOOL_FILTER / LLM_ANALYZE / HYBRID
  - SummaryDecisionEngine 类：为每条消息决定摘要策略
  - has_error_signals() 错误信号检测（排除测试结果中的 "0 failed"）
  - apply_tool_filter() 工具过滤规则（pytest/git/文件内容）
  - is_redundant_message() 冗余消息检测
  - LAYER2_SUMMARY_PROMPT LLM 摘要 Prompt 模板
- 实现 `scripts/context_compactor.py` — 两层压缩引擎
  - ContextCompactor 类：Layer1 实时压缩 + Layer2 归档压缩
  - Layer1: 工具输出超阈值 → 保存 .log + 替换为摘要
  - Layer2: LLM 生成结构化摘要 → .mem 归档 + .ses 摘要版
  - 错误信号永不压缩（KEEP_FULL 最高优先级）
  - create_compactor() 便捷函数
- 修改 `scripts/agent_loop.py` — 集成 Token 预算和压缩
  - 导入 TokenBudget, SessionManager, ContextCompactor
  - AgentLoop 构造函数增加 project_root/agent_role/feature 参数
  - _init_session_budget() 初始化 session 和预算
  - _archive_session() Session 结束时归档
  - /model 命令显示 Token 使用情况
  - 预算警告注入对话
- 修改 `scripts/system_prompt_builder.py` — 注入上一个 session 摘要
  - build_system_prompt() 增加 prev_session_summary 上下文
  - _build_prev_session_section() 构建链式上下文段落
- 修改 `scripts/adds.py` — CLI 集成
  - start 命令传入 project_root/agent_role/feature
  - 新增 session 子命令: list/status/restore/logs
  - init 命令增加 memories/ 目录

**验证**:
- ✅ token_budget 单元测试通过（预算分配、阈值判断、Token 估算）
- ✅ summary_decision_engine 单元测试通过（KEEP_FULL/TOOL_FILTER/LLM_ANALYZE 策略）
- ✅ session_manager 单元测试通过（创建/归档/恢复/链式指针/摘要获取）
- ✅ context_compactor 单元测试通过（Layer1 压缩/Layer2 归档/统计）
- ✅ P0-2 完整集成测试通过（多轮对话 + 压缩 + 归档 + prev summary）
- ✅ 所有模块导入正常
- ✅ system_prompt_builder prev session 注入正常

**Handoff Notes for Next Session**:
> P0-2 上下文压缩层实现完成。下一步 P0-3：实现记忆系统（memory_manager.py, memory_conflict_detector.py, memory_retriever.py, memory_detox.py, consistency_guard.py, role_memory_injector.py, memory_cli.py, index_priority_sorter.py）。这是最复杂的模块，包含记忆进化/排毒/角色化/反思协议/回归警报/注意力热点/晋升仪式等子功能。

---

### [2026-04-10 10:00] Session — P0-1 模型调用层实现

**Agent**: Developer (模型层实现)

**Tasks Completed**:
- 实现 `scripts/model/` 完整目录结构（9 个文件）
- `base.py`: ModelInterface 抽象基类 + ModelResponse 统一响应
- `factory.py`: ModelFactory 交互式模型选择工厂
- `api_adapter.py`: API 调用适配器（基于 openai 库）
- `cli_adapter.py`: CLI 工具适配器（基于 CLIProfile + TaskDispatcher）
- `sdk_adapter.py`: SDK 适配器（基于 codebuddy-agent-sdk）
- `task_dispatcher.py`: CLI 任务派发器 + CLIProfile 配置描述
- `skill_generator.py`: 技能自动生成器（从文档提取技能描述）
- `providers/minimax.py`: MiniMax Provider 配置（API + CLI）
- `providers/codebuddy.py`: Codebuddy Provider 配置（CLI + SDK）
- `providers/registry.py`: Provider 注册表（可扩展）
- 修改 `adds.py`: start 命令集成模型选择
- 修改 `agent_loop.py`: 注入 ModelInterface，Developer Agent 可调用模型
- 新增 `requirements.txt`: 添加 openai 依赖

**验证**:
- ✅ Model layer imports OK
- ✅ Provider registry OK（检测到 MiniMax CLI + Codebuddy CLI）
- ✅ APIAdapter / CLIAdapter / SDKAdapter 单元测试通过
- ✅ SkillGenerator 提取 6 个 Codebuddy 技能
- ✅ adds.py / agent_loop.py 集成导入测试通过

**Handoff Notes for Next Session**:
> P0-1 模型调用层实现完成。下一步 P0-2：实现上下文压缩层（context_compactor.py, token_budget.py, session_manager.py, summary_decision_engine.py）。

---

### [2026-04-10 09:33] Session — P0 架构设计与项目调整

**Agent**: Architect (架构设计 + 项目调整)

**Tasks Completed**:
- 全面阅读 P0 roadmap（6 个文档，共 ~3000 行）
- 阅读当前项目全部文档和代码结构
- 设计 P0 四层架构：CLI 入口层 → Agent Loop 调度层 → 核心模块层（模型/压缩/记忆/权限） → 基础设施层
- 更新 architecture.md 反映 P0 架构设计
- 将参考资料归档到 docs/references/（不修改）
- 更新文档结构：specification.md、guide/ 等
- 创建 docs/references/ 目录，移入研究报告

**架构设计要点**:
- 模型层 (model/)：API/CLI/SDK 三模式 + TaskDispatcher 统一协议
- 压缩层：两层压缩 + TokenBudget + SessionManager
- 记忆层：两层记忆 + 进化/排毒/角色化 + ConsistencyGuard
- 权限层：三级权限 + 死循环防护

**文件调整**:
- 新建: docs/references/ 目录
- 移动: Claude_Code_架构白皮书研究报告.md → docs/references/
- 移动: Hermes_Agent_研究报告.md → docs/references/
- 更新: .ai/architecture.md — 完整 P0 架构设计
- 归档: docs/improvement-plan.md → docs/references/ (被 roadmap 替代)
- 更新: docs/specification.md — 反映 P0 架构
- 更新: docs/guide/ — 反映新架构

**Handoff Notes for Next Session**:
> P0 架构设计完成。下一步按 Phase 1 实施：先实现 model/ 目录下的模型调用层（base.py → factory.py → api_adapter.py → cli_adapter.py → providers/），然后集成到 adds.py 和 agent_loop.py。

---

### [2026-04-09 18:07] Session — 改进规划

**Agent**: Main (知识学习 + 规划)

**知识来源**:
- Claude Code 架构白皮书研究报告
- Hermes Agent 研究报告

**Tasks Completed**:
- 学习两篇研究文档并提炼核心知识
- 创建改进路线图（.ai/improvement_roadmap.md）
- 创建记忆系统基础文件
- 创建项目配置文件：.ai/settings.json

**Handoff Notes for Next Session**:
> 按 improvement_roadmap.md Phase 1 执行

---

### [YYYY-MM-DD HH:MM] Session #1 — Initialization

**Agent**: Initializer Agent

**Tasks Completed**:
- None yet.

**Environment Status**:
- [ ] init.sh verified
- [ ] Dependencies installed
- [ ] Services running

**Handoff Notes for Next Session**:
> Start by running the Initializer Agent to generate the full feature list from the app specification.

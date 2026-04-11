# P0 整体架构集成

> 📋 [返回总览](README.md) | [← P0-4: 命令批准](P0-4-permission.md) | [P0-5: TUI 重构](P0-5-tui-redesign.md) | [P1/P2 概要 →](P1-P2-outline.md)

---

### 数据流全景（P0-5 多 Workspace 架构）

```
用户启动 adds start --tui
    │
    ▼
┌─ ModelFactory.select_model() ──────────────────────┐
│  交互式选择: API/CLI + Provider + Model             │
│  → 返回 ModelInterface 实例（全局共享）             │
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
┌─ ADDSApp 初始化 ──────────────────────────────────┐
│  1. 加载皮肤配置                                    │
│  2. 初始化 AppState（全局状态）                     │
│  3. 创建第一个 Workspace（默认 PM Agent）           │
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
┌─ Workspace 初始化 ──────────────────────────────────┐
│  1. 读取 index.mem → 角色感知过滤注入固定记忆+索引线索 │  ← P0-3/P0-5 协同
│  2. 读取上一个 .mem → 注入结构化摘要 + 链式指针    │
│  3. 检测冲突: SP vs 固定记忆 → 自动以 SP 为准       │
│     用户最新 vs 固定记忆 → Recency Bias 自动解决     │
│     SP vs 用户最新 → 必须暂停确认                    │
│  4. 构建 System Prompt（静态+动态+记忆+摘要+强制复读）│
│  5. 初始化 TokenBudget(context_window) — 独立预算   │  ← P0-5: 每个 Workspace 独立
│  6. 构建代码热度地图(code_heat_map)                 │
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
┌─ Agent Loop（多 Workspace 并行）──────────────────┐
│  while True:                                      │
│    ① 上下文预处理（当前 Workspace）                 │
│       - 检查 TokenBudget（独立预算）               │
│       - if utilization > 50%: Layer 1 压缩        │
│       - if utilization > 80%: Layer 2 归档 → 新Workspace │
│    ② 路由决策 → 选择 Agent                        │
│    ③ 执行 Agent（获取模型调用锁）                  │  ← P0-5: 流式互斥
│       - 权限检查 (PermissionManager)               │
│       - 调用模型 (ModelInterface.chat())           │
│       - 工具输出 → 检查阈值 → 保存 .log            │
│    ④ 状态更新（锁存保护）                          │
│    ⑤ 终止判定                                     │
│    ⑥ Workspace 切换检测（Ctrl+Tab / 点击标签）     │  ← P0-5 新增
│       - 保存草稿 → 暂停流式 → 释放锁               │
│       - 激活目标 Workspace → 获取锁 → 恢复流式     │
└─────���──────────────┬───────────────────────────────┘
                     │ Workspace 结束
                     ▼
┌─ 记忆保存与进化 ──────────────────────────────────┐
│  1. Layer 1 workspace → 合并 log → 生成 .mem        │
│  2. LLM 生成结构化摘要 → 写入 .mem (APPEND-ONLY)  │
│  3. 回写 .ses 为摘要版 + 链式指针                  │
│  4. 成功 workspace → 反思协议(角色第一人称) → 升级固定记忆 │
│  5. 失败 workspace → 记忆排毒（验证性失效检测）      │
│  6. 回归警报 → ConsistencyGuard 元诊断(三层防御失效) │
│  7. 低置信度升级 → 强模型复核                       │
│  8. 轻量级冲突扫描 → 发现可疑 → 标记待审           │
│  9. 固定记忆冲突检测 → Recency Bias 自动/人工解决  │
│  10. 容量超限 → 优先级排序(含负反馈+code_heat) → 降级 │
│  11. 里程碑检测(Git Tag/核心模块重构/连续失败)      │
│  12. 晋升仪式(--promote) → 临时记忆→长期直觉        │
│  13. 角色感知注入(role字段过滤) → 精准上下文        │
│  14. 强制复读(invalidation>=2) → SP 顶部警示       │
│  15. 更新记忆索引                                   │
│  16. P1: 写入 staging.mem → 触发记忆共振           │  ← P1 新增
└──────────────────────────────────────────────────┘
```

### 完整文件目录（P0-5 更新）

```
.ai/
├── feature_list.md              # 功能状态（不变）
├── progress.md                  # 进度日志（不变）
├── architecture.md              # 架构文档（不变）
├── CORE_GUIDELINES.md           # 核心规范（不变）
├── compliance_report.json       # 合规报告（不变）
├── settings.json                # 权限+模型+压缩配置
├── improvement_roadmap.md       # 本文件
│
├── sessions/                    # Workspace + 记忆文件
│   ├── index.mem                # 记忆索引（线索+固定记忆，Page 1）
│   ├── index-prev.mem           # 记忆索引（降级区，Page 2）
│   ├── staging.mem              # P1: 记忆共振共享区
│   │
│   ├── dev-001_20260409-153000.ses      # Dev Agent Workspace
│   ├── dev-001_20260409-153000-ses1.log # 工具输出 log
│   ├── dev-001_20260409-153000.mem      # 记忆归档
│   │
│   ├── pm-001_20260409-154000.ses       # PM Agent Workspace
│   ├── pm-001_20260409-154000.mem
│   │
│   └── reviewer-001_20260409-160000.ses  # Reviewer Agent Workspace
│
└── memories/                    # 技能库 + 角色化记忆（P1 物理拆分）
    ├── SKILLS/
    │   └── README.md
    ├── dev/                     # P1: Dev Agent 角色记忆
    │   └── index.mem
    ├── architect/               # P1: Architect Agent 角色记忆
    │   └── index.mem
    └── qa/                      # P1: QA Agent 角色记忆
        └── index.mem

scripts/
├── adds.py                      # CLI 主工具（修改：集成模型选择、workspace 管理）
├── adds_tui.py                  # TUI 入口（新增：P0-5）           │
├── agent_loop.py                # Agent Loop（修改：集成模型、压缩、权限）
├── agents.py                    # 5 个代理实现（不变）
├── compliance_tracker.py        # 合规追踪（不变）
├── system_prompt_builder.py     # 提示词构建（修改：注入记忆+摘要）
│
├── model/                       # 新增：模型调用层
│   ├── __init__.py
│   ├── base.py                  # ModelInterface 抽象基类
│   ├── factory.py               # 交互式模型工厂
│   ├── api_adapter.py           # API 调用适配器
│   ├── cli_adapter.py           # CLI 工具适配器（基于 CLIProfile）
│   ├── sdk_adapter.py           # SDK 适配器（codebuddy-agent-sdk）
│   ├── task_dispatcher.py       # CLI 任务派发器（统一协议）
│   ├── skill_generator.py       # 技能自动生成器（从文档提取）
│   └── providers/
│       ├── __init__.py
│       ├── minimax.py           # MiniMax Provider
│       ├── codebuddy.py         # Codebuddy Provider（CLI+SDK）
│       └── registry.py          # Provider 注册表
│
├── context_compactor.py         # 新增：两层压缩引擎
├── summary_decision_engine.py   # 新增：摘要策略决策引擎
├── token_budget.py              # 新增：Token 预算管理器
├── session_manager.py           # 新增：Session 文件管理（重命名为 workspace_manager.py）
├── memory_manager.py            # 新增：记忆管理器
├── memory_conflict_detector.py  # 新增：记忆冲突检测器（含 auto_resolve）
├── memory_retriever.py          # 新增：记忆检索接口（P0 rg, P1 向量占位）
├── memory_detox.py              # 新增：记忆排毒引擎（失效+惩罚+冲突扫描）
├── consistency_guard.py         # 新增：一致性守护（回归警报+元诊断+强制复读）
├── role_memory_injector.py      # 新增：角色感知记忆注入器
├── memory_cli.py                # 新增：CLI 记忆管理子命令
├── index_priority_sorter.py     # 新增：index.mem 优先级排序器（含负反馈）
├── permission_manager.py        # 新增：权限管理器
│
├── tui/                         # 新增：TUI 模块（P0-5）
│   ├── __init__.py
│   ├── app.py                   # ADDSApp 主应用（Agent 工作区管理器）
│   ├── state.py                 # AppState / WorkspaceState 状态管理
│   ├── skin_adapter.py          # 皮肤适配器
│   ├── workspace_manager.py     # Workspace 管理器
│   └── widgets/                 # 组件目录
│       ├── __init__.py
│       ├── header.py            # 顶部状态栏
│       ├── workspace_tab.py     # Agent 工作区标签页
│       ├── task_panel.py        # 任务面板（主工作区）
│       ├── reference_panel.py   # 参考资料面板（分屏用）
│       ├── input_area.py        # 输入区域
│       ├── split_view.py        # 分屏容器
│       └── permission_sidebar.py # 权限侧边栏
│
└── test_integration.py          # 集成测试（更新）
```

---

### P0-5 TUI 重构相关文档

详见 [P0-5: TUI 重构设计](P0-5-tui-redesign.md)，包含：
- 多 Workspace 架构设计
- 分屏与交互设计
- Agent 间通信机制
- 与 P1/P2 路线图的关系


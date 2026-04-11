# Architecture Document

> ADDS P0 架构设计 — 基于改进路线图的完整架构

**版本**: P0
**最后更新**: 2026-04-10

---

## Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| CLI | Python 3.9+ (Click/argparse) | `adds.py` 主入口 |
| Model | OpenAI SDK + CLI Adapter | 多 Provider 支持（MiniMax, Codebuddy） |
| Memory | Markdown 文件 (.mem) | 纯文本存储，rg 检索 |
| Compression | 两层压缩引擎 | Layer 1 规则过滤 + Layer 2 LLM 摘要 |
| Permission | 三级权限模型 | Allow / Ask / Deny |
| Testing | pytest | 集成测试 + 单元测试 |

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    CLI 入口层                             │
│  adds.py — init/start/status/route/mem/session 命令       │
├──────────────────────────────────────────────────────────┤
│                 Agent Loop 调度层                          │
│  agent_loop.py — 状态机 + 路由 + 迭代控制                  │
│  system_prompt_builder.py — 分段式 SP 构建 + 记忆注入       │
│  agents.py — 5 个 Agent 实现                              │
│  compliance_tracker.py — 合规追踪                          │
├────────┬──────────┬─────────────┬─────────────────────────┤
│ 模型层  │ 压缩层   │ 记忆层       │ 权限层                  │
│        │          │             │                         │
│ model/ │ context_ │ memory_     │ permission_             │
│  base  │ compactor│ manager     │  manager.py             │
│  api_  │  .py     │  .py        │                         │
│  cli_  │ token_   │ memory_     │                         │
│  sdk_  │  budget  │  conflict_  │                         │
│  task_ │  .py     │  detector   │                         │
│  dis-  │ session_ │ memory_     │                         │
│  patch │  manager │  retriever  │                         │
│  er.py │  .py     │ memory_     │                         │
│  fact- │ summary_ │  detox.py  │                         │
│  ory   │  decision│ consistency│                         │
│  skill │  _engine │  _guard.py │                         │
│  _gen  │  .py     │ role_      │                         │
│  prov- │          │  memory_   │                         │
│  iders │          │  injector  │                         │
│        │          │ index_     │                         │
│        │          │  priority_ │                         │
│        │          │  sorter.py │                         │
│        │          │ memory_cli │                         │
├────────┴──────────┴─────────────┴─────────────────────────┤
│                    基础设施层                               │
│  .ai/sessions/ — .ses/.log/.mem 文件存储                    │
│  .ai/memories/ — SKILLS/ + 角色化记忆 (P1)                  │
│  .ai/settings.json — 全局配置                               │
└──────────────────────────────────────────────────────────┘
```

---

## Core Data Flow

```
用户启动 adds start
    │
    ▼
ModelFactory.select_model()
  → 交互式选择 API/CLI/SDK + Provider + Model
  → 返回 ModelInterface 实例
    │
    ▼
Session 初始化
  1. 读取 index.mem → 角色感知过滤注入固定记忆 + 索引线索
  2. 读取上一个 .mem → 注入结构化摘要 + 链式指针
  3. 检测冲突: SP vs 固定记忆 → 自动以 SP 为准
  4. 构建 System Prompt（静态 + 动态 + 记忆 + 摘要 + 强制复读）
  5. 初始化 TokenBudget(context_window)
  6. 构建代码热度地图 (code_heat_map)
    │
    ▼
Agent Loop
  while True:
    ① 上下文预处理
       - 检查 TokenBudget
       - if utilization > 50%: Layer 1 压缩
       - if utilization > 80%: Layer 2 归档 → 新 session
    ② 路由决策 → 选择 Agent
    ③ 执行 Agent
       - 权限检查 (PermissionManager)
       - 调用模型 (ModelInterface.chat())
       - 工具输出 → 检查阈值 → 保存 .log
    ④ 状态更新（锁存保护）
    ⑤ 终止判定
    │
    ▼
记忆保存与进化
  1. Layer 1 session → 合并 log → 生成 .mem
  2. LLM 生成结构化摘要 → 写入 .mem (APPEND-ONLY)
  3. 回写 .ses 为摘要版 + 链式指针
  4. 成功 session → 反思协议(角色第一人称) → 升级固定记忆
  5. 失败 session → 记忆排毒（验证性失效检测）
  6. 回归警报 → ConsistencyGuard 元诊断
  7. 容量超限 → 优先级排序(含负反馈 + code_heat) → 降级
  8. 角色感知注入(role 字段过滤) → 精准上下文
  9. 强制复读(invalidation >= 2) → SP 顶部警示
  10. 更新记忆索引
```

---

## Directory Structure

```
project/
├── scripts/                        # ADDS 核心实现
│   ├── adds.py                     # CLI 主工具
│   ├── agent_loop.py               # Agent Loop 状态机
│   ├── agents.py                   # 5 个代理实现
│   ├── compliance_tracker.py       # 合规追踪
│   ├── system_prompt_builder.py    # 提示词构建器
│   │
│   ├── model/                      # 【P0-1】模型调用层
│   │   ├── __init__.py
│   │   ├── base.py                 # ModelInterface 抽象基类
│   │   ├── factory.py              # 交互式模型工厂
│   │   ├── api_adapter.py          # API 调用适配器
│   │   ├── cli_adapter.py          # CLI 工具适配器
│   │   ├── sdk_adapter.py          # SDK 适配器
│   │   ├── task_dispatcher.py      # CLI 任务派发器
│   │   ├── skill_generator.py      # 技能自动生成器
│   │   └── providers/
│   │       ├── __init__.py
│   │       ├── minimax.py          # MiniMax Provider
│   │       ├── codebuddy.py        # Codebuddy Provider
│   │       └── registry.py         # Provider 注册表
│   │
│   ├── context_compactor.py        # 【P0-2】两层压缩引擎
│   ├── summary_decision_engine.py  # 【P0-2】摘要策略决策引擎
│   ├── token_budget.py             # 【P0-2】Token 预算管理器
│   ├── session_manager.py          # 【P0-2】Session 文件管理
│   │
│   ├── memory_manager.py           # 【P0-3】记忆管理器
│   ├── memory_conflict_detector.py # 【P0-3】记忆冲突检测器
│   ├── memory_retriever.py         # 【P0-3】记忆检索接口
│   ├── memory_detox.py             # 【P0-3】记忆排毒引擎
│   ├── consistency_guard.py        # 【P0-3】一致性守护
│   ├── role_memory_injector.py     # 【P0-3】角色感知记忆注入器
│   ├── memory_cli.py               # 【P0-3】CLI 记忆管理子命令
│   ├── index_priority_sorter.py    # 【P0-3】优先级排序器
│   │
│   ├── permission_manager.py       # 【P0-4】权限管理器
│   │
│   └── test_p0_integration.py      # 【P0】集成测试（25个端到端场景）
│
├── .ai/                            # 项目状态
│   ├── CORE_GUIDELINES.md          # 核心规范
│   ├── architecture.md             # 架构文档（本文件）
│   ├── feature_list.md             # 功能列表
│   ├── progress.md                 # 进度日志
│   ├── settings.json               # 全局配置
│   ├── compliance_report.json      # 合规报告
│   ├── improvement_roadmap.md      # 改进路线图入口
│   │
│   ├── sessions/                   # Session + 记忆文件
│   │   ├── index.mem               # 记忆索引（固定记忆 + 线索）
│   │   ├── index-prev.mem          # 降级记忆索引
│   │   ├── YYYYMMDD-HHMMSS.ses    # Session 文件
│   │   ├── YYYYMMDD-HHMMSS-sesN.log # 工具输出 log
│   │   └── YYYYMMDD-HHMMSS.mem    # 记忆归档
│   │
│   ├── memories/                   # 技能库 + 角色化记忆
│   │   ├── MEMORY.md               # Agent 经验笔记
│   │   ├── USER.md                 # 用户偏好
│   │   └── SKILLS/                 # 技能库
│   │       └── README.md
│   │
│   └── roadmap/                    # 改进路线图
│       ├── README.md
│       ├── P0-1-model-layer.md
│       ├── P0-2-context-compaction.md
│       ├── P0-3-memory-system.md
│       ├── P0-4-permission.md
│       ├── P0-integration.md
│       └── P1-P2-outline.md
│
├── templates/                      # 模板文件
│   ├── prompts/                    # Agent 提示词
│   │   ├── sections/               # SP 分段
│   │   ├── pm_prompt.md
│   │   ├── architect_prompt.md
│   │   ├── developer_prompt.md
│   │   ├── tester_prompt.md
│   │   └── reviewer_prompt.md
│   └── scaffold/                   # 项目脚手架模板
│
├── docs/                           # 文档
│   ├── guide/                      # 使用指南
│   ├── references/                 # 参考资料（不修改）
│   │   ├── Claude_Code_架构白皮书研究报告.md
│   │   └── Hermes_Agent_研究报告.md
│   ├── specification.md            # 完整技术规范
│   ├── quick-start.md              # 快速开始
│   ├── usage-examples.md           # 使用示例
│   ├── feature-branch-workflow.md  # 功能分支工作流
│   ├── ide-integration.md          # IDE 集成指南
│   └── en/                         # 英文文档
│
├── schemas/                        # JSON Schema
│   └── feature_list.schema.json
│
├── setup.py                        # 安装脚本
├── CHANGELOG.md                    # 变更日志
├── README.md                       # 项目说明
└── LICENSE                         # 许可证
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| 模型调用 | API + CLI + SDK 三模式 | 适配不同使用场景和模型提供商 |
| 上下文压缩 | 两层压缩（实时 + 归档） | 平衡效率与信息保留 |
| 记忆存储 | Markdown 文件 | 人/LLM 可读，git 友好，KB-MB 级足够 |
| 记忆检索 | P0 rg + P1 向量 | 渐进式，P0 够用，P1 按需升级 |
| 权限模型 | Allow/Ask/Deny 三级 | 平衡安全与效率 |
| 冲突解决 | Recency Bias + SP 最高 | 系统提示词不可被覆盖 |
| 记忆不可变 | .mem APPEND-ONLY | 保留历史真相，避免推理链断裂 |
| 角色化记忆 | P0 role 字段过滤 | 低成本实现，P1 物理拆分 |

---

## Security Considerations

1. **模型调用安全**: API Key 不落盘，CLI 权限分级
2. **命令执行安全**: 三级权限 (Allow/Ask/Deny) + 死循环防护
3. **记忆安全**: APPEND-ONLY 不可变 + 冲突检测 + 排毒机制
4. **上下文安全**: 错误信号保留 (KEEP_FULL) + 失败关闭
5. **会话安全**: 会话隔离 + 链式指针防篡改

---

## P0 实施路径

| Phase | 周次 | 模块 | 核心文件 |
|-------|------|------|---------|
| Phase 1 | 第1周 | 模型调用层 | model/ 目录 |
| Phase 2 | 第2周 | 压缩 + Session | context_compactor.py, token_budget.py, session_manager.py |
| Phase 3 | 第3周 | 记忆 + 权限 | memory_*.py, consistency_guard.py, permission_manager.py |

详见 [改进路线图](.ai/roadmap/README.md)

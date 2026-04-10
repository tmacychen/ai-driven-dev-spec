# AI-Driven Development Specification (ADDS)

> **Agent-driven development framework — enabling AI Agents to autonomously complete project development across multiple context windows**

Inspired by [Anthropic's research](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) and [LangChain's harness engineering](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/).

**[中文文档](#中文文档) | [English Documentation](#english-documentation)**

---

## Core Principles

1. **Multi-Agent Team Model** — PM, Architect, Developer, Tester, Reviewer agents
2. **State-Driven** — `.ai/feature_list.md` is the single source of truth
3. **Incremental Development** — One feature at a time, never one-shot
4. **Clean Handoffs** — Every session leaves a mergeable state
5. **Evidence-First** — Prove features work with tool-based evidence
6. **Regression Protection** — Verify existing features before adding new ones

---

## 核心理念

ADDS 是一个 AI 驱动的软件开发规范，旨在让 AI Agent 能够自主完成项目开发。通过**架构约束而非 AI 理解**来保证行为的确定性和可靠性。

### 核心改进

基于 [Claude Code 的设计思路](https://github.com/ZhangHanDong/harness-engineering-from-cc-to-ai-coding)，ADDS 实现了从"规范文档"到"可执行规范系统"的转变：

| 改进项 | 传统方法问题 | ADDS 解决方案 |
|--------|------------|--------------|
| **系统提示词** | AI 需阅读规范 | 分段式自动注入 |
| **状态管理** | 依赖 AI 记住 | Agent Loop 强制执行 |
| **代理选择** | AI 判断 | 自动路由决策 |
| **状态稳定性** | 可能抖动 | 锁存机制保护 |
| **安全性** | 依赖 AI 判断 | 失败关闭 + 三级权限 |
| **可观测性** | 仅日志 | 合规性追踪 |
| **上下文管理** | 依赖模型窗口 | 两层压缩 + 两层记忆 |
| **记忆延续** | 每次会话失忆 | 进化记忆 + 链式 Session |

**核心特性**：系统提示词注入 • Agent Loop 状态机 • 锁存保护 • 失败关闭 • 合规追踪 • 两层压缩 • 两层记忆 • 三级权限

---

## 快速开始

**要求**：Python 3.9+

### 5 步上手（5 分钟）

```bash
# 1. 初始化项目
python3 scripts/adds.py init

# 2. 编辑功能列表
vim .ai/feature_list.md

# 3. 查看推荐代理
python3 scripts/adds.py route

# 4. 启动开发循环
python3 scripts/adds.py start

# 5. 查看进度
python3 scripts/adds.py status
```

**完整指南**：[quick-start.md](docs/quick-start.md) | [English](docs/en/quick-start.md)

---

## 核心特性

### 1. 分段式系统提示词

```
[静态区] identity, core_principles
  → 所有项目相同，可全局缓存
  
[边界标记] STATIC_BOUNDARY
  
[动态区] state_management, feature_workflow
  → 项目特定内容，按需生成
```

**优势**：AI 无需理解规范，自动注入约束，节省 token 成本

### 2. Agent Loop 状态机

```python
while True:
    ① 上下文预处理    # 强制检查 feature_list.md
    ② 路由决策        # 自动选择代理
    ③ 执行代理        # 权限检查 → 确定性执行
    ④ 状态更新        # 锁存保护
    ⑤ 终止判定        # 明确的终止条件
```

**优势**：状态驱动而非 AI 判断，防止非法状态转换

### 3. 两层压缩 (P0-2)

```
Layer 1: 工具输出超阈值 → 保存 .log + 替换为摘要（实时，无 API 调用）
Layer 2: 上下文超 80% → LLM 结构化摘要 + .mem 归档 + 新 Session
```

**优势**：错误信号永不压缩，历史数据归档不丢失

### 4. 两层记忆 (P0-3)

```
Layer 1: index.mem（固定记忆 + 索引线索）→ 始终注入上下文
Layer 2: .mem 文件（链式归档）→ 按需加载
```

**优势**：记忆进化/排毒/角色化/反思协议/回归警报/强制复读

### 5. 三级权限 (P0-4)

```
Allow  → 自动放行（ls, cat, python, git status...）
Ask    → 需确认（rm, pip install, git push...）
Deny   → 直接拒绝（sudo, mkfs, 写入 /etc...）
```

**优势**：四种模式（default/plan/auto/bypass）+ 死循环防护 + 会话级覆盖

### 6. 失败关闭机制

```python
if not pending_features:
    raise RuntimeError("停止而非猜测")  # 失败关闭
```

**优势**：默认最安全行为，避免错误累积

### 7. 合规性追踪

- ✅ 检测"一次一个功能"违规
- ✅ 验证状态转换合法性
- ✅ 监控代理边界约束
- ✅ 量化合规分数

**优势**：主动检测违规，而非依赖 AI 报告

---

## P0 架构

```
┌──────────────────────────────────────────────────────────┐
│                    CLI 入口层                             │
│  adds.py — init/start/status/route/mem/session/perm 命令  │
├──────────────────────────────────────────────────────────┤
│                 Agent Loop 调度层                          │
│  agent_loop.py — 状态机 + 路由 + 迭代控制                  │
│  system_prompt_builder.py — 分段式 SP 构建 + 记忆注入       │
│  compliance_tracker.py — 合规追踪                          │
├────────┬──────────┬─────────────┬─────────────────────────┤
│ P0-1   │ P0-2     │ P0-3        │ P0-4                   │
│ 模型层  │ 压缩层   │ 记忆层       │ 权限层                  │
│        │          │             │                         │
│ model/ │ context_ │ memory_     │ permission_             │
│  API   │ compactor│ manager     │  manager.py             │
│  CLI   │ token_   │ conflict_   │                         │
│  SDK   │ budget   │ detector    │                         │
│        │ session_ │ retriever   │                         │
│        │ manager  │ detox       │                         │
│        │ summary_ │ consistency │                         │
│        │ decision │ _guard      │                         │
│        │ _engine  │ role_       │                         │
│        │          │ injector    │                         │
│        │          │ memory_cli  │                         │
│        │          │ priority_   │                         │
│        │          │ sorter      │                         │
├────────┴──────────┴─────────────┴─────────────────────────┤
│                    基础设施层                               │
│  .ai/sessions/ — .ses/.log/.mem 文件存储                    │
│  .ai/memories/ — SKILLS/ + 角色化记忆                       │
│  .ai/settings.json — 全局配置                               │
└──────────────────────────────────────────────────────────┘
```

详见：[架构文档](.ai/architecture.md) | [改进路线图](.ai/roadmap/README.md)

---

## 文档导航

### 🚀 新用户（5-30 分钟）

| 文档 | 时间 | 内容 |
|------|------|------|
| [快速开始](docs/quick-start.md) \| [EN](docs/en/quick-start.md) | 5分钟 | 5步上手指南 |
| [使用示例](docs/usage-examples.md) \| [EN](docs/en/usage-examples.md) | 15分钟 | 实际项目示例 |
| [核心规范](.ai/CORE_GUIDELINES.md) | 10分钟 | Agent 必读规范 |

### 🎯 技术人员（30-120 分钟）

| 文档 | 时间 | 内容 |
|------|------|------|
| [改进路线图](.ai/roadmap/README.md) | 60分钟 | P0/P1/P2 完整规划 |
| [架构设计](.ai/architecture.md) | 30分钟 | P0 架构与数据流 |
| [完整规范](docs/specification.md) | 60分钟 | 技术规范全文 |

### 📊 项目管理者（10-30 分钟）

| 文档 | 时间 | 内容 |
|------|------|------|
| [快速开始](docs/quick-start.md) | 10分钟 | 快速上手指南 |
| [使用示例](docs/usage-examples.md) | 30分钟 | 实践案例和最佳实践 |

---

## 项目结构

```
ai-driven-dev-spec/
├── scripts/                        # 核心实现
│   ├── adds.py                     # CLI 主工具
│   ├── agent_loop.py               # Agent Loop 状态机
│   ├── system_prompt_builder.py    # 提示词构建器
│   ├── compliance_tracker.py       # 合规追踪器
│   ├── agents.py                   # 5 个代理实现
│   │
│   ├── model/                      # [P0-1] 模型调用层
│   │   ├── base.py                 # ModelInterface 抽象基类
│   │   ├── factory.py              # 交互式模型工厂
│   │   ├── api_adapter.py          # API 调用适配器
│   │   ├── cli_adapter.py          # CLI 工具适配器
│   │   ├── sdk_adapter.py          # SDK 适配器
│   │   ├── task_dispatcher.py      # CLI 任务派发器
│   │   ├── skill_generator.py      # 技能自动生成器
│   │   └── providers/              # Provider 注册表
│   │       ├── minimax.py
│   │       ├── codebuddy.py
│   │       └── registry.py
│   │
│   ├── token_budget.py             # [P0-2] Token 预算管理器
│   ├── session_manager.py          # [P0-2] Session 文件管理
│   ├── summary_decision_engine.py  # [P0-2] 摘要策略决策引擎
│   ├── context_compactor.py        # [P0-2] 两层压缩引擎
│   │
│   ├── memory_manager.py           # [P0-3] 记忆管理器
│   ├── memory_conflict_detector.py # [P0-3] 记忆冲突检测器
│   ├── memory_retriever.py         # [P0-3] 记忆检索接口
│   ├── memory_detox.py             # [P0-3] 记忆排毒引擎
│   ├── consistency_guard.py        # [P0-3] 一致性守护
│   ├── role_memory_injector.py     # [P0-3] 角色感知记忆注入器
│   ├── memory_cli.py               # [P0-3] CLI 记忆管理子命令
│   ├── index_priority_sorter.py    # [P0-3] 优先级排序器
│   │
│   ├── permission_manager.py       # [P0-4] 权限管理器
│   │
│   ├── test_p0_2.py               # P0-2 单元测试 (57 tests)
│   ├── test_p0_3.py               # P0-3 单元测试 (74 tests)
│   └── test_p0_4.py               # P0-4 单元测试 (69 tests)
│
├── .ai/                            # 项目状态
│   ├── CORE_GUIDELINES.md          # 核心规范
│   ├── architecture.md             # 架构文档
│   ├── feature_list.md             # 功能列表
│   ├── progress.md                 # 进度日志
│   ├── settings.json               # 全局配置
│   ├── sessions/                   # Session + 记忆文件
│   ├── memories/                   # 技能库 + 角色化记忆
│   └── roadmap/                    # 改进路线图
│
├── docs/                           # 文档
│   ├── guide/                      # 使用指南
│   ├── references/                 # 参考资料
│   ├── specification.md            # 完整技术规范
│   └── en/                         # 英文文档
│
├── templates/                      # 模板文件
├── schemas/                        # JSON Schema
├── setup.py                        # 安装脚本
├── CHANGELOG.md                    # 变更日志
├── README.md                       # 项目说明
└── LICENSE                         # 许可证
```

---

## 测试结果

```
P0 单元测试: 200 个测试 | 通过率: 100%

✅ test_p0_2 (57 tests) - 上下文压缩层
   TokenBudget / SessionManager / SummaryDecisionEngine / ContextCompactor

✅ test_p0_3 (74 tests) - 记忆系统
   MemoryManager / ConflictDetector / MemoryRetriever / MemoryDetox
   ConsistencyGuard / RoleMemoryInjector / IndexPrioritySorter / MemoryCLI

✅ test_p0_4 (69 tests) - 权限管理器
   PermissionLevel / PermissionMode / RuleMatch / CooldownState
   SessionOverrides / PermissionDecision / ParseToolCommand
```

运行测试：
```bash
cd scripts
python3 -m unittest test_p0_2 test_p0_3 test_p0_4 -v
```

---

## 设计原则（参考 Claude Code）

ADDS 完全实现了 Claude Code 的六条驾驭工程原则：

| 原则 | 实现方式 | 代码位置 |
|------|---------|---------|
| **提示词即控制面** | SystemPromptBuilder | `system_prompt_builder.py` |
| **缓存感知设计** | 静态/动态边界 | `system_prompt_builder.py` |
| **失败关闭，显式开放** | SafetyDefaults | `agent_loop.py` |
| **A/B测试一切** | ComplianceTracker | `compliance_tracker.py` |
| **先观察再修复** | 违规追踪 | `compliance_tracker.py` |
| **锁存以求稳定** | ProjectLatches | `agent_loop.py` |

**参考书籍**：[《驾驭工程：从 Claude Code 源码到 AI 编码最佳实践》](https://github.com/ZhangHanDong/harness-engineering-from-cc-to-ai-coding)

---

## 常用命令

```bash
# 项目管理
python3 scripts/adds.py init      # 初始化项目
python3 scripts/adds.py status    # 查看进度
python3 scripts/adds.py route     # 推荐代理

# 开发循环
python3 scripts/adds.py start     # 启动 Agent Loop
python3 scripts/adds.py start --perm default  # 指定权限模式

# Session 管理
python3 scripts/adds.py session list     # Session 列表
python3 scripts/adds.py session restore <id>  # 恢复 Session

# 记忆管理
python3 scripts/adds.py mem status       # 记忆状态
python3 scripts/adds.py mem audit        # 交互式审查
python3 scripts/adds.py mem prune --module auth  # 清理记忆

# 权限管理
python3 scripts/adds.py perm status      # 权限状态
python3 scripts/adds.py perm rules       # 权限规则
python3 scripts/adds.py perm mode auto   # 切换模式

# 测试验证
cd scripts && python3 -m unittest test_p0_2 test_p0_3 test_p0_4 -v
```

---

## 许可证 & 合规说明

本项目采用 **GNU General Public License v3.0 (GPLv3)** 许可证。

详见 [LICENSE](LICENSE) 文件。

---

## 致谢

本项目设计参考了 [Claude Code 的架构思路](https://github.com/ZhangHanDong/harness-engineering-from-cc-to-ai-coding)，特此致谢。

---

## 联系方式

- **Issues**: [GitHub Issues](https://github.com/tmacychen/ai-driven-dev-spec/issues)
- **Discussions**: [GitHub Discussions](https://github.com/tmacychen/ai-driven-dev-spec/discussions)

---

**项目状态**：🚧 P0 开发完成，待集成测试  
**P0 进度**：4/4 模块已完成  
**测试通过率**：100% (200/200)  

---

<a name="中文文档"></a>
## 中文文档

- [快速开始指南](docs/quick-start.md)
- [使用示例和最佳实践](docs/usage-examples.md)
- [改进路线图](.ai/roadmap/README.md)
- [架构设计](.ai/architecture.md)
- [核心规范](.ai/CORE_GUIDELINES.md)
- [完整技术规范](docs/specification.md)

---

<a name="english-documentation"></a>
## English Documentation

Full English documentation: [README-en.md](README-en.md)

Detailed docs:
- [Quick Start Guide](docs/en/quick-start.md)
- [Usage Examples & Best Practices](docs/en/usage-examples.md)
- [Improvement Roadmap](.ai/roadmap/README.md)
- [Architecture](.ai/architecture.md)
- [Core Guidelines](.ai/CORE_GUIDELINES.md)

# ADDS 改进路线图

> **来源**: 基于 Claude Code 架构白皮书与 Hermes Agent 研究报告的核心知识提炼
> **创建时间**: 2026-04-09
> **最后更新**: 2026-04-09 (P0 第四轮讨论)
> **状态**: P0 + P1 + P2 全部完成 (15/15) — 2026-04-20

---

## 文档索引

| 文件 | 内容 | 行数 |
|------|------|------|
| [P0-1-model-layer.md](P0-1-model-layer.md) | 大模型调用层（MiniMax + Codebuddy, CLI 派发协议） | ~750 |
| [P0-2-context-compaction.md](P0-2-context-compaction.md) | 上下文压缩策略（两层压缩, 摘要决策, 链式 Session） | ~470 |
| [P0-3-memory-system.md](P0-3-memory-system.md) | 记忆系统（两层记忆, 进化/排毒, 角色化, 反思协议, 回归警报, 注意力热点, 晋升仪式） | ~1580 |
| [P0-4-permission.md](P0-4-permission.md) | 命令批准机制（三级权限, Allow/Ask/Deny） | ~80 |
| [P0-integration.md](P0-integration.md) | P0 整体架构集成（数据流全景, 完整文件目录） | ~130 |
| [P1-P2-outline.md](P1-P2-outline.md) | P1/P2 改进项概要（技能披露, 向量检索, 记忆共振, 韧性增强, P2 远期） | ~130 |

---

## 改进优先级矩阵

| 优先级 | 改进项 | 来源 | 影响范围 | 预估工作量 | 状态 |
|--------|--------|------|----------|-----------|------|
| 🔴 P0-1 | 大模型调用层 | Claude Code + MiniMax | 基础能力 | 大 | ✅ 完成 |
| 🔴 P0-2 | 上下文压缩策略（两层） | Claude Code | Agent Loop 核心 | 大 | ✅ 完成 |
| 🔴 P0-3 | 记忆系统（两层+无限记忆+角色化+免疫） | Hermes + Claude Code | 跨会话进化 | 大 | ✅ 完成 |
| 🔴 P0-4 | 命令批准机制 | Claude Code + Hermes | 安全体系 | 中 | ✅ 完成 |
| 🟡 P1 | 技能渐进式披露 | Hermes | Token 优化 | 中 | ✅ 完成 |
| 🟡 P1 | Agent Loop 韧性增强 | Claude Code | 稳定性 | 中 | ✅ 完成 |
| 🟢 P2 | 执行后端隔离(Docker/SSH) | Hermes | 安全体系 | 大 | ✅ 完成 |
| 🟢 P2 | 多平台通信网关 | Hermes | 可达性 | 大 | ✅ 完成 |
| 🟢 P2 | Fork 子 Agent 路径 | Claude Code | 缓存优化 | 中 | ✅ 完成 |
| 🟢 P2 | 定时调度系统 | Hermes | 自动化 | 小 | ✅ 完成 |

---

## 实施路径（P0）

### Phase 1: 模型调用层（第 1 周）

```
Day 1-2:
  - [ ] 实现 ModelInterface 抽象基类 (model/base.py)
  - [ ] 实现 MiniMax Provider 配置 (model/providers/minimax.py)
  - [ ] 实现 Provider 注册表 (model/providers/registry.py)

Day 3-4:
  - [ ] 实现 API 适配器 (model/api_adapter.py)
  - [ ] 实现 CLI 适配器 (model/cli_adapter.py)

Day 5:
  - [ ] 实现交互式模型工厂 (model/factory.py)
  - [ ] 集成到 adds.py start 命令
  - [ ] 测试: API/CLI 两种模式均可用
```

### Phase 2: 压缩 + Session 管理（第 2 周）

```
Day 1-2:
  - [ ] 实现 TokenBudget (token_budget.py)
  - [ ] 实现 SessionManager (session_manager.py)
  - [ ] 定义 .ses / .log / .mem 文件格式

Day 3-4:
  - [ ] 实现 Layer 1 压缩 (context_compactor.py)
  - [ ] 实现 Layer 2 归档 (context_compactor.py)
  - [ ] 集成到 agent_loop.py

Day 5:
  - [ ] 集成到 system_prompt_builder.py（注入上一 session 摘要）
  - [ ] 测试: 完整压缩流程
```

### Phase 3: 记忆系统（第 3 周）

```
Day 1-2:
  - [ ] 实现 MemoryManager (memory_manager.py)
  - [ ] 实现 index.mem 读写
  - [ ] 实现记忆进化逻辑（升级/降级固定记忆）
  - [ ] 实现角色化记忆: role 字段 + RoleAwareMemoryInjector (role_memory_injector.py)  ← 第四轮新增

Day 3-4:
  - [ ] 实现记忆检索（链式回溯 + grep 搜索）
  - [ ] 实现记忆排毒引擎（验证性失效 + 负反馈惩罚 + 轻量级冲突扫描）
  - [ ] 实现反思协议: 角色第一人称反思 prompt 替换旁观评估  ← 第四轮新增
  - [ ] 实现回归警报 + ConsistencyGuard (consistency_guard.py)  ← 第四轮新增
  - [ ] 实现元诊断 _diagnose_defense_failure()  ← 第四轮新增
  - [ ] 集成到 agent_loop.py（会话结束时保存 + 失败时排毒 + 回归警报）

Day 5:
  - [ ] 实现 CLI 记忆管理子命令（adds mem status/audit/prune/override/history/checkpoint/promote）  ← promote 第四轮新增
  - [ ] 实现注意力热点 code_heat (IndexPrioritySorter 第6因子)  ← 第四轮新增
  - [ ] 实现强制复读机制 (SystemPromptBuilder 集成)  ← 第四轮新增
  - [ ] 实现 PermissionManager (permission_manager.py)
  - [ ] 集成到 agent_loop.py
  - [ ] P0 全流程集成测试
```

---

## 知识来源映射

| ADDS 改进项 | Claude Code 对应 | Hermes 对应 |
|-------------|-----------------|-------------|
| 大模型调用层 | 多 Provider 兼容层 | 多模型支持 |
| CLI 任务派发协议 | — | — (ADDS 原创) |
| 技能自动生成 | — | — (ADDS 原创，从文档提取) |
| 摘要策略决策 | — | — (ADDS 原创，TOOL_FILTER/LLM_ANALYZE) |
| 两层压缩 | MicroCompact + API 摘要 | — |
| 链式 Session | — | — (ADDS 原创) |
| .mem 恢复机制 | — | — (ADDS 原创) |
| 无限记忆 | CLAUDE.md 多级注入 | 双文件记忆 |
| 链式 index.mem | — | — (ADDS 原创) |
| 记忆进化 | — | 自进化技能系统 |
| 记忆不可变原则 | — | — (ADDS 原创) |
| 记忆冲突检测 | — | — (ADDS 原创) |
| System Prompt 优先级 | — | — (ADDS 原创) |
| 文本索引检索 | — | FTS5 搜索(改为 grep) |
| 权限控制 | 三级权限(Allow/Ask/Deny) | 命令批准机制 |
| 长时任务 HealthCheck | — | — (ADDS 原创，第三轮新增) |
| progress_hints | — | — (ADDS 原创，第三轮新增) |
| 错误保留原则 (KEEP_FULL) | — | — (ADDS 原创，第三轮新增) |
| 文件快照引用 (file_ref) | — | — (ADDS 原创，第三轮新增) |
| MemoryRetriever 接口 | — | — (ADDS 原创，第三轮新增，P0 rg + P1 向量) |
| 验证性失效 (Failure-Driven Invalidation) | — | — (ADDS 原创，第三轮新增) |
| 负反馈惩罚 (Negative Penalty) | — | — (ADDS 原创，第三轮新增，融入优先级排序) |
| 记忆排毒流程 | — | — (ADDS 原创，第三轮新增) |
| 轻量级冲突扫描 | — | — (ADDS 原创，第三轮新增，P0 关键词级) |
| 里程碑触发机制 | — | — (ADDS 原创，第三轮新增) |
| CLI 记忆管理子命令 | — | — (ADDS 原创，第三轮新增) |
| 记忆快照与对比 | — | — (ADDS 原创，第三轮新增) |
| 记忆 override 机制 | — | — (ADDS 原创，第三轮新增) |
| 角色化记忆 (role 字段 + index-{role}.mem) | — | — (ADDS 原创，第四轮新增) |
| 反思协议 (Reflection Protocol) | — | — (ADDS 原创，第四轮新增，第一人称角色反思) |
| 回归警报 (Regression Alarm) | — | — (ADDS 原创，第四轮新增，ConsistencyGuard) |
| 元诊断 (_diagnose_defense_failure) | — | — (ADDS 原创，第四轮新增，三层防御失效诊断) |
| 强制复读机制 | — | — (ADDS 原创，第四轮新增，invalidation_count >= 2 触发) |
| 注意力热点 (code_heat) | — | — (ADDS 原创，第四轮新增，第6权重因子) |
| 记忆晋升仪式 (--promote) | — | — (ADDS 原创，第四轮新增，临时记忆→长期直觉) |
| 记忆共振 (staging.mem) | — | — (ADDS 原创，第四轮新增，P1 跨角色二次进化) |

---

*最后更新: 2026-04-20 (P0 + P1 + P2 全部完成：15/15 功能)*

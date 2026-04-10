# P1/P2 改进项概要

> 📋 [返回总览](README.md) | [← P0 集成](P0-integration.md)

---

### 8.1 技能渐进式披露

- Level 0: 技能列表（名称+描述），注入上下文
- Level 1: 技能详情（触发条件+操作步骤），按需加载
- Level 2: 技能参考文件，执行时加载
- 与 MiniMax Skills 生态集成

### 8.2 语义检索升级（VectorMemoryRetriever）

- 当记忆量达到几百个 session、rg 关键词搜索不够用时启动
- 技术选型: LanceDB（轻量本地向量数据库，Rust 实现，零服务器依赖）
- 仅对 index.mem 中的"核心经验"做向量化（控制索引大小）
- .mem 文件的完整记录仍用 rg 检索（文本搜索更快）
- 混合检索策略: 向量检索（语义相似）+ rg 检索（精确匹配）→ 融合排序

### 8.3 语义冲突检测（重量级）

- 当记忆量增长到一定程度，轻量级关键词匹配不够用时启动
- 专员 Agent 扫描: 每次写入新固定记忆时，用 LLM 检查新老记忆是否存在逻辑矛盾
- 触发"记忆审计任务": 人工或高级 Agent 介入，决定保留哪条
- 与 P0 的 LightweightConflictScanner 互补: P0 快筛（零成本），P1 深扫（有成本但精准）

### 8.4 记忆共振: 跨角色二次进化（第四轮新增）

> **核心洞察**: 在多 Agent 并行系统中，不同角色的 Agent 可以通过共享的 `staging.mem` 看到彼此的审计意见，触发"协作习惯的养成"——这就是"记忆共振"。

**设计思路**:

```
记忆共振机制:

任务结束时，各 Agent 的反思结果先写入共享的 staging.mem:

staging.mem
├── Dev Agent 反思: "FFI 调用后需 Box::from_raw"
├── Architect Agent 反思: "FFI 必须封装在 safety-wrapper"
└── QA Agent 反思: "FFI 变更需 valgrind 检查"
         │
         ▼ 二次进化
Dev 看到 Architect 的边界定义:
  → "如果 Architect 说了要封装，我作为 Dev 就不该在业务逻辑里直接调 FFI"
  → 形成协作习惯，写入 Dev 的记忆

Architect 看到 QA 的测试策略:
  → "如果 QA 说必须 valgrind 检查，我在架构评审时应该提前要求"
  → 形成协作意识，写入 Architect 的记忆
```

**实现路径**:

- P0 阶段: 单 Agent 运行，不启用记忆共振
- P1 阶段: 多 Agent 并行设计，引入 `staging.mem` 共享反思
- 实现: session 结束时，各 Agent 反思结果写入共享 staging.mem，记忆升级时允许跨角色"参考"（不是复制）其他角色的反思结论
- 安全: 共享是"参考"而非"复制"——每个 Agent 只写入自己角色的记忆，但可以从其他角色的反思中提取协作性的行为准则

**与角色化记忆的关系**:

```
角色化记忆 (index-{role}.mem) + 记忆共振 (staging.mem):

P0: 单 Agent → role 字段过滤注入 → 无共振
P1: 多 Agent → 物理 index-{role}.mem + staging.mem 共享 → 有共振

共振不等于复制:
  ❌ 不会把 Architect 的架构知识复制到 Dev 的记忆中
  ✅ 会把"协作习惯"写入 Dev 的记忆（如"遵守封装规则"）
  ✅ 协作习惯是角色间的"接口契约"，而非角色内的"知识复用"
```

### 8.5 Agent Loop 韧性增强

- 7 种终止条件 + 5 种继续条件
- PTL 恢复、max_output_tokens 重试
- 错误恢复策略

---

# P2 改进项（概要）

- 执行后端隔离（Docker/SSH/远程沙箱）
- 多平台通信网关
- Fork 子 Agent 路径
- 定时调度系统

---

# 知识来源映射

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

*最后更新: 2026-04-09 (P0 第四轮讨论：角色化记忆/反思协议/回归警报与元诊断(ConsistencyGuard)/强制复读机制/注意力热点(code_heat)/记忆晋升仪式(--promote)/P1记忆共振)*

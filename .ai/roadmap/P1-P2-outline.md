# P1/P2 改进项概要

> 📋 [返回总览](README.md) | [← P0 集成](P0-integration.md)

---

### 8.1 技能渐进式披露 ✅

- Level 0: 技能列表（名称+描述+类别），~50 token/skill，始终注入 System Prompt
- Level 1: 技能详情（触发条件+操作步骤），~200-500 token/skill，按需 `skill_view(name)` 加载
- Level 2: 技能参考文件，~500-2000 token/skill，执行时 `skill_load(name, path)` 加载
- 关键词匹配与推荐 (`match_skills`/`suggest_skills`)
- 从 SkillGenerator 导入技能 (`import_from_skill_generator`)
- CLI: `adds skill list/view/load/match/register/import/delete/stats`
- AgentLoop: `/skill [name]` 命令
- 持久化: `registry.json` + `detail.json` + Markdown 兼容 + `usage_stats.json`
- 实现文件: `scripts/skill_manager.py`

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

### 8.5 Agent Loop 韧性增强 ✅ 已实现

> **实现文件**: `scripts/loop_state.py` + `scripts/agent_loop.py`

**7 种终止条件**:

| 条件 | 触发机制 |
|------|----------|
| `completed` | 用户主动退出或模型正常完成 |
| `blocking_limit` | Token 超硬限制且 PTL 恢复无效 |
| `aborted_streaming` | 用户中止流式输出（Ctrl+C） |
| `model_error` | 模型调用异常且重试耗尽 |
| `prompt_too_long` | 413/context_length 错误且压缩恢复无效 |
| `image_error` | 图片处理错误 |
| `hook_prevented` | Stop hook 阻止继续 |

**5 种继续条件**:

| 条件 | 恢复策略 |
|------|----------|
| `normal` | 正常对话循环 |
| `max_output_tokens` | 模型输出截断 → 续写提示，最多 3 次重试 |
| `prompt_too_long` | 上下文超限 → Layer1 压缩 → Layer2 归档，最多 2 次重试 |
| `error_retry` | 环境/速率错误 → 指数退避重试，最多 2 次 |
| `hook_retry` | Hook 阻塞后重试 |

**错误分类与恢复**:

| 类别 | 典型错误 | 策略 |
|------|----------|------|
| `environment` | ConnectionError, TimeoutError, OSError | 可重试 + 退避 |
| `model` | HTTP 413/429/500+, context_length | 413→PTL, 429→退避, 其他→终止 |
| `user_abort` | KeyboardInterrupt | 立即终止 |
| `system` | MemoryError | 不重试，直接终止 |

**关键参数** (ResilienceConfig):
- `max_output_tokens_retries`: 3 (续写重试次数)
- `ptl_max_retries`: 2 (PTL 恢复次数)
- `ptl_compression_target`: 0.60 (PTL 压缩目标利用率)
- `error_max_retries`: 2 (通用错误重试次数)
- `error_backoff_base`: 1.0s (指数退避基础时间)

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

*最后更新: 2026-04-20 (P1 功能11 Agent Loop 韧性增强已实现：7种终止条件/5种继续条件/PTL恢复/max_output_tokens续写/错误分类重试)*

# ADDS 功能列表

> 本文档是项目功能追踪的唯一真相源

## 项目信息
- 项目名称: ai-driven-dev-spec (ADDS)
- 技术栈: Python 3.9+, Rich, prompt_toolkit
- 创建时间: 2026-02-26
- 最后更新: 2026-04-20 (P2 规划)

---

## P0: 核心架构层

### 功能 1: 大模型调用层 (P0-1)
- **描述**: 统一模型调用接口，支持 API/CLI/SDK 三种模式 + Provider 注册表
- **状态**: completed
- **核心文件**: model/base.py, model/factory.py, model/api_adapter.py, model/cli_adapter.py, model/sdk_adapter.py
- **验收标准**:
  - [x] ModelInterface 抽象基类
  - [x] API 适配器（OpenAI 兼容）
  - [x] CLI 适配器（mmx/codebuddy）
  - [x] SDK 适配器（codebuddy-agent-sdk）
  - [x] Provider 注册表（MiniMax, Codebuddy）
  - [x] 交互式模型选择工厂

### 功能 2: 上下文压缩层 (P0-2)
- **描述**: Token 预算管理 + 两层压缩引擎 + 链式 Session 管理
- **状态**: completed
- **核心文件**: token_budget.py, session_manager.py, summary_decision_engine.py, context_compactor.py
- **验收标准**:
  - [x] TokenBudget 预算分配与阈值触发
  - [x] SessionManager .ses/.log/.mem 文件管理
  - [x] SummaryDecisionEngine 摘要策略决策
  - [x] ContextCompactor Layer1 实时压缩 + Layer2 归档
  - [x] 链式 Session Prev/Next 指针

### 功能 3: 记忆系统 (P0-3)
- **描述**: 两层记忆 + 进化/排毒 + 角色化注入 + 反思协议 + 回归警报
- **状态**: completed
- **核心文件**: memory_manager.py, memory_conflict_detector.py, memory_retriever.py, memory_detox.py, consistency_guard.py, role_memory_injector.py, memory_cli.py, index_priority_sorter.py
- **验收标准**:
  - [x] MemoryManager 两层记忆读写
  - [x] 记忆进化（规则评估 + 升级写入）
  - [x] 记忆排毒（验证性失效 + 负反馈惩罚）
  - [x] 角色化记忆注入（role 字段过滤）
  - [x] 反思协议（第一人称角色反思）
  - [x] ConsistencyGuard 回归警报
  - [x] 记忆检索（rg 关键词）
  - [x] CLI 记忆管理子命令（adds mem）

### 功能 4: 权限管理 (P0-4)
- **描述**: 三级权限（Allow/Ask/Deny）+ 四种模式 + 死循环防护
- **状态**: completed
- **核心文件**: permission_manager.py
- **验收标准**:
  - [x] PermissionLevel 三级权限
  - [x] PermissionMode 四种模式（default/plan/auto/bypass）
  - [x] 死循环防护（cooldown 机制）
  - [x] 会话级覆盖（session overrides）
  - [x] AI 分类器（auto 模式）

### 功能 5: P0 集成测试
- **描述**: 四层模块协同集成测试，25 个端到端场景
- **状态**: completed
- **核心文件**: test_p0_integration.py
- **验收标准**:
  - [x] 四层模块初始化与数据流串联
  - [x] 压缩触发与 Session 归档
  - [x] 记忆注入与 SystemPromptBuilder
  - [x] 权限拦截与决策流转
  - [x] 完整会话生命周期
  - [x] 跨层数据一致性

---

## P0+: TUI 与 CLI

### 功能 6: CLI 皮肤引擎
- **描述**: 基于 YAML 的终端美化系统，支持多主题切换
- **状态**: completed
- **核心文件**: scripts/skins/

### 功能 7: pyfiglet 动态 Logo
- **描述**: 使用 pyfiglet 运行时生成 ASCII art logo，支持自定义字体
- **状态**: completed
- **核心文件**: scripts/skins/

### 功能 8: 多主题皮肤
- **描述**: 7 个内置主题（default/cyberpunk/matrix/nordic/sakura/skynet/vault-tec）
- **状态**: completed
- **核心文件**: scripts/skins/*.yaml

### 功能 9: CLI 统一重构
- **描述**: 删除 v2 标记，统一 CLI 接口到 adds，集成 hooks 功能
- **状态**: completed
- **核心文件**: scripts/adds.py
- **验收标准**:
  - [x] scripts_v2 → scripts 重命名
  - [x] adds_v2.py → adds.py 重命名
  - [x] hooks 功能集成到 adds.py
  - [x] validate 命令
  - [x] 过时文档清理

---

## P1: 增强

### 功能 10: 技能渐进式披露
- **描述**: Level 0/1/2 三级技能加载，优化 Token 使用
- **状态**: completed
- **核心文件**: skill_manager.py
- **依赖**: P0 完成
- **验收标准**:
  - [x] Level 0: 技能列表索引（名称+描述+类别），~50 token/skill，始终注入
  - [x] Level 1: 技能详情（触发条件+操作步骤），~200-500 token/skill，按需加载
  - [x] Level 2: 技能参考文件，~500-2000 token/skill，执行时加载
  - [x] 关键词匹配与推荐（match_skills/suggest_skills）
  - [x] 从 SkillGenerator 导入技能
  - [x] System Prompt Level 0 自动注入
  - [x] AgentLoop /skill 命令集成
  - [x] CLI skill 子命令（list/view/load/match/register/import/delete/stats）
  - [x] 使用统计与持久化

### 功能 11: Agent Loop 韧性增强
- **描述**: 7 种终止条件 + 5 种继续条件 + PTL 恢复 + max_output_tokens 重试 + 错误分类与恢复策略
- **状态**: completed
- **核心文件**: loop_state.py, agent_loop.py
- **依赖**: P0 完成
- **验收标准**:
  - [x] TerminationReason 7 种终止条件枚举
  - [x] ContinueReason 5 种继续条件枚举
  - [x] ErrorCategory 错误分类枚举
  - [x] LoopStateMachine 状态机核心逻辑
  - [x] PTL (prompt-too-long) 恢复策略
  - [x] max_output_tokens 续写恢复（最多 3 次重试）
  - [x] 环境错误重试 + 指数退避
  - [x] 用户中止检测
  - [x] ResilienceConfig 可配置参数
  - [x] 终止/继续人类可读描述
  - [x] AgentLoop 集成韧性机制

---

## P2: 高级特性

### 功能 12: 定时调度系统 (P2-1)
- **描述**: 基于 cron 表达式的定时任务调度，支持 Agent Loop 自动执行、结果通知、失败重试
- **状态**: completed
- **核心文件**: scheduler.py
- **依赖**: P0+P1 完成
- **验收标准**:
  - [x] CronExpression 解析器（支持 5 字段 cron 语法 + 快捷方式）
  - [x] ScheduledTask 数据模型（任务定义 + 调度配置 + 执行历史）
  - [x] TaskScheduler 调度引擎（添加/删除/暂停/恢复任务）
  - [x] AgentExecutor 任务执行器（command/agent/python 三种类型）
  - [x] 执行结果记录（成功/失败/超时 + 输出摘要）
  - [x] 失败重试策略（可配置重试次数 + 指数退避）
  - [x] 通知机制（log/file/command 三种渠道 + notify_on 过滤）
  - [x] CLI schedule 子命令（add/list/remove/run/pause/resume/history/daemon/stats）
  - [x] AgentLoop /schedule 命令集成
  - [x] 配置持久化（scheduler.json）
  - [x] 守护进程模式（adds schedule daemon --interval）

### 功能 13: 执行后端隔离 (P2-2)
- **描述**: Docker/SSH/远程沙箱执行后端，隔离 Agent 执行环境
- **状态**: pending
- **核心文件**: executor_backend.py, backends/
- **依赖**: P0+P1 完成
- **验收标准**:
  - [ ] ExecutionBackend 抽象基类（统一接口）
  - [ ] LocalBackend 本地执行（默认后端）
  - [ ] DockerBackend Docker 容器执行（隔离环境）
  - [ ] SSHBackend 远程 SSH 执行
  - [ ] BackendFactory 后端选择工厂
  - [ ] 执行上下文序列化（命令/环境变量/文件传输）
  - [ ] 执行结果反序列化（stdout/stderr/exit_code）
  - [ ] 安全沙箱策略（资源限制 + 网络隔离）
  - [ ] CLI executor 子命令
  - [ ] 权限层集成（后端选择需权限检查）

### 功能 14: 多平台通信网关 (P2-3)
- **描述**: 统一消息网关，支持 Webhook/API/IM 等多平台通信
- **状态**: pending
- **核心文件**: gateway.py, channels/
- **依赖**: P0+P1 完成, 功能 12 (调度系统)
- **验收标准**:
  - [ ] MessageGateway 网关核心（消息路由 + 协议转换）
  - [ ] Channel 抽象基类（统一消息接口）
  - [ ] WebhookChannel HTTP Webhook 接收
  - [ ] CLIChannel CLI 命令行交互
  - [ ] 通知渠道（执行结果/调度通知/权限审批）
  - [ ] 消息格式标准化（MessageEnvelope）
  - [ ] 异步消息处理队列
  - [ ] CLI gateway 子命令

### 功能 15: Fork 子 Agent 路径 (P2-4)
- **描述**: 子 Agent 派生与管理，支持并行执行和结果汇聚
- **状态**: pending
- **核心文件**: agent_fork.py
- **依赖**: P0+P1 完成, 功能 13 (执行后端)
- **验收标准**:
  - [ ] AgentFork 子 Agent 派生器
  - [ ] ForkContext 上下文传递（系统提示词 + 记忆 + 权限）
  - [ ] 子 Agent 生命周期管理（创建/运行/等待/取消）
  - [ ] 结果汇聚（多子 Agent 结果合并）
  - [ ] 资源隔离（每个子 Agent 独立 session + 预算）
  - [ ] 最大并发数限制
  - [ ] CLI fork 子命令
  - [ ] AgentLoop /fork 命令集成

---

## 统计信息
- 总功能数: 15
- 已完成: 12
- 待实现: 3 (P2)

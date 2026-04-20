# ADDS 功能列表

> 本文档是项目功能追踪的唯一真相源

## 项目信息
- 项目名称: ai-driven-dev-spec (ADDS)
- 技术栈: Python 3.9+, Rich, prompt_toolkit
- 创建时间: 2026-02-26
- 最后更新: 2026-04-20

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

## 统计信息
- 总功能数: 11
- 已完成: 11
- 待实现: 0

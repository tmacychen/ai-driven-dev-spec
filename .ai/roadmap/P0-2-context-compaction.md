# P0-2: 上下文压缩策略（两层）

> 📋 [返回总览](README.md) | [← P0-1: 大模型调用层](P0-1-model-layer.md) | [P0-3: 记忆系统 →](P0-3-memory-system.md)

---

### 设计目标

实现**任务级上下文压缩**，确保当前 session 的上下文空间始终最优，同时通过链式结构实现可回溯的无限上下文。

### 核心设计思想

```
压缩 ≠ 丢弃细节
压缩 = 将细节移出当前上下文 + 保留回溯线索 + 结构化摘要留在链上

当前 session 只保留：
  1. System Prompt
  2. 上一 session 的结构化摘要 + 链式指针
  3. 固定记忆（升级后的精华）
  4. 当前任务的消息（精简后）

历史详情不丢弃，存在 .mem 文件中，可按需回溯
```

### 文件体系设计

```
.ai/sessions/
├── 20260409-153000.ses       # Session 文件（当前任务的对话记录）
├── 20260409-153000-ses1.log  # 工具输出 log（序号关联 session）
├── 20260409-153000-ses2.log  # 同一 session 的第 2 个 log
├── 20260409-160000.ses       # 下一 session
├── 20260409-160000-ses1.log
│
├── 20260409-153000.mem       # 记忆文件（高密度 Markdown 归档）
├── 20260409-160000.mem       # 含完整详情 + 结构化摘要 + 链式指针
│
└── index.mem                 # 记忆索引（线索目录，始终注入上下文）
```

### 摘要策略决策框架

> **核心问题**: 摘要生成有两种路径 — 工具过滤（快速无 LLM）和 LLM 分析（精准有成本）。决策依据：**摘要与结论的重要性**。

```python
from enum import Enum

class SummaryStrategy(Enum):
    """摘要策略"""
    KEEP_FULL = "keep_full"        # 完全保留：错误信号触发，不做任何压缩
    TOOL_FILTER = "tool_filter"    # 工具过滤：无需 LLM，快速
    LLM_ANALYZE = "llm_analyze"    # LLM 分析：需要 LLM，精准
    HYBRID = "hybrid"              # 混合：工具过滤 + LLM 精炼

class SummaryDecisionEngine:
    """摘要决策引擎 — 决定使用哪种摘要策略"""
    
    def decide(self, message: dict, context: dict) -> SummaryStrategy:
        """决策逻辑:
        
        0. 错误保留原则（最高优先级）:
           → KEEP_FULL: 检测到错误信号时完全保留，不做任何压缩
           → 错误信号: Exit Code != 0, Error/Exception/Traceback/FAIL/CRITICAL/WARNING
           → 包含错误信号的 stdout/stderr 都不压缩
           → 错误输出 ±3 行上下文也保留
        
        1. 结构化输出（测试结果、文件内容、命令输出）
           → TOOL_FILTER: 正则/规则提取关键指标
           → 示例: pytest 输出 → 提取 passed/failed/warnings
        
        2. 非结构化对话（需求讨论、架构决策、代码审查意见）
           → LLM_ANALYZE: 需要理解语义，提取关键决策和结论
           → 示例: "我觉得应该用 JWT 而不是 session" → 提取决策
        
        3. 混合内容（带结论的工具输出 + 人类讨论）
           → HYBRID: 先 TOOL_FILTER 提取结构化信息，再 LLM 精炼
        
        判断依据:
        - 错误信号存在 → KEEP_FULL（最高优先级）
        - 摘要与结论的重要性高 → 倾向 LLM_ANALYZE
        - 消息类型为 tool_result → 倾向 TOOL_FILTER
        - 上下文利用率高 → 倾向 TOOL_FILTER（省 token）
        """
        msg_type = message.get("role")
        content = message.get("content", "")
        
        # 规则 0（最高优先级）: 错误信号 → KEEP_FULL
        if msg_type == "tool_result" and self._has_error_signals(content):
            return SummaryStrategy.KEEP_FULL
        
        # 规则 1: 工具输出 → TOOL_FILTER
        if msg_type == "tool_result":
            return SummaryStrategy.TOOL_FILTER
        
        # 规则 2: 长对话讨论 → LLM_ANALYZE
        if msg_type == "assistant" and len(content) > 500:
            return SummaryStrategy.LLM_ANALYZE
        
        # 规则 3: 包含决策关键词 → LLM_ANALYZE
        decision_keywords = ["决定", "结论", "选择", "方案", "decided", "conclusion"]
        if any(kw in content.lower() for kw in decision_keywords):
            return SummaryStrategy.LLM_ANALYZE
        
        # 默认: TOOL_FILTER
        return SummaryStrategy.TOOL_FILTER
    
    def _has_error_signals(self, content: str) -> bool:
        """检测内容是否包含错误信号
        
        检测规则:
        1. Exit Code != 0
        2. 标准错误关键词: Error, Exception, Traceback, FAILED, CRITICAL, WARNING
        3. 大小写不敏感匹配（stdout 中也可能有错误）
        4. 匹配到错误信号的行 ±3 行上下文都保留
        """
        import re
        error_signals = [
            r'exit\s+code\s+[1-9]',                          # Exit Code != 0
            r'(Error|Exception|Traceback|FAILED?|CRITICAL)',  # 大写变体
            r'(error|exception|traceback|failed?|critical)',  # 小写变体
            r'WARNING',                                       # 警告信号
        ]
        return any(re.search(p, content, re.IGNORECASE) for p in error_signals)
```

**Layer 1 和 Layer 2 的摘要策略分布**:

| 层级 | 策略 | 说明 |
|------|------|------|
| Layer 1 | KEEP_FULL 最高优先级 | 错误信号触发时完全保留，不做任何压缩 |
| Layer 1 | TOOL_FILTER 为主 | 实时压缩，不能等 LLM 响应。仅用规则过滤 |
| Layer 1 | LLM_ANALYZE 补充 | 仅当决策关键词触发，且上下文有空余时 |
| Layer 2 | LLM_ANALYZE 为主 | 归档压缩，需要精准提取关键信息 |
| Layer 2 | TOOL_FILTER 辅助 | 结构化输出部分先用工具提取，减少 LLM token 消耗 |

### Layer 1: 任务内压缩（实时，无需 API 调用）

**触发条件**: 工具输出超过阈值（默认 2000 字符，可配置）

**操作**:

```
任务执行中的消息流:
┌──────────────────────────────────────────────────────┐
│ [user] 实现 xxx 功能                                  │
│ [assistant] 我来分析需求...                            │
│ [tool_call] bash("pytest tests/")                     │
│ [tool_result] ← 超过 2000 字符！触发 Layer 1          │
│     ↓                                                 │
│     摘要决策: TOOL_FILTER（结构化输出）                  │
│     1. 将完整输出保存到 20260409-153000-ses1.log      │
│     2. Session 中替换为：                              │
│        [tool_result] 测试完成。详见 ses1.log           │
│        摘要: 12 passed, 0 failed, 2 warnings          │
│ [assistant] 测试通过，继续...                          │
│ [tool_call] bash("cat src/main.py")                   │
│ [tool_result] ← 又超阈值                              │
│     ↓                                                 │
│     摘要决策: TOOL_FILTER（文件内容）                    │
│     1. 保存到 20260409-153000-ses2.log                │
│     2. Session 中替换为占位符 + 摘要                   │
│ ...                                                   │
│ [assistant] 任务完成。结论：xxx                         │
│     ↓                                                 │
│     摘要决策: LLM_ANALYZE（含结论的重要消息）            │
│     → 标记此消息为"高价值"，Layer 2 归档时重点提取      │
└──────────────────────────────────────────────────────┘
```

**Layer 1 的 .ses 文件格式**:

```markdown
# Session: 20260409-153000
# Agent: developer
# Feature: user_authentication
# Created: 2026-04-09 15:30:00
# Status: active

## Messages

### [user] 实现 xxx 功能

### [assistant] 我来分析需求...

### [tool_call] bash("pytest tests/")

### [tool_result]
测试完成。详见 `20260409-153000-ses1.log`
摘要: 12 passed, 0 failed, 2 warnings
<!-- strategy: tool_filter -->

### [assistant] 测试通过，继续...

### [tool_call] bash("cat src/main.py")

### [tool_result]
文件内容。详见 `20260409-153000-ses2.log`
摘要: main.py 共 150 行，包含 Auth 类和路由定义
<!-- strategy: tool_filter -->
<!-- file_ref: src/main.py | md5=abc123 | lines=150 | modified=2026-04-09T15:35:00 -->

### [assistant] 任务完成。结论：用户认证功能已实现
<!-- strategy: llm_analyze | priority: high -->
```

**Layer 1 额外清理规则**:

| 操作 | 说明 | 策略 |
|------|------|------|
| **错误保留（最高优先级）** | **包含错误信号的工具输出完全保留，不做任何压缩** | **KEEP_FULL** |
| **错误上下文保留** | **错误信号行 ±3 行上下文也保留** | **KEEP_FULL** |
| 清除已完成任务输出 | 仅保留任务说明与结论，删除中间过程 | TOOL_FILTER |
| 保存过长工具结果 | > 阈值 → log 文件，session 留占位符 + 摘要 | TOOL_FILTER |
| 文件内容快照引用 | 对 cat 结果记录 file_ref（md5 + 修改时间 + 行数） | TOOL_FILTER |
| 删除重复消息 | 折叠连续相同/确认性消息 | TOOL_FILTER |
| 删除冗余确认 | "好的"、"我理解了" 等无实质内容消息 | TOOL_FILTER |
| 标记高价值消息 | 含决策/结论的消息标记 priority: high | LLM_ANALYZE |

### Layer 2: 会话归档压缩（触发时调用 LLM）

**触发条件**: 上下文超过 80% 窗口

**操作流程**:

```
Step 1: 合并 Layer 1 的 session + log → 完整记录
  20260409-153000.ses + ses1.log + ses2.log
  → 将 log 占位符替换为实际内容（markdown 引入语法）

Step 2: 摘要决策 — 分区域选择策略
  对完整记录中的每条消息：
  - TOOL_FILTER 标记的 → 用规则提取（省 token）
  - LLM_ANALYZE 标记的 → 送 LLM 分析（精准）
  - 优先提取 priority: high 的消息

Step 3: 调用 LLM 对高价值部分生成结构化摘要
  - 保留：关键决策、代码变更、测试结果、错误与修复
  - 保留：任务结论和未完成事项
  - 保留：经验教训（用于记忆进化评估）
  - 格式：高密度 Markdown

Step 4: 生成 .mem 文件（记忆归档）
  内容 = 完整记录（含 log） + 结构化摘要 + 链式指针
  20260409-153000.mem
  ⚠️ 完整记录区是 APPEND-ONLY，写入后不可修改

Step 5: 回写 .ses 文件为摘要版
  保留结构化摘要 + 指向前一个 session 的指针
  20260409-153000.ses → 覆写为摘要版

Step 6: 检查是否需要升级固定记忆
  如果摘要中有高价值经验 → 升级为固定记忆
```

**.mem 文件格式（高密度 Markdown）**:

```markdown
# Memory: 20260409-153000
# Agent: developer | Feature: user_authentication
# Created: 2026-04-09 15:30:00
# Archived: 2026-04-09 16:00:00
# Prev: 20260409-143000.mem    ← 链式指针（前一个 session）
# Next: (待写入)               ← 链式指针（后一个 session）

---

## 结构化摘要（由 LLM 生成）

### 关键决策
- 使用 JWT 进行用户认证
- 密码使用 bcrypt 哈希存储
- Token 有效期设为 24 小时

### 代码变更
- 新增: src/auth/jwt_handler.py (JWT 生成/验证)
- 新增: src/auth/password.py (bcrypt 哈希)
- 修改: src/routes/user.py (添加 /login, /logout 端点)
- 修改: src/middleware/auth.py (添加 JWT 验证中间件)

### 测试结果
- 单元测试: 12 passed, 0 failed
- 集成测试: 3 passed (登录/登出/Token刷新)
- 覆盖率: 87%

### 错误与修复
- JWT 过期时返回 500 → 修复为返回 401
- bcrypt 需安装额外依赖 → 已添加到 requirements.txt

### 未完成事项
- Token 刷新端点尚未实现
- 需要 Reviewer 审查安全漏洞

### 经验教训
- JWT 库 PyJWT 2.x API 与 1.x 不兼容，需注意版本

---

## 完整记录（含工具输出详情）

### [user] 实现用户认证功能

### [assistant] 我来分析需求...

### [tool_call] bash("pytest tests/")

### [tool_result]
12 passed, 0 failed, 2 warnings in 3.2s
tests/test_auth.py::test_jwt_generation PASSED
tests/test_auth.py::test_jwt_validation PASSED
tests/test_auth.py::test_password_hashing PASSED
...（完整输出）

### [tool_call] bash("cat src/main.py")

### [tool_result]
```python
from auth.jwt_handler import JWTHandler
from auth.password import hash_password, verify_password
...（完整代码）
```

...（完整对话记录，包含所有 log 内容）
```

**.mem 文件设计要点**:

| 特性 | 说明 |
|------|------|
| **高密度 Markdown** | 非二进制压缩，LLM 可直接读取 |
| **双区结构** | 结构化摘要（精炼）+ 完整记录（详尽） |
| **摘要不丢细节** | 摘要提取关键信息，完整记录保留一切 |
| **链式指针** | Prev/Next 指针构成双向链表 |
| **文本检索** | 可用 grep/rg 直接在 .mem 文件中搜索 |
| **容量** | 单文件无硬限制，实际通常 5-50KB |
| **APPEND-ONLY** | 完整记录区写入后不可修改（历史记忆不可变） |
| **可恢复** | .mem → .ses 可逆，从完整记录区重建 |

### .mem 恢复到 .ses 的机制

> **核心问题**: 结构化摘要是否会丢失细节？如何从 .mem 恢复到 .ses？
> 
> **回答**: 摘要本身会丢失细节，但 .mem 的完整记录区保留了 Layer 1 清理后的全部信息。恢复是从完整记录区重建，而非从摘要重建。

```
恢复流程（.mem → .ses）:

20260409-153000.mem
├── 结构化摘要区 ← 摘要确实丢失了细节，但这是设计意图
│   （精炼版，用于快速理解 session 内容）
│
└── 完整记录区   ← 包含 Layer 1 清理后的全部信息
    │              （所有对话 + 所有 log 内容）
    │
    ▼ 恢复操作
    1. 读取完整记录区
    2. 反向替换: 将 log 引用还原为实际内容
    3. 生成与 Layer 1 压缩前等价的 .ses 文件
    4. 恢复的 .ses 与原始 .ses 的差异:
       - 内容完整等价
       - 格式可能略有不同（元数据标记）
    
    恢复命令: adds session restore 20260409-153000
```

### 文件存储 vs 数据库存储对比

> **问题**: 压缩文件 vs DB（如 SQLite），哪种存储效率更高？是否保留全部记忆信息？

| 维度 | 文件存储（.mem Markdown） | 数据库存储（SQLite） |
|------|--------------------------|---------------------|
| **信息完整性** | ✅ 保留全部信息（完整记录区） | ✅ 保留全部信息 |
| **存储效率** | 中等（文本，可 gzip 压缩） | 较高（二进制，自动压缩） |
| **检索效率** | grep/rg（文本搜索，够用） | SQL 索引（结构化查询，快） |
| **可读性** | ✅ 人/LLM 可直接阅读 | ❌ 需工具查看 |
| **可移植性** | ✅ 纯文本，git 友好 | ❌ 二进制，合并困难 |
| **维护成本** | 低（无 schema 迁移） | 中（需管理表结构） |
| **ADDS 规模适用性** | ✅ KB-MB 级，完全够用 | 过度设计 |
| **与 LLM 交互** | ✅ 直接注入上下文 | 需额外转换 |

**结论**: 对于 ADDS 的规模和使用场景，文件存储完全足够。数据库的优势（索引、结构化查询）在 KB-MB 级数据上不明显，而文件存储的可读性和可移植性优势更大。如果未来数据量增长到 GB 级，再考虑引入 SQLite 作为 Layer 2 的索引层。

### 链式 Session 结构

```
时间线:  ←──────────────────────────────────────→

  ses1.ses         ses2.ses         ses3.ses (当前)
  ses1.mem         ses2.mem
    │                │                │
    │  Prev: null    │  Prev: ses1    │  Prev: ses2
    │  Next: ses2    │  Next: ses3    │  Next: null
    │                │                │
    ▼                ▼                ▼
  [摘要+详情]     [摘要+详情]      [活跃对话]
```

**新 session 启动时的上下文构建**:

```
新 session 上下文 = 
  System Prompt                    ← 静态 + 动态（最高优先级）
  + 固定记忆 (index.mem)           ← 升级后的精华，优先级低于 System Prompt
  + 上一个 session 的结构化摘要     ← 从 prev_ses.mem 的摘要区读取
  + 上一个 session 的链式指针       ← "历史详情在 {prev_ses.mem}，可回溯"
  + 当前任务消息                    ← 实时对话

⚠️ 上下文构建前需检测:
  System Prompt 与 固定记忆冲突 → 自动以 System Prompt 为准 + 通知用户
  用户最新指令与固定记忆冲突 → 自动以用户最新为准（Recency Bias）+ 记录冲突日志
  System Prompt 与用户最新指令冲突 → 必须暂停，向用户确认
```

**回溯机制**:

```
当 LLM 需要历史细节时:
1. LLM 在上下文中看到: "上一个 session 的链式指针: 20260409-153000.mem"
2. LLM 调用工具: 读取该 .mem 文件的完整记录区
3. 如果需要更早的: 沿 Prev 指针继续回溯
4. 文本检索: grep/rg 在 .ai/sessions/*.mem 中搜索关键词
```

### Token 预算管理

```python
class TokenBudget:
    """Token 预算管理器"""
    
    # 预算分配比例
    SYSTEM_PROMPT_RATIO = 0.15    # 15% for system prompt
    MEMORY_RATIO = 0.10           # 10% for 固定记忆 + 上一个摘要
    HISTORY_RATIO = 0.55          # 55% for 当前 session 对话
    TOOL_RESULT_RATIO = 0.15      # 15% for 工具输出
    RESERVE_RATIO = 0.05          # 5% 预留
    
    def __init__(self, context_window: int):
        self.context_window = context_window
        self.used = 0
    
    @property
    def utilization(self) -> float:
        return self.used / self.context_window
    
    def should_compact_layer1(self) -> bool:
        """是否需要 Layer 1 压缩"""
        return self.utilization > 0.5  # 工具输出大时提前压缩
    
    def should_compact_layer2(self) -> bool:
        """是否需要 Layer 2 归档"""
        return self.utilization > 0.8  # 上下文达 80%
    
    def should_warn(self) -> bool:
        """提醒 AI 加速收尾"""
        return self.utilization > 0.85
```

### 实现文件变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `scripts/context_compactor.py` | 新建 | 两层压缩引擎 |
| `scripts/token_budget.py` | 新建 | Token 预算管理器 |
| `scripts/session_manager.py` | 新建 | Session 文件管理（.ses/.log/.mem 读写） |
| `scripts/agent_loop.py` | 修改 | 每次迭代前检查预算 + 触发压缩 |
| `scripts/system_prompt_builder.py` | 修改 | 注入上一个 session 摘要 + 链式指针 |
| `scripts/adds.py` | 修改 | start 命令集成 session 管理 |

---


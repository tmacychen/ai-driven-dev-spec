# ADDS 改进计划：从"依赖理解"到"架构约束"

## 📋 问题诊断

### 当前 ADDS 的核心问题

| 问题 | 表现 | Claude Code 的解决思路 |
|------|------|----------------------|
| **依赖 AI 理解** | AI 需要阅读规范文档才能遵循 | 提示词即控制面：行为约束嵌入系统提示词 |
| **状态管理外部化** | feature_list.md 是外部文件，AI 可能忘记读取 | Agent Loop 状态机：状态是循环的核心字段 |
| **缺乏强制执行** | 没有"失败关闭"的安全默认值 | 失败关闭哲学：默认最安全，显式声明才允许危险操作 |
| **缓存不友好** | 每次会话需重新加载整个规范 | 分段记忆化：静态/动态边界 + 三级缓存 |
| **缺乏锁存机制** | 状态可能在会话中抖动 | 锁存以求稳定：一旦确定就不再变化 |
| **缺乏自动裁决** | 依赖 AI 判断选择代理 | YOLO 分类器：自动分类 + 拒绝追踪回退 |

---

## 🎯 改进目标

### 设计原则（参考 Claude Code 第24章）

1. **提示词即控制面** - 用系统提示词段落引导 AI 行为，而非依赖 AI 阅读文档
2. **失败关闭，显式开放** - 默认只允许安全操作，危险操作需要显式授权
3. **锁存以求稳定** - 功能状态一旦确定，会话内不再变化
4. **先观察再修复** - 建立可观测性，追踪 AI 是否遵循规范
5. **工具级提示词** - 每个代理有专属行为约束

---

## 📅 改进路线图（4个阶段）

### 阶段 1：系统提示词架构重构（优先级：最高）

**目标**：将 ADDS 规范从"外部文档"变为"嵌入式约束"

#### 1.1 创建分段式系统提示词注册表

**参考**：Claude Code 第5章 - 系统提示词架构

```
templates/prompts/
├── sections/
│   ├── identity.md              # 静态：AI 身份定义（可全局缓存）
│   ├── core_principles.md       # 静态：核心原则（可全局缓存）
│   ├── state_management.md      # 动态：状态管理指令
│   ├── feature_workflow.md      # 动态：功能工作流指令
│   ├── agent_routing.md         # 动态：代理路由规则
│   └── safety_constraints.md    # 动态：安全约束
├── agents/
│   ├── pm_agent.md              # PM Agent 专属提示词
│   ├── architect_agent.md       # Architect Agent 专属提示词
│   ├── developer_agent.md       # Developer Agent 专属提示词
│   ├── tester_agent.md          # Tester Agent 专属提示词
│   └── reviewer_agent.md        # Reviewer Agent 专属提示词
└── system_prompt_builder.py     # 动态组装系统提示词
```

#### 1.2 实现静态/动态边界标记

**核心思想**：将系统提示词分为"所有项目相同"和"项目特定"两部分

```python
# templates/prompts/system_prompt_builder.py

STATIC_BOUNDARY = "__ADDS_STATIC_BOUNDARY__"

def build_system_prompt(context):
    """
    构建分段式系统提示词
    
    返回结构：
    [
        静态区：identity, core_principles → 可全局缓存
        STATIC_BOUNDARY
        动态区：state_management, feature_workflow, agent_routing, safety_constraints
    ]
    """
    sections = []
    
    # 静态区：所有 ADDS 项目相同
    sections.append(load_section("identity"))
    sections.append(load_section("core_principles"))
    
    # 边界标记
    sections.append(STATIC_BOUNDARY)
    
    # 动态区：项目特定
    sections.append(build_state_management_section(context))
    sections.append(build_feature_workflow_section(context))
    sections.append(build_agent_routing_section(context))
    sections.append(build_safety_constraints_section(context))
    
    return sections
```

#### 1.3 为每个代理创建专属提示词

**参考**：Claude Code 第8章 - 工具级提示词

```python
# templates/prompts/agents/developer_agent.md

# Developer Agent - 专属行为约束

## 身份
你是 Developer Agent，负责实现功能。

## 核心职责（不可违反）
1. **一次只实现一个功能** - 从 feature_list.md 中选择状态为 `pending` 的第一个功能
2. **状态驱动** - 必须先读取 `.ai/feature_list.md`，按照状态推进：`pending → in_progress → testing → completed`
3. **禁止越权** - 不做架构决策（Architect 负责），不写测试用例（Tester 负责）

## 强制流程
```
开始 → 读取 feature_list.md → 验证当前功能状态 → 实现代码 → 更新状态为 testing → 结束
```

## 失败关闭机制
- 如果 feature_list.md 不存在 → **停止并提示用户运行 adds init**
- 如果当前功能状态不是 pending → **停止并报告异常**
- 如果实现过程中发现架构问题 → **停止并建议调用 Architect Agent**

## 输出格式
```
## 当前功能：{feature_name}
## 状态变更：{old_status} → {new_status}
## 实现证据：
- 文件修改：{file_list}
- 工具执行：{tool_commands}
```
```

---

### 阶段 2：Agent Loop 状态机实现（优先级：高）

**目标**：从"依赖 AI 判断"变为"显式状态转换"

#### 2.1 定义状态类型

**参考**：Claude Code 第3章 - Agent Loop

```python
# scripts/state_machine.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional, List

class AgentType(Enum):
    PM = "pm"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    TESTER = "tester"
    REVIEWER = "reviewer"

class FeatureStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    COMPLETED = "completed"
    BUG = "bug"

class ContinueReason(Enum):
    NEXT_TURN = "next_turn"
    AGENT_SWITCH = "agent_switch"
    FEATURE_COMPLETE = "feature_complete"
    REGRESSION_DETECTED = "regression_detected"
    
class TerminalReason(Enum):
    ALL_COMPLETED = "all_completed"
    USER_ABORT = "user_abort"
    BLOCKING_ERROR = "blocking_error"
    MAX_TURNS = "max_turns"

@dataclass
class State:
    """会话状态 - 跨迭代传递"""
    current_agent: AgentType
    current_feature: Optional[str]
    current_feature_status: FeatureStatus
    messages: List[dict]
    turn_count: int
    max_turns: int = 50
    
    # 锁存字段（一旦确定，会话内不变）
    project_type: Optional[str] = None
    tech_stack: Optional[List[str]] = None
    initial_feature_count: int = 0
    
    # 恢复追踪
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3
```

#### 2.2 实现主循环

```python
# scripts/agent_loop.py

async def adds_loop(initial_state: State):
    """
    ADDS 主循环 - 显式状态机
    
    参考：Claude Code 第3章 queryLoop
    """
    state = initial_state
    
    while True:
        # 阶段 1：上下文预处理
        state = preprocess_context(state)
        
        # 阶段 2：路由决策
        next_agent = route_agent(state)
        
        # 阶段 3：执行当前代理
        result = await execute_agent(next_agent, state)
        
        # 阶段 4：状态更新
        state = update_state(state, result)
        
        # 阶段 5：终止判定
        terminal = check_termination(state)
        if terminal:
            return terminal
        
        # 阶段 6：继续判定
        continue_reason = check_continue(state)
        state = handle_continue(state, continue_reason)
```

#### 2.3 实现代理路由器（替代 AI 判断）

```python
# scripts/agent_router.py

def route_agent(state: State) -> AgentType:
    """
    代理路由器 - 自动决定使用哪个代理
    
    参考：Claude Code 第17章 YOLO 分类器
    """
    # 规则 1：项目启动 → PM Agent
    if not state.project_type:
        return AgentType.PM
    
    # 规则 2：无架构设计 → Architect Agent
    if not has_architecture():
        return AgentType.ARCHITECT
    
    # 规则 3：有 pending 功能 → Developer Agent
    pending_features = get_pending_features()
    if pending_features:
        return AgentType.DEVELOPER
    
    # 规则 4：有 testing 功能 → Tester Agent
    testing_features = get_testing_features()
    if testing_features:
        return AgentType.TESTER
    
    # 规则 5：所有功能 completed → Reviewer Agent
    if all_features_completed():
        return AgentType.REVIEWER
    
    # 默认：PM Agent（安全降级）
    return AgentType.PM
```

---

### 阶段 3：锁存机制与失败关闭（优先级：中）

**目标**：保证状态稳定性，防止会话中抖动

#### 3.1 项目类型锁存

```python
# scripts/latches.py

class ProjectLatches:
    """
    项目级锁存器 - 会话内不变
    
    参考：Claude Code 第13章 - Beta Header 锁存
    """
    
    def __init__(self):
        self._project_type_latched = False
        self._tech_stack_latched = False
        self._initial_feature_count_latched = False
        
    def latch_project_type(self, project_type: str):
        """首次确定后，会话内不再变化"""
        if not self._project_type_latched:
            STATE.project_type = project_type
            self._project_type_latched = True
            log_event("project_type_latched", {"value": project_type})
    
    def latch_tech_stack(self, tech_stack: List[str]):
        """技术栈一旦确定，不再变化"""
        if not self._tech_stack_latched:
            STATE.tech_stack = tech_stack
            self._tech_stack_latched = True
```

#### 3.2 功能状态锁存

```python
# scripts/feature_latches.py

class FeatureStateLatches:
    """
    功能状态锁存 - 防止状态抖动
    
    参考：Claude Code 第13章 - TTL 资格锁存
    """
    
    def __init__(self):
        self._current_feature_latched = False
        
    def latch_current_feature(self, feature_name: str):
        """当前功能一旦开始，不允许中途切换"""
        if not self._current_feature_latched:
            STATE.current_feature = feature_name
            STATE.current_feature_status = FeatureStatus.IN_PROGRESS
            self._current_feature_latched = True
        elif STATE.current_feature != feature_name:
            # 拒绝切换 - 保护当前功能
            raise RuntimeError(
                f"Feature already in progress: {STATE.current_feature}. "
                f"Cannot switch to {feature_name}."
            )
```

#### 3.3 失败关闭机制

```python
# scripts/safety_defaults.py

class SafetyDefaults:
    """
    失败关闭 - 默认最安全行为
    
    参考：Claude Code 第2章 - Tool 接口
    """
    
    @staticmethod
    def safe_feature_selection(features: List[dict]) -> dict:
        """
        安全的功能选择
        
        默认：选择第一个 pending 功能
        失败时：停止而非猜测
        """
        pending = [f for f in features if f['status'] == 'pending']
        
        if not pending:
            raise RuntimeError(
                "No pending features found. "
                "ADDS requires at least one pending feature to proceed."
            )
        
        # 安全默认：第一个 pending 功能
        return pending[0]
    
    @staticmethod
    def safe_status_transition(current: str, target: str) -> bool:
        """
        安全的状态转换
        
        默认：只允许合法转换
        失败时：拒绝而非猜测
        """
        valid_transitions = {
            'pending': ['in_progress'],
            'in_progress': ['testing', 'bug'],
            'testing': ['completed', 'bug'],
            'bug': ['in_progress'],
            'completed': []  # 终态
        }
        
        if target not in valid_transitions.get(current, []):
            raise RuntimeError(
                f"Invalid status transition: {current} → {target}. "
                f"Valid targets: {valid_transitions.get(current, [])}"
            )
        
        return True
```

---

### 阶段 4：可观测性与自动裁决（优先级：中）

**目标**：监控 AI 是否遵循规范，自动裁决异常情况

#### 4.1 规范遵循追踪

```python
# scripts/compliance_tracker.py

class ComplianceTracker:
    """
    规范遵循追踪 - 监控 AI 是否遵循 ADDS
    
    参考：Claude Code 第14章 - 缓存中断检测
    """
    
    def __init__(self):
        self.violations = []
        self.compliance_score = 1.0
        
    def check_one_feature_per_session(self, state: State) -> bool:
        """检查：一次只实现一个功能"""
        if state.turn_count > 0:
            completed_count = count_completed_features()
            if completed_count > 1:
                self.record_violation(
                    "MULTIPLE_FEATURES_PER_SESSION",
                    f"Completed {completed_count} features in one session"
                )
                return False
        return True
    
    def check_state_driven(self, state: State) -> bool:
        """检查：状态驱动"""
        if not file_exists(".ai/feature_list.md"):
            self.record_violation(
                "MISSING_FEATURE_LIST",
                "feature_list.md not found - AI skipped state check"
            )
            return False
        return True
    
    def record_violation(self, violation_type: str, details: str):
        """记录违规"""
        self.violations.append({
            "type": violation_type,
            "details": details,
            "timestamp": datetime.now()
        })
        self.compliance_score *= 0.9  # 每次违规降低 10%
```

#### 4.2 自动代理分类器（简化版 YOLO）

```python
# scripts/agent_classifier.py

async def classify_agent_autonomously(
    context: dict,
    safety_settings: dict
) -> tuple[AgentType, str]:
    """
    自动代理分类器 - 减少人工介入
    
    参考：Claude Code 第17章 - YOLO 分类器
    """
    
    # 阶段 1：规则匹配（快速路径）
    if context.get('project_type') is None:
        return AgentType.PM, "Project not initialized"
    
    if not has_architecture():
        return AgentType.ARCHITECT, "Architecture design required"
    
    pending_features = get_pending_features()
    if pending_features:
        return AgentType.DEVELOPER, f"Feature pending: {pending_features[0]}"
    
    # 阶段 2：AI 分类（深度推理）
    if safety_settings.get('allow_ai_routing'):
        prompt = build_routing_prompt(context)
        response = await call_ai_model(prompt, max_tokens=64)
        
        agent_type = parse_agent_type(response)
        return agent_type, "AI-classified"
    
    # 失败关闭：默认 PM Agent
    return AgentType.PM, "Default fallback"
```

#### 4.3 拒绝追踪与回退

```python
# scripts/denial_tracking.py

class DenialTracker:
    """
    拒绝追踪 - 连续拒绝后回退到人工确认
    
    参考：Claude Code 第17章 - 拒绝追踪
    """
    
    MAX_CONSECUTIVE_DENIALS = 3
    MAX_TOTAL_DENIALS = 20
    
    def __init__(self):
        self.consecutive_denials = 0
        self.total_denials = 0
        
    def record_denial(self, reason: str):
        """记录拒绝"""
        self.consecutive_denials += 1
        self.total_denials += 1
        
        # 检查阈值
        if self.consecutive_denials >= self.MAX_CONSECUTIVE_DENIALS:
            self.fallback_to_human("Too many consecutive denials")
        
        if self.total_denials >= self.MAX_TOTAL_DENIALS:
            self.fallback_to_human("Total denial limit reached")
    
    def reset_consecutive(self):
        """成功操作后重置连续拒绝计数"""
        self.consecutive_denials = 0
    
    def fallback_to_human(self, reason: str):
        """回退到人工确认"""
        raise HumanInterventionRequired(
            f"Automatic routing failed: {reason}. "
            f"Please manually select the agent."
        )
```

---

## 📊 改进效果预期

### 改进前 vs 改进后

| 维度 | 改进前 | 改进后 |
|------|-------|-------|
| **AI 理解负担** | 需要阅读完整规范文档 | 系统提示词自动注入约束 |
| **状态管理** | 依赖 AI 记住读取 feature_list.md | Agent Loop 强制读取，失败则停止 |
| **代理选择** | AI 判断（可能出错） | 路由器自动决策 + 锁存保护 |
| **状态稳定性** | 可能抖动 | 锁存机制保证会话内稳定 |
| **安全性** | 依赖 AI 判断 | 失败关闭 + 自动分类器 |
| **可观测性** | 仅日志 | 规范遵循追踪 + 违规记录 |

---

## 🚀 实施优先级

### 第一周：阶段 1（系统提示词架构）
- [ ] 创建分段式提示词目录结构
- [ ] 实现系统提示词构建器
- [ ] 为每个代理创建专属提示词
- [ ] 添加静态/动态边界标记

### 第二周：阶段 2（Agent Loop 状态机）
- [ ] 实现状态类型定义
- [ ] 实现主循环框架
- [ ] 实现代理路由器
- [ ] 添加状态转换验证

### 第三周：阶段 3（锁存与失败关闭）
- [ ] 实现项目级锁存器
- [ ] 实现功能状态锁存
- [ ] 实现失败关闭机制
- [ ] 添加安全默认值

### 第四周：阶段 4（可观测性）
- [ ] 实现规范遵循追踪器
- [ ] 实现自动代理分类器
- [ ] 实现拒绝追踪与回退
- [ ] 添加监控仪表盘

---

## 📝 与 Claude Code 的设计对齐

### Claude Code 设计原则 → ADDS 改进

| Claude Code 原则 | ADDS 改进 |
|-----------------|----------|
| **提示词即控制面** | 阶段 1：系统提示词架构重构 |
| **失败关闭，显式开放** | 阶段 3：安全默认值 + 状态转换验证 |
| **锁存以求稳定** | 阶段 3：项目级锁存 + 功能状态锁存 |
| **A/B测试一切** | 阶段 4：规范遵循追踪 + 违规记录 |
| **先观察再修复** | 阶段 4：可观测性基础设施 |

---

## 🎯 成功标准

### 定量指标

1. **规范遵循率** ≥ 95%（通过 ComplianceTracker 测量）
2. **状态抖动率** ≤ 5%（通过 FeatureStateLatches 测量）
3. **AI 理解负担** 减少 80%（从阅读完整规范到注入提示词）
4. **代理选择准确率** ≥ 90%（通过 AgentRouter 测量）

### 定性目标

1. **AI 无需阅读规范** - 通过系统提示词自动注入约束
2. **状态稳定可靠** - 锁存机制防止会话内抖动
3. **失败可恢复** - 失败关闭 + 自动回退
4. **行为可观测** - 规范遵循追踪 + 违规记录

---

## 📚 参考资料

- **Claude Code 第3章**：Agent Loop 状态机设计
- **Claude Code 第5章**：系统提示词架构
- **Claude Code 第13章**：锁存机制设计
- **Claude Code 第17章**：YOLO 分类器
- **Claude Code 第24章**：驾驭工程六原则

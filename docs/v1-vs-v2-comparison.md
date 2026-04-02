# ADDS v1.0 vs v2.0 详细对比

## 📊 总体对比

| 维度 | v1.0 | v2.0 |
|------|------|------|
| **设计哲学** | 依赖 AI 理解规范 | 架构约束，AI 无需理解 |
| **规范传递** | 外部文档，AI 需阅读 | 系统提示词注入 |
| **状态管理** | 依赖 AI 记住读取 | Agent Loop 强制读取 |
| **代理选择** | AI 判断 | 路由器自动决策 |
| **状态稳定性** | 可能抖动 | 锁存机制保护 |
| **安全性** | 依赖 AI 判断 | 失败关闭 |
| **可观测性** | 仅日志 | 合规追踪 |

---

## 🔍 详细对比

### 1. 规范传递方式

#### v1.0：外部文档

```
项目结构：
├── docs/
│   ├── specification.md      # 核心规范（AI 需阅读）
│   └── guide/                # 使用指南（AI 需阅读）
├── templates/
│   └── prompts/
│       ├── pm_prompt.md      # PM 提示词（AI 需理解）
│       └── developer_prompt.md
└── .ai/
    └── feature_list.md       # 状态文件（AI 需记住读取）
```

**问题**：
- ❌ AI 可能不阅读规范文档
- ❌ AI 可能不完全理解规范
- ❌ AI 可能忘记遵循规范
- ❌ 每次会话都需重新加载规范

#### v2.0：系统提示词注入

```
项目结构：
├── templates/
│   └── prompts/
│       ├── sections/         # 分段式提示词
│       │   ├── identity.md
│       │   ├── core_principles.md
│       │   ├── state_management.md
│       │   └── safety_constraints.md
│       └── agents/           # 代理专属提示词
│           ├── developer_agent.md
│           └── tester_agent.md
└── .ai/
    └── system_prompt.md      # 自动生成的系统提示词
```

**改进**：
- ✅ 系统提示词自动注入，AI 无需阅读
- ✅ 分段式架构，静态/动态边界清晰
- ✅ 静态区可全局缓存，节省成本
- ✅ 动态区按需生成，适应项目状态

**代码对比**：

```python
# v1.0：依赖 AI 阅读
# templates/prompts/developer_prompt.md
"""
你是 Developer Agent，请遵循 ADDS 规范：
1. 阅读 docs/specification.md
2. 阅读 .ai/feature_list.md
3. 实现功能...
"""

# v2.0：系统提示词注入
builder = SystemPromptBuilder()
prompt = builder.build_system_prompt(context)

# prompt 内容：
"""
# AI-Driven Development Specification Agent

## 你的身份
你是一个遵循 ADDS 规范的 AI 开发代理。

## 核心约束（不可违反）
1. 一次一个功能
2. 状态驱动
3. 显式状态转换
4. 证据优先

## 当前状态
- 当前功能：user_authentication
- 当前状态：in_progress

**约束**：你当前正在实现 user_authentication，禁止切换到其他功能。
"""
```

---

### 2. 状态管理

#### v1.0：依赖 AI 记住

```python
# v1.0：依赖 AI 主动读取
# templates/prompts/developer_prompt.md
"""
开始任务前：
1. 读取 .ai/feature_list.md
2. 选择一个 pending 功能
3. 更新状态
"""

# 问题：
# - AI 可能忘记读取 feature_list.md
# - AI 可能选择错误的功能
# - AI 可能忘记更新状态
```

#### v2.0：Agent Loop 强制读取

```python
# v2.0：Agent Loop 强制执行
class ADDSAgentLoop:
    async def _loop(self, features):
        while True:
            # 阶段 1：上下文预处理
            self._preprocess_context()  # 强制检查 feature_list.md
            
            # 阶段 2：路由决策
            next_agent = self.safety.safe_agent_selection(features)
            
            # 阶段 3：执行代理
            result = await self._execute_agent(features)
            
            # 阶段 4：状态更新
            self._update_state(result)

# 优势：
# - 强制读取 feature_list.md，不存在则停止
# - 自动选择功能，失败则停止
# - 强制更新状态，非法转换则拒绝
```

**代码对比**：

```python
# v1.0：AI 主动选择功能
# AI 可能选择错误的逻辑：
if some_condition:
    feature = features[5]  # AI 可能选错索引
    # 或者：
    feature = random.choice(features)  # AI 可能随机选择

# v2.0：确定性选择
def safe_feature_selection(features):
    pending = [f for f in features if f.status == 'pending']
    
    if not pending:
        raise RuntimeError("无待处理功能")  # 失败关闭
    
    return pending[0]  # 确定性选择第一个
```

---

### 3. 代理选择

#### v1.0：AI 判断

```python
# v1.0：依赖 AI 判断
# templates/prompts/pm_prompt.md
"""
根据当前项目状态，判断应该使用哪个代理：
- 如果没有 feature_list.md → PM Agent
- 如果没有架构设计 → Architect Agent
- 如果有 pending 功能 → Developer Agent
"""

# 问题：
# - AI 可能判断错误
# - AI 可能选择不符合规范的代理
# - AI 可能中途切换代理（状态抖动）
```

#### v2.0：路由器自动决策

```python
# v2.0：确定性路由
def safe_agent_selection(state, features):
    # 规则 1：项目未初始化 → PM Agent
    if state.project_type is None:
        return AgentType.PM
    
    # 规则 2：有 pending 功能 → Developer Agent
    if any(f.status == FeatureStatus.PENDING for f in features):
        return AgentType.DEVELOPER
    
    # 规则 3：有 testing 功能 → Tester Agent
    if any(f.status == FeatureStatus.TESTING for f in features):
        return AgentType.TESTER
    
    # 规则 4：所有功能 completed → Reviewer Agent
    if all(f.status == FeatureStatus.COMPLETED for f in features):
        return AgentType.REVIEWER
    
    # 失败关闭：默认 PM Agent
    return AgentType.PM
```

**锁存机制对比**：

```python
# v1.0：可能抖动
# 会话 #1
AI: "我觉得应该用 PM Agent"
# 会话 #2
AI: "我觉得应该用 Architect Agent"  # 抖动！

# v2.0：锁存保护
class ProjectLatches:
    def latch_project_type(self, state, project_type):
        if not self._project_type_latched:
            state.project_type = project_type
            self._project_type_latched = True  # 锁存
            
# 一旦锁存，会话内不再变化
# 防止状态抖动
```

---

### 4. 状态转换

#### v1.0：依赖 AI 判断

```python
# v1.0：AI 可能非法转换
# AI 可能的逻辑：
feature.status = 'completed'  # 直接跳过 testing 状态！

# 或者：
feature.status = 'pending'    # 倒退状态！

# 问题：
# - 跳过状态：pending → completed（跳过 testing）
# - 倒退状态：testing → pending（倒退）
# - 非法状态：completed → in_progress（终态变化）
```

#### v2.0：强制验证

```python
# v2.0：合法性验证
def safe_status_transition(current, target):
    valid_transitions = {
        'pending': ['in_progress'],
        'in_progress': ['testing', 'bug'],
        'testing': ['completed', 'bug'],
        'bug': ['in_progress'],
        'completed': []  # 终态
    }
    
    if target not in valid_transitions.get(current, []):
        raise RuntimeError(f"非法状态转换: {current} → {target}")
    
    return True

# 使用：
safe_status_transition('pending', 'completed')  # ❌ 抛出异常
safe_status_transition('pending', 'in_progress')  # ✅ 通过
```

---

### 5. 安全性

#### v1.0：依赖 AI 判断

```python
# v1.0：AI 可能执行危险操作
# AI 可能的逻辑：
if need_cleanup:
    os.system("rm -rf /")  # 危险！

# 或者：
subprocess.run(["git", "push", "--force"])  # 危险！

# 问题：
# - AI 可能不理解危险操作的后果
# - AI 可能被提示词注入攻击
# - AI 可能执行未验证的外部脚本
```

#### v2.0：失败关闭

```python
# v2.0：安全默认值
class SafetyDefaults:
    DANGEROUS_OPERATIONS = [
        "rm -rf",
        "git push --force",
        "git reset --hard",
        "curl ... | bash",
    ]
    
    def check_safety(self, operation):
        if operation in self.DANGEROUS_OPERATIONS:
            raise RuntimeError(f"危险操作被拒绝: {operation}")

# 使用：
safety.check_safety("rm -rf")  # ❌ 拒绝
safety.check_safety("ls")      # ✅ 允许
```

**权限模式对比**：

```python
# v1.0：二元选择
# config.py
REQUIRE_CONFIRMATION = True  # 或 False

# 问题：要么全部确认，要么全部自动

# v2.0：多级权限梯度（参考 Claude Code 第16章）
class PermissionMode(Enum):
    DEFAULT = "default"              # 所有操作需确认
    ACCEPT_EDITS = "acceptEdits"     # 文件编辑自动，命令需确认
    PLAN = "plan"                    # 只读，不执行任何写操作
    BYPASS = "bypassPermissions"     # 跳过所有检查（危险）
    AUTO = "auto"                    # AI 分类器自动裁决

# 使用：
mode = PermissionMode.ACCEPT_EDITS
# 文件编辑：自动通过
# Shell 命令：需要确认
```

---

### 6. 可观测性

#### v1.0：仅日志

```python
# v1.0：简单日志
# progress.md
"""
## 2026-04-02 18:00
- 实现了用户认证功能
- 测试通过
"""

# 问题：
# - 无结构化数据
# - 无合规性指标
# - 无违规记录
# - 无法追踪 AI 是否遵循规范
```

#### v2.0：合规追踪

```python
# v2.0：结构化追踪
class ComplianceTracker:
    def check_one_feature_per_session(self, feature_name):
        if self.current_feature and feature_name != self.current_feature:
            self.record_violation(Violation(
                type=ViolationType.MULTIPLE_FEATURES_PER_SESSION,
                details=f"尝试切换功能: {self.current_feature} → {feature_name}",
                severity="critical"
            ))

# 输出：
{
    "timestamp": "2026-04-02T18:00:00",
    "summary": {
        "total_checks": 25,
        "passed_checks": 23,
        "failed_checks": 2,
        "compliance_score": 0.92,
        "violations_by_type": {
            "multiple_features_per_session": 1,
            "missing_evidence": 1
        }
    },
    "violations": [
        {
            "type": "multiple_features_per_session",
            "details": "尝试切换功能: feature_1 → feature_2",
            "severity": "critical"
        }
    ]
}
```

---

## 📈 改进效果

### 定量指标（预期）

| 指标 | v1.0 | v2.0 | 改进 |
|------|------|------|------|
| 规范遵循率 | ~60% | ≥95% | +35% |
| 状态抖动率 | ~20% | ≤5% | -75% |
| AI 理解负担 | 阅读完整规范 | 无需阅读 | -80% |
| 代理选择准确率 | ~70% | ≥90% | +20% |
| 安全违规次数 | 不可控 | 可追踪 | 可量化 |

### 定性改进

1. **AI 无需理解规范**
   - v1.0：AI 需阅读并理解规范文档
   - v2.0：系统提示词自动注入约束

2. **状态稳定可靠**
   - v1.0：可能抖动，AI 中途改变决策
   - v2.0：锁存机制保证会话内稳定

3. **失败可恢复**
   - v1.0：错误累积，难以调试
   - v2.0：失败关闭 + 自动回退

4. **行为可观测**
   - v1.0：仅日志，无结构化数据
   - v2.0：合规追踪 + 违规记录

---

## 🔄 迁移指南

### 从 v1.0 迁移到 v2.0

#### 步骤 1：更新项目结构

```bash
# 保留 v1.0 的功能列表
cp .ai/feature_list.md .ai/feature_list.md.backup

# 创建 v2.0 目录结构
mkdir -p templates/prompts/sections
mkdir -p templates/prompts/agents
```

#### 步骤 2：生成系统提示词

```bash
cd scripts_v2
python adds_v2.py inject-prompt --output ../.ai/system_prompt.md
```

#### 步骤 3：使用新版 CLI

```bash
# v1.0 命令
python scripts/adds.py status

# v2.0 命令
python scripts_v2/adds_v2.py status
```

#### 步骤 4：监控合规性

```bash
python scripts_v2/adds_v2.py start --max-turns 10
# 自动生成合规报告：.ai/compliance_report.json
```

---

## 📚 设计原则对齐

### Claude Code 六原则 → ADDS v2.0

| Claude Code 原则 | v1.0 | v2.0 |
|-----------------|------|------|
| **提示词即控制面** | ❌ 外部文档 | ✅ 系统提示词注入 |
| **缓存感知设计** | ❌ 无缓存策略 | ✅ 静态/动态边界 |
| **失败关闭，显式开放** | ❌ 依赖 AI 判断 | ✅ SafetyDefaults 类 |
| **A/B测试一切** | ❌ 无测试框架 | ✅ 合规追踪器 |
| **先观察再修复** | ❌ 仅日志 | ✅ ComplianceTracker |
| **锁存以求稳定** | ❌ 可能抖动 | ✅ ProjectLatches |

---

## 🎯 总结

### 核心改进

ADDS v2.0 从"依赖 AI 理解规范"升级为"架构约束，AI 无需理解"：

1. **系统提示词自动注入** - AI 无需阅读规范
2. **Agent Loop 强制执行** - 状态驱动而非 AI 判断
3. **锁存机制保护** - 防止状态抖动
4. **失败关闭设计** - 默认最安全行为
5. **合规性追踪** - 监控 AI 是否遵循规范

### 设计哲学转变

```
v1.0: 信任 AI → AI 理解规范 → AI 遵循规范
v2.0: 架构约束 → 系统注入规范 → 强制执行规范
```

### 与 Claude Code 对齐

v2.0 充分借鉴了 Claude Code 的设计思路，实现了：

- 提示词即控制面
- 缓存感知设计
- 失败关闭哲学
- 锁存机制
- 可观测性基础设施

这些改进使 ADDS 从"规范文档"升级为"可执行的规范系统"。

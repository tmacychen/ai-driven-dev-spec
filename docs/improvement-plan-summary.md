# ADDS 改进计划总结

## 📋 改进背景

### 核心问题

ADDS v1.0 是一个优秀的 AI 开发规范，但存在一个根本性问题：**依赖 AI 理解并自觉遵循规范**。

具体表现：

1. **AI 可能不阅读规范** - 每次会话 AI 需要主动阅读规范文档
2. **AI 可能不完全理解** - 规范复杂，AI 可能误解或遗漏
3. **AI 可能忘记遵循** - 会话中 AI 可能偏离规范
4. **状态可能抖动** - AI 中途可能改变决策
5. **缺乏强制执行** - 没有机制确保 AI 必须遵循规范

### 解决思路

参考 Claude Code 的设计哲学：**通过架构约束而非 AI 理解来保证行为**。

核心转变：

```
从：AI 阅读规范 → AI 理解规范 → AI 遵循规范（可能失败）
到：系统注入规范 → 架构强制执行 → 合规追踪监控（确定性）
```

---

## 🎯 改进目标

### 六大改进

| 改进项 | v1.0 问题 | v2.0 解决方案 | Claude Code 参考 |
|--------|----------|--------------|-----------------|
| **系统提示词** | AI 需阅读规范文档 | 分段式注入，静态/动态边界 | 第5章：系统提示词架构 |
| **状态管理** | 依赖 AI 记住读取 | Agent Loop 强制读取，失败停止 | 第3章：Agent Loop |
| **代理选择** | AI 判断（可能出错） | 路由器自动决策 + 锁存保护 | 第17章：YOLO 分类器 |
| **状态稳定性** | 可能抖动 | 锁存机制保证会话内稳定 | 第13章：锁存机制 |
| **安全性** | 依赖 AI 判断 | 失败关闭 + 安全默认值 | 第16章：权限系统 |
| **可观测性** | 仅日志 | 规范遵循追踪 + 违规记录 | 第14章：缓存中断检测 |

---

## 📅 改进计划

### 阶段 1：系统提示词架构重构（优先级：最高）

**目标**：将 ADDS 规范从"外部文档"变为"嵌入式约束"

**关键实现**：

1. **分段式提示词注册表**
   ```
   templates/prompts/sections/
   ├── identity.md              # 静态：AI 身份定义
   ├── core_principles.md       # 静态：核心原则
   ├── state_management.md      # 动态：状态管理
   ├── feature_workflow.md      # 动态：功能工作流
   ├── agent_routing.md         # 动态：代理路由
   └── safety_constraints.md    # 动态：安全约束
   ```

2. **静态/动态边界标记**
   ```python
   STATIC_BOUNDARY = "__ADDS_STATIC_BOUNDARY__"
   
   # 静态区：所有 ADDS 项目相同 → 可全局缓存
   # 动态区：项目特定内容 → 不缓存
   ```

3. **代理专属提示词**
   ```python
   def build_agent_specific_prompt(agent_type, context):
       # Developer Agent 独有的行为约束
       # Tester Agent 独有的验证流程
       # ...
   ```

**成果文件**：
- ✅ `scripts_v2/system_prompt_builder.py` - 已实现

---

### 阶段 2：Agent Loop 状态机实现（优先级：高）

**目标**：从"依赖 AI 判断"变为"显式状态转换"

**关键实现**：

1. **状态类型定义**
   ```python
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
   ```

2. **主循环框架**
   ```python
   async def adds_loop(initial_state):
       while True:
           ① 上下文预处理
           ② 路由决策
           ③ 执行代理
           ④ 状态更新
           ⑤ 终止判定
           ⑥ 继续判定
   ```

3. **代理路由器**
   ```python
   def route_agent(state, features):
       # 规则 1：项目未初始化 → PM Agent
       # 规则 2：有 pending 功能 → Developer Agent
       # 规则 3：有 testing 功能 → Tester Agent
       # ...
   ```

**成果文件**：
- ✅ `scripts_v2/agent_loop.py` - 已实现

---

### 阶段 3：锁存机制与失败关闭（优先级：中）

**目标**：保证状态稳定性，防止会话中抖动

**关键实现**：

1. **项目级锁存**
   ```python
   class ProjectLatches:
       def latch_project_type(self, state, project_type):
           if not self._project_type_latched:
               state.project_type = project_type
               self._project_type_latched = True  # 锁存
   ```

2. **功能状态锁存**
   ```python
   class FeatureStateLatches:
       def latch_current_feature(self, state, feature_name):
           if not self._current_feature_latched:
               state.current_feature = feature_name
               self._current_feature_latched = True
           else:
               raise RuntimeError("功能状态已锁存，禁止切换")
   ```

3. **失败关闭机制**
   ```python
   class SafetyDefaults:
       def safe_feature_selection(features):
           pending = [f for f in features if f.status == 'pending']
           if not pending:
               raise RuntimeError("无待处理功能")  # 停止而非猜测
           return pending[0]
   ```

**成果文件**：
- ✅ `scripts_v2/agent_loop.py` - 已集成

---

### 阶段 4：可观测性与自动裁决（优先级：中）

**目标**：监控 AI 是否遵循规范，自动裁决异常情况

**关键实现**：

1. **规范遵循追踪**
   ```python
   class ComplianceTracker:
       def check_one_feature_per_session(feature_name):
           # 检查：一次只实现一个功能
       
       def check_feature_list_exists():
           # 检查：状态驱动
       
       def check_valid_status_transition():
           # 检查：合法状态转换
   ```

2. **自动代理分类器**
   ```python
   async def classify_agent_autonomously(context):
       # 规则匹配（快速路径）
       if context.get('project_type') is None:
           return AgentType.PM
       
       # AI 分类（深度推理）
       if allow_ai_routing:
           return await call_ai_model(prompt)
       
       # 失败关闭
       return AgentType.PM
   ```

3. **拒绝追踪与回退**
   ```python
   class DenialTracker:
       MAX_CONSECUTIVE_DENIALS = 3
       
       def record_denial():
           if consecutive_denials >= MAX:
               fallback_to_human()  # 回退到人工
   ```

**成果文件**：
- ✅ `scripts_v2/compliance_tracker.py` - 已实现

---

## 📂 成果文件

### 核心实现

```
scripts_v2/
├── adds_v2.py                  # 改进版 CLI 工具
├── system_prompt_builder.py    # 系统提示词构建器
├── agent_loop.py               # Agent Loop 状态机
└── compliance_tracker.py       # 规范遵循追踪器
```

### 文档

```
docs/
├── improvement-plan.md         # 改进计划（本文档）
├── v2-quick-start.md          # 快速开始指南
└── v1-vs-v2-comparison.md      # 详细对比文档
```

---

## 📊 改进效果

### 定量指标（预期）

| 指标 | v1.0 | v2.0 预期 | 改进 |
|------|------|----------|------|
| **规范遵循率** | ~60% | ≥95% | +35% |
| **状态抖动率** | ~20% | ≤5% | -75% |
| **AI 理解负担** | 阅读完整规范 | 无需阅读 | -80% |
| **代理选择准确率** | ~70% | ≥90% | +20% |
| **安全违规次数** | 不可控 | 可追踪 | 可量化 |

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

## 🧪 测试验证

### 单元测试

```bash
# 测试系统提示词构建器
cd scripts_v2
python system_prompt_builder.py

# 测试 Agent Loop
python agent_loop.py

# 测试合规追踪器
python compliance_tracker.py
```

### 集成测试

```bash
# 初始化项目
python adds_v2.py init

# 查看状态
python adds_v2.py status

# 查看路由
python adds_v2.py route

# 启动 Agent Loop
python adds_v2.py start --max-turns 10

# 注入系统提示词
python adds_v2.py inject-prompt --output .ai/system_prompt.md
```

---

## 🔄 下一步工作

### 短期（1-2周）

1. **完善代理实现**
   - [ ] 实现 PM Agent 完整逻辑
   - [ ] 实现 Architect Agent 完整逻辑
   - [ ] 实现 Developer Agent 完整逻辑
   - [ ] 实现 Tester Agent 完整逻辑
   - [ ] 实现 Reviewer Agent 完整逻辑

2. **集成测试框架**
   - [ ] 编写单元测试
   - [ ] 编写集成测试
   - [ ] 编写端到端测试

3. **文档完善**
   - [ ] API 文档
   - [ ] 架构设计文档
   - [ ] 贡献指南

### 中期（3-4周）

4. **可视化仪表盘**
   - [ ] Web UI 显示合规性
   - [ ] Web UI 显示进度
   - [ ] Web UI 显示违规记录

5. **AI 集成**
   - [ ] 将系统提示词注入到实际 AI 会话
   - [ ] 支持多种 AI 提供商（OpenAI, Anthropic, etc.）
   - [ ] 自动化测试 AI 遵循规范

6. **多项目管理**
   - [ ] 支持多个项目的并行开发
   - [ ] 项目间依赖管理
   - [ ] 跨项目代理协调

### 长期（1-2月）

7. **高级特性**
   - [ ] 缓存优化（参考 Claude Code 第13章）
   - [ ] 性能监控
   - [ ] 自动化 CI/CD 集成

8. **生态建设**
   - [ ] 插件系统
   - [ ] 社区贡献机制
   - [ ] 最佳实践案例库

---

## 📚 参考资料

### Claude Code 章节

- **第3章**：Agent Loop 状态机设计
- **第5章**：系统提示词架构
- **第13章**：锁存机制设计
- **第14章**：缓存中断检测
- **第16章**：权限系统
- **第17章**：YOLO 分类器
- **第24章**：驾驭工程六原则
- **第25章**：上下文管理五大原则
- **第26章**：六大生产级模式

### 设计原则

1. **提示词即控制面** - 用系统提示词引导行为，而非硬编码
2. **缓存感知设计** - 设计必须考虑缓存稳定性
3. **失败关闭，显式开放** - 默认最安全，显式声明才允许危险操作
4. **A/B测试一切** - 行为变更先验证
5. **先观察再修复** - 建立可观测性
6. **锁存以求稳定** - 防止状态抖动

---

## 🎯 总结

### 核心改进

ADDS v2.0 通过以下改进，从"规范文档"升级为"可执行的规范系统"：

1. **系统提示词自动注入** - AI 无需理解规范
2. **Agent Loop 强制执行** - 状态驱动而非 AI 判断
3. **锁存机制保护** - 防止状态抖动
4. **失败关闭设计** - 默认最安全行为
5. **合规性追踪** - 监控 AI 是否遵循规范

### 设计哲学转变

```
v1.0: 信任 AI → AI 理解规范 → AI 遵循规范（不确定性）
v2.0: 架构约束 → 系统注入规范 → 强制执行规范（确定性）
```

### 与 Claude Code 对齐

v2.0 充分借鉴了 Claude Code 的设计思路，实现了：

- ✅ 提示词即控制面
- ✅ 缓存感知设计
- ✅ 失败关闭哲学
- ✅ 锁存机制
- ✅ 可观测性基础设施

这些改进使 ADDS 成为真正可靠、可执行、可观测的 AI 开发规范系统。

---

**准备就绪，可以开始实施！** 🚀

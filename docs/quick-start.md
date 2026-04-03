# ADDS 快速开始指南

## 🎯 改进亮点

ADDS 基于 Claude Code 的设计思路，从"依赖 AI 理解"升级为"架构约束"：

### 核心改进

| 改进项 | 改进前 | 改进后 |
|--------|----------|--------------|
| **系统提示词** | AI 需阅读完整规范 | 分段式注入，静态/动态边界 |
| **状态管理** | 依赖 AI 记住读取 feature_list.md | Agent Loop 强制读取，失败则停止 |
| **代理选择** | AI 判断（可能出错） | 路由器自动决策 + 锁存保护 |
| **状态稳定性** | 可能抖动 | 锁存机制保证会话内稳定 |
| **安全性** | 依赖 AI 判断 | 失败关闭 + 安全默认值 |
| **可观测性** | 仅日志 | 规范遵循追踪 + 违规记录 |

---

## 🚀 快速开始

### 1. 初始化项目

```bash
cd scripts
python adds.py init
```

**输出**：
```
🚀 ADDS 项目初始化
================================================================================
✅ 创建目录: .ai
✅ 创建目录: .ai/sessions
✅ 创建目录: templates/prompts/sections
✅ 创建功能列表模板: .ai/feature_list.md
✅ 创建进度日志: .ai/progress.md
✅ 创建系统提示词段落: templates/prompts/sections/identity.md
✅ 锁存项目类型: web_app

✅ 初始化完成！
```

### 2. 查看项目状态

```bash
python adds.py status
```

**输出**：
```
📊 ADDS 项目状态
================================================================================

功能总数: 3

状态分布:
  pending: 3

进度: 0.0% (0/3)
```

### 3. 查看代理路由推荐

```bash
python adds.py route
```

**输出**：
```
🧭 代理路由推荐
================================================================================
✅ 代理选择: Developer Agent (有 3 个 pending 功能)

推荐代理: DEVELOPER Agent
原因: 有 3 个待实现功能

================================================================================
代理专属提示词预览:
================================================================================
# Developer Agent - 专属行为约束

## 核心职责
1. 实现单个功能（一次一个）
2. 编写单元测试
3. 更新功能状态
...
```

### 4. 启动 Agent Loop

```bash
python adds.py start --max-turns 10
```

**输出**：
```
🚀 启动 ADDS Agent Loop v2.0
================================================================================
🚀 ADDS Agent Loop 启动
================================================================================
✅ 锁存初始功能数量: 3

================================================================================
📍 迭代 #1
   当前代理: pm
   当前功能: None
================================================================================
🔍 检查环境健康...
✅ 环境健康
✅ 代理选择: PM Agent (项目未初始化)
🔄 代理切换: pm → pm

📋 PM Agent 执行中...
✅ 锁存项目类型: web_app
✅ 锁存技术栈: ['Python', 'FastAPI']
✅ PM Agent 完成: 需求分析完成

...

================================================================================
📍 迭代 #5
   当前代理: developer
   当前功能: user_authentication
================================================================================
💻 Developer Agent 执行中...
✅ 安全选择功能: user_authentication (第一个 pending)
✅ 锁存当前功能: user_authentication
✅ 合法状态转换: pending → in_progress
✅ Developer Agent 完成: 功能 'user_authentication' 实现完成
✅ 合法状态转换: in_progress → testing
🔓 释放功能锁存

...

🏁 ADDS Agent Loop 终止: TerminalReason.ALL_COMPLETED
================================================================================

最终结果: all_completed
功能状态:
  - user_authentication: completed
  - data_validation: completed
  - api_endpoints: completed
✅ 合规报告已保存到: .ai/compliance_report.json
```

### 5. 注入系统提示词

```bash
python adds.py inject-prompt --output .ai/system_prompt.md
```

**输出**：
```
💉 注入系统提示词
================================================================================
✅ 系统提示词已注入到: .ai/system_prompt.md
```

---

## 📂 项目结构

```
your-project/
├── .ai/
│   ├── feature_list.md          # 功能列表（唯一真实来源）
│   ├── progress.md              # 进度日志
│   ├── compliance_report.json   # 合规性报告
│   ├── system_prompt.md         # 生成的系统提示词
│   └── sessions/                # 会话记录
├── templates/
│   └── prompts/
│       ├── sections/            # 提示词段落
│       └── agents/              # 代理专属提示词
└── scripts/
    ├── adds.py               # CLI 主工具
    ├── system_prompt_builder.py # 系统提示词构建器
    ├── agent_loop.py            # Agent Loop 状态机
    └── compliance_tracker.py    # 规范遵循追踪器
```

---

## 🔑 核心概念

### 1. 系统提示词分段架构

参考 Claude Code 第5章，将系统提示词分为：

```
[静态区] 
  ├── identity.md              # AI 身份定义（可全局缓存）
  ├── core_principles.md       # 核心原则（可全局缓存）
  │
[STATIC_BOUNDARY]              # 边界标记
  │
[动态区]
  ├── state_management.md      # 状态管理指令（不缓存）
  ├── feature_workflow.md      # 功能工作流（不缓存）
  ├── agent_routing.md         # 代理路由（不缓存）
  └── safety_constraints.md    # 安全约束（不缓存）
```

**优势**：
- 静态区可全局缓存，节省 token 成本
- 动态区按需生成，适应项目状态
- 边界标记明确区分，便于管理

### 2. Agent Loop 状态机

参考 Claude Code 第3章，显式状态转换：

```
while (true):
  ① 上下文预处理（检查环境健康）
  ② 路由决策（自动选择代理）
  ③ 执行当前代理
  ④ 状态更新（锁存保护）
  ⑤ 终止判定
  ⑥ 继续判定
```

**优势**：
- 不依赖 AI 判断，强制执行
- 状态转换可验证，防止非法跳转
- 锁存机制防止状态抖动

### 3. 锁存机制

参考 Claude Code 第13章，保证会话内稳定：

```python
# 项目级锁存
project_latches.latch_project_type(state, "web_app")
project_latches.latch_tech_stack(state, ["Python", "FastAPI"])

# 功能状态锁存
feature_latches.latch_current_feature(state, "user_authentication")
# 一旦锁存，禁止切换到其他功能
```

**优势**：
- 防止 AI 中途改变决策
- 保证功能专注（一次一个功能）
- 会话内状态一致

### 4. 失败关闭

参考 Claude Code 第2章，默认最安全行为：

```python
# 安全的功能选择
feature = safety.safe_feature_selection(features)
# 默认：选择第一个 pending 功能
# 失败：停止而非猜测

# 安全的状态转换
safety.safe_status_transition(current, target)
# 默认：只允许合法转换
# 失败：拒绝而非猜测
```

**优势**：
- 不确定性场景默认保守行为
- 强制显式声明才允许危险操作
- 避免错误累积

### 5. 规范遵循追踪

参考 Claude Code 第14章，监控 AI 行为：

```python
# 检查：一次一个功能
tracker.check_one_feature_per_session("feature_1")

# 检查：状态驱动
tracker.check_feature_list_exists(".ai/feature_list.md")

# 检查：合法状态转换
tracker.check_valid_status_transition("pending", "completed", "feature_1")

# 生成报告
tracker.get_compliance_report()
```

**优势**：
- 主动检测违规，而非依赖 AI 报告
- 记录证据，便于调试
- 合规分数量化规范遵循程度

---

## 🧪 测试组件

### 测试系统提示词构建器

```bash
cd scripts
python system_prompt_builder.py
```

### 测试 Agent Loop

```bash
python agent_loop.py
```

### 测试合规追踪器

```bash
python compliance_tracker.py
```

---

## 📊 对比 Claude Code

| Claude Code 设计 | ADDS 实现 |
|-----------------|---------------|
| **提示词即控制面** | 系统提示词分段注入 |
| **Agent Loop 状态机** | ADDSAgentLoop 类 |
| **锁存机制** | ProjectLatches + FeatureStateLatches |
| **失败关闭** | SafetyDefaults 类 |
| **YOLO 分类器** | 简化版 AgentRouter |
| **缓存中断检测** | ComplianceTracker |
| **工具级提示词** | build_agent_specific_prompt() |

---

## 🎯 设计哲学对比

### v1.0：依赖 AI 理解

```
用户 → AI 阅读 ADDS 规范 → AI 理解规范 → AI 遵循规范
                ↑
            可能失败
```

**问题**：
- AI 可能不阅读规范
- AI 可能不完全理解规范
- AI 可能忘记遵循规范

### v2.0：架构约束

```
用户 → 系统提示词注入 → Agent Loop 强制执行 → 锁存保护 → 合规追踪
         ↓                    ↓                ↓            ↓
      AI 无需理解          状态驱动         防止抖动      监控行为
```

**优势**：
- AI 无需阅读规范（提示词自动注入）
- 状态驱动而非 AI 判断（Agent Loop 强制）
- 防止状态抖动（锁存机制）
- 失败默认安全（失败关闭）
- 监控 AI 行为（合规追踪）

---

## 🔗 参考资料

- **Claude Code 第3章**：Agent Loop 状态机
- **Claude Code 第5章**：系统提示词架构
- **Claude Code 第13章**：锁存机制设计
- **Claude Code 第14章**：缓存中断检测
- **Claude Code 第17章**：YOLO 分类器
- **Claude Code 第24章**：驾驭工程六原则

---

## 📝 下一步

1. **完善代理实现**：实现完整的 PM/Architect/Developer/Tester/Reviewer 代理逻辑
2. **集成测试框架**：自动化测试 ADDS 规范遵循
3. **可视化仪表盘**：Web UI 显示合规性和进度
4. **AI 集成**：将系统提示词注入到实际的 AI 会话中
5. **多项目管理**：支持多个项目的并行开发

---

## 🤝 贡献

欢迎贡献代码、报告问题、提出建议！

参考 CONTRIBUTING.md（待创建）

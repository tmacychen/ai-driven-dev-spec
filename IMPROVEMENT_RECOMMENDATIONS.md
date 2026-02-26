# ADDS v2.0 改进建议

> 基于 Anthropic 官方最佳实践的对比分析

---

## 📊 核心发现

### 审查文件的关键观点

审查文件 `ADDS_IMPROVEMENT_CRITICAL_REVIEW.md` 提出了一个核心理念：

> **ADDS 是一个 "Harness"（约束框架），而非 "Toolbox"（工具箱）**

**目标用户**：AI Agent（而非人类开发者）

**核心机制**：通过强约束引导 AI 行为，而非提供更多工具

---

## ✅ 当前项目的优势

经过分析，ADDS v2.0 已经在很多方面符合 Anthropic 的最佳实践：

| 维度 | 实现状态 | 说明 |
|------|---------|------|
| **双 Agent 模式** | ✅ 完善 | Initializer + Coding Agent，职责清晰 |
| **结构化状态管理** | ✅ 完善 | feature_list.json, progress.log, architecture.md |
| **增量开发流程** | ✅ 完善 | 每次一个功能，原子提交 |
| **测试驱动验证** | ✅ 完善 | test_cases 内嵌，要求工具证据 |
| **安全执行规范** | ✅ 完善 | 命令白名单，安全检查 |
| **回归保护** | ✅ 完善 | 回归检测机制，修复优先 |
| **环境健康检查** | ✅ 完善 | init.sh 自动化，环境验证 |

---

## ⚠️ 需要改进的关键领域

根据审查文件的建议，以下是需要改进的高优先级领域：

### 1. 更强的约束规则 ⭐⭐⭐

#### 当前状态

`coding_prompt.md` 中有 "Constraints" 部分，但约束力度不够强硬：

```markdown
## Constraints

- ❌ Never work on more than one feature per session.
- ❌ Never mark a feature as complete without tool-based evidence.
- ❌ Never skip the regression check at session start.
- ❌ Never execute commands outside the security whitelist.
- ✅ Always leave the code in a working, mergeable state.
- ✅ Always update documentation alongside code changes.
```

#### 问题分析

- ❌ 缺少具体的"绝对禁止"场景描述
- ❌ 缺少违规检测机制
- ❌ 约束语句不够强硬，AI 可能会"灵活理解"

#### 改进方案

在 `coding_prompt.md` 中增加 **"⛔ 绝对禁止行为"** 章节：

```markdown
## ⛔ 绝对禁止行为

以下行为 **严格禁止**，任何情况下都不可违反：

### 禁止一次做多个功能
- ❌ **错误示例**：看到 F001 完成后，自作主张开始 F002
- ✅ **正确做法**：完成 F001，提交，更新进度，结束会话
- 🔍 **检测机制**：检查 Git commit 是否包含多个 feature ID

### 禁止跳过测试
- ❌ **错误示例**："这个改动很小，不需要测试"
- ✅ **正确做法**：任何代码变更必须运行相关测试
- 🔍 **检测机制**：检查 feature_list.json 中 test_cases 是否全部 status: "passed"

### 禁止修改已完成功能
- ❌ **错误示例**：发现 F001 的小问题，顺手修复
- ✅ **正确做法**：创建新的修复任务 F-BUG-001
- 🔍 **检测机制**：检查 Git diff 是否修改了其他功能的文件

### 禁止假设环境状态
- ❌ **错误示例**："假设数据库已经创建"
- ✅ **正确做法**：运行 init.sh 验证环境
- 🔍 **检测机制**：每个会话开始必须执行环境验证步骤

### 禁止在没有工具证据的情况下标记完成
- ❌ **错误示例**："我认为功能已经完成"
- ✅ **正确做法**：提供测试日志、截图、API 响应等工具执行结果
- 🔍 **检测机制**：检查 progress.log 是否包含验证证据

### 违规后果
如果检测到违规行为：
1. 🛑 立即停止当前工作
2. 🔧 回退到上一个 Git commit
3. 📝 在 progress.log 中记录违规详情
4. ⚠️ 将功能状态标记为 "blocked"
```

---

### 2. 更明确的验证标准 ⭐⭐⭐

#### 当前状态

`feature_list.json` 中有 `test_cases` 和 `acceptance_criteria`，但缺少具体的验证证据要求：

```json
{
  "id": "F002",
  "test_cases": [...],
  "acceptance_criteria": [...],
  "passes": false
}
```

#### 问题分析

- ❌ 缺少 `validation_requirements` 字段
- ❌ 缺少完成标准的明确定义
- ❌ 缺少证据格式规范

#### 改进方案

在 `feature_list.json` 中增加 **`validation_requirements`** 字段：

```json
{
  "id": "F002",
  "category": "auth",
  "core": true,
  "description": "Implement basic user login with hardcoded credentials",
  
  "validation_requirements": {
    "test_evidence": {
      "required": true,
      "format": "terminal_output",
      "must_include": ["PASS", "✓", "Tests: X passed"],
      "description": "测试执行日志，显示所有测试通过"
    },
    "e2e_evidence": {
      "required": true,
      "format": "screenshot_or_video",
      "description": "浏览器截图或视频，显示完整用户操作流程",
      "must_show": [
        "登录表单填写",
        "提交按钮点击",
        "页面跳转结果",
        "欢迎消息显示"
      ]
    },
    "api_response": {
      "required_for_api": true,
      "format": "json",
      "must_match_schema": true,
      "description": "API 响应符合预期格式",
      "example": {
        "status": 200,
        "body": {
          "token": "string",
          "user": "object"
        }
      }
    }
  },
  
  "completion_criteria": [
    "所有 test_cases 状态为 passed",
    "提供了工具执行的证据（截图/日志）",
    "代码已提交到 Git",
    "progress.log 已更新",
    "所有 acceptance_criteria 已满足",
    "所有 security_checks 已处理"
  ],
  
  "test_cases": [...],
  "acceptance_criteria": [...],
  "security_checks": [...]
}
```

---

### 3. 标准化错误恢复机制 ⭐⭐

#### 当前状态

规范中提到了 `regression` 和 `blocked` 状态，但缺乏详细的重试机制：

```markdown
### 8.2 阻塞问题 (Blocked)
- 更新功能状态为 `"status": "blocked"`，记录 `blocked_reason`。
- 跳过该功能，选择下一个可执行功能。
```

#### 问题分析

- ❌ 缺少错误分类
- ❌ 缺少重试机制
- ❌ 缺少自动恢复流程

#### 改进方案

#### 3.1 在 `feature_list.json` 中增加重试字段

```json
{
  "id": "F002",
  "retry_count": 0,
  "max_retries": 3,
  "escalation": {
    "trigger": "retry_count >= max_retries",
    "action": "标记为 blocked，跳过，选择下一个功能"
  }
}
```

#### 3.2 在 `coding_prompt.md` 中增加错误恢复流程

```markdown
## 🔄 错误恢复流程

### 遇到错误时的自动处理机制

AI 在遇到错误时，必须按照以下流程自动处理：

### 场景 1：测试失败

```
运行测试 → 失败
  ↓
1. 记录失败详情到 .ai/test_failure_log.json
2. 截取错误现场（保存当前代码状态）
3. 分析失败原因：
   - 如果是新功能代码问题 → 修复并重试
   - 如果是环境问题 → 运行 init.sh
   - 如果是依赖问题 → 检查并安装依赖
4. 重试计数器 +1
5. 如果 retry_count >= max_retries：
   - Git reset --hard 到上一个 commit
   - 标记功能为 "blocked"
   - 记录阻塞原因到 progress.log
   - 选择下一个功能
```

### 场景 2：环境问题

```
检测到环境问题（缺少 node_modules、venv 等）
  ↓
→ 自动运行 init.sh
→ 无需人类干预
→ 重试验证步骤
```

### 场景 3：依赖问题

```
检测到依赖问题（Module not found、ImportError 等）
  ↓
→ 自动安装缺失依赖
→ 无需人类干预
→ 重试验证步骤
```

### 场景 4：代码问题

```
检测到代码问题（SyntaxError、TypeError 等）
  ↓
→ 自动修复
→ 最多重试 3 次
→ 如果失败，标记为 blocked
```

### 场景 5：需求不明

```
检测到功能描述模糊
  ↓
→ 自动细化需求（查阅 architecture.md、app_spec.md）
→ 无法细化则标记为 blocked
→ 记录问题详情
```

### 场景 6：超出能力范围

```
检测到外部 API 错误、权限问题等
  ↓
→ 记录问题详情
→ 标记为 blocked
→ 跳到下一个功能
```
```

---

### 4. 增强自主解决问题能力 ⭐⭐

#### 当前状态

`coding_prompt.md` 中有 "If anything fails: fix it first before proceeding"，但不够详细：

```markdown
2. **Bootstrap Environment**:
   - Execute `./init.sh` to ensure the environment is healthy.
   - Verify all dependencies are installed.
   - Verify services are running (if applicable).
   - If anything fails: **fix it first before proceeding**.
```

#### 问题分析

- ❌ 缺少问题自动分类
- ❌ 缺少自主决策流程
- ❌ 缺少减少人类干预的机制

#### 改进方案

在 `coding_prompt.md` 中增加 **"🤖 自主问题解决"** 章节：

```markdown
## 🤖 自主问题解决能力

AI Agent 应该能够在没有人类干预的情况下持续工作。

### 自动问题分类

遇到错误时，AI 应该自动分类并处理：

| 问题类型 | 检测方式 | 处理方式 | 需要人类干预？ |
|---------|---------|---------|--------------|
| **环境问题** | 缺少 node_modules、venv 等 | 自动运行 init.sh | ❌ 否 |
| **依赖问题** | Module not found、ImportError | 自动安装缺失依赖 | ❌ 否 |
| **代码问题** | SyntaxError、TypeError | 自动修复，最多 3 次 | ❌ 否 |
| **需求不明** | 功能描述模糊 | 自动细化需求 | ❌ 否 |
| **超出能力** | 外部 API 错误、权限问题 | 标记 blocked，跳过 | ✅ 是 |

### 自主决策原则

1. **优先尝试自动修复**，而不是停下来等待人类指令
2. **记录所有决策过程** 到 progress.log
3. **只有在超出能力范围时** 才标记为 blocked
4. **保持环境始终处于可交付状态**

### 错误恢复检查清单

每遇到一个错误，执行以下检查：

- [ ] 错误类型是什么？（环境/依赖/代码/需求/能力）
- [ ] 是否可以自动修复？
- [ ] 重试次数是否已达上限？
- [ ] 是否需要回退到上一个 commit？
- [ ] 是否需要标记为 blocked？
- [ ] 是否已记录到 progress.log？
```

---

## 📋 改进实施优先级

### 高优先级 ⭐⭐⭐（立即实施）

1. **强化约束规则**
   - 在 `coding_prompt.md` 中增加 "⛔ 绝对禁止行为" 章节
   - 添加违规检测机制说明
   - 加强约束语句的强硬程度

2. **明确验证标准**
   - 在 `feature_list_example.json` 中增加 `validation_requirements` 字段
   - 在 `initializer_prompt.md` 中要求生成该字段
   - 在 `coding_prompt.md` 中要求验证该字段

3. **标准化错误恢复**
   - 在 `coding_prompt.md` 中增加错误恢复流程
   - 在 `feature_list_example.json` 中增加 retry 相关字段
   - 在规范中增加错误分类说明

### 中优先级 ⭐⭐（后续迭代）

4. **增强自主解决问题能力**
   - 在 `coding_prompt.md` 中增加自主问题解决章节
   - 减少需要人类干预的场景
   - 添加自动问题分类表

5. **细化测试要求**
   - 在 `testing_prompt.md` 中增加不同项目类型的测试模板
   - 明确测试覆盖的最低要求
   - 增加测试证据收集的标准格式

### 低优先级 ⭐（可选）

6. **性能监控**
   - 在 `feature_list.json` 中增加 `time_spent` 字段
   - 在 `progress.log` 中记录每个功能的开发时间
   - 用于后续优化 AI 效率

---

## 🎯 改进的核心原则

根据审查文件，所有改进必须遵循以下原则：

```
❌ 为 AI 提供更多工具
✅ 为 AI 设定更强约束

❌ 帮助人类理解项目
✅ 帮助 AI 正确执行

❌ 适配不同场景
✅ 固定标准流程

❌ 人类协作模式
✅ 单线程增量开发
```

---

## 📝 总结

ADDS v2.0 已经非常接近 Anthropic 的官方最佳实践，主要改进方向是：

1. **更强的约束** - 防止 AI 越界
2. **更明确的标准** - 定义"完成"的清晰标准
3. **更好的恢复** - 自动处理错误，减少人类干预
4. **更少的干预** - AI 自主解决问题

**核心观点**：ADDS 是一个 **Harness（约束框架）**，不是 **Toolbox（工具箱）**。

所有改进都应该围绕"约束 AI 行为"展开，而不是"为 AI 提供更多工具"。

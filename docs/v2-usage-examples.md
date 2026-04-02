# ADDS v2.0 使用示例

## 📋 目录

1. [快速开始](#快速开始)
2. [实际项目示例](#实际项目示例)
3. [常见场景](#常见场景)
4. [最佳实践](#最佳实践)
5. [故障排查](#故障排查)

---

## 快速开始

### 步骤 1：初始化项目

```bash
# 创建新项目
mkdir my-project
cd my-project

# 初始化 ADDS
python3 /path/to/adds_v2.py init
```

**输出**：
```
🚀 ADDS v2.0 项目初始化
================================================================================
✅ 创建目录: .ai
✅ 创建目录: .ai/sessions
✅ 创建功能列表模板: .ai/feature_list.md
✅ 创建进度日志: .ai/progress.md
✅ 锁存项目类型: web_app

✅ 初始化完成！
```

### 步骤 2：编辑功能列表

```bash
# 编辑功能列表
vim .ai/feature_list.md
```

**示例内容**：
```markdown
# 功能列表

## 功能 1: user_registration
- **描述**: 实现用户注册功能
- **状态**: pending
- **依赖**: 无
- **验收标准**:
  - 用户可以使用邮箱注册
  - 密码使用 bcrypt 加密
  - 邮箱格式验证

## 功能 2: user_login
- **描述**: 实现用户登录功能
- **状态**: pending
- **依赖**: user_registration
- **验收标准**:
  - 用户可以使用邮箱和密码登录
  - 返回 JWT token
  - 登录失败有友好提示
```

### 步骤 3：查看推荐代理

```bash
python3 /path/to/adds_v2.py route
```

**输出**：
```
🧭 代理路由推荐
================================================================================
✅ 代理选择: Developer Agent (有 2 个 pending 功能)

推荐代理: DEVELOPER Agent
原因: 有 2 个待实现功能
```

### 步骤 4：启动开发流程

```bash
python3 /path/to/adds_v2.py start --max-turns 10
```

**输出**：
```
🚀 启动 ADDS Agent Loop v2.0
================================================================================
✅ 锁存初始功能数量: 2

📍 迭代 #1
   当前代理: developer
   当前功能: None
================================================================================
💻 Developer Agent 执行中...
  [20:37:10] select_feature: 选择功能: user_registration
  [20:37:10] implement_feature: 实现功能: user_registration
  [20:37:10] write_unit_tests: 编写测试: user_registration
  [20:37:10] update_status: 状态: pending → testing

📍 迭代 #2
================================================================================
🧪 Tester Agent 执行中...
  [20:37:10] select_testing_feature: 选择功能: user_registration
  [20:37:10] run_tests: 运行测试: user_registration
  [20:37:10] check_regression: 检测回归
  [20:37:10] update_status: 状态: testing → completed

...

🏁 ADDS Agent Loop 终止: TerminalReason.ALL_COMPLETED
================================================================================
```

### 步骤 5：查看合规报告

```bash
cat .ai/compliance_report.json
```

**输出**：
```json
{
  "timestamp": "2026-04-02T20:37:10",
  "summary": {
    "total_checks": 15,
    "passed_checks": 15,
    "failed_checks": 0,
    "pass_rate": 1.0,
    "compliance_score": 1.0,
    "violations_count": 0
  }
}
```

---

## 实际项目示例

### 示例 1：Web API 项目

#### 项目结构

```
my-api/
├── .ai/
│   ├── feature_list.md
│   ├── progress.md
│   ├── architecture.md
│   └── compliance_report.json
├── src/
│   ├── api/
│   │   ├── auth.py
│   │   ├── users.py
│   │   └── products.py
│   ├── models/
│   │   ├── user.py
│   │   └── product.py
│   └── services/
├── tests/
│   ├── unit/
│   └── integration/
└── templates/
    └── prompts/
        ├── sections/
        └── agents/
```

#### 功能列表示例

```markdown
# 功能列表

## 阶段 1：基础架构

### 功能 1: project_setup
- **描述**: 项目初始化和配置
- **状态**: completed
- **依赖**: 无
- **验收标准**:
  - Poetry 配置完成
  - 基础目录结构创建
  - 代码格式化工具配置

### 功能 2: database_connection
- **描述**: 数据库连接和 ORM 配置
- **状态**: completed
- **依赖**: project_setup
- **验收标准**:
  - PostgreSQL 连接成功
  - SQLAlchemy 配置完成
  - 基础模型定义

## 阶段 2：核心功能

### 功能 3: user_authentication
- **描述**: 用户认证（注册、登录、登出）
- **状态**: in_progress
- **依赖**: database_connection
- **验收标准**:
  - 用户注册功能正常
  - JWT token 生成和验证
  - 密码加密存储

### 功能 4: product_crud
- **描述**: 产品 CRUD 操作
- **状态**: pending
- **依赖**: database_connection
- **验收标准**:
  - 创建产品 API
  - 查询产品 API
  - 更新产品 API
  - 删除产品 API

### 功能 5: order_management
- **描述**: 订单管理
- **状态**: pending
- **依赖**: user_authentication, product_crud
- **验收标准**:
  - 创建订单
  - 查询订单
  - 更新订单状态
```

#### 运行示例

```bash
# 查看当前状态
python3 adds_v2.py status

# 输出：
📊 ADDS v2.0 项目状态
================================================================================
功能总数: 5

状态分布:
  completed: 2
  in_progress: 1
  pending: 2

进度: 40.0% (2/5)

最近合规报告:
合规分数: 0.95
违规次数: 1

# 查看推荐代理
python3 adds_v2.py route

# 输出：
🧭 代理路由推荐
================================================================================
✅ 代理选择: Developer Agent (有 1 个 in_progress 功能)

推荐代理: DEVELOPER Agent
原因: 有 1 个正在实现的功能

# 继续开发
python3 adds_v2.py start --max-turns 5
```

---

### 示例 2：CLI 工具项目

#### 项目结构

```
my-cli/
├── .ai/
│   ├── feature_list.md
│   └── progress.md
├── src/
│   ├── commands/
│   │   ├── init.py
│   │   ├── build.py
│   │   └── deploy.py
│   ├── utils/
│   └── __main__.py
└── tests/
```

#### 功能列表

```markdown
# 功能列表

## 功能 1: cli_framework
- **描述**: CLI 框架搭建（使用 Click）
- **状态**: completed
- **依赖**: 无
- **验收标准**:
  - 基础命令结构
  - 帮助信息显示
  - 版本信息显示

## 功能 2: init_command
- **描述**: init 命令实现
- **状态**: testing
- **依赖**: cli_framework
- **验收标准**:
  - 创建项目目录结构
  - 生成配置文件
  - 交互式问答

## 功能 3: build_command
- **描述**: build 命令实现
- **状态**: pending
- **依赖**: cli_framework
- **验收标准**:
  - 编译项目
  - 生成可执行文件
  - 错误处理完善
```

---

## 常见场景

### 场景 1：添加新功能

```bash
# 1. 编辑功能列表，添加新功能
vim .ai/feature_list.md

# 添加：
## 功能 6: email_notification
- **描述**: 邮件通知功能
- **状态**: pending
- **依赖**: user_authentication
- **验收标准**:
  - 用户注册后发送欢迎邮件
  - 订单状态变更发送通知

# 2. 查看状态
python3 adds_v2.py status

# 3. 启动开发
python3 adds_v2.py start
```

### 场景 2：修复 Bug

```bash
# 1. 手动标记功能为 bug 状态
vim .ai/feature_list.md

# 修改：
## 功能 3: user_authentication
- **状态**: bug  # 改为 bug

# 2. 启动修复
python3 adds_v2.py start

# Developer Agent 会自动修复 bug
```

### 场景 3：重构代码

```bash
# 1. 创建重构任务
vim .ai/feature_list.md

# 添加：
## 功能 7: refactor_database_layer
- **描述**: 重构数据库访问层
- **状态**: pending
- **依赖**: 无
- **验收标准**:
  - 提取公共数据库操作
  - 优化查询性能
  - 保持原有功能不变

# 2. 运行
python3 adds_v2.py start
```

### 场景 4：多项目管理

```bash
# 项目 A
cd ~/projects/api-gateway
python3 /path/to/adds_v2.py status

# 项目 B
cd ~/projects/user-service
python3 /path/to/adds_v2.py status

# 每个项目独立的 feature_list.md
```

---

## 最佳实践

### 1. 功能粒度控制

**推荐**：
```
✅ 功能大小：50-200 行代码或 1-3 小时工作量
✅ 功能描述：明确、可测试、可验收
✅ 验收标准：具体、可量化、可验证
```

**避免**：
```
❌ 功能太大："实现整个用户系统"（应拆分为多个功能）
❌ 功能太小："创建一个文件"（应合并到相关功能）
❌ 模糊描述："优化性能"（应具体化：优化查询响应时间 < 100ms）
```

### 2. 依赖关系设计

**推荐**：
```markdown
✅ 线性依赖：
feature_1 (无依赖)
  └── feature_2 (依赖 feature_1)
      └── feature_3 (依赖 feature_2)

✅ 并行依赖：
feature_1 (无依赖)
feature_2 (无依赖)
feature_3 (依赖 feature_1, feature_2)
```

**避免**：
```markdown
❌ 循环依赖：
feature_1 依赖 feature_2
feature_2 依赖 feature_1

❌ 过度依赖：
feature_10 依赖 feature_1, feature_2, ..., feature_9
```

### 3. 状态管理

**推荐**：
```
✅ 严格按照状态转换规则：
pending → in_progress → testing → completed

✅ 使用锁存保护：
一旦开始某个功能，会话内不切换

✅ 及时更新状态：
每个阶段完成后立即更新
```

**避免**：
```
❌ 跳过状态：
pending → completed（跳过 testing）

❌ 倒退状态：
testing → pending

❌ 忘记更新状态：
功能已完成但状态仍为 in_progress
```

### 4. 证据记录

**推荐**：
```markdown
## 实现证据

### 文件修改
- src/api/auth.py
- src/models/user.py

### 工具执行
- pytest tests/unit/test_auth.py
- black src/api/auth.py

### 测试结果
- 单元测试：5 passed
- 覆盖率：85%
```

**避免**：
```
❌ 无证据：
"功能已完成"（但没有提供任何证据）

❌ 证据不足：
只提供"代码已写"（没有测试、没有工具执行记录）
```

### 5. 合规性维护

**推荐**：
```
✅ 定期查看合规报告：
cat .ai/compliance_report.json

✅ 关注违规类型：
- multiple_features_per_session（一次多功能）
- missing_feature_list（缺少状态文件）
- invalid_status_transition（非法状态转换）

✅ 保持合规分数 > 0.9
```

**避免**：
```
❌ 忽略违规：
继续开发而不修复违规

❌ 合规分数过低：
< 0.7 表示严重偏离规范
```

---

## 故障排查

### 问题 1：功能状态卡住

**症状**：
```
功能一直处于 in_progress 或 testing 状态
```

**解决方案**：
```bash
# 1. 检查功能列表
cat .ai/feature_list.md

# 2. 手动更新状态
vim .ai/feature_list.md
# 修改状态为正确值

# 3. 重启 Agent Loop
python3 adds_v2.py start
```

### 问题 2：合规分数过低

**症状**：
```
合规分数 < 0.7
```

**解决方案**：
```bash
# 1. 查看违规详情
cat .ai/compliance_report.json

# 2. 根据违规类型修复：
# - multiple_features_per_session：确保一次只实现一个功能
# - missing_feature_list：检查文件路径
# - invalid_status_transition：检查状态转换规则

# 3. 重新运行
python3 adds_v2.py start
```

### 问题 3：代理选择错误

**症状**：
```
系统选择了错误的代理
```

**解决方案**：
```bash
# 1. 手动指定代理（高级功能）
# 编辑配置文件，设置 preferred_agent

# 2. 或手动调用代理
# （需要修改代码，暂不支持）
```

### 问题 4：锁存机制阻止操作

**症状**：
```
错误：功能状态锁存保护
```

**解决方案**：
```bash
# 这是正常行为！
# 表示系统正在保护当前功能的完整性

# 解决方法：
# 1. 完成当前功能
# 2. 或重新开始会话（重置锁存）
python3 adds_v2.py init  # 重新初始化会重置锁存
```

### 问题 5：状态转换被拒绝

**症状**：
```
错误：非法状态转换
```

**解决方案**：
```bash
# 检查状态转换规则：
pending → in_progress ✅
in_progress → testing ✅
testing → completed ✅

pending → completed ❌（非法）
testing → pending ❌（非法）

# 修复方法：
# 1. 查看当前状态
cat .ai/feature_list.md

# 2. 按正确路径转换
# 如果是 pending，先转为 in_progress
# 如果是 in_progress，先转为 testing
# 如果是 testing，可转为 completed
```

---

## 📚 参考资源

- [快速开始指南](v2-quick-start.md)
- [详细对比文档](v1-vs-v2-comparison.md)
- [改进计划](improvement-plan.md)
- [API 文档](api-reference.md)（待创建）

---

**更新时间**：2026-04-02
**版本**：ADDS v2.0
**状态**：✅ 生产就绪

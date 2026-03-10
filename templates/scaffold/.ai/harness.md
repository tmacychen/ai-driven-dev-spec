# Harness Configuration

> AI 开发 Harness 配置 - 控制开发流程行为

## 核心模块

| 模块 | 启用 | 说明 |
|------|:----:|------|
| Dual Agent Pattern | ✅ | 初始化 Agent + 编码 Agent 分离 |
| Regression Check | ✅ | 每次会话检查已完成的核心功能 |
| Atomic Commits | ✅ | 每个会话只完成一个功能 |
| Environment Validation | ✅ | 会话开始时验证环境 |
| Tool-based Validation | ✅ | 必须提供工具执行证据 |
| Command Whitelist | ✅ | 安全命令白名单 |
| Data Collection | ✅ | 收集失败/成功案例用于改进 |

## 回归检查配置

```
num_features_to_check: 1-2
selection_criteria: core=true AND passes=true
auto_fix: true
```

## 环境验证配置

```
run_init_sh: true
check_dependencies: true
verify_services: true
deep_health_checks:
  - Database connectivity
  - API endpoint reachability
  - Required environment variables
  - Disk space and permissions
```

## 数据收集配置

| 收集类型 | 启用 | 说明 |
|----------|:----:|------|
| Failures | ✅ | 失败案例、恢复过程 |
| Successes | ✅ | 成功模式、效率指标 |
| Timing | ✅ | 每功能耗时 |
| Context Usage | ✅ | Token 使用量 |

### 失败类型

- test_failure
- environment_error
- dependency_error
- code_error
- requirement_unclear
- beyond_capability

### 存储位置

```
.ai/training_data/
├── failures.jsonl
├── successes.jsonl
├── performance.jsonl
└── context_metrics.jsonl
```

### 隐私保护

自动排除敏感字段：password, token, secret, api_key, credential

## 安全配置

### 禁止命令

- `sudo`
- `rm -rf /`
- `curl | bash`

### 审批规则

新命令需要人工确认后才可执行

---

## 设计理念

**Build for Deletion** - 假设未来模型会淘汰当前逻辑，因此：
- 模块化设计，清晰接口
- 每个约束都有文档化的理由
- 定期审查是否可以简化

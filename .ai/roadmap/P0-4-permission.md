# P0-4: 命令批准机制（安全 Layer 2）

> 📋 [返回总览](README.md) | [← P0-3: 记忆系统](P0-3-memory-system.md) | [P0 集成 →](P0-integration.md)

---

### 设计目标

在现有 Layer 1（黑白名单）基础上，增加交互式命令批准机制。Docker 等执行后端隔离放到 P2。

### 三级权限模型

```
┌─────────────────────────────────────────────────┐
│ Layer 1: 命令黑白名单（已有，在 CORE_GUIDELINES.md）│
│  - 静态规则，无法动态调整                          │
│  - 仅能拒绝明确禁止的命令                          │
└──────────────────────┬──────────────────────────┘
                       │ 增强
┌──────────────────────▼──────────────────────────┐
│ Layer 2: 命令批准机制（新增）                      │
│  - 三级权限：Allow / Ask / Deny                    │
│  - 权限来源：会话 > 命令行 > 项目设置 > 用户设置   │
│  - 模式匹配：工具名 + 命令模式 + 路径模式          │
│  - 死循环防护：同一工具连续拒绝 3 次后冷却 30 秒   │
└─────────────────────────────────────────────────┘
```

### 权限配置

```json
// .ai/settings.json
{
  "permissions": {
    "mode": "default",
    "rules": {
      "allow": [
        "bash(ls*)",
        "bash(cat*)",
        "bash(python*)",
        "bash(git status*)",
        "bash(git log*)",
        "bash(git diff*)",
        "read(*)",
        "write(./*)"
      ],
      "ask": [
        "bash(rm*)",
        "bash(npm install*)",
        "bash(pip install*)",
        "bash(git push*)",
        "bash(git commit*)",
        "write(../../*)"
      ],
      "deny": [
        "bash(sudo*)",
        "bash(chmod 777*)",
        "bash(mkfs*)",
        "bash(dd*)",
        "write(/etc/*)",
        "write(/System/*)",
        "write(/usr/*)"
      ]
    }
  }
}
```

### 权限模式

| 模式 | 说明 |
|------|------|
| `default` | 敏感操作逐一确认（推荐） |
| `plan` | 只能读不能写（探索阶段） |
| `auto` | AI 分类器自动决策（高级） |
| `bypass` | 所有操作自动放行（危险） |

### 实现文件变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `scripts/permission_manager.py` | 新建 | 权限管理器 |
| `scripts/agent_loop.py` | 修改 | 工具执行前插入权限检查 |
| `.ai/settings.json` | 更新 | 添加权限配置 |

---


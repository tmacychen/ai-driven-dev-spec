# ADDS 功能列表

> **最后更新**: 2026-04-11
> **状态**: P0-1~P0-4 完成，P0-5 设计完成待实现

---

## P0 核心功能

### P0-1: 大模型调用层 ✅
- **描述**: 统一的模型调用层，支持 API/CLI/SDK 三种模式
- **状态**: 完成
- **文件**: `scripts/model/` (9 个文件)
- **测试**: ✅ 通过

### P0-2: 上下文压缩策略 ✅
- **描述**: 两层压缩（Layer1 实时 + Layer2 归档），Token 预算管理，链式 Workspace
- **状态**: 完成
- **文件**: `scripts/token_budget.py`, `scripts/session_manager.py`, `scripts/context_compactor.py`, `scripts/summary_decision_engine.py`
- **测试**: ✅ 通过

### P0-3: 记忆系统 ✅
- **描述**: 两层记忆、记忆进化/排毒、角色化记忆、反思协议、回归警报
- **状态**: 完成
- **文件**: `scripts/memory_manager.py`, `scripts/memory_conflict_detector.py`, `scripts/memory_retriever.py`, `scripts/memory_detox.py`, `scripts/consistency_guard.py`, `scripts/role_memory_injector.py`, `scripts/memory_cli.py`, `scripts/index_priority_sorter.py`
- **测试**: ✅ 通过

### P0-4: 权限系统 ✅
- **描述**: 三级权限（Allow/Ask/Deny），死循环防护，会话级覆盖
- **状态**: 完成
- **文件**: `scripts/permission_manager.py`
- **测试**: ✅ 通过

### P0-5: TUI 重构 ⏳
- **描述**: 多 Workspace 架构，分屏多任务视图，Agent 间通信
- **状态**: 设计完成，待实现
- **设计文档**: `.ai/roadmap/P0-5-tui-redesign.md`
- **预估工作量**: 4 周

---

## 基础功能

### 功能 1: CLI 皮肤引擎 ✅
- **描述**: 基于 YAML 的终端美化系统，支持多主题切换
- **状态**: 完成
- **文件**: `scripts/skins/`

### 功能 2: pyfiglet 动态 Logo ✅
- **描述**: 使用 pyfiglet 运行时生成 ASCII art logo，支持自定义字体
- **状态**: 完成

### 功能 3: 多主题皮肤 ✅
- **描述**: 7 个内置主题（default/cyberpunk/matrix/nordic/sakura/skynet/vault-tec）
- **状态**: 完成

---

## P1 规划功能

### P1-1: 技能渐进式披露 ⏳
- **描述**: Level 0-2 技能加载机制，与 MiniMax Skills 生态集成
- **状态**: 待实现

### P1-2: Agent Loop 韧性增强 ⏳
- **描述**: 7 种终止条件 + 5 种继续条件，PTL 恢复
- **状态**: 待实现

### P1-3: 记忆共振 ⏳
- **描述**: staging.mem 跨角色二次进化
- **状态**: 待实现

### P1-4: 语义检索升级 ⏳
- **描述**: VectorMemoryRetriever (LanceDB)
- **状态**: 待实现

---

## P2 规划功能

### P2-1: 执行后端隔离 ⏳
- **描述**: Docker/SSH/远程沙箱
- **状态**: 待实现

### P2-2: 多平台通信网关 ⏳
- **描述**: 多平台集成
- **状态**: 待实现

### P2-3: Fork 子 Agent 路径 ⏳
- **描述**: `/fork` 命令，从当前 Workspace 派生子 Workspace
- **状态**: 待实现

### P2-4: 定时调度系统 ⏳
- **描述**: 自动化任务
- **状态**: 待实现

---
description: 项目会话交接规范流程（含安全与稳定性验证）
---

# 会话交接流程 (Handoff Workflow)

完成一次增量功能后，AI Agent 必须执行此流程，以便新上下文窗口能够平稳接手。

## 交接清单

### 1. 代码提交
- [ ] 所有代码变更已通过 `git add . && git commit` 提交。
- [ ] 提交信息格式正确：`feat(<scope>): desc [Closes #ID]`。
- [ ] 没有未跟踪的关键文件。

### 2. 状态同步
- [ ] `.ai/feature_list.json` 已更新。
- [ ] `progress.log` 已更新：
  - 更新了顶部的 "Overall Status"。
  - **追加** 了本次会话的人性化历史记录。
  - "Current Focus" 指向下一个待开发功能。

### 3. 交接说明
在 `progress.log` 中清楚列出：
- ✅ 本次完成了什么
- 🎯 下一步应开始哪个任务
- ⚠️ 是否有已知的未修复 Bug 或技术债
- 💡 任何关键的设计决策或上下文信息

### 4. 环境清理
- [ ] 确保没有悬挂的后台进程（如未关闭的 dev server）。
- [ ] 如有临时文件，已清理。

### 5. 验证交接
- [ ] 运行 `bash init.sh` 确认项目在"干净"状态下依然能通过自检。
- [ ] 运行 1 个核心功能的测试确认系统稳定。
- [ ] 在 `progress.log` 中确认下一次会话的基础入口。

### 6. 归档会话（可选）
如果有重要的思考过程或设计决策，追加到 `.ai/session_log.jsonl`：

```json
{"timestamp": "2026-02-26T14:00:00Z", "session": 5, "feature": "F012", "action": "completed", "notes": "Chose SQLite over PostgreSQL for simplicity in dev phase", "next": "F013"}
```

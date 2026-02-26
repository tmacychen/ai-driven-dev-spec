---
description: 单个 AI 增量开发会话流程（含安全与回归检查）
---

# 开发会话流程 (Development Session Workflow)

// turbo-all

## Phase 1: 环境与稳定性 (必须先执行)

1. 运行 `bash init.sh` 确保环境就绪、依赖已安装、服务已启动。
2. 读取 `CORE_GUIDELINES.md` 对齐角色，读取 `progress.log` 和 `.ai/feature_list.json` 获取最新上下文。
3. 运行 `git log --oneline -5` 查看最近变更。
4. **回归检查**：从已完成的核心功能中挑选 1-2 个，运行其 `test_cases`。
   - 如果全部通过 → 继续。
   - 如果有失败 → **立即修复**，标记为 `regression`，记录到 progress.md。

## Phase 2: 任务选取与开发

5. 加载 `templates/prompts/coding_prompt.md` 作为系统提示词。
6. **任务选取**：在 `.ai/feature_list.json` 中找到第一个符合条件的任务：
   - `passes: false`
   - `status: "pending"`
   - 所有 `dependencies` 已完成
   - 按 `priority` 排序（high > medium > low）
7. 更新该功能的 `status` 为 `"in_progress"`。

## Phase 3: 实现与验证

8. **编写代码**：仅针对选中的功能。
9. **验证实现**：
   - 读取该功能的 `validation_requirements` 和 `completion_criteria`。
   - 执行所有 `test_cases`。
10. **收集证据**：获取符合 `validation_requirements` 格式的日志、截图或 API 响应。
11. **处理失败 (Retry)**：
    - 如果测试失败，根据错误类型分类并尝试修复。
    - 增加 `retry_count`。
    - 如果达到 `max_retries`，执行 `git reset --hard`，标记为 `blocked` 并跳过。
12. **安全与审查**：验证 `security_checks` 已处理，参照 `review_prompt.md` 自查。

## Phase 4: 持久化与交接

13. Git 提交。
14. 更新 `.ai/feature_list.json`:
    - `passes: true`, `status: "completed"`, `last_worked_on: <timestamp>`
15. 更新 `progress.log`:
    - **追加** 本次会话的人性化总结、验证证据、交接说明。
    - 更新顶部的总体统计。
16. 输出会话总结报告。

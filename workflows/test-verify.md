---
description: 测试与验证工作流
---

# 测试与验证流程 (Test & Verify Workflow)

// turbo-all

## 何时执行

- 每个功能实现完成后
- 每个会话开始时（回归测试）
- 合并代码前

## 步骤

1. **加载测试指南**：阅读 `templates/prompts/testing_prompt.md` 了解验证标准。

2. **识别测试类型**：
   - Web 项目 → E2E 测试优先（Playwright/Cypress）
   - API 项目 → Integration 测试（pytest/Jest）
   - CLI 项目 → 命令行输出测试

3. **执行功能测试**：
   ```bash
   # 运行当前功能的测试用例
   npm test -- --grep "feature-name"
   # 或
   pytest tests/test_feature.py -v
   ```

4. **收集证据**：
   - 复制测试输出到终端
   - 确认所有断言显示 PASS
   - 如有 E2E 测试，确认页面行为符合预期

5. **回归测试**（会话开始时）：
   - 从 `.ai/feature_list.json` 中筛选 `core: true` 且 `passes: true` 的功能
   - 运行其 `test_cases`
   - 如有失败，按 regression 处理流程操作

6. **更新测试状态**：
   - 在 `.ai/feature_list.json` 中更新每个 `test_cases[].status`
   - `"passed"` | `"failed"` | `"pending"`

7. **质量审查**：
   ```bash
   # Lint 检查
   npm run lint    # 或 flake8, eslint, etc.
   
   # 类型检查（如适用）
   npx tsc --noEmit    # TypeScript
   mypy src/            # Python
   ```

8. **输出验证报告**：
   ```
   ## 🧪 测试报告
   
   ### 功能: [Feature ID] - [Description]
   - test-001: ✅ PASSED
   - test-002: ✅ PASSED
   - test-003: ❌ FAILED (原因: ...)
   
   ### 质量检查
   - Lint: ✅ 0 errors
   - Type Check: ✅ passed
   
   ### 总结
   X/Y 测试通过
   ```

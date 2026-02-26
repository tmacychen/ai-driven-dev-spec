---
description: 初始化 AI 自主开发项目流程
---

# 初始化项目流程 (Initialization Workflow)

// turbo-all

1. 创建项目目录并进入。
2. 拷贝 `templates/scaffold/` 模板文件夹到当前项目根目录。
3. 创建 `app_spec.md`，用详细的自然语言描述你想要构建的应用（参考 `examples/app_spec_example.md`）。
4. 加载 `templates/prompts/initializer_prompt.md` 作为系统提示词（上下文）。
5. 运行 AI 指令，要求开启"初始化 Agent"模式，生成：
    - `CORE_GUIDELINES.md` (自引导核心指南)
    - `progress.log` (人性化进度日志)
    - `.ai/feature_list.json`（含 test_cases, security_checks, core 标记）
    - `.ai/architecture.md`（技术栈、架构、数据流）
6. 验证 `init.sh` 可以正确运行：`chmod +x init.sh && bash init.sh`。
7. 初始化 Git 仓库并进行首次提交：
   ```bash
   git init
   git add .
   git commit -m "chore: initial project setup"
   ```
8. 验证 `.ai/feature_list.json` 中每个功能都包含 `test_cases` 字段。
9. 输出初始化报告：总功能数、高/中/低优先级分布、核心功能数量。

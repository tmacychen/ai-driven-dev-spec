# Agent 经验笔记

> 此文件由 Agent 自动维护，记录跨会话的关键经验和知识。
> 每次会话启动时作为"冻结快照"注入，修改在下次会话生效。

---

## 环境事实

- 项目：ai-driven-dev-spec (ADDS)
- 语言：Python 3.9+
- 核心脚本：scripts/ 目录下
- 状态文件：.ai/ 目录下

## 项目规范

- 功能列表(.ai/feature_list.md)是唯一真相源
- 一次一个功能，不允许并行开发
- 每个功能必须有测试证据
- 原子提交：一个功能一个 commit

## 经验教训

- P0-1 模型层：三种适配器（API/CLI/SDK）+ TaskDispatcher 统一协议 + SkillGenerator 技能自动生成
- P0-2 压缩层：错误信号检测要排除测试结果中的 "0 failed" 等非错误信号；Session 时间戳可能冲突需处理
- Token 预算分配：SP 15% + Memory 10% + History 55% + Tool 15% + Reserve 5%
- 链式 Session：.mem 文件双区结构（摘要+完整记录），APPEND-ONLY 原则

## 工作模式

- Agent Loop 五阶段：上下文预处理 → 路由决策 → 执行代理 → 状态更新 → 终止判定
- 安全约束：失败关闭，默认最安全行为
- 合规追踪：主动检测违规

## 已知限制

- ~~无上下文压缩机制（长会话可能爆 token）~~ → P0-2 已解决
- 无跨会话记忆（正在改进中）→ P0-3 将解决
- 无工具执行沙箱（直接本地执行）→ P2 将解决
- 旧版 test_integration.py 引用了已删除的 ADDSAgentLoop 等类，需要重写

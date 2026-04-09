# ADDS 改进路线图

> **来源**: 基于 Claude Code 架构白皮书与 Hermes Agent 研究报告的核心知识提炼
> **创建时间**: 2026-04-09
> **最后更新**: 2026-04-09 (P0 第四轮讨论)
> **状态**: P0 第四轮讨论（角色化记忆/反思协议/回归警报与元诊断/注意力热点与强制复读/记忆晋升仪式/记忆共振）

---

## 一、改进总览

### 改进优先级矩阵

| 优先级 | 改进项 | 来源 | 影响范围 | 预估工作量 |
|--------|--------|------|----------|-----------|
| 🔴 P0-1 | 大模型调用层 | Claude Code + MiniMax | 基础能力 | 大 |
| 🔴 P0-2 | 上下文压缩策略（两层） | Claude Code | Agent Loop 核心 | 大 |
| 🔴 P0-3 | 记忆系统（两层+无限记忆+角色化+免疫） | Hermes + Claude Code | 跨会话进化 | 大 |
| 🔴 P0-4 | 命令批准机制 | Claude Code + Hermes | 安全体系 | 中 |
| 🟡 P1 | 技能渐进式披露 | Hermes | Token 优化 | 中 |
| 🟡 P1 | Agent Loop 韧性增强 | Claude Code | 稳定性 | 中 |
| 🟢 P2 | 执行后端隔离(Docker/SSH) | Hermes | 安全体系 | 大 |
| 🟢 P2 | 多平台通信网关 | Hermes | 可达性 | 大 |
| 🟢 P2 | Fork 子 Agent 路径 | Claude Code | 缓存优化 | 中 |
| 🟢 P2 | 定时调度系统 | Hermes | 自动化 | 小 |

---

## 二、P0-1: 大模型调用层

### 设计目标

ADDS 当前完全缺失大模型调用能力。需要实现统一的模型调用层，同时支持 **API 调用** 和 **CLI 工具调用** 两种模式，并在启动时交互式让用户选择。

**核心设计原则**：
1. **API 模式**: 参考 Claude Code / Hermes 的交互方式 — 直接 HTTP 调用，标准消息格式
2. **CLI 模式**: 各 CLI 工具的输入输出/命令格式各异，需要**统一的任务派发协议**
3. **Provider 扩展**: 首批支持 MiniMax + Codebuddy，通过注册表机制可扩展

### 首批支持：MiniMax + Codebuddy

#### MiniMax

| 维度 | API 模式 | CLI 模式 |
|------|---------|---------|
| **调用方式** | HTTP API（OpenAI/Anthropic 兼容） | 命令行工具 `mmx` |
| **认证** | `MINIMAX_API_KEY` 环境变量 | `mmx auth login` |
| **安装** | 无需额外安装 | `npm install -g mmx-cli` |
| **输入格式** | 标准消息数组 | `--message` / `--messages-file` / stdin |
| **输出格式** | JSON / SSE 流 | stdout / `--output json` |
| **流式支持** | SSE 流式 | `--stream` |
| **Skills 支持** | 无 | 集成 [MiniMax Skills](https://github.com/MiniMax-AI/skills) |

**MiniMax API 详情**:

**OpenAI 兼容格式**（推荐）：
- Endpoint: `https://api.minimaxi.com/v1`
- 认证: `MINIMAX_API_KEY` → 设为 `OPENAI_API_KEY`
- 模型: MiniMax-M2.7, M2.7-highspeed, M2.5, M2.5-highspeed, M2.1, M2.1-highspeed, M2
- 上下文窗口: 204,800 tokens
- 限制: temperature (0.0, 1.0]，n=1，暂不支持图像/音频

**Anthropic 兼容格式**：
- Endpoint: `https://api.minimaxi.com/anthropic`
- 认证: `MINIMAX_API_KEY` → 设为 `ANTHROPIC_API_KEY`
- 同上模型列表

**MiniMax CLI 模式**：
- 安装: `npm install -g mmx-cli`
- 认证: `mmx auth login --api-key sk-xxxxx`
- 文本聊天: `mmx text chat --message "xxx" --stream`
- 多轮对话: `mmx text chat --message "user:你好" --message "assistant:嗨" --message "user:..."`
- JSON 输入: `cat messages.json | mmx text chat --messages-file -`
- JSON 输出: `mmx text chat --message "xxx" --output json`
- Skills: `npx skills add MiniMax-AI/cli -y -g`

#### Codebuddy（新增）

> **关键差异**: Codebuddy 没有 Skills 系统，需要通过使用文档自动生成技能描述和方法。同时 Codebuddy 提供 CLI 和 SDK 两种集成方式。

| 维度 | CLI 模式 | SDK 模式 |
|------|---------|---------|
| **调用方式** | `codebuddy -p "query"` 非交互式 | Python `codebuddy-agent-sdk` |
| **认证** | `codebuddy` 交互登录 / `CODEBUDDY_API_KEY` | 复用 CLI 登录凭证 / `CODEBUDDY_API_KEY` |
| **安装** | `npm install -g @anthropic-ai/codebuddy` | `pip install codebuddy-agent-sdk` |
| **Prompt 注入** | `--system-prompt` / `--append-system-prompt` / `--system-prompt-file` | `query(prompt=..., options={...})` |
| **输出格式** | `--output-format text/json/stream-json` | 异步迭代器，消息类型化 |
| **会话延续** | `-c` 继续 / `-r <session-id>` 恢复 | `unstable_v2_createSession()` 多轮对话 |
| **权限控制** | `-y` 跳过权限确认 | `canUseTool` 回调 / `permissionMode` |
| **Skills 支持** | **无** — 需独立开发技能模块 | **无** — 需独立开发技能模块 |
| **后台任务** | `--bg --name <name>` | — |

**Codebuddy CLI 命令参考**:

```bash
# 非交互式查询（核心模式）
codebuddy -p "解释这个函数"                        # 单次查询，输出到 stdout
codebuddy -p "分析项目" --output-format json       # JSON 结构化输出
codebuddy -p "审查代码" --output-format stream-json # 流式 JSON

# Prompt 注入
codebuddy -p --system-prompt "你是 Python 专家" "审查代码"       # 替换系统提示
codebuddy -p --append-system-prompt "请用 TypeScript" "重构代码" # 追加系统提示
codebuddy -p --system-prompt-file ./prompt.txt "执行任务"        # 文件加载提示

# 管道输入
cat logs.txt | codebuddy -p "分析日志"             # 管道传入内容

# 会话管理
codebuddy -c                                      # 继续最近对话
codebuddy -c -p "检查类型错误"                     # 继续对话并查询
codebuddy -r "abc123" "完成 MR"                   # 恢复指定会话

# 权限
codebuddy -p -y "修复代码错误"                     # 跳过权限确认（危险）

# 后台任务
codebuddy --bg --name my-task "实现登录功能"        # 后台运行
codebuddy logs my-task                             # 查看输出
codebuddy attach my-task                           # 附加到任务
```

**Codebuddy SDK (Python) 参考**:

```python
import asyncio
from codebuddy_agent_sdk import query, CodeBuddyAgentOptions
from codebuddy_agent_sdk import AssistantMessage, TextBlock

async def main():
    options = CodeBuddyAgentOptions(
        permission_mode="bypassPermissions",
        cwd="/path/to/project",
        max_turns=10
    )

    async for message in query(prompt="请解释什么是递归函数", options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)

asyncio.run(main())
```

### CLI 任务派发协议

> **核心问题**: 不同 CLI 工具（mmx / codebuddy / 其他）的命令格式、输入输出、会话管理各不相同。需要统一的派发协议来屏蔽差异。

```
┌─────────────────────────────────────────────────────────┐
│                  CLI 任务派发协议                          │
│                                                          │
│  ADDS Agent Loop                                        │
│      │                                                   │
│      ▼                                                   │
│  TaskDispatcher                                         │
│      │                                                   │
│      ├── 构建任务 Prompt                                  │
│      │   ├─ system_prompt_file → /tmp/adds-task-prompt   │
│      │   ├─ context → stdin 管道 或 --messages-file      │
│      │   └─ 指令 → 位置参数                               │
│      │                                                   │
│      ├── 选择派发方式（CLIProfile 定义）                   │
│      │   ├─ exec_command: 完整命令模板                     │
│      │   ├─ input_method: stdin | arg | file             │
│      │   ├─ output_format: text | json | stream-json     │
│      │   └─ session_resume: -c | -r | 无                 │
│      │                                                   │
│      ├── 执行并捕获输出                                   │
│      │   ├─ subprocess.run() 或 asyncio.create_subprocess│
│      │   ├─ 实时流式捕获 stdout                           │
│      │   └─ 解析输出格式（text 直接用 / json 结构化解析）  │
│      │                                                   │
│      └── 结果标准化 → ModelResponse                      │
│          ├─ content: 文本内容                             │
│          ├─ usage: token 估算                             │
│          └─ finish_reason: stop / error                  │
└─────────────────────────────────────────────────────────┘
```

**CLIProfile — CLI 工具配置描述**:

```python
@dataclass
class CLIProfile:
    """CLI 工具配置文件 — 描述如何与特定 CLI 交互"""
    name: str                    # 工具名称，如 "codebuddy"
    command: str                 # 主命令，如 "codebuddy"
    version_command: str         # 版本检查，如 "codebuddy --version"
    
    # 任务派发配置
    dispatch: dict = field(default_factory=lambda: {
        "exec_template": "{command} -p {prompt} --output-format {output_format}",
        "input_method": "arg",         # stdin | arg | file
        "output_format": "json",       # text | json | stream-json
        "stream_supported": True,
        "system_prompt_method": "flag", # flag | stdin | env
        "system_prompt_flag": "--system-prompt-file",
    })
    
    # 会话管理配置
    session: dict = field(default_factory=lambda: {
        "resume_flag": "-c",           # 继续会话的标志
        "session_id_flag": "-r",       # 恢复指定会话的标志
        "session_id_source": "stdout", # session_id 从哪里获取
    })
    
    # 权限配置
    permission: dict = field(default_factory=lambda: {
        "bypass_flag": "-y",           # 跳过权限确认的标志
    })
    
    # 技能生成（无 Skills 的 CLI 需要）
    skill_generation: dict = field(default_factory=lambda: {
        "enabled": False,
        "docs_source": "",             # 使用文档 URL 或本地路径
        "output_path": "",             # 生成的技能文件存放路径
    })
    
    # 健康检查与长时任务配置（第三轮新增）
    health_check: dict = field(default_factory=lambda: {
        "timeout": 300,              # 默认超时（秒）
        "timeout_long_task": 3600,   # 长时任务超时（秒）
        "health_check_interval": 30, # 健康检查间隔（秒）
        "max_retries": 2,            # 超时最大重试次数
        "zombie_check": True,        # 是否检查僵尸进程
        "long_task_flags": ["--bg"], # 标记为长时任务的 CLI 参数
        "stall_threshold": 60,       # 无输出超过此秒数视为 stall（卡死）
    })
```

**各 Provider 的 CLIProfile 实例**:

```python
# MiniMax CLI
MINIMAX_CLI_PROFILE = CLIProfile(
    name="minimax",
    command="mmx",
    version_command="mmx --version",
    dispatch={
        "exec_template": "{command} text chat --message {prompt} --output {output_format}",
        "input_method": "arg",
        "output_format": "json",
        "stream_supported": True,
        "system_prompt_method": "flag",
        "system_prompt_flag": "--system-prompt",
    },
    session={
        "resume_flag": None,            # mmx 无会话延续
        "session_id_flag": None,
        "session_id_source": None,
    },
    permission={"bypass_flag": None},
    skill_generation={"enabled": True, "docs_source": "https://github.com/MiniMax-AI/cli"},
)

# Codebuddy CLI
CODEBUDDY_CLI_PROFILE = CLIProfile(
    name="codebuddy",
    command="codebuddy",
    version_command="codebuddy --version",
    dispatch={
        "exec_template": "{command} -p {prompt} --output-format {output_format}",
        "input_method": "arg",
        "output_format": "json",
        "stream_supported": True,
        "system_prompt_method": "file",
        "system_prompt_flag": "--system-prompt-file",
    },
    session={
        "resume_flag": "-c",
        "session_id_flag": "-r",
        "session_id_source": "json_output",  # 从 JSON 输出中提取 session_id
    },
    permission={"bypass_flag": "-y"},
    skill_generation={
        "enabled": True,
        "docs_source": "https://www.codebuddy.ai/docs/cli/cli-reference",
    },
)

# Codebuddy SDK — 不同于 CLI，直接编程调用
CODEBUDDY_SDK_PROFILE = CLIProfile(
    name="codebuddy-sdk",
    command="codebuddy-agent-sdk",  # Python 包名，非命令
    version_command="pip show codebuddy-agent-sdk",
    dispatch={
        "exec_template": None,  # SDK 模式不走 subprocess
        "input_method": "sdk",
        "output_format": "stream-json",
        "stream_supported": True,
        "system_prompt_method": "api",
        "system_prompt_flag": None,
    },
    session={
        "resume_flag": None,
        "session_id_flag": None,
        "session_id_source": "sdk_session",
    },
    permission={"bypass_flag": None},  # 通过 options.permission_mode 控制
    skill_generation={
        "enabled": True,
        "docs_source": "https://www.codebuddy.ai/docs/cli/sdk",
    },
)
```

### Codebuddy 技能生成模块

> **问题**: Codebuddy 没有 Skills 系统，需要独立开发技能模块。方案：从 Codebuddy 使用文档自动生成技能描述。

```python
class SkillGenerator:
    """从 CLI 使用文档自动生成技能描述"""
    
    async def generate_from_docs(self, profile: CLIProfile) -> list[dict]:
        """从文档生成技能列表
        
        流程:
        1. 抓取/读取 CLI 使用文档
        2. 调用 LLM 分析文档，提取:
           - 功能列表（每个功能 = 一个技能）
           - 触发条件（何时使用该技能）
           - 命令模板（如何调用）
           - 输入输出格式
        3. 生成技能描述文件（Markdown）
        4. 存入 .ai/memories/SKILLS/<provider>/
        """
        docs = await self._fetch_docs(profile.skill_generation["docs_source"])
        skills = await self._llm_extract_skills(docs, profile.name)
        await self._save_skills(skills, profile.name)
        return skills
    
    async def _llm_extract_skills(self, docs: str, provider: str) -> list[dict]:
        """LLM 从文档中提取技能
        
        提示词:
        "分析以下 CLI 工具的使用文档，提取出所有可用的功能/技能。
        每个技能需包含:
        - name: 技能名称
        - trigger: 触发条件（什么时候该用这个技能）
        - command_template: 命令模板（含占位符）
        - input_format: 输入格式说明
        - output_format: 输出格式说明
        - examples: 使用示例"
        """
        pass
```

**生成的 Codebuddy 技能示例**:

```markdown
# .ai/memories/SKILLS/codebuddy/code-analysis.md

## Skill: code-analysis
- **Provider**: codebuddy
- **Trigger**: 当需要分析代码结构、查找 bug、代码审查时
- **Command**: `codebuddy -p "{query}" --output-format json`
- **System Prompt**: `--append-system-prompt "请重点关注代码质量和潜在 bug"`
- **Input**: 自然语言查询
- **Output**: JSON 格式，包含 analysis 文本
- **Examples**:
  - `codebuddy -p "分析这个项目的架构" --output-format json`
  - `cat main.py | codebuddy -p "审查这段代码的安全问题" --output-format json`
```

### 架构设计

```
scripts/model/
├── __init__.py
├── base.py            # ModelInterface 抽象基类
├── factory.py         # 工厂：启动时选择 API/CLI/SDK + Provider
├── api_adapter.py     # API 调用适配器（基于 openai 库）
├── cli_adapter.py     # CLI 工具适配器（基于 subprocess + CLIProfile）
├── sdk_adapter.py     # SDK 适配器（基于 codebuddy-agent-sdk）
├── task_dispatcher.py # CLI 任务派发器（统一协议）
├── skill_generator.py # 技能自动生成器（从文档提取技能）
└── providers/
    ├── __init__.py
    ├── minimax.py     # MiniMax Provider 配置
    ├── codebuddy.py   # Codebuddy Provider 配置（CLI + SDK）
    └── registry.py    # Provider 注册表（可扩展）
```

### 核心接口设计

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
from dataclasses import dataclass, field

@dataclass
class ModelResponse:
    """统一模型响应"""
    content: str
    model: str
    usage: dict  # {"input_tokens": int, "output_tokens": int}
    tool_calls: Optional[list] = None
    finish_reason: str = "stop"
    progress_hints: Optional[list[dict]] = None  # 粗粒度进度提示（第三轮新增）
    # progress_hints 示例:
    # [{"phase": "compiling", "progress": 30, "detail": "Building contracts..."},
    #  {"phase": "testing", "progress": 80, "detail": "Running test suite..."}]

class ModelInterface(ABC):
    """模型调用抽象基类"""
    
    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        stream: bool = True,
        **kwargs
    ) -> AsyncIterator[ModelResponse]:
        """流式聊天接口"""
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Token 计数（近似估算）"""
        pass
    
    @abstractmethod
    def get_context_window(self) -> int:
        """返回模型上下文窗口大小"""
        pass
    
    @abstractmethod
    def supports_feature(self, name: str) -> bool:
        """查询模型支持的功能"""
        pass

class APIAdapter(ModelInterface):
    """API 调用适配器 — 基于 openai 库"""
    def __init__(self, provider_config: dict):
        self.base_url = provider_config["base_url"]
        self.api_key = provider_config["api_key"]
        self.model = provider_config["model"]
        self.context_window = provider_config.get("context_window", 204800)
        # from openai import AsyncOpenAI
        # self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)
    pass

class CLIAdapter(ModelInterface):
    """CLI 工具适配器 — 基于 subprocess + CLIProfile"""
    def __init__(self, cli_config: dict):
        self.profile = cli_config["profile"]  # CLIProfile 实例
        self.model = cli_config.get("model")
        self.context_window = cli_config.get("context_window", 204800)
        self.dispatcher = TaskDispatcher(self.profile)
    pass

class SDKAdapter(ModelInterface):
    """SDK 适配器 — 直接编程调用（如 codebuddy-agent-sdk）"""
    def __init__(self, sdk_config: dict):
        self.package = sdk_config["package"]  # e.g. "codebuddy-agent-sdk"
        self.model = sdk_config.get("model")
        self.context_window = sdk_config.get("context_window", 204800)
    pass

class TaskDispatcher:
    """CLI 任务派发器 — 统一协议"""
    
    def __init__(self, profile: CLIProfile):
        self.profile = profile
    
    async def dispatch(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        output_format: str = "json",
        resume_session: Optional[str] = None,
        bypass_permissions: bool = False,
    ) -> ModelResponse:
        """派发任务到 CLI 工具
        
        1. 根据 CLIProfile 构建完整命令
        2. 处理 system_prompt 注入方式
        3. 处理会话延续
        4. 执行并捕获输出
        5. 解析输出格式，标准化为 ModelResponse
        """
        # 构建 system_prompt 文件（如果需要）
        if system_prompt and self.profile.dispatch["system_prompt_method"] == "file":
            sp_file = await self._write_system_prompt_file(system_prompt)
            system_prompt = sp_file
        
        # 构建完整命令
        cmd = self._build_command(
            prompt=prompt,
            system_prompt=system_prompt,
            output_format=output_format,
            resume_session=resume_session,
            bypass_permissions=bypass_permissions,
        )
        
        # 执行
        result = await self._execute(cmd)
        
        # 解析输出
        return self._parse_output(result, output_format)
    
    def _build_command(self, **kwargs) -> list[str]:
        """根据 CLIProfile.exec_template 构建命令"""
        pass
    
    async def _execute(self, cmd: list[str]) -> str:
        """执行命令，实时流式捕获 stdout
        
        长时任务处理策略（第三轮新增）:
        1. 区分 stall（卡死）和 slow（慢但活跃）:
           - stall: 进程无输出超过 stall_threshold 秒 → kill + retry
           - slow: 有输出但未完成 → 继续等待 + 报告进度
        2. 重试前检查幂等性:
           - 读操作（ls, cat, grep, test, check）→ 可直接重试
           - 写操作（commit, push, install, write）→ 需用户确认重试
        3. 后台任务（--bg）:
           - 利用 `codebuddy logs <name>` 和 `codebuddy attach <name>` 轮询状态
           - 不直接检查 PID（进程已 detach）
        4. progress_hints 实时更新:
           - 从 stdout 解析进度信息（百分比、计数等）
           - 粗粒度报告，不记录每行输出
        """
        import asyncio
        
        hc = self.profile.health_check
        is_long_task = any(flag in " ".join(cmd) for flag in hc.get("long_task_flags", []))
        timeout = hc.get("timeout_long_task", 3600) if is_long_task else hc.get("timeout", 300)
        stall_threshold = hc.get("stall_threshold", 60)
        max_retries = hc.get("max_retries", 2)
        
        for attempt in range(max_retries + 1):
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                
                output_lines = []
                last_output_time = asyncio.get_event_loop().time()
                
                async def _read_stream(stream):
                    nonlocal last_output_time
                    async for line in stream:
                        last_output_time = asyncio.get_event_loop().time()
                        output_lines.append(line.decode())
                        # TODO: 解析 progress_hints 从输出中
                
                # 并发读取 stdout 和 stderr
                await asyncio.gather(
                    _read_stream(proc.stdout),
                    _read_stream(proc.stderr),
                )
                
                await proc.wait()
                
                if proc.returncode != 0:
                    stderr = "".join(output_lines)
                    if attempt < max_retries and self._is_idempotent(cmd):
                        continue  # 幂等操作可重试
                    # 非幂等或最后一次重试，返回错误
                    return f"Exit Code: {proc.returncode}\n{stderr}"
                
                return "".join(output_lines)
                
            except asyncio.TimeoutError:
                if attempt < max_retries and self._is_idempotent(cmd):
                    continue
                return f"Timeout after {timeout}s (attempt {attempt + 1})"
        
        return f"Max retries ({max_retries}) exceeded"
    
    def _is_idempotent(self, cmd: list[str]) -> bool:
        """检查命令是否为幂等操作
        
        幂等操作（可直接重试）: ls, cat, grep, test, check, status, diff, log
        非幂等操作（需用户确认）: commit, push, install, write, rm, create
        """
        idempotent_prefixes = ("ls", "cat", "grep", "rg", "test", "check", 
                               "status", "diff", "log", "head", "tail", "find")
        command_str = " ".join(cmd)
        return any(command_str.startswith(p) for p in idempotent_prefixes)
    
    def _parse_output(self, raw: str, output_format: str) -> ModelResponse:
        """解析输出格式，标准化为 ModelResponse"""
        pass

class ModelFactory:
    """模型工厂 — 启动时交互式选择"""
    
    PROVIDERS = {
        "minimax": {
            "name": "MiniMax",
            "api": {
                "base_url": "https://api.minimaxi.com/v1",
                "api_key_env": "MINIMAX_API_KEY",
                "models": ["MiniMax-M2.7", "MiniMax-M2.7-highspeed", 
                           "MiniMax-M2.5", "MiniMax-M2.5-highspeed",
                           "MiniMax-M2.1", "MiniMax-M2.1-highspeed", "MiniMax-M2"],
                "context_window": 204800
            },
            "cli": {
                "command": "mmx",
                "install_hint": "npm install -g mmx-cli",
                "auth_command": "mmx auth login --api-key $MINIMAX_API_KEY",
                "models": ["MiniMax-M2.7", "MiniMax-M2.5", "MiniMax-M2.1", "MiniMax-M2"],
                "context_window": 204800,
                "profile": MINIMAX_CLI_PROFILE,
            }
        },
        "codebuddy": {
            "name": "Codebuddy",
            "cli": {
                "command": "codebuddy",
                "install_hint": "npm install -g @anthropic-ai/codebuddy",
                "auth_command": "codebuddy",  # 交互式登录
                "api_key_env": "CODEBUDDY_API_KEY",
                "models": ["default"],  # Codebuddy 自带模型选择
                "context_window": 200000,
                "profile": CODEBUDDY_CLI_PROFILE,
            },
            "sdk": {
                "package": "codebuddy-agent-sdk",
                "install_hint": "pip install codebuddy-agent-sdk",
                "auth_command": None,  # 复用 CLI 登录凭证
                "api_key_env": "CODEBUDDY_API_KEY",
                "models": ["default"],
                "context_window": 200000,
                "profile": CODEBUDDY_SDK_PROFILE,
            }
        },
        # 可扩展: openai, anthropic, deepseek, etc.
    }
    
    def select_model(self) -> ModelInterface:
        """交互式选择模型
        
        流程:
        1. 检测可用模式（API key 存在? CLI 工具已安装? SDK 已安装?）
        2. 列出可用选项让用户选择
        3. 如果有多个模型，让用户选择模型
        4. 返回对应的 Adapter 实例
        5. 首次使用某个 CLI Provider 时，触发技能生成
        """
        available_modes = []
        
        for provider_id, provider in self.PROVIDERS.items():
            # 检测 API 可用性
            if "api" in provider:
                api_key = os.environ.get(provider["api"]["api_key_env"])
                if api_key:
                    available_modes.append({
                        "mode": "api",
                        "provider": provider_id,
                        "label": f"{provider['name']} (API)",
                        "models": provider["api"]["models"]
                    })
            
            # 检测 CLI 可用性
            if "cli" in provider:
                if shutil.which(provider["cli"]["command"]):
                    available_modes.append({
                        "mode": "cli",
                        "provider": provider_id,
                        "label": f"{provider['name']} (CLI: {provider['cli']['command']})",
                        "models": provider["cli"]["models"]
                    })
            
            # 检测 SDK 可用性
            if "sdk" in provider:
                if self._check_sdk_installed(provider["sdk"]["package"]):
                    available_modes.append({
                        "mode": "sdk",
                        "provider": provider_id,
                        "label": f"{provider['name']} (SDK: {provider['sdk']['package']})",
                        "models": provider["sdk"]["models"]
                    })
        
        if not available_modes:
            print("❌ 未检测到可用的模型。请配置 API Key 或安装 CLI 工具。")
            sys.exit(1)
        
        # 交互式选择
        print("\n🤖 请选择大模型调用方式：")
        for i, mode in enumerate(available_modes, 1):
            print(f"  {i}. {mode['label']}")
        
        choice = int(input("\n请输入编号: ")) - 1
        selected = available_modes[choice]
        
        # 选择具体模型
        if len(selected["models"]) > 1:
            print(f"\n📋 可用模型：")
            for i, model in enumerate(selected["models"], 1):
                print(f"  {i}. {model}")
            model_choice = int(input("\n请输入编号: ")) - 1
            model_name = selected["models"][model_choice]
        else:
            model_name = selected["models"][0]
        
        # 创建适配器
        provider = self.PROVIDERS[selected["provider"]]
        adapter = self._create_adapter(selected, provider, model_name)
        
        # 首次使用 CLI/SDK Provider 时，检查/生成技能
        if selected["mode"] in ("cli", "sdk"):
            profile = provider[selected["mode"]]["profile"]
            if profile.skill_generation.get("enabled"):
                await self._ensure_skills_generated(profile)
        
        return adapter
    
    def _check_sdk_installed(self, package: str) -> bool:
        """检查 SDK 包是否已安装"""
        try:
            importlib.import_module(package.replace("-", "_"))
            return True
        except ImportError:
            return False
    
    async def _ensure_skills_generated(self, profile: CLIProfile):
        """确保技能已从文档生成"""
        skill_path = Path(f".ai/memories/SKILLS/{profile.name}")
        if not skill_path.exists() or not list(skill_path.glob("*.md")):
            print(f"\n📖 首次使用 {profile.name}，正在从文档生成技能描述...")
            generator = SkillGenerator()
            await generator.generate_from_docs(profile)
            print(f"✅ 技能生成完成，存入 .ai/memories/SKILLS/{profile.name}/")
```

### 启动交互示例

```
$ python3 scripts/adds.py start

🤖 请选择大模型调用方式：
  1. MiniMax (API)              ← 检测到 MINIMAX_API_KEY
  2. MiniMax (CLI: mmx)         ← 检测到 mmx 已安装
  3. Codebuddy (CLI: codebuddy) ← 检测到 codebuddy 已安装
  4. Codebuddy (SDK)            ← 检测到 codebuddy-agent-sdk

请输入编号: 3

📖 首次使用 codebuddy，正在从文档生成技能描述...
✅ 技能生成完成，存入 .ai/memories/SKILLS/codebuddy/

✅ 已选择: Codebuddy (CLI: codebuddy)
✅ 上下文窗口: 200,000 tokens
```

### 实现文件变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `scripts/model/__init__.py` | 新建 | 模块入口 |
| `scripts/model/base.py` | 新建 | ModelInterface 抽象基类 |
| `scripts/model/factory.py` | 新建 | 交互式模型工厂 |
| `scripts/model/api_adapter.py` | 新建 | API 调用适配器 |
| `scripts/model/cli_adapter.py` | 新建 | CLI 工具适配器（基于 CLIProfile） |
| `scripts/model/sdk_adapter.py` | 新建 | SDK 适配器（基于 codebuddy-agent-sdk） |
| `scripts/model/task_dispatcher.py` | 新建 | CLI 任务派发器（统一协议） |
| `scripts/model/skill_generator.py` | 新建 | 技能自动生成器（从文档提取） |
| `scripts/model/providers/minimax.py` | 新建 | MiniMax Provider 配置 |
| `scripts/model/providers/codebuddy.py` | 新建 | Codebuddy Provider 配置（CLI+SDK） |
| `scripts/model/providers/registry.py` | 新建 | Provider 注册表 |
| `scripts/agent_loop.py` | 修改 | 接入 ModelInterface |
| `scripts/adds.py` | 修改 | start 命令集成模型选择 |
| `requirements.txt` | 新增 | 添加 openai, codebuddy-agent-sdk 依赖 |

---

## 三、P0-2: 上下文压缩策略（两层）

### 设计目标

实现**任务级上下文压缩**，确保当前 session 的上下文空间始终最优，同时通过链式结构实现可回溯的无限上下文。

### 核心设计思想

```
压缩 ≠ 丢弃细节
压缩 = 将细节移出当前上下文 + 保留回溯线索 + 结构化摘要留在链上

当前 session 只保留：
  1. System Prompt
  2. 上一 session 的结构化摘要 + 链式指针
  3. 固定记忆（升级后的精华）
  4. 当前任务的消息（精简后）

历史详情不丢弃，存在 .mem 文件中，可按需回溯
```

### 文件体系设计

```
.ai/sessions/
├── 20260409-153000.ses       # Session 文件（当前任务的对话记录）
├── 20260409-153000-ses1.log  # 工具输出 log（序号关联 session）
├── 20260409-153000-ses2.log  # 同一 session 的第 2 个 log
├── 20260409-160000.ses       # 下一 session
├── 20260409-160000-ses1.log
│
├── 20260409-153000.mem       # 记忆文件（高密度 Markdown 归档）
├── 20260409-160000.mem       # 含完整详情 + 结构化摘要 + 链式指针
│
└── index.mem                 # 记忆索引（线索目录，始终注入上下文）
```

### 摘要策略决策框架

> **核心问题**: 摘要生成有两种路径 — 工具过滤（快速无 LLM）和 LLM 分析（精准有成本）。决策依据：**摘要与结论的重要性**。

```python
from enum import Enum

class SummaryStrategy(Enum):
    """摘要策略"""
    KEEP_FULL = "keep_full"        # 完全保留：错误信号触发，不做任何压缩
    TOOL_FILTER = "tool_filter"    # 工具过滤：无需 LLM，快速
    LLM_ANALYZE = "llm_analyze"    # LLM 分析：需要 LLM，精准
    HYBRID = "hybrid"              # 混合：工具过滤 + LLM 精炼

class SummaryDecisionEngine:
    """摘要决策引擎 — 决定使用哪种摘要策略"""
    
    def decide(self, message: dict, context: dict) -> SummaryStrategy:
        """决策逻辑:
        
        0. 错误保留原则（最高优先级）:
           → KEEP_FULL: 检测到错误信号时完全保留，不做任何压缩
           → 错误信号: Exit Code != 0, Error/Exception/Traceback/FAIL/CRITICAL/WARNING
           → 包含错误信号的 stdout/stderr 都不压缩
           → 错误输出 ±3 行上下文也保留
        
        1. 结构化输出（测试结果、文件内容、命令输出）
           → TOOL_FILTER: 正则/规则提取关键指标
           → 示例: pytest 输出 → 提取 passed/failed/warnings
        
        2. 非结构化对话（需求讨论、架构决策、代码审查意见）
           → LLM_ANALYZE: 需要理解语义，提取关键决策和结论
           → 示例: "我觉得应该用 JWT 而不是 session" → 提取决策
        
        3. 混合内容（带结论的工具输出 + 人类讨论）
           → HYBRID: 先 TOOL_FILTER 提取结构化信息，再 LLM 精炼
        
        判断依据:
        - 错误信号存在 → KEEP_FULL（最高优先级）
        - 摘要与结论的重要性高 → 倾向 LLM_ANALYZE
        - 消息类型为 tool_result → 倾向 TOOL_FILTER
        - 上下文利用率高 → 倾向 TOOL_FILTER（省 token）
        """
        msg_type = message.get("role")
        content = message.get("content", "")
        
        # 规则 0（最高优先级）: 错误信号 → KEEP_FULL
        if msg_type == "tool_result" and self._has_error_signals(content):
            return SummaryStrategy.KEEP_FULL
        
        # 规则 1: 工具输出 → TOOL_FILTER
        if msg_type == "tool_result":
            return SummaryStrategy.TOOL_FILTER
        
        # 规则 2: 长对话讨论 → LLM_ANALYZE
        if msg_type == "assistant" and len(content) > 500:
            return SummaryStrategy.LLM_ANALYZE
        
        # 规则 3: 包含决策关键词 → LLM_ANALYZE
        decision_keywords = ["决定", "结论", "选择", "方案", "decided", "conclusion"]
        if any(kw in content.lower() for kw in decision_keywords):
            return SummaryStrategy.LLM_ANALYZE
        
        # 默认: TOOL_FILTER
        return SummaryStrategy.TOOL_FILTER
    
    def _has_error_signals(self, content: str) -> bool:
        """检测内容是否包含错误信号
        
        检测规则:
        1. Exit Code != 0
        2. 标准错误关键词: Error, Exception, Traceback, FAILED, CRITICAL, WARNING
        3. 大小写不敏感匹配（stdout 中也可能有错误）
        4. 匹配到错误信号的行 ±3 行上下文都保留
        """
        import re
        error_signals = [
            r'exit\s+code\s+[1-9]',                          # Exit Code != 0
            r'(Error|Exception|Traceback|FAILED?|CRITICAL)',  # 大写变体
            r'(error|exception|traceback|failed?|critical)',  # 小写变体
            r'WARNING',                                       # 警告信号
        ]
        return any(re.search(p, content, re.IGNORECASE) for p in error_signals)
```

**Layer 1 和 Layer 2 的摘要策略分布**:

| 层级 | 策略 | 说明 |
|------|------|------|
| Layer 1 | KEEP_FULL 最高优先级 | 错误信号触发时完全保留，不做任何压缩 |
| Layer 1 | TOOL_FILTER 为主 | 实时压缩，不能等 LLM 响应。仅用规则过滤 |
| Layer 1 | LLM_ANALYZE 补充 | 仅当决策关键词触发，且上下文有空余时 |
| Layer 2 | LLM_ANALYZE 为主 | 归档压缩，需要精准提取关键信息 |
| Layer 2 | TOOL_FILTER 辅助 | 结构化输出部分先用工具提取，减少 LLM token 消耗 |

### Layer 1: 任务内压缩（实时，无需 API 调用）

**触发条件**: 工具输出超过阈值（默认 2000 字符，可配置）

**操作**:

```
任务执行中的消息流:
┌──────────────────────────────────────────────────────┐
│ [user] 实现 xxx 功能                                  │
│ [assistant] 我来分析需求...                            │
│ [tool_call] bash("pytest tests/")                     │
│ [tool_result] ← 超过 2000 字符！触发 Layer 1          │
│     ↓                                                 │
│     摘要决策: TOOL_FILTER（结构化输出）                  │
│     1. 将完整输出保存到 20260409-153000-ses1.log      │
│     2. Session 中替换为：                              │
│        [tool_result] 测试完成。详见 ses1.log           │
│        摘要: 12 passed, 0 failed, 2 warnings          │
│ [assistant] 测试通过，继续...                          │
│ [tool_call] bash("cat src/main.py")                   │
│ [tool_result] ← 又超阈值                              │
│     ↓                                                 │
│     摘要决策: TOOL_FILTER（文件内容）                    │
│     1. 保存到 20260409-153000-ses2.log                │
│     2. Session 中替换为占位符 + 摘要                   │
│ ...                                                   │
│ [assistant] 任务完成。结论：xxx                         │
│     ↓                                                 │
│     摘要决策: LLM_ANALYZE（含结论的重要消息）            │
│     → 标记此消息为"高价值"，Layer 2 归档时重点提取      │
└──────────────────────────────────────────────────────┘
```

**Layer 1 的 .ses 文件格式**:

```markdown
# Session: 20260409-153000
# Agent: developer
# Feature: user_authentication
# Created: 2026-04-09 15:30:00
# Status: active

## Messages

### [user] 实现 xxx 功能

### [assistant] 我来分析需求...

### [tool_call] bash("pytest tests/")

### [tool_result]
测试完成。详见 `20260409-153000-ses1.log`
摘要: 12 passed, 0 failed, 2 warnings
<!-- strategy: tool_filter -->

### [assistant] 测试通过，继续...

### [tool_call] bash("cat src/main.py")

### [tool_result]
文件内容。详见 `20260409-153000-ses2.log`
摘要: main.py 共 150 行，包含 Auth 类和路由定义
<!-- strategy: tool_filter -->
<!-- file_ref: src/main.py | md5=abc123 | lines=150 | modified=2026-04-09T15:35:00 -->

### [assistant] 任务完成。结论：用户认证功能已实现
<!-- strategy: llm_analyze | priority: high -->
```

**Layer 1 额外清理规则**:

| 操作 | 说明 | 策略 |
|------|------|------|
| **错误保留（最高优先级）** | **包含错误信号的工具输出完全保留，不做任何压缩** | **KEEP_FULL** |
| **错误上下文保留** | **错误信号行 ±3 行上下文也保留** | **KEEP_FULL** |
| 清除已完成任务输出 | 仅保留任务说明与结论，删除中间过程 | TOOL_FILTER |
| 保存过长工具结果 | > 阈值 → log 文件，session 留占位符 + 摘要 | TOOL_FILTER |
| 文件内容快照引用 | 对 cat 结果记录 file_ref（md5 + 修改时间 + 行数） | TOOL_FILTER |
| 删除重复消息 | 折叠连续相同/确认性消息 | TOOL_FILTER |
| 删除冗余确认 | "好的"、"我理解了" 等无实质内容消息 | TOOL_FILTER |
| 标记高价值消息 | 含决策/结论的消息标记 priority: high | LLM_ANALYZE |

### Layer 2: 会话归档压缩（触发时调用 LLM）

**触发条件**: 上下文超过 80% 窗口

**操作流程**:

```
Step 1: 合并 Layer 1 的 session + log → 完整记录
  20260409-153000.ses + ses1.log + ses2.log
  → 将 log 占位符替换为实际内容（markdown 引入语法）

Step 2: 摘要决策 — 分区域选择策略
  对完整记录中的每条消息：
  - TOOL_FILTER 标记的 → 用规则提取（省 token）
  - LLM_ANALYZE 标记的 → 送 LLM 分析（精准）
  - 优先提取 priority: high 的消息

Step 3: 调用 LLM 对高价值部分生成结构化摘要
  - 保留：关键决策、代码变更、测试结果、错误与修复
  - 保留：任务结论和未完成事项
  - 保留：经验教训（用于记忆进化评估）
  - 格式：高密度 Markdown

Step 4: 生成 .mem 文件（记忆归档）
  内容 = 完整记录（含 log） + 结构化摘要 + 链式指针
  20260409-153000.mem
  ⚠️ 完整记录区是 APPEND-ONLY，写入后不可修改

Step 5: 回写 .ses 文件为摘要版
  保留结构化摘要 + 指向前一个 session 的指针
  20260409-153000.ses → 覆写为摘要版

Step 6: 检查是否需要升级固定记忆
  如果摘要中有高价值经验 → 升级为固定记忆
```

**.mem 文件格式（高密度 Markdown）**:

```markdown
# Memory: 20260409-153000
# Agent: developer | Feature: user_authentication
# Created: 2026-04-09 15:30:00
# Archived: 2026-04-09 16:00:00
# Prev: 20260409-143000.mem    ← 链式指针（前一个 session）
# Next: (待写入)               ← 链式指针（后一个 session）

---

## 结构化摘要（由 LLM 生成）

### 关键决策
- 使用 JWT 进行用户认证
- 密码使用 bcrypt 哈希存储
- Token 有效期设为 24 小时

### 代码变更
- 新增: src/auth/jwt_handler.py (JWT 生成/验证)
- 新增: src/auth/password.py (bcrypt 哈希)
- 修改: src/routes/user.py (添加 /login, /logout 端点)
- 修改: src/middleware/auth.py (添加 JWT 验证中间件)

### 测试结果
- 单元测试: 12 passed, 0 failed
- 集成测试: 3 passed (登录/登出/Token刷新)
- 覆盖率: 87%

### 错误与修复
- JWT 过期时返回 500 → 修复为返回 401
- bcrypt 需安装额外依赖 → 已添加到 requirements.txt

### 未完成事项
- Token 刷新端点尚未实现
- 需要 Reviewer 审查安全漏洞

### 经验教训
- JWT 库 PyJWT 2.x API 与 1.x 不兼容，需注意版本

---

## 完整记录（含工具输出详情）

### [user] 实现用户认证功能

### [assistant] 我来分析需求...

### [tool_call] bash("pytest tests/")

### [tool_result]
12 passed, 0 failed, 2 warnings in 3.2s
tests/test_auth.py::test_jwt_generation PASSED
tests/test_auth.py::test_jwt_validation PASSED
tests/test_auth.py::test_password_hashing PASSED
...（完整输出）

### [tool_call] bash("cat src/main.py")

### [tool_result]
```python
from auth.jwt_handler import JWTHandler
from auth.password import hash_password, verify_password
...（完整代码）
```

...（完整对话记录，包含所有 log 内容）
```

**.mem 文件设计要点**:

| 特性 | 说明 |
|------|------|
| **高密度 Markdown** | 非二进制压缩，LLM 可直接读取 |
| **双区结构** | 结构化摘要（精炼）+ 完整记录（详尽） |
| **摘要不丢细节** | 摘要提取关键信息，完整记录保留一切 |
| **链式指针** | Prev/Next 指针构成双向链表 |
| **文本检索** | 可用 grep/rg 直接在 .mem 文件中搜索 |
| **容量** | 单文件无硬限制，实际通常 5-50KB |
| **APPEND-ONLY** | 完整记录区写入后不可修改（历史记忆不可变） |
| **可恢复** | .mem → .ses 可逆，从完整记录区重建 |

### .mem 恢复到 .ses 的机制

> **核心问题**: 结构化摘要是否会丢失细节？如何从 .mem 恢复到 .ses？
> 
> **回答**: 摘要本身会丢失细节，但 .mem 的完整记录区保留了 Layer 1 清理后的全部信息。恢复是从完整记录区重建，而非从摘要重建。

```
恢复流程（.mem → .ses）:

20260409-153000.mem
├── 结构化摘要区 ← 摘要确实丢失了细节，但这是设计意图
│   （精炼版，用于快速理解 session 内容）
│
└── 完整记录区   ← 包含 Layer 1 清理后的全部信息
    │              （所有对话 + 所有 log 内容）
    │
    ▼ 恢复操作
    1. 读取完整记录区
    2. 反向替换: 将 log 引用还原为实际内容
    3. 生成与 Layer 1 压缩前等价的 .ses 文件
    4. 恢复的 .ses 与原始 .ses 的差异:
       - 内容完整等价
       - 格式可能略有不同（元数据标记）
    
    恢复命令: adds session restore 20260409-153000
```

### 文件存储 vs 数据库存储对比

> **问题**: 压缩文件 vs DB（如 SQLite），哪种存储效率更高？是否保留全部记忆信息？

| 维度 | 文件存储（.mem Markdown） | 数据库存储（SQLite） |
|------|--------------------------|---------------------|
| **信息完整性** | ✅ 保留全部信息（完整记录区） | ✅ 保留全部信息 |
| **存储效率** | 中等（文本，可 gzip 压缩） | 较高（二进制，自动压缩） |
| **检索效率** | grep/rg（文本搜索，够用） | SQL 索引（结构化查询，快） |
| **可读性** | ✅ 人/LLM 可直接阅读 | ❌ 需工具查看 |
| **可移植性** | ✅ 纯文本，git 友好 | ❌ 二进制，合并困难 |
| **维护成本** | 低（无 schema 迁移） | 中（需管理表结构） |
| **ADDS 规模适用性** | ✅ KB-MB 级，完全够用 | 过度设计 |
| **与 LLM 交互** | ✅ 直接注入上下文 | 需额外转换 |

**结论**: 对于 ADDS 的规模和使用场景，文件存储完全足够。数据库的优势（索引、结构化查询）在 KB-MB 级数据上不明显，而文件存储的可读性和可移植性优势更大。如果未来数据量增长到 GB 级，再考虑引入 SQLite 作为 Layer 2 的索引层。

### 链式 Session 结构

```
时间线:  ←──────────────────────────────────────→

  ses1.ses         ses2.ses         ses3.ses (当前)
  ses1.mem         ses2.mem
    │                │                │
    │  Prev: null    │  Prev: ses1    │  Prev: ses2
    │  Next: ses2    │  Next: ses3    │  Next: null
    │                │                │
    ▼                ▼                ▼
  [摘要+详情]     [摘要+详情]      [活跃对话]
```

**新 session 启动时的上下文构建**:

```
新 session 上下文 = 
  System Prompt                    ← 静态 + 动态（最高优先级）
  + 固定记忆 (index.mem)           ← 升级后的精华，优先级低于 System Prompt
  + 上一个 session 的结构化摘要     ← 从 prev_ses.mem 的摘要区读取
  + 上一个 session 的链式指针       ← "历史详情在 {prev_ses.mem}，可回溯"
  + 当前任务消息                    ← 实时对话

⚠️ 上下文构建前需检测:
  System Prompt 与 固定记忆冲突 → 自动以 System Prompt 为准 + 通知用户
  用户最新指令与固定记忆冲突 → 自动以用户最新为准（Recency Bias）+ 记录冲突日志
  System Prompt 与用户最新指令冲突 → 必须暂停，向用户确认
```

**回溯机制**:

```
当 LLM 需要历史细节时:
1. LLM 在上下文中看到: "上一个 session 的链式指针: 20260409-153000.mem"
2. LLM 调用工具: 读取该 .mem 文件的完整记录区
3. 如果需要更早的: 沿 Prev 指针继续回溯
4. 文本检索: grep/rg 在 .ai/sessions/*.mem 中搜索关键词
```

### Token 预算管理

```python
class TokenBudget:
    """Token 预算管理器"""
    
    # 预算分配比例
    SYSTEM_PROMPT_RATIO = 0.15    # 15% for system prompt
    MEMORY_RATIO = 0.10           # 10% for 固定记忆 + 上一个摘要
    HISTORY_RATIO = 0.55          # 55% for 当前 session 对话
    TOOL_RESULT_RATIO = 0.15      # 15% for 工具输出
    RESERVE_RATIO = 0.05          # 5% 预留
    
    def __init__(self, context_window: int):
        self.context_window = context_window
        self.used = 0
    
    @property
    def utilization(self) -> float:
        return self.used / self.context_window
    
    def should_compact_layer1(self) -> bool:
        """是否需要 Layer 1 压缩"""
        return self.utilization > 0.5  # 工具输出大时提前压缩
    
    def should_compact_layer2(self) -> bool:
        """是否需要 Layer 2 归档"""
        return self.utilization > 0.8  # 上下文达 80%
    
    def should_warn(self) -> bool:
        """提醒 AI 加速收尾"""
        return self.utilization > 0.85
```

### 实现文件变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `scripts/context_compactor.py` | 新建 | 两层压缩引擎 |
| `scripts/token_budget.py` | 新建 | Token 预算管理器 |
| `scripts/session_manager.py` | 新建 | Session 文件管理（.ses/.log/.mem 读写） |
| `scripts/agent_loop.py` | 修改 | 每次迭代前检查预算 + 触发压缩 |
| `scripts/system_prompt_builder.py` | 修改 | 注入上一个 session 摘要 + 链式指针 |
| `scripts/adds.py` | 修改 | start 命令集成 session 管理 |

---

## 四、P0-3: 记忆系统（两层 + 无限记忆）

### 设计目标

1. **两层记忆**: 索引层（常驻上下文）+ 记忆层（按需加载）
2. **无限记忆**: 通过文本索引留线索，LLM 可沿线索找到任意历史
3. **记忆进化**: 高价值经验自动升级为固定记忆，让 LLM 持续提升能力
4. **纯文件存储**: 不使用数据库，.mem 文件 + grep/rg 检索
5. **记忆不可变**: 历史 .mem 文件的内容不可修改，仅索引可修订
6. **记忆优先级**: System Prompt > index.mem 固定记忆，冲突按 Recency Bias 规则自动/手动解决
7. **链式索引**: index.mem 自身也实现链式存储，按优先级排序

### 记忆层次与优先级体系

> **核心设计**: System Prompt 也是一种记忆，是用户为 Agent 创建的初始记忆。

```
┌─────────────────────────────────────────────────────────┐
│              记忆优先级体系（从高到低）                     │
│                                                          │
│  ① System Prompt（用户初始记忆）                          │
│     - 用户显式定义的指令和约束                              │
│     - 最高优先级，不可被覆盖                                │
│     - 来源: .ai/CORE_GUIDELINES.md + 动态构建部分         │
│                                                          │
│  ② index.mem 固定记忆（Agent 进化积累）                    │
│     - Agent 自主学习和积累的精华                            │
│     - 优先级低于 System Prompt                             │
│     - 来源: 记忆升级机制                                   │
│                                                          │
│  ③ index.mem 记忆索引（线索目录）                          │
│     - 指向 .mem 文件的引用                                 │
│     - 可被修订，但不影响 .mem 原文                         │
│                                                          │
│  ④ .mem 文件完整记录（历史记忆）                           │
│     - APPEND-ONLY，写入后不可修改                          │
│     - 是记忆的"真相源"                                    │
│                                                          │
│  冲突处理规则:                                             │
│  - System Prompt vs 固定记忆 → 自动以 System Prompt 为准   │
│  - 用户最新指令 vs 固定记忆 → 自动以用户最新为准(Recency)   │
│  - System Prompt vs 用户最新指令 → ⚠️ 必须暂停确认         │
│  - 原则: System Prompt 不可被 Recency Bias 覆盖            │
└─────────────────────────────────────────────────────────┘
```

### 记忆冲突检测与解决

```python
class MemoryConflictDetector:
    """记忆冲突检测器"""
    
    async def check_conflict(
        self, 
        system_prompt: str, 
        fixed_memory: dict
    ) -> list[dict]:
        """检测 System Prompt 与固定记忆的冲突
        
        方法: 调用 LLM 对比 system_prompt 与 index.mem 固定记忆
        检查是否存在语义冲突（非字面冲突）
        """
        conflicts = []
        prompt = f"""检查以下 System Prompt 与固定记忆是否存在冲突:

System Prompt 关键指令:
{self._extract_key_directives(system_prompt)}

固定记忆:
{self._format_fixed_memory(fixed_memory)}

请列出所有冲突项，格式:
- conflict: 冲突描述
- system_prompt_says: System Prompt 的说法
- memory_says: 固定记忆的说法
- suggestion: 建议处理方式（delete_memory / update_memory / ask_user）
"""
        result = await self.llm.chat(prompt)
        conflicts = self._parse_conflicts(result)
        return conflicts
    
    async def resolve_conflict(self, conflict: dict, user_decision: str):
        """根据用户决策解决冲突
        
        - delete_memory: 从 index.mem 删除冲突的固定记忆条目
        - update_memory: 更新固定记忆条目使其与 System Prompt 一致
        - 任何解决都记录到 .mem 文件（历史不可变原则）
        """
        pass
    
    async def auto_resolve(self, conflict: dict) -> Optional[str]:
        """自动解决冲突（Recency Bias 策略）
        
        自动解决规则（仅适用于"固定记忆 vs 用户最新指令"）：
        - System Prompt vs 固定记忆 → 自动以 System Prompt 为准 + 通知用户
        - 用户最新指令 vs 固定记忆 → 自动以用户最新指令为准 + 记录到冲突日志
        - System Prompt vs 用户最新指令 → ⚠️ 必须暂停，向用户确认
        
        返回: None 表示无法自动解决（需用户确认），否则返回解决方式
        """
        source_a = conflict.get("source_a")  # "system_prompt" | "user_latest" | "fixed_memory"
        source_b = conflict.get("source_b")
        
        # System Prompt vs 固定记忆 → 自动以 System Prompt 为准
        if ("system_prompt" in (source_a, source_b) and 
            "fixed_memory" in (source_a, source_b)):
            return "system_prompt_wins"
        
        # 用户最新指令 vs 固定记忆 → Recency Bias，以用户最新为准
        if ("user_latest" in (source_a, source_b) and 
            "fixed_memory" in (source_a, source_b)):
            return "user_latest_wins"
        
        # System Prompt vs 用户最新指令 → 无法自动解决
        return None
```

### 两层记忆架构

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: 索引层（常驻上下文，始终注入）                    │
│                                                          │
│  index.mem — 记忆线索目录（链式存储，按优先级排序）        │
│  ├─ 固定记忆（升级后的精华，直接可用）                     │
│  │   - 项目环境事实                                       │
│  │   - 核心经验教训                                       │
│  │   - 已掌握的技能摘要                                   │
│  │   - 用户关键偏好                                      │
│  │   ⚠️ 优先级低于 System Prompt                          │
│  │                                                      │
│  ├─ 记忆索引（线索，指向 .mem 文件）                      │
│  │   - 20260409-153000: 用户认证实现 (JWT+bcrypt)         │
│  │   - 20260409-143000: 项目初始化 (FastAPI+pytest)       │
│  │   - ...                                              │
│  │                                                      │
│  └─ 链式指针（当固定记忆超出容量时）                       │
│      Prev: index-prev.mem                                │
│      Next: null                                          │
│                                                          │
│  Token 预算: ~500-1000 tokens                           │
└──────────────────────┬──────────────────────────────────┘
                       │ 按需加载
┌──────────────────────▼──────────────────────────────────┐
│ Layer 2: 记忆层（.mem 文件，按需加载）                     │
│                                                          │
│  每个 .mem 文件包含:                                      │
│  ├─ 结构化摘要（精炼版）                                  │
│  ├─ 完整记录（含工具输出详情）— APPEND-ONLY              │
│  └─ 链式指针（Prev/Next）                                │
│                                                          │
│  ⚠️ 历史 .mem 文件不可修改                               │
│  ⚠️ 索引引用可修订，但 .mem 原文不可变                    │
│                                                          │
│  检索方式:                                               │
│  - 链式回溯: 从当前 session 沿 Prev 指针逐层回溯          │
│  - 关键词搜索: rg "JWT" .ai/sessions/*.mem               │
│  - 时间定位: 直接按文件名时间戳定位                       │
│                                                          │
│  Token 预算: 按需占用，用完释放                           │
└─────────────────────────────────────────────────────────┘
```

### 链式 index.mem 设计

> **核心问题**: 长任务中固定记忆不断增长，index.mem 空间会被压缩。解决方案：index 也实现链式存储，按优先级排序。

```
index.mem 链式结构:

index.mem (最新，最高优先级)     index-prev.mem (较早，较低优先级)
┌───────────────────────────┐   ┌───────────────────────────┐
│ # ADDS 记忆索引 (Page 1)   │   │ # ADDS 记忆索引 (Page 2)   │
│ Prev: index-prev.mem       │──→│ Prev: null                 │
│ Next: null                 │←──│ Next: index.mem            │
│                            │   │                            │
│ ## 固定记忆                │   │ ## 固定记忆（降级区）       │
│ [高优先级固定记忆]          │   │ [从 Page 1 降级来的]       │
│ - 当前项目核心经验          │   │ - 较早期的经验             │
│ - 最近验证的用户偏好        │   │ - 已不再活跃的技能         │
│                            │   │ - ❌ 已被证伪的经验        │
│                            │   │                            │
│ ## 记忆索引                │   │ ## 记忆索引（较早期）       │
│ [最近 session 线索]         │   │ [早期 session 线索]        │
└───────────────────────────┘   └───────────────────────────┘
```

**优先级排序算法**:

```python
class IndexPrioritySorter:
    """index.mem 内容的优先级排序"""
    
    def calculate_priority(self, item: dict) -> float:
        """计算记忆条目的优先级分数
        
        权重因子:
        1. 时间衰减: priority *= exp(-lambda * days_since_last_access)
           - 最近使用的记忆优先级更高
           - lambda = 0.05 (约 14 天半衰期)
        
        2. 重要性权重: 
           - 环境事实: weight = 1.0 (不会过时)
           - 经验教训: weight = 0.9 (长期有效)
           - 技能模式: weight = 0.7 (可能过时)
           - 用户偏好: weight = 1.0 (核心约束)
        
        3. 引用频率:
           - 在 .mem 文件中被引用次数越多，优先级越高
           - priority *= (1 + log(reference_count + 1))
        
        4. System Prompt 关联度:
           - 与 System Prompt 直接相关的条目权重 +0.5
        
        5. 负反馈惩罚（第三轮新增 — 记忆排毒）:
           - 验证性失效: 每被证伪一次，优先级 ×0.5
           - 任务回滚惩罚: 每导致回滚一次，优先级 ×0.7
           - 降级阈值: 优先级 < 0.1 → 自动降级到 index-prev.mem
        """
        base_priority = item.get("importance_weight", 0.5)
        
        # 时间衰减
        days_since = (datetime.now() - item["last_accessed"]).days
        time_decay = math.exp(-0.05 * days_since)
        
        # 引用频率
        ref_bonus = 1 + math.log(item.get("reference_count", 0) + 1)
        
        # System Prompt 关联度
        sp_related = 0.5 if item.get("system_prompt_related") else 0
        
        # 【第三轮新增】负反馈惩罚
        invalidation_count = item.get("invalidation_count", 0)   # 被证伪次数
        negative_penalty = 0.5 ** invalidation_count              # 每次证伪打5折
        
        rollback_count = item.get("rollback_count", 0)           # 导致回滚次数
        rollback_penalty = 0.7 ** rollback_count                  # 每次回滚打7折
        
        return (base_priority * time_decay * ref_bonus 
                * negative_penalty * rollback_penalty + sp_related)
    
    def sort_for_index(self, items: list[dict], capacity: int) -> tuple[list, list]:
        """排序并分割为当前 index 和溢出区
        
        返回: (current_index_items, overflow_items)
        - current_index_items: 高优先级，放入 index.mem（常驻上下文）
        - overflow_items: 低优先级，降级到 index-prev.mem
        """
        sorted_items = sorted(items, key=self.calculate_priority, reverse=True)
        total_chars = 0
        current = []
        overflow = []
        
        for item in sorted_items:
            item_chars = len(item["content"])
            if total_chars + item_chars <= capacity:
                current.append(item)
                total_chars += item_chars
            else:
                overflow.append(item)
        
        return current, overflow
```

### index.mem 格式

```markdown
# ADDS 记忆索引
# Page: 1
# 更新时间: 2026-04-09 16:00:00
# 此文件始终注入上下文，是 Agent 的"长期记忆索引"
# Prev: index-prev.mem    ← 链式指针（更早的索引）
# Next: null              ← 链式指针（更新的索引）
# ⚠️ 固定记忆优先级低于 System Prompt，冲突以 System Prompt 为准

---

## 固定记忆（精华，始终可用）

### 项目环境
- 语言: Python 3.9+
- 框架: FastAPI
- 测试: pytest
- 认证: JWT (PyJWT 2.x) + bcrypt

### 核心经验
- PyJWT 2.x API 与 1.x 不兼容，import 时注意 | module: auth | tags: jwt, token, auth, version | id: exp-001
- MiniMax API 使用 OpenAI 兼容格式，base_url: https://api.minimaxi.com/v1 | module: api | tags: minimax, api, openai | id: exp-002
- pytest-cov 用于覆盖率，命令: pytest --cov=src tests/ | module: test | tags: test, coverage | id: exp-003
- ~~用 requests 库做 HTTP 调用~~ ❌ 被 session 20260409-170000 证伪：导致内存溢出，应改用 httpx | module: http | status: invalidated | invalidation_count: 2 | id: exp-004

### 已掌握技能
- [jwt-auth] JWT 认证实现：生成/验证/刷新
- [api-testing] FastAPI 测试：TestClient + fixture

### 用户偏好
- 中文沟通，简洁直接
- 安全性 > 正确性 > 可读性 > 性能
- 先理解再动手

---

## 记忆索引（线索，按需回溯）

| 时间 | 文件 | 摘要 | 优先级 |
|------|------|------|--------|
| 04-09 15:30 | 20260409-153000.mem | 用户认证实现：JWT+bcrypt，12测试通过，87%覆盖率 | 高 |
| 04-09 14:30 | 20260409-143000.mem | 项目初始化：FastAPI+pytest，基础结构搭建 | 中 |

---

## 冲突记录

| 检测时间 | 冲突描述 | 来源A | 来源B | 解决方式 |
|----------|----------|-------|-------|----------|
| 04-09 16:00 | 认证方式 | System Prompt (JWT) | 固定记忆 (Session) | 自动: System Prompt 优先，删除 Session 条目 |
| 04-09 16:05 | 优先写测试 | 固定记忆 (先写测试) | 用户最新 (赶时间不写) | 自动: Recency Bias，以用户最新为准 |
| 04-09 16:10 | 代码风格 | System Prompt (严格类型) | 用户最新 (用 any) | 需确认: 两者都可能代表真实意图 |
```

### 记忆进化机制

```
                    记忆升级流程（第四轮更新）
                    ────────────

Session 结束
    │
    ▼
Layer 2 归档 → 生成 .mem 文件（APPEND-ONLY）
    │
    ├── 成功 session ──→ 反思协议(角色第一人称) ──→ 不重要 → 仅保留在 .mem 中
    │                   "作为 {role}，我学到了什么？"     └→ 重要 → 升级为固定记忆
    │                                                          └→ 标记 role 字段
    │
    └── 失败 session ──→ 记忆排毒检测（第三轮新增）
                          │
                          ├── 失败与某条固定记忆相关 → 验证性失效
                          │   ├─ 标记 status = "invalidated"
                          │   ├─ 记录 invalidated_reason + invalidated_by
                          │   ├─ invalidation_count++ → 优先级衰减
                          │   ├─ 优先级 < 0.1 → 降级到 index-prev.mem
                          │   └─ invalidation_count >= 2 → 强制复读（SP 顶部警示）← 第四轮新增
                          │
                          ├── 回归警报检测 ← 第四轮新增
                          │   ├─ ConsistencyGuard: 全量记忆检索
                          │   ├─ 相似度 > 85% → 触发回归警报
                          │   ├─ 元诊断: _diagnose_defense_failure()
                          │   │   ├─ 直觉层失效 → promote 到 SP
                          │   │   ├─ 记忆层失效 → 重写 + 加权
                          │   │   └─ 工具层失效 → 建议添加检查规则
                          │   └─ 记录回归警报到 .mem
                          │
                          └── 失败与固定记忆无关 → 仅记录失败到 .mem

升级为固定记忆:
    │
    ├── 环境事实类 → 写入 index.mem "项目环境" (role: common)
    ├── 经验教训类 → 写入 index.mem "核心经验" (role: {agent_role})  ← 第四轮改进
    ├── 技能模式类 → 写入 index.mem "已掌握技能" (role: {agent_role})
    └── 用户偏好类 → 写入 index.mem "用户偏好" (role: common)
    │
    ▼
轻量级冲突扫描（P0）── 发现可疑冲突 → 标记待审
    │
    ▼ 无冲突
检查容量 ──── 未超出 ──→ 完成
    │
    ▼ 超出 (~2000 字符)
优先级排序（含 code_heat 热度）→ 低优先级降级到 index-prev.mem  ← 第四轮改进
    │
    ▼
冲突检测 ──── 无冲突 ──→ 完成
    │
    ▼ 有冲突
向用户确认 → 更新/删除冲突条目
    │
    ▼
晋升仪式 (adds mem checkpoint --promote)  ← 第四轮新增
  - 展示本阶段各条记忆的进化历史
  - 交互确认: 哪些"新准则"正式晋升为"长期直觉"
  - 晋升记忆在 SP 中获得更高注入权重
```

**升级判断标准**:

| 类型 | 升级条件 | 示例 |
|------|---------|------|
| 环境事实 | 发现新的环境约束/配置 | "项目依赖 Python 3.9+" |
| 经验教训 | 踩坑后获得的通用教训 | "PyJWT 2.x API 不兼容" |
| 技能模式 | 成功完成某种模式 ≥2 次 | "JWT 认证实现模式" |
| 用户偏好 | 用户重复强调 ≥2 次 | "安全性优先" |

**记忆升级的 LLM 评估与置信度**:

> **核心问题**: 不同 LLM 的能力不同，评估结果可能有差异。

```python
@dataclass
class MemoryUpgradeEvaluation:
    """记忆升级评估结果"""
    should_upgrade: bool
    category: str           # environment | experience | skill | preference
    confidence: float       # 0.0 - 1.0，LLM 评估的置信度
    content: str            # 要升级的固定记忆内容
    reasoning: str          # LLM 的评估理由
    
    def needs_review(self) -> bool:
        """是否需要更强模型复核
        
        规则:
        - confidence < 0.7 → 需要复核
        - 涉及用户偏好 → 需要复核（不可替用户决策）
        - 涉及安全相关 → 需要复核
        """
        if self.confidence < 0.7:
            return True
        if self.category == "preference":
            return True
        return False

class MemoryEvolutionEngine:
    """记忆进化引擎"""
    
    async def evaluate_and_upgrade(
        self, 
        mem_content: str, 
        llm: ModelInterface
    ) -> list[MemoryUpgradeEvaluation]:
        """评估 .mem 内容中的经验价值
        
        LLM 评估提示词设计:
        - 明确列出四种升级类型和条件
        - 要求给出 confidence 和 reasoning
        - 要求判断是否需要人工复核
        """
        evaluations = []
        prompt = self._build_evaluation_prompt(mem_content)
        result = await llm.chat([{"role": "user", "content": prompt}])
        evaluations = self._parse_evaluations(result)
        
        # 复核逻辑
        for ev in evaluations:
            if ev.needs_review() and ev.should_upgrade:
                # 选择更强模型复核（如果有）
                reviewer = self._get_reviewer_llm(llm)
                if reviewer:
                    review_result = await self._review(reviewer, ev)
                    ev.should_upgrade = review_result.should_upgrade
                    ev.confidence = max(ev.confidence, review_result.confidence)
        
        return evaluations
    
    async def evaluate_and_invalidate(
        self,
        session_mem: str,
        failed_task_context: dict,
        llm: ModelInterface
    ) -> list[dict]:
        """验证性失效: 检测失败任务是否与某条固定记忆相关（第三轮新增）
        
        流程:
        1. 提取本次 session 中引用的固定记忆条目
        2. LLM 判断: 失败是否与某条固定记忆直接相关
        3. 相关 → 标记 invalidated, 增加 invalidation_count
        4. 优先级 < 0.1 → 降级到 index-prev.mem
        
        判断标准:
        - Agent 在本次 session 中主动引用了该固定记忆
        - 按照该记忆的建议执行后导致了任务失败
        - 失败的根本原因可追溯到该记忆的错误/过时
        """
        # 提取本次引用的固定记忆
        referenced_memories = failed_task_context.get("referenced_fixed_memories", [])
        
        if not referenced_memories:
            return []  # 没有引用固定记忆，无需排毒
        
        prompt = f"""分析以下任务失败是否与引用的固定记忆直接相关:

任务失败摘要:
{session_mem[:2000]}

引用的固定记忆:
{self._format_memories(referenced_memories)}

对每条引用的固定记忆，判断:
- related: 失败是否与该记忆直接相关 (true/false)
- reason: 如果相关，解释该记忆如何导致了失败
- severity: low / medium / high（该记忆的错误程度）

格式:
- memory_id: ...
- related: ...
- reason: ...
- severity: ...
"""
        result = await llm.chat([{"role": "user", "content": prompt}])
        invalidations = self._parse_invalidation_result(result, referenced_memories)
        
        # 执行失效标记
        for inv in invalidations:
            if inv.get("related"):
                await self._mark_invalidated(inv)
        
        return invalidations
    
    async def _mark_invalidated(self, invalidation: dict):
        """标记固定记忆为已失效
        
        操作:
        1. 在 index.mem 中标记: status = "invalidated"
        2. 记录: invalidated_reason = invalidation["reason"]
        3. 记录: invalidated_by = 当前 session ID
        4. 增加: invalidation_count += 1
        5. 重新计算优先级:
           - 优先级 < 0.1 → 降级到 index-prev.mem
           - 优先级 >= 0.1 → 保留但标记（仍可见但不被优先引用）
        6. 通知用户: "经验 X 已被证伪"
        """
        memory_id = invalidation["memory_id"]
        item = self._get_fixed_memory_item(memory_id)
        
        # 更新失效计数
        item["invalidation_count"] = item.get("invalidation_count", 0) + 1
        item["status"] = "invalidated"
        item["invalidated_reason"] = invalidation.get("reason", "")
        item["invalidated_by"] = invalidation.get("session_id", "")
        
        # 重新计算优先级
        sorter = IndexPrioritySorter()
        new_priority = sorter.calculate_priority(item)
        
        if new_priority < 0.1:
            # 降级到 index-prev.mem
            item["demotion_reason"] = "invalidation"
            await self._demote_to_prev(item)
        else:
            # 保留但标记
            await self._update_in_index(item)

**历史记忆不可变原则**:

### 记忆排毒与遗忘机制（第三轮新增）

> **核心问题**: 即使经过审查，错误的经验仍可能潜伏在固定记忆中。没有失效机制的记忆进化是单向的，只有积累没有清理，最终会拖累 Agent 的推理质量。需要设计"排毒闭环"。

**三大排毒手段**:

```
┌─────────────────────────────────────────────────────────┐
│                记忆排毒体系                               │
│                                                          │
│  ① 验证性失效 (Failure-Driven Invalidation)              │
│     触发: 任务失败且与某条固定记忆直接相关                  │
│     操作: 标记 invalidated → invalidation_count++          │
│     效果: 优先级 ×0.5/次 → 低于 0.1 自动降级              │
│     特点: 最有效的自动排毒手段，基于实际失败证据            │
│                                                          │
│  ② 负反馈惩罚 (Negative Penalty)                         │
│     触发: Agent 引用固定记忆后导致任务回滚                  │
│     操作: rollback_count++ → 优先级 ×0.7/次               │
│     效果: 持续回滚的记忆自然衰减退出主索引                  │
│     特点: 融入现有优先级排序，无需独立 Confidence 体系      │
│                                                          │
│  ③ 轻量级冲突扫描 (Lightweight Conflict Scan)             │
│     触发: 新记忆写入 index.mem 时                         │
│     操作: 关键词互斥对检测（零 LLM 成本）                  │
│     效果: 发现可疑冲突 → 标记待审 → P1 重量级扫描          │
│     特点: P0 规则匹配，P1 专员 Agent 语义扫描              │
│                                                          │
│  降级路径:                                               │
│  index.mem (活跃) → index-prev.mem (降级) → 可回溯        │
│  降级原因: invalidation | priority_decay | rollback       │
│  降级后: 不再主动注入上下文，但回溯时可见 + 标记证伪原因    │
└─────────────────────────────────────────────────────────┘
```

**轻量级冲突扫描器（P0）**:

```python
class LightweightConflictScanner:
    """P0: 关键词级冲突扫描（零 LLM 成本）
    
    在新记忆写入 index.mem 时执行，检测新老记忆的互斥关键词对。
    精度有限但零成本，发现可疑冲突后标记待审，P1 再用专员 Agent 深扫。
    """
    
    # 互斥关键词对（可扩展）
    CONFLICT_PAIRS = [
        ("JWT", "Session"),           # 认证方式冲突
        ("SQL", "NoSQL"),             # 数据库类型冲突
        ("REST", "GraphQL"),          # API 风格冲突
        ("Python", "Rust"),           # 语言冲突
        ("monolith", "microservice"), # 架构冲突
        ("sync", "async"),            # 并发模型冲突
    ]
    
    def scan(self, new_memory: str, existing_memories: list[str]) -> list[dict]:
        """扫描新记忆与现有记忆的冲突"""
        conflicts = []
        for kw_a, kw_b in self.CONFLICT_PAIRS:
            if kw_a.lower() in new_memory.lower():
                for existing in existing_memories:
                    if kw_b.lower() in existing.lower():
                        conflicts.append({
                            "new_memory": new_memory,
                            "existing_memory": existing,
                            "conflict_type": f"{kw_a} vs {kw_b}",
                            "severity": "suspected",  # 需进一步确认
                        })
            # 反向检查
            if kw_b.lower() in new_memory.lower():
                for existing in existing_memories:
                    if kw_a.lower() in existing.lower():
                        conflicts.append({
                            "new_memory": new_memory,
                            "existing_memory": existing,
                            "conflict_type": f"{kw_b} vs {kw_a}",
                            "severity": "suspected",
                        })
        return conflicts
```

**排毒流程中的记忆状态**:

| 状态 | 含义 | 在 index.mem 中的表现 | 是否注入上下文 |
|------|------|----------------------|--------------|
| `active` | 正常活跃 | 标准显示 | ✅ 是 |
| `suspected` | 冲突待审 | 显示 + ⚠️ 标记 | ✅ 是（带警告） |
| `invalidated` | 已被证伪 | 显示 + ❌ 标记 + 证伪原因 | ⚠️ 低优先级，降级后不再注入 |
| `demoted` | 已降级 | 移到 index-prev.mem | ❌ 否（可回溯） |

**排毒与不可变原则的关系**:

```
不可变原则适用于 .mem 文件（历史记忆）
排毒机制作用于 index.mem（固定记忆索引）

两者不矛盾:
  - .mem 文件: APPEND-ONLY，记录"曾经有过这个经验"（含证伪记录）
  - index.mem: 可修订，标记"这个经验已被证伪/降级"
  - 回溯时: Agent 能看到 "经验 X，已被 session Y 证伪，原因：..."
  - 价值: 保留"犯过错"的信息，避免重蹈覆辙
```

### 角色化记忆体系（第四轮新增）

> **核心洞察**: 不同角色的 Agent 需要差异化的"肌肉记忆"。Dev 记住"手"的动作（实现细节、API 技巧），Architect 记住"界"的定义（模块边界、架构约束），QA 记住"眼"的焦点（高风险代码特征、回归点）。这不是构建统一百科，而是为每个角色构建"职场生存手册"。

**P0 策略: `role:` 字段 + 过滤注入**

在现有 `index.mem` 的固定记忆条目中新增 `role:` 字段。P0 阶段共享 index.mem 但按 role 过滤注入；P1 阶段再物理拆分到 `index-{role}.mem`。

```
角色与记忆维度对应:

┌─────────────────────────────────────────────────────────┐
│                角色化记忆映射                              │
│                                                          │
│  Dev Agent → 记住"手"的动作                               │
│     - 高效代码片段、库的坑、具体实现模式                     │
│     - 例: "在调用 C 接口后，必须显式调用 Box::from_raw"    │
│                                                          │
│  Architect Agent → 记住"界"的定义                         │
│     - 系统边界、模块依赖约束、技术选型禁忌                   │
│     - 例: "FFI 调用必须封装在 safety-wrapper 模块中"       │
│                                                          │
│  QA Agent → 记住"眼"的焦点                               │
│     - 高风险代码特征、曾出现的边界用例、测试回归点           │
│     - 例: "FFI 变更必须强制 valgrind 检查"                │
│                                                          │
│  所有角色共享:                                            │
│     - 项目环境事实 (role: common)                          │
│     - 用户偏好 (role: common)                             │
│     - 通用经验教训 (role: common)                          │
└─────────────────────────────────────────────────────────┘
```

**固定记忆条目格式扩展**:

```markdown
### 核心经验
- PyJWT 2.x API 与 1.x 不兼容 | module: auth | role: dev | tags: jwt, token | id: exp-001
- FFI 调用必须封装在 safety-wrapper 模块中 | module: ffi | role: architect | tags: ffi, safety | id: exp-005
- FFI 变更必须强制 valgrind 检查 | module: ffi | role: qa | tags: ffi, testing | id: exp-006
- 项目依赖 Python 3.9+ | role: common | id: exp-007
```

**注入逻辑**:

```python
class RoleAwareMemoryInjector:
    """角色感知记忆注入器"""
    
    def filter_memories_for_role(
        self, 
        index_mem: dict, 
        current_role: str
    ) -> list[dict]:
        """根据当前 Agent 角色过滤固定记忆
        
        规则:
        1. role: common → 所有角色都注入
        2. role: {specific} → 仅注入给匹配角色
        3. 未标记 role → 默认 common（向后兼容）
        """
        filtered = []
        for item in index_mem["fixed_memories"]:
            item_role = item.get("role", "common")
            if item_role == "common" or item_role == current_role:
                filtered.append(item)
        return filtered
```

**P1 路径: 物理拆分**

```
.ai/memories/
├── dev/
│   ├── index.mem       # 记录：高效代码片段、库的坑、具体实现模式
│   └── 20260409.mem    # 开发过程详情
├── architect/
│   ├── index.mem       # 记录：系统边界、模块依赖约束、技术选型禁忌
│   └── 20260409.mem    # 架构演进决策理由
└── qa/
    ├── index.mem       # 记录：高风险代码特征、曾出现的边界用例、测试回归点
    └── 20260409.mem    # 测试覆盖分析
```

**角色进化逻辑示例**:

当同一个 Bug（Rust 内存泄漏在 FFI 调用处）被解决后：

| 角色 | 记忆内容 | 进化方向 |
|------|---------|---------|
| Dev | "在调用 C 接口后，必须显式调用 Box::from_raw 以防泄露" | 以后写代码直接避坑 |
| Architect | "FFI 调用必须封装在统一的 safety-wrapper 模块中，禁止散落在业务逻辑层" | 以后设计评审报错 |
| QA | "涉及 FFI 变更的任务，必须强制进行 valgrind 检查" | 以后测试计划权重提升 |

### 反思协议（第四轮新增）

> **核心洞察**: 记忆升级不应是"旁观评估"（LLM 从第三者视角判断什么值得记住），而应是"第一人称反思"（Agent 自己反思"我学到了什么"）。这是从"被动记录"到"主动进化"的质变。

**设计原理**:

```
当前设计:
  LLM 评估 .mem → 决定是否升级 → 写入 index.mem
  视角: 第三者旁观 → "这段经验是否有价值？"

反思协议设计:
  Agent 反思 → 自我定义行为守则 → 写入 index.mem
  视角: 第一人称 → "作为 {role}，我这次学到了什么必须记住的？"
```

**任务闭环反思指令**:

在每个任务闭环前，框架向参与 Agent 发送强制性反思上下文：

```python
REFLECTION_PROMPT = """[Framework Protocol: Role-Based Evolution]

当前任务已闭环。作为 **{role_name}**，请审阅本次任务的全部过程，并执行以下思考逻辑：

1. **提取核心事实**: 本次任务中，哪些信息是本角色未来**必须**知道的？
   - 不是"发生了什么"，而是"什么会改变我未来的决策"

2. **更新行为守则**: 基于此任务，我以后在执行 **{role_name}** 职责时，应该增加/修改哪条准则？
   - 格式: "以后遇到 {条件} 时，必须 {行为}"
   - 例: "以后调用 C 接口后，必须显式调用 Box::from_raw"

3. **压缩与抽象**: 请将上述内容压缩为高密度的 Markdown 条目，准备更新至你的 index.mem。
   - 不要记录琐碎的过程，只记录改变你未来决策的"精华"
   - 每条不超过 50 字

输出格式:
- fact: 核心事实（1-3 条）
- rule: 行为守则（0-2 条）
- memory_candidate: 压缩后的记忆条目（0-3 条）
- role: {role_name}
"""
```

**与现有 `MemoryEvolutionEngine` 的融合**:

```python
class MemoryEvolutionEngine:
    """记忆进化引擎（融合反思协议）"""
    
    async def evaluate_and_upgrade(
        self, 
        mem_content: str, 
        llm: ModelInterface,
        role: str = "common"  # 第四轮新增: 角色参数
    ) -> list[MemoryUpgradeEvaluation]:
        """评估 .mem 内容中的经验价值
        
        改进: 从第三者旁观评估 → 第一人称角色反思
        - 旧: LLM 从外部判断"这段经验是否有价值"
        - 新: Agent 以 {role} 的第一人称反思"我学到了什么"
        """
        # 使用反思协议替代原有的旁观评估 prompt
        reflection_prompt = REFLECTION_PROMPT.format(role_name=role)
        result = await llm.chat([
            {"role": "system", "content": reflection_prompt},
            {"role": "user", "content": f"本次任务过程:\n{mem_content}"}
        ])
        
        reflections = self._parse_reflection(result, role)
        
        # 转换为 MemoryUpgradeEvaluation 格式（保持与现有流程兼容）
        evaluations = []
        for r in reflections:
            evaluations.append(MemoryUpgradeEvaluation(
                should_upgrade=r.get("memory_candidate") is not None,
                category=r.get("category", "experience"),
                confidence=r.get("confidence", 0.7),
                content=r.get("memory_candidate", ""),
                reasoning=f"角色反思: {r.get('fact', '')} → {r.get('rule', '')}",
                role=role  # 新增字段
            ))
        
        # 复核逻辑（保持不变）
        for ev in evaluations:
            if ev.needs_review() and ev.should_upgrade:
                reviewer = self._get_reviewer_llm(llm)
                if reviewer:
                    review_result = await self._review(reviewer, ev)
                    ev.should_upgrade = review_result.should_upgrade
                    ev.confidence = max(ev.confidence, review_result.confidence)
        
        return evaluations
```

**MemoryUpgradeEvaluation 扩展**:

```python
@dataclass
class MemoryUpgradeEvaluation:
    """记忆升级评估结果"""
    should_upgrade: bool
    category: str           # environment | experience | skill | preference
    confidence: float       # 0.0 - 1.0
    content: str            # 要升级的固定记忆内容
    reasoning: str          # 评估理由
    role: str = "common"    # 第四轮新增: 产生此评估的角色
```

### 回归警报与元诊断（第四轮新增）

> **核心洞察**: 当旧 Bug 再现时，不仅要修复 Bug，还需启动"元修复"——诊断为什么旧记忆没拦截住。这是从"产生抗体"升级到"诊断免疫失效原因"，是真正的"免疫系统"设计。

**三位一体防御体系**:

```
┌─────────────────────────────────────────────────────────┐
│           三位一体防御: 直觉 / 记忆 / 工具                │
│                                                          │
│  ① 直觉 (Intuition)                                     │
│     载体: System Prompt + 角色准则                        │
│     响应: 极快 — 在写代码的第一行就避开违规操作            │
│     失效表现: Agent 写出了违反准则的代码                   │
│                                                          │
│  ② 记忆 (Memory)                                        │
│     载体: index-{role}.mem                               │
│     响应: 中等 — 通过语义搜索发现历史经验                  │
│     失效表现: Agent 犯了曾经记住要避免的错误               │
│                                                          │
│  ③ 工具 (Tools)                                         │
│     载体: 测试集 / Linter / 静态分析                      │
│     响应: 慢但确定 — 通过 pytest/cargo check 强制把关     │
│     失效表现: 测试覆盖不足或 lint 规则缺失                 │
│                                                          │
│  防御优先级: 直觉 > 记忆 > 工具                           │
│  修复优先级: 工具 > 记忆 > 直觉（越早拦截越好）           │
└─────────────────────────────────────────────────────────┘
```

**回归警报: 历史碰撞检测**:

当 QA 发现一个 Bug 时，系统强制执行全量记忆检索：

```python
class ConsistencyGuard:
    """一致性守护 — 回归警报与元诊断"""
    
    SIMILARITY_THRESHOLD = 0.85  # 碰撞检测阈值
    
    async def analyze_failure(
        self, 
        current_failure: dict, 
        memories: 'MemoryStore',
        llm: ModelInterface
    ) -> Optional[RegressionAlarm]:
        """分析失败是否为旧问题回归
        
        流程:
        1. 将当前错误日志 + 受影响代码片段作为查询
        2. 在所有历史 .mem 归档中检索相似案例
        3. 相似度 > 85% → 触发"回归警报 (Regression Alarm)"
        4. 回归警报 → 启动"元修复任务"
        """
        # 全量记忆检索
        similar_cases = await memories.search(
            query=self._build_failure_query(current_failure),
            top_k=5
        )
        
        # 碰撞检测
        for case in similar_cases:
            similarity = await self._compute_similarity(
                current_failure, case, llm
            )
            if similarity > self.SIMILARITY_THRESHOLD:
                return RegressionAlarm(
                    current_failure=current_failure,
                    historical_case=case,
                    similarity=similarity,
                    diagnosis=await self._diagnose_defense_failure(
                        current_failure, case, llm
                    )
                )
        
        return None
    
    async def _diagnose_defense_failure(
        self,
        current_failure: dict,
        historical_case: dict,
        llm: ModelInterface
    ) -> DefenseFailureDiagnosis:
        """元诊断: 为什么旧记忆没有拦截住旧问题的回归？
        
        诊断三层防御的失效点:
        
        ① 直觉层失效?
           → 这条经验没进入 System Prompt
           → 处方: 建议 promote 到 SP 顶部
        
        ② 记忆层失效?
           → 描述太模糊/注意力不足/被其他信息淹没
           → 处方: 重写记忆 + 提升权重
        
        ③ 工具层失效?
           → 没有 lint/test 规则覆盖这类问题
           → 处方: 建议添加静态检查规则
        """
        prompt = f"""诊断: 为什么已有的记忆没能防止此问题再次发生？

历史记忆:
{historical_case.get('memory_content', '')}

当前失败:
- 错误: {current_failure.get('error', '')}
- 代码: {current_failure.get('code_snippet', '')}
- 该记忆在历史中被引用: {historical_case.get('reference_count', 0)} 次

请判断哪层防御失效:
1. 直觉层: 该经验是否已写入 System Prompt? (是/否/不确定)
2. 记忆层: 该经验描述是否足够精准? 是否被其他信息淹没?
3. 工具层: 是否存在对应的 lint/test 规则?

输出格式:
- failed_layer: intuition | memory | tool | multiple
- diagnosis: 诊断说明
- prescription: 修复建议（具体操作）
"""
        result = await llm.chat([{"role": "user", "content": prompt}])
        return self._parse_diagnosis(result)
```

**回归警报触发后的处理流程**:

```
回归警报触发:
    │
    ▼
┌─ 元诊断: 为什么防御失败？ ─────────────────────────┐
│                                                      │
│  直觉层失效?                                         │
│  → 这条经验没进入 System Prompt                      │
│  → 处方: 在 SP 顶部强制置顶此条经验（promote）        │
│                                                      │
│  记忆层失效?                                         │
│  → 描述太模糊 / 注意力不足 / 被淹没                  │
│  → 处方: 重写记忆 + 增加 invalidation_count 权重      │
│                                                      │
│  工具层失效?                                         │
│  → 没有 lint/test 规则覆盖                           │
│  → 处方: 建议添加静态检查规则                         │
│                                                      │
│  多层同时失效?                                       │
│  → 向人类发送元通知                                   │
│  → 建议"全层强化"                                    │
└──────────────────────────────────────────────────────┘
    │
    ▼
自动修正:
  1. 修订 index.mem: 增加"高能警示标记"（⚠️ 回归风险）
  2. 向人类发送元通知: "检测到旧问题回归，已自动强化记忆权重"
  3. 强制复读: 在该 Agent 接下来的 3 个任务中，SP 顶部强制置顶历史教训
```

**与现有 `evaluate_and_invalidate()` 的融合**:

```python
class MemoryEvolutionEngine:
    # ... 现有方法 ...
    
    async def evaluate_and_invalidate(
        self,
        session_mem: str,
        failed_task_context: dict,
        llm: ModelInterface
    ) -> list[dict]:
        """验证性失效（融合元诊断）"""
        
        # 原有逻辑: 检测失败与固定记忆的关联
        invalidations = await self._detect_invalidation(
            session_mem, failed_task_context, llm
        )
        
        # 第四轮新增: 回归警报检测
        guard = ConsistencyGuard()
        alarm = await guard.analyze_failure(
            current_failure=failed_task_context,
            memories=self.memory_store,
            llm=llm
        )
        
        if alarm:
            # 执行元诊断
            diagnosis = alarm.diagnosis
            
            # 根据诊断结果自动修正
            if diagnosis.failed_layer == "intuition":
                # 直觉层失效 → 建议 promote 到 SP
                await self._promote_to_system_prompt(
                    alarm.historical_case, 
                    reason="回归警报: 直觉层失效"
                )
            elif diagnosis.failed_layer == "memory":
                # 记忆层失效 → 重写 + 加权
                await self._refine_memory_description(
                    alarm.historical_case,
                    diagnosis.prescription
                )
            elif diagnosis.failed_layer == "tool":
                # 工具层失效 → 建议添加检查规则
                await self._suggest_lint_rule(
                    alarm.historical_case,
                    diagnosis.prescription
                )
            
            # 记录回归警报到 .mem
            await self._record_regression_alarm(alarm, diagnosis)
        
        return invalidations
```

**强制复读机制**:

当某条记忆的 `invalidation_count >= 2`（被证伪 ≥2 次，说明回归风险高），自动在 System Prompt 顶部添加警示：

```python
class SystemPromptBuilder:
    def build(self, context: dict) -> str:
        # ... 现有逻辑 ...
        
        # 第四轮新增: 强制复读
        forced_reminders = self._get_forced_reminders(context["role"])
        if forced_reminders:
            reminder_block = "\n".join([
                f"⚠️ 历史教训: {r['content']} (被证伪 {r['invalidation_count']} 次)"
                for r in forced_reminders
            ])
            system_prompt = f"【强制复读 — 历史回归风险】\n{reminder_block}\n\n{system_prompt}"
        
        return system_prompt
    
    def _get_forced_reminders(self, role: str) -> list[dict]:
        """获取需要强制复读的记忆
        
        条件: invalidation_count >= 2 且未被 promote 到 SP
        效果: 在该 Agent 接下来的 3 个任务中强制置顶
        """
        reminders = []
        for item in self.index_mem["fixed_memories"]:
            if (item.get("invalidation_count", 0) >= 2 
                and not item.get("promoted_to_sp", False)
                and (item.get("role", "common") in (role, "common"))):
                reminders.append(item)
        return reminders
```

### 注意力热点与动态权重（第四轮新增）

> **核心洞察**: 频繁修改的模块相关记忆应自动"加热"到上下文顶部。LLM 的上下文空间有限，注意力应当高度聚焦于当前热点区域。

**第 6 权重因子: 代码热度 (code_heat)**

在 `IndexPrioritySorter.calculate_priority()` 中新增第 6 个权重因子：

```python
class IndexPrioritySorter:
    """index.mem 内容的优先级排序（含代码热度）"""
    
    def calculate_priority(self, item: dict, code_heat_map: dict = None) -> float:
        """计算记忆条目的优先级分数
        
        权重因子 (第四轮更新):
        1. 时间衰减: exp(-0.05 * days_since_last_access)
        2. 重要性权重: environment=1.0, experience=0.9, skill=0.7, preference=1.0
        3. 引用频率: (1 + log(reference_count + 1))
        4. System Prompt 关联度: +0.5
        5. 负反馈惩罚: 0.5^invalidation_count * 0.7^rollback_count
        6. 代码热度 (code_heat): 最近频繁修改的模块相关记忆临时加温 ← 第四轮新增
        """
        base_priority = item.get("importance_weight", 0.5)
        
        # 1. 时间衰减
        days_since = (datetime.now() - item["last_accessed"]).days
        time_decay = math.exp(-0.05 * days_since)
        
        # 2. 引用频率
        ref_bonus = 1 + math.log(item.get("reference_count", 0) + 1)
        
        # 3. System Prompt 关联度
        sp_related = 0.5 if item.get("system_prompt_related") else 0
        
        # 4. 负反馈惩罚
        invalidation_count = item.get("invalidation_count", 0)
        negative_penalty = 0.5 ** invalidation_count
        rollback_count = item.get("rollback_count", 0)
        rollback_penalty = 0.7 ** rollback_count
        
        # 5. 代码热度（第四轮新增）
        code_heat_bonus = 1.0  # 默认无加温
        if code_heat_map:
            module = item.get("module", "")
            if module in code_heat_map:
                # 热度 = 最近 7 天内该模块的文件变更数
                # 变更越多，相关记忆越重要
                heat = code_heat_map[module]
                code_heat_bonus = 1.0 + min(heat * 0.1, 0.5)  # 最多 +50%
        
        return (base_priority * time_decay * ref_bonus 
                * negative_penalty * rollback_penalty * code_heat_bonus
                + sp_related)
    
    def build_code_heat_map(self, days: int = 7) -> dict:
        """构建代码热度地图
        
        输入: git log --since="7 days ago" --name-only
        处理: 按模块路径前缀统计变更频率
        输出: {"auth": 5, "api": 3, "ffi": 8, ...}
        """
        import subprocess
        try:
            result = subprocess.run(
                ["git", "log", f"--since={days} days ago", "--name-only", "--pretty=format:"],
                capture_output=True, text=True
            )
            heat_map = {}
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                # 提取模块前缀 (e.g., "src/auth/jwt.py" → "auth")
                parts = line.split("/")
                module = parts[1] if len(parts) > 1 else parts[0]
                heat_map[module] = heat_map.get(module, 0) + 1
            return heat_map
        except Exception:
            return {}
```

**注意力热点在 Agent Loop 中的集成**:

```python
# 在 agent_loop.py 中，每次新 session 启动时:
sorter = IndexPrioritySorter()
code_heat_map = sorter.build_code_heat_map(days=7)
# 将 code_heat_map 传入 calculate_priority，影响记忆排序
```

### 记忆晋升仪式（第四轮新增）

> **核心洞察**: `checkpoint` 是"快照"（静态存档），`promote` 是"晋升"（动态确认）。promote 说的是"我认可这段进化，让它成为你的直觉"，是从"临时记忆"向"长期直觉"的转变仪式。

**`adds mem checkpoint --promote` 模式**:

在现有 `adds mem checkpoint` 命令基础上增加 `--promote` 模式：

```bash
# 现有: 快照
adds mem checkpoint --tag v1.0.0
# → 复制 index.mem → index-v1.0.0.mem（静态快照）

# 第四轮新增: 快照 + 晋升
adds mem checkpoint --tag v1.0.0 --promote
# → 1. 复制 index.mem → index-v1.0.0.mem（快照，已有）
# → 2. 展示本阶段各条记忆的进化历史（新增）
# → 3. 交互确认: 哪些"新准则"正式晋升为"直觉"（新增）
# → 4. 晋升的记忆标记 promoted: true + promoted_at: v1.0.0（新增）
# → 5. 晋升的记忆在 SP 中获得更高注入权重（新增）
```

**晋升交互流程**:

```
$ adds mem checkpoint --tag v1.0.0 --promote

📸 快照: index.mem → index-v1.0.0.mem ✓

📋 本阶段记忆进化报告:
─────────────────────────────────────────────────
[1] 🔥 晋升候选 (引用 5 次, 优先级 0.92)
    "PyJWT 2.x API 与 1.x 不兼容，import 时注意"
    来源: session 20260409-153000 | 角色: dev
    → (p)romote / (s)kip

[2] ⚠️ 回归风险 (被证伪 2 次)
    "用 httpx 替代 requests 做 HTTP 调用"
    来源: session 20260409-170000 | 角色: dev
    → (p)romote / (s)kip / (e)nhance

[3] 📌 新行为守则 (引用 3 次, 优先级 0.85)
    "FFI 调用必须封装在 safety-wrapper 模块中"
    来源: session 20260410-090000 | 角色: architect
    → (p)romote / (s)kip

─────────────────────────────────────────────────
确认晋升 2 条记忆为"长期直觉"? (y/n) y

✅ 已晋升:
  - exp-001: promoted=true, promoted_at=v1.0.0
  - exp-005: promoted=true, promoted_at=v1.0.0

✅ 晋升的记忆将在 System Prompt 中获得更高注入权重
```

**晋升标记在 index.mem 中的表现**:

```markdown
### 核心经验
- PyJWT 2.x API 与 1.x 不兼容 | module: auth | role: dev | promoted: true | promoted_at: v1.0.0 | id: exp-001
- FFI 调用必须封装在 safety-wrapper 模块中 | module: ffi | role: architect | promoted: true | promoted_at: v1.0.0 | id: exp-005
```

**晋升记忆的 SP 注入权重**:

```python
class SystemPromptBuilder:
    def _get_memory_injection_priority(self, item: dict) -> float:
        """计算记忆条目的 SP 注入权重
        
        规则:
        - promoted=true → 权重 × 1.5（更靠近 SP 顶部）
        - promoted_at 与当前 tag 一致 → 权重 × 1.3（最新晋升，特别关注）
        - invalidation_count >= 2 → 权重 × 1.2（强制复读区域）
        - 普通 active → 权重 × 1.0
        """
        weight = 1.0
        if item.get("promoted", False):
            weight *= 1.5
        if item.get("promoted_at") == self.current_tag:
            weight *= 1.3
        if item.get("invalidation_count", 0) >= 2:
            weight *= 1.2  # 强制复读
        return weight
```

**晋升与不可变原则**:

```
promote 操作不违反不可变原则:
  ✅ index.mem 条目标记 promoted=true（索引可修订）
  ✅ .mem 文件追加晋升记录（append-only）
  ❌ 不修改 .mem 文件中的原始内容

晋升记录格式（追加到 .mem 文件末尾）:
### [promote] 2026-04-09T23:30:00
记忆: exp-001 "PyJWT 2.x API 与 1.x 不兼容"
晋升为: 长期直觉 (promoted_at: v1.0.0)
原因: 引用 5 次, 优先级 0.92, 人工确认
操作者: human
```

### 人工干预与里程碑节点（第三轮新增）

> **设计原则**: 人工干预不应是"修修补补"，而应是"方向对齐"。自动排毒机制处理常规失效，人工干预处理战略级记忆管理。

**里程碑触发机制**:

| 触发点 | 触发条件 | 执行操作 | 阶段 |
|--------|---------|---------|------|
| Git Tag 产生 | `git tag v*` 被创建 | 触发 `adds mem checkpoint` — 固化当前固定记忆快照 | P0 |
| 合并到主分支 | `git merge` 到 main/master | 审查合并涉及的模块相关记忆是否仍然有效 | P1 |
| 核心模块重构 | 配置的"核心模块"文件被大量修改（>30% 行变更） | 触发 `adds mem flush --module <name>` — 标记相关记忆待审 | P0 |
| 连续任务失败 | 同一 session 连续 3 次引用相同固定记忆且失败 | 触发记忆排毒 + 暂停 Agent + 通知人工审查 | P0 |
| 新 Provider 首次使用 | 首次切换到新模型/CLI | 提示"旧经验可能不适用于新模型，建议审查" | P1 |

**核心模块配置**:

```json
// .ai/settings.json
{
  "memory": {
    "core_modules": [
      "src/auth/",       // 认证模块重构时需审查 auth 相关记忆
      "src/models/",     // 数据模型重构时需审查 schema 相关记忆
      "src/api/"         // API 层重构时需审查接口相关记忆
    ],
    "failure_threshold": 3,      // 连续失败触发审查的阈值
    "checkpoint_on_tag": true,   // Git Tag 时自动 checkpoint
    "auto_audit_on_merge": false // P1: 合并时自动审查（默认关闭，成本高）
  }
}
```

**CLI 记忆管理子命令**:

```bash
# ═══ 记忆状态检查 ═══

adds mem status
# 显示记忆系统健康概览:
#   固定记忆: 12 条 (active: 9, suspected: 2, invalidated: 1)
#   容量: 1850/2000 字符 (92%)
#   最近证伪: "用 requests 库做 HTTP 调用" (2 天前)
#   最近降级: 1 条 (rollback ×3)
#   待审条目: 2 条 (轻量级冲突扫描发现)

# ═══ 记忆审计 ═══

adds mem audit
# 进入交互模式，逐条审查 index.mem 中的固定记忆:
# 
#   [1/12] 核心经验 | active
#   "PyJWT 2.x API 与 1.x 不兼容，import 时注意"
#   引用次数: 5 | 优先级: 0.87 | 创建: 04-09
#   操作: (k)eep / (i)nvalidate / (e)dit / (d)emote / (s)kip

adds mem audit --status suspected
# 仅审查状态为 suspected 的条目

adds mem audit --module auth
# 仅审查与 auth 模块相关的条目

# ═══ 记忆清理 ═══

adds mem prune --module auth
# 清理特定模块的陈旧/失效记忆:
#   - 扫描 index.mem 中 module=auth 的条目
#   - 显示每条的状态和优先级
#   - 交互确认是否降级/删除

adds mem prune --status invalidated
# 清理所有已证伪但尚未降级的条目

adds mem prune --older-than 30d
# 清理 30 天以上未被引用的低优先级条目

# ═══ 记忆覆盖（人工更正）═══

adds mem override <id>
# 人工更正某条被固化的错误经验:
#   1. 显示该条记忆的完整信息
#   2. 提示输入更正内容和原因
#   3. 在 index.mem 中覆盖原条目（标记 override_by: human）
#   4. 在 .mem 中追加覆盖记录（不可变原则：不删原文，追加更正）
#
# 覆盖记录格式（追加到 .mem 文件末尾）:
# ### [override] 2026-04-09T23:00:00
# 原记忆: "用 requests 库做 HTTP 调用"
# 更正为: "用 httpx 库做 HTTP 调用（支持 async）"
# 原因: requests 导致内存溢出
# 操作者: human

# ═══ 记忆生命周期查看 ═══

adds mem history <id>
# 查看某条记忆的完整生命周期:
#   创建: 2026-04-09 15:30 (session 20260409-153000, LLM评估 confidence=0.85)
#   引用: 5 次 (04-09, 04-10×2, 04-11, 04-12)
#   证伪: 1 次 (04-12, session 20260412-100000, "导致内存溢出")
#   回滚: 0 次
#   当前状态: invalidated | 优先级: 0.22
#   覆盖: 2026-04-12 human → "用 httpx 库做 HTTP 调用"

# ═══ 记忆快照（里程碑）═══

adds mem checkpoint --tag v1.0.0
# 固化当前固定记忆快照:
#   1. 复制 index.mem → index-v1.0.0.mem
#   2. 记录当前所有固定记忆的状态和优先级
#   3. 后续可对比: adds mem diff --from v1.0.0 --to current

adds mem diff --from v1.0.0 --to current
# 对比两个快照之间的记忆变化:
#   新增: 3 条
#   失效: 1 条 ("用 requests 做 HTTP")
#   降级: 2 条
#   覆盖: 1 条
```

**固定记忆条目格式扩展**（支持 module 标签）:

```markdown
### 核心经验
- PyJWT 2.x API 与 1.x 不兼容 | module: auth | tags: jwt, token | id: exp-001
- MiniMax API 使用 OpenAI 兼容格式 | module: api | tags: minimax | id: exp-002
- ~~用 requests 库做 HTTP 调用~~ ❌ | module: http | status: invalidated | id: exp-003
```

**override 与不可变原则的兼容**:

```
override 操作流程:
1. 在 index.mem 中: 替换条目内容 + 标记 override_by: human + override_reason
2. 在 .mem 文件末尾: 追加 override 记录（append-only，不修改原文）
3. 原 .mem 记录: 完整保留，包括"该经验曾被错误地固化"这一事实

不可变原则:
  ✅ index.mem 条目可覆盖（索引可修订）
  ✅ .mem 文件追加 override 记录（append-only）
  ❌ 不修改 .mem 文件中的原始内容
```

**历史记忆不可变原则**:

```
不可变原则: .mem 文件写入后，完整记录区不可修改

允许的操作:
  ✅ 修订 index.mem 中的线索描述（索引可修订）
  ✅ 降级固定记忆到 index-prev.mem（索引重组）
  ✅ 在 .mem 文件末尾追加"后续关联"注释（append-only）
  ✅ 删除整个 .mem 文件（磁盘清理，非内容修改）

禁止的操作:
  ❌ 修改 .mem 文件中的完整记录区内容
  ❌ 修改 .mem 文件中的结构化摘要内容
  ❌ 回溯修改历史 .mem 的 Prev/Next 指针
  ❌ 覆盖已存在的 .mem 文件

原因:
  1. 记忆是 Agent 的"真相源"，修改历史会破坏推理链
  2. 不同的 LLM 对同一记忆可能有不同解读，保留原文可交叉验证
  3. 记忆进化应该是增量的（新增 > 修改），而非修正式的
```

**固定记忆容量控制**:

```
index.mem 总容量上限: ~2000 字符（~800 tokens）
超出时: 优先级排序 → 低优先级降级到 index-prev.mem
降级标准: 使用频率低、时间衰减严重、不再相关、已被新记忆覆盖
降级原因标记（第三轮新增）:
  - "priority_decay": 优先级自然衰减
  - "invalidation": 被验证性失效标记
  - "rollback": 多次导致任务回滚
  - "capacity_overflow": 容量溢出，被动降级

自动降级阈值（第三轮新增）:
  - 优先级 < 0.1 → 自动降级（相当于被证伪 3 次或回滚 5 次）
  - invalidation_count >= 3 → 强制降级（无论优先级分数）
  - rollback_count >= 5 → 强制降级

index-prev.mem 容量上限: ~2000 字符
再超出: 创建 index-prev-2.mem（更早期）
链式深度无硬限制，但通常 2-3 层足够
```

### 记忆检索方式

| 方式 | 命令 | 场景 |
|------|------|------|
| 链式回溯 | 读取 prev_ses.mem | 需要上一个 session 详情 |
| 关键词搜索 | `rg "JWT" .ai/sessions/*.mem` | 记得关键词，查找历史 |
| 时间定位 | 读取 `20260409-153000.mem` | 知道大概时间 |
| 索引查找 | 读取 index.mem 记忆索引 | 浏览全部可用线索 |
| 固定记忆 | 已在上下文中 | 常用经验无需检索 |
| 索引链回溯 | 读取 index-prev.mem | 需要更早期的固定记忆 |

### 记忆检索抽象接口（P0/P1 渐进）

> **设计意图**: P0 阶段记忆量小（几十个 session），rg 关键词搜索足够。P1 阶段记忆量增长后，引入轻量向量索引提升语义检索效率。通过抽象接口实现渐进升级，不破坏已有代码。

```python
from abc import ABC, abstractmethod

class MemoryRetriever(ABC):
    """记忆检索抽象接口"""
    
    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """搜索记忆，返回最相关的 top_k 条结果
        
        每条结果格式:
        {
            "source": "固定记忆" | "记忆索引" | ".mem文件",
            "file": "index.mem" | "20260409-153000.mem",
            "content": "匹配的内容片段",
            "relevance": 0.0-1.0  # 相关度分数
        }
        """
        pass

class RegexMemoryRetriever(MemoryRetriever):
    """P0: 基于 rg 的关键词检索
    
    实现策略:
    1. 从 query 中提取关键词（去停用词、保留名词/动词）
    2. 用 rg 在 .ai/sessions/*.mem 和 index.mem 中搜索
    3. 按匹配行数和关键词密度排序
    4. 固定记忆区 + index.mem 的匹配权重加倍
    
    补充优化: 在 index.mem 的"核心经验"区增加同义词标签
    示例: "- PyJWT 2.x API 不兼容 | tags: jwt, token, auth, version"
    使得 rg 搜索时即使关键词不完全匹配也能命中
    """
    
    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        keywords = self._extract_keywords(query)
        results = await self._rg_search(keywords)
        return self._rank_and_topk(results, top_k)
    
    def _extract_keywords(self, query: str) -> list[str]:
        """从查询中提取搜索关键词"""
        pass
    
    async def _rg_search(self, keywords: list[str]) -> list[dict]:
        """用 rg 在 .mem 文件中搜索"""
        pass

class VectorMemoryRetriever(MemoryRetriever):
    """P1: 基于向量索引的语义检索（占位，P1 实现）
    
    技术选型:
    - LanceDB: 轻量本地向量数据库，Rust 实现，零服务器依赖
    - 嵌入模型: 本地 small model 或 API 调用
    - 仅对 index.mem 中的"核心经验"做向量化（控制索引大小）
    - .mem 文件的完整记录仍用 rg 检索（文本搜索更快）
    
    混合检索策略:
    1. 向量检索 → 语义相似的固定记忆/经验
    2. rg 检索 → 精确关键词匹配
    3. 融合排序 → 综合两路结果
    """
    
    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        # P1 实现
        pass
```

### 实现文件变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `scripts/memory_manager.py` | 新建 | 记忆管理器（两层 + 进化 + 检索 + 冲突检测） |
| `scripts/memory_conflict_detector.py` | 新建 | 记忆冲突检测器（含 auto_resolve Recency Bias） |
| `scripts/memory_retriever.py` | 新建 | 记忆检索抽象接口（P0: RegexMemoryRetriever, P1: VectorMemoryRetriever 占位） |
| `scripts/memory_detox.py` | 新建 | 记忆排毒引擎（验证性失效 + 负反馈惩罚 + 轻量级冲突扫描） |
| `scripts/consistency_guard.py` | 新建 | 一致性守护（回归警报 + 元诊断 + 强制复读）（第四轮新增） |
| `scripts/role_memory_injector.py` | 新建 | 角色感知记忆注入器（role 字段过滤）（第四轮新增） |
| `scripts/memory_cli.py` | 新建 | CLI 记忆管理子命令（status/audit/prune/override/history/checkpoint/promote） |
| `scripts/index_priority_sorter.py` | 新建 | index.mem 优先级排序器（含负反馈惩罚因子） |
| `scripts/session_manager.py` | 新建 | Session 文件管理（.ses/.log/.mem） |
| `scripts/agent_loop.py` | 修改 | 会话结束时触发记忆保存和进化 |
| `scripts/system_prompt_builder.py` | 修改 | 注入 index.mem + 上一 session 摘要 + 冲突检测 |
| `.ai/sessions/index.mem` | 新建 | 记忆索引文件（链式 Page 1） |

---

## 五、P0-4: 命令批准机制（安全 Layer 2）

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

## 六、P0 整体架构集成

### 数据流全景

```
用户启动 adds start
    │
    ▼
┌─ ModelFactory.select_model() ──────────────────────┐
│  交互式选择: API/CLI + Provider + Model             │
│  → 返回 ModelInterface 实例                         │
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
┌─ Session 初始化 ──────────────────────────────────┐
│  1. 读取 index.mem → 角色感知过滤注入固定记忆+索引线索 │  ← 第四轮改进
│  2. 读取上一个 .mem → 注入结构化摘要 + 链式指针    │
│  3. 检测冲突: SP vs 固定记忆 → 自动以 SP 为准       │
│     用户最新 vs 固定记忆 → Recency Bias 自动解决     │
│     SP vs 用户最新 → 必须暂停确认                    │
│  4. 构建 System Prompt（静态+动态+记忆+摘要+强制复读）│  ← 第四轮改进
│  5. 初始化 TokenBudget(context_window)             │
│  6. 构建代码热度地图(code_heat_map)                 │  ← 第四轮新增
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
┌─ Agent Loop ─────────────────────────────────────┐
│  while True:                                      │
│    ① 上下文预处理                                  │
│       - 检查 TokenBudget                          │
│       - if utilization > 50%: Layer 1 压缩        │
│       - if utilization > 80%: Layer 2 归档 → 新session │
│    ② 路由决策 → 选择 Agent                        │
│    ③ 执行 Agent                                   │
│       - 权限检查 (PermissionManager)               │
│       - 调用模型 (ModelInterface.chat())           │
│       - 工具输出 → 检查阈值 → 保存 .log            │
│    ④ 状态更新（锁存保护）                          │
│    ⑤ 终止判定                                     │
└────────────────────┬───────────────────────────────┘
                     │ Session 结束
                     ▼
┌─ 记忆保存与进化 ──────────────────────────────────┐
│  1. Layer 1 session → 合并 log → 生成 .mem        │
│  2. LLM 生成结构化摘要 → 写入 .mem (APPEND-ONLY)  │
│  3. 回写 .ses 为摘要版 + 链式指针                  │
│  4. 成功 session → 反思协议(角色第一人称) → 升级固定记忆 │  ← 第四轮改进
│  5. 失败 session → 记忆排毒（验证性失效检测）      │
│  6. 回归警报 → ConsistencyGuard 元诊断(三层防御失效) │  ← 第四轮新增
│  7. 低置信度升级 → 强模型复核                       │
│  8. 轻量级冲突扫描 → 发现可疑 → 标记待审           │
│  9. 固定记忆冲突检测 → Recency Bias 自动/人工解决  │
│  10. 容量超限 → 优先级排序(含负反馈+code_heat) → 降级 │  ← 第四轮改进
│  11. 里程碑检测(Git Tag/核心模块重构/连续失败)      │
│  12. 晋升仪式(--promote) → 临时记忆→长期直觉        │  ← 第四轮新增
│  13. 角色感知注入(role字段过滤) → 精准上下文        │  ← 第四轮新增
│  14. 强制复读(invalidation>=2) → SP 顶部警示       │  ← 第四轮新增
│  15. 更新记忆索引                                   │
└──────────────────────────────────────────────────┘
```

### 完整文件目录

```
.ai/
├── feature_list.md              # 功能状态（不变）
├── progress.md                  # 进度日志（不变）
├── architecture.md              # 架构文档（不变）
├── CORE_GUIDELINES.md           # 核心规范（不变）
├── compliance_report.json       # 合规报告（不变）
├── settings.json                # 权限+模型+压缩配置
├── improvement_roadmap.md       # 本文件
│
├── sessions/                    # Session + 记忆文件
│   ├── index.mem                # 记忆索引（线索+固定记忆，Page 1）
│   ├── index-prev.mem           # 记忆索引（降级区，Page 2）
│   ├── 20260409-153000.ses      # Session 文件
│   ├── 20260409-153000-ses1.log # 工具输出 log
│   ├── 20260409-153000-ses2.log # 工具输出 log
│   ├── 20260409-153000.mem      # 记忆归档（摘要+完整记录，APPEND-ONLY）
│   ├── 20260409-160000.ses
│   └── 20260409-160000.mem
│
└── memories/                    # 技能库 + 角色化记忆（P1 物理拆分）
    ├── SKILLS/
    │   └── README.md
    ├── dev/                     # P1: Dev Agent 角色记忆（第四轮规划）
    │   └── index.mem
    ├── architect/               # P1: Architect Agent 角色记忆
    │   └── index.mem
    └── qa/                      # P1: QA Agent 角色记忆
        └── index.mem

scripts/
├── adds.py                      # CLI 主工具（修改：集成模型选择、session 管理）
├── agent_loop.py                # Agent Loop（修改：集成模型、压缩、权限）
├── agents.py                    # 5 个代理实现（不变）
├── compliance_tracker.py        # 合规追踪（不变）
├── system_prompt_builder.py     # 提示词构建（修改：注入记忆+摘要）
│
├── model/                       # 新增：模型调用层
│   ├── __init__.py
│   ├── base.py                  # ModelInterface 抽象基类
│   ├── factory.py               # 交互式模型工厂
│   ├── api_adapter.py           # API 调用适配器
│   ├── cli_adapter.py           # CLI 工具适配器（基于 CLIProfile）
│   ├── sdk_adapter.py           # SDK 适配器（codebuddy-agent-sdk）
│   ├── task_dispatcher.py       # CLI 任务派发器（统一协议）
│   ├── skill_generator.py       # 技能自动生成器（从文档提取）
│   └── providers/
│       ├── __init__.py
│       ├── minimax.py           # MiniMax Provider
│       ├── codebuddy.py         # Codebuddy Provider（CLI+SDK）
│       └── registry.py          # Provider 注册表
│
├── context_compactor.py         # 新增：两层压缩引擎
├── summary_decision_engine.py   # 新增：摘要策略决策引擎
├── token_budget.py              # 新增：Token 预算管理器
├── session_manager.py           # 新增：Session 文件管理
├── memory_manager.py            # 新增：记忆管理器
├── memory_conflict_detector.py  # 新增：记忆冲突检测器（含 auto_resolve）
├── memory_retriever.py          # 新增：记忆检索接口（P0 rg, P1 向量占位）
├── memory_detox.py              # 新增：记忆排毒引擎（失效+惩罚+冲突扫描）
├── consistency_guard.py         # 新增：一致性守护（回归警报+元诊断+强制复读）（第四轮）
├── role_memory_injector.py      # 新增：角色感知记忆注入器（第四轮）
├── memory_cli.py                # 新增：CLI 记忆管理子命令
├── index_priority_sorter.py     # 新增：index.mem 优先级排序器（含负反馈）
├── permission_manager.py        # 新增：权限管理器
└── test_integration.py          # 集成测试（更新）
```

---

## 七、实施路径（P0）

### Phase 1: 模型调用层（第 1 周）

```
Day 1-2:
  - [ ] 实现 ModelInterface 抽象基类 (model/base.py)
  - [ ] 实现 MiniMax Provider 配置 (model/providers/minimax.py)
  - [ ] 实现 Provider 注册表 (model/providers/registry.py)

Day 3-4:
  - [ ] 实现 API 适配器 (model/api_adapter.py)
  - [ ] 实现 CLI 适配器 (model/cli_adapter.py)

Day 5:
  - [ ] 实现交互式模型工厂 (model/factory.py)
  - [ ] 集成到 adds.py start 命令
  - [ ] 测试: API/CLI 两种模式均可用
```

### Phase 2: 压缩 + Session 管理（第 2 周）

```
Day 1-2:
  - [ ] 实现 TokenBudget (token_budget.py)
  - [ ] 实现 SessionManager (session_manager.py)
  - [ ] 定义 .ses / .log / .mem 文件格式

Day 3-4:
  - [ ] 实现 Layer 1 压缩 (context_compactor.py)
  - [ ] 实现 Layer 2 归档 (context_compactor.py)
  - [ ] 集成到 agent_loop.py

Day 5:
  - [ ] 集成到 system_prompt_builder.py（注入上一 session 摘要）
  - [ ] 测试: 完整压缩流程
```

### Phase 3: 记忆系统（第 3 周）

```
Day 1-2:
  - [ ] 实现 MemoryManager (memory_manager.py)
  - [ ] 实现 index.mem 读写
  - [ ] 实现记忆进化逻辑（升级/降级固定记忆）
  - [ ] 实现角色化记忆: role 字段 + RoleAwareMemoryInjector (role_memory_injector.py)  ← 第四轮新增

Day 3-4:
  - [ ] 实现记忆检索（链式回溯 + grep 搜索）
  - [ ] 实现记忆排毒引擎（验证性失效 + 负反馈惩罚 + 轻量级冲突扫描）
  - [ ] 实现反思协议: 角色第一人称反思 prompt 替换旁观评估  ← 第四轮新增
  - [ ] 实现回归警报 + ConsistencyGuard (consistency_guard.py)  ← 第四轮新增
  - [ ] 实现元诊断 _diagnose_defense_failure()  ← 第四轮新增
  - [ ] 集成到 agent_loop.py（会话结束时保存 + 失败时排毒 + 回归警报）

Day 5:
  - [ ] 实现 CLI 记忆管理子命令（adds mem status/audit/prune/override/history/checkpoint/promote）  ← promote 第四轮新增
  - [ ] 实现注意力热点 code_heat (IndexPrioritySorter 第6因子)  ← 第四轮新增
  - [ ] 实现强制复读机制 (SystemPromptBuilder 集成)  ← 第四轮新增
  - [ ] 实现 PermissionManager (permission_manager.py)
  - [ ] 集成到 agent_loop.py
  - [ ] P0 全流程集成测试
```

---

## 八、P1 改进项（概要，待 P0 完成后详细设计）

### 8.1 技能渐进式披露

- Level 0: 技能列表（名称+描述），注入上下文
- Level 1: 技能详情（触发条件+操作步骤），按需加载
- Level 2: 技能参考文件，执行时加载
- 与 MiniMax Skills 生态集成

### 8.2 语义检索升级（VectorMemoryRetriever）

- 当记忆量达到几百个 session、rg 关键词搜索不够用时启动
- 技术选型: LanceDB（轻量本地向量数据库，Rust 实现，零服务器依赖）
- 仅对 index.mem 中的"核心经验"做向量化（控制索引大小）
- .mem 文件的完整记录仍用 rg 检索（文本搜索更快）
- 混合检索策略: 向量检索（语义相似）+ rg 检索（精确匹配）→ 融合排序

### 8.3 语义冲突检测（重量级）

- 当记忆量增长到一定程度，轻量级关键词匹配不够用时启动
- 专员 Agent 扫描: 每次写入新固定记忆时，用 LLM 检查新老记忆是否存在逻辑矛盾
- 触发"记忆审计任务": 人工或高级 Agent 介入，决定保留哪条
- 与 P0 的 LightweightConflictScanner 互补: P0 快筛（零成本），P1 深扫（有成本但精准）

### 8.4 记忆共振: 跨角色二次进化（第四轮新增）

> **核心洞察**: 在多 Agent 并行系统中，不同角色的 Agent 可以通过共享的 `staging.mem` 看到彼此的审计意见，触发"协作习惯的养成"——这就是"记忆共振"。

**设计思路**:

```
记忆共振机制:

任务结束时，各 Agent 的反思结果先写入共享的 staging.mem:

staging.mem
├── Dev Agent 反思: "FFI 调用后需 Box::from_raw"
├── Architect Agent 反思: "FFI 必须封装在 safety-wrapper"
└── QA Agent 反思: "FFI 变更需 valgrind 检查"
         │
         ▼ 二次进化
Dev 看到 Architect 的边界定义:
  → "如果 Architect 说了要封装，我作为 Dev 就不该在业务逻辑里直接调 FFI"
  → 形成协作习惯，写入 Dev 的记忆

Architect 看到 QA 的测试策略:
  → "如果 QA 说必须 valgrind 检查，我在架构评审时应该提前要求"
  → 形成协作意识，写入 Architect 的记忆
```

**实现路径**:

- P0 阶段: 单 Agent 运行，不启用记忆共振
- P1 阶段: 多 Agent 并行设计，引入 `staging.mem` 共享反思
- 实现: session 结束时，各 Agent 反思结果写入共享 staging.mem，记忆升级时允许跨角色"参考"（不是复制）其他角色的反思结论
- 安全: 共享是"参考"而非"复制"——每个 Agent 只写入自己角色的记忆，但可以从其他角色的反思中提取协作性的行为准则

**与角色化记忆的关系**:

```
角色化记忆 (index-{role}.mem) + 记忆共振 (staging.mem):

P0: 单 Agent → role 字段过滤注入 → 无共振
P1: 多 Agent → 物理 index-{role}.mem + staging.mem 共享 → 有共振

共振不等于复制:
  ❌ 不会把 Architect 的架构知识复制到 Dev 的记忆中
  ✅ 会把"协作习惯"写入 Dev 的记忆（如"遵守封装规则"）
  ✅ 协作习惯是角色间的"接口契约"，而非角色内的"知识复用"
```

### 8.5 Agent Loop 韧性增强

- 7 种终止条件 + 5 种继续条件
- PTL 恢复、max_output_tokens 重试
- 错误恢复策略

---

## 九、P2 改进项（概要）

- 执行后端隔离（Docker/SSH/远程沙箱）
- 多平台通信网关
- Fork 子 Agent 路径
- 定时调度系统

---

## 十、知识来源映射

| ADDS 改进项 | Claude Code 对应 | Hermes 对应 |
|-------------|-----------------|-------------|
| 大模型调用层 | 多 Provider 兼容层 | 多模型支持 |
| CLI 任务派发协议 | — | — (ADDS 原创) |
| 技能自动生成 | — | — (ADDS 原创，从文档提取) |
| 摘要策略决策 | — | — (ADDS 原创，TOOL_FILTER/LLM_ANALYZE) |
| 两层压缩 | MicroCompact + API 摘要 | — |
| 链式 Session | — | — (ADDS 原创) |
| .mem 恢复机制 | — | — (ADDS 原创) |
| 无限记忆 | CLAUDE.md 多级注入 | 双文件记忆 |
| 链式 index.mem | — | — (ADDS 原创) |
| 记忆进化 | — | 自进化技能系统 |
| 记忆不可变原则 | — | — (ADDS 原创) |
| 记忆冲突检测 | — | — (ADDS 原创) |
| System Prompt 优先级 | — | — (ADDS 原创) |
| 文本索引检索 | — | FTS5 搜索(改为 grep) |
| 权限控制 | 三级权限(Allow/Ask/Deny) | 命令批准机制 |
| 长时任务 HealthCheck | — | — (ADDS 原创，第三轮新增) |
| progress_hints | — | — (ADDS 原创，第三轮新增) |
| 错误保留原则 (KEEP_FULL) | — | — (ADDS 原创，第三轮新增) |
| 文件快照引用 (file_ref) | — | — (ADDS 原创，第三轮新增) |
| MemoryRetriever 接口 | — | — (ADDS 原创，第三轮新增，P0 rg + P1 向量) |
| 验证性失效 (Failure-Driven Invalidation) | — | — (ADDS 原创，第三轮新增) |
| 负反馈惩罚 (Negative Penalty) | — | — (ADDS 原创，第三轮新增，融入优先级排序) |
| 记忆排毒流程 | — | — (ADDS 原创，第三轮新增) |
| 轻量级冲突扫描 | — | — (ADDS 原创，第三轮新增，P0 关键词级) |
| 里程碑触发机制 | — | — (ADDS 原创，第三轮新增) |
| CLI 记忆管理子命令 | — | — (ADDS 原创，第三轮新增) |
| 记忆快照与对比 | — | — (ADDS 原创，第三轮新增) |
| 记忆 override 机制 | — | — (ADDS 原创，第三轮新增) |
| 角色化记忆 (role 字段 + index-{role}.mem) | — | — (ADDS 原创，第四轮新增) |
| 反思协议 (Reflection Protocol) | — | — (ADDS 原创，第四轮新增，第一人称角色反思) |
| 回归警报 (Regression Alarm) | — | — (ADDS 原创，第四轮新增，ConsistencyGuard) |
| 元诊断 (_diagnose_defense_failure) | — | — (ADDS 原创，第四轮新增，三层防御失效诊断) |
| 强制复读机制 | — | — (ADDS 原创，第四轮新增，invalidation_count >= 2 触发) |
| 注意力热点 (code_heat) | — | — (ADDS 原创，第四轮新增，第6权重因子) |
| 记忆晋升仪式 (--promote) | — | — (ADDS 原创，第四轮新增，临时记忆→长期直觉) |
| 记忆共振 (staging.mem) | — | — (ADDS 原创，第四轮新增，P1 跨角色二次进化) |

---

*最后更新: 2026-04-09 (P0 第四轮讨论：角色化记忆/反思协议/回归警报与元诊断(ConsistencyGuard)/强制复读机制/注意力热点(code_heat)/记忆晋升仪式(--promote)/P1记忆共振)*

# P0-1: 大模型调用层

> 📋 [返回总览](README.md) | [P0-2: 上下文压缩 →](P0-2-context-compaction.md)

---

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


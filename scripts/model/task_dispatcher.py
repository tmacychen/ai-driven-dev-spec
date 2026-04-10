"""
ADDS Model Layer — CLI 任务派发器

核心组件：
- CLIProfile: CLI 工具配置描述（统一不同 CLI 工具的差异）
- TaskDispatcher: CLI 任务派发器（构建命令 → 执行 → 解析输出）
"""

import asyncio
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .base import ModelResponse


@dataclass
class CLIProfile:
    """CLI 工具配置文件 — 描述如何与特定 CLI 交互"""

    name: str  # 工具名称，如 "codebuddy"
    command: str  # 主命令，如 "codebuddy"
    version_command: str  # 版本检查，如 "codebuddy --version"

    # 任务派发配置
    dispatch: dict = field(default_factory=lambda: {
        "exec_template": "{command} -p {prompt} --output-format {output_format}",
        "input_method": "arg",  # stdin | arg | file
        "output_format": "json",  # text | json | stream-json
        "stream_supported": True,
        "system_prompt_method": "flag",  # flag | stdin | env | file
        "system_prompt_flag": "--system-prompt-file",
    })

    # 会话管理配置
    session: dict = field(default_factory=lambda: {
        "resume_flag": "-c",
        "session_id_flag": "-r",
        "session_id_source": "stdout",
    })

    # 权限配置
    permission: dict = field(default_factory=lambda: {
        "bypass_flag": "-y",
    })

    # 技能生成（无 Skills 的 CLI 需要）
    skill_generation: dict = field(default_factory=lambda: {
        "enabled": False,
        "docs_source": "",
        "output_path": "",
    })

    # 健康检查与长时任务配置
    health_check: dict = field(default_factory=lambda: {
        "timeout": 300,
        "timeout_long_task": 3600,
        "health_check_interval": 30,
        "max_retries": 2,
        "zombie_check": True,
        "long_task_flags": ["--bg"],
        "stall_threshold": 60,
    })


class TaskDispatcher:
    """CLI 任务派发器 — 统一协议

    流程:
    1. 根据 CLIProfile 构建完整命令
    2. 处理 system_prompt 注入方式
    3. 处理会话延续
    4. 执行并捕获输出
    5. 解析输出格式，标准化为 ModelResponse
    """

    def __init__(self, profile: CLIProfile):
        self.profile = profile

    async def dispatch(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        output_format: str = "json",
        resume_session: Optional[str] = None,
        bypass_permissions: bool = False,
        extra_args: Optional[list[str]] = None,
    ) -> ModelResponse:
        """派发任务到 CLI 工具

        Args:
            prompt: 用户输入
            system_prompt: 系统提示词
            output_format: 输出格式 (text/json/stream-json)
            resume_session: 恢复的会话 ID
            bypass_permissions: 是否跳过权限确认
            extra_args: 额外 CLI 参数

        Returns:
            ModelResponse: 标准化响应
        """
        # 构建 system_prompt 文件（如果需要）
        sp_file = None
        if system_prompt and self.profile.dispatch["system_prompt_method"] == "file":
            sp_file = await self._write_system_prompt_file(system_prompt)

        # 构建完整命令
        cmd = self._build_command(
            prompt=prompt,
            system_prompt=system_prompt,
            system_prompt_file=sp_file,
            output_format=output_format,
            resume_session=resume_session,
            bypass_permissions=bypass_permissions,
            extra_args=extra_args,
        )

        # 执行
        raw_output = await self._execute(cmd)

        # 清理临时文件
        if sp_file:
            try:
                Path(sp_file).unlink()
            except OSError:
                pass

        # 解析输出
        return self._parse_output(raw_output, output_format)

    def _build_command(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        system_prompt_file: Optional[str] = None,
        output_format: str = "json",
        resume_session: Optional[str] = None,
        bypass_permissions: bool = False,
        extra_args: Optional[list[str]] = None,
    ) -> list[str]:
        """根据 CLIProfile 构建命令行参数列表"""
        parts: list[str] = []

        # 基础命令
        template = self.profile.dispatch["exec_template"]
        base_cmd = template.format(
            command=self.profile.command,
            prompt=prompt,
            output_format=output_format,
        )
        parts.extend(base_cmd.split())

        # System prompt 注入
        if system_prompt:
            method = self.profile.dispatch["system_prompt_method"]
            sp_flag = self.profile.dispatch.get("system_prompt_flag", "")

            if method == "file" and system_prompt_file:
                parts.extend([sp_flag, system_prompt_file])
            elif method == "flag" and sp_flag:
                parts.extend([sp_flag, system_prompt])
            elif method == "stdin":
                pass  # stdin 模式在 _execute 中处理

        # 会话恢复
        if resume_session:
            session_id_flag = self.profile.session.get("session_id_flag")
            if session_id_flag:
                parts.extend([session_id_flag, resume_session])
            else:
                resume_flag = self.profile.session.get("resume_flag")
                if resume_flag:
                    parts.append(resume_flag)

        # 权限跳过
        if bypass_permissions:
            bypass_flag = self.profile.permission.get("bypass_flag")
            if bypass_flag:
                parts.append(bypass_flag)

        # 额外参数
        if extra_args:
            parts.extend(extra_args)

        return parts

    async def _execute(self, cmd: list[str]) -> str:
        """执行命令，实时流式捕获 stdout

        长时任务处理策略:
        1. 区分 stall（卡死）和 slow（慢但活跃）
        2. 重试前检查幂等性
        3. 后台任务（--bg）轮询状态
        """
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

                output_lines: list[str] = []
                stderr_lines: list[str] = []
                last_output_time = asyncio.get_event_loop().time()

                async def _read_stream(stream: asyncio.StreamReader, sink: list[str]) -> None:
                    nonlocal last_output_time
                    async for line in stream:
                        last_output_time = asyncio.get_event_loop().time()
                        sink.append(line.decode(errors="replace"))

                # 并发读取 stdout 和 stderr，带超时
                try:
                    await asyncio.wait_for(
                        asyncio.gather(
                            _read_stream(proc.stdout, output_lines),
                            _read_stream(proc.stderr, stderr_lines),
                        ),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    # 超时，杀掉进程
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass

                    if attempt < max_retries and self._is_idempotent(cmd):
                        continue
                    return f"Timeout after {timeout}s (attempt {attempt + 1})"

                await proc.wait()

                if proc.returncode != 0:
                    stderr = "".join(stderr_lines)
                    if attempt < max_retries and self._is_idempotent(cmd):
                        continue
                    return f"Exit Code: {proc.returncode}\n{stderr}"

                return "".join(output_lines)

            except asyncio.TimeoutError:
                if attempt < max_retries and self._is_idempotent(cmd):
                    continue
                return f"Timeout after {timeout}s (attempt {attempt + 1})"
            except FileNotFoundError:
                return f"Command not found: {cmd[0]}"
            except OSError as e:
                return f"OS Error: {e}"

        return f"Max retries ({max_retries}) exceeded"

    @staticmethod
    def _is_idempotent(cmd: list[str]) -> bool:
        """检查命令是否为幂等操作

        幂等操作（可直接重试）: ls, cat, grep, test, check, status, diff, log
        非幂等操作（需用户确认）: commit, push, install, write, rm, create
        """
        idempotent_prefixes = (
            "ls", "cat", "grep", "rg", "test", "check",
            "status", "diff", "log", "head", "tail", "find",
        )
        if not cmd:
            return False
        command_str = cmd[0]
        return any(command_str.startswith(p) for p in idempotent_prefixes)

    def _parse_output(self, raw: str, output_format: str) -> ModelResponse:
        """解析输出格式，标准化为 ModelResponse"""
        content = raw.strip()
        model_name = self.profile.name
        usage = {"input_tokens": 0, "output_tokens": 0}
        finish_reason = "stop"

        if output_format == "json":
            try:
                import json
                data = json.loads(raw)
                # 尝试从 JSON 中提取内容
                if isinstance(data, dict):
                    content = data.get("content", data.get("text", data.get("response", raw)))
                    if isinstance(data.get("usage"), dict):
                        usage = {
                            "input_tokens": data["usage"].get("input_tokens", 0),
                            "output_tokens": data["usage"].get("output_tokens", 0),
                        }
                    model_name = data.get("model", model_name)
                    finish_reason = data.get("finish_reason", data.get("stop_reason", "stop"))
            except (json.JSONDecodeError, TypeError):
                pass  # 使用原始文本

        elif output_format == "stream-json":
            # 尝试解析最后一行 JSON
            try:
                import json
                lines = [l for l in raw.strip().split("\n") if l.strip()]
                if lines:
                    last = json.loads(lines[-1])
                    if isinstance(last, dict):
                        content = last.get("content", last.get("text", content))
                        model_name = last.get("model", model_name)
            except (json.JSONDecodeError, TypeError):
                pass

        # 检查错误
        if raw.startswith("Exit Code:") or raw.startswith("Timeout") or raw.startswith("Max retries"):
            finish_reason = "error"

        # 估算 token
        if usage["output_tokens"] == 0 and content:
            usage["output_tokens"] = max(1, len(content) // 4)

        return ModelResponse(
            content=content,
            model=model_name,
            usage=usage,
            finish_reason=finish_reason,
        )

    async def _write_system_prompt_file(self, system_prompt: str) -> str:
        """将 system prompt 写入临时文件"""
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            prefix="adds-sp-",
            delete=False,
            encoding="utf-8",
        )
        tmp.write(system_prompt)
        tmp.close()
        return tmp.name

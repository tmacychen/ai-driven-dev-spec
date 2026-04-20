#!/usr/bin/env python3
"""
ADDS 执行后端隔离 (P2-2)

支持多种执行后端：本地 / Docker / SSH，统一接口隔离 Agent 执行环境。

核心组件：
- ExecutionBackend: 抽象基类（统一接口）
- LocalBackend: 本地执行（默认）
- DockerBackend: Docker 容器执行
- SSHBackend: 远程 SSH 执行
- BackendFactory: 后端选择工厂
- ExecutionContext: 执行上下文（命令/环境/文件）
- ExecutionResult: 执行结果（stdout/stderr/exit_code）
"""

import json
import logging
import os
import shlex
import subprocess
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# ExecutionContext — 执行上下文
# ═══════════════════════════════════════════════════════════════

@dataclass
class FileTransfer:
    """文件传输描述"""
    local_path: str       # 本地路径
    remote_path: str      # 远程/容器路径
    direction: str = "upload"  # upload / download

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'FileTransfer':
        return cls(**d)


@dataclass
class ResourceLimits:
    """资源限制"""
    cpu_limit: Optional[str] = None      # CPU 限制（如 "1.0" = 1 核）
    memory_limit: Optional[str] = None    # 内存限制（如 "512m"）
    timeout: int = 600                    # 超时时间（秒）
    network_access: bool = True           # 是否允许网络访问
    max_file_size: Optional[str] = None   # 最大文件大小

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'ResourceLimits':
        return cls(**d)

    def to_docker_args(self) -> List[str]:
        """转换为 Docker 资源限制参数"""
        args = []
        if self.cpu_limit:
            args.extend(["--cpus", self.cpu_limit])
        if self.memory_limit:
            args.extend(["-m", self.memory_limit])
        if not self.network_access:
            args.append("--network=none")
        return args


@dataclass
class ExecutionContext:
    """执行上下文

    包含执行命令所需的所有信息：
    - 命令和环境变量
    - 工作目录
    - 文件传输列表
    - 资源限制
    """
    command: str                                    # 要执行的命令
    work_dir: str = "."                             # 工作目录
    env: Dict[str, str] = field(default_factory=dict)  # 环境变量
    files: List[FileTransfer] = field(default_factory=list)  # 文件传输
    resource_limits: Dict[str, Any] = field(default_factory=dict)  # 资源限制
    stdin: str = ""                                 # 标准输入
    tags: List[str] = field(default_factory=list)   # 标签

    def get_resource_limits(self) -> ResourceLimits:
        """获取资源限制对象"""
        if isinstance(self.resource_limits, dict):
            return ResourceLimits.from_dict(self.resource_limits)
        return self.resource_limits or ResourceLimits()

    def get_env_with_defaults(self) -> Dict[str, str]:
        """获取合并了系统环境变量的环境"""
        env = os.environ.copy()
        env.update(self.env)
        return env

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> 'ExecutionContext':
        if 'files' in d and isinstance(d['files'], list):
            d['files'] = [FileTransfer.from_dict(f) if isinstance(f, dict) else f for f in d['files']]
        return cls(**d)


# ═══════════════════════════════════════════════════════════════
# ExecutionResult — 执行结果
# ═══════════════════════════════════════════════════════════════

class ExecutionStatus(str, Enum):
    """执行状态"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class ExecutionResult:
    """执行结果"""
    status: str = "success"             # ExecutionStatus
    exit_code: int = 0                  # 退出码
    stdout: str = ""                    # 标准输出
    stderr: str = ""                    # 标准错误
    duration: float = 0.0               # 执行时长（秒）
    backend: str = "local"              # 执行后端名称
    container_id: Optional[str] = None  # Docker 容器 ID
    host: Optional[str] = None          # SSH 主机
    started_at: str = ""                # 开始时间
    finished_at: str = ""               # 结束时间
    error: str = ""                     # 错误信息

    @property
    def success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'ExecutionResult':
        return cls(**d)

    def summary(self, max_output: int = 200) -> str:
        """生成执行结果摘要"""
        stdout_summary = self.stdout[:max_output]
        if len(self.stdout) > max_output:
            stdout_summary += "..."
        parts = [
            f"status={self.status.value if isinstance(self.status, ExecutionStatus) else self.status}",
            f"exit={self.exit_code}",
            f"duration={self.duration:.2f}s",
            f"backend={self.backend}",
        ]
        if stdout_summary.strip():
            parts.append(f"output={stdout_summary.strip()}")
        if self.stderr.strip():
            parts.append(f"error={self.stderr[:100].strip()}")
        return " | ".join(parts)


# ═══════════════════════════════════════════════════════════════
# ExecutionBackend — 抽象基类
# ═══════════════════════════════════════════════════════════════

class ExecutionBackend(ABC):
    """执行后端抽象基类

    所有执行后端必须实现 execute() 方法。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """后端名称"""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """后端是否可用"""
        ...

    @abstractmethod
    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """执行命令

        Args:
            context: 执行上下文

        Returns:
            ExecutionResult 执行结果
        """
        ...

    def validate(self) -> Tuple[bool, str]:
        """验证后端配置是否正确

        Returns:
            (is_valid, message)
        """
        if not self.is_available:
            return False, f"Backend '{self.name}' is not available"
        return True, "OK"

    def health_check(self) -> Tuple[bool, str]:
        """健康检查

        Returns:
            (is_healthy, message)
        """
        try:
            context = ExecutionContext(command="echo health_check", tags=["health-check"])
            result = self.execute(context)
            if result.success and "health_check" in result.stdout:
                return True, f"Backend '{self.name}' is healthy"
            return False, f"Backend '{self.name}' health check failed: {result.summary()}"
        except Exception as e:
            return False, f"Backend '{self.name}' health check error: {e}"


# ═══════════════════════════════════════════════════════════════
# LocalBackend — 本地执行
# ═══════════════════════════════════════════════════════════════

class LocalBackend(ExecutionBackend):
    """本地执行后端

    直接在本地 shell 中执行命令。
    """

    def __init__(self, project_root: str = "."):
        self.project_root = project_root

    @property
    def name(self) -> str:
        return "local"

    @property
    def is_available(self) -> bool:
        return True  # 本地执行始终可用

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """在本地执行命令"""
        limits = context.get_resource_limits()
        env = context.get_env_with_defaults()
        started_at = datetime.now().isoformat()
        start_time = time.time()

        try:
            result = subprocess.run(
                context.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=limits.timeout,
                cwd=context.work_dir or self.project_root,
                env=env,
                input=context.stdin or None,
            )

            duration = time.time() - start_time
            status = ExecutionStatus.SUCCESS if result.returncode == 0 else ExecutionStatus.FAILED

            return ExecutionResult(
                status=status,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration,
                backend=self.name,
                started_at=started_at,
                finished_at=datetime.now().isoformat(),
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                exit_code=-1,
                stderr=f"Command timed out after {limits.timeout}s",
                duration=duration,
                backend=self.name,
                started_at=started_at,
                finished_at=datetime.now().isoformat(),
            )

        except Exception as e:
            duration = time.time() - start_time
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                exit_code=-1,
                error=str(e),
                duration=duration,
                backend=self.name,
                started_at=started_at,
                finished_at=datetime.now().isoformat(),
            )


# ═══════════════════════════════════════════════════════════════
# DockerBackend — Docker 容器执行
# ═══════════════════════════════════════════════════════════════

class DockerBackend(ExecutionBackend):
    """Docker 容器执行后端

    在 Docker 容器中隔离执行命令。
    """

    def __init__(self, project_root: str = ".",
                 image: str = "python:3.11-slim",
                 docker_path: str = "docker"):
        self.project_root = project_root
        self.image = image
        self.docker_path = docker_path

    @property
    def name(self) -> str:
        return "docker"

    @property
    def is_available(self) -> bool:
        """检查 Docker 是否可用"""
        try:
            result = subprocess.run(
                [self.docker_path, "version"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """在 Docker 容器中执行命令"""
        limits = context.get_resource_limits()
        started_at = datetime.now().isoformat()
        start_time = time.time()

        # 构建 docker run 命令
        docker_args = [
            self.docker_path, "run", "--rm",
        ]

        # 资源限制
        docker_args.extend(limits.to_docker_args())

        # 超时（通过 Docker 的 --stop-timeout 间接实现）
        # 注意：Docker 没有直接的执行超时，我们使用 subprocess timeout

        # 挂载工作目录
        work_dir = context.work_dir or self.project_root
        abs_work_dir = os.path.abspath(work_dir)
        docker_args.extend(["-v", f"{abs_work_dir}:/workspace"])
        docker_args.extend(["-w", "/workspace"])

        # 环境变量
        for key, value in context.env.items():
            docker_args.extend(["-e", f"{key}={value}"])

        # 文件挂载
        for file_transfer in context.files:
            abs_local = os.path.abspath(file_transfer.local_path)
            if file_transfer.direction == "upload":
                docker_args.extend(["-v", f"{abs_local}:{file_transfer.remote_path}"])

        # 镜像和命令
        docker_args.append(self.image)
        docker_args.extend(["sh", "-c", context.command])

        try:
            result = subprocess.run(
                docker_args,
                capture_output=True,
                text=True,
                timeout=limits.timeout,
                input=context.stdin or None,
            )

            duration = time.time() - start_time
            status = ExecutionStatus.SUCCESS if result.returncode == 0 else ExecutionStatus.FAILED

            return ExecutionResult(
                status=status,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration,
                backend=self.name,
                started_at=started_at,
                finished_at=datetime.now().isoformat(),
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                exit_code=-1,
                stderr=f"Docker command timed out after {limits.timeout}s",
                duration=duration,
                backend=self.name,
                started_at=started_at,
                finished_at=datetime.now().isoformat(),
            )

        except FileNotFoundError:
            duration = time.time() - start_time
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                exit_code=-1,
                error=f"Docker not found: {self.docker_path}",
                duration=duration,
                backend=self.name,
                started_at=started_at,
                finished_at=datetime.now().isoformat(),
            )

        except Exception as e:
            duration = time.time() - start_time
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                exit_code=-1,
                error=str(e),
                duration=duration,
                backend=self.name,
                started_at=started_at,
                finished_at=datetime.now().isoformat(),
            )

    def list_images(self) -> List[str]:
        """列出本地 Docker 镜像"""
        try:
            result = subprocess.run(
                [self.docker_path, "images", "--format", "{{.Repository}}:{{.Tag}}"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return [img for img in result.stdout.strip().split('\n') if img]
            return []
        except Exception:
            return []

    def pull_image(self, image: Optional[str] = None) -> bool:
        """拉取 Docker 镜像"""
        img = image or self.image
        try:
            result = subprocess.run(
                [self.docker_path, "pull", img],
                capture_output=True, text=True, timeout=300,
            )
            return result.returncode == 0
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════
# SSHBackend — 远程 SSH 执行
# ═══════════════════════════════════════════════════════════════

@dataclass
class SSHConfig:
    """SSH 连接配置"""
    host: str = ""
    port: int = 22
    user: str = ""
    key_path: str = ""      # SSH 私钥路径
    password: str = ""       # 密码（不推荐，优先用 key）
    ssh_path: str = "ssh"    # ssh 命令路径

    def to_dict(self) -> dict:
        # 不序列化密码
        d = asdict(self)
        d['password'] = '***' if self.password else ''
        return d

    @classmethod
    def from_dict(cls, d: dict) -> 'SSHConfig':
        # 保留密码
        return cls(**d)

    def to_ssh_args(self) -> List[str]:
        """生成 SSH 命令参数"""
        args = [self.ssh_path]

        if self.port != 22:
            args.extend(["-p", str(self.port)])

        if self.key_path:
            args.extend(["-i", os.path.expanduser(self.key_path)])

        # 严格主机密钥检查（自动化场景用 no）
        args.extend(["-o", "StrictHostKeyChecking=no"])
        args.extend(["-o", "ConnectTimeout=10"])

        # 拼接 user@host
        target = f"{self.user}@{self.host}" if self.user else self.host
        args.append(target)

        return args


class SSHBackend(ExecutionBackend):
    """SSH 远程执行后端

    通过 SSH 在远程主机上执行命令。
    """

    def __init__(self, project_root: str = ".", config: Optional[SSHConfig] = None):
        self.project_root = project_root
        self.config = config or SSHConfig()

    @property
    def name(self) -> str:
        return "ssh"

    @property
    def is_available(self) -> bool:
        """检查 SSH 是否可用"""
        if not self.config.host:
            return False
        try:
            result = subprocess.run(
                ["which", self.config.ssh_path],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """在远程 SSH 主机上执行命令"""
        limits = context.get_resource_limits()
        started_at = datetime.now().isoformat()
        start_time = time.time()

        # 构建 SSH 命令
        ssh_args = self.config.to_ssh_args()

        # 添加环境变量（通过 env 前缀）
        env_prefix = ""
        if context.env:
            env_parts = [f"{k}={shlex.quote(v)}" for k, v in context.env.items()]
            env_prefix = " ".join(env_parts) + " "

        # 远程命令
        remote_cmd = f"cd {shlex.quote(context.work_dir)} 2>/dev/null; {env_prefix}{context.command}"
        ssh_args.append(remote_cmd)

        try:
            result = subprocess.run(
                ssh_args,
                capture_output=True,
                text=True,
                timeout=limits.timeout,
                input=context.stdin or None,
            )

            duration = time.time() - start_time
            status = ExecutionStatus.SUCCESS if result.returncode == 0 else ExecutionStatus.FAILED

            return ExecutionResult(
                status=status,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration,
                backend=self.name,
                host=self.config.host,
                started_at=started_at,
                finished_at=datetime.now().isoformat(),
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                exit_code=-1,
                stderr=f"SSH command timed out after {limits.timeout}s",
                duration=duration,
                backend=self.name,
                host=self.config.host,
                started_at=started_at,
                finished_at=datetime.now().isoformat(),
            )

        except Exception as e:
            duration = time.time() - start_time
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                exit_code=-1,
                error=str(e),
                duration=duration,
                backend=self.name,
                host=self.config.host,
                started_at=started_at,
                finished_at=datetime.now().isoformat(),
            )

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """上传文件到远程主机"""
        try:
            scp_args = ["scp"]
            if self.config.key_path:
                scp_args.extend(["-i", os.path.expanduser(self.config.key_path)])
            if self.config.port != 22:
                scp_args.extend(["-P", str(self.config.port)])

            target = f"{self.config.user}@{self.config.host}" if self.config.user else self.config.host
            scp_args.extend([local_path, f"{target}:{remote_path}"])

            result = subprocess.run(scp_args, capture_output=True, text=True, timeout=60)
            return result.returncode == 0
        except Exception:
            return False

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """从远程主机下载文件"""
        try:
            scp_args = ["scp"]
            if self.config.key_path:
                scp_args.extend(["-i", os.path.expanduser(self.config.key_path)])
            if self.config.port != 22:
                scp_args.extend(["-P", str(self.config.port)])

            target = f"{self.config.user}@{self.config.host}" if self.config.user else self.config.host
            scp_args.extend([f"{target}:{remote_path}", local_path])

            result = subprocess.run(scp_args, capture_output=True, text=True, timeout=60)
            return result.returncode == 0
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════
# BackendFactory — 后端选择工厂
# ═══════════════════════════════════════════════════════════════

class BackendFactory:
    """执行后端工厂

    根据配置选择合适的执行后端。
    """

    _registry: Dict[str, type] = {
        "local": LocalBackend,
        "docker": DockerBackend,
        "ssh": SSHBackend,
    }

    @classmethod
    def register(cls, name: str, backend_class: type):
        """注册自定义后端"""
        cls._registry[name] = backend_class

    @classmethod
    def create(cls, backend_name: str = "local",
               project_root: str = ".",
               **kwargs) -> ExecutionBackend:
        """创建执行后端实例

        Args:
            backend_name: 后端名称
            project_root: 项目根目录
            **kwargs: 后端特定参数

        Returns:
            ExecutionBackend 实例
        """
        if backend_name not in cls._registry:
            raise ValueError(
                f"Unknown backend: {backend_name}. "
                f"Available: {list(cls._registry.keys())}"
            )

        backend_class = cls._registry[backend_name]

        # 根据后端类型传递参数
        if backend_name == "docker":
            return backend_class(
                project_root=project_root,
                image=kwargs.get("image", "python:3.11-slim"),
                docker_path=kwargs.get("docker_path", "docker"),
            )
        elif backend_name == "ssh":
            config = kwargs.get("config") or SSHConfig(
                host=kwargs.get("host", ""),
                port=kwargs.get("port", 22),
                user=kwargs.get("user", ""),
                key_path=kwargs.get("key_path", ""),
            )
            return backend_class(project_root=project_root, config=config)
        else:
            return backend_class(project_root=project_root)

    @classmethod
    def list_backends(cls) -> List[str]:
        """列出所有已注册的后端"""
        return list(cls._registry.keys())

    @classmethod
    def detect_available(cls, project_root: str = ".") -> Dict[str, bool]:
        """检测可用的后端"""
        available = {}
        for name in cls._registry:
            try:
                backend = cls.create(name, project_root=project_root)
                available[name] = backend.is_available
            except Exception:
                available[name] = False
        return available


# ═══════════════════════════════════════════════════════════════
# 安全策略
# ═══════════════════════════════════════════════════════════════

class SandboxPolicy:
    """安全沙箱策略

    定义哪些操作在沙箱中允许/禁止。
    """

    # 危险命令模式
    DANGEROUS_PATTERNS = [
        r'\brm\s+-rf\s+/',
        r'\bmk' + 'fs\b',
        r'\bfd' + 'isk\b',
        r'\bdd\s+if=',
        r'\bformat\b',
        r'>\s*/dev/sd',
        r'\bchmod\s+777',
        r'\bchown\s+root',
        r'\bip' + 'tables\b',
        r'\broute\s+add',
    ]

    # 高风险命令（需要确认）
    HIGH_RISK_PATTERNS = [
        r'\bsudo\b',
        r'\bsu\s+',
        r'\binstall\b',
        r'\bpip\s+install',
        r'\bnpm\s+install',
        r'\bgit\s+push\s+--force',
        r'\bgit\s+reset\s+--hard',
    ]

    @classmethod
    def check_command(cls, command: str) -> Tuple[str, str]:
        """检查命令安全性

        Returns:
            (level, message) — level: safe/dangerous/high_risk
        """
        import re

        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return "dangerous", f"Dangerous command detected: matches '{pattern}'"

        for pattern in cls.HIGH_RISK_PATTERNS:
            if re.search(pattern, command):
                return "high_risk", f"High-risk command detected: matches '{pattern}'"

        return "safe", "Command is safe"

    @classmethod
    def get_default_limits(cls) -> ResourceLimits:
        """获取默认沙箱资源限制"""
        return ResourceLimits(
            cpu_limit="1.0",
            memory_limit="512m",
            timeout=600,
            network_access=True,
        )

    @classmethod
    def get_strict_limits(cls) -> ResourceLimits:
        """获取严格沙箱资源限制"""
        return ResourceLimits(
            cpu_limit="0.5",
            memory_limit="256m",
            timeout=300,
            network_access=False,
        )


# ═══════════════════════════════════════════════════════════════
# ExecutionManager — 统一执行管理
# ═══════════════════════════════════════════════════════════════

class ExecutionManager:
    """统一执行管理器

    提供执行后端的统一入口，集成安全策略和权限检查。
    """

    def __init__(self, project_root: str = ".", backend_name: str = "local", **kwargs):
        self.project_root = project_root
        self.backend = BackendFactory.create(backend_name, project_root=project_root, **kwargs)
        self._default_backend_name = backend_name

    def execute(self, command: str, work_dir: str = ".",
                env: Optional[Dict[str, str]] = None,
                backend: Optional[str] = None,
                check_safety: bool = True,
                **kwargs) -> ExecutionResult:
        """执行命令

        Args:
            command: 要执行的命令
            work_dir: 工作目录
            env: 环境变量
            backend: 临时使用不同的后端
            check_safety: 是否检查安全性
            **kwargs: 传递给 ExecutionContext 的参数

        Returns:
            ExecutionResult
        """
        # 安全检查
        if check_safety:
            level, message = SandboxPolicy.check_command(command)
            if level == "dangerous":
                return ExecutionResult(
                    status=ExecutionStatus.ERROR,
                    exit_code=-1,
                    error=f"Command blocked by sandbox policy: {message}",
                    backend=self.backend.name,
                )

        # 构建执行上下文
        context = ExecutionContext(
            command=command,
            work_dir=work_dir or self.project_root,
            env=env or {},
            **kwargs,
        )

        # 选择后端
        executor = self.backend
        if backend and backend != self._default_backend_name:
            executor = BackendFactory.create(backend, project_root=self.project_root)

        # 执行
        return executor.execute(context)

    def switch_backend(self, backend_name: str, **kwargs):
        """切换执行后端"""
        self.backend = BackendFactory.create(backend_name, project_root=self.project_root, **kwargs)
        self._default_backend_name = backend_name

    def get_available_backends(self) -> Dict[str, bool]:
        """获取可用后端列表"""
        return BackendFactory.detect_available(self.project_root)

    def health_check(self) -> Dict[str, Tuple[bool, str]]:
        """对所有可用后端做健康检查"""
        results = {}
        for name in BackendFactory.list_backends():
            try:
                backend = BackendFactory.create(name, project_root=self.project_root)
                if backend.is_available:
                    results[name] = backend.health_check()
                else:
                    results[name] = (False, "Not available")
            except Exception as e:
                results[name] = (False, str(e))
        return results


# ═══════════════════════════════════════════════════════════════
# CLI 子命令
# ═══════════════════════════════════════════════════════════════

def add_executor_subparser(subparsers):
    """添加 executor 子命令到 argparse"""
    exec_parser = subparsers.add_parser(
        "executor", help="执行后端管理（P2-2）",
    )
    exec_sub = exec_parser.add_subparsers(dest="executor_command")

    # list
    exec_sub.add_parser("list", help="列出可用后端")

    # run
    run_parser = exec_sub.add_parser("run", help="执行命令")
    run_parser.add_argument("command", type=str, help="要执行的命令")
    run_parser.add_argument("--backend", type=str, default="local",
                            choices=["local", "docker", "ssh"],
                            help="执行后端")
    run_parser.add_argument("--work-dir", type=str, default=".", help="工作目录")
    run_parser.add_argument("--env", type=str, action="append",
                            help="环境变量 (KEY=VALUE)")
    run_parser.add_argument("--timeout", type=int, default=600, help="超时时间（秒）")
    run_parser.add_argument("--no-safety-check", action="store_true",
                            help="跳过安全检查（危险）")

    # docker 特定
    run_parser.add_argument("--image", type=str, default="python:3.11-slim",
                            help="Docker 镜像")

    # ssh 特定
    run_parser.add_argument("--host", type=str, help="SSH 主机")
    run_parser.add_argument("--user", type=str, help="SSH 用户")
    run_parser.add_argument("--key", type=str, help="SSH 私钥路径")
    run_parser.add_argument("--port", type=int, default=22, help="SSH 端口")

    # health
    exec_sub.add_parser("health", help="后端健康检查")

    # check
    check_parser = exec_sub.add_parser("check", help="检查命令安全性")
    check_parser.add_argument("command", type=str, help="要检查的命令")


def handle_executor_command(args, project_root: str = "."):
    """处理 executor 子命令"""
    cmd = getattr(args, 'executor_command', None)
    if not cmd:
        print("⚠️  请指定子命令。使用 adds executor --help 查看帮助。")
        return

    if cmd == "list":
        _cmd_executor_list(project_root)
    elif cmd == "run":
        _cmd_executor_run(args, project_root)
    elif cmd == "health":
        _cmd_executor_health(project_root)
    elif cmd == "check":
        _cmd_executor_check(args)
    else:
        print(f"❌ 未知子命令: {cmd}")


def _cmd_executor_list(project_root: str):
    """列出可用后端"""
    available = BackendFactory.detect_available(project_root)
    print("=" * 50)
    print("🖥️  执行后端")
    print("=" * 50)
    for name, is_avail in available.items():
        icon = "✅" if is_avail else "❌"
        desc = {
            "local": "本地执行（默认）",
            "docker": "Docker 容器隔离执行",
            "ssh": "远程 SSH 执行",
        }.get(name, "")
        print(f"  {icon} {name:10s} — {desc}")
    print()


def _cmd_executor_run(args, project_root: str):
    """执行命令"""
    # 解析环境变量
    env = {}
    if args.env:
        for e in args.env:
            if '=' in e:
                k, v = e.split('=', 1)
                env[k] = v

    # 构建后端参数
    kwargs = {}
    if args.backend == "docker":
        kwargs['image'] = args.image
    elif args.backend == "ssh":
        from executor_backend import SSHConfig
        kwargs['config'] = SSHConfig(
            host=args.host or "",
            user=args.user or "",
            key_path=args.key or "",
            port=args.port,
        )

    mgr = ExecutionManager(
        project_root=project_root,
        backend_name=args.backend,
        **kwargs,
    )

    # 更新资源限制
    result = mgr.execute(
        command=args.command,
        work_dir=args.work_dir,
        env=env,
        check_safety=not args.no_safety_check,
        resource_limits={"timeout": args.timeout},
    )

    # 输出结果
    if result.success:
        print(f"✅ 执行成功 (exit={result.exit_code}, {result.duration:.2f}s)")
        if result.stdout:
            print(result.stdout)
    else:
        print(f"❌ 执行失败: {result.status} (exit={result.exit_code})")
        if result.stderr:
            print(f"stderr: {result.stderr}")
        if result.error:
            print(f"error: {result.error}")


def _cmd_executor_health(project_root: str):
    """后端健康检查"""
    mgr = ExecutionManager(project_root=project_root)
    results = mgr.health_check()

    print("=" * 50)
    print("🏥 后端健康检查")
    print("=" * 50)

    for name, (is_healthy, message) in results.items():
        icon = "✅" if is_healthy else "❌"
        print(f"  {icon} {name}: {message}")
    print()


def _cmd_executor_check(args):
    """检查命令安全性"""
    level, message = SandboxPolicy.check_command(args.command)
    icons = {"safe": "✅", "high_risk": "⚠️", "dangerous": "🚫"}
    print(f"{icons.get(level, '❓')} [{level}] {message}")


# ═══════════════════════════════════════════════════════════════
# 内置测试
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from log_config import configure_standalone_logging
    configure_standalone_logging()

    print("=== LocalBackend 测试 ===")
    local = LocalBackend()
    ctx = ExecutionContext(command="echo hello from local")
    result = local.execute(ctx)
    print(f"  Result: {result.summary()}")
    print(f"  Available: {local.is_available}")

    print("\n=== DockerBackend 测试 ===")
    docker = DockerBackend()
    print(f"  Available: {docker.is_available}")

    print("\n=== BackendFactory 测试 ===")
    print(f"  Registered: {BackendFactory.list_backends()}")
    print(f"  Available: {BackendFactory.detect_available('.')}")

    print("\n=== SandboxPolicy 测试 ===")
    tests = [
        "echo hello",
        "sudo apt update",
        "pip install requests",
        "ls -la",
    ]
    for cmd in tests:
        level, msg = SandboxPolicy.check_command(cmd)
        print(f"  [{level}] {cmd}: {msg}")

    print("\n=== ExecutionManager 测试 ===")
    mgr = ExecutionManager(project_root=".", backend_name="local")
    result = mgr.execute("echo managed execution")
    print(f"  Result: {result.summary()}")

    # 安全检查（dangerous 级别会被阻止）
    result = mgr.execute("dd if=/dev/zero of=/dev/sda", check_safety=True)
    print(f"  Blocked: {result.status}, error: {result.error}")

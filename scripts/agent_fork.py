#!/usr/bin/env python3
"""
ADDS Fork 子 Agent 路径 (P2-4)

子 Agent 派生与管理，支持并行执行和结果汇聚。

核心组件：
- AgentFork: 子 Agent 派生器
- ForkContext: 上下文传递
- ForkResult: 子 Agent 执行结果
- ForkPool: 子 Agent 线程池
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# ForkContext — 上下文传递
# ═══════════════════════════════════════════════════════════════

@dataclass
class ForkContext:
    """子 Agent 上下文

    从父 Agent 继承的上下文信息：
    - 系统提示词
    - 记忆（角色化过滤后）
    - 权限配置
    - 项目根目录
    """
    parent_session_id: str = ""           # 父 session ID
    system_prompt: str = ""               # 继承的系统提示词
    role: str = ""                        # 子 Agent 角色
    feature: str = ""                     # 子 Agent 负责的功能
    project_root: str = "."               # 项目根目录
    permission_mode: str = "default"      # 权限模式
    memory_filter: str = ""               # 记忆过滤条件（role/module/tag）
    max_turns: int = 5                    # 最大对话轮数
    timeout: int = 300                    # 超时时间（秒）
    inherit_memory: bool = True           # 是否继承记忆
    inherit_skills: bool = True           # 是否继承技能
    task_prompt: str = ""                 # 任务提示词
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'ForkContext':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ═══════════════════════════════════════════════════════════════
# ForkResult — 子 Agent 执行结果
# ═══════════════════════════════════════════════════════════════

class ForkStatus(str, Enum):
    """子 Agent 状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ForkResult:
    """子 Agent 执行结果"""
    fork_id: str = ""                     # 子 Agent ID
    role: str = ""                        # 角色
    feature: str = ""                     # 功能
    status: str = "pending"               # ForkStatus
    output: str = ""                      # 输出摘要
    error: str = ""                       # 错误信息
    exit_code: int = 0                    # 退出码
    duration: float = 0.0                 # 执行时长
    turns: int = 0                        # 对话轮数
    session_id: str = ""                  # Session ID
    started_at: str = ""                  # 开始时间
    finished_at: Optional[str] = None     # 结束时间
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == ForkStatus.COMPLETED

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'ForkResult':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def summary(self) -> str:
        return (
            f"[{self.role}] {self.feature or 'unnamed'}: "
            f"{self.status} ({self.duration:.1f}s, {self.turns} turns)"
        )


# ═══════════════════════════════════════════════════════════════
# AgentFork — 子 Agent 派生器
# ═══════════════════════════════════════════════════════════════

class AgentFork:
    """子 Agent 派生器

    通过子进程方式启动独立的 Agent Loop 实例。
    每个子 Agent 拥有独立的 session、记忆和预算。
    """

    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        self._forks: Dict[str, ForkResult] = {}

    def create_fork_id(self) -> str:
        """生成唯一 fork ID"""
        return f"fork-{uuid.uuid4().hex[:8]}"

    def fork(self, context: ForkContext) -> ForkResult:
        """派生子 Agent

        Args:
            context: 子 Agent 上下文

        Returns:
            ForkResult 执行结果
        """
        fork_id = self.create_fork_id()
        result = ForkResult(
            fork_id=fork_id,
            role=context.role,
            feature=context.feature,
            status=ForkStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )
        self._forks[fork_id] = result

        start_time = time.time()

        try:
            # 构建命令
            cmd = self._build_command(context)

            # 执行子进程
            process_result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=context.timeout,
                cwd=context.project_root or self.project_root,
                input=context.task_prompt or None,
            )

            duration = time.time() - start_time
            result.duration = duration
            result.exit_code = process_result.returncode
            result.output = process_result.stdout[:500] if process_result.stdout else ""
            result.error = process_result.stderr[:500] if process_result.stderr else ""

            if process_result.returncode == 0:
                result.status = ForkStatus.COMPLETED
            else:
                result.status = ForkStatus.FAILED

        except subprocess.TimeoutExpired:
            result.status = ForkStatus.TIMEOUT
            result.duration = time.time() - start_time
            result.error = f"Fork timed out after {context.timeout}s"

        except Exception as e:
            result.status = ForkStatus.FAILED
            result.duration = time.time() - start_time
            result.error = str(e)

        result.finished_at = datetime.now().isoformat()
        self._forks[fork_id] = result
        return result

    def _build_command(self, context: ForkContext) -> List[str]:
        """构建子 Agent 启动命令"""
        cmd = [
            sys.executable,
            str(Path(__file__).parent / "adds.py"),
            "start",
            "--non-interactive",
        ]

        # 角色
        role = context.role or "developer"
        cmd.extend(["--role", role])

        # 权限模式
        if context.permission_mode:
            cmd.extend(["--perm", context.permission_mode])

        return cmd

    def cancel(self, fork_id: str) -> bool:
        """取消子 Agent（标记为 cancelled）"""
        if fork_id in self._forks:
            self._forks[fork_id].status = ForkStatus.CANCELLED
            return True
        return False

    def get_result(self, fork_id: str) -> Optional[ForkResult]:
        """获取子 Agent 结果"""
        return self._forks.get(fork_id)

    def list_forks(self, status: Optional[str] = None) -> List[ForkResult]:
        """列出所有子 Agent"""
        forks = list(self._forks.values())
        if status:
            forks = [f for f in forks if f.status == status]
        return sorted(forks, key=lambda f: f.started_at)

    def get_stats(self) -> Dict[str, Any]:
        """获取 fork 统计"""
        total = len(self._forks)
        status_counts = {}
        for f in self._forks.values():
            status_counts[f.status] = status_counts.get(f.status, 0) + 1
        return {
            'total_forks': total,
            'status_counts': status_counts,
        }


# ═══════════════════════════════════════════════════════════════
# ForkPool — 子 Agent 线程池
# ═══════════════════════════════════════════════════════════════

class ForkPool:
    """子 Agent 线程池

    管理多个子 Agent 的并行执行：
    - 最大并发数限制
    - 结果汇聚
    - 资源隔离
    """

    def __init__(self, project_root: str = ".",
                 max_workers: int = 3):
        self.project_root = project_root
        self.max_workers = max_workers
        self._fork = AgentFork(project_root=project_root)
        self._results: List[ForkResult] = []

    def execute(self, contexts: List[ForkContext]) -> List[ForkResult]:
        """并行执行多个子 Agent

        Args:
            contexts: 子 Agent 上下文列表

        Returns:
            执行结果列表
        """
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_context = {
                executor.submit(self._fork.fork, ctx): ctx
                for ctx in contexts
            }

            # 收集结果
            for future in as_completed(future_to_context):
                ctx = future_to_context[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    # 创建失败结果
                    result = ForkResult(
                        fork_id=self._fork.create_fork_id(),
                        role=ctx.role,
                        feature=ctx.feature,
                        status=ForkStatus.FAILED,
                        error=str(e),
                    )
                    results.append(result)

        self._results.extend(results)
        return results

    def execute_sequential(self, contexts: List[ForkContext]) -> List[ForkResult]:
        """顺序执行多个子 Agent（用于调试）"""
        results = []
        for ctx in contexts:
            result = self._fork.fork(ctx)
            results.append(result)
        self._results.extend(results)
        return results

    def merge_results(self, results: Optional[List[ForkResult]] = None) -> Dict[str, Any]:
        """汇聚多个子 Agent 的结果

        Args:
            results: 要汇聚的结果列表（默认使用所有结果）

        Returns:
            汇聚报告
        """
        if results is None:
            results = self._results

        total = len(results)
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        total_duration = sum(r.duration for r in results)
        total_turns = sum(r.turns for r in results)

        # 按角色分组
        by_role = {}
        for r in results:
            by_role.setdefault(r.role, []).append(r)

        # 按状态分组
        by_status = {}
        for r in results:
            by_status.setdefault(r.status, []).append(r)

        return {
            'total': total,
            'successful': len(successful),
            'failed': len(failed),
            'total_duration': total_duration,
            'total_turns': total_turns,
            'by_role': {role: len(results) for role, results in by_role.items()},
            'by_status': {status: len(results) for status, results in by_status.items()},
            'results': [r.to_dict() for r in results],
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取池统计"""
        return {
            'max_workers': self.max_workers,
            'total_executed': len(self._results),
            'fork_stats': self._fork.get_stats(),
        }

    def clear_results(self):
        """清除结果缓存"""
        self._results.clear()


# ═══════════════════════════════════════════════════════════════
# CLI 子命令
# ═══════════════════════════════════════════════════════════════

def add_fork_subparser(subparsers):
    """添加 fork 子命令到 argparse"""
    fork_parser = subparsers.add_parser(
        "fork", help="子 Agent 管理（P2-4）",
    )
    fork_sub = fork_parser.add_subparsers(dest="fork_command")

    # run
    run_parser = fork_sub.add_parser("run", help="派生子 Agent")
    run_parser.add_argument("--role", type=str, default="developer", help="角色")
    run_parser.add_argument("--feature", type=str, default="", help="功能")
    run_parser.add_argument("--prompt", type=str, default="", help="任务提示词")
    run_parser.add_argument("--timeout", type=int, default=300, help="超时时间（秒）")
    run_parser.add_argument("--perm", type=str, default="default",
                            choices=["default", "plan", "auto", "bypass"],
                            help="权限模式")

    # parallel
    par_parser = fork_sub.add_parser("parallel", help="并行执行多个子 Agent")
    par_parser.add_argument("--config", type=str, required=True,
                            help="JSON 配置文件路径")
    par_parser.add_argument("--workers", type=int, default=3, help="最大并发数")

    # list
    fork_sub.add_parser("list", help="列出子 Agent")

    # merge
    merge_parser = fork_sub.add_parser("merge", help="汇聚结果")
    merge_parser.add_argument("--results", type=str, help="JSON 结果文件路径")

    # stats
    fork_sub.add_parser("stats", help="统计信息")


def handle_fork_command(args, project_root: str = "."):
    """处理 fork 子命令"""
    cmd = getattr(args, 'fork_command', None)
    if not cmd:
        print("⚠️  请指定子命令。使用 adds fork --help 查看帮助。")
        return

    if cmd == "run":
        _cmd_fork_run(args, project_root)
    elif cmd == "parallel":
        _cmd_fork_parallel(args, project_root)
    elif cmd == "list":
        _cmd_fork_list(project_root)
    elif cmd == "merge":
        _cmd_fork_merge(args, project_root)
    elif cmd == "stats":
        _cmd_fork_stats(project_root)
    else:
        print(f"❌ 未知子命令: {cmd}")


def _cmd_fork_run(args, project_root: str):
    """派生子 Agent"""
    fork = AgentFork(project_root=project_root)
    context = ForkContext(
        role=args.role,
        feature=args.feature,
        task_prompt=args.prompt,
        timeout=args.timeout,
        permission_mode=args.perm,
        project_root=project_root,
    )

    print(f"🚀 派生子 Agent (role={args.role})")
    result = fork.fork(context)

    if result.success:
        print(f"✅ 子 Agent 完成: {result.summary()}")
        if result.output:
            print(f"   输出: {result.output[:200]}")
    else:
        print(f"❌ 子 Agent 失败: {result.summary()}")
        if result.error:
            print(f"   错误: {result.error[:200]}")


def _cmd_fork_parallel(args, project_root: str):
    """并行执行"""
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"❌ 配置文件不存在: {args.config}")
        return

    try:
        config = json.loads(config_path.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"❌ 配置文件解析失败: {e}")
        return

    contexts = []
    for item in config.get('forks', []):
        ctx = ForkContext(
            role=item.get('role', 'developer'),
            feature=item.get('feature', ''),
            task_prompt=item.get('prompt', ''),
            timeout=item.get('timeout', 300),
            project_root=project_root,
        )
        contexts.append(ctx)

    pool = ForkPool(project_root=project_root, max_workers=args.workers)
    print(f"🚀 并行执行 {len(contexts)} 个子 Agent (workers={args.workers})")
    results = pool.execute(contexts)

    # 输出结果
    for r in results:
        icon = "✅" if r.success else "❌"
        print(f"  {icon} {r.summary()}")

    # 汇聚
    report = pool.merge_results(results)
    print(f"\n📊 汇聚: {report['successful']}/{report['total']} 成功, "
          f"总时长 {report['total_duration']:.1f}s")


def _cmd_fork_list(project_root: str):
    """列出子 Agent"""
    fork = AgentFork(project_root=project_root)
    forks = fork.list_forks()
    if not forks:
        print("📭 暂无子 Agent 记录")
        return
    print("=" * 60)
    print("📋 子 Agent 列表")
    print("=" * 60)
    for f in forks:
        icon = {"completed": "✅", "failed": "❌", "running": "🔄", "pending": "⏳"}.get(f.status, "❓")
        print(f"  {icon} [{f.fork_id}] {f.role} — {f.feature or 'unnamed'}: {f.status}")
    print()


def _cmd_fork_merge(args, project_root: str):
    """汇聚结果"""
    if args.results:
        try:
            results_data = json.loads(Path(args.results).read_text(encoding='utf-8'))
            results = [ForkResult.from_dict(d) for d in results_data]
        except Exception as e:
            print(f"❌ 结果文件解析失败: {e}")
            return
    else:
        print("❌ 请指定 --results 文件路径")
        return

    pool = ForkPool(project_root=project_root)
    report = pool.merge_results(results)

    print("=" * 50)
    print("📊 汇聚报告")
    print("=" * 50)
    print(f"  总数: {report['total']}")
    print(f"  成功: {report['successful']}")
    print(f"  失败: {report['failed']}")
    print(f"  总时长: {report['total_duration']:.1f}s")
    print(f"  按角色: {report['by_role']}")
    print(f"  按状态: {report['by_status']}")


def _cmd_fork_stats(project_root: str):
    """统计信息"""
    fork = AgentFork(project_root=project_root)
    stats = fork.get_stats()
    print("=" * 50)
    print("📊 子 Agent 统计")
    print("=" * 50)
    print(f"  总 Fork 数: {stats['total_forks']}")
    print(f"  状态分布: {stats['status_counts']}")
    print()


# ═══════════════════════════════════════════════════════════════
# 内置测试
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    print("=== ForkContext 测试 ===")
    ctx = ForkContext(
        role="developer",
        feature="测试功能",
        task_prompt="请执行测试任务",
        project_root=".",
    )
    print(f"  创建: role={ctx.role}, feature={ctx.feature}")

    print("\n=== ForkResult 测试 ===")
    result = ForkResult(
        fork_id="fork-test",
        role="developer",
        feature="测试",
        status=ForkStatus.COMPLETED,
        output="测试完成",
        duration=5.0,
        turns=3,
    )
    print(f"  结果: {result.summary()}")
    print(f"  成功: {result.success}")

    print("\n=== AgentFork 测试 ===")
    fork = AgentFork(project_root=".")
    # 快速命令测试（不用真正的 adds start）
    ctx = ForkContext(
        role="developer",
        feature="echo测试",
        task_prompt="echo hello from fork",
        timeout=30,
    )
    result = fork.fork(ctx)
    print(f"  Fork 结果: status={result.status}, duration={result.duration:.2f}s")
    print(f"  统计: {fork.get_stats()}")

    print("\n=== ForkPool 测试 ===")
    pool = ForkPool(project_root=".", max_workers=2)
    contexts = [
        ForkContext(role="developer", feature="echo1", task_prompt="echo task1", timeout=10),
        ForkContext(role="tester", feature="echo2", task_prompt="echo task2", timeout=10),
    ]
    results = pool.execute(contexts)
    for r in results:
        print(f"  {r.summary()}")
    report = pool.merge_results(results)
    print(f"  汇聚: {report['successful']}/{report['total']} 成功")

#!/usr/bin/env python3
"""
ADDS 定时调度系统 (P2-1)

基于 cron 表达式的定时任务调度，支持 Agent Loop 自动执行、结果通知、失败重试。

核心组件：
- CronExpression: cron 表达式解析器
- ScheduledTask: 任务数据模型
- TaskScheduler: 调度引擎
- AgentExecutor: 任务执行器
- NotificationManager: 通知管理
"""

import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, Tuple

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# CronExpression — 5 字段 cron 解析器
# ═══════════════════════════════════════════════════════════════

class CronField:
    """单个 cron 字段的解析与匹配

    支持格式：
    - *        任意值
    - 5        固定值
    - 1,3,5    列表
    - 1-5      范围
    - */2      步长
    - 1-5/2    范围+步长
    """

    def __init__(self, expr: str, min_val: int, max_val: int):
        self.expr = expr.strip()
        self.min_val = min_val
        self.max_val = max_val
        self._values: Optional[set] = None

    def _parse(self) -> set:
        """解析表达式为允许值集合"""
        if self._values is not None:
            return self._values

        values = set()

        for part in self.expr.split(','):
            part = part.strip()
            if part == '*':
                # 步长
                step_match = re.match(r'^\*/(\d+)$', part)
                if step_match:
                    step = int(step_match.group(1))
                    values.update(range(self.min_val, self.max_val + 1, step))
                else:
                    values.update(range(self.min_val, self.max_val + 1))

            elif '/' in part:
                # 范围+步长 或 */步长
                range_part, step_str = part.split('/', 1)
                step = int(step_str)
                if range_part == '*':
                    start, end = self.min_val, self.max_val
                elif '-' in range_part:
                    start, end = map(int, range_part.split('-', 1))
                else:
                    start, end = int(range_part), self.max_val
                values.update(range(start, end + 1, step))

            elif '-' in part:
                # 范围
                start, end = map(int, part.split('-', 1))
                values.update(range(start, end + 1))

            else:
                # 固定值
                values.add(int(part))

        # 限制在合法范围内
        self._values = {v for v in values if self.min_val <= v <= self.max_val}
        return self._values

    def matches(self, value: int) -> bool:
        """检查给定值是否匹配此字段"""
        return value in self._parse()


class CronExpression:
    """5 字段 cron 表达式解析器

    格式: 分 时 日 月 周
    示例:
      * * * * *      每分钟
      */5 * * * *    每 5 分钟
      0 * * * *      每小时
      0 9 * * *      每天上午 9 点
      0 9 * * 1      每周一上午 9 点
      30 8 1 * *     每月 1 号上午 8:30
    """

    # 月份和星期的别名映射
    MONTH_ALIASES = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
        'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
        'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    }
    DOW_ALIASES = {
        'sun': 0, 'mon': 1, 'tue': 2, 'wed': 3,
        'thu': 4, 'fri': 5, 'sat': 6,
    }

    # 预定义快捷方式
    SHORTCUTS = {
        '@yearly': '0 0 1 1 *',
        '@annually': '0 0 1 1 *',
        '@monthly': '0 0 1 * *',
        '@weekly': '0 0 * * 0',
        '@daily': '0 0 * * *',
        '@hourly': '0 * * * *',
        '@minutely': '* * * * *',
    }

    def __init__(self, expression: str):
        self.raw = expression.strip()

        # 处理快捷方式
        if self.raw.startswith('@'):
            key = self.raw.lower()
            if key in self.SHORTCUTS:
                self.raw = self.SHORTCUTS[key]
            else:
                raise ValueError(f"Unknown cron shortcut: {self.raw}")

        parts = self.raw.split()
        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression (expected 5 fields, got {len(parts)}): {self.raw}"
            )

        # 解析各字段（替换别名）
        minute_expr = self._replace_aliases(parts[0], self.MONTH_ALIASES)
        hour_expr = self._replace_aliases(parts[1], {})
        dom_expr = self._replace_aliases(parts[2], {})
        month_expr = self._replace_aliases(parts[3].lower(), self.MONTH_ALIASES)
        dow_expr = self._replace_aliases(parts[4].lower(), self.DOW_ALIASES)

        # 0-6 → 0-7 (0 和 7 都代表周日)
        # 先将 7 替换为 0
        dow_expr = re.sub(r'\b7\b', '0', dow_expr)

        self.minute = CronField(minute_expr, 0, 59)
        self.hour = CronField(hour_expr, 0, 23)
        self.dom = CronField(dom_expr, 1, 31)
        self.month = CronField(month_expr, 1, 12)
        self.dow = CronField(dow_expr, 0, 6)

    @staticmethod
    def _replace_aliases(expr: str, aliases: Dict[str, int]) -> str:
        """将别名替换为数字"""
        result = expr
        for name, num in aliases.items():
            result = re.sub(rf'\b{name}\b', str(num), result, flags=re.IGNORECASE)
        return result

    def matches(self, dt: Optional[datetime] = None) -> bool:
        """检查给定时间是否匹配此 cron 表达式"""
        if dt is None:
            dt = datetime.now()
        return (
            self.minute.matches(dt.minute) and
            self.hour.matches(dt.hour) and
            self.dom.matches(dt.day) and
            self.month.matches(dt.month) and
            self.dow.matches(dt.weekday())  # 0=Monday in Python, but cron uses 0=Sunday
        )

    def matches_cron_weekday(self, dt: Optional[datetime] = None) -> bool:
        """检查给定时间是否匹配（cron 风格：0=Sunday）

        Python 的 weekday() 返回 0=Monday，需要转换：
        Python: Mon=0, Tue=1, ..., Sun=6
        Cron:   Sun=0, Mon=1, ..., Sat=6
        """
        if dt is None:
            dt = datetime.now()
        # 转换 Python weekday → cron dow
        cron_dow = (dt.weekday() + 1) % 7
        return (
            self.minute.matches(dt.minute) and
            self.hour.matches(dt.hour) and
            self.dom.matches(dt.day) and
            self.month.matches(dt.month) and
            self.dow.matches(cron_dow)
        )

    def next_run(self, after: Optional[datetime] = None) -> datetime:
        """计算下一次运行时间"""
        if after is None:
            after = datetime.now()
        # 从下一分钟开始搜索
        check = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
        # 最多搜索 366 天
        max_iterations = 366 * 24 * 60
        for _ in range(max_iterations):
            if self.matches_cron_weekday(check):
                return check
            check += timedelta(minutes=1)
        raise ValueError(f"Cannot find next run time within 366 days for: {self.raw}")

    def __repr__(self) -> str:
        return f"CronExpression('{self.raw}')"


# ═══════════════════════════════════════════════════════════════
# ScheduledTask — 任务数据模型
# ═══════════════════════════════════════════════════════════════

class TaskStatus(str, Enum):
    """任务状态"""
    ACTIVE = "active"
    PAUSED = "paused"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(str, Enum):
    """任务类型"""
    AGENT = "agent"          # 启动 Agent Loop
    COMMAND = "command"       # 执行命令
    PYTHON = "python"         # 执行 Python 函数


@dataclass
class ExecutionRecord:
    """执行记录"""
    started_at: str           # ISO 格式时间
    finished_at: Optional[str] = None
    status: str = "running"   # running / success / failed / timeout
    exit_code: Optional[int] = None
    output: str = ""          # 输出摘要（前 500 字符）
    error: str = ""           # 错误信息
    retry_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'ExecutionRecord':
        return cls(**d)


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 2              # 最大重试次数（0 = 不重试）
    backoff_base: float = 60.0        # 退避基础时间（秒）
    backoff_max: float = 3600.0       # 退避最大时间（秒）

    def get_backoff(self, retry_count: int) -> float:
        """计算退避时间"""
        backoff = self.backoff_base * (2 ** retry_count)
        return min(backoff, self.backoff_max)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'RetryConfig':
        return cls(**d)


@dataclass
class ScheduledTask:
    """定时任务"""
    task_id: str                         # 唯一 ID
    name: str                            # 任务名称
    task_type: str = "command"           # TaskType
    cron_expr: str = "* * * * *"         # cron 表达式
    status: str = "active"               # TaskStatus
    command: str = ""                     # 执行的命令（command 类型）
    role: str = ""                        # Agent 角色（agent 类型）
    prompt: str = ""                      # Agent 提示词（agent 类型）
    python_module: str = ""              # Python 模块路径
    python_function: str = ""            # Python 函数名
    retry_config: Dict[str, Any] = field(default_factory=lambda: asdict(RetryConfig()))
    notify_on: str = "always"            # always / on_failure / never
    max_output_lines: int = 50           # 最大输出行数
    created_at: str = ""                 # 创建时间
    last_run: Optional[str] = None       # 上次执行时间
    next_run: Optional[str] = None       # 下次执行时间
    last_status: Optional[str] = None    # 上次执行状态
    execution_count: int = 0             # 总执行次数
    failure_count: int = 0               # 连续失败次数
    history: List[Dict[str, Any]] = field(default_factory=list)  # 执行历史（最近 20 条）
    tags: List[str] = field(default_factory=list)                # 标签
    description: str = ""                                       # 描述

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.task_id:
            self.task_id = f"task-{int(time.time())}"
        # 规范化 retry_config
        if isinstance(self.retry_config, dict) and not isinstance(self.retry_config, RetryConfig):
            self.retry_config = self.retry_config  # 保持 dict 格式用于序列化

    def get_retry_config(self) -> RetryConfig:
        """获取重试配置对象"""
        if isinstance(self.retry_config, dict):
            return RetryConfig.from_dict(self.retry_config)
        return self.retry_config

    def add_history(self, record: ExecutionRecord):
        """添加执行记录"""
        self.history.append(record.to_dict())
        # 只保留最近 20 条
        if len(self.history) > 20:
            self.history = self.history[-20:]
        self.execution_count += 1
        if record.status == "failed":
            self.failure_count += 1
        else:
            self.failure_count = 0
        self.last_status = record.status
        self.last_run = record.started_at

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'ScheduledTask':
        # 兼容缺少的字段
        defaults = {
            'tags': [], 'description': '', 'python_module': '',
            'python_function': '', 'max_output_lines': 50,
        }
        for k, v in defaults.items():
            if k not in d:
                d[k] = v
        return cls(**d)


# ═══════════════════════════════════════════════════════════════
# NotificationManager — 通知管理
# ═══════════════════════════════════════════════════════════════

class NotificationLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class Notification:
    """通知消息"""
    task_id: str
    task_name: str
    level: str       # NotificationLevel
    message: str
    timestamp: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class NotificationManager:
    """通知管理器

    支持的通知渠道：
    - log: 记录到日志
    - file: 写入通知文件
    - command: 执行自定义通知命令
    """

    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        self.notifications_dir = Path(project_root) / ".ai" / "notifications"
        self.notifications_dir.mkdir(parents=True, exist_ok=True)
        self._handlers: List[Callable[[Notification], None]] = []
        self._command: Optional[str] = None

    def set_command(self, command: str):
        """设置通知命令（如发送到 IM）"""
        self._command = command

    def add_handler(self, handler: Callable[[Notification], None]):
        """添加自定义通知处理器"""
        self._handlers.append(handler)

    def notify(self, notification: Notification):
        """发送通知"""
        # 1. 记录日志
        log_level = {
            NotificationLevel.INFO: logging.INFO,
            NotificationLevel.WARNING: logging.WARNING,
            NotificationLevel.ERROR: logging.ERROR,
        }.get(notification.level, logging.INFO)
        logger.log(log_level, f"[{notification.task_name}] {notification.message}")

        # 2. 写入文件
        try:
            notif_file = self.notifications_dir / f"{datetime.now().strftime('%Y%m%d')}.jsonl"
            with open(notif_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'task_id': notification.task_id,
                    'task_name': notification.task_name,
                    'level': notification.level,
                    'message': notification.message,
                    'timestamp': notification.timestamp,
                    'details': notification.details,
                }, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.debug(f"Failed to write notification file: {e}")

        # 3. 执行命令
        if self._command:
            try:
                env = os.environ.copy()
                env.update({
                    'ADDS_TASK_ID': notification.task_id,
                    'ADDS_TASK_NAME': notification.task_name,
                    'ADDS_LEVEL': notification.level,
                    'ADDS_MESSAGE': notification.message,
                })
                subprocess.run(
                    self._command, shell=True, env=env,
                    timeout=30, capture_output=True,
                )
            except Exception as e:
                logger.debug(f"Notification command failed: {e}")

        # 4. 自定义处理器
        for handler in self._handlers:
            try:
                handler(notification)
            except Exception as e:
                logger.debug(f"Notification handler failed: {e}")


# ═══════════════════════════════════════════════════════════════
# AgentExecutor — 任务执行器
# ═══════════════════════════════════════════════════════════════

class AgentExecutor:
    """任务执行器

    支持三种任务类型：
    - command: 执行 shell 命令
    - agent: 启动 Agent Loop
    - python: 执行 Python 函数
    """

    def __init__(self, project_root: str = ".", timeout: int = 600):
        self.project_root = project_root
        self.timeout = timeout  # 默认超时 10 分钟

    def execute(self, task: ScheduledTask) -> ExecutionRecord:
        """执行任务

        Returns:
            ExecutionRecord 执行记录
        """
        record = ExecutionRecord(started_at=datetime.now().isoformat())

        try:
            if task.task_type == TaskType.COMMAND:
                exit_code, output, error = self._execute_command(task.command)
            elif task.task_type == TaskType.AGENT:
                exit_code, output, error = self._execute_agent(task)
            elif task.task_type == TaskType.PYTHON:
                exit_code, output, error = self._execute_python(task)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")

            # 截断输出
            max_chars = 500
            record.output = output[:max_chars] + ("..." if len(output) > max_chars else "")
            record.error = error[:max_chars] + ("..." if len(error) > max_chars else "")
            record.exit_code = exit_code
            record.status = "success" if exit_code == 0 else "failed"

        except subprocess.TimeoutExpired:
            record.status = "timeout"
            record.error = f"Task timed out after {self.timeout}s"
            record.exit_code = -1

        except Exception as e:
            record.status = "failed"
            record.error = str(e)
            record.exit_code = -1

        record.finished_at = datetime.now().isoformat()
        return record

    def _execute_command(self, command: str) -> Tuple[int, str, str]:
        """执行 shell 命令"""
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=self.timeout, cwd=self.project_root,
        )
        return result.returncode, result.stdout, result.stderr

    def _execute_agent(self, task: ScheduledTask) -> Tuple[int, str, str]:
        """启动 Agent Loop 执行任务"""
        # 构建 adds start 命令
        cmd_parts = [
            sys.executable,
            str(Path(__file__).parent / "adds.py"),
            "start",
            "--non-interactive",
        ]
        if task.role:
            cmd_parts.extend(["--role", task.role])
        else:
            cmd_parts.extend(["--role", "developer"])

        # 通过 prompt 环境变量传递任务提示词
        env = os.environ.copy()
        if task.prompt:
            env['ADDS_SCHEDULED_PROMPT'] = task.prompt

        # 将提示词作为第一个用户消息
        # 非交互模式下直接传入 prompt
        prompt_arg = task.prompt or "执行定时任务"

        result = subprocess.run(
            cmd_parts,
            input=prompt_arg,
            capture_output=True, text=True,
            timeout=self.timeout,
            cwd=self.project_root,
            env=env,
        )
        return result.returncode, result.stdout, result.stderr

    def _execute_python(self, task: ScheduledTask) -> Tuple[int, str, str]:
        """执行 Python 函数"""
        if not task.python_module or not task.python_function:
            return 1, "", "python_module and python_function are required"

        # 动态导入并执行
        try:
            import importlib
            module = importlib.import_module(task.python_module)
            func = getattr(module, task.python_function)
            result = func()
            output = str(result) if result is not None else ""
            return 0, output, ""
        except Exception as e:
            return 1, "", str(e)


# ═══════════════════════════════════════════════════════════════
# TaskScheduler — 调度引擎
# ═══════════════════════════════════════════════════════════════

class TaskScheduler:
    """定时任务调度引擎

    功能：
    - 添加/删除/暂停/恢复任务
    - 守护进程模式运行
    - 单次运行模式（检查并执行到期任务）
    - 执行历史记录
    - 失败重试
    - 通知
    """

    def __init__(self, project_root: str = ".", timeout: int = 600):
        self.project_root = project_root
        self.config_path = Path(project_root) / ".ai" / "scheduler.json"
        self.executor = AgentExecutor(project_root=project_root, timeout=timeout)
        self.notifier = NotificationManager(project_root=project_root)
        self.tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 加载已有任务
        self._load()

    def _load(self):
        """从配置文件加载任务"""
        if not self.config_path.exists():
            return
        try:
            data = json.loads(self.config_path.read_text(encoding='utf-8'))
            for task_data in data.get('tasks', []):
                task = ScheduledTask.from_dict(task_data)
                self.tasks[task.task_id] = task
            logger.info(f"Loaded {len(self.tasks)} scheduled tasks")
        except Exception as e:
            logger.warning(f"Failed to load scheduler config: {e}")

    def _save(self):
        """保存任务到配置文件"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'version': '1.0',
            'updated_at': datetime.now().isoformat(),
            'tasks': [task.to_dict() for task in self.tasks.values()],
        }
        self.config_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    def add_task(self, task: ScheduledTask) -> ScheduledTask:
        """添加任务"""
        with self._lock:
            # 计算 next_run
            try:
                cron = CronExpression(task.cron_expr)
                task.next_run = cron.next_run().isoformat()
            except Exception as e:
                raise ValueError(f"Invalid cron expression '{task.cron_expr}': {e}")

            self.tasks[task.task_id] = task
            self._save()
            logger.info(f"Added task: {task.task_id} ({task.name})")
            return task

    def remove_task(self, task_id: str) -> bool:
        """删除任务"""
        with self._lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                self._save()
                logger.info(f"Removed task: {task_id}")
                return True
            return False

    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].status = TaskStatus.PAUSED
                self._save()
                logger.info(f"Paused task: {task_id}")
                return True
            return False

    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].status = TaskStatus.ACTIVE
                try:
                    cron = CronExpression(self.tasks[task_id].cron_expr)
                    self.tasks[task_id].next_run = cron.next_run().isoformat()
                except Exception:
                    pass
                self._save()
                logger.info(f"Resumed task: {task_id}")
                return True
            return False

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """获取任务"""
        return self.tasks.get(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[ScheduledTask]:
        """列出任务"""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at)

    def run_task_now(self, task_id: str) -> Optional[ExecutionRecord]:
        """立即执行任务（忽略调度时间）"""
        task = self.tasks.get(task_id)
        if not task:
            return None

        return self._execute_task(task)

    def _execute_task(self, task: ScheduledTask) -> ExecutionRecord:
        """执行单个任务（含重试逻辑）"""
        retry_config = task.get_retry_config()
        record = self.executor.execute(task)
        record.retry_count = 0

        # 失败重试
        if record.status == "failed" and retry_config.max_retries > 0:
            for attempt in range(retry_config.max_retries):
                backoff = retry_config.get_backoff(attempt)
                logger.info(
                    f"Task {task.task_id} failed, retrying in {backoff:.0f}s "
                    f"(attempt {attempt + 1}/{retry_config.max_retries})"
                )
                time.sleep(backoff)
                record = self.executor.execute(task)
                record.retry_count = attempt + 1
                if record.status == "success":
                    break

        # 更新任务状态
        with self._lock:
            task.add_history(record)
            # 计算下次运行时间
            try:
                cron = CronExpression(task.cron_expr)
                task.next_run = cron.next_run().isoformat()
            except Exception:
                task.next_run = None
            self._save()

        # 通知
        self._notify_task_result(task, record)

        return record

    def _notify_task_result(self, task: ScheduledTask, record: ExecutionRecord):
        """根据任务配置发送通知"""
        if task.notify_on == "never":
            return
        if task.notify_on == "on_failure" and record.status == "success":
            return

        level = NotificationLevel.INFO if record.status == "success" else NotificationLevel.ERROR
        message = (
            f"任务 '{task.name}' 执行{'成功' if record.status == 'success' else '失败'}"
            f" (exit_code={record.exit_code})"
        )
        if record.retry_count > 0:
            message += f" [重试 {record.retry_count} 次]"

        self.notifier.notify(Notification(
            task_id=task.task_id,
            task_name=task.name,
            level=level,
            message=message,
            details={
                'exit_code': record.exit_code,
                'output': record.output[:200],
                'error': record.error[:200] if record.error else "",
                'retry_count': record.retry_count,
            },
        ))

    def check_and_run(self):
        """检查并执行到期任务（单次检查）

        适用于外部调度器（如系统 cron）调用。
        """
        now = datetime.now()
        tasks_to_run = []

        with self._lock:
            for task in self.tasks.values():
                if task.status != TaskStatus.ACTIVE:
                    continue
                try:
                    cron = CronExpression(task.cron_expr)
                    if cron.matches_cron_weekday(now):
                        # 避免同一分钟内重复执行
                        if task.last_run:
                            last = datetime.fromisoformat(task.last_run)
                            if (now - last).total_seconds() < 60:
                                continue
                        tasks_to_run.append(task)
                except Exception as e:
                    logger.warning(f"Invalid cron for task {task.task_id}: {e}")

        for task in tasks_to_run:
            logger.info(f"Running scheduled task: {task.task_id} ({task.name})")
            try:
                self._execute_task(task)
            except Exception as e:
                logger.error(f"Task {task.task_id} execution error: {e}")

    def run_daemon(self, interval: int = 60):
        """守护进程模式运行

        Args:
            interval: 检查间隔（秒），默认 60 秒
        """
        self._running = True
        logger.info(f"Scheduler daemon started (interval={interval}s)")

        # 注册信号处理
        def _signal_handler(signum, frame):
            logger.info("Received shutdown signal, stopping...")
            self._running = False

        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

        while self._running:
            try:
                self.check_and_run()
            except Exception as e:
                logger.error(f"Scheduler check error: {e}")

            # 分段 sleep，以便能及时响应停止信号
            for _ in range(interval):
                if not self._running:
                    break
                time.sleep(1)

        logger.info("Scheduler daemon stopped")

    def start_daemon(self, interval: int = 60):
        """在后台线程启动守护进程"""
        if self._thread and self._thread.is_alive():
            logger.warning("Daemon already running")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self.run_daemon,
            args=(interval,),
            daemon=True,
            name="adds-scheduler",
        )
        self._thread.start()
        logger.info("Scheduler daemon thread started")

    def stop_daemon(self):
        """停止守护进程"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Scheduler daemon stopped")

    def is_daemon_running(self) -> bool:
        """守护进程是否在运行"""
        return self._running and self._thread is not None and self._thread.is_alive()

    def get_stats(self) -> Dict[str, Any]:
        """获取调度统计信息"""
        total = len(self.tasks)
        active = sum(1 for t in self.tasks.values() if t.status == TaskStatus.ACTIVE)
        paused = sum(1 for t in self.tasks.values() if t.status == TaskStatus.PAUSED)
        total_executions = sum(t.execution_count for t in self.tasks.values())

        return {
            'total_tasks': total,
            'active_tasks': active,
            'paused_tasks': paused,
            'total_executions': total_executions,
            'daemon_running': self.is_daemon_running(),
        }


# ═══════════════════════════════════════════════════════════════
# CLI 子命令
# ═══════════════════════════════════════════════════════════════

def add_schedule_subparser(subparsers):
    """添加 schedule 子命令到 argparse"""
    sched_parser = subparsers.add_parser(
        "schedule", help="定时调度管理（P2-1）",
    )
    sched_sub = sched_parser.add_subparsers(dest="schedule_command")

    # add
    add_parser = sched_sub.add_parser("add", help="添加定时任务")
    add_parser.add_argument("name", type=str, help="任务名称")
    add_parser.add_argument("--cron", type=str, required=True, help="Cron 表达式（5字段）")
    add_parser.add_argument("--type", type=str, default="command",
                            choices=["command", "agent", "python"],
                            help="任务类型")
    add_parser.add_argument("--command", type=str, help="执行命令（command 类型）")
    add_parser.add_argument("--role", type=str, help="Agent 角色（agent 类型）")
    add_parser.add_argument("--prompt", type=str, help="Agent 提示词（agent 类型）")
    add_parser.add_argument("--module", type=str, help="Python 模块路径")
    add_parser.add_argument("--function", type=str, help="Python 函数名")
    add_parser.add_argument("--retries", type=int, default=2, help="最大重试次数")
    add_parser.add_argument("--notify", type=str, default="always",
                            choices=["always", "on_failure", "never"],
                            help="通知策略")
    add_parser.add_argument("--tag", type=str, action="append", help="标签（可多次）")
    add_parser.add_argument("--description", type=str, default="", help="描述")

    # list
    sched_sub.add_parser("list", help="列出定时任务")

    # remove
    rm_parser = sched_sub.add_parser("remove", help="删除定时任务")
    rm_parser.add_argument("task_id", type=str, help="任务 ID")

    # run
    run_parser = sched_sub.add_parser("run", help="立即执行任务")
    run_parser.add_argument("task_id", type=str, help="任务 ID")

    # pause
    pause_parser = sched_sub.add_parser("pause", help="暂停任务")
    pause_parser.add_argument("task_id", type=str, help="任务 ID")

    # resume
    resume_parser = sched_sub.add_parser("resume", help="恢复任务")
    resume_parser.add_argument("task_id", type=str, help="任务 ID")

    # history
    hist_parser = sched_sub.add_parser("history", help="查看任务执行历史")
    hist_parser.add_argument("task_id", type=str, help="任务 ID")
    hist_parser.add_argument("--limit", type=int, default=10, help="显示条数")

    # daemon
    daemon_parser = sched_sub.add_parser("daemon", help="启动守护进程")
    daemon_parser.add_argument("--interval", type=int, default=60, help="检查间隔（秒）")
    daemon_parser.add_argument("--stop", action="store_true", help="停止守护进程")

    # stats
    sched_sub.add_parser("stats", help="调度统计信息")


def handle_schedule_command(args, project_root: str = "."):
    """处理 schedule 子命令"""
    scheduler = TaskScheduler(project_root=project_root)

    cmd = getattr(args, 'schedule_command', None)
    if not cmd:
        print("⚠️  请指定子命令。使用 adds schedule --help 查看帮助。")
        return

    if cmd == "add":
        _cmd_add(scheduler, args)
    elif cmd == "list":
        _cmd_list(scheduler)
    elif cmd == "remove":
        _cmd_remove(scheduler, args)
    elif cmd == "run":
        _cmd_run(scheduler, args)
    elif cmd == "pause":
        _cmd_pause(scheduler, args)
    elif cmd == "resume":
        _cmd_resume(scheduler, args)
    elif cmd == "history":
        _cmd_history(scheduler, args)
    elif cmd == "daemon":
        _cmd_daemon(scheduler, args)
    elif cmd == "stats":
        _cmd_stats(scheduler)
    else:
        print(f"❌ 未知子命令: {cmd}")


def _cmd_add(scheduler: TaskScheduler, args):
    """添加定时任务"""
    import uuid
    task_id = f"task-{uuid.uuid4().hex[:8]}"

    task = ScheduledTask(
        task_id=task_id,
        name=args.name,
        task_type=args.type,
        cron_expr=args.cron,
        command=args.command or "",
        role=args.role or "",
        prompt=args.prompt or "",
        python_module=args.module or "",
        python_function=args.function or "",
        retry_config=asdict(RetryConfig(max_retries=args.retries)),
        notify_on=args.notify,
        tags=args.tag or [],
        description=args.description,
    )

    try:
        scheduler.add_task(task)
        print(f"✅ 定时任务已添加")
        print(f"   ID: {task.task_id}")
        print(f"   名称: {task.name}")
        print(f"   类型: {task.task_type}")
        print(f"   Cron: {task.cron_expr}")
        print(f"   下次运行: {task.next_run}")
    except ValueError as e:
        print(f"❌ 添加失败: {e}")


def _cmd_list(scheduler: TaskScheduler):
    """列出定时任务"""
    tasks = scheduler.list_tasks()
    if not tasks:
        print("📭 暂无定时任务")
        return

    print("=" * 80)
    print("📋 定时任务列表")
    print("=" * 80)

    status_icons = {
        TaskStatus.ACTIVE: "🟢",
        TaskStatus.PAUSED: "⏸️",
        TaskStatus.RUNNING: "🔄",
        TaskStatus.COMPLETED: "✅",
        TaskStatus.FAILED: "❌",
    }

    for task in tasks:
        icon = status_icons.get(task.status, "❓")
        print(f"\n  {icon} [{task.task_id}] {task.name}")
        print(f"     类型: {task.task_type}  Cron: {task.cron_expr}")
        print(f"     执行次数: {task.execution_count}  上次状态: {task.last_status or '-'}")
        print(f"     下次运行: {task.next_run or '-'}")
        if task.tags:
            print(f"     标签: {', '.join(task.tags)}")
    print()


def _cmd_remove(scheduler: TaskScheduler, args):
    """删除定时任务"""
    if scheduler.remove_task(args.task_id):
        print(f"✅ 任务 {args.task_id} 已删除")
    else:
        print(f"❌ 未找到任务: {args.task_id}")


def _cmd_run(scheduler: TaskScheduler, args):
    """立即执行任务"""
    record = scheduler.run_task_now(args.task_id)
    if not record:
        print(f"❌ 未找到任务: {args.task_id}")
        return

    status_icon = "✅" if record.status == "success" else "❌"
    print(f"{status_icon} 任务执行{record.status}")
    print(f"   开始: {record.started_at}")
    print(f"   结束: {record.finished_at}")
    print(f"   退出码: {record.exit_code}")
    if record.output:
        print(f"   输出: {record.output[:200]}")
    if record.error:
        print(f"   错误: {record.error[:200]}")


def _cmd_pause(scheduler: TaskScheduler, args):
    """暂停任务"""
    if scheduler.pause_task(args.task_id):
        print(f"⏸️  任务 {args.task_id} 已暂停")
    else:
        print(f"❌ 未找到任务: {args.task_id}")


def _cmd_resume(scheduler: TaskScheduler, args):
    """恢复任务"""
    if scheduler.resume_task(args.task_id):
        print(f"▶️  任务 {args.task_id} 已恢复")
    else:
        print(f"❌ 未找到任务: {args.task_id}")


def _cmd_history(scheduler: TaskScheduler, args):
    """查看执行历史"""
    task = scheduler.get_task(args.task_id)
    if not task:
        print(f"❌ 未找到任务: {args.task_id}")
        return

    history = task.history[-args.limit:]
    if not history:
        print(f"📭 任务 {args.task_id} 暂无执行历史")
        return

    print("=" * 70)
    print(f"📜 任务 {task.name} 执行历史（最近 {len(history)} 条）")
    print("=" * 70)

    for record in reversed(history):
        status_icon = "✅" if record.get('status') == 'success' else "❌"
        started = record.get('started_at', '?')
        exit_code = record.get('exit_code', '?')
        print(f"\n  {status_icon} {started}  (exit={exit_code})")
        if record.get('retry_count'):
            print(f"     重试: {record['retry_count']} 次")
        output = record.get('output', '')
        if output:
            print(f"     输出: {output[:100]}")
        error = record.get('error', '')
        if error:
            print(f"     错误: {error[:100]}")
    print()


def _cmd_daemon(scheduler: TaskScheduler, args):
    """守护进程管理"""
    if args.stop:
        scheduler.stop_daemon()
        print("🛑 守护进程已停止")
        return

    if scheduler.is_daemon_running():
        print("⚠️  守护进程已在运行")
        return

    print(f"🚀 启动调度守护进程（间隔 {args.interval}s）")
    print("   按 Ctrl+C 停止")
    scheduler.run_daemon(interval=args.interval)


def _cmd_stats(scheduler: TaskScheduler):
    """调度统计"""
    stats = scheduler.get_stats()
    print("=" * 50)
    print("📊 调度统计")
    print("=" * 50)
    print(f"  总任务数: {stats['total_tasks']}")
    print(f"  活跃任务: {stats['active_tasks']}")
    print(f"  暂停任务: {stats['paused_tasks']}")
    print(f"  总执行次数: {stats['total_executions']}")
    print(f"  守护进程: {'运行中' if stats['daemon_running'] else '未启动'}")
    print()


# ═══════════════════════════════════════════════════════════════
# 内置测试
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from log_config import configure_standalone_logging
    configure_standalone_logging()

    # 测试 CronExpression
    print("=== CronExpression 测试 ===")

    # 每分钟
    cron = CronExpression("* * * * *")
    now = datetime.now()
    print(f"  * * * * * matches now: {cron.matches_cron_weekday(now)}")
    next_run = cron.next_run()
    print(f"  next run: {next_run}")

    # 每天 9 点
    cron9 = CronExpression("0 9 * * *")
    print(f"  0 9 * * * next run: {cron9.next_run()}")

    # 每 5 分钟
    cron5 = CronExpression("*/5 * * * *")
    print(f"  */5 * * * * next run: {cron5.next_run()}")

    # 快捷方式
    cron_daily = CronExpression("@daily")
    print(f"  @daily = {cron_daily.raw}")
    print(f"  @daily next run: {cron_daily.next_run()}")

    # 测试 TaskScheduler
    print("\n=== TaskScheduler 测试 ===")
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        sched = TaskScheduler(project_root=tmpdir)
        task = ScheduledTask(
            task_id="test-001",
            name="测试任务",
            task_type="command",
            cron_expr="*/5 * * * *",
            command="echo hello",
        )
        sched.add_task(task)
        print(f"  添加任务: {task.task_id}")
        print(f"  任务列表: {[t.task_id for t in sched.list_tasks()]}")
        print(f"  统计: {sched.get_stats()}")

        # 立即执行
        record = sched.run_task_now("test-001")
        print(f"  执行结果: status={record.status}, exit_code={record.exit_code}")
        print(f"  输出: {record.output.strip()}")

        # 清理
        sched.remove_task("test-001")
        print(f"  删除后统计: {sched.get_stats()}")

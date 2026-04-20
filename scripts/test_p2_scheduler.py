#!/usr/bin/env python3
"""
ADDS P2-1 定时调度系统测试

测试场景：
1. CronExpression 解析
2. CronExpression 匹配
3. CronExpression next_run
4. CronExpression 快捷方式
5. ScheduledTask 数据模型
6. TaskScheduler 添加/删除/暂停/恢复
7. TaskScheduler 执行命令
8. TaskScheduler 执行历史
9. TaskScheduler 失败重试
10. NotificationManager 通知
11. CLI 子命令
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

# 确保可以导入
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scheduler import (
    CronExpression, CronField,
    ScheduledTask, ExecutionRecord, RetryConfig,
    TaskStatus, TaskType,
    TaskScheduler, AgentExecutor, NotificationManager, Notification,
    NotificationLevel,
)


class TestCronField(unittest.TestCase):
    """场景 1: CronField 单字段解析"""

    def test_wildcard(self):
        f = CronField("*", 0, 59)
        for v in range(60):
            self.assertTrue(f.matches(v))

    def test_fixed_value(self):
        f = CronField("5", 0, 59)
        self.assertTrue(f.matches(5))
        self.assertFalse(f.matches(4))
        self.assertFalse(f.matches(6))

    def test_list(self):
        f = CronField("1,3,5", 0, 59)
        self.assertTrue(f.matches(1))
        self.assertTrue(f.matches(3))
        self.assertTrue(f.matches(5))
        self.assertFalse(f.matches(2))
        self.assertFalse(f.matches(0))

    def test_range(self):
        f = CronField("1-5", 0, 59)
        for v in range(1, 6):
            self.assertTrue(f.matches(v))
        self.assertFalse(f.matches(0))
        self.assertFalse(f.matches(6))

    def test_step(self):
        f = CronField("*/15", 0, 59)
        for v in [0, 15, 30, 45]:
            self.assertTrue(f.matches(v))
        self.assertFalse(f.matches(5))

    def test_range_step(self):
        f = CronField("1-10/2", 0, 59)
        for v in [1, 3, 5, 7, 9]:
            self.assertTrue(f.matches(v))
        self.assertFalse(f.matches(0))
        self.assertFalse(f.matches(2))
        self.assertFalse(f.matches(11))


class TestCronExpressionParsing(unittest.TestCase):
    """场景 2: CronExpression 解析"""

    def test_five_fields(self):
        cron = CronExpression("* * * * *")
        self.assertIsNotNone(cron)

    def test_invalid_field_count(self):
        with self.assertRaises(ValueError):
            CronExpression("* * *")

    def test_month_aliases(self):
        cron = CronExpression("0 0 1 jan *")
        # 1月1日 00:00 应该匹配
        dt = datetime(2026, 1, 1, 0, 0)
        # 注意：CronExpression 用 matches_cron_weekday

    def test_dow_aliases(self):
        cron = CronExpression("0 0 * * mon")
        # 周一
        dt = datetime(2026, 4, 20, 0, 0)  # 2026-04-20 是周一
        self.assertTrue(cron.matches_cron_weekday(dt))

    def test_dow_7_is_sunday(self):
        cron = CronExpression("0 0 * * 7")
        # 7 应该等同于 0 (Sunday)
        dt = datetime(2026, 4, 19, 0, 0)  # 2026-04-19 是周日
        self.assertTrue(cron.matches_cron_weekday(dt))


class TestCronExpressionMatching(unittest.TestCase):
    """场景 3: CronExpression 时间匹配"""

    def test_every_minute(self):
        cron = CronExpression("* * * * *")
        for h in range(24):
            for m in range(0, 60, 15):
                dt = datetime(2026, 1, 1, h, m)
                self.assertTrue(cron.matches_cron_weekday(dt), f"Should match {dt}")

    def test_specific_time(self):
        cron = CronExpression("30 8 * * *")
        dt_match = datetime(2026, 4, 20, 8, 30)
        dt_no_match = datetime(2026, 4, 20, 8, 31)
        self.assertTrue(cron.matches_cron_weekday(dt_match))
        self.assertFalse(cron.matches_cron_weekday(dt_no_match))

    def test_specific_month(self):
        cron = CronExpression("0 0 1 6 *")
        dt_june = datetime(2026, 6, 1, 0, 0)
        dt_july = datetime(2026, 7, 1, 0, 0)
        self.assertTrue(cron.matches_cron_weekday(dt_june))
        self.assertFalse(cron.matches_cron_weekday(dt_july))

    def test_specific_dow(self):
        cron = CronExpression("0 9 * * 1")  # 周一上午 9 点
        # 2026-04-20 是周一
        dt_monday = datetime(2026, 4, 20, 9, 0)
        dt_tuesday = datetime(2026, 4, 21, 9, 0)
        self.assertTrue(cron.matches_cron_weekday(dt_monday))
        self.assertFalse(cron.matches_cron_weekday(dt_tuesday))

    def test_step_minutes(self):
        cron = CronExpression("*/5 * * * *")
        for m in [0, 5, 10, 15, 55]:
            dt = datetime(2026, 1, 1, 0, m)
            self.assertTrue(cron.matches_cron_weekday(dt), f"Should match minute {m}")
        for m in [1, 3, 7, 13]:
            dt = datetime(2026, 1, 1, 0, m)
            self.assertFalse(cron.matches_cron_weekday(dt), f"Should not match minute {m}")


class TestCronExpressionNextRun(unittest.TestCase):
    """场景 4: CronExpression next_run 计算"""

    def test_every_minute(self):
        cron = CronExpression("* * * * *")
        after = datetime(2026, 4, 20, 14, 0, 0)
        next_run = cron.next_run(after)
        self.assertEqual(next_run, datetime(2026, 4, 20, 14, 1, 0))

    def test_hourly(self):
        cron = CronExpression("0 * * * *")
        after = datetime(2026, 4, 20, 14, 30, 0)
        next_run = cron.next_run(after)
        self.assertEqual(next_run, datetime(2026, 4, 20, 15, 0, 0))

    def test_daily(self):
        cron = CronExpression("0 9 * * *")
        after = datetime(2026, 4, 20, 14, 0, 0)
        next_run = cron.next_run(after)
        self.assertEqual(next_run, datetime(2026, 4, 21, 9, 0, 0))

    def test_weekly(self):
        cron = CronExpression("0 9 * * 1")  # 周一
        after = datetime(2026, 4, 20, 14, 0, 0)  # 周一下午
        next_run = cron.next_run(after)
        # 下一个周一
        self.assertEqual(next_run.weekday(), 0)  # Monday in Python
        self.assertGreater(next_run, after)

    def test_monthly(self):
        cron = CronExpression("0 0 1 * *")
        after = datetime(2026, 4, 20, 0, 0, 0)
        next_run = cron.next_run(after)
        self.assertEqual(next_run.month, 5)
        self.assertEqual(next_run.day, 1)


class TestCronShortcuts(unittest.TestCase):
    """场景 5: Cron 快捷方式"""

    def test_yearly(self):
        cron = CronExpression("@yearly")
        self.assertEqual(cron.raw, "0 0 1 1 *")

    def test_monthly(self):
        cron = CronExpression("@monthly")
        self.assertEqual(cron.raw, "0 0 1 * *")

    def test_weekly(self):
        cron = CronExpression("@weekly")
        self.assertEqual(cron.raw, "0 0 * * 0")

    def test_daily(self):
        cron = CronExpression("@daily")
        self.assertEqual(cron.raw, "0 0 * * *")

    def test_hourly(self):
        cron = CronExpression("@hourly")
        self.assertEqual(cron.raw, "0 * * * *")

    def test_minutely(self):
        cron = CronExpression("@minutely")
        self.assertEqual(cron.raw, "* * * * *")

    def test_unknown_shortcut(self):
        with self.assertRaises(ValueError):
            CronExpression("@invalid")


class TestScheduledTask(unittest.TestCase):
    """场景 6: ScheduledTask 数据模型"""

    def test_creation(self):
        task = ScheduledTask(
            task_id="test-001",
            name="测试",
            task_type="command",
            cron_expr="*/5 * * * *",
            command="echo hello",
        )
        self.assertEqual(task.task_id, "test-001")
        self.assertEqual(task.name, "测试")
        self.assertEqual(task.status, "active")

    def test_auto_created_at(self):
        task = ScheduledTask(task_id="t1", name="t")
        self.assertTrue(task.created_at)

    def test_add_history(self):
        task = ScheduledTask(task_id="t1", name="t")
        record = ExecutionRecord(
            started_at=datetime.now().isoformat(),
            status="success",
            exit_code=0,
            output="hello",
        )
        task.add_history(record)
        self.assertEqual(task.execution_count, 1)
        self.assertEqual(task.last_status, "success")
        self.assertEqual(task.failure_count, 0)

    def test_add_history_failure(self):
        task = ScheduledTask(task_id="t1", name="t")
        record = ExecutionRecord(
            started_at=datetime.now().isoformat(),
            status="failed",
            exit_code=1,
            error="something wrong",
        )
        task.add_history(record)
        self.assertEqual(task.execution_count, 1)
        self.assertEqual(task.last_status, "failed")
        self.assertEqual(task.failure_count, 1)

    def test_history_limit(self):
        task = ScheduledTask(task_id="t1", name="t")
        for i in range(25):
            record = ExecutionRecord(
                started_at=datetime.now().isoformat(),
                status="success",
                exit_code=0,
            )
            task.add_history(record)
        self.assertEqual(len(task.history), 20)
        self.assertEqual(task.execution_count, 25)

    def test_to_dict_from_dict(self):
        task = ScheduledTask(
            task_id="t1",
            name="测试",
            task_type="command",
            cron_expr="0 9 * * *",
            command="echo hi",
        )
        d = task.to_dict()
        task2 = ScheduledTask.from_dict(d)
        self.assertEqual(task2.task_id, task.task_id)
        self.assertEqual(task2.name, task.name)
        self.assertEqual(task2.cron_expr, task.cron_expr)


class TestRetryConfig(unittest.TestCase):
    """场景 7: RetryConfig 重试配置"""

    def test_defaults(self):
        config = RetryConfig()
        self.assertEqual(config.max_retries, 2)
        self.assertEqual(config.backoff_base, 60.0)

    def test_get_backoff(self):
        config = RetryConfig(backoff_base=10.0)
        self.assertEqual(config.get_backoff(0), 10.0)
        self.assertEqual(config.get_backoff(1), 20.0)
        self.assertEqual(config.get_backoff(2), 40.0)

    def test_backoff_max(self):
        config = RetryConfig(backoff_base=100.0, backoff_max=200.0)
        self.assertEqual(config.get_backoff(10), 200.0)  # 100*2^10 = 102400, capped at 200

    def test_serialization(self):
        config = RetryConfig(max_retries=3, backoff_base=30.0)
        d = config.to_dict()
        config2 = RetryConfig.from_dict(d)
        self.assertEqual(config2.max_retries, 3)
        self.assertEqual(config2.backoff_base, 30.0)


class TestTaskScheduler(unittest.TestCase):
    """场景 8: TaskScheduler 核心功能"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.scheduler = TaskScheduler(project_root=self.tmpdir)

    def test_add_task(self):
        task = ScheduledTask(
            task_id="test-add",
            name="添加测试",
            task_type="command",
            cron_expr="*/5 * * * *",
            command="echo test",
        )
        result = self.scheduler.add_task(task)
        self.assertEqual(result.task_id, "test-add")
        self.assertIsNotNone(result.next_run)

    def test_add_task_invalid_cron(self):
        task = ScheduledTask(
            task_id="test-invalid",
            name="无效Cron",
            cron_expr="invalid",
        )
        with self.assertRaises(ValueError):
            self.scheduler.add_task(task)

    def test_remove_task(self):
        task = ScheduledTask(
            task_id="test-rm",
            name="删除测试",
            task_type="command",
            cron_expr="@daily",
            command="echo rm",
        )
        self.scheduler.add_task(task)
        self.assertTrue(self.scheduler.remove_task("test-rm"))
        self.assertFalse(self.scheduler.remove_task("nonexistent"))

    def test_pause_resume(self):
        task = ScheduledTask(
            task_id="test-pause",
            name="暂停测试",
            task_type="command",
            cron_expr="@hourly",
            command="echo pause",
        )
        self.scheduler.add_task(task)
        self.assertTrue(self.scheduler.pause_task("test-pause"))
        self.assertEqual(self.scheduler.get_task("test-pause").status, "paused")
        self.assertTrue(self.scheduler.resume_task("test-pause"))
        self.assertEqual(self.scheduler.get_task("test-pause").status, "active")

    def test_list_tasks(self):
        for i in range(3):
            task = ScheduledTask(
                task_id=f"test-list-{i}",
                name=f"列表测试{i}",
                task_type="command",
                cron_expr="@daily",
                command=f"echo {i}",
            )
            self.scheduler.add_task(task)
        tasks = self.scheduler.list_tasks()
        self.assertEqual(len(tasks), 3)

    def test_list_tasks_by_status(self):
        task1 = ScheduledTask(task_id="t1", name="活跃", cron_expr="@daily", command="echo 1")
        task2 = ScheduledTask(task_id="t2", name="暂停", cron_expr="@daily", command="echo 2")
        self.scheduler.add_task(task1)
        self.scheduler.add_task(task2)
        self.scheduler.pause_task("t2")
        active = self.scheduler.list_tasks(status="active")
        paused = self.scheduler.list_tasks(status="paused")
        self.assertEqual(len(active), 1)
        self.assertEqual(len(paused), 1)

    def test_persistence(self):
        task = ScheduledTask(
            task_id="test-persist",
            name="持久化测试",
            task_type="command",
            cron_expr="@daily",
            command="echo persist",
        )
        self.scheduler.add_task(task)

        # 创建新的 scheduler 实例加载
        scheduler2 = TaskScheduler(project_root=self.tmpdir)
        loaded = scheduler2.get_task("test-persist")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "持久化测试")


class TestTaskSchedulerExecution(unittest.TestCase):
    """场景 9: TaskScheduler 执行功能"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.scheduler = TaskScheduler(project_root=self.tmpdir)

    def test_run_command(self):
        task = ScheduledTask(
            task_id="test-exec",
            name="命令执行",
            task_type="command",
            cron_expr="@daily",
            command="echo hello world",
        )
        self.scheduler.add_task(task)
        record = self.scheduler.run_task_now("test-exec")
        self.assertEqual(record.status, "success")
        self.assertEqual(record.exit_code, 0)
        self.assertIn("hello world", record.output)

    def test_run_failed_command(self):
        task = ScheduledTask(
            task_id="test-fail",
            name="失败命令",
            task_type="command",
            cron_expr="@daily",
            command="exit 1",
        )
        self.scheduler.add_task(task)
        record = self.scheduler.run_task_now("test-fail")
        self.assertEqual(record.status, "failed")
        self.assertEqual(record.exit_code, 1)

    def test_execution_history(self):
        task = ScheduledTask(
            task_id="test-hist",
            name="历史测试",
            task_type="command",
            cron_expr="@daily",
            command="echo history",
        )
        self.scheduler.add_task(task)
        self.scheduler.run_task_now("test-hist")
        self.scheduler.run_task_now("test-hist")

        loaded = self.scheduler.get_task("test-hist")
        self.assertEqual(loaded.execution_count, 2)
        self.assertEqual(len(loaded.history), 2)

    def test_nonexistent_task(self):
        record = self.scheduler.run_task_now("nonexistent")
        self.assertIsNone(record)

    def test_stats(self):
        task = ScheduledTask(
            task_id="test-stats",
            name="统计测试",
            task_type="command",
            cron_expr="@daily",
            command="echo stats",
        )
        self.scheduler.add_task(task)
        stats = self.scheduler.get_stats()
        self.assertEqual(stats['total_tasks'], 1)
        self.assertEqual(stats['active_tasks'], 1)
        self.assertEqual(stats['daemon_running'], False)


class TestTaskSchedulerRetry(unittest.TestCase):
    """场景 10: 失败重试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.scheduler = TaskScheduler(project_root=self.tmpdir)

    def test_no_retry_on_success(self):
        task = ScheduledTask(
            task_id="test-no-retry",
            name="成功不重试",
            task_type="command",
            cron_expr="@daily",
            command="echo ok",
            retry_config={"max_retries": 2, "backoff_base": 0.1, "backoff_max": 1.0},
        )
        self.scheduler.add_task(task)
        record = self.scheduler.run_task_now("test-no-retry")
        self.assertEqual(record.status, "success")
        self.assertEqual(record.retry_count, 0)

    def test_retry_on_failure(self):
        # 使用一个总是失败的命令
        task = ScheduledTask(
            task_id="test-retry",
            name="失败重试",
            task_type="command",
            cron_expr="@daily",
            command="exit 1",
            retry_config={"max_retries": 2, "backoff_base": 0.1, "backoff_max": 1.0},
        )
        self.scheduler.add_task(task)
        record = self.scheduler.run_task_now("test-retry")
        # 2 次重试后仍然失败
        self.assertEqual(record.status, "failed")
        self.assertEqual(record.retry_count, 2)

    def test_zero_retries(self):
        task = ScheduledTask(
            task_id="test-zero-retry",
            name="零重试",
            task_type="command",
            cron_expr="@daily",
            command="exit 1",
            retry_config={"max_retries": 0, "backoff_base": 0.1, "backoff_max": 1.0},
        )
        self.scheduler.add_task(task)
        record = self.scheduler.run_task_now("test-zero-retry")
        self.assertEqual(record.status, "failed")
        self.assertEqual(record.retry_count, 0)


class TestNotificationManager(unittest.TestCase):
    """场景 11: 通知管理"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.notifier = NotificationManager(project_root=self.tmpdir)

    def test_notify_creates_file(self):
        notification = Notification(
            task_id="test-001",
            task_name="测试",
            level=NotificationLevel.INFO,
            message="任务执行成功",
        )
        self.notifier.notify(notification)

        # 检查通知文件
        notif_dir = Path(self.tmpdir) / ".ai" / "notifications"
        notif_files = list(notif_dir.glob("*.jsonl"))
        self.assertEqual(len(notif_files), 1)

        # 检查内容
        content = notif_files[0].read_text(encoding='utf-8').strip()
        data = json.loads(content)
        self.assertEqual(data['task_id'], "test-001")
        self.assertEqual(data['level'], "info")

    def test_custom_handler(self):
        received = []
        self.notifier.add_handler(lambda n: received.append(n))

        notification = Notification(
            task_id="test-002",
            task_name="自定义",
            level=NotificationLevel.WARNING,
            message="警告通知",
        )
        self.notifier.notify(notification)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].task_id, "test-002")

    def test_notify_on_failure_only(self):
        """测试 notify_on='on_failure' 只在失败时通知"""
        scheduler = TaskScheduler(project_root=self.tmpdir)
        task = ScheduledTask(
            task_id="test-notify-filter",
            name="通知过滤",
            task_type="command",
            cron_expr="@daily",
            command="echo ok",
            notify_on="on_failure",
        )
        scheduler.add_task(task)
        record = scheduler.run_task_now("test-notify-filter")
        self.assertEqual(record.status, "success")

        # 不应该产生通知文件（因为成功且 notify_on=on_failure）
        notif_dir = Path(self.tmpdir) / ".ai" / "notifications"
        notif_files = list(notif_dir.glob("*.jsonl"))
        self.assertEqual(len(notif_files), 0)


class TestCheckAndRun(unittest.TestCase):
    """场景 12: check_and_run 调度检查"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.scheduler = TaskScheduler(project_root=self.tmpdir)

    def test_check_runs_matching_task(self):
        # 使用每分钟匹配的 cron
        task = ScheduledTask(
            task_id="test-check",
            name="检查测试",
            task_type="command",
            cron_expr="* * * * *",
            command="echo check",
        )
        self.scheduler.add_task(task)
        self.scheduler.check_and_run()

        loaded = self.scheduler.get_task("test-check")
        self.assertEqual(loaded.execution_count, 1)

    def test_check_skips_paused_task(self):
        task = ScheduledTask(
            task_id="test-skip",
            name="跳过测试",
            task_type="command",
            cron_expr="* * * * *",
            command="echo skip",
        )
        self.scheduler.add_task(task)
        self.scheduler.pause_task("test-skip")
        self.scheduler.check_and_run()

        loaded = self.scheduler.get_task("test-skip")
        self.assertEqual(loaded.execution_count, 0)


class TestExecutionRecord(unittest.TestCase):
    """场景 13: ExecutionRecord 数据模型"""

    def test_creation(self):
        record = ExecutionRecord(
            started_at="2026-04-20T14:00:00",
            finished_at="2026-04-20T14:00:01",
            status="success",
            exit_code=0,
            output="hello",
        )
        self.assertEqual(record.status, "success")
        self.assertEqual(record.exit_code, 0)

    def test_serialization(self):
        record = ExecutionRecord(
            started_at="2026-04-20T14:00:00",
            status="success",
            exit_code=0,
        )
        d = record.to_dict()
        record2 = ExecutionRecord.from_dict(d)
        self.assertEqual(record2.started_at, record.started_at)
        self.assertEqual(record2.status, record.status)


class TestAgentExecutor(unittest.TestCase):
    """场景 14: AgentExecutor 执行器"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.executor = AgentExecutor(project_root=self.tmpdir, timeout=10)

    def test_execute_command(self):
        task = ScheduledTask(
            task_id="test-exec",
            name="执行",
            task_type="command",
            command="echo exec",
        )
        record = self.executor.execute(task)
        self.assertEqual(record.status, "success")
        self.assertIn("exec", record.output)

    def test_execute_timeout(self):
        executor = AgentExecutor(project_root=self.tmpdir, timeout=1)
        task = ScheduledTask(
            task_id="test-timeout",
            name="超时",
            task_type="command",
            command="sleep 10",
        )
        record = executor.execute(task)
        self.assertEqual(record.status, "timeout")

    def test_execute_invalid_type(self):
        task = ScheduledTask(
            task_id="test-invalid",
            name="无效类型",
            task_type="nonexistent",
        )
        record = self.executor.execute(task)
        self.assertEqual(record.status, "failed")

    def test_execute_python_missing_module(self):
        task = ScheduledTask(
            task_id="test-py",
            name="Python",
            task_type="python",
            python_module="nonexistent_module",
            python_function="nonexistent_func",
        )
        record = self.executor.execute(task)
        self.assertEqual(record.status, "failed")


if __name__ == "__main__":
    unittest.main(verbosity=2)

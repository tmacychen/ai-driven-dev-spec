#!/usr/bin/env python3
"""
ADDS P2-2 执行后端隔离测试

测试场景：
1. ExecutionContext 数据模型
2. ExecutionResult 数据模型
3. ResourceLimits 资源限制
4. LocalBackend 本地执行
5. DockerBackend 检测与接口
6. SSHBackend 检测与接口
7. BackendFactory 工厂
8. SandboxPolicy 安全策略
9. ExecutionManager 统一管理
10. SSHConfig 配置
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from executor_backend import (
    ExecutionContext, ExecutionResult, ExecutionStatus,
    ResourceLimits, FileTransfer, ExecutionBackend,
    LocalBackend, DockerBackend, SSHBackend, SSHConfig,
    BackendFactory, ExecutionManager, SandboxPolicy,
)


class TestExecutionContext(unittest.TestCase):
    """场景 1: ExecutionContext 数据模型"""

    def test_creation(self):
        ctx = ExecutionContext(command="echo hello")
        self.assertEqual(ctx.command, "echo hello")
        self.assertEqual(ctx.work_dir, ".")
        self.assertIsInstance(ctx.env, dict)
        self.assertIsInstance(ctx.files, list)

    def test_with_env(self):
        ctx = ExecutionContext(
            command="echo $NAME",
            env={"NAME": "ADDS"},
        )
        self.assertEqual(ctx.env["NAME"], "ADDS")

    def test_get_resource_limits(self):
        ctx = ExecutionContext(
            command="echo test",
            resource_limits={"timeout": 300, "memory_limit": "256m"},
        )
        limits = ctx.get_resource_limits()
        self.assertEqual(limits.timeout, 300)
        self.assertEqual(limits.memory_limit, "256m")

    def test_default_resource_limits(self):
        ctx = ExecutionContext(command="echo test")
        limits = ctx.get_resource_limits()
        self.assertEqual(limits.timeout, 600)

    def test_serialization(self):
        ctx = ExecutionContext(
            command="echo test",
            work_dir="/tmp",
            env={"KEY": "VALUE"},
        )
        d = ctx.to_dict()
        ctx2 = ExecutionContext.from_dict(d)
        self.assertEqual(ctx2.command, ctx.command)
        self.assertEqual(ctx2.work_dir, ctx.work_dir)
        self.assertEqual(ctx2.env["KEY"], "VALUE")

    def test_file_transfers(self):
        ctx = ExecutionContext(
            command="cat /remote/file.txt",
            files=[FileTransfer(local_path="/local/file.txt", remote_path="/remote/file.txt")],
        )
        self.assertEqual(len(ctx.files), 1)
        self.assertEqual(ctx.files[0].local_path, "/local/file.txt")


class TestExecutionResult(unittest.TestCase):
    """场景 2: ExecutionResult 数据模型"""

    def test_success(self):
        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            exit_code=0,
            stdout="hello",
            duration=0.5,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.exit_code, 0)

    def test_failed(self):
        result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            exit_code=1,
            stderr="error",
        )
        self.assertFalse(result.success)

    def test_timeout(self):
        result = ExecutionResult(
            status=ExecutionStatus.TIMEOUT,
            exit_code=-1,
        )
        self.assertFalse(result.success)

    def test_summary(self):
        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            exit_code=0,
            stdout="hello world",
            duration=0.5,
            backend="local",
        )
        summary = result.summary()
        self.assertIn("success", summary)
        self.assertIn("local", summary)

    def test_serialization(self):
        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            exit_code=0,
            stdout="test",
            duration=1.5,
            backend="local",
        )
        d = result.to_dict()
        result2 = ExecutionResult.from_dict(d)
        self.assertEqual(result2.status, result.status)
        self.assertEqual(result2.exit_code, result.exit_code)


class TestResourceLimits(unittest.TestCase):
    """场景 3: ResourceLimits 资源限制"""

    def test_defaults(self):
        limits = ResourceLimits()
        self.assertEqual(limits.timeout, 600)
        self.assertTrue(limits.network_access)
        self.assertIsNone(limits.cpu_limit)

    def test_custom(self):
        limits = ResourceLimits(
            cpu_limit="1.0",
            memory_limit="512m",
            timeout=300,
            network_access=False,
        )
        self.assertEqual(limits.cpu_limit, "1.0")
        self.assertEqual(limits.memory_limit, "512m")
        self.assertFalse(limits.network_access)

    def test_docker_args(self):
        limits = ResourceLimits(
            cpu_limit="1.0",
            memory_limit="512m",
            network_access=False,
        )
        args = limits.to_docker_args()
        self.assertIn("--cpus", args)
        self.assertIn("1.0", args)
        self.assertIn("-m", args)
        self.assertIn("512m", args)
        self.assertIn("--network=none", args)

    def test_empty_docker_args(self):
        limits = ResourceLimits()
        args = limits.to_docker_args()
        self.assertEqual(len(args), 0)  # 默认无限制

    def test_serialization(self):
        limits = ResourceLimits(cpu_limit="2.0", memory_limit="1g")
        d = limits.to_dict()
        limits2 = ResourceLimits.from_dict(d)
        self.assertEqual(limits2.cpu_limit, "2.0")


class TestLocalBackend(unittest.TestCase):
    """场景 4: LocalBackend 本地执行"""

    def setUp(self):
        self.backend = LocalBackend()

    def test_name(self):
        self.assertEqual(self.backend.name, "local")

    def test_is_available(self):
        self.assertTrue(self.backend.is_available)

    def test_execute_simple(self):
        ctx = ExecutionContext(command="echo hello")
        result = self.backend.execute(ctx)
        self.assertTrue(result.success)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hello", result.stdout)

    def test_execute_with_env(self):
        ctx = ExecutionContext(
            command="echo $ADDS_TEST_VAR",
            env={"ADDS_TEST_VAR": "test_value"},
        )
        result = self.backend.execute(ctx)
        self.assertTrue(result.success)
        self.assertIn("test_value", result.stdout)

    def test_execute_failed(self):
        ctx = ExecutionContext(command="exit 42")
        result = self.backend.execute(ctx)
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 42)

    def test_execute_timeout(self):
        ctx = ExecutionContext(
            command="sleep 10",
            resource_limits={"timeout": 1},
        )
        result = self.backend.execute(ctx)
        self.assertEqual(result.status, ExecutionStatus.TIMEOUT)

    def test_execute_with_workdir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ExecutionContext(
                command="pwd",
                work_dir=tmpdir,
            )
            result = self.backend.execute(ctx)
            self.assertTrue(result.success)
            self.assertIn(tmpdir, result.stdout)

    def test_execute_with_stdin(self):
        ctx = ExecutionContext(
            command="cat",
            stdin="hello stdin",
        )
        result = self.backend.execute(ctx)
        self.assertTrue(result.success)
        self.assertIn("hello stdin", result.stdout)

    def test_health_check(self):
        is_healthy, message = self.backend.health_check()
        self.assertTrue(is_healthy)

    def test_duration(self):
        ctx = ExecutionContext(command="sleep 0.1")
        result = self.backend.execute(ctx)
        self.assertGreater(result.duration, 0.05)


class TestDockerBackend(unittest.TestCase):
    """场景 5: DockerBackend 检测与接口"""

    def test_name(self):
        backend = DockerBackend()
        self.assertEqual(backend.name, "docker")

    def test_is_available(self):
        # CI 环境通常没有 Docker
        backend = DockerBackend()
        # 只要不崩溃就行
        _ = backend.is_available

    def test_custom_image(self):
        backend = DockerBackend(image="node:18")
        self.assertEqual(backend.image, "node:18")


class TestSSHBackend(unittest.TestCase):
    """场景 6: SSHBackend 检测与接口"""

    def test_name(self):
        backend = SSHBackend()
        self.assertEqual(backend.name, "ssh")

    def test_is_available_no_host(self):
        backend = SSHBackend()
        # 没有 host 配置时不可用
        self.assertFalse(backend.is_available)


class TestSSHConfig(unittest.TestCase):
    """场景 10: SSHConfig 配置"""

    def test_defaults(self):
        config = SSHConfig()
        self.assertEqual(config.port, 22)
        self.assertEqual(config.host, "")

    def test_to_ssh_args(self):
        config = SSHConfig(
            host="example.com",
            user="admin",
            port=2222,
            key_path="~/.ssh/id_rsa",
        )
        args = config.to_ssh_args()
        self.assertIn("ssh", args)
        self.assertIn("-p", args)
        self.assertIn("2222", args)
        self.assertIn("-i", args)
        self.assertIn("admin@example.com", args)

    def test_serialization_hides_password(self):
        config = SSHConfig(host="example.com", password="secret123")
        d = config.to_dict()
        self.assertEqual(d['password'], '***')

    def test_from_dict_preserves_password(self):
        config = SSHConfig(host="example.com", password="secret123")
        d = config.to_dict()
        # from_dict 用原始数据
        d['password'] = 'secret123'
        config2 = SSHConfig.from_dict(d)
        self.assertEqual(config2.password, 'secret123')


class TestBackendFactory(unittest.TestCase):
    """场景 7: BackendFactory 工厂"""

    def test_create_local(self):
        backend = BackendFactory.create("local")
        self.assertIsInstance(backend, LocalBackend)

    def test_create_docker(self):
        backend = BackendFactory.create("docker")
        self.assertIsInstance(backend, DockerBackend)

    def test_create_ssh(self):
        backend = BackendFactory.create("ssh", host="example.com")
        self.assertIsInstance(backend, SSHBackend)

    def test_unknown_backend(self):
        with self.assertRaises(ValueError):
            BackendFactory.create("nonexistent")

    def test_list_backends(self):
        backends = BackendFactory.list_backends()
        self.assertIn("local", backends)
        self.assertIn("docker", backends)
        self.assertIn("ssh", backends)

    def test_detect_available(self):
        available = BackendFactory.detect_available(".")
        self.assertIn("local", available)
        self.assertTrue(available["local"])

    def test_register_custom(self):
        class MockBackend(ExecutionBackend):
            def __init__(self, project_root=".", **kwargs):
                pass
            @property
            def name(self): return "mock"
            @property
            def is_available(self): return True
            def execute(self, ctx): return ExecutionResult(status="success")

        BackendFactory.register("mock", MockBackend)
        self.assertIn("mock", BackendFactory.list_backends())
        backend = BackendFactory.create("mock")
        self.assertIsInstance(backend, MockBackend)

        # 清理
        del BackendFactory._registry["mock"]


class TestSandboxPolicy(unittest.TestCase):
    """场景 8: SandboxPolicy 安全策略"""

    def test_safe_command(self):
        level, msg = SandboxPolicy.check_command("echo hello")
        self.assertEqual(level, "safe")

    def test_safe_ls(self):
        level, msg = SandboxPolicy.check_command("ls -la")
        self.assertEqual(level, "safe")

    def test_dangerous_rm_rf(self):
        level, msg = SandboxPolicy.check_command("rm -rf /tmp/test_dir_cleanup")
        self.assertEqual(level, "dangerous")

    def test_dangerous_sudo_rm(self):
        level, msg = SandboxPolicy.check_command("sudo rm -rf /tmp/test")
        self.assertEqual(level, "dangerous")

    def test_dangerous_mkfs(self):
        level, msg = SandboxPolicy.check_command("dd if=/dev/zero of=/dev/sda")
        self.assertEqual(level, "dangerous")

    def test_high_risk_sudo(self):
        level, msg = SandboxPolicy.check_command("sudo apt update")
        self.assertEqual(level, "high_risk")

    def test_high_risk_pip_install(self):
        level, msg = SandboxPolicy.check_command("pip install requests")
        self.assertEqual(level, "high_risk")

    def test_high_risk_git_force(self):
        level, msg = SandboxPolicy.check_command("git push --force origin main")
        self.assertEqual(level, "high_risk")

    def test_default_limits(self):
        limits = SandboxPolicy.get_default_limits()
        self.assertEqual(limits.cpu_limit, "1.0")
        self.assertEqual(limits.memory_limit, "512m")

    def test_strict_limits(self):
        limits = SandboxPolicy.get_strict_limits()
        self.assertEqual(limits.cpu_limit, "0.5")
        self.assertFalse(limits.network_access)


class TestExecutionManager(unittest.TestCase):
    """场景 9: ExecutionManager 统一管理"""

    def setUp(self):
        self.mgr = ExecutionManager(project_root=".", backend_name="local")

    def test_execute_simple(self):
        result = self.mgr.execute("echo managed")
        self.assertTrue(result.success)
        self.assertIn("managed", result.stdout)

    def test_execute_with_env(self):
        result = self.mgr.execute(
            "echo $ADDS_TEST",
            env={"ADDS_TEST": "hello"},
        )
        self.assertTrue(result.success)
        self.assertIn("hello", result.stdout)

    def test_execute_blocked_by_sandbox(self):
        result = self.mgr.execute("dd if=/dev/zero of=/dev/sda", check_safety=True)
        self.assertFalse(result.success)
        self.assertIn("blocked", result.error.lower())

    def test_execute_skip_safety(self):
        # 跳过安全检查时，命令仍然会执行失败（因为权限不够）
        result = self.mgr.execute("echo skip_safety", check_safety=False)
        self.assertTrue(result.success)

    def test_get_available_backends(self):
        available = self.mgr.get_available_backends()
        self.assertIn("local", available)
        self.assertTrue(available["local"])

    def test_switch_backend(self):
        self.mgr.switch_backend("local")
        result = self.mgr.execute("echo switched")
        self.assertTrue(result.success)

    def test_health_check(self):
        results = self.mgr.health_check()
        self.assertIn("local", results)
        is_healthy, _ = results["local"]
        self.assertTrue(is_healthy)

    def test_execute_with_workdir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.mgr.execute("pwd", work_dir=tmpdir)
            self.assertTrue(result.success)
            self.assertIn(tmpdir, result.stdout)


class TestFileTransfer(unittest.TestCase):
    """场景: FileTransfer 文件传输"""

    def test_creation(self):
        ft = FileTransfer(
            local_path="/local/file.txt",
            remote_path="/remote/file.txt",
        )
        self.assertEqual(ft.local_path, "/local/file.txt")
        self.assertEqual(ft.direction, "upload")

    def test_download(self):
        ft = FileTransfer(
            local_path="/local/file.txt",
            remote_path="/remote/file.txt",
            direction="download",
        )
        self.assertEqual(ft.direction, "download")

    def test_serialization(self):
        ft = FileTransfer(local_path="/a", remote_path="/b")
        d = ft.to_dict()
        ft2 = FileTransfer.from_dict(d)
        self.assertEqual(ft2.local_path, "/a")


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""
ADDS P2-3 多平台通信网关测试

测试场景：
1. MessageEnvelope 数据模型
2. AsyncMessageQueue 优先级队列
3. CLIChannel 命令行渠道
4. FileChannel 文件渠道
5. WebhookChannel Webhook 渠道
6. MessageGateway 路由
7. MessageGateway 处理器
8. 消息历史记录
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gateway import (
    MessageEnvelope, MessageType, MessagePriority, MessageStatus,
    Channel, CLIChannel, FileChannel, WebhookChannel,
    AsyncMessageQueue, MessageGateway,
)


class TestMessageEnvelope(unittest.TestCase):
    """场景 1: MessageEnvelope 数据模型"""

    def test_creation(self):
        msg = MessageEnvelope(
            message_type=MessageType.COMMAND,
            subject="测试",
            body="测试正文",
        )
        self.assertEqual(msg.message_type, "command")
        self.assertTrue(msg.message_id.startswith("msg-"))
        self.assertTrue(msg.created_at)

    def test_auto_id(self):
        msg1 = MessageEnvelope(subject="a")
        msg2 = MessageEnvelope(subject="b")
        self.assertNotEqual(msg1.message_id, msg2.message_id)

    def test_is_urgent(self):
        msg = MessageEnvelope(priority=MessagePriority.URGENT)
        self.assertTrue(msg.is_urgent)
        msg_normal = MessageEnvelope(priority=MessagePriority.NORMAL)
        self.assertFalse(msg_normal.is_urgent)

    def test_serialization(self):
        msg = MessageEnvelope(
            message_type=MessageType.NOTIFICATION,
            priority=MessagePriority.HIGH,
            subject="序列化测试",
            body="测试内容",
            source="test",
            tags=["test", "unit"],
        )
        d = msg.to_dict()
        msg2 = MessageEnvelope.from_dict(d)
        self.assertEqual(msg2.subject, msg.subject)
        self.assertEqual(msg2.message_type, msg.message_type)
        self.assertEqual(msg2.tags, msg.tags)

    def test_json_roundtrip(self):
        msg = MessageEnvelope(
            message_type=MessageType.COMMAND,
            subject="JSON测试",
        )
        json_str = msg.to_json()
        msg2 = MessageEnvelope.from_json(json_str)
        self.assertEqual(msg2.message_id, msg.message_id)
        self.assertEqual(msg2.subject, msg.subject)

    def test_summary(self):
        msg = MessageEnvelope(
            message_type=MessageType.COMMAND,
            priority=MessagePriority.HIGH,
            subject="摘要测试",
            source="cli",
        )
        summary = msg.summary()
        self.assertIn("command", summary)
        self.assertIn("high", summary)
        self.assertIn("摘要测试", summary)

    def test_reply_to(self):
        original = MessageEnvelope(subject="原始消息")
        reply = MessageEnvelope(
            subject="回复",
            reply_to=original.message_id,
        )
        self.assertEqual(reply.reply_to, original.message_id)

    def test_correlation_id(self):
        msg = MessageEnvelope(
            subject="关联消息",
            correlation_id="corr-123",
        )
        self.assertEqual(msg.correlation_id, "corr-123")


class TestAsyncMessageQueue(unittest.TestCase):
    """场景 2: AsyncMessageQueue 优先级队列"""

    def test_enqueue_dequeue(self):
        q = AsyncMessageQueue()
        msg = MessageEnvelope(subject="测试")
        q.enqueue(msg)
        self.assertEqual(q.size(), 1)
        result = q.dequeue()
        self.assertEqual(result.message_id, msg.message_id)
        self.assertTrue(q.is_empty())

    def test_priority_ordering(self):
        q = AsyncMessageQueue()
        q.enqueue(MessageEnvelope(priority=MessagePriority.LOW, subject="低"))
        q.enqueue(MessageEnvelope(priority=MessagePriority.URGENT, subject="紧急"))
        q.enqueue(MessageEnvelope(priority=MessagePriority.NORMAL, subject="普通"))
        q.enqueue(MessageEnvelope(priority=MessagePriority.HIGH, subject="高"))

        # 应该按优先级出队
        first = q.dequeue()
        self.assertEqual(first.subject, "紧急")
        second = q.dequeue()
        self.assertEqual(second.subject, "高")
        third = q.dequeue()
        self.assertEqual(third.subject, "普通")
        fourth = q.dequeue()
        self.assertEqual(fourth.subject, "低")

    def test_max_size(self):
        q = AsyncMessageQueue(max_size=3)
        for i in range(5):
            q.enqueue(MessageEnvelope(subject=f"msg{i}"))
        # 队列应该不超过 max_size
        self.assertLessEqual(q.size(), 3)

    def test_peek(self):
        q = AsyncMessageQueue()
        msg = MessageEnvelope(priority=MessagePriority.URGENT, subject="紧急")
        q.enqueue(msg)
        peeked = q.peek()
        self.assertEqual(peeked.message_id, msg.message_id)
        # peek 不移除消息
        self.assertEqual(q.size(), 1)

    def test_register_handler(self):
        q = AsyncMessageQueue()
        processed = []
        q.register_handler("command", lambda m: processed.append(m.message_id))

        msg = MessageEnvelope(message_type=MessageType.COMMAND, subject="测试")
        q.enqueue(msg)
        q.process_next()

        self.assertEqual(len(processed), 1)

    def test_process_all(self):
        q = AsyncMessageQueue()
        for i in range(5):
            q.enqueue(MessageEnvelope(subject=f"msg{i}"))
        count = q.process_all()
        self.assertEqual(count, 5)
        self.assertTrue(q.is_empty())

    def test_stats(self):
        q = AsyncMessageQueue()
        q.enqueue(MessageEnvelope(message_type=MessageType.COMMAND, subject="c1"))
        q.enqueue(MessageEnvelope(message_type=MessageType.NOTIFICATION, subject="n1"))
        stats = q.get_stats()
        self.assertEqual(stats['total'], 2)


class TestCLIChannel(unittest.TestCase):
    """场景 3: CLIChannel 命令行渠道"""

    def test_name(self):
        ch = CLIChannel()
        self.assertEqual(ch.name, "cli")

    def test_is_available(self):
        ch = CLIChannel()
        self.assertTrue(ch.is_available)

    def test_send_default(self):
        """默认发送（打印到 stdout）"""
        ch = CLIChannel()
        msg = MessageEnvelope(subject="CLI测试")
        result = ch.send(msg)
        self.assertTrue(result)

    def test_inject_and_receive(self):
        ch = CLIChannel()
        msg = MessageEnvelope(subject="注入测试")
        ch.inject(msg)
        received = ch.receive()
        self.assertIsNotNone(received)
        self.assertEqual(received.subject, "注入测试")
        self.assertEqual(received.source, "cli")

    def test_receive_empty(self):
        ch = CLIChannel()
        result = ch.receive()
        self.assertIsNone(result)


class TestFileChannel(unittest.TestCase):
    """场景 4: FileChannel 文件渠道"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.inbox = Path(self.tmpdir) / "inbox"
        self.outbox = Path(self.tmpdir) / "outbox"
        self.channel = FileChannel(
            project_root=self.tmpdir,
            inbox_dir=str(self.inbox),
            outbox_dir=str(self.outbox),
        )

    def test_name(self):
        self.assertEqual(self.channel.name, "file")

    def test_is_available(self):
        self.assertTrue(self.channel.is_available)

    def test_send_creates_file(self):
        msg = MessageEnvelope(subject="文件测试", body="测试内容")
        result = self.channel.send(msg)
        self.assertTrue(result)
        # 检查文件
        files = list(self.outbox.glob("*.json"))
        self.assertEqual(len(files), 1)

    def test_receive_from_inbox(self):
        # 手动创建 inbox 消息
        self.inbox.mkdir(parents=True, exist_ok=True)
        msg = MessageEnvelope(subject="收件测试", body="收件内容")
        filepath = self.inbox / f"{msg.message_id}.json"
        filepath.write_text(msg.to_json(), encoding='utf-8')

        received = self.channel.receive()
        self.assertIsNotNone(received)
        self.assertEqual(received.subject, "收件测试")
        # 文件应该被删除
        self.assertFalse(filepath.exists())

    def test_receive_empty(self):
        result = self.channel.receive()
        self.assertIsNone(result)

    def test_roundtrip(self):
        """发送到 outbox，手动移到 inbox，再接收"""
        msg = MessageEnvelope(subject="往返测试", body="往返内容")
        self.channel.send(msg)

        # 移动 outbox → inbox
        self.inbox.mkdir(parents=True, exist_ok=True)
        for f in self.outbox.glob("*.json"):
            dest = self.inbox / f.name
            f.rename(dest)

        received = self.channel.receive()
        self.assertIsNotNone(received)
        self.assertEqual(received.subject, "往返测试")


class TestWebhookChannel(unittest.TestCase):
    """场景 5: WebhookChannel Webhook 渠道"""

    def test_name(self):
        ch = WebhookChannel()
        self.assertEqual(ch.name, "webhook")

    def test_is_available(self):
        ch = WebhookChannel()
        self.assertTrue(ch.is_available)

    def test_receive_from_incoming(self):
        ch = WebhookChannel()
        msg = MessageEnvelope(subject="Webhook测试")
        ch._add_incoming(msg)
        received = ch.receive()
        self.assertIsNotNone(received)
        self.assertEqual(received.subject, "Webhook测试")

    def test_receive_empty(self):
        ch = WebhookChannel()
        result = ch.receive()
        self.assertIsNone(result)

    def test_incoming_limit(self):
        ch = WebhookChannel()
        for i in range(110):
            ch._add_incoming(MessageEnvelope(subject=f"msg{i}"))
        # 队列应该被截断
        self.assertLessEqual(len(ch._incoming), 100)


class TestMessageGateway(unittest.TestCase):
    """场景 6+7: MessageGateway 路由和处理器"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gateway = MessageGateway(project_root=self.tmpdir)
        self.inbox = Path(self.tmpdir) / "inbox"
        self.outbox = Path(self.tmpdir) / "outbox"
        self.file_channel = FileChannel(
            project_root=self.tmpdir,
            inbox_dir=str(self.inbox),
            outbox_dir=str(self.outbox),
        )
        self.gateway.register_channel(self.file_channel)
        self.gateway.register_channel(WebhookChannel(project_root=self.tmpdir))

    def test_register_channel(self):
        self.assertIn("file", self.gateway.channels)
        self.assertIn("cli", self.gateway.channels)

    def test_unregister_channel(self):
        self.assertTrue(self.gateway.unregister_channel("file"))
        self.assertFalse(self.gateway.unregister_channel("nonexistent"))

    def test_send_to_channel(self):
        msg = MessageEnvelope(subject="网关发送", body="测试")
        result = self.gateway.send(msg, channel_name="file")
        self.assertTrue(result)
        # 检查文件
        files = list(self.outbox.glob("*.json"))
        self.assertEqual(len(files), 1)

    def test_send_broadcast(self):
        msg = MessageEnvelope(subject="广播测试")
        result = self.gateway.send(msg)
        # 广播到所有渠道，部分渠道可能失败（如 webhook 无 outbound URL）
        # 但至少 cli 渠道应该成功，且历史应该记录
        history = self.gateway.get_recent_history()
        self.assertGreater(len(history), 0)

    def test_send_to_unknown_channel(self):
        msg = MessageEnvelope(subject="未知渠道")
        result = self.gateway.send(msg, channel_name="nonexistent")
        self.assertFalse(result)

    def test_receive_from_channel(self):
        # 创建 inbox 消息
        self.inbox.mkdir(parents=True, exist_ok=True)
        msg = MessageEnvelope(subject="接收测试", body="内容")
        filepath = self.inbox / f"{msg.message_id}.json"
        filepath.write_text(msg.to_json(), encoding='utf-8')

        received = self.gateway.receive(channel_name="file")
        self.assertIsNotNone(received)
        self.assertEqual(received.subject, "接收测试")

    def test_route(self):
        msg = MessageEnvelope(subject="路由测试", target="cli")
        channel = self.gateway.route(msg)
        self.assertEqual(channel, "cli")

    def test_route_with_prefix(self):
        msg = MessageEnvelope(subject="路由测试", target="webhook:http://example.com")
        channel = self.gateway.route(msg)
        self.assertEqual(channel, "webhook")

    def test_route_unknown(self):
        msg = MessageEnvelope(subject="路由测试", target="nonexistent")
        channel = self.gateway.route(msg)
        self.assertIsNone(channel)

    def test_register_handler(self):
        processed = []
        self.gateway.register_handler("command", lambda m: processed.append(m.message_id))
        self.assertIn("command", self.gateway._handlers)

    def test_process_message(self):
        processed = []
        self.gateway.register_handler("notification", lambda m: processed.append(m.message_id))
        msg = MessageEnvelope(message_type=MessageType.NOTIFICATION, subject="处理测试")
        result = self.gateway.process_message(msg)
        self.assertTrue(result)
        self.assertEqual(len(processed), 1)

    def test_process_no_handler(self):
        msg = MessageEnvelope(message_type=MessageType.EVENT, subject="无处理器")
        result = self.gateway.process_message(msg)
        self.assertFalse(result)


class TestMessageHistory(unittest.TestCase):
    """场景 8: 消息历史记录"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gateway = MessageGateway(project_root=self.tmpdir)

    def test_history_recorded(self):
        msg = MessageEnvelope(subject="历史测试")
        self.gateway.send(msg, channel_name="cli")
        history = self.gateway.get_recent_history()
        self.assertGreater(len(history), 0)

    def test_history_limit(self):
        for i in range(25):
            msg = MessageEnvelope(subject=f"历史{i}")
            self.gateway.send(msg, channel_name="cli")
        history = self.gateway.get_recent_history(limit=10)
        self.assertEqual(len(history), 10)

    def test_stats(self):
        msg = MessageEnvelope(subject="统计测试")
        self.gateway.send(msg, channel_name="cli")
        stats = self.gateway.get_stats()
        self.assertIn('channels', stats)
        self.assertIn('queue', stats)
        self.assertGreater(stats['history_count'], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

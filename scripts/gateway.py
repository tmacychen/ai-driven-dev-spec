#!/usr/bin/env python3
"""
ADDS 多平台通信网关 (P2-3)

统一消息网关，支持 Webhook/API/IM 等多平台通信。

核心组件：
- MessageGateway: 网关核心（消息路由 + 协议转换）
- Channel: 抽象基类（统一消息接口）
- WebhookChannel: HTTP Webhook 接收
- CLIChannel: CLI 命令行交互
- MessageEnvelope: 标准化消息格式
- AsyncMessageQueue: 异步消息处理队列
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# MessageEnvelope — 标准化消息格式
# ═══════════════════════════════════════════════════════════════

class MessageType(str, Enum):
    """消息类型"""
    COMMAND = "command"          # 命令消息（触发 Agent 执行）
    NOTIFICATION = "notification"  # 通知消息（执行结果/调度通知）
    QUERY = "query"              # 查询消息（请求信息）
    RESPONSE = "response"        # 响应消息
    EVENT = "event"              # 事件消息（状态变更）
    APPROVAL = "approval"        # 审批消息（权限请求）


class MessagePriority(str, Enum):
    """消息优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageStatus(str, Enum):
    """消息状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class MessageEnvelope:
    """标准化消息信封

    所有通过网关的消息都必须封装在此格式中。
    """
    message_id: str = ""             # 唯一消息 ID
    message_type: str = "command"    # MessageType
    priority: str = "normal"         # MessagePriority
    status: str = "pending"          # MessageStatus
    source: str = ""                 # 来源渠道
    target: str = ""                 # 目标（Agent/Channel）
    subject: str = ""                # 主题
    body: str = ""                   # 消息正文
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    created_at: str = ""             # 创建时间
    processed_at: Optional[str] = None  # 处理时间
    reply_to: Optional[str] = None   # 回复的消息 ID
    correlation_id: Optional[str] = None  # 关联 ID（用于消息链）
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.message_id:
            import random
            self.message_id = f"msg-{int(time.time()*1000)}-{random.randint(1000,9999)}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    @property
    def is_urgent(self) -> bool:
        return self.priority == MessagePriority.URGENT

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'MessageEnvelope':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'MessageEnvelope':
        return cls.from_dict(json.loads(json_str))

    def summary(self) -> str:
        mtype = self.message_type.value if isinstance(self.message_type, MessageType) else self.message_type
        mpri = self.priority.value if isinstance(self.priority, MessagePriority) else self.priority
        return (
            f"[{mtype}][{mpri}] "
            f"{self.subject or self.body[:50]} "
            f"(from={self.source}, id={self.message_id})"
        )


# ═══════════════════════════════════════════════════════════════
# Channel — 抽象基类
# ═══════════════════════════════════════════════════════════════

class Channel(ABC):
    """通信渠道抽象基类

    每种通信渠道必须实现：
    - send: 发送消息
    - receive: 接收消息（可选）
    - name: 渠道名称
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """渠道名称"""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """渠道是否可用"""
        ...

    @abstractmethod
    def send(self, envelope: MessageEnvelope) -> bool:
        """发送消息

        Returns:
            True 如果发送成功
        """
        ...

    def receive(self) -> Optional[MessageEnvelope]:
        """接收消息（轮询模式）

        Returns:
            MessageEnvelope 或 None（无消息）
        """
        return None

    def validate(self) -> tuple:
        """验证渠道配置

        Returns:
            (is_valid, message)
        """
        if not self.is_available:
            return False, f"Channel '{self.name}' is not available"
        return True, "OK"


# ═══════════════════════════════════════════════════════════════
# WebhookChannel — HTTP Webhook 渠道
# ═══════════════════════════════════════════════════════════════

class WebhookChannel(Channel):
    """HTTP Webhook 渠道

    支持两种模式：
    - 接收模式：启动 HTTP 服务器接收外部 Webhook
    - 发送模式：向外部 URL 发送 Webhook
    """

    def __init__(self, project_root: str = ".",
                 listen_port: int = 8888,
                 outbound_url: str = "",
                 secret: str = ""):
        self.project_root = project_root
        self.listen_port = listen_port
        self.outbound_url = outbound_url
        self.secret = secret
        self._incoming: List[MessageEnvelope] = []
        self._server: Optional[HTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None

    @property
    def name(self) -> str:
        return "webhook"

    @property
    def is_available(self) -> bool:
        return True  # Webhook 始终可用

    def send(self, envelope: MessageEnvelope) -> bool:
        """向外部 URL 发送 Webhook"""
        if not self.outbound_url:
            logger.debug("No outbound URL configured, webhook send skipped")
            return False

        try:
            import urllib.request
            headers = {
                "Content-Type": "application/json",
            }
            if self.secret:
                headers["X-ADDS-Signature"] = f"sha256={self.secret}"

            data = envelope.to_json().encode("utf-8")
            req = urllib.request.Request(
                self.outbound_url,
                data=data,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Webhook send failed: {e}")
            return False

    def receive(self) -> Optional[MessageEnvelope]:
        """接收待处理的 Webhook 消息"""
        if self._incoming:
            return self._incoming.pop(0)
        return None

    def _add_incoming(self, envelope: MessageEnvelope):
        """添加接收到的消息"""
        self._incoming.append(envelope)
        # 限制队列长度
        if len(self._incoming) > 100:
            self._incoming = self._incoming[-50:]

    def start_server(self):
        """启动 Webhook 接收服务器"""
        channel = self

        class WebhookHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')

                try:
                    data = json.loads(body)
                    envelope = MessageEnvelope.from_dict(data)
                    envelope.source = "webhook"
                    channel._add_incoming(envelope)

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "ok",
                        "message_id": envelope.message_id,
                    }).encode('utf-8'))
                except Exception as e:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "error",
                        "message": str(e),
                    }).encode('utf-8'))

            def do_GET(self):
                """健康检查端点"""
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "channel": "webhook",
                    "incoming_count": len(channel._incoming),
                }).encode('utf-8'))

            def log_message(self, format, *args):
                logger.debug(f"Webhook: {format % args}")

        self._server = HTTPServer(('0.0.0.0', self.listen_port), WebhookHandler)
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="webhook-server",
        )
        self._server_thread.start()
        logger.info(f"Webhook server started on port {self.listen_port}")

    def stop_server(self):
        """停止 Webhook 服务器"""
        if self._server:
            self._server.shutdown()
            self._server = None
            logger.info("Webhook server stopped")

    def is_server_running(self) -> bool:
        """服务器是否在运行"""
        return self._server is not None and self._server_thread is not None and self._server_thread.is_alive()


# ═══════════════════════════════════════════════════════════════
# CLIChannel — CLI 命令行渠道
# ═══════════════════════════════════════════════════════════════

class CLIChannel(Channel):
    """CLI 命令行渠道

    通过命令行发送消息（执行外部命令、脚本等）。
    """

    def __init__(self, project_root: str = ".",
                 send_command: str = ""):
        self.project_root = project_root
        self.send_command = send_command  # 自定义发送命令模板
        self._incoming: List[MessageEnvelope] = []

    @property
    def name(self) -> str:
        return "cli"

    @property
    def is_available(self) -> bool:
        return True

    def send(self, envelope: MessageEnvelope) -> bool:
        """通过 CLI 命令发送消息"""
        if not self.send_command:
            # 默认：打印到 stdout
            print(f"[{envelope.message_type}] {envelope.subject or envelope.body[:80]}")
            return True

        try:
            env = os.environ.copy()
            env['ADDS_MSG_ID'] = envelope.message_id
            env['ADDS_MSG_TYPE'] = envelope.message_type
            env['ADDS_MSG_SUBJECT'] = envelope.subject
            env['ADDS_MSG_BODY'] = envelope.body
            env['ADDS_MSG_PRIORITY'] = envelope.priority

            result = subprocess.run(
                self.send_command,
                shell=True,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"CLI send failed: {e}")
            return False

    def receive(self) -> Optional[MessageEnvelope]:
        """从队列中获取消息"""
        if self._incoming:
            return self._incoming.pop(0)
        return None

    def inject(self, envelope: MessageEnvelope):
        """注入消息到队列（模拟接收）"""
        envelope.source = "cli"
        self._incoming.append(envelope)


# ═══════════════════════════════════════════════════════════════
# FileChannel — 文件渠道
# ═══════════════════════════════════════════════════════════════

class FileChannel(Channel):
    """文件渠道

    通过文件系统交换消息（适用于无网络的隔离环境）。
    """

    def __init__(self, project_root: str = ".",
                 inbox_dir: str = "",
                 outbox_dir: str = ""):
        self.project_root = project_root
        self.inbox_dir = Path(inbox_dir) if inbox_dir else Path(project_root) / ".ai" / "gateway" / "inbox"
        self.outbox_dir = Path(outbox_dir) if outbox_dir else Path(project_root) / ".ai" / "gateway" / "outbox"

    @property
    def name(self) -> str:
        return "file"

    @property
    def is_available(self) -> bool:
        return True

    def send(self, envelope: MessageEnvelope) -> bool:
        """写入文件到 outbox"""
        try:
            self.outbox_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{envelope.message_id}.json"
            filepath = self.outbox_dir / filename
            filepath.write_text(envelope.to_json(), encoding='utf-8')
            return True
        except Exception as e:
            logger.error(f"File send failed: {e}")
            return False

    def receive(self) -> Optional[MessageEnvelope]:
        """从 inbox 读取文件"""
        try:
            self.inbox_dir.mkdir(parents=True, exist_ok=True)
            files = sorted(self.inbox_dir.glob("*.json"))
            if not files:
                return None
            # 读取最旧的消息
            filepath = files[0]
            data = json.loads(filepath.read_text(encoding='utf-8'))
            envelope = MessageEnvelope.from_dict(data)
            envelope.source = "file"
            # 删除已读取的文件
            filepath.unlink()
            return envelope
        except Exception as e:
            logger.error(f"File receive failed: {e}")
            return None


# ═══════════════════════════════════════════════════════════════
# AsyncMessageQueue — 异步消息处理队列
# ═══════════════════════════════════════════════════════════════

class AsyncMessageQueue:
    """异步消息处理队列

    线程安全的消息队列，支持优先级排序。
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._queue: List[MessageEnvelope] = []
        self._lock = threading.Lock()
        self._handlers: Dict[str, List[Callable]] = {}

    def enqueue(self, envelope: MessageEnvelope) -> bool:
        """入队"""
        with self._lock:
            if len(self._queue) >= self.max_size:
                # 移除最低优先级的消息
                self._queue.sort(key=lambda m: self._priority_value(m.priority))
                self._queue.pop(0)
            self._queue.append(envelope)
            # 按优先级排序
            self._queue.sort(key=lambda m: -self._priority_value(m.priority))
            return True

    def dequeue(self) -> Optional[MessageEnvelope]:
        """出队（最高优先级）"""
        with self._lock:
            if not self._queue:
                return None
            return self._queue.pop(0)

    def peek(self) -> Optional[MessageEnvelope]:
        """查看队首消息"""
        with self._lock:
            if not self._queue:
                return None
            return self._queue[0]

    def size(self) -> int:
        """队列大小"""
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        return self.size() == 0

    def register_handler(self, message_type: str, handler: Callable):
        """注册消息处理器"""
        if message_type not in self._handlers:
            self._handlers[message_type] = []
        self._handlers[message_type].append(handler)

    def process_next(self) -> Optional[MessageEnvelope]:
        """处理下一条消息"""
        envelope = self.dequeue()
        if not envelope:
            return None

        envelope.status = MessageStatus.PROCESSING
        handlers = self._handlers.get(envelope.message_type, [])
        for handler in handlers:
            try:
                handler(envelope)
            except Exception as e:
                logger.error(f"Handler error for {envelope.message_id}: {e}")

        envelope.status = MessageStatus.COMPLETED
        envelope.processed_at = datetime.now().isoformat()
        return envelope

    def process_all(self) -> int:
        """处理所有消息"""
        count = 0
        while not self.is_empty():
            self.process_next()
            count += 1
        return count

    @staticmethod
    def _priority_value(priority: str) -> int:
        """优先级数值（越高越优先）"""
        return {
            MessagePriority.URGENT: 4,
            MessagePriority.HIGH: 3,
            MessagePriority.NORMAL: 2,
            MessagePriority.LOW: 1,
        }.get(priority, 2)

    def get_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        with self._lock:
            type_counts = {}
            for msg in self._queue:
                type_counts[msg.message_type] = type_counts.get(msg.message_type, 0) + 1
            return {
                'total': len(self._queue),
                'max_size': self.max_size,
                'type_counts': type_counts,
                'handlers': {k: len(v) for k, v in self._handlers.items()},
            }


# ═══════════════════════════════════════════════════════════════
# MessageGateway — 网关核心
# ═══════════════════════════════════════════════════════════════

class MessageGateway:
    """消息网关核心

    功能：
    - 消息路由：根据目标分发到不同渠道
    - 协议转换：不同渠道间的消息格式转换
    - 消息处理：注册处理器处理特定类型消息
    - 消息记录：记录所有消息的处理历史
    """

    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        self.channels: Dict[str, Channel] = {}
        self.queue = AsyncMessageQueue()
        self._handlers: Dict[str, List[Callable]] = {}
        self._history: List[Dict[str, Any]] = []
        self._running = False
        self._processor_thread: Optional[threading.Thread] = None

        # 加载配置
        self._config_path = Path(project_root) / ".ai" / "gateway.json"

        # 注册默认渠道
        self.register_channel(CLIChannel(project_root=project_root))

    def register_channel(self, channel: Channel):
        """注册通信渠道"""
        self.channels[channel.name] = channel
        logger.info(f"Registered channel: {channel.name}")

    def unregister_channel(self, name: str) -> bool:
        """注销通信渠道"""
        if name in self.channels:
            del self.channels[name]
            return True
        return False

    def send(self, envelope: MessageEnvelope,
             channel_name: Optional[str] = None) -> bool:
        """发送消息

        Args:
            envelope: 消息信封
            channel_name: 目标渠道（不指定则广播到所有渠道）
        """
        if channel_name:
            channel = self.channels.get(channel_name)
            if channel:
                result = channel.send(envelope)
                self._record(envelope, "send", channel_name, result)
                return result
            return False

        # 广播到所有渠道
        all_success = True
        for name, channel in self.channels.items():
            try:
                result = channel.send(envelope)
                self._record(envelope, "send", name, result)
                if not result:
                    all_success = False
            except Exception as e:
                logger.error(f"Send to {name} failed: {e}")
                all_success = False
        return all_success

    def receive(self, channel_name: Optional[str] = None) -> Optional[MessageEnvelope]:
        """接收消息

        从指定渠道或所有渠道轮询接收。
        """
        if channel_name:
            channel = self.channels.get(channel_name)
            if channel:
                envelope = channel.receive()
                if envelope:
                    self._record(envelope, "receive", channel_name, True)
                    self.queue.enqueue(envelope)
                return envelope
            return None

        # 从所有渠道接收
        for name, channel in self.channels.items():
            try:
                envelope = channel.receive()
                if envelope:
                    self._record(envelope, "receive", name, True)
                    self.queue.enqueue(envelope)
                    return envelope
            except Exception as e:
                logger.error(f"Receive from {name} failed: {e}")
        return None

    def receive_all(self) -> List[MessageEnvelope]:
        """从所有渠道接收消息"""
        messages = []
        for name, channel in self.channels.items():
            try:
                while True:
                    envelope = channel.receive()
                    if not envelope:
                        break
                    self._record(envelope, "receive", name, True)
                    self.queue.enqueue(envelope)
                    messages.append(envelope)
            except Exception as e:
                logger.error(f"Receive from {name} failed: {e}")
        return messages

    def route(self, envelope: MessageEnvelope) -> Optional[str]:
        """路由消息到目标渠道

        根据消息的 target 字段决定发送到哪个渠道。
        """
        target = envelope.target
        if not target:
            return None

        # 解析目标（格式：channel:address）
        if ':' in target:
            channel_name, _ = target.split(':', 1)
            if channel_name in self.channels:
                return channel_name

        # 按名称直接匹配
        if target in self.channels:
            return target

        return None

    def register_handler(self, message_type: str, handler: Callable):
        """注册消息处理器"""
        if message_type not in self._handlers:
            self._handlers[message_type] = []
        self._handlers[message_type].append(handler)
        self.queue.register_handler(message_type, handler)

    def process_message(self, envelope: MessageEnvelope) -> bool:
        """处理单条消息"""
        handlers = self._handlers.get(envelope.message_type, [])
        if not handlers:
            logger.debug(f"No handler for message type: {envelope.message_type}")
            return False

        for handler in handlers:
            try:
                handler(envelope)
            except Exception as e:
                logger.error(f"Handler error: {e}")
                return False
        return True

    def start_processor(self, poll_interval: float = 1.0):
        """启动消息处理器（后台线程）"""
        self._running = True

        def _processor():
            while self._running:
                try:
                    # 1. 从所有渠道接收
                    self.receive_all()

                    # 2. 处理队列中的消息
                    self.queue.process_all()

                except Exception as e:
                    logger.error(f"Processor error: {e}")

                time.sleep(poll_interval)

        self._processor_thread = threading.Thread(
            target=_processor,
            daemon=True,
            name="gateway-processor",
        )
        self._processor_thread.start()
        logger.info("Gateway processor started")

    def stop_processor(self):
        """停止消息处理器"""
        self._running = False
        if self._processor_thread:
            self._processor_thread.join(timeout=5)
            self._processor_thread = None
        logger.info("Gateway processor stopped")

    def is_processor_running(self) -> bool:
        return self._running and self._processor_thread is not None and self._processor_thread.is_alive()

    def _record(self, envelope: MessageEnvelope, action: str, channel: str, success: bool):
        """记录消息处理历史"""
        self._history.append({
            'message_id': envelope.message_id,
            'action': action,
            'channel': channel,
            'success': success,
            'timestamp': datetime.now().isoformat(),
        })
        # 限制历史长度
        if len(self._history) > 1000:
            self._history = self._history[-500:]

    def get_stats(self) -> Dict[str, Any]:
        """获取网关统计"""
        return {
            'channels': {name: ch.is_available for name, ch in self.channels.items()},
            'queue': self.queue.get_stats(),
            'history_count': len(self._history),
            'handlers': {k: len(v) for k, v in self._handlers.items()},
            'processor_running': self.is_processor_running(),
        }

    def get_recent_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的消息历史"""
        return self._history[-limit:]


# ═══════════════════════════════════════════════════════════════
# CLI 子命令
# ═══════════════════════════════════════════════════════════════

def add_gateway_subparser(subparsers):
    """添加 gateway 子命令到 argparse"""
    gw_parser = subparsers.add_parser(
        "gateway", help="通信网关管理（P2-3）",
    )
    gw_sub = gw_parser.add_subparsers(dest="gateway_command")

    # list
    gw_sub.add_parser("list", help="列出已注册渠道")

    # send
    send_parser = gw_sub.add_parser("send", help="发送消息")
    send_parser.add_argument("subject", type=str, help="消息主题")
    send_parser.add_argument("--body", type=str, default="", help="消息正文")
    send_parser.add_argument("--type", type=str, default="notification",
                             choices=["command", "notification", "query", "event"],
                             help="消息类型")
    send_parser.add_argument("--channel", type=str, help="目标渠道")
    send_parser.add_argument("--priority", type=str, default="normal",
                             choices=["low", "normal", "high", "urgent"],
                             help="优先级")

    # receive
    gw_sub.add_parser("receive", help="接收消息")

    # stats
    gw_sub.add_parser("stats", help="网关统计")

    # history
    hist_parser = gw_sub.add_parser("history", help="消息历史")
    hist_parser.add_argument("--limit", type=int, default=20, help="显示条数")


def handle_gateway_command(args, project_root: str = "."):
    """处理 gateway 子命令"""
    gateway = MessageGateway(project_root=project_root)

    # 注册额外渠道
    gateway.register_channel(WebhookChannel(project_root=project_root))
    gateway.register_channel(FileChannel(project_root=project_root))

    cmd = getattr(args, 'gateway_command', None)
    if not cmd:
        print("⚠️  请指定子命令。使用 adds gateway --help 查看帮助。")
        return

    if cmd == "list":
        _cmd_gw_list(gateway)
    elif cmd == "send":
        _cmd_gw_send(gateway, args)
    elif cmd == "receive":
        _cmd_gw_receive(gateway)
    elif cmd == "stats":
        _cmd_gw_stats(gateway)
    elif cmd == "history":
        _cmd_gw_history(gateway, args)


def _cmd_gw_list(gateway: MessageGateway):
    """列出渠道"""
    print("=" * 50)
    print("📡 通信渠道")
    print("=" * 50)
    for name, channel in gateway.channels.items():
        icon = "✅" if channel.is_available else "❌"
        desc = {
            "webhook": "HTTP Webhook",
            "cli": "命令行",
            "file": "文件系统",
        }.get(name, "")
        print(f"  {icon} {name:10s} — {desc}")
    print()


def _cmd_gw_send(gateway: MessageGateway, args):
    """发送消息"""
    envelope = MessageEnvelope(
        message_type=args.type,
        priority=args.priority,
        subject=args.subject,
        body=args.body or args.subject,
        source="cli",
    )
    success = gateway.send(envelope, channel_name=args.channel)
    if success:
        print(f"✅ 消息已发送 (id={envelope.message_id})")
    else:
        print(f"❌ 消息发送失败")


def _cmd_gw_receive(gateway: MessageGateway):
    """接收消息"""
    envelope = gateway.receive()
    if envelope:
        print(f"📨 收到消息:")
        print(f"   ID: {envelope.message_id}")
        print(f"   类型: {envelope.message_type}")
        print(f"   主题: {envelope.subject}")
        print(f"   正文: {envelope.body[:200]}")
    else:
        print("📭 暂无消息")


def _cmd_gw_stats(gateway: MessageGateway):
    """网关统计"""
    stats = gateway.get_stats()
    print("=" * 50)
    print("📊 网关统计")
    print("=" * 50)
    print(f"  渠道: {stats['channels']}")
    print(f"  队列: {stats['queue']}")
    print(f"  历史记录: {stats['history_count']} 条")
    print(f"  处理器: {'运行中' if stats['processor_running'] else '未启动'}")
    print()


def _cmd_gw_history(gateway: MessageGateway, args):
    """消息历史"""
    history = gateway.get_recent_history(limit=args.limit)
    if not history:
        print("📭 暂无消息历史")
        return
    print("=" * 60)
    print(f"📜 消息历史（最近 {len(history)} 条）")
    print("=" * 60)
    for record in reversed(history):
        icon = "✅" if record['success'] else "❌"
        print(f"  {icon} {record['timestamp'][:19]}  "
              f"{record['action']}  {record['channel']}  "
              f"id={record['message_id']}")
    print()


# ═══════════════════════════════════════════════════════════════
# 内置测试
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    print("=== MessageEnvelope 测试 ===")
    msg = MessageEnvelope(
        message_type=MessageType.COMMAND,
        priority=MessagePriority.HIGH,
        subject="测试消息",
        body="这是一条测试消息",
        source="test",
    )
    print(f"  创建: {msg.summary()}")
    print(f"  JSON: {msg.to_json()[:100]}...")

    msg2 = MessageEnvelope.from_json(msg.to_json())
    print(f"  反序列化: {msg2.summary()}")

    print("\n=== AsyncMessageQueue 测试 ===")
    q = AsyncMessageQueue()
    q.enqueue(MessageEnvelope(priority=MessagePriority.LOW, subject="低优先级"))
    q.enqueue(MessageEnvelope(priority=MessagePriority.URGENT, subject="紧急"))
    q.enqueue(MessageEnvelope(priority=MessagePriority.NORMAL, subject="普通"))
    print(f"  队列大小: {q.size()}")
    first = q.dequeue()
    print(f"  最高优先级: {first.subject}")  # 应该是 "紧急"

    print("\n=== MessageGateway 测试 ===")
    gw = MessageGateway()
    gw.register_channel(FileChannel(project_root="."))
    envelope = MessageEnvelope(
        message_type=MessageType.NOTIFICATION,
        subject="网关测试",
        body="测试消息",
    )
    gw.send(envelope, channel_name="file")
    received = gw.receive(channel_name="file")
    if received:
        print(f"  收到: {received.summary()}")
    else:
        print(f"  未收到消息")
    print(f"  统计: {gw.get_stats()}")

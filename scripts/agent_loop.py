#!/usr/bin/env python3
"""
ADDS Agent Loop — 简化版

核心能力：创建 agent → 注入系统提示词 → 调用大模型 → 交互对话
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from model.base import ModelInterface


@dataclass
class AgentSession:
    """Agent 会话状态"""
    system_prompt: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    turn_count: int = 0


class AgentLoop:
    """
    简化 Agent Loop

    流程：
    1. 注入 system_prompt
    2. 用户输入 → 模型响应 → 打印
    3. 循环直到用户退出
    """

    def __init__(self, model: ModelInterface, system_prompt: str = ""):
        self.model = model
        self.session = AgentSession(system_prompt=system_prompt)

    async def run(self):
        """主循环：交互式对话"""
        model_name = self.model.get_model_name()
        ctx_window = self.model.get_context_window()

        print(f"\n🤖 Agent 已启动")
        print(f"   模型: {model_name}")
        print(f"   上下文: {ctx_window:,} tokens")
        if self.session.system_prompt:
            print(f"   角色设定: {self.session.system_prompt[:80]}{'...' if len(self.session.system_prompt) > 80 else ''}")
        print(f"\n💡 输入消息开始对话，输入 /quit 或 Ctrl+C 退出\n")

        while True:
            try:
                user_input = input("你> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n👋 再见！")
                break

            if not user_input:
                continue
            if user_input.lower() in ("/quit", "/exit", "/q"):
                print("👋 再见！")
                break

            # 追加用户消息
            self.session.messages.append({"role": "user", "content": user_input})
            self.session.turn_count += 1

            # 调用模型
            print()
            full_response = []
            thinking_shown = False
            try:
                async for resp in self.model.chat(
                    self.session.messages,
                    system_prompt=self.session.system_prompt or None,
                    stream=True,
                ):
                    if resp.finish_reason == "error":
                        print(f"❌ {resp.content}")
                        break
                    # 显示思考过程
                    if resp.thinking and resp.finish_reason == "thinking":
                        if not thinking_shown:
                            print("🧠 ", end="", flush=True)
                            thinking_shown = True
                        print(resp.thinking, end="", flush=True)
                    # 显示回复内容
                    if resp.content and resp.finish_reason == "streaming":
                        if thinking_shown:
                            print("\n")  # 思考结束，换行
                            thinking_shown = False
                        print(resp.content, end="", flush=True)
                        full_response.append(resp.content)
                    if resp.finish_reason == "stop":
                        print()  # 换行

                assistant_content = "".join(full_response)
                if assistant_content:
                    self.session.messages.append({"role": "assistant", "content": assistant_content})

            except Exception as e:
                print(f"\n❌ 调用失败: {e}")

            print()  # 空行分隔

        return self.session.turn_count

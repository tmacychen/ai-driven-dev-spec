"""
ADDS Model Layer — 模型工厂

启动时交互式选择 API/CLI/SDK + Provider + Model，
返回对应的 ModelInterface 实例。
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from .base import ModelInterface
from .api_adapter import APIAdapter
from .openai_adapter import OpenAIAdapter
from .cli_adapter import CLIAdapter
from .sdk_adapter import SDKAdapter
from .providers.registry import ProviderRegistry, get_registry


class ModelFactory:
    """模型工厂 — 启动时交互式选择

    流程:
    1. 检测可用模式（API key 存在? CLI 工具已安装? SDK 已安装?）
    2. 列出可用选项让用户选择
    3. 如果有多个模型，让用户选择模型
    4. 返回对应的 Adapter 实例
    """

    def __init__(self, registry: Optional[ProviderRegistry] = None, project_root: Optional[Path] = None):
        self.registry = registry or get_registry()
        self.project_root = project_root or Path(".")

    def select_model(self, interactive: bool = True) -> ModelInterface:
        """交互式选择模型

        Args:
            interactive: 是否交互式选择（False 时自动选第一个可用模式）

        Returns:
            ModelInterface 实例
        """
        available_modes = self.registry.get_available_modes()

        if not available_modes:
            print("❌ 未检测到可用的模型。请配置 API Key 或安装 CLI 工具。")
            print("\n可用选项:")
            for provider_id, provider in self.registry.get_all().items():
                if "api" in provider:
                    env = provider["api"].get("api_key_env", "")
                    print(f"  - 设置环境变量 {env} 以启用 {provider['name']} API")
                if "cli" in provider:
                    print(f"  - 运行 `{provider['cli']['install_hint']}` 以安装 {provider['name']} CLI")
                if "sdk" in provider:
                    print(f"  - 运行 `{provider['sdk']['install_hint']}` 以安装 {provider['name']} SDK")
            sys.exit(1)

        if not interactive or len(available_modes) == 1:
            selected = available_modes[0]
        else:
            # 交互式选择
            print("\n🤖 请选择大模型调用方式：")
            for i, mode in enumerate(available_modes, 1):
                print(f"  {i}. {mode['label']}")

            try:
                choice = int(input("\n请输入编号: ")) - 1
                if choice < 0 or choice >= len(available_modes):
                    print("❌ 无效选择")
                    sys.exit(1)
            except (ValueError, EOFError, KeyboardInterrupt):
                print("\n❌ 已取消")
                sys.exit(1)

            selected = available_modes[choice]

        # 选择具体模型
        model_name = selected["models"][0]
        if len(selected["models"]) > 1 and interactive:
            print(f"\n📋 可用模型：")
            for i, model in enumerate(selected["models"], 1):
                print(f"  {i}. {model}")
            try:
                model_choice = int(input("\n请输入编号: ")) - 1
                if 0 <= model_choice < len(selected["models"]):
                    model_name = selected["models"][model_choice]
            except (ValueError, EOFError, KeyboardInterrupt):
                pass  # 使用默认模型

        # 创建适配器
        provider = self.registry.get(selected["provider"])
        adapter = self._create_adapter(selected, provider, model_name)

        print(f"\n✅ 已选择: {selected['label']}")
        print(f"✅ 上下文窗口: {adapter.get_context_window():,} tokens")

        return adapter

    def _create_adapter(self, selected: dict, provider: dict, model_name: str) -> ModelInterface:
        """根据选择创建适配器"""
        mode = selected["mode"]

        if mode == "api":
            api_config = provider["api"]
            adapter_type = api_config.get("adapter", "anthropic")
            if adapter_type == "openai":
                return OpenAIAdapter({
                    "base_url": api_config["base_url"],
                    "api_key_env": api_config.get("api_key_env", ""),
                    "model": model_name,
                    "context_window": api_config.get("context_window", 128000),
                })
            else:
                return APIAdapter({
                    "base_url": api_config["base_url"],
                    "api_key_env": api_config.get("api_key_env", ""),
                    "model": model_name,
                    "context_window": api_config.get("context_window", 128000),
                    "thinking_budget": api_config.get("thinking_budget", 10000),
                })

        elif mode == "cli":
            cli_config = provider["cli"]
            return CLIAdapter({
                "cli_type": cli_config.get("cli_type", "generic"),
                "command": cli_config["command"],
                "model": model_name,
                "context_window": cli_config.get("context_window", 204800),
            })

        elif mode == "sdk":
            sdk_config = provider["sdk"]
            return SDKAdapter({
                "package": sdk_config["package"],
                "model": model_name,
                "context_window": sdk_config.get("context_window", 200000),
            })

        else:
            raise ValueError(f"未知的调用模式: {mode}")

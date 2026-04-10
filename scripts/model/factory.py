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
from .cli_adapter import CLIAdapter
from .sdk_adapter import SDKAdapter
from .providers.registry import ProviderRegistry, get_registry
from .skill_generator import SkillGenerator
from .task_dispatcher import CLIProfile


class ModelFactory:
    """模型工厂 — 启动时交互式选择

    流程:
    1. 检测可用模式（API key 存在? CLI 工具已安装? SDK 已安装?）
    2. 列出可用选项让用户选择
    3. 如果有多个模型，让用户选择模型
    4. 返回对应的 Adapter 实例
    5. 首次使用某个 CLI Provider 时，触发技能生成
    """

    def __init__(self, registry: Optional[ProviderRegistry] = None, project_root: Optional[Path] = None):
        self.registry = registry or get_registry()
        self.project_root = project_root or Path(".")
        self._skill_generator = SkillGenerator(self.project_root)

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

    async def select_model_async(self, interactive: bool = True) -> ModelInterface:
        """异步版本的 select_model，支持技能生成"""
        adapter = self.select_model(interactive=interactive)

        # 首次使用 CLI/SDK Provider 时，检查/生成技能
        await self._check_skill_generation(adapter)

        return adapter

    def _create_adapter(self, selected: dict, provider: dict, model_name: str) -> ModelInterface:
        """根据选择创建适配器"""
        mode = selected["mode"]
        provider_id = selected["provider"]

        if mode == "api":
            api_config = provider["api"]
            return APIAdapter({
                "base_url": api_config["base_url"],
                "api_key_env": api_config.get("api_key_env", ""),
                "model": model_name,
                "context_window": api_config.get("context_window", 128000),
            })

        elif mode == "cli":
            cli_config = provider["cli"]
            return CLIAdapter({
                "profile": cli_config["profile"],
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

    async def _check_skill_generation(self, adapter: ModelInterface) -> None:
        """首次使用 CLI/SDK Provider 时，检查/生成技能"""
        if not isinstance(adapter, (CLIAdapter, SDKAdapter)):
            return

        profile = adapter.profile if isinstance(adapter, CLIAdapter) else None
        if profile is None and isinstance(adapter, SDKAdapter):
            # SDK 也可能有 profile
            profile = adapter._sdk_config.get("profile")

        if profile and profile.skill_generation.get("enabled"):
            skill_path = self.project_root / ".ai" / "memories" / "SKILLS" / profile.name
            if not skill_path.exists() or not list(skill_path.glob("*.md")):
                print(f"\n📖 首次使用 {profile.name}，正在从文档生成技能描述...")
                await self._skill_generator.generate_from_docs(profile)
                print(f"✅ 技能生成完成，存入 .ai/memories/SKILLS/{profile.name}/")

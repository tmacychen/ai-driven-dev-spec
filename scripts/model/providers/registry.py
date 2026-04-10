"""
ADDS Model Layer — Provider 注册表

可扩展的 Provider 注册机制，支持动态注册新的模型提供商。
"""

from typing import Optional

from .minimax import MINIMAX_PROVIDER
from .codebuddy import CODEBUDDY_PROVIDER


class ProviderRegistry:
    """Provider 注册表 — 可扩展

    管理所有可用的模型提供商配置。
    支持运行时注册新 Provider。
    """

    def __init__(self):
        self._providers: dict[str, dict] = {}
        # 注册内置 Provider
        self.register("minimax", MINIMAX_PROVIDER)
        self.register("codebuddy", CODEBUDDY_PROVIDER)

    def register(self, provider_id: str, config: dict) -> None:
        """注册 Provider

        Args:
            provider_id: Provider 唯一标识，如 "minimax"
            config: Provider 配置，格式参考 MINIMAX_PROVIDER / CODEBUDDY_PROVIDER
        """
        self._providers[provider_id] = config

    def unregister(self, provider_id: str) -> None:
        """移除 Provider"""
        self._providers.pop(provider_id, None)

    def get(self, provider_id: str) -> Optional[dict]:
        """获取 Provider 配置"""
        return self._providers.get(provider_id)

    def list_providers(self) -> list[str]:
        """列出所有已注册的 Provider ID"""
        return list(self._providers.keys())

    def get_all(self) -> dict[str, dict]:
        """获取所有 Provider 配置"""
        return dict(self._providers)

    def get_available_modes(self) -> list[dict]:
        """获取所有可用的调用模式

        检测环境（API Key、CLI 安装状态、SDK 安装状态），
        返回当前可用的模式列表。
        """
        import os
        import shutil
        import importlib

        available = []

        for provider_id, provider in self._providers.items():
            # 检测 API 可用性
            if "api" in provider:
                api_key_env = provider["api"].get("api_key_env", "")
                api_key = os.environ.get(api_key_env, "")
                if api_key:
                    available.append({
                        "mode": "api",
                        "provider": provider_id,
                        "label": f"{provider['name']} (API)",
                        "models": provider["api"]["models"],
                    })

            # 检测 CLI 可用性
            if "cli" in provider:
                command = provider["cli"]["command"]
                if shutil.which(command):
                    available.append({
                        "mode": "cli",
                        "provider": provider_id,
                        "label": f"{provider['name']} (CLI: {command})",
                        "models": provider["cli"]["models"],
                    })

            # 检测 SDK 可用性
            if "sdk" in provider:
                package = provider["sdk"]["package"]
                try:
                    importlib.import_module(package.replace("-", "_"))
                    available.append({
                        "mode": "sdk",
                        "provider": provider_id,
                        "label": f"{provider['name']} (SDK: {package})",
                        "models": provider["sdk"]["models"],
                    })
                except ImportError:
                    pass

        return available


# 全局单例
_registry: Optional[ProviderRegistry] = None


def get_registry() -> ProviderRegistry:
    """获取全局 Provider 注册表"""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry

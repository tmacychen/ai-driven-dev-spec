"""
ADDS Model Layer — MiniMax Provider 配置

支持 API 和 CLI 两种调用模式。
"""

from ..task_dispatcher import CLIProfile

# MiniMax Provider 完整配置
MINIMAX_PROVIDER = {
    "name": "MiniMax",
    "api": {
        "base_url": "https://api.minimaxi.com/anthropic",  # Anthropic 兼容端点
        "api_key_env": "MINIMAX_API_KEY",
        "models": [
            "MiniMax-M2.7",
            "MiniMax-M2.7-highspeed",
            "MiniMax-M2.5",
            "MiniMax-M2.5-highspeed",
            "MiniMax-M2.1",
            "MiniMax-M2.1-highspeed",
            "MiniMax-M2",
        ],
        "context_window": 204800,
        "thinking_budget": 10000,  # 推理过程 token 预算
    },
    "cli": {
        "command": "mmx",
        "cli_type": "mmx",
        "install_hint": "npm install -g minimax-cli",
        "auth_command": "mmx auth login --api-key $MINIMAX_API_KEY",
        "models": ["MiniMax-M2.7", "MiniMax-M2.5", "MiniMax-M2.1", "MiniMax-M2"],
        "context_window": 204800,
    },
}

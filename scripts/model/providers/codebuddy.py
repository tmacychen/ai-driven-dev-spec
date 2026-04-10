"""
ADDS Model Layer — Codebuddy Provider 配置

支持 CLI 和 SDK 两种调用模式。
"""

# Codebuddy Provider 完整配置
CODEBUDDY_PROVIDER = {
    "name": "Codebuddy",
    "cli": {
        "command": "codebuddy",
        "cli_type": "codebuddy",
        "install_hint": "npm install -g @anthropic-ai/codebuddy",
        "auth_command": "codebuddy",  # 交互式登录
        "api_key_env": "CODEBUDDY_API_KEY",
        "models": ["default"],
        "context_window": 200000,
    },
    "sdk": {
        "package": "codebuddy-agent-sdk",
        "install_hint": "pip install codebuddy-agent-sdk",
        "auth_command": None,
        "api_key_env": "CODEBUDDY_API_KEY",
        "models": ["default"],
        "context_window": 200000,
    },
}

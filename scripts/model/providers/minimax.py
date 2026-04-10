"""
ADDS Model Layer — MiniMax Provider 配置

支持 API 和 CLI 两种调用模式。
"""

from ..task_dispatcher import CLIProfile

# MiniMax CLI Profile
MINIMAX_CLI_PROFILE = CLIProfile(
    name="minimax",
    command="mmx",
    version_command="mmx --version",
    dispatch={
        "exec_template": "{command} text chat --message {prompt} --output {output_format}",
        "input_method": "arg",
        "output_format": "json",
        "stream_supported": True,
        "system_prompt_method": "flag",
        "system_prompt_flag": "--system-prompt",
    },
    session={
        "resume_flag": None,
        "session_id_flag": None,
        "session_id_source": None,
    },
    permission={"bypass_flag": None},
    skill_generation={
        "enabled": True,
        "docs_source": "https://github.com/MiniMax-AI/cli",
    },
)

# MiniMax Provider 完整配置
MINIMAX_PROVIDER = {
    "name": "MiniMax",
    "api": {
        "base_url": "https://api.minimaxi.com/v1",
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
    },
    "cli": {
        "command": "mmx",
        "install_hint": "npm install -g mmx-cli",
        "auth_command": "mmx auth login --api-key $MINIMAX_API_KEY",
        "models": ["MiniMax-M2.7", "MiniMax-M2.5", "MiniMax-M2.1", "MiniMax-M2"],
        "context_window": 204800,
        "profile": MINIMAX_CLI_PROFILE,
    },
}

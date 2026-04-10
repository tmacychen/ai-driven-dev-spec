"""
ADDS Model Layer — Codebuddy Provider 配置

支持 CLI 和 SDK 两种调用模式。
"""

from ..task_dispatcher import CLIProfile

# Codebuddy CLI Profile
CODEBUDDY_CLI_PROFILE = CLIProfile(
    name="codebuddy",
    command="codebuddy",
    version_command="codebuddy --version",
    dispatch={
        "exec_template": "{command} -p {prompt} --output-format {output_format}",
        "input_method": "arg",
        "output_format": "json",
        "stream_supported": True,
        "system_prompt_method": "file",
        "system_prompt_flag": "--system-prompt-file",
    },
    session={
        "resume_flag": "-c",
        "session_id_flag": "-r",
        "session_id_source": "json_output",
    },
    permission={"bypass_flag": "-y"},
    skill_generation={
        "enabled": True,
        "docs_source": "https://www.codebuddy.ai/docs/cli/cli-reference",
    },
)

# Codebuddy SDK Profile — 不同于 CLI，直接编程调用
CODEBUDDY_SDK_PROFILE = CLIProfile(
    name="codebuddy-sdk",
    command="codebuddy-agent-sdk",  # Python 包名，非命令
    version_command="pip show codebuddy-agent-sdk",
    dispatch={
        "exec_template": None,  # SDK 模式不走 subprocess
        "input_method": "sdk",
        "output_format": "stream-json",
        "stream_supported": True,
        "system_prompt_method": "api",
        "system_prompt_flag": None,
    },
    session={
        "resume_flag": None,
        "session_id_flag": None,
        "session_id_source": "sdk_session",
    },
    permission={"bypass_flag": None},  # 通过 options.permission_mode 控制
    skill_generation={
        "enabled": True,
        "docs_source": "https://www.codebuddy.ai/docs/cli/sdk",
    },
)

# Codebuddy Provider 完整配置
CODEBUDDY_PROVIDER = {
    "name": "Codebuddy",
    "cli": {
        "command": "codebuddy",
        "install_hint": "npm install -g @anthropic-ai/codebuddy",
        "auth_command": "codebuddy",  # 交互式登录
        "api_key_env": "CODEBUDDY_API_KEY",
        "models": ["default"],  # Codebuddy 自带模型选择
        "context_window": 200000,
        "profile": CODEBUDDY_CLI_PROFILE,
    },
    "sdk": {
        "package": "codebuddy-agent-sdk",
        "install_hint": "pip install codebuddy-agent-sdk",
        "auth_command": None,  # 复用 CLI 登录凭证
        "api_key_env": "CODEBUDDY_API_KEY",
        "models": ["default"],
        "context_window": 200000,
        "profile": CODEBUDDY_SDK_PROFILE,
    },
}

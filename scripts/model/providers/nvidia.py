"""
ADDS Model Layer — NVIDIA NIM Provider 配置

NVIDIA NIM 提供 OpenAI 兼容格式的 API。
API Key 环境变量：NVIDIA_API_KEY
官方文档：https://docs.api.nvidia.com
"""

NVIDIA_PROVIDER = {
    "name": "NVIDIA NIM",
    "api": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key_env": "NVIDIA_API_KEY",
        "adapter": "openai",   # 使用 OpenAI 兼容适配器
        "models": [
            # ── Meta Llama ──────────────────────────────────────
            "meta/llama-3.3-70b-instruct",
            "meta/llama-3.1-405b-instruct",
            "meta/llama-3.1-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            "meta/llama-4-maverick-17b-128e-instruct",
            # ── NVIDIA Nemotron ──────────────────────────────────
            "nvidia/llama-3.1-nemotron-ultra-253b-v1",
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "nvidia/llama-3.3-nemotron-super-49b-v1.5",
            "nvidia/llama-3.1-nemotron-51b-instruct",
            "nvidia/llama-3.1-nemotron-nano-8b-v1",
            "nvidia/nemotron-4-340b-instruct",
            # ── Mistral ──────────────────────────────────────────
            "mistralai/mistral-large-3-675b-instruct-2512",
            "mistralai/mistral-large-2-instruct",
            "mistralai/mistral-medium-3-instruct",
            "mistralai/mistral-small-4-119b-2603",
            "mistralai/mixtral-8x22b-instruct-v0.1",
            "mistralai/mistral-nemotron",
            "mistralai/devstral-2-123b-instruct-2512",
            "mistralai/magistral-small-2506",
            # ── DeepSeek ─────────────────────────────────────────
            "deepseek-ai/deepseek-v3.2",
            "deepseek-ai/deepseek-v3.1-terminus",
            # ── Qwen ─────────────────────────────────────────────
            "qwen/qwen3.5-397b-a17b",
            "qwen/qwen3.5-122b-a10b",
            "qwen/qwen3-coder-480b-a35b-instruct",
            "qwen/qwen2.5-coder-32b-instruct",
            # ── Moonshot Kimi ─────────────────────────────────────
            "moonshotai/kimi-k2-instruct",
            "moonshotai/kimi-k2-thinking",
            # ── Google Gemma ──────────────────────────────────────
            "google/gemma-4-31b-it",
            "google/gemma-3-27b-it",
            "google/gemma-3-12b-it",
            # ── Microsoft Phi ─────────────────────────────────────
            "microsoft/phi-4-mini-instruct",
            "microsoft/phi-3.5-moe-instruct",
            # ── MiniMax ───────────────────────────────────────────
            "minimaxai/minimax-m2.7",
            "minimaxai/minimax-m2.5",
            # ── IBM Granite ───────────────────────────────────────
            "ibm/granite-3.0-8b-instruct",
            "ibm/granite-34b-code-instruct",
            # ── Writer Palmyra ────────────────────────────────────
            "writer/palmyra-fin-70b-32k",
            "writer/palmyra-med-70b-32k",
        ],
        "context_window": 128000,
    },
}

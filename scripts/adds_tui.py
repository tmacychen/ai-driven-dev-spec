#!/usr/bin/env python3
"""
ADDS TUI 入口

用法：
  adds start --tui              启动 TUI 模式
  python3 scripts/adds_tui.py   直接运行
"""

import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))


def run_tui(model=None, project_root: str = ".", skin=None,
            perm_mode: str = "default") -> None:
    """启动 TUI 应用"""
    from tui.app import ADDSApp
    app = ADDSApp(
        model=model,
        project_root=project_root,
        skin=skin,
        perm_mode=perm_mode,
    )
    app.run()


if __name__ == "__main__":
    # 独立运行时使用 mock 模型（用于开发调试）
    import argparse

    parser = argparse.ArgumentParser(description="ADDS TUI")
    parser.add_argument("--mock", action="store_true", help="使用 Mock 模型（调试用）")
    parser.add_argument("--perm", default="default",
                        choices=["default", "plan", "auto", "bypass"])
    args = parser.parse_args()

    model = None
    if args.mock or True:  # 默认使用 mock
        from model.base import ModelInterface, ModelResponse

        class MockModel(ModelInterface):
            async def chat(self, messages, system_prompt=None, tools=None,
                           stream=True, **kwargs):
                last = messages[-1]["content"] if messages else ""
                response = f"[Mock] 收到: {last[:50]}"
                yield ModelResponse(
                    content=response,
                    model="mock",
                    usage={"input_tokens": 10, "output_tokens": 20},
                    finish_reason="stop",
                )

            def count_tokens(self, text: str) -> int:
                return len(text) // 4

            def get_context_window(self) -> int:
                return 128000

            def get_model_name(self) -> str:
                return "Mock-Model"

            def supports_feature(self, name: str) -> bool:
                return False

        model = MockModel()

    run_tui(model=model, perm_mode=args.perm)

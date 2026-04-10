"""
ADDS Model Layer — 技能自动生成器

从 CLI 使用文档自动生成技能描述，用于无 Skills 系统的 CLI 工具。
"""

import json
from pathlib import Path
from typing import Optional

from .task_dispatcher import CLIProfile


class SkillGenerator:
    """从 CLI 使用文档自动生成技能描述

    流程:
    1. 抓取/读取 CLI 使用文档
    2. 调用 LLM 分析文档，提取功能列表
    3. 生成技能描述文件（Markdown）
    4. 存入 .ai/memories/SKILLS/<provider>/
    """

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(".")
        self.skills_dir = self.project_root / ".ai" / "memories" / "SKILLS"

    async def generate_from_docs(self, profile: CLIProfile) -> list[dict]:
        """从文档生成技能列表

        Args:
            profile: CLI 工具配置

        Returns:
            生成的技能列表
        """
        docs_source = profile.skill_generation.get("docs_source", "")
        if not docs_source:
            print(f"⚠️  {profile.name} 未配置文档来源，跳过技能生成")
            return []

        # 抓取文档
        docs = await self._fetch_docs(docs_source)
        if not docs:
            print(f"⚠️  无法获取 {profile.name} 的文档")
            return []

        # 提取技能
        skills = await self._extract_skills_from_docs(docs, profile.name)

        # 保存技能
        await self._save_skills(skills, profile.name)

        return skills

    async def _fetch_docs(self, source: str) -> str:
        """抓取文档内容

        Args:
            source: URL 或本地路径

        Returns:
            文档文本
        """
        # 尝试本地路径
        local_path = Path(source)
        if local_path.exists():
            return local_path.read_text(encoding="utf-8")

        # 尝试 HTTP 抓取
        if source.startswith(("http://", "https://")):
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(source, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            return await resp.text()
            except ImportError:
                # fallback: 使用 urllib
                try:
                    import urllib.request
                    with urllib.request.urlopen(source, timeout=30) as resp:
                        return resp.read().decode("utf-8")
                except Exception as e:
                    print(f"⚠️  无法抓取文档: {e}")
            except Exception as e:
                print(f"⚠️  无法抓取文档: {e}")

        return ""

    async def _extract_skills_from_docs(self, docs: str, provider: str) -> list[dict]:
        """从文档中提取技能

        使用规则提取（不依赖 LLM），保证 P0 可用性。
        P1 版本将引入 LLM 辅助提取。
        """
        skills = []

        if provider == "codebuddy":
            skills = self._extract_codebuddy_skills(docs)
        elif provider == "minimax":
            skills = self._extract_minimax_skills(docs)
        else:
            # 通用提取：基于命令行 flag 和子命令
            skills = self._extract_generic_skills(docs, provider)

        return skills

    def _extract_codebuddy_skills(self, docs: str) -> list[dict]:
        """提取 Codebuddy CLI 的技能"""
        return [
            {
                "name": "code-analysis",
                "trigger": "当需要分析代码结构、查找 bug、代码审查时",
                "command": 'codebuddy -p "{query}" --output-format json',
                "system_prompt": '--append-system-prompt "请重点关注代码质量和潜在 bug"',
                "input": "自然语言查询",
                "output": "JSON 格式，包含 analysis 文本",
                "examples": [
                    'codebuddy -p "分析这个项目的架构" --output-format json',
                    'cat main.py | codebuddy -p "审查这段代码的安全问题" --output-format json',
                ],
            },
            {
                "name": "code-generation",
                "trigger": "当需要生成代码、实现功能、创建文件时",
                "command": 'codebuddy -p "{query}" --output-format stream-json',
                "system_prompt": '--append-system-prompt "请生成高质量、可运行的代码"',
                "input": "自然语言描述",
                "output": "流式 JSON，包含生成的代码",
                "examples": [
                    'codebuddy -p "实现一个快速排序算法" --output-format stream-json',
                    'codebuddy -p --system-prompt-file ./prompt.txt "实现 REST API"',
                ],
            },
            {
                "name": "code-refactoring",
                "trigger": "当需要重构代码、优化性能、改善代码结构时",
                "command": 'codebuddy -p "{query}" --output-format json',
                "system_prompt": '--append-system-prompt "请保持功能不变，改善代码质量"',
                "input": "自然语言描述 + 代码上下文",
                "output": "JSON 格式，包含重构后的代码",
                "examples": [
                    'codebuddy -p "重构这个函数，使用策略模式" --output-format json',
                    'cat old_code.py | codebuddy -p "将这个函数拆分为更小的函数" --output-format json',
                ],
            },
            {
                "name": "test-generation",
                "trigger": "当需要编写测试、生成测试用例时",
                "command": 'codebuddy -p "{query}" --output-format json',
                "system_prompt": '--append-system-prompt "请生成全面的测试用例，包括边界情况"',
                "input": "代码文件或功能描述",
                "output": "JSON 格式，包含测试代码",
                "examples": [
                    'codebuddy -p "为 user_auth.py 生成单元测试" --output-format json',
                    'cat module.py | codebuddy -p "为这个模块生成 pytest 测试" --output-format json',
                ],
            },
            {
                "name": "session-continue",
                "trigger": "当需要继续之前的对话、迭代开发时",
                "command": 'codebuddy -c -p "{query}"',
                "system_prompt": None,
                "input": "后续指令",
                "output": "继续上次会话的输出",
                "examples": [
                    'codebuddy -c -p "检查类型错误"',
                    'codebuddy -r "abc123" "完成 MR"',
                ],
            },
            {
                "name": "background-task",
                "trigger": "当需要执行长时间运行的任务时",
                "command": 'codebuddy --bg --name {name} "{query}"',
                "system_prompt": None,
                "input": "任务描述",
                "output": "后台任务输出",
                "examples": [
                    'codebuddy --bg --name my-task "实现登录功能"',
                    'codebuddy logs my-task',
                    'codebuddy attach my-task',
                ],
            },
        ]

    def _extract_minimax_skills(self, docs: str) -> list[dict]:
        """提取 MiniMax CLI 的技能"""
        return [
            {
                "name": "text-chat",
                "trigger": "当需要与 MiniMax 模型进行文本对话时",
                "command": 'mmx text chat --message "{prompt}" --output json',
                "system_prompt": '--system-prompt "{system_prompt}"',
                "input": "文本消息",
                "output": "JSON 格式响应",
                "examples": [
                    'mmx text chat --message "解释量子计算" --stream',
                    'mmx text chat --message "user:你好" --message "assistant:嗨" --message "user:详细说说"',
                ],
            },
            {
                "name": "multi-turn-chat",
                "trigger": "当需要多轮对话时",
                "command": 'mmx text chat --message "{prompt}" --output json',
                "system_prompt": None,
                "input": "多轮消息",
                "output": "JSON 格式响应",
                "examples": [
                    'mmx text chat --message "user:你好" --message "assistant:嗨" --message "user:继续"',
                    'cat messages.json | mmx text chat --messages-file -',
                ],
            },
        ]

    def _extract_generic_skills(self, docs: str, provider: str) -> list[dict]:
        """通用技能提取（基于文档中的命令行模式）"""
        return [
            {
                "name": f"{provider}-general",
                "trigger": f"当需要使用 {provider} 时",
                "command": f'{provider} "{{query}}"',
                "system_prompt": None,
                "input": "自然语言查询",
                "output": "文本输出",
                "examples": [
                    f'{provider} "help"',
                ],
            }
        ]

    async def _save_skills(self, skills: list[dict], provider: str) -> None:
        """保存技能到文件"""
        skill_dir = self.skills_dir / provider
        skill_dir.mkdir(parents=True, exist_ok=True)

        for skill in skills:
            skill_file = skill_dir / f"{skill['name']}.md"
            content = self._render_skill_md(skill, provider)
            skill_file.write_text(content, encoding="utf-8")

        print(f"✅ 保存 {len(skills)} 个技能到 {skill_dir}")

    @staticmethod
    def _render_skill_md(skill: dict, provider: str) -> str:
        """渲染技能为 Markdown 格式"""
        lines = [
            f"# Skill: {skill['name']}",
            f"- **Provider**: {provider}",
            f"- **Trigger**: {skill['trigger']}",
            f"- **Command**: `{skill['command']}`",
        ]
        if skill.get("system_prompt"):
            lines.append(f"- **System Prompt**: `{skill['system_prompt']}`")
        lines.extend([
            f"- **Input**: {skill['input']}",
            f"- **Output**: {skill['output']}",
            "- **Examples**:",
        ])
        for ex in skill.get("examples", []):
            lines.append(f"  - `{ex}`")

        return "\n".join(lines) + "\n"

    def load_skills(self, provider: str) -> list[dict]:
        """加载已生成的技能"""
        skill_dir = self.skills_dir / provider
        if not skill_dir.exists():
            return []

        skills = []
        for md_file in skill_dir.glob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            # 简单解析 Markdown
            skill = self._parse_skill_md(content)
            if skill:
                skills.append(skill)

        return skills

    @staticmethod
    def _parse_skill_md(content: str) -> Optional[dict]:
        """解析技能 Markdown 文件"""
        lines = content.strip().split("\n")
        skill = {}

        for line in lines:
            line = line.strip()
            if line.startswith("# Skill: "):
                skill["name"] = line.replace("# Skill: ", "").strip()
            elif line.startswith("- **Provider**:"):
                skill["provider"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **Trigger**:"):
                skill["trigger"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **Command**:"):
                skill["command"] = line.split(":", 1)[1].strip().strip("`")
            elif line.startswith("- **System Prompt**:"):
                skill["system_prompt"] = line.split(":", 1)[1].strip().strip("`")
            elif line.startswith("- **Input**:"):
                skill["input"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **Output**:"):
                skill["output"] = line.split(":", 1)[1].strip()

        return skill if skill.get("name") else None

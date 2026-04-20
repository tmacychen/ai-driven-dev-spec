#!/usr/bin/env python3
"""
ADDS 技能渐进式披露管理器

设计目标：
- Level 0: 技能列表（名称+描述+类别），始终注入上下文，~50 token/skill
- Level 1: 技能详情（触发条件+操作步骤），按需加载，~200-500 token/skill
- Level 2: 技能参考文件，执行时加载，~500-2000 token/skill

核心优势：
- 避免一次性注入所有技能描述浪费 Token
- 按需加载，只在 Agent 需要时展开详细信息
- 与 SkillGenerator 和记忆系统集成

参考：P1 路线图 §8.1 技能渐进式披露
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════

@dataclass
class SkillMeta:
    """技能元数据（Level 0 — 始终注入上下文）"""
    name: str
    description: str
    category: str = "general"  # general | tool | pattern | domain
    provider: str = ""
    tags: List[str] = field(default_factory=list)
    version: str = "1.0"

    def to_index_line(self) -> str:
        """Level 0 输出：单行索引"""
        tag_str = ",".join(self.tags) if self.tags else ""
        return f"- [{self.category}] {self.name}: {self.description} | provider={self.provider} tags={tag_str}"


@dataclass
class SkillDetail:
    """技能详情（Level 1 — 按需加载）"""
    name: str
    trigger: str  # 触发条件
    command: str  # 命令模板
    input_desc: str = ""
    output_desc: str = ""
    system_prompt: Optional[str] = None
    examples: List[str] = field(default_factory=list)
    notes: str = ""
    meta: Optional[SkillMeta] = None

    def to_level1_text(self) -> str:
        """Level 1 输出：完整技能描述"""
        lines = [
            f"### Skill: {self.name}",
            f"- **触发**: {self.trigger}",
            f"- **命令**: `{self.command}`",
        ]
        if self.input_desc:
            lines.append(f"- **输入**: {self.input_desc}")
        if self.output_desc:
            lines.append(f"- **输出**: {self.output_desc}")
        if self.system_prompt:
            lines.append(f"- **System Prompt**: `{self.system_prompt}`")
        if self.examples:
            lines.append("- **示例**:")
            for ex in self.examples:
                lines.append(f"  - `{ex}`")
        if self.notes:
            lines.append(f"- **注意**: {self.notes}")
        return "\n".join(lines)


@dataclass
class SkillFile:
    """技能参考文件（Level 2 — 执行时加载）"""
    name: str
    path: str  # 相对路径
    description: str
    size_hint: str = ""  # 如 "~500 token"

    def to_level2_ref(self) -> str:
        """Level 2 输出：文件引用"""
        size = f" ({self.size_hint})" if self.size_hint else ""
        return f"- `{self.path}` — {self.description}{size}"


# ═══════════════════════════════════════════════════════════
# 技能管理器
# ═══════════════════════════════════════════════════════════

class SkillManager:
    """技能渐进式披露管理器

    核心职责:
    1. 管理技能库的 CRUD
    2. 分级加载技能内容（Level 0/1/2）
    3. 生成注入 System Prompt 的技能段落
    4. 按触发条件匹配技能
    5. 记录技能使用统计
    """

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.skills_dir = self.project_root / ".ai" / "memories" / "SKILLS"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.skills_dir / "registry.json"

        # 内存缓存
        self._meta_cache: Dict[str, SkillMeta] = {}
        self._detail_cache: Dict[str, SkillDetail] = {}
        self._file_cache: Dict[str, List[SkillFile]] = {}

        # 使用统计
        self._usage_stats: Dict[str, int] = {}

        # 加载注册表
        self._load_registry()

    # ════════════════════════════════════════════
    # Level 0: 技能列表（始终注入）
    # ════════════════════════════════════════════

    def skills_list(self) -> List[SkillMeta]:
        """Level 0: 获取所有技能元数据列表

        Returns:
            技能元数据列表，用于注入 System Prompt
        """
        return list(self._meta_cache.values())

    def build_level0_section(self) -> str:
        """构建 Level 0 技能索引段落（注入 System Prompt）

        格式：每个技能一行，包含名称+描述+类别
        Token 预算：~50 token/skill
        """
        metas = self.skills_list()
        if not metas:
            return ""

        lines = [
            "## 可用技能（Level 0 索引）",
            "",
            "以下是当前可用的技能列表。需要使用某技能时，调用 `skill_view(name)` 加载详情。",
            "",
        ]

        # 按类别分组
        by_category: Dict[str, List[SkillMeta]] = {}
        for meta in metas:
            by_category.setdefault(meta.category, []).append(meta)

        for category, items in sorted(by_category.items()):
            lines.append(f"### {category}")
            for meta in items:
                lines.append(meta.to_index_line())
            lines.append("")

        # 使用提示
        lines.append("💡 使用 `skill_view(skill_name)` 查看技能详情，`skill_load(skill_name, path)` 加载参考文件。")

        return "\n".join(lines)

    # ════════════════════════════════════════════
    # Level 1: 技能详情（按需加载）
    # ════════════════════════════════════════════

    def skill_view(self, name: str) -> Optional[SkillDetail]:
        """Level 1: 查看技能详情

        Args:
            name: 技能名称

        Returns:
            技能详情，不存在返回 None
        """
        # 先查缓存
        if name in self._detail_cache:
            self._record_usage(name)
            return self._detail_cache[name]

        # 从磁盘加载
        detail = self._load_skill_detail(name)
        if detail:
            self._detail_cache[name] = detail
            self._record_usage(name)

        return detail

    def build_level1_section(self, skill_names: List[str]) -> str:
        """构建 Level 1 技能详情段落

        Args:
            skill_names: 需要展开的技能名称列表

        Returns:
            合并后的技能详情文本
        """
        sections = []
        for name in skill_names:
            detail = self.skill_view(name)
            if detail:
                sections.append(detail.to_level1_text())

        if not sections:
            return ""

        header = "## 技能详情（Level 1 — 按需加载）\n"
        return header + "\n\n".join(sections)

    # ════════════════════════════════════════════
    # Level 2: 技能参考文件（执行时加载）
    # ════════════════════════════════════════════

    def skill_files(self, name: str) -> List[SkillFile]:
        """获取技能的参考文件列表"""
        if name in self._file_cache:
            return self._file_cache[name]

        files = self._load_skill_files(name)
        self._file_cache[name] = files
        return files

    def skill_load(self, name: str, file_path: str) -> Optional[str]:
        """Level 2: 加载技能参考文件内容

        Args:
            name: 技能名称
            file_path: 参考文件相对路径

        Returns:
            文件内容，不存在返回 None
        """
        full_path = self.skills_dir / name / file_path
        if not full_path.exists():
            return None

        self._record_usage(name)
        return full_path.read_text(encoding="utf-8")

    def build_level2_section(self, name: str, file_path: str) -> str:
        """构建 Level 2 参考文件段落"""
        content = self.skill_load(name, file_path)
        if not content:
            return f"⚠️ 技能参考文件不存在: {name}/{file_path}"

        return f"## 技能参考文件: {name}/{file_path}\n\n{content}"

    # ════════════════════════════════════════════
    # 技能匹配
    # ════════════════════════════════════════════

    def match_skills(self, query: str) -> List[Tuple[str, float]]:
        """根据查询匹配技能

        使用关键词匹配（P1），未来可升级为语义检索（P2）。

        Args:
            query: 用户查询

        Returns:
            [(skill_name, relevance_score), ...] 按相关性降序
        """
        query_lower = query.lower()
        results = []

        for name, meta in self._meta_cache.items():
            score = 0.0

            # 名称匹配
            if name.lower() in query_lower:
                score += 0.5
            # 描述匹配
            if meta.description.lower() in query_lower or any(
                w in meta.description.lower() for w in query_lower.split() if len(w) > 2
            ):
                score += 0.3
            # 标签匹配
            for tag in meta.tags:
                if tag.lower() in query_lower:
                    score += 0.2

            # 触发条件匹配（如果有 Level 1 详情）
            if name in self._detail_cache:
                trigger = self._detail_cache[name].trigger.lower()
                if any(w in trigger for w in query_lower.split() if len(w) > 2):
                    score += 0.3

            if score > 0:
                results.append((name, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def suggest_skills(self, query: str, top_k: int = 3) -> List[str]:
        """根据查询推荐技能名称

        Args:
            query: 用户查询
            top_k: 返回前 K 个推荐

        Returns:
            技能名称列表
        """
        matches = self.match_skills(query)
        return [name for name, _ in matches[:top_k]]

    # ════════════════════════════════════════════
    # 技能管理（CRUD）
    # ════════════════════════════════════════════

    def register_skill(
        self,
        name: str,
        description: str,
        category: str = "general",
        provider: str = "",
        tags: Optional[List[str]] = None,
        trigger: str = "",
        command: str = "",
        input_desc: str = "",
        output_desc: str = "",
        system_prompt: Optional[str] = None,
        examples: Optional[List[str]] = None,
        notes: str = "",
        ref_files: Optional[List[Dict]] = None,
    ) -> bool:
        """注册新技能

        Args:
            name: 技能名称（唯一标识）
            description: 简短描述（Level 0）
            category: 类别
            provider: 来源工具
            tags: 标签
            trigger: 触发条件（Level 1）
            command: 命令模板（Level 1）
            input_desc: 输入描述
            output_desc: 输出描述
            system_prompt: System Prompt 模板
            examples: 示例命令
            notes: 注意事项
            ref_files: 参考文件 [{"name", "path", "description", "size_hint"}]

        Returns:
            是否注册成功
        """
        if name in self._meta_cache:
            logger.warning(f"技能已存在: {name}，将更新")
            return self.update_skill(name, description=description, **{
                k: v for k, v in locals().items()
                if k not in ("self", "name", "description") and v
            })

        # 创建元数据
        meta = SkillMeta(
            name=name,
            description=description,
            category=category,
            provider=provider,
            tags=tags or [],
        )
        self._meta_cache[name] = meta

        # 创建详情
        if trigger or command:
            detail = SkillDetail(
                name=name,
                trigger=trigger,
                command=command,
                input_desc=input_desc,
                output_desc=output_desc,
                system_prompt=system_prompt,
                examples=examples or [],
                notes=notes,
                meta=meta,
            )
            self._detail_cache[name] = detail
            self._save_skill_detail(detail)

        # 创建参考文件
        if ref_files:
            skill_files = []
            for rf in ref_files:
                sf = SkillFile(
                    name=name,
                    path=rf["path"],
                    description=rf["description"],
                    size_hint=rf.get("size_hint", ""),
                )
                skill_files.append(sf)
            self._file_cache[name] = skill_files
            self._save_skill_files(name, skill_files)

        # 保存注册表
        self._save_registry()
        logger.info(f"Registered skill: {name}")
        return True

    def update_skill(self, name: str, **kwargs) -> bool:
        """更新技能属性"""
        if name not in self._meta_cache:
            return False

        meta = self._meta_cache[name]
        for key, value in kwargs.items():
            if value and hasattr(meta, key):
                setattr(meta, key, value)

        if name in self._detail_cache:
            detail = self._detail_cache[name]
            for key, value in kwargs.items():
                if value and hasattr(detail, key):
                    setattr(detail, key, value)
            self._save_skill_detail(detail)

        self._save_registry()
        return True

    def delete_skill(self, name: str) -> bool:
        """删除技能"""
        if name not in self._meta_cache:
            return False

        del self._meta_cache[name]
        self._detail_cache.pop(name, None)
        self._file_cache.pop(name, None)
        self._usage_stats.pop(name, None)

        # 删除磁盘文件
        skill_dir = self.skills_dir / name
        if skill_dir.exists():
            import shutil
            shutil.rmtree(skill_dir)

        self._save_registry()
        logger.info(f"Deleted skill: {name}")
        return True

    # ════════════════════════════════════════════
    # 从 SkillGenerator 导入
    # ════════════════════════════════════════════

    def import_from_skill_generator(self, provider: str) -> int:
        """从 SkillGenerator 生成的技能文件导入

        Args:
            provider: 提供者名称（如 codebuddy, minimax）

        Returns:
            导入的技能数量
        """
        from model.skill_generator import SkillGenerator

        gen = SkillGenerator(project_root=self.project_root)
        skills = gen.load_skills(provider)

        count = 0
        for skill in skills:
            name = skill.get("name", "")
            if not name:
                continue

            # 从 SkillGenerator 格式提取
            trigger = skill.get("trigger", "")
            command = skill.get("command", "")
            input_desc = skill.get("input", "")
            output_desc = skill.get("output", "")
            system_prompt = skill.get("system_prompt")
            examples = skill.get("examples", [])

            # 推断类别
            category = "tool"
            if any(kw in name for kw in ("analysis", "review", "check")):
                category = "pattern"
            elif any(kw in name for kw in ("generation", "refactor")):
                category = "domain"

            # 推断描述
            description = trigger if trigger else f"{provider} {name} skill"
            if len(description) > 80:
                description = description[:77] + "..."

            # 推断标签
            tags = [provider]
            if "code" in name:
                tags.append("code")
            if "test" in name:
                tags.append("testing")

            self.register_skill(
                name=name,
                description=description,
                category=category,
                provider=provider,
                tags=tags,
                trigger=trigger,
                command=command,
                input_desc=input_desc,
                output_desc=output_desc,
                system_prompt=system_prompt,
                examples=examples,
            )
            count += 1

        return count

    # ════════════════════════════════════════════
    # 使用统计
    # ════════════════════════════════════════════

    def _record_usage(self, name: str) -> None:
        """记录技能使用"""
        self._usage_stats[name] = self._usage_stats.get(name, 0) + 1

    def get_usage_stats(self) -> Dict[str, int]:
        """获取使用统计"""
        return dict(sorted(self._usage_stats.items(), key=lambda x: x[1], reverse=True))

    def get_status(self) -> Dict:
        """获取技能管理器状态"""
        total = len(self._meta_cache)
        with_details = len(self._detail_cache)
        with_files = len(self._file_cache)
        categories = {}
        for meta in self._meta_cache.values():
            categories[meta.category] = categories.get(meta.category, 0) + 1

        return {
            "total_skills": total,
            "with_level1": with_details,
            "with_level2": with_files,
            "categories": categories,
            "total_usage": sum(self._usage_stats.values()),
        }

    # ════════════════════════════════════════════
    # 注册表持久化
    # ════════════════════════════════════════════

    def _load_registry(self) -> None:
        """加载注册表"""
        if not self.registry_path.exists():
            return

        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
            for name, meta_dict in data.get("skills", {}).items():
                self._meta_cache[name] = SkillMeta(
                    name=name,
                    description=meta_dict.get("description", ""),
                    category=meta_dict.get("category", "general"),
                    provider=meta_dict.get("provider", ""),
                    tags=meta_dict.get("tags", []),
                    version=meta_dict.get("version", "1.0"),
                )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load skill registry: {e}")

        # 加载使用统计
        stats_path = self.skills_dir / "usage_stats.json"
        if stats_path.exists():
            try:
                self._usage_stats = json.loads(stats_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_registry(self) -> None:
        """保存注册表"""
        skills_data = {}
        for name, meta in self._meta_cache.items():
            skills_data[name] = {
                "description": meta.description,
                "category": meta.category,
                "provider": meta.provider,
                "tags": meta.tags,
                "version": meta.version,
            }

        data = {
            "version": "1.0",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "skills": skills_data,
        }

        self.registry_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # 保存使用统计
        stats_path = self.skills_dir / "usage_stats.json"
        stats_path.write_text(
            json.dumps(self._usage_stats, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load_skill_detail(self, name: str) -> Optional[SkillDetail]:
        """从磁盘加载技能详情"""
        detail_path = self.skills_dir / name / "detail.json"
        if not detail_path.exists():
            # 尝试从 Markdown 加载（兼容 SkillGenerator 格式）
            md_path = self.skills_dir / name / f"{name}.md"
            if md_path.exists():
                return self._parse_skill_md(md_path.read_text(encoding="utf-8"), name)
            return None

        try:
            data = json.loads(detail_path.read_text(encoding="utf-8"))
            meta = self._meta_cache.get(name)
            return SkillDetail(
                name=name,
                trigger=data.get("trigger", ""),
                command=data.get("command", ""),
                input_desc=data.get("input_desc", ""),
                output_desc=data.get("output_desc", ""),
                system_prompt=data.get("system_prompt"),
                examples=data.get("examples", []),
                notes=data.get("notes", ""),
                meta=meta,
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load skill detail {name}: {e}")
            return None

    def _save_skill_detail(self, detail: SkillDetail) -> None:
        """保存技能详情到磁盘"""
        skill_dir = self.skills_dir / detail.name
        skill_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "trigger": detail.trigger,
            "command": detail.command,
            "input_desc": detail.input_desc,
            "output_desc": detail.output_desc,
            "system_prompt": detail.system_prompt,
            "examples": detail.examples,
            "notes": detail.notes,
        }

        detail_path = skill_dir / "detail.json"
        detail_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # 同时保存 Markdown 格式（兼容 SkillGenerator）
        md_path = skill_dir / f"{detail.name}.md"
        md_path.write_text(self._render_skill_md(detail), encoding="utf-8")

    def _load_skill_files(self, name: str) -> List[SkillFile]:
        """加载技能参考文件列表"""
        files_path = self.skills_dir / name / "files.json"
        if not files_path.exists():
            return []

        try:
            data = json.loads(files_path.read_text(encoding="utf-8"))
            return [
                SkillFile(
                    name=name,
                    path=f.get("path", ""),
                    description=f.get("description", ""),
                    size_hint=f.get("size_hint", ""),
                )
                for f in data
            ]
        except (json.JSONDecodeError, KeyError):
            return []

    def _save_skill_files(self, name: str, files: List[SkillFile]) -> None:
        """保存技能参考文件列表"""
        skill_dir = self.skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        data = [
            {"path": f.path, "description": f.description, "size_hint": f.size_hint}
            for f in files
        ]

        files_path = skill_dir / "files.json"
        files_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _parse_skill_md(content: str, name: str) -> Optional[SkillDetail]:
        """从 Markdown 解析技能详情（兼容 SkillGenerator 格式）"""
        detail = SkillDetail(name=name, trigger="", command="")

        for line in content.strip().split("\n"):
            line = line.strip()
            if line.startswith("- **Trigger**:"):
                detail.trigger = line.split(":", 1)[1].strip()
            elif line.startswith("- **Command**:"):
                detail.command = line.split(":", 1)[1].strip().strip("`")
            elif line.startswith("- **System Prompt**:"):
                detail.system_prompt = line.split(":", 1)[1].strip().strip("`")
            elif line.startswith("- **Input**:"):
                detail.input_desc = line.split(":", 1)[1].strip()
            elif line.startswith("- **Output**:"):
                detail.output_desc = line.split(":", 1)[1].strip()

        return detail if detail.trigger or detail.command else None

    @staticmethod
    def _render_skill_md(detail: SkillDetail) -> str:
        """渲染技能为 Markdown 格式"""
        lines = [
            f"# Skill: {detail.name}",
            f"- **Trigger**: {detail.trigger}",
            f"- **Command**: `{detail.command}`",
        ]
        if detail.input_desc:
            lines.append(f"- **Input**: {detail.input_desc}")
        if detail.output_desc:
            lines.append(f"- **Output**: {detail.output_desc}")
        if detail.system_prompt:
            lines.append(f"- **System Prompt**: `{detail.system_prompt}`")
        if detail.examples:
            lines.append("- **Examples**:")
            for ex in detail.examples:
                lines.append(f"  - `{ex}`")
        if detail.notes:
            lines.append(f"- **Notes**: {detail.notes}")
        return "\n".join(lines) + "\n"


# ═══════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════

def create_skill_manager(project_root: str = ".") -> SkillManager:
    """创建技能管理器"""
    return SkillManager(project_root=project_root)


# ═══════════════════════════════════════════════════════════
# CLI 集成
# ═══════════════════════════════════════════════════════════

def add_skill_subparser(subparsers) -> None:
    """添加 skill 子命令到 CLI parser"""
    skill_parser = subparsers.add_parser("skill", help="技能管理（P1）")
    skill_sub = skill_parser.add_subparsers(dest="skill_command")

    # list
    skill_sub.add_parser("list", help="列出所有技能（Level 0）")

    # view
    view_parser = skill_sub.add_parser("view", help="查看技能详情（Level 1）")
    view_parser.add_argument("name", type=str, help="技能名称")

    # load
    load_parser = skill_sub.add_parser("load", help="加载技能参考文件（Level 2）")
    load_parser.add_argument("name", type=str, help="技能名称")
    load_parser.add_argument("path", type=str, help="参考文件路径")

    # match
    match_parser = skill_sub.add_parser("match", help="匹配技能")
    match_parser.add_argument("query", type=str, help="查询文本")
    match_parser.add_argument("--top-k", type=int, default=5, help="返回数量")

    # register
    reg_parser = skill_sub.add_parser("register", help="注册新技能")
    reg_parser.add_argument("name", type=str, help="技能名称")
    reg_parser.add_argument("--desc", type=str, required=True, help="技能描述")
    reg_parser.add_argument("--category", type=str, default="general",
                            choices=["general", "tool", "pattern", "domain"],
                            help="类别")
    reg_parser.add_argument("--provider", type=str, default="", help="提供者")
    reg_parser.add_argument("--tag", type=str, action="append", dest="tags",
                            help="标签（可多次）")
    reg_parser.add_argument("--trigger", type=str, default="", help="触发条件")
    reg_parser.add_argument("--command", type=str, default="", help="命令模板")

    # import
    imp_parser = skill_sub.add_parser("import", help="从 SkillGenerator 导入")
    imp_parser.add_argument("provider", type=str, help="提供者名称")

    # delete
    del_parser = skill_sub.add_parser("delete", help="删除技能")
    del_parser.add_argument("name", type=str, help="技能名称")

    # stats
    skill_sub.add_parser("stats", help="技能使用统计")


def handle_skill_command(args, project_root: str = ".") -> None:
    """处理 skill 子命令"""
    mgr = SkillManager(project_root=project_root)

    if not args.skill_command or args.skill_command == "list":
        _cmd_skill_list(mgr)
    elif args.skill_command == "view":
        _cmd_skill_view(mgr, args.name)
    elif args.skill_command == "load":
        _cmd_skill_load(mgr, args.name, args.path)
    elif args.skill_command == "match":
        _cmd_skill_match(mgr, args.query, top_k=args.top_k)
    elif args.skill_command == "register":
        _cmd_skill_register(mgr, args.name, desc=args.desc,
                            category=args.category, provider=args.provider,
                            tags=args.tags, trigger=args.trigger,
                            command=args.command)
    elif args.skill_command == "import":
        _cmd_skill_import(mgr, args.provider)
    elif args.skill_command == "delete":
        _cmd_skill_delete(mgr, args.name)
    elif args.skill_command == "stats":
        _cmd_skill_stats(mgr)
    else:
        print("未知 skill 子命令。使用 adds skill --help 查看帮助。")


def _cmd_skill_list(mgr: SkillManager) -> None:
    """adds skill list"""
    metas = mgr.skills_list()
    if not metas:
        print("📭 暂无技能")
        return

    print(f"📋 技能列表（{len(metas)} 个）\n")
    by_category: Dict[str, List[SkillMeta]] = {}
    for meta in metas:
        by_category.setdefault(meta.category, []).append(meta)

    for category, items in sorted(by_category.items()):
        print(f"  [{category}]")
        for meta in items:
            tag_str = f" ({','.join(meta.tags)})" if meta.tags else ""
            provider_str = f" ← {meta.provider}" if meta.provider else ""
            print(f"    - {meta.name}: {meta.description}{tag_str}{provider_str}")
        print()


def _cmd_skill_view(mgr: SkillManager, name: str) -> None:
    """adds skill view"""
    detail = mgr.skill_view(name)
    if not detail:
        print(f"❌ 未找到技能: {name}")
        return

    print(f"📖 技能详情: {name}\n")
    print(detail.to_level1_text())

    # 显示参考文件
    files = mgr.skill_files(name)
    if files:
        print("\n参考文件:")
        for f in files:
            print(f"  {f.to_level2_ref()}")


def _cmd_skill_load(mgr: SkillManager, name: str, path: str) -> None:
    """adds skill load"""
    content = mgr.skill_load(name, path)
    if not content:
        print(f"❌ 未找到参考文件: {name}/{path}")
        return

    print(f"📄 {name}/{path}\n")
    print(content)


def _cmd_skill_match(mgr: SkillManager, query: str, top_k: int = 5) -> None:
    """adds skill match"""
    matches = mgr.match_skills(query)
    if not matches:
        print(f"📭 未找到匹配 \"{query}\" 的技能")
        return

    print(f"🔍 匹配结果: \"{query}\" ({len(matches)} 个)\n")
    for i, (name, score) in enumerate(matches[:top_k], 1):
        meta = mgr._meta_cache.get(name)
        desc = meta.description if meta else ""
        print(f"  {i}. {name} (相关度: {score:.2f})")
        print(f"     {desc}")
        print()


def _cmd_skill_register(mgr: SkillManager, name: str, desc: str = "",
                        category: str = "general", provider: str = "",
                        tags: Optional[List[str]] = None,
                        trigger: str = "", command: str = "") -> None:
    """adds skill register"""
    success = mgr.register_skill(
        name=name,
        description=desc,
        category=category,
        provider=provider,
        tags=tags,
        trigger=trigger,
        command=command,
    )
    if success:
        print(f"✅ 技能已注册: {name}")
        print(f"   描述: {desc}")
        print(f"   类别: {category}")
    else:
        print(f"❌ 注册失败: {name}")


def _cmd_skill_import(mgr: SkillManager, provider: str) -> None:
    """adds skill import"""
    count = mgr.import_from_skill_generator(provider)
    if count > 0:
        print(f"✅ 从 {provider} 导入了 {count} 个技能")
    else:
        print(f"📭 {provider} 无可导入的技能")


def _cmd_skill_delete(mgr: SkillManager, name: str) -> None:
    """adds skill delete"""
    if mgr.delete_skill(name):
        print(f"✅ 已删除技能: {name}")
    else:
        print(f"❌ 未找到技能: {name}")


def _cmd_skill_stats(mgr: SkillManager) -> None:
    """adds skill stats"""
    status = mgr.get_status()
    stats = mgr.get_usage_stats()

    print("=" * 50)
    print("🎯 技能系统状态")
    print("=" * 50)
    print(f"  总技能数: {status['total_skills']}")
    print(f"  Level 1 详情: {status['with_level1']}")
    print(f"  Level 2 参考文件: {status['with_level2']}")
    print(f"  总使用次数: {status['total_usage']}")
    print()

    if status["categories"]:
        print("  类别分布:")
        for cat, count in sorted(status["categories"].items()):
            print(f"    {cat}: {count}")

    if stats:
        print("\n  使用排行:")
        for name, count in list(stats.items())[:10]:
            print(f"    {name}: {count} 次")


# ═══════════════════════════════════════════════════════════
# Logger
# ═══════════════════════════════════════════════════════════

import logging

logger = logging.getLogger(__name__)

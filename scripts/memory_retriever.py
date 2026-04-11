#!/usr/bin/env python3
"""
ADDS Memory Retriever — 记忆检索抽象接口

设计目标：
- P0: RegexMemoryRetriever（基于 rg 的关键词检索）
- P1: VectorMemoryRetriever（向量索引语义检索，占位）
- 统一抽象接口，支持渐进升级

参考：P0-3 路线图 — 记忆检索方式
"""

import asyncio
import logging
import re
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """检索结果"""
    source: str = ""        # "固定记忆" | "记忆索引" | ".mem文件"
    file: str = ""          # "index.mem" | "20260409-153000.mem"
    content: str = ""       # 匹配的内容片段
    relevance: float = 0.0  # 相关度分数 0.0-1.0
    line_number: int = 0    # 行号


class MemoryRetriever(ABC):
    """记忆检索抽象接口"""

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """搜索记忆，返回最相关的 top_k 条结果"""
        pass


class RegexMemoryRetriever(MemoryRetriever):
    """P0: 基于 rg 的关键词检索

    实现策略:
    1. 从 query 中提取关键词（去停用词、保留名词/动词）
    2. 用 rg 在 .ai/sessions/*.mem 和 index.mem 中搜索
    3. 按匹配行数和关键词密度排序
    4. 固定记忆区 + index.mem 的匹配权重加倍
    """

    # 中文停用词
    STOP_WORDS = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
        "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
        "你", "会", "着", "没有", "看", "好", "自己", "这",
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "can", "shall",
        "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "and",
        "but", "or", "not", "no", "nor", "so", "yet", "both",
        "either", "neither", "each", "every", "all", "any", "few",
        "more", "most", "other", "some", "such", "than", "too",
        "very", "just", "about", "above", "below", "between",
    }

    def __init__(self, sessions_dir: str = ".ai/sessions"):
        self.sessions_dir = Path(sessions_dir)

    def _extract_keywords(self, query: str) -> List[str]:
        """从查询中提取搜索关键词

        策略：
        1. 按空格和中文字符边界分词
        2. 去除停用词
        3. 保留 2 字符以上的词
        4. 技术术语保持原样
        """
        # 按空格和标点分词
        words = re.split(r'[\s,，。！？、；：\u201c\u201d\u2018\u2019\uff08\uff09()\[\]{}]+', query)
        keywords = []

        for word in words:
            word = word.strip()
            if not word:
                continue
            # 跳过停用词
            if word.lower() in self.STOP_WORDS:
                continue
            # 跳过单字符（中文单字可能有意义，但搜索噪声太大）
            if len(word) == 1 and not word.isascii():
                continue
            keywords.append(word)

        return keywords

    async def _rg_search(self, keywords: List[str]) -> List[SearchResult]:
        """用 rg 在 .mem 文件中搜索"""
        if not keywords:
            return []

        results = []
        mem_files = list(self.sessions_dir.glob("*.mem"))

        if not mem_files:
            return []

        for keyword in keywords:
            try:
                cmd = ["rg", "-n", "--no-heading", "-i", keyword]
                cmd.extend(str(f) for f in mem_files)

                proc = subprocess.run(
                    cmd, capture_output=True, text=True,
                    cwd=str(self.sessions_dir.parent.parent),
                )

                if proc.returncode != 0:
                    continue

                for line in proc.stdout.strip().split("\n"):
                    if not line:
                        continue

                    # 解析 rg 输出: filename:linenum:content
                    match = re.match(r'(.+?):(\d+):(.*)', line)
                    if match:
                        filepath, linenum, content = match.groups()
                        filename = Path(filepath).name

                        # 判断来源
                        source = ".mem文件"
                        if filename == "index.mem":
                            source = "固定记忆"
                            # 检查是否在索引区
                            if "记忆索引" in content or "| 时间 |" in content:
                                source = "记忆索引"

                        results.append(SearchResult(
                            source=source,
                            file=filename,
                            content=content.strip(),
                            relevance=1.0 if source == "固定记忆" else 0.5,
                            line_number=int(linenum),
                        ))

            except FileNotFoundError:
                # rg 未安装，尝试 grep 回退
                try:
                    grep_cmd = ["grep", "-n", "-i", keyword]
                    grep_cmd.extend(str(f) for f in mem_files)
                    proc = subprocess.run(
                        grep_cmd, capture_output=True, text=True,
                        cwd=str(self.sessions_dir.parent.parent),
                    )
                    if proc.returncode == 0:
                        for line in proc.stdout.strip().split("\n"):
                            if not line:
                                continue
                            # grep 输出格式: filename:linenum:content
                            match = re.match(r'(.+?):(\d+):(.*)', line)
                            if match:
                                filepath, linenum, content = match.groups()
                                results.append(SearchResult(
                                    source=Path(filepath).name,
                                    file=Path(filepath).name,
                                    content=content.strip(),
                                    relevance=0.5,
                                    line_number=int(linenum),
                                ))
                    else:
                        results.extend(await self._python_search(keyword, mem_files))
                except FileNotFoundError:
                    # grep 也没有，回退到纯 Python 搜索
                    if not hasattr(self, '_warned_grep_fallback'):
                        logger.warning(
                            "[ADDS] 未检测到 ripgrep (rg) 或 grep，"
                            "记忆检索将使用 Python 回退搜索（较慢）。"
                            "建议安装 ripgrep: brew install ripgrep"
                        )
                        self._warned_grep_fallback = True
                    results.extend(await self._python_search(keyword, mem_files))
            except Exception as e:
                logger.debug(f"Search error for '{keyword}': {e}")

        return results

    async def _python_search(self, keyword: str,
                             mem_files: List[Path]) -> List[SearchResult]:
        """回退: Python 实现的关键词搜索"""
        results = []
        kw_lower = keyword.lower()

        for mem_path in mem_files:
            try:
                content = mem_path.read_text(encoding="utf-8")
                for i, line in enumerate(content.split("\n"), 1):
                    if kw_lower in line.lower():
                        filename = mem_path.name
                        source = ".mem文件"
                        if filename == "index.mem":
                            source = "固定记忆"

                        results.append(SearchResult(
                            source=source,
                            file=filename,
                            content=line.strip(),
                            relevance=1.0 if source == "固定记忆" else 0.5,
                            line_number=i,
                        ))
            except Exception as e:
                logger.debug(f"Failed to read {mem_path}: {e}")

        return results

    def _rank_and_topk(self, results: List[SearchResult],
                       top_k: int) -> List[SearchResult]:
        """排序并取 top_k

        排序策略：
        1. 固定记忆权重 ×2
        2. 多关键词匹配加权
        3. 按 relevance 降序
        """
        # 合并同文件同行的结果
        merged: Dict[str, SearchResult] = {}
        for r in results:
            key = f"{r.file}:{r.line_number}"
            if key in merged:
                merged[key].relevance += r.relevance * 0.5
            else:
                merged[key] = SearchResult(
                    source=r.source,
                    file=r.file,
                    content=r.content,
                    relevance=r.relevance,
                    line_number=r.line_number,
                )

        # 固定记忆权重加倍
        for r in merged.values():
            if r.source == "固定记忆":
                r.relevance *= 2.0

        # 排序
        ranked = sorted(merged.values(), key=lambda x: x.relevance, reverse=True)
        return ranked[:top_k]

    async def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """搜索记忆

        Args:
            query: 搜索查询
            top_k: 返回结果数

        Returns:
            搜索结果列表
        """
        keywords = self._extract_keywords(query)
        if not keywords:
            return []

        results = await self._rg_search(keywords)
        return self._rank_and_topk(results, top_k)


class VectorMemoryRetriever(MemoryRetriever):
    """P1: 基于向量索引的语义检索（占位，P1 实现）

    技术选型:
    - LanceDB: 轻量本地向量数据库
    - 嵌入模型: 本地 small model 或 API 调用
    - 混合检索: 向量 + rg 融合排序
    """

    async def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """P1 实现: 向量语义检索"""
        logger.warning("VectorMemoryRetriever not implemented, falling back to regex")
        # 回退到正则检索
        fallback = RegexMemoryRetriever()
        return await fallback.search(query, top_k)

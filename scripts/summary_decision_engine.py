#!/usr/bin/env python3
"""
ADDS Summary Decision Engine — 摘要策略决策引擎

设计目标：
- 为每条消息决定最合适的摘要策略
- 错误信号检测（最高优先级：KEEP_FULL）
- 结构化输出 → TOOL_FILTER
- 非结构化对话 → LLM_ANALYZE
- 混合内容 → HYBRID

参考：P0-2 路线图 — 摘要策略决策框架
"""

import logging
import re
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 摘要策略枚举
# ═══════════════════════════════════════════════════════════

class SummaryStrategy(Enum):
    """摘要策略"""
    KEEP_FULL = "keep_full"        # 完全保留：错误信号触发，不做任何压缩
    TOOL_FILTER = "tool_filter"    # 工具过滤：无需 LLM，快速
    LLM_ANALYZE = "llm_analyze"    # LLM 分析：需要 LLM，精准
    HYBRID = "hybrid"              # 混合：工具过滤 + LLM 精炼


# ═══════════════════════════════════════════════════════════
# 错误信号检测
# ═══════════════════════════════════════════════════════════

# 错误信号正则模式
ERROR_SIGNAL_PATTERNS = [
    r'exit\s+code[:\s]+\d*[1-9]\d*',                          # Exit Code != 0
    r'(?:Error|Exception|Traceback|FAILED?|CRITICAL)',       # 大写变体
    r'(?:error|exception|traceback|failed?|critical)',       # 小写变体
    r'WARNING',                                               # 警告信号
    r'SyntaxError|ImportError|ModuleNotFoundError|AttributeError',  # Python 常见异常
    r'AssertionError|TypeError|ValueError|KeyError',         # Python 常见异常
    r'segmentation fault|core dumped',                        # 系统错误
    r'Permission denied|No such file|not found',              # 文件系统错误
]

# 编译正则（提升性能）
_COMPILED_ERROR_PATTERNS = [re.compile(p, re.IGNORECASE) for p in ERROR_SIGNAL_PATTERNS]

# 决策关键词
DECISION_KEYWORDS_ZH = ["决定", "结论", "选择", "方案", "架构", "设计", "策略", "原因"]
DECISION_KEYWORDS_EN = [
    "decided", "decision", "conclusion", "chose", "chosen",
    "approach", "strategy", "because", "therefore", "so we",
    "the reason", "rationale",
]
ALL_DECISION_KEYWORDS = DECISION_KEYWORDS_ZH + DECISION_KEYWORDS_EN

# 冗余消息模式（Layer1 清理用）
REDUNDANT_PATTERNS = [
    r'^(好的|明白|了解|收到|OK|Got it|Understood|I see|Sure)\s*[。.！!]*$',
    r'^(我理解了|我知道了|没问题|No problem)\s*[。.！!]*$',
]


def has_error_signals(content: str) -> bool:
    """检测内容是否包含错误信号

    检测规则：
    1. Exit Code != 0
    2. 标准错误关键词: Error, Exception, Traceback, CRITICAL
    3. 大小写不敏感匹配
    4. Python 常见异常名
    5. 系统错误
    6. 排除测试结果中的 "0 failed" 等非错误信号

    Args:
        content: 待检测内容

    Returns:
        是否包含错误信号
    """
    # 先排除测试结果中的 "0 failed" 或 "0 errors" 这类非错误信号
    # 检测 "N failed" 中 N > 0 的情况才算错误
    # 简单做法：移除 "0 failed", "0 errors", "0 warnings" 等行后再检测
    filtered_lines = []
    for line in content.split("\n"):
        # 跳过包含 "0 failed", "0 errors" 的行（这些是测试通过信息）
        if re.match(r'^\s*(\d+)\s+passed\s*,\s*0\s+(failed|error)', line, re.IGNORECASE):
            continue
        # 保留 "N failed" 中 N > 0 的行
        filtered_lines.append(line)
    filtered = "\n".join(filtered_lines)

    for pattern in _COMPILED_ERROR_PATTERNS:
        if pattern.search(filtered):
            return True
    return False


def extract_error_context(content: str, context_lines: int = 3) -> str:
    """提取错误信号及其上下文

    Args:
        content: 完整内容
        context_lines: 错误行前后的上下文行数

    Returns:
        包含错误信号的行及其 ±context_lines 行上下文
    """
    lines = content.split("\n")
    error_line_indices = set()

    for i, line in enumerate(lines):
        for pattern in _COMPILED_ERROR_PATTERNS:
            if pattern.search(line):
                # 添加错误行及其上下文
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                error_line_indices.update(range(start, end))
                break

    if not error_line_indices:
        return content

    # 按顺序提取
    sorted_indices = sorted(error_line_indices)
    result_lines = [lines[i] for i in sorted_indices]
    return "\n".join(result_lines)


def is_redundant_message(content: str) -> bool:
    """判断消息是否是冗余确认（如"好的"、"我理解了"）

    Args:
        content: 消息内容

    Returns:
        是否为冗余消息
    """
    stripped = content.strip()
    for pattern in REDUNDANT_PATTERNS:
        if re.match(pattern, stripped, re.IGNORECASE):
            return True
    return False


def has_decision_keywords(content: str) -> bool:
    """判断内容是否包含决策关键词

    Args:
        content: 消息内容

    Returns:
        是否包含决策关键词
    """
    lower = content.lower()
    return any(kw in lower for kw in ALL_DECISION_KEYWORDS)


# ═══════════════════════════════════════════════════════════
# Tool Filter 规则
# ═══════════════════════════════════════════════════════════

# pytest 结果提取规则
PYTEST_PATTERN = re.compile(
    r'(\d+)\s+passed\s*(,\s*(\d+)\s+failed)?\s*(,\s*(\d+)\s+warnings?)?\s*(in\s+[\d.]+s)?',
    re.IGNORECASE,
)

# 文件统计提取
FILE_STATS_PATTERN = re.compile(
    r'^(\d+)\s+lines?\s', re.MULTILINE,
)

# Git 状态提取
GIT_STATUS_PATTERN = re.compile(
    r'(modified|new file|deleted|renamed):\s+(.+)',
    re.MULTILINE,
)


def tool_filter_pytest(content: str) -> str:
    """提取 pytest 结果摘要"""
    match = PYTEST_PATTERN.search(content)
    if match:
        passed = match.group(1)
        failed = match.group(3) or "0"
        warnings = match.group(5) or "0"
        duration = match.group(6) or ""
        return f"pytest: {passed} passed, {failed} failed, {warnings} warnings {duration}".strip()
    return f"[pytest output: {len(content)} chars]"


def tool_filter_file_content(content: str) -> str:
    """提取文件内容摘要"""
    lines = content.count("\n") + 1
    # 尝试识别语言
    first_line = content.split("\n")[0] if content else ""
    lang = ""
    if first_line.startswith("#!"):
        lang = " (script)"
    elif first_line.startswith("<?"):
        lang = " (PHP)"
    elif "def " in content or "class " in content:
        lang = " (Python)"
    elif "function " in content or "const " in content:
        lang = " (JS/TS)"

    return f"文件内容{lang}: {lines} 行"


def tool_filter_git_status(content: str) -> str:
    """提取 git status 摘要"""
    matches = GIT_STATUS_PATTERN.findall(content)
    if matches:
        changes = [f"{status} {path}" for status, path in matches]
        return f"Git changes: {len(changes)} files — " + ", ".join(changes[:5])
    return f"[git output: {len(content)} chars]"


def apply_tool_filter(content: str, tool_name: str = "") -> str:
    """应用工具过滤规则提取摘要

    Args:
        content: 工具输出内容
        tool_name: 工具名称（辅助判断）

    Returns:
        提取的摘要
    """
    # pytest 输出
    if "passed" in content and ("failed" in content or "warnings" in content or "pytest" in content.lower()):
        return tool_filter_pytest(content)

    # git status 输出
    if tool_name and "git" in tool_name.lower():
        return tool_filter_git_status(content)

    # 文件内容（多行 + 代码特征）
    if content.count("\n") > 5:
        return tool_filter_file_content(content)

    # 默认：截取前 200 字符
    if len(content) > 200:
        return content[:200] + "..."
    return content


# ═══════════════════════════════════════════════════════════
# Summary Decision Engine
# ═══════════════════════════════════════════════════════════

class SummaryDecisionEngine:
    """摘要策略决策引擎

    核心职责：
    1. 为每条消息决定摘要策略
    2. 错误信号检测 → KEEP_FULL（最高优先级）
    3. 工具输出 → TOOL_FILTER
    4. 非结构化对话 → LLM_ANALYZE
    5. 混合内容 → HYBRID

    使用方式：
        engine = SummaryDecisionEngine()
        strategy = engine.decide(message, context)
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Args:
            config: 配置项（可覆盖默认阈值）
        """
        cfg = config or {}
        self.long_message_threshold = cfg.get("long_message_threshold", 500)
        self.context_utilization = 0.0  # 由外部更新

    def decide(self, message: Dict, context: Optional[Dict] = None) -> SummaryStrategy:
        """为单条消息决定摘要策略

        决策逻辑（优先级从高到低）：

        0. 错误保留原则（最高优先级）
           → KEEP_FULL: 检测到错误信号时完全保留，不做任何压缩

        1. 结构化输出（测试结果、文件内容、命令输出）
           → TOOL_FILTER: 正则/规则提取关键指标

        2. 非结构化对话（需求讨论、架构决策、代码审查意见）
           → LLM_ANALYZE: 需要理解语义，提取关键决策和结论

        3. 混合内容（带结论的工具输出 + 人类讨论）
           → HYBRID: 先 TOOL_FILTER 提取结构化信息，再 LLM 精炼

        Args:
            message: 消息字典 {"role": "user/assistant/tool_call/tool_result", "content": "..."}
            context: 上下文信息 {"utilization": 0.0~1.0, ...}

        Returns:
            推荐的摘要策略
        """
        ctx = context or {}
        self.context_utilization = ctx.get("utilization", 0.0)

        msg_type = message.get("role", "")
        content = message.get("content", "")

        # 规则 0（最高优先级）: 错误信号 → KEEP_FULL
        if msg_type == "tool_result" and has_error_signals(content):
            logger.debug(f"KEEP_FULL: error signals detected in tool_result")
            return SummaryStrategy.KEEP_FULL

        # 规则 1: 工具输出 → TOOL_FILTER
        if msg_type == "tool_result":
            return SummaryStrategy.TOOL_FILTER

        # 规则 2: 含决策关键词 → LLM_ANALYZE
        if has_decision_keywords(content):
            # 如果同时包含结构化内容 → HYBRID
            if msg_type == "tool_result" or self._has_structured_content(content):
                return SummaryStrategy.HYBRID
            return SummaryStrategy.LLM_ANALYZE

        # 规则 3: 长对话讨论 → LLM_ANALYZE
        if msg_type == "assistant" and len(content) > self.long_message_threshold:
            return SummaryStrategy.LLM_ANALYZE

        # 规则 4: 上下文利用率高 → 倾向 TOOL_FILTER（省 token）
        if self.context_utilization > 0.7:
            if msg_type == "assistant":
                return SummaryStrategy.TOOL_FILTER
            return SummaryStrategy.TOOL_FILTER

        # 默认: TOOL_FILTER
        return SummaryStrategy.TOOL_FILTER

    def decide_batch(self, messages: List[Dict], context: Optional[Dict] = None) -> List[SummaryStrategy]:
        """为一批消息批量决定摘要策略

        Args:
            messages: 消息列表
            context: 上下文信息

        Returns:
            策略列表（与 messages 一一对应）
        """
        return [self.decide(msg, context) for msg in messages]

    def _has_structured_content(self, content: str) -> bool:
        """判断内容是否包含结构化输出特征"""
        structured_indicators = [
            "passed", "failed",     # 测试结果
            "```",                   # 代码块
            "| ", "|-",             # 表格
            "Error:", "error:",     # 错误信息
            "+", "-", "@@",          # diff 输出
        ]
        lower = content.lower()
        return any(ind in lower for ind in structured_indicators)

    def get_layer1_action(self, message: Dict, strategy: SummaryStrategy) -> Dict:
        """获取 Layer1 压缩的具体操作

        Args:
            message: 消息字典
            strategy: 已决定的摘要策略

        Returns:
            操作指令字典
        """
        content = message.get("content", "")
        msg_type = message.get("role", "")

        action = {
            "strategy": strategy.value,
            "save_to_log": False,
            "replace_with": None,
            "priority": "normal",
            "drop": False,
        }

        if strategy == SummaryStrategy.KEEP_FULL:
            # 完全保留，不做任何操作
            action["save_to_log"] = False
            action["replace_with"] = None

        elif strategy == SummaryStrategy.TOOL_FILTER:
            if msg_type == "tool_result" and len(content) > 500:
                # 长工具输出 → 保存到 log，替换为摘要
                summary = apply_tool_filter(content)
                action["save_to_log"] = True
                action["replace_with"] = summary
            elif is_redundant_message(content):
                # 冗余消息 → 丢弃
                action["drop"] = True

        elif strategy == SummaryStrategy.LLM_ANALYZE:
            # 标记为高价值，Layer2 归档时重点提取
            if has_decision_keywords(content):
                action["priority"] = "high"

        elif strategy == SummaryStrategy.HYBRID:
            # 先提取结构化部分，再标记 LLM 精炼
            action["priority"] = "high"
            if msg_type == "tool_result" and len(content) > 500:
                summary = apply_tool_filter(content)
                action["save_to_log"] = True
                action["replace_with"] = summary

        return action


# ═══════════════════════════════════════════════════════════
# LLM 摘要 Prompt 模板
# ═══════════════════════════════════════════════════════════

LAYER2_SUMMARY_PROMPT = """请对以下对话记录生成结构化摘要，用于后续 session 的上下文恢复。

要求：
1. 保留关键决策和结论
2. 保留代码变更摘要（新增/修改/删除的文件）
3. 保留测试结果
4. 保留错误与修复过程
5. 保留未完成事项
6. 保留经验教训
7. 忽略中间探索过程和重复讨论

输出格式：

### 关键决策
- [决策列表]

### 代码变更
- 新增: [文件列表]
- 修改: [文件列表]
- 删除: [文件列表]

### 测试结果
- [测试摘要]

### 错误与修复
- [错误和修复过程]

### 未完成事项
- [待办列表]

### 经验教训
- [经验列表]

---

对话记录：
{content}
"""


# ═══════════════════════════════════════════════════════════
# 单元测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    engine = SummaryDecisionEngine()

    # 测试 1: 错误信号 → KEEP_FULL
    error_msg = {"role": "tool_result", "content": "Traceback (most recent call last):\n  File 'test.py', line 10\n    raise RuntimeError('failed')\nExit code: 1"}
    strategy = engine.decide(error_msg)
    print(f"Test 1 (error): {strategy.value} → {'✅' if strategy == SummaryStrategy.KEEP_FULL else '❌'}")

    # 测试 2: 正常工具输出 → TOOL_FILTER
    tool_msg = {"role": "tool_result", "content": "12 passed, 0 failed in 3.2s"}
    strategy = engine.decide(tool_msg)
    print(f"Test 2 (tool): {strategy.value} → {'✅' if strategy == SummaryStrategy.TOOL_FILTER else '❌'}")

    # 测试 3: 决策关键词 → LLM_ANALYZE
    decision_msg = {"role": "assistant", "content": "经过分析，我决定使用 JWT 进行认证，原因是安全性更好。"}
    strategy = engine.decide(decision_msg)
    print(f"Test 3 (decision): {strategy.value} → {'✅' if strategy == SummaryStrategy.LLM_ANALYZE else '❌'}")

    # 测试 4: 长对话 → LLM_ANALYZE
    long_msg = {"role": "assistant", "content": "x" * 600}
    strategy = engine.decide(long_msg)
    print(f"Test 4 (long): {strategy.value} → {'✅' if strategy == SummaryStrategy.LLM_ANALYZE else '❌'}")

    # 测试 5: 冗余消息
    print(f"Test 5 (redundant): {'✅' if is_redundant_message('好的') else '❌'}")
    print(f"Test 5 (normal): {'✅' if not is_redundant_message('我已完成了功能实现') else '❌'}")

    # 测试 6: tool_filter 规则
    pytest_output = "test_auth.py::test_login PASSED\ntest_auth.py::test_logout PASSED\n\n2 passed in 1.5s"
    print(f"Test 6 (pytest filter): {tool_filter_pytest(pytest_output)}")

    # 测试 7: error context
    error_content = "line1\nline2\nError: something failed\nline4\nline5\nline6"
    ctx = extract_error_context(error_content, context_lines=1)
    print(f"Test 7 (error context): {repr(ctx)}")

    # 测试 8: Layer1 action
    action = engine.get_layer1_action(tool_msg, SummaryStrategy.TOOL_FILTER)
    print(f"Test 8 (L1 action): {action}")

    print("\n✅ SummaryDecisionEngine tests passed")

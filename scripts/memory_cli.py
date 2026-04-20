#!/usr/bin/env python3
"""
ADDS Memory CLI — CLI 记忆管理子命令

设计目标：
- adds mem status — 记忆系统健康概览
- adds mem audit — 交互式审查固定记忆
- adds mem prune — 清理陈旧/失效记忆
- adds mem override — 人工更正固定记忆
- adds mem history — 查看记忆生命周期
- adds mem checkpoint — 记忆快照
- adds mem search — 搜索记忆

参考：P0-3 路线图 — CLI 记忆管理子命令
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def add_mem_subparser(subparsers) -> None:
    """添加 mem 子命令到 CLI parser"""

    mem_parser = subparsers.add_parser("mem", help="记忆管理（P0-3）")
    mem_sub = mem_parser.add_subparsers(dest="mem_command")

    # status
    mem_sub.add_parser("status", help="显示记忆系统健康概览")

    # audit
    audit_parser = mem_sub.add_parser("audit", help="交互式审查固定记忆")
    audit_parser.add_argument("--status", type=str, default="",
                               help="仅审查指定状态的条目 (active/suspected/invalidated)")
    audit_parser.add_argument("--module", type=str, default="",
                               help="仅审查指定模块的条目")

    # prune
    prune_parser = mem_sub.add_parser("prune", help="清理陈旧/失效记忆")
    prune_parser.add_argument("--module", type=str, default="",
                               help="清理指定模块的记忆")
    prune_parser.add_argument("--status", type=str, default="",
                               help="清理指定状态的记忆 (invalidated/demoted)")
    prune_parser.add_argument("--older-than", type=str, default="",
                               help="清理 N 天以上未引用的记忆 (如 30d)")

    # override
    override_parser = mem_sub.add_parser("override", help="人工更正固定记忆")
    override_parser.add_argument("id", type=str, help="记忆条目 ID")
    override_parser.add_argument("--content", type=str, default="",
                                  help="更正后的内容")

    # history
    history_parser = mem_sub.add_parser("history", help="查看记忆生命周期")
    history_parser.add_argument("id", type=str, help="记忆条目 ID")

    # checkpoint
    checkpoint_parser = mem_sub.add_parser("checkpoint", help="记忆快照")
    checkpoint_parser.add_argument("--tag", type=str, required=True,
                                    help="快照标签 (如 v1.0.0)")
    checkpoint_parser.add_argument("--promote", action="store_true",
                                    help="同时执行晋升仪式")

    # search
    search_parser = mem_sub.add_parser("search", help="搜索记忆")
    search_parser.add_argument("query", type=str, help="搜索查询")
    search_parser.add_argument("--top-k", type=int, default=5,
                                help="返回结果数")

    # add
    add_parser = mem_sub.add_parser("add", help="手动添加记忆到 index.mem")
    add_parser.add_argument("content", type=str, help="记忆内容")
    add_parser.add_argument("--category", type=str, default="experience",
                            choices=["environment", "experience", "skill", "preference"],
                            help="记忆类别")
    add_parser.add_argument("--role", type=str, default="common",
                            help="角色")
    add_parser.add_argument("--module", type=str, default="",
                            help="模块")
    add_parser.add_argument("--tag", type=str, action="append", dest="tags",
                            help="标签（可多次）")
    add_parser.add_argument("--summary", type=str, default="",
                            help="索引摘要（默认取内容前50字）")


def handle_mem_command(args, project_root: str = ".") -> None:
    """处理 mem 子命令"""
    from memory_manager import MemoryManager

    sessions_dir = str(Path(project_root) / ".ai" / "sessions")
    mgr = MemoryManager(sessions_dir=sessions_dir, project_root=project_root)

    if not args.mem_command or args.mem_command == "status":
        _cmd_status(mgr)
    elif args.mem_command == "audit":
        _cmd_audit(mgr, status=args.status, module=args.module)
    elif args.mem_command == "prune":
        _cmd_prune(mgr, module=args.module, status=args.status,
                   older_than=args.older_than)
    elif args.mem_command == "override":
        _cmd_override(mgr, args.id, content=args.content)
    elif args.mem_command == "history":
        _cmd_history(mgr, args.id)
    elif args.mem_command == "checkpoint":
        _cmd_checkpoint(mgr, args.tag, promote=args.promote)
    elif args.mem_command == "search":
        _cmd_search(mgr, args.query, top_k=args.top_k)
    elif args.mem_command == "add":
        _cmd_add(mgr, args.content, category=args.category,
                 role=args.role, module=args.module,
                 tags=args.tags, summary=args.summary)
    else:
        print("未知 mem 子命令。使用 adds mem --help 查看帮助。")


# ═══════════════════════════════════════════════════════════
# 子命令实现
# ═══════════════════════════════════════════════════════════

def _cmd_status(mgr) -> None:
    """adds mem status — 记忆系统健康概览"""
    status = mgr.get_status()

    print("=" * 60)
    print("🧠 记忆系统状态")
    print("=" * 60)
    print(f"  固定记忆: {status.total_fixed_memories} 条 "
          f"(✅active: {status.active_count}, "
          f"⚠️suspected: {status.suspected_count}, "
          f"❌invalidated: {status.invalidated_count}, "
          f"⬇️demoted: {status.demoted_count})")
    print(f"  容量: {status.capacity_used}/{status.capacity_total} 字符 "
          f"({status.capacity_used/status.capacity_total:.0%})")
    print(f"  待审冲突: {status.pending_conflicts} 条")
    print(f"  强制复读: {status.forced_reminders_count} 条")

    # 容量警告
    if status.capacity_used / status.capacity_total > 0.9:
        print("\n  ⚠️ 容量接近上限！建议执行 adds mem prune 清理")
    elif status.capacity_used / status.capacity_total > 0.7:
        print("\n  💡 容量已用 70%+，可考虑清理低优先级记忆")

    print()


def _cmd_audit(mgr, status: str = "", module: str = "") -> None:
    """adds mem audit — 交互式审查固定记忆"""
    _, items = mgr.read_index_mem()

    # 过滤
    if status:
        items = [i for i in items if i.status == status]
    if module:
        items = [i for i in items if i.module == module or module in i.tags]

    if not items:
        print("📭 无匹配的记忆条目")
        return

    print(f"📋 审查模式 — {len(items)} 条记忆\n")

    for idx, item in enumerate(items, 1):
        status_icon = {"active": "✅", "suspected": "⚠️",
                       "invalidated": "❌", "demoted": "⬇️"}.get(item.status, "?")
        print(f"  [{idx}/{len(items)}] {status_icon} {item.category} | {item.status}")
        print(f"      \"{item.content}\"")
        print(f"      ID: {item.id} | role: {item.role} | module: {item.module}")
        if item.invalidation_count:
            print(f"      证伪: {item.invalidation_count} 次")
        if item.rollback_count:
            print(f"      回滚: {item.rollback_count} 次")
        if item.promoted:
            print(f"      晋升: {item.promoted_at}")
        print()

        # 交互
        try:
            choice = input("  操作: (k)eep / (i)nvalidate / (d)emote / (s)kip / (q)uit: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if choice == "i":
            mgr.update_item(item.id, {"status": "invalidated"})
            print(f"  ❌ 已标记为 invalidated: {item.id}")
        elif choice == "d":
            mgr.update_item(item.id, {"status": "demoted"})
            print(f"  ⬇️ 已降级: {item.id}")
        elif choice == "q":
            break
        else:
            print(f"  ✅ 保留: {item.id}")

        print()

    print("审查完成。")


def _cmd_prune(mgr, module: str = "", status: str = "",
               older_than: str = "") -> None:
    """adds mem prune — 清理陈旧/失效记忆"""
    _, items = mgr.read_index_mem()

    # 过滤待清理条目
    to_prune = []
    for item in items:
        if status and item.status != status:
            continue
        if module and item.module != module and module not in item.tags:
            continue
        if item.status in ("invalidated", "demoted"):
            to_prune.append(item)

    if not to_prune:
        print("📭 无需清理的记忆条目")
        return

    print(f"🧹 待清理: {len(to_prune)} 条\n")
    for item in to_prune:
        status_icon = {"invalidated": "❌", "demoted": "⬇️"}.get(item.status, "?")
        print(f"  {status_icon} [{item.id}] {item.content[:50]}")

    try:
        confirm = input(f"\n确认清理 {len(to_prune)} 条? (y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消")
        return

    if confirm == "y":
        for item in to_prune:
            mgr.delete_item(item.id)
        print(f"✅ 已清理 {len(to_prune)} 条记忆")
    else:
        print("已取消")


def _cmd_override(mgr, item_id: str, content: str = "") -> None:
    """adds mem override — 人工更正固定记忆"""
    item = mgr.get_item_by_id(item_id)
    if not item:
        print(f"❌ 未找到记忆条目: {item_id}")
        return

    print(f"📌 当前记忆 [{item_id}]:")
    print(f"   内容: {item.content}")
    print(f"   类别: {item.category} | 角色: {item.role} | 状态: {item.status}")

    if not content:
        try:
            content = input("\n更正为: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            return

    if not content:
        print("已取消（内容为空）")
        return

    try:
        reason = input("原因: ").strip()
    except (EOFError, KeyboardInterrupt):
        reason = "人工更正"

    mgr.update_item(item_id, {"content": content})
    print(f"✅ 已更正: {item_id}")
    print(f"   新内容: {content}")
    print(f"   原因: {reason}")

    # 记录到冲突日志
    mgr.add_conflict_record(
        description=f"人工更正 {item_id}",
        source_a="human_override",
        source_b=item.content[:50],
        resolution=f"更正为: {content[:50]}",
    )


def _cmd_history(mgr, item_id: str) -> None:
    """adds mem history — 查看记忆生命周期"""
    item = mgr.get_item_by_id(item_id)
    if not item:
        print(f"❌ 未找到记忆条目: {item_id}")
        return

    print(f"📜 记忆生命周期 [{item_id}]")
    print("=" * 50)
    print(f"  内容: {item.content}")
    print(f"  类别: {item.category}")
    print(f"  角色: {item.role}")
    print(f"  模块: {item.module or '未指定'}")
    print(f"  标签: {', '.join(item.tags) if item.tags else '无'}")
    print(f"  状态: {item.status}")
    print(f"  证伪次数: {item.invalidation_count}")
    print(f"  回滚次数: {item.rollback_count}")
    print(f"  引用次数: {item.reference_count}")
    if item.promoted:
        print(f"  已晋升: {item.promoted_at}")

    # 计算当前优先级
    priority = mgr.sorter.calculate_priority(item)
    print(f"  当前优先级: {priority:.3f}")
    print()


def _cmd_checkpoint(mgr, tag: str, promote: bool = False) -> None:
    """adds mem checkpoint — 记忆快照"""
    path = mgr.checkpoint(tag)
    print(f"📸 快照已创建: index.mem → index-{tag}.mem")
    print(f"   文件: {path}")

    if promote:
        _cmd_promote(mgr, tag)


def _cmd_promote(mgr, tag: str) -> None:
    """晋升仪式"""
    _, items = mgr.read_index_mem()

    # 筛选晋升候选
    candidates = []
    for item in items:
        if item.status == "active" and not item.promoted:
            priority = mgr.sorter.calculate_priority(item)
            if priority > 0.7:
                candidates.append((item, priority))

    # 排序
    candidates.sort(key=lambda x: x[1], reverse=True)

    if not candidates:
        print("\n📭 无晋升候选")
        return

    print(f"\n📋 本阶段记忆进化报告:")
    print("─" * 50)

    promoted = []
    for idx, (item, priority) in enumerate(candidates, 1):
        status_str = "🔥 晋升候选" if priority > 0.8 else "📌 新行为守则"
        if item.invalidation_count >= 2:
            status_str = "⚠️ 回归风险"

        print(f"\n[{idx}] {status_str} (优先级 {priority:.2f})")
        print(f"    \"{item.content}\"")
        print(f"    角色: {item.role} | 类别: {item.category}")

    print(f"\n{'─' * 50}")
    try:
        confirm = input(f"\n确认晋升 {len(candidates)} 条记忆为\"长期直觉\"? (y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消")
        return

    if confirm == "y":
        for item, _ in candidates:
            mgr.update_item(item.id, {
                "promoted": True,
                "promoted_at": tag,
            })
            promoted.append(item.id)

        print(f"\n✅ 已晋升 {len(promoted)} 条记忆:")
        for pid in promoted:
            print(f"  - {pid}: promoted=true, promoted_at={tag}")
        print("\n✅ 晋升的记忆将在 System Prompt 中获得更高注入权重")
    else:
        print("已取消")


def _cmd_search(mgr, query: str, top_k: int = 5) -> None:
    """adds mem search — 搜索记忆"""
    results = asyncio.run(mgr.search_memory(query, top_k))

    if not results:
        print(f"📭 未找到与 \"{query}\" 相关的记忆")
        return

    print(f"🔍 搜索结果: \"{query}\" ({len(results)} 条)\n")
    for i, result in enumerate(results, 1):
        source_icon = {"固定记忆": "📌", "记忆索引": "📋", ".mem文件": "📄"}.get(
            result.source, "?"
        )
        print(f"  {i}. {source_icon} [{result.source}] {result.file}:{result.line_number}")
        print(f"     {result.content[:100]}")
        print(f"     相关度: {result.relevance:.2f}")
        print()


def _cmd_add(mgr, content: str, category: str = "experience",
             role: str = "common", module: str = "",
             tags: Optional[List[str]] = None,
             summary: str = "") -> None:
    """adds mem add — 手动添加记忆到 index.mem"""
    success = mgr.add_item(
        content=content,
        category=category,
        role=role,
        module=module,
        tags=tags,
        summary=summary or None,
    )

    if success:
        print(f"✅ 记忆已添加: {content[:50]}{'...' if len(content) > 50 else ''}")
        print(f"   类别: {category} | 角色: {role}")
        if module:
            print(f"   模块: {module}")
        if tags:
            print(f"   标签: {', '.join(tags)}")
        print(f"   索引已更新（adds mem status 查看）")
    else:
        print("❌ 添加失败")

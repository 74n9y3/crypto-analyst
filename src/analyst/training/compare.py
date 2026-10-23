"""你 vs AI 计划对比器。"""

from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from analyst.compute.plan import TradePlan
from analyst.i18n import L


@dataclass
class PlanDiff:
    same_direction: bool
    entry_overlap: bool
    stop_diff_pct: float
    target_diff_pct: float
    rr_diff: float
    user_more_conservative: bool
    notes: list[str]


def compare_plans(user: TradePlan, ai: TradePlan) -> PlanDiff:
    """比较你和 AI 的计划，生成差异分析。"""
    notes: list[str] = []

    same_dir = user.direction == ai.direction

    if same_dir:
        notes.append(L(f"✅ 方向一致：均为 {user.direction}", f"✅ Same direction: both {user.direction}"))
    else:
        notes.append(
            L(
                f"⚠️  方向不一致：你 {user.direction}，AI {ai.direction}",
                f"⚠️  Direction mismatch: you {user.direction}, AI {ai.direction}",
            )
        )

    # 任一为 wait，无意义比较细节
    if user.direction == "wait" or ai.direction == "wait":
        return PlanDiff(
            same_direction=same_dir,
            entry_overlap=False,
            stop_diff_pct=0.0,
            target_diff_pct=0.0,
            rr_diff=user.rr_ratio - ai.rr_ratio,
            user_more_conservative=False,
            notes=notes,
        )

    entry_overlap = (
        user.entry_low <= ai.entry_high and ai.entry_low <= user.entry_high
    )
    if entry_overlap:
        notes.append(L("✅ 入场区有重叠", "✅ Entry zones overlap"))
    else:
        notes.append(
            L(
                "⚠️  入场区不重叠 - 你和 AI 看的位置不一样",
                "⚠️  Entry zones do not overlap - you and the AI are watching different levels",
            )
        )

    stop_diff_pct = (
        abs(user.stop_loss - ai.stop_loss) / ai.stop_loss * 100
        if ai.stop_loss
        else 0.0
    )
    target_diff_pct = (
        abs(user.take_profit_1 - ai.take_profit_1) / ai.take_profit_1 * 100
        if ai.take_profit_1
        else 0.0
    )

    if stop_diff_pct < 0.5:
        notes.append(L(f"✅ 止损接近（差 {stop_diff_pct:.2f}%）", f"✅ Stops are close (diff {stop_diff_pct:.2f}%)"))
    elif stop_diff_pct < 2.0:
        notes.append(L(f"📍 止损略不同（差 {stop_diff_pct:.2f}%）", f"📍 Stops differ slightly (diff {stop_diff_pct:.2f}%)"))
    else:
        notes.append(L(f"⚠️  止损差距大（差 {stop_diff_pct:.2f}%）", f"⚠️  Stops differ a lot (diff {stop_diff_pct:.2f}%)"))

    rr_diff = user.rr_ratio - ai.rr_ratio
    if abs(rr_diff) < 0.3:
        notes.append(
            L(
                f"✅ R:R 接近（你 {user.rr_ratio:.2f} vs AI {ai.rr_ratio:.2f}）",
                f"✅ R:R is close (you {user.rr_ratio:.2f} vs AI {ai.rr_ratio:.2f})",
            )
        )
    elif rr_diff > 0:
        notes.append(L(f"📍 你的 R:R 更高（+{rr_diff:.2f}）", f"📍 Your R:R is higher (+{rr_diff:.2f})"))
    else:
        notes.append(L(f"📍 AI 的 R:R 更高（{rr_diff:.2f}）", f"📍 AI R:R is higher ({rr_diff:.2f})"))

    user_more_conservative = (
        user.direction == "long"
        and user.stop_loss > ai.stop_loss
        and user.take_profit_1 < ai.take_profit_1
    ) or (
        user.direction == "short"
        and user.stop_loss < ai.stop_loss
        and user.take_profit_1 > ai.take_profit_1
    )

    if user_more_conservative:
        notes.append(L("📍 你的方案整体更保守", "📍 Your plan is more conservative overall"))

    return PlanDiff(
        same_direction=same_dir,
        entry_overlap=entry_overlap,
        stop_diff_pct=stop_diff_pct,
        target_diff_pct=target_diff_pct,
        rr_diff=rr_diff,
        user_more_conservative=user_more_conservative,
        notes=notes,
    )


def plan_diff_to_dict(diff: PlanDiff) -> dict:
    """供 API / DTO 序列化。"""
    return {
        "same_direction": diff.same_direction,
        "entry_overlap": diff.entry_overlap,
        "stop_diff_pct": round(diff.stop_diff_pct, 3),
        "target_diff_pct": round(diff.target_diff_pct, 3),
        "rr_diff": round(diff.rr_diff, 3),
        "user_more_conservative": diff.user_more_conservative,
        "notes": diff.notes,
    }


def render_comparison(
    diff: PlanDiff,
    user: TradePlan,
    ai: TradePlan,
    console: Console | None = None,
) -> None:
    """用 Rich 展示对比表格 + 论述面板。"""
    if console is None:
        console = Console()

    table = Table(title=L("🥋 你 vs AI", "🥋 You vs AI"), show_lines=True)
    table.add_column(L("项目", "Item"), style="cyan", no_wrap=True)
    table.add_column(L("你", "You"), style="yellow")
    table.add_column("AI", style="green")

    table.add_row(L("方向", "Direction"), user.direction, ai.direction)
    table.add_row(
        L("入场区", "Entry zone"),
        f"{user.entry_low:.2f} - {user.entry_high:.2f}" if user.direction != "wait" else "-",
        f"{ai.entry_low:.2f} - {ai.entry_high:.2f}" if ai.direction != "wait" else "-",
    )
    table.add_row(
        L("止损", "Stop loss"),
        f"{user.stop_loss:.2f}" if user.direction != "wait" else "-",
        f"{ai.stop_loss:.2f}" if ai.direction != "wait" else "-",
    )
    table.add_row(
        L("止盈 1", "Take profit 1"),
        f"{user.take_profit_1:.2f}" if user.direction != "wait" else "-",
        f"{ai.take_profit_1:.2f}" if ai.direction != "wait" else "-",
    )
    table.add_row(
        L("止盈 2", "Take profit 2"),
        f"{user.take_profit_2:.2f}" if user.take_profit_2 else "-",
        f"{ai.take_profit_2:.2f}" if ai.take_profit_2 else "-",
    )
    table.add_row("R:R", f"{user.rr_ratio:.2f}", f"{ai.rr_ratio:.2f}")

    console.print(table)

    notes_text = "\n".join(diff.notes)
    console.print(Panel(notes_text, title=L("差异分析", "Differences"), border_style="blue"))

    console.print(L("\n[bold green]🤖 AI 论述：[/bold green]", "\n[bold green]🤖 AI rationale:[/bold green]"))
    console.print(Panel(ai.rationale, border_style="green"))

    console.print(L("\n[bold yellow]🧠 你的理由：[/bold yellow]", "\n[bold yellow]🧠 Your reasoning:[/bold yellow]"))
    console.print(Panel(user.rationale, border_style="yellow"))

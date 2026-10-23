"""Rich 报告渲染。"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from analyst.i18n import L
from analyst.stats.progress import ProgressReport
from analyst.stats.weakness import WeaknessPattern


def render_progress(report: ProgressReport, console: Console | None = None) -> None:
    """用 Rich 表格 + 面板渲染进度报告。"""
    if console is None:
        console = Console()

    if report.total_sessions == 0:
        console.print(
            Panel(
                L(
                    "暂无已验证会话。\n"
                    "请先用 [cyan]analyst practice <symbol>[/cyan] 创建会话，"
                    "并在到期后用 [cyan]analyst verify[/cyan] 验证。",
                    "No verified sessions yet.\n"
                    "Create one with [cyan]analyst practice <symbol>[/cyan], "
                    "then verify it with [cyan]analyst verify[/cyan] once it is due.",
                ),
                title=L("📈 分析进度", "📈 Progress"),
                border_style="dim",
            )
        )
        return

    table = Table(
        title=L(
            f"📈 最近 {report.period_days} 天分析摘要",
            f"📈 Summary of the last {report.period_days} days",
        ),
        show_header=False,
        show_lines=True,
    )
    table.add_column(L("指标", "Metric"), style="cyan", no_wrap=True)
    table.add_column(L("数值", "Value"), style="bold")

    table.add_row(L("总会话数", "Total sessions"), f"{report.total_sessions}")
    table.add_row(L("实际触发", "Triggered"), f"{report.completed}")
    table.add_row(L("胜率", "Win rate"), _fmt_pct(report.win_rate))
    table.add_row(L("平均 R 倍数", "Avg R multiple"), _fmt_r(report.avg_user_pnl_r))
    table.add_row(L("计划 R:R", "Planned R:R"), f"{report.avg_rr:.2f}")
    table.add_row(L("与 AI 一致率", "Agreement with AI"), _fmt_pct(report.vs_ai_agreement_rate))
    table.add_row(L("跑赢 AI 比例", "Beat AI rate"), _fmt_pct(report.vs_ai_outperform_rate))
    table.add_row(L("vs AI 收益差", "R diff vs AI"), _fmt_r(report.vs_ai_pnl_diff))
    table.add_row(L("最优捕获率", "Optimal capture rate"), _fmt_pct(report.vs_optimal_capture_rate))

    console.print(table)

    if report.weekly_win_rates:
        weekly = " → ".join(f"{w:.0%}" for w in report.weekly_win_rates)
        console.print(
            Panel(weekly, title=L("📊 周度胜率（旧 → 新）", "📊 Weekly win rate (old → new)"), border_style="blue")
        )


def render_weakness(
    patterns: list[WeaknessPattern],
    console: Console | None = None,
) -> None:
    if console is None:
        console = Console()

    if not patterns:
        console.print(
            Panel(
                L(
                    "尚无足够数据分析弱点。至少需要 5 次已验证会话才能给出有意义的归纳。",
                    "Not enough data to analyze weaknesses yet. At least 5 verified sessions are needed.",
                ),
                title=L("🎯 弱点分析", "🎯 Weaknesses"),
                border_style="dim",
            )
        )
        return

    table = Table(title=L("🎯 你最常犯的错", "🎯 Your most common mistakes"), show_lines=True)
    table.add_column("#", no_wrap=True, style="dim")
    table.add_column(L("弱点", "Weakness"), style="red")
    table.add_column(L("次数", "Count"), justify="right", style="yellow")
    table.add_column(L("占比", "Share"), justify="right")
    table.add_column(L("改进建议", "Suggestion"), style="green")

    for i, p in enumerate(patterns, 1):
        table.add_row(
            str(i),
            p.description,
            str(p.occurrences),
            f"{p.pct:.1f}%",
            p.suggestion,
        )

    console.print(table)


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _fmt_r(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f} R"

"""CLI 入口 - 所有命令都从这里注册。"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from analyst.i18n import L

app = typer.Typer(
    name="analyst",
    help="📊 Crypto Analyst - AI 行情分析、预测与结果验证",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════
def _normalize_symbol(symbol: str) -> str:
    """BTC -> BTC/USDT"""
    s = symbol.upper()
    if "/" not in s:
        s = f"{s}/USDT"
    return s


def _parse_period(period: str) -> int:
    """解析 30d / 4w 等格式为天数。"""
    p = period.strip().lower()
    if p.endswith("d"):
        return int(p[:-1])
    if p.endswith("w"):
        return int(p[:-1]) * 7
    if p.endswith("m"):
        return int(p[:-1]) * 30
    return int(p)


def _lan_ipv4() -> list[str]:
    """本机局域网 IPv4，供手机浏览器填写。"""
    import socket

    found: list[str] = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith("127."):
            found.append(ip)
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in found and not ip.startswith("127."):
                found.append(ip)
    except OSError:
        pass
    return found


def _render_market(ctx) -> None:
    """渲染市场快照面板。"""
    m = ctx.market
    structure = ctx.structure
    fib = ctx.fib

    price_panel = Panel(
        f"[bold yellow]{m.current_price:.4f}[/bold yellow]\n"
        f"24h: {m.low_24h:.2f} - {m.high_24h:.2f}\n"
        f"7d:  {m.low_7d:.2f} - {m.high_7d:.2f}\n"
        f"30d: {m.low_30d:.2f} - {m.high_30d:.2f}",
        title=f"💹 {m.symbol}",
        border_style="cyan",
    )

    res = ", ".join(f"{r:.2f}" for r in structure.resistances) or "-"
    sup = ", ".join(f"{s:.2f}" for s in structure.supports) or "-"
    structure_panel = Panel(
        L(
            f"趋势：[bold]{structure.trend}[/bold]\n"
            f"近高：{structure.recent_high:.2f}\n"
            f"近低：{structure.recent_low:.2f}\n"
            f"分界：{structure.key_pivot:.2f}\n"
            f"阻力：{res}\n"
            f"支撑：{sup}",
            f"Trend: [bold]{structure.trend}[/bold]\n"
            f"Recent high: {structure.recent_high:.2f}\n"
            f"Recent low: {structure.recent_low:.2f}\n"
            f"Pivot: {structure.key_pivot:.2f}\n"
            f"Resistance: {res}\n"
            f"Support: {sup}",
        ),
        title=L("📐 结构", "📐 Structure"),
        border_style="magenta",
    )

    fib_panel = Panel(
        f"H: {fib.high:.2f}  L: {fib.low:.2f}  Δ: {fib.range:.2f}\n"
        f"0.382: {fib.retr_382:.2f}\n"
        f"0.500: {fib.retr_500:.2f}\n"
        f"0.618: {fib.retr_618:.2f}\n"
        f"0.786: {fib.retr_786:.2f}\n"
        f"1.272: {fib.ext_1272:.2f}",
        title=L("🔢 斐波回撤", "🔢 Fibonacci"),
        border_style="blue",
    )

    console.print(price_panel)
    console.print(structure_panel)
    console.print(fib_panel)


def _plan_to_table_text(plan) -> str:
    if plan.direction == "wait":
        return f"[yellow]{L('观望', 'Wait')}[/yellow]\n{plan.rationale}"
    return (
        L(f"方向：[bold]{plan.direction}[/bold]\n", f"Direction: [bold]{plan.direction}[/bold]\n")
        + L(
            f"入场区：{plan.entry_low:.2f} - {plan.entry_high:.2f}\n",
            f"Entry: {plan.entry_low:.2f} - {plan.entry_high:.2f}\n",
        )
        + L(f"止损：{plan.stop_loss:.2f}\n", f"Stop loss: {plan.stop_loss:.2f}\n")
        + L(f"止盈 1：{plan.take_profit_1:.2f}\n", f"TP 1: {plan.take_profit_1:.2f}\n")
        + (
            L(f"止盈 2：{plan.take_profit_2:.2f}\n", f"TP 2: {plan.take_profit_2:.2f}\n")
            if plan.take_profit_2
            else ""
        )
        + L(f"R:R：{plan.rr_ratio:.2f}", f"R:R: {plan.rr_ratio:.2f}")
        + f"\n\n{plan.rationale}"
    )


# ═══════════════════════════════════════════════════════════════
# 分析会话命令
# ═══════════════════════════════════════════════════════════════
@app.command()
def practice(
    symbol: str = typer.Argument(..., help="品种，如 BTC / ETH / SOL"),
    timeframe: str = typer.Option("4h", "--tf", help="主时间周期"),
):
    """🎯 开启一次 AI 分析会话（拉盘 → AI 计划 → 落库，稍后 CLI verify 回溯）。"""
    from analyst.config import get_settings
    from analyst.llm.analyst import analyze_market
    from analyst.storage import repo
    from analyst.storage.models import AIPlan
    from analyst.training import session as ts

    sym = _normalize_symbol(symbol)

    # 1. 创建会话
    try:
        with console.status(
            L(f"[bold cyan]拉取 {sym} 多周期数据...", f"[bold cyan]Fetching {sym} multi-timeframe data...")
        ):
            ctx = ts.create_session(sym, timeframe)
    except Exception as e:
        console.print(L(f"[bold red]❌ 数据拉取失败：{e}[/bold red]", f"[bold red]❌ Data fetch failed: {e}[/bold red]"))
        raise typer.Exit(1) from e

    # 2. 渲染市场快照
    _render_market(ctx)

    # 3. 调用 AI
    try:
        with console.status(L("[bold green]🤖 AI 分析中...", "[bold green]🤖 AI analyzing...")):
            market_dict = ctx.market.to_dict()
            market_dict["primary_timeframe"] = ctx.db_session.timeframe
            ai_response = analyze_market(
                market_snapshot=market_dict,
                indicators_snapshot=ctx.indicators,
            )
    except Exception as e:
        console.print(L(f"[bold red]❌ AI 调用失败：{e}[/bold red]", f"[bold red]❌ AI call failed: {e}[/bold red]"))
        raise typer.Exit(1) from e

    repo.save_ai_plan(
        AIPlan(
            session_id=ctx.db_session.id,
            direction=ai_response.plan.direction,
            entry_low=ai_response.plan.entry_low,
            entry_high=ai_response.plan.entry_high,
            stop_loss=ai_response.plan.stop_loss,
            take_profit_1=ai_response.plan.take_profit_1,
            take_profit_2=ai_response.plan.take_profit_2,
            confidence=3,
            rationale=ai_response.plan.rationale,
            rr_ratio=ai_response.plan.rr_ratio,
            raw_response=ai_response.raw_text,
            prompt_version=ai_response.prompt_version,
            model_id=ai_response.model,
            cost_usd=ai_response.cost_usd,
        )
    )
    repo.update_session_status(ctx.db_session.id, "ai_planned")

    console.print(
        Panel(
            _plan_to_table_text(ai_response.plan),
            title=L("🤖 AI 计划", "🤖 AI plan"),
            border_style="green",
        )
    )

    # 4. 提示验证时机
    settings = get_settings()
    verify_at = datetime.now(timezone.utc) + timedelta(
        hours=settings.verification_delay_hours
    )

    console.print(
        L(
            f"\n[bold green]✅ 会话 #{ctx.db_session.id} 已记录[/bold green]",
            f"\n[bold green]✅ Session #{ctx.db_session.id} recorded[/bold green]",
        )
    )
    console.print(
        L(
            f"[dim]💰 本次 AI 成本：${ai_response.cost_usd:.4f} ({ai_response.latency_ms}ms)[/dim]",
            f"[dim]💰 AI cost: ${ai_response.cost_usd:.4f} ({ai_response.latency_ms}ms)[/dim]",
        )
    )
    console.print(
        L(
            f"[dim]⏰ 请在 {verify_at:%Y-%m-%d %H:%M UTC} 后运行 [cyan]analyst verify[/cyan][/dim]",
            f"[dim]⏰ Run [cyan]analyst verify[/cyan] after {verify_at:%Y-%m-%d %H:%M UTC}[/dim]",
        )
    )


# ═══════════════════════════════════════════════════════════════
# 验证命令
# ═══════════════════════════════════════════════════════════════
@app.command()
def verify(
    session: Optional[int] = typer.Option(None, "--session", help="只验证指定会话"),
):
    """✅ 验证已到期会话"""
    from analyst.storage import repo

    if session is not None:
        s = repo.get_session(session)
        if not s:
            console.print(L(f"[red]会话 #{session} 不存在[/red]", f"[red]Session #{session} not found[/red]"))
            raise typer.Exit(1)
        if s.status != "ai_planned":
            console.print(
                L(
                    f"[yellow]会话 #{session} 状态是 {s.status}，已不需要验证[/yellow]",
                    f"[yellow]Session #{session} is {s.status}; no verification needed[/yellow]",
                )
            )
            return
        sessions_to_verify = [s]
    else:
        sessions_to_verify = repo.list_pending_verification()

    if not sessions_to_verify:
        console.print(L("[dim]✨ 没有待验证的会话[/dim]", "[dim]✨ No sessions pending verification[/dim]"))
        return

    console.print(
        L(
            f"[cyan]共 {len(sessions_to_verify)} 个会话待验证[/cyan]\n",
            f"[cyan]{len(sessions_to_verify)} session(s) pending verification[/cyan]\n",
        )
    )
    for s in sessions_to_verify:
        try:
            _verify_one(s)
        except Exception as e:
            console.print(L(f"[red]会话 #{s.id} 验证失败：{e}[/red]", f"[red]Session #{s.id} verification failed: {e}[/red]"))


def _verify_one(s) -> None:
    """验证单个会话。"""
    from analyst.compute.plan import TradePlan
    from analyst.storage import repo
    from analyst.storage.models import Verification
    from analyst.training.verify import (
        TradeOutcome,
        fetch_future_candles,
        find_optimal_trade,
        verify_plan,
    )

    user_plan_db = repo.get_user_plan(s.id)
    ai_plan_db = repo.get_ai_plan(s.id)

    if not ai_plan_db:
        console.print(L(f"[yellow]会话 #{s.id} 没有 AI 计划，跳过[/yellow]", f"[yellow]Session #{s.id} has no AI plan, skipped[/yellow]"))
        return

    console.print(
        L(f"[cyan]验证会话 #{s.id}[/cyan] ", f"[cyan]Verifying session #{s.id}[/cyan] ")
        + f"{s.symbol} {s.timeframe} [dim]@ {s.created_at}[/dim]"
    )

    candles = fetch_future_candles(s.symbol, s.created_at, timeframe="1h")
    if not candles:
        console.print(L("[yellow]  验证 K线不足，跳过[/yellow]", "[yellow]  Not enough candles to verify, skipped[/yellow]"))
        return

    # 用户结果
    if user_plan_db:
        user_plan = TradePlan(
            direction=user_plan_db.direction,
            entry_low=user_plan_db.entry_low,
            entry_high=user_plan_db.entry_high,
            stop_loss=user_plan_db.stop_loss,
            take_profit_1=user_plan_db.take_profit_1,
            take_profit_2=user_plan_db.take_profit_2,
            rr_ratio=user_plan_db.rr_ratio,
            rationale=user_plan_db.rationale,
        )
        user_result = verify_plan(user_plan, candles)
        user_outcome = user_result.outcome.value
        user_pnl = user_result.pnl_r
    else:
        user_outcome = TradeOutcome.NO_TRIGGER.value
        user_pnl = 0.0

    # AI 结果
    ai_plan = TradePlan(
        direction=ai_plan_db.direction,
        entry_low=ai_plan_db.entry_low,
        entry_high=ai_plan_db.entry_high,
        stop_loss=ai_plan_db.stop_loss,
        take_profit_1=ai_plan_db.take_profit_1,
        take_profit_2=ai_plan_db.take_profit_2,
        rr_ratio=ai_plan_db.rr_ratio,
        rationale=ai_plan_db.rationale,
    )
    ai_result = verify_plan(ai_plan, candles)

    # 最优参考线
    optimal_dir = (
        ai_plan.direction
        if ai_plan.direction != "wait"
        else (user_plan_db.direction if user_plan_db else "wait")
    )
    optimal = find_optimal_trade(optimal_dir, candles)

    v = Verification(
        session_id=s.id,
        actual_high=max(c.high for c in candles),
        actual_low=min(c.low for c in candles),
        actual_close=candles[-1].close,
        user_outcome=user_outcome,
        user_pnl_r=user_pnl,
        ai_outcome=ai_result.outcome.value,
        ai_pnl_r=ai_result.pnl_r,
        optimal_pnl_r=optimal.pnl_r,
        notes="",
    )
    repo.save_verification(v)
    repo.update_session_status(s.id, "verified")

    table = Table(show_header=True, header_style="bold")
    table.add_column(L("方", "Side"), style="cyan")
    table.add_column(L("结果", "Outcome"))
    table.add_column(L("R 倍数", "R multiple"), justify="right")

    table.add_row("AI", ai_result.outcome.value, _fmt_r(ai_result.pnl_r))
    table.add_row(L("最优参考", "Optimal ref"), "-", _fmt_r(optimal.pnl_r))

    console.print(table)
    console.print()


# ═══════════════════════════════════════════════════════════════
# 统计命令
# ═══════════════════════════════════════════════════════════════
@app.command()
def progress(
    period: str = typer.Option("30d", help="周期，如 7d, 30d, 90d"),
):
    """📈 查看你的成长曲线"""
    from analyst.stats.progress import calculate
    from analyst.stats.report import render_progress

    days = _parse_period(period)
    report = calculate(days)
    render_progress(report, console)


@app.command()
def weakness(top: int = typer.Option(5, "--top", help="只看前 N 个弱点")):
    """🎯 找出你最常犯的错"""
    from analyst.stats.report import render_weakness
    from analyst.stats.weakness import detect_weaknesses

    patterns = detect_weaknesses(top_n=top)
    render_weakness(patterns, console)


@app.command("ai-benchmark")
def ai_benchmark_cmd(
    period: str = typer.Option("30d", help="统计周期，如 7d, 30d"),
):
    """📊 已验证会话里 AI 侧表现摘要（不依赖用户是否提交计划）"""
    from rich.table import Table

    from analyst.stats.ai_benchmark import calculate_ai_benchmark

    days = _parse_period(period)
    r = calculate_ai_benchmark(period_days=days)
    if r.verified_count == 0:
        console.print(L(f"[dim]近 {days} 天暂无已验证会话[/dim]", f"[dim]No verified sessions in the last {days} days[/dim]"))
        return
    table = Table(title=L(f"📊 AI 基准（近 {days} 天 · 已验证）", f"📊 AI benchmark (last {days} days · verified)"))
    table.add_column(L("项", "Metric"), style="cyan")
    table.add_column(L("值", "Value"), justify="right")
    table.add_row(L("已验证会话", "Verified sessions"), str(r.verified_count))
    table.add_row(L("实际触发次数", "Triggered"), str(r.ai_triggered))
    table.add_row(L("触发后胜率", "Win rate when triggered"), f"{r.ai_win_rate:.0%}")
    table.add_row(L("平均 AI R", "Avg AI R"), f"{r.avg_ai_pnl_r:+.2f}")
    table.add_row(L("含用户计划的会话", "Sessions with user plan"), str(r.sessions_with_user_plan))
    console.print(table)


@app.command()
def history(
    limit: int = typer.Option(20, help="显示条数"),
    symbol: Optional[str] = typer.Option(None, help="按品种过滤"),
):
    """📚 历史会话列表"""
    from analyst.storage import repo

    sym = _normalize_symbol(symbol) if symbol else None
    sessions = repo.list_sessions(limit=limit, symbol=sym)

    if not sessions:
        console.print(L("[dim]暂无会话[/dim]", "[dim]No sessions yet[/dim]"))
        return

    table = Table(title=L("📚 历史会话", "📚 Session history"))
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column(L("时间", "Time"))
    table.add_column(L("品种", "Symbol"))
    table.add_column(L("周期", "Timeframe"))
    table.add_column(L("状态", "Status"), style="bold")

    for s in sessions:
        status_style = {
            "verified": "green",
            "ai_planned": "yellow",
            "user_planned": "blue",
            "ai_running": "cyan",
            "ai_failed": "red",
            "created": "dim",
            "expired": "red",
        }.get(s.status, "white")

        table.add_row(
            str(s.id),
            s.created_at.strftime("%m-%d %H:%M"),
            s.symbol,
            s.timeframe,
            f"[{status_style}]{s.status}[/{status_style}]",
        )

    console.print(table)


@app.command()
def review(session_id: int = typer.Argument(..., help="会话 ID")):
    """🔍 复盘单个会话（AI 计划 + 验证）"""
    from analyst.storage import repo

    s = repo.get_session(session_id)
    if not s:
        console.print(L(f"[red]会话 #{session_id} 不存在[/red]", f"[red]Session #{session_id} not found[/red]"))
        raise typer.Exit(1)

    ai_plan_db = repo.get_ai_plan(session_id)
    verification = repo.get_verification(session_id)

    console.print(
        Panel.fit(
            f"[bold]{s.symbol} {s.timeframe}[/bold]\n"
            + L(
                f"创建：{s.created_at}\n状态：[bold]{s.status}[/bold]",
                f"Created: {s.created_at}\nStatus: [bold]{s.status}[/bold]",
            ),
            title=L(f"🔍 会话 #{s.id}", f"🔍 Session #{s.id}"),
            border_style="cyan",
        )
    )

    if ai_plan_db:
        a = _row_to_plan(ai_plan_db)
        console.print(
            Panel(_plan_to_table_text(a), title=L("🤖 AI 计划", "🤖 AI plan"), border_style="green")
        )

    if verification:
        table = Table(title=L("✅ 验证结果", "✅ Verification"), show_header=True)
        table.add_column(L("项", "Side"), style="cyan")
        table.add_column(L("结果", "Outcome"))
        table.add_column(L("R 倍数", "R multiple"), justify="right")
        table.add_row("AI", verification.ai_outcome, _fmt_r(verification.ai_pnl_r))
        table.add_row(L("最优参考", "Optimal ref"), "-", _fmt_r(verification.optimal_pnl_r))
        console.print(table)


def _row_to_plan(row):
    from analyst.compute.plan import TradePlan

    return TradePlan(
        direction=row.direction,
        entry_low=row.entry_low,
        entry_high=row.entry_high,
        stop_loss=row.stop_loss,
        take_profit_1=row.take_profit_1,
        take_profit_2=row.take_profit_2,
        rr_ratio=row.rr_ratio,
        rationale=row.rationale,
    )


def _fmt_r(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f} R"


# ═══════════════════════════════════════════════════════════════
# data 子命令
# ═══════════════════════════════════════════════════════════════
data_app = typer.Typer(help="数据相关命令")
app.add_typer(data_app, name="data")


@data_app.command("status")
def data_status():
    """查看数据缓存状态"""
    from analyst.data.fetcher import get_cache

    cache = get_cache()
    console.print(L(f"缓存目录：[cyan]{cache.directory}[/cyan]", f"Cache dir: [cyan]{cache.directory}[/cyan]"))
    console.print(L(f"条目数：{len(cache)}", f"Entries: {len(cache)}"))
    console.print(L(f"占用：{cache.volume() / 1024:.1f} KB", f"Size: {cache.volume() / 1024:.1f} KB"))


@data_app.command("refresh")
def data_refresh(symbol: str = typer.Argument(...)):
    """强制刷新指定品种的所有周期"""
    from analyst.data import fetcher

    sym = _normalize_symbol(symbol)
    with console.status(L(f"刷新 {sym}...", f"Refreshing {sym}...")):
        for tf in ["1d", "4h", "1h", "30m"]:
            fetcher.fetch_candles(sym, timeframe=tf, use_cache=False)
    console.print(L(f"[green]✅ {sym} 已刷新[/green]", f"[green]✅ {sym} refreshed[/green]"))


# ═══════════════════════════════════════════════════════════════
# db 子命令
# ═══════════════════════════════════════════════════════════════
db_app = typer.Typer(help="数据库管理命令")
app.add_typer(db_app, name="db")


@db_app.command("init")
def db_init():
    """初始化数据库"""
    from analyst.storage.db import init_db

    init_db()
    console.print(L("[green]✅ 数据库已初始化[/green]", "[green]✅ Database initialized[/green]"))


@db_app.command("backup")
def db_backup(
    output: str = typer.Option("backup.db", help="备份文件名"),
):
    """备份数据库"""
    from analyst.config import get_settings

    settings = get_settings()
    db_path = settings.database_url.replace("sqlite:///", "")
    if db_path.startswith("./"):
        db_path = db_path[2:]
    try:
        shutil.copy(db_path, output)
        console.print(L(f"[green]✅ 已备份到 {output}[/green]", f"[green]✅ Backed up to {output}[/green]"))
    except FileNotFoundError:
        console.print(L(f"[red]数据库文件不存在：{db_path}[/red]", f"[red]Database file not found: {db_path}[/red]"))
        raise typer.Exit(1) from None


# ═══════════════════════════════════════════════════════════════
# config 子命令
# ═══════════════════════════════════════════════════════════════
config_app = typer.Typer(help="配置管理")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show():
    """显示当前配置"""
    from analyst.config import get_settings

    settings = get_settings()
    table = Table(title=L("⚙️  当前配置", "⚙️  Current config"))
    table.add_column(L("键", "Key"), style="cyan")
    table.add_column(L("值", "Value"))

    for k, v in settings.model_dump().items():
        if "key" in k.lower() and v:
            v = f"{str(v)[:8]}***"
        table.add_row(k, str(v))

    console.print(table)


@app.command("lang")
def lang_cmd(
    lang: Optional[str] = typer.Argument(None, help="zh / en；不填则显示当前语言"),
):
    """🌐 查看或设置输出语言（与 Web 页面共用）。"""
    from analyst import i18n

    if lang is None:
        console.print(L(f"当前语言：{i18n.get_lang()}", f"Current language: {i18n.get_lang()}"))
        return
    if lang.strip().lower() not in i18n.SUPPORTED:
        console.print(L(f"[red]不支持的语言 {lang}，可选：zh / en[/red]", f"[red]Unsupported language {lang}; use zh / en[/red]"))
        raise typer.Exit(1)
    v = i18n.set_lang(lang)
    console.print(L(f"[green]✅ 语言已设为 {v}[/green]", f"[green]✅ Language set to {v}[/green]"))


@config_app.command("test-llm")
def config_test_llm():
    """🔌 测试 LLM API 连通性（不消耗大额 token）"""
    from analyst.config import get_settings
    from analyst.llm.analyst import analyze_market

    settings = get_settings()
    bk = (settings.bai_api_key or "").strip()
    bm = (settings.bai_model or "").strip()
    console.print(
        f"[cyan]Provider:[/cyan] {settings.llm_provider}  "
        f"[cyan]Model:[/cyan] {settings.llm_model}"
    )
    if bk and bm and getattr(settings, "llm_try_bai_after_groq", True):
        console.print(
            L(
                f"[cyan]链路 1 b.ai:[/cyan] {settings.bai_model}（最先尝试，失败再走免费层 / 主 Provider）",
                f"[cyan]Route 1 b.ai:[/cyan] {settings.bai_model} (tried first; falls back to free tier / main provider)",
            )
        )
    from analyst.llm.analyst import list_free_endpoints

    free_eps = list_free_endpoints(settings)
    if free_eps:
        console.print(
            L("[cyan]免费层:[/cyan] ", "[cyan]Free tier:[/cyan] ")
            + " → ".join(L(f"{e['name']}「{e['model']}」", f"{e['name']} ({e['model']})") for e in free_eps)
        )

    fake_market = {
        "symbol": "BTC/USDT",
        "captured_at": 0,
        "current_price": 100000.0,
        "high_24h": 102000.0,
        "low_24h": 98000.0,
        "high_7d": 105000.0,
        "low_7d": 95000.0,
        "high_30d": 110000.0,
        "low_30d": 90000.0,
    }
    fake_indicators = {
        "1d": {"macd": {"dif": 100.0, "dea": 80.0, "histogram": 40.0,
                        "above_zero": True, "cross_signal": None},
               "ema": {"ema7": 100500, "ema30": 99000, "ema52": 97000},
               "boll": {"upper": 105000, "middle": 100000, "lower": 95000}},
        "4h": {"macd": {"dif": 50, "dea": 60, "histogram": -20,
                        "above_zero": True, "cross_signal": "death"},
               "ema": {"ema7": 100200, "ema30": 99800, "ema52": 99200},
               "boll": {"upper": 102000, "middle": 100000, "lower": 98000}},
        "1h": {"macd": {"dif": 10, "dea": 20, "histogram": -20,
                        "above_zero": True, "cross_signal": None},
               "ema": {"ema7": 100100, "ema30": 100000, "ema52": 99900}},
    }

    try:
        with console.status(L("[bold green]测试调用...", "[bold green]Testing call...")):
            response = analyze_market(fake_market, fake_indicators)
    except Exception as e:
        console.print(L(f"[bold red]❌ 失败：{e}[/bold red]", f"[bold red]❌ Failed: {e}[/bold red]"))
        raise typer.Exit(1) from e

    console.print(L("[bold green]✅ 连通成功[/bold green]", "[bold green]✅ Connected[/bold green]"))
    console.print(L(f"  方向：{response.plan.direction}", f"  Direction: {response.plan.direction}"))
    console.print(L(f"  延迟：{response.latency_ms} ms", f"  Latency: {response.latency_ms} ms"))
    console.print(L(f"  成本：${response.cost_usd:.6f}", f"  Cost: ${response.cost_usd:.6f}"))
    console.print(L(f"  R:R：{response.plan.rr_ratio:.2f}", f"  R:R: {response.plan.rr_ratio:.2f}"))


# ═══════════════════════════════════════════════════════════════
# 回测
# ═══════════════════════════════════════════════════════════════
@app.command()
def backtest(
    symbol: str = typer.Argument("BTC", help="币种，如 BTC / ETH / SOL"),
    timeframe: str = typer.Option("15m", "--timeframe", "-t", help="K 线周期"),
    bars: int = typer.Option(1000, "--bars", help="回放历史根数（≤1500）"),
    market: str = typer.Option("futures", "--market", help="spot 或 futures"),
    rules: bool = typer.Option(True, "--rules/--no-rules", help="是否统计规则告警命中率"),
    horizon: int = typer.Option(12, "--horizon", help="规则前瞻窗口（根）"),
    json_out: Optional[str] = typer.Option(None, "--json", help="结果另存 JSON 文件"),
):
    """🧪 历史回放：各规则告警前瞻命中率。"""
    import json as _json

    from analyst.backtest import run_backtest

    sym = _normalize_symbol(symbol)

    with console.status(
        L(f"[bold cyan]回放 {sym} {timeframe} × {bars} 根...", f"[bold cyan]Replaying {sym} {timeframe} × {bars} bars...")
    ):
        report = run_backtest(
            sym,
            timeframe,
            bars=bars,
            market=market,
            include_rules=rules,
            rule_horizon=horizon,
        )

    span = ""
    if report.start and report.end:
        span = f"{report.start:%m-%d %H:%M} → {report.end:%m-%d %H:%M} UTC"
    console.print(
        Panel(
            L(
                f"品种：[bold]{report.symbol}[/bold] · 周期：{report.timeframe} · 共 {report.bars} 根\n{span}",
                f"Symbol: [bold]{report.symbol}[/bold] · Timeframe: {report.timeframe} · {report.bars} bars\n{span}",
            ),
            title=L("🧪 回测范围", "🧪 Backtest range"),
            border_style="cyan",
        )
    )

    if rules and report.rule_stats:
        rt = Table(
            title=L(
                f"📡 规则告警前瞻命中率（{horizon} 根内先走 ±1×ATR）",
                f"📡 Rule alert forward hit rate (first ±1×ATR move within {horizon} bars)",
            )
        )
        rt.add_column(L("规则", "Rule"), style="cyan")
        rt.add_column(L("样本", "Samples"), justify="right")
        rt.add_column(L("命中", "Hits"), justify="right")
        rt.add_column(L("打脸", "Misses"), justify="right")
        rt.add_column(L("未决", "Flat"), justify="right")
        rt.add_column(L("命中率", "Hit rate"), justify="right")
        rt.add_column(L("平均前瞻收益", "Avg fwd return"), justify="right")
        for name, st in sorted(
            report.rule_stats.items(), key=lambda kv: -kv[1].win_rate
        ):
            wr = st.win_rate
            wr_style = "green" if wr >= 0.55 else ("red" if wr < 0.45 else "yellow")
            rt.add_row(
                name,
                str(st.n),
                str(st.wins),
                str(st.losses),
                str(st.flat),
                f"[{wr_style}]{wr:.0%}[/{wr_style}]",
                f"{st.avg_fwd_ret_pct:+.3f}%",
            )
        console.print(rt)
        console.print(
            L(
                "[dim]命中率≈50% 说明该规则单独使用无优势，只适合当上下文参考；"
                "样本 < 10 时结论不可靠。[/dim]",
                "[dim]A ~50% hit rate means the rule has no edge on its own and is only useful as context; "
                "results with < 10 samples are unreliable.[/dim]",
            )
        )
    elif rules:
        console.print(
            L(
                "[yellow]该区间内未触发任何带方向的规则告警[/yellow]",
                "[yellow]No directional rule alerts fired in this range[/yellow]",
            )
        )

    if json_out:
        from pathlib import Path as _P

        _P(json_out).write_text(
            _json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        console.print(L(f"[green]✅ 已保存 {json_out}[/green]", f"[green]✅ Saved {json_out}[/green]"))


@app.command("strategies")
def strategies_list():
    """📚 列出策略库（经典组合策略 + 实时周期策略）。"""
    from analyst.compute.strategies.registry import list_strategies

    t = Table(title=L("策略库", "Strategy library"))
    t.add_column("ID", style="cyan")
    t.add_column(L("名称", "Name"))
    t.add_column(L("类型", "Type"))
    t.add_column(L("说明", "Description"))
    t.add_column(L("CLI 示例", "CLI example"), style="dim")
    for s in list_strategies():
        kind = L("实时", "Realtime") if s.kind == "realtime" else L("组合回测", "Portfolio backtest")
        t.add_row(s.id, s.name, kind, s.description, s.cli or "-")
    console.print(t)
    console.print(
        L(
            "[dim]组合策略走 backtest-classic / backtest-xs / backtest-carry；"
            "规则命中率走 backtest；实时盯盘走 Web。[/dim]",
            "[dim]Portfolio strategies: backtest-classic / backtest-xs / backtest-carry; "
            "rule hit rates: backtest; live monitoring: Web.[/dim]",
        )
    )


def _print_robustness(bundle: dict) -> None:
    wf = bundle["walk_forward"]
    color = {"PASS": "green", "WARN": "yellow", "FAIL": "red"}.get(wf["verdict"], "yellow")
    console.print(
        L(
            f"[bold]滚动样本外[/bold]（每窗 {wf['oos_days']} 天，步长 {wf['step_days']} 天）："
            f"通过 {wf['n_pass']}/{wf['n_windows']}，最长连续 {wf['max_consecutive']}"
            f"（门槛 {wf['consecutive_required']}）",
            f"[bold]Walk-forward OOS[/bold] ({wf['oos_days']}d windows, {wf['step_days']}d step): "
            f"passed {wf['n_pass']}/{wf['n_windows']}, longest streak {wf['max_consecutive']}"
            f" (need {wf['consecutive_required']})",
        )
        + f" [{color}]{wf['verdict']}[/{color}]"
    )
    bits = []
    for row in bundle["cost_sensitivity"]:
        bits.append(f"{row['scale']:g}× {row['total_return_pct']:+.1f}%")
    if bundle["cost_2x_still_positive"]:
        doubled = L("仍为正", "still positive")
    else:
        doubled = L("转负或持平", "flat or negative")
    console.print(
        L(
            f"[bold]成本敏感度[/bold]：{' · '.join(bits)}（2× {doubled}）",
            f"[bold]Cost sensitivity[/bold]: {' · '.join(bits)} (2× {doubled})",
        )
    )
    dsr = bundle["deflated_sharpe"]
    if dsr.get("dsr_prob") is None:
        console.print(L(f"[bold]Deflated Sharpe[/bold]：{dsr['verdict']}", f"[bold]Deflated Sharpe[/bold]: {dsr['verdict']}"))
    else:
        dsr_color = "green" if dsr["verdict"] == "PASS" else "red"
        console.print(
            L(
                f"[bold]Deflated Sharpe[/bold]：概率 {dsr['dsr_prob']:.2f}（候选 {dsr['n_trials']}）",
                f"[bold]Deflated Sharpe[/bold]: prob {dsr['dsr_prob']:.2f} ({dsr['n_trials']} trials)",
            )
            + f" [{dsr_color}]{dsr['verdict']}[/{dsr_color}]"
        )
    pbo = bundle["pbo"]
    if pbo.get("pbo") is None:
        console.print(f"[bold]PBO[/bold]{L('：', ': ')}{pbo.get('reason') or pbo.get('verdict')}")
    else:
        pbo_color = {"PASS": "green", "WARN": "yellow"}.get(pbo["verdict"], "red")
        console.print(
            L(
                f"[bold]PBO[/bold]：{pbo['pbo']:.2f}（{pbo['n_strategies']} 个参数邻域，{pbo['n_splits']} 折）",
                f"[bold]PBO[/bold]: {pbo['pbo']:.2f} ({pbo['n_strategies']} param neighbors, {pbo['n_splits']} folds)",
            )
            + f" [{pbo_color}]{pbo['verdict']}[/{pbo_color}]"
        )


@app.command("backtest-classic")
def backtest_classic(
    symbol: str = typer.Argument("BTC", help="币种，如 BTC / ETH / SOL"),
    timeframe: str = typer.Option("4h", "--timeframe", "-t", help="K 线周期"),
    days: int = typer.Option(1095, "--days", help="回测历史天数（自动分页拉取）"),
    strategy: str = typer.Option(
        "cycle_switch", "--strategy", "-s",
        help="cycle_switch / buy_hold",
    ),
    long_only: bool = typer.Option(
        True, "--long-only/--long-short",
        help="只做多（5 年回测显示做空腿在加密市场拖累收益）",
    ),
    fee_pct: float = typer.Option(0.05, "--fee", help="单边手续费 %"),
    slippage_pct: float = typer.Option(0.02, "--slippage", help="单边基础滑点 %"),
    spread_pct: float = typer.Option(0.01, "--spread", help="买卖价差全宽 %，每边收一半"),
    vol_slip: float = typer.Option(
        0.1, "--vol-slip",
        help="波动滑点：换手时额外收取该比例 × ATR/价格；0=关",
    ),
    oos_days: int = typer.Option(365, "--oos-days", help="样本外天数（0=不分割）"),
    include_funding: bool = typer.Option(
        True, "--funding/--no-funding",
        help="计入历史资金费（多头付正费率、空头收）",
    ),
    vol_target: float = typer.Option(
        0.0, "--vol-target",
        help="波动率目标化：目标年化波动（如 0.3）；0=关。降回撤、也降收益",
    ),
    window_days: int = typer.Option(
        0, "--windows",
        help="滚动窗口稳健性检查：每段天数（如 180）；0=关",
    ),
):
    """📈 经典组合策略回测：复利收益口径、含成本+资金费、牛熊震荡分段 + 样本外。"""
    from analyst.backtest.classic import (
        STRATEGIES,
        CostModel,
        apply_vol_target,
        build_cycle_regime,
        label_regimes,
        rolling_window_report,
        simulate,
    )
    from analyst.data.derivatives import fetch_funding_history
    from analyst.data.fetcher import fetch_candles_history

    if strategy not in STRATEGIES:
        console.print(f"[red]未知策略 {strategy}，可选：{', '.join(STRATEGIES)}[/red]")
        raise typer.Exit(1)

    sym = _normalize_symbol(symbol)
    cost = CostModel(
        fee_pct=fee_pct,
        slippage_pct=slippage_pct,
        spread_pct=spread_pct,
        vol_slip_atr_frac=vol_slip,
    )
    with console.status(f"[bold cyan]拉取 {sym} {timeframe} × {days} 天历史..."):
        series = fetch_candles_history(sym, timeframe, days=days, market="futures")
    candles = series.candles
    if len(candles) < 300:
        console.print(f"[red]历史数据不足（{len(candles)} 根）[/red]")
        raise typer.Exit(1)

    from analyst.data.bar_store import record_history

    data_check = record_history(
        candles, symbol=sym, timeframe=timeframe, market="futures"
    )
    gap = "通过" if data_check["ok"] else "有缺口"
    console.print(
        f"[dim]K 线自检 {gap}：{data_check['bars']} 根，缺 {data_check['missing_bars']} 根，"
        f"已写入 ohlcv.sqlite {data_check['stored_bars']} 根[/dim]"
    )
    for note in data_check["warnings"]:
        console.print(f"[yellow]· {note}[/yellow]")

    fn = STRATEGIES[strategy]
    kwargs = {}
    if strategy == "cycle_switch":
        # 牛熊用 BTC 判定（山寨跟随 BTC beta）
        with console.status("[bold cyan]拉取 BTC 历史构建牛熊判定..."):
            btc = fetch_candles_history(
                "BTC/USDT", timeframe, days=days, market="futures"
            )
        kwargs["regime"] = build_cycle_regime(btc.candles)
        kwargs["symbol"] = sym
    positions = fn(candles, **kwargs) if kwargs else fn(candles)
    if vol_target > 0:
        positions = apply_vol_target(
            candles, positions, timeframe=timeframe, target_annual_vol=vol_target
        )
    funding = None
    if include_funding:
        funding = fetch_funding_history(sym, days=days) or None
    labels = label_regimes(candles)
    rep = simulate(
        candles, positions, strategy=strategy, symbol=sym,
        timeframe=timeframe, cost=cost, regime_labels=labels, funding=funding,
    )

    mode = "（牛市多/熊市反弹空+破位空）" if strategy == "cycle_switch" else ""
    t = Table(title=f"📈 {strategy}{mode} · "
                    f"{sym} {timeframe} · {candles[0].timestamp:%Y-%m-%d} → "
                    f"{candles[-1].timestamp:%Y-%m-%d}")
    t.add_column("指标", style="cyan")
    t.add_column("值", justify="right")
    t.add_row("总收益（复利）", f"{rep.total_return_pct:+.1f}%")
    t.add_row("年化 CAGR", f"{rep.cagr_pct:+.1f}%")
    t.add_row("最大回撤", f"{rep.max_drawdown_pct:.1f}%")
    t.add_row("夏普（年化）", f"{rep.sharpe:.2f}")
    t.add_row("调仓次数", str(rep.trades))
    t.add_row("持仓时间占比", f"{rep.exposure:.0%}")
    t.add_row(
        "成本假设",
        f"手续费 {fee_pct:.3f}% + 滑点 {slippage_pct:.3f}% + 半价差 {spread_pct / 2:.3f}%",
    )
    if funding is not None:
        t.add_row("资金费净损益", f"{rep.funding_pnl_pct:+.2f}%")
    if vol_slip > 0:
        t.add_row("波动滑点", f"{vol_slip:.0%} × ATR/价格")
    if vol_target > 0:
        t.add_row("波动率目标", f"年化 {vol_target:.0%}")
    for k, zh in (("bull", "牛市段"), ("bear", "熊市段"), ("chop", "震荡段")):
        t.add_row(
            f"{zh}贡献（{rep.regime_bars.get(k, 0)} 根）",
            f"{rep.regime_return_pct.get(k, 0):+.1f}%",
        )
    console.print(t)

    if oos_days > 0:
        cutoff = candles[-1].timestamp.timestamp() - oos_days * 86400
        idx = next(
            (i for i, c in enumerate(candles)
             if c.timestamp.timestamp() >= cutoff),
            None,
        )
        if idx and idx > 60:
            oos_rep = simulate(
                candles[idx:], positions[idx:], strategy=strategy, symbol=sym,
                timeframe=timeframe, cost=cost, funding=funding,
            )
            console.print(
                f"[bold]样本外（最近 {oos_days} 天）[/bold]：收益 "
                f"{oos_rep.total_return_pct:+.1f}% · 回撤 "
                f"{oos_rep.max_drawdown_pct:.1f}% · 夏普 {oos_rep.sharpe:.2f}"
            )
    if window_days > 0:
        wins = rolling_window_report(
            candles, positions, strategy=strategy, symbol=sym,
            timeframe=timeframe, window_days=window_days,
            cost=cost, funding=funding,
        )
        if wins:
            pos_cnt = sum(1 for r in wins if r.total_return_pct > 0)
            seg = "  ".join(
                f"{r.start:%y-%m}:{r.total_return_pct:+.0f}%" for r in wins
            )
            console.print(
                f"[bold]滚动窗口（每 {window_days} 天）[/bold]："
                f"盈利 {pos_cnt}/{len(wins)} 段\n[dim]{seg}[/dim]"
            )
            if pos_cnt < len(wins) * 0.6:
                console.print(
                    "[yellow]⚠ 超过四成窗口亏损：整体数字可能靠个别行情段撑起，谨慎。[/yellow]"
                )

    from analyst.backtest.robustness import robustness_bundle

    bundle = robustness_bundle(
        candles, positions, rep,
        strategy=strategy, symbol=sym, timeframe=timeframe,
        cost=cost, funding=funding, regime=kwargs.get("regime"),
    )
    _print_robustness(bundle)
    console.print(
        "[dim]提示：回测≠未来。上线前先小仓位验证，单笔风险 ≤ 账户 1%。[/dim]"
    )


@app.command("backtest-xs")
def backtest_xs(
    symbols: str = typer.Option(
        "BTC,ETH,SOL,BNB,AAVE,UNI,SUI,DOGE", "--symbols",
        help="观察池（逗号分隔），上市晚的币自动延后进入排序",
    ),
    timeframe: str = typer.Option("4h", "--timeframe", "-t"),
    days: int = typer.Option(1095, "--days"),
    lookback_days: int = typer.Option(14, "--lookback", help="动量窗口（天）"),
    top_n: int = typer.Option(2, "--top"),
    rebalance_days: int = typer.Option(7, "--rebalance", help="调仓间隔（天）"),
    short_in_bear: bool = typer.Option(
        True, "--bear-short/--bear-flat", help="熊市做空最弱 / 熊市空仓"
    ),
    include_funding: bool = typer.Option(True, "--funding/--no-funding"),
):
    """🏁 横截面动量组合回测：做多最强、熊市做空最弱（BTC 定相位）。"""
    from analyst.backtest.classic import BARS_PER_YEAR
    from analyst.compute.strategies.cycle_switch import build_cycle_regime
    from analyst.compute.strategies.xs_momentum import (
        XsMomentumConfig,
        backtest_xs_momentum,
        current_xs_ranking,
    )
    from analyst.data.derivatives import fetch_funding_history
    from analyst.data.fetcher import fetch_candles_history

    bars_per_day = BARS_PER_YEAR.get(timeframe, 2190) // 365
    syms = [_normalize_symbol(s) for s in symbols.split(",") if s.strip()]
    series_map = {}
    with console.status(f"[bold cyan]拉取 {len(syms)} 币 × {days} 天..."):
        for s in syms:
            try:
                sr = fetch_candles_history(s, timeframe, days=days, market="futures")
                if len(sr.candles) > 300:
                    series_map[s] = sr.candles
            except Exception as e:
                console.print(f"[yellow]{s} 拉取失败，跳过：{e}[/yellow]")
    if "BTC/USDT" not in series_map:
        console.print("[red]观察池必须含 BTC（定牛熊相位）[/red]")
        raise typer.Exit(1)

    regime = build_cycle_regime(series_map["BTC/USDT"])
    funding_map = None
    if include_funding:
        with console.status("[bold cyan]拉取各币历史资金费..."):
            funding_map = {s: fetch_funding_history(s, days=days) for s in series_map}

    cfg = XsMomentumConfig(
        lookback=lookback_days * bars_per_day,
        rebalance=rebalance_days * bars_per_day,
        top_n=top_n,
        short_in_bear=short_in_bear,
    )
    rep = backtest_xs_momentum(
        series_map, regime, cfg, timeframe=timeframe, funding_map=funding_map
    )

    t = Table(
        title=L(
            f"🏁 横截面动量 · {len(series_map)} 币池 · "
            f"{rep.start:%Y-%m-%d} → {rep.end:%Y-%m-%d}",
            f"🏁 Cross-sectional momentum · {len(series_map)} coins · "
            f"{rep.start:%Y-%m-%d} → {rep.end:%Y-%m-%d}",
        )
    )
    t.add_column(L("指标", "Metric"), style="cyan")
    t.add_column(L("值", "Value"), justify="right")
    t.add_row(L("总收益（复利）", "Total return (compounded)"), f"{rep.total_return_pct:+.1f}%")
    t.add_row(L("年化 CAGR", "CAGR"), f"{rep.cagr_pct:+.1f}%")
    t.add_row(L("最大回撤", "Max drawdown"), f"{rep.max_drawdown_pct:.1f}%")
    t.add_row(L("夏普（年化）", "Sharpe (ann.)"), f"{rep.sharpe:.2f}")
    t.add_row(L("调仓次数", "Rebalances"), str(rep.rebalances))
    t.add_row(L("持仓时间占比", "Time in market"), f"{rep.exposure:.0%}")
    if include_funding:
        t.add_row(L("资金费净损益", "Funding P&L"), f"{rep.funding_pnl_pct:+.2f}%")
    t.add_row(
        L("参数", "Params"),
        L(
            f"动量 {lookback_days}天 · top{top_n} · {rebalance_days}天调仓 · "
            f"熊市{'做空最弱' if short_in_bear else '空仓'}",
            f"Momentum {lookback_days}d · top{top_n} · rebalance {rebalance_days}d · "
            f"bear {'short weakest' if short_in_bear else 'flat'}",
        ),
    )
    console.print(t)

    console.print("\n[bold]当前动量排名[/bold]")
    for s, m in current_xs_ranking(series_map, cfg):
        bar = "█" * min(20, int(abs(m) * 60))
        color = "green" if m >= 0 else "red"
        console.print(f"  {s:12s} [{color}]{m:+7.1%} {bar}[/{color}]")
    console.print(
        "[dim]与 cycle_switch 相关性低，适合并行分资金跑；参数平原 12~25 天。[/dim]"
    )


@app.command("backtest-carry")
def backtest_carry(
    symbol: str = typer.Argument("BTC", help="币种"),
    days: int = typer.Option(1095, "--days"),
    enter_apr: float = typer.Option(
        5.5, "--enter-apr", help="建仓门槛：费率 EMA 年化 %（÷1095 得每档）"
    ),
    ema_days: int = typer.Option(7, "--ema-days", help="费率 EMA 窗口（天）"),
    fee_pct: float = typer.Option(0.05, "--fee", help="每腿单边费率 %"),
):
    """💰 资金费套利回测：现货多+永续空 delta 中性收费（方向无关）。"""
    from analyst.backtest.classic import CostModel
    from analyst.compute.strategies.funding_carry import (
        FundingCarryConfig,
        backtest_funding_carry,
        current_carry_status,
    )
    from analyst.data.derivatives import fetch_funding_history

    sym = _normalize_symbol(symbol)
    with console.status(f"[bold cyan]拉取 {sym} 历史资金费 × {days} 天..."):
        funding = fetch_funding_history(sym, days=days)
    if len(funding) < 100:
        console.print(f"[red]资金费样本不足（{len(funding)}）[/red]")
        raise typer.Exit(1)

    cfg = FundingCarryConfig(
        ema_n=ema_days * 3,
        enter_rate=enter_apr / 100.0 / (3 * 365),
    )
    rep = backtest_funding_carry(
        sym, funding, cfg, cost=CostModel(fee_pct=fee_pct, slippage_pct=0.02)
    )

    t = Table(
        title=L(
            f"💰 资金费套利 · {sym} · {rep.start:%Y-%m-%d} → {rep.end:%Y-%m-%d}",
            f"💰 Funding carry · {sym} · {rep.start:%Y-%m-%d} → {rep.end:%Y-%m-%d}",
        )
    )
    t.add_column("指标", style="cyan")
    t.add_column("值", justify="right")
    t.add_row("总收益（复利）", f"{rep.total_return_pct:+.2f}%")
    t.add_row("年化（全程）", f"{rep.apr_pct:+.2f}%")
    t.add_row("年化（在仓时段）", f"{rep.apr_in_position_pct:+.2f}%")
    t.add_row("最大回撤", f"{rep.max_drawdown_pct:.2f}%")
    t.add_row("在仓时间占比", f"{rep.exposure:.0%}")
    t.add_row("进出往返次数", str(rep.round_trips))
    t.add_row("累计成本", f"{rep.cost_paid_pct:.2f}%")
    t.add_row("在仓平均费率", f"{rep.avg_rate_collected_pct:+.5f}%/8h")
    console.print(t)

    st = current_carry_status(funding[-270:], cfg)
    icon = "🟢" if st.get("signal") == "carry" else "⚪"
    console.print(
        f"\n{icon} 当前：费率 EMA {st.get('ema_rate_pct', 0):+.5f}%/8h"
        f"（年化 {st.get('ema_apr_pct', 0):+.2f}%）· {st.get('note', '')}"
    )
    console.print(
        "[dim]delta 中性：价格涨跌无关，赚多头杠杆的融资成本；"
        "牛熊震荡皆可收，负费率期自动离场。实操需现货+合约双账户等名义对冲。[/dim]"
    )


@app.command("digest")
def digest(
    send: bool = typer.Option(False, "--send", help="生成后推送 Telegram"),
):
    """📋 生成 AI 交易日报（事实来自系统数据，AI 只做总结）。"""
    from analyst.llm.digest import compose_daily_digest

    with console.status("[bold cyan]聚合系统事实并生成日报..."):
        out = compose_daily_digest()
    console.print(
        f"[dim]来源: {out.get('source')}"
        + (f" · {out.get('provider')}/{out.get('model')}" if out.get("model") else "")
        + "[/dim]\n"
    )
    console.print(out.get("text", ""))
    if send:
        from analyst.config import get_settings
        from analyst.monitor.notifier import build_default_notifier

        s = get_settings()
        n = build_default_notifier(
            telegram_bot_token=s.telegram_bot_token,
            telegram_chat_id=s.telegram_chat_id,
        )
        n.send_text(out.get("text") or "")
        console.print("[green]已推送 Telegram[/green]")


@app.command("square-post")
def square_post_cmd(
    text: str = typer.Option("", "--text", help="直接发这段文案（测试用）"),
    symbol: str = typer.Option("BTC/USDT", "--symbol", help="预览用品种"),
    timeframe: str = typer.Option("4h", "--timeframe", "-t"),
    publish: bool = typer.Option(
        False, "--publish", help="真发到币安广场（默认只预览文案）"
    ),
):
    """广场短评：预览文案，或用 --publish / --text 真发。"""
    from analyst.config import get_settings
    from analyst.integrations.binance_square import mask_key, post_text
    from analyst.monitor.square_posts import compose_regime_square_post

    s = get_settings()
    body = (text or "").strip()
    if not body:
        # 最小可预览：用假锁点结构拼一版示意（真链路走盯盘 market_regime）
        from analyst.compute.swing_levels import SwingLevels
        from analyst.compute.market_regime import MarketRegime

        swing = SwingLevels(
            swing_high=70000,
            swing_low=60000,
            rebound_382=63820,
            rebound_500=65000,
            rebound_618=66180,
            retr_382=66180,
            retr_618=63820,
            boll_mid=64000,
            confluence_382=False,
            confluence_618=False,
            daily_bias="up",
            defense_level=62000,
            htf_ready=True,
            horizon="swing",
            touch_level=67000,
            touch_count=1,
            rs_note="—",
            summary_line="预览",
        )
        reg = MarketRegime(
            regime="strong_trend",
            regime_zh="强势盘",
            trade_side="long",
            seed_style="market",
            add_mode="breakout",
            tp_style="new_high",
            defense_broken=False,
            continuation_intact=True,
            nearest_support=62000,
            nearest_resistance=67000,
            prev_day_high=None,
            prev_day_low=None,
            intraday_high=None,
            intraday_low=None,
            tp_intraday_50=None,
            tp_intraday_618=None,
            ema12h_6=None,
            spike_stop_recent=False,
            playbook_line="市价小头仓 + 突破近阻力加仓",
            summary_line="预览短评",
        )
        body = compose_regime_square_post(
            symbol=symbol, timeframe=timeframe, price=65000.0, swing=swing, regime=reg
        )
        console.print("[dim]（示意文案；真发帖由盯盘 market_regime 触发）[/dim]\n")

    console.print(body)
    if not publish and not text:
        console.print("\n[yellow]加 --publish --text '...' 才会真发[/yellow]")
        return
    if not publish:
        console.print("\n[yellow]未加 --publish，只预览[/yellow]")
        return
    key = (s.binance_square_openapi_key or "").strip()
    if not key:
        console.print("[red]未配置 BINANCE_SQUARE_OPENAPI_KEY[/red]")
        raise typer.Exit(1)
    with console.status(f"[bold cyan]发帖中 key={mask_key(key)}..."):
        result = post_text(key, body)
    console.print(
        f"[green]已发[/green] id={result.get('id')} link={result.get('shareLink')}"
    )


@app.command("research-ideas")
def research_ideas():
    """🔬 AI 研究助手：基于系统近况提出可回测的改进假设（AI 提假设，回测当法官）。"""
    from analyst.llm.digest import compose_research_ideas

    with console.status("[bold cyan]AI 生成研究假设..."):
        out = compose_research_ideas()
    if not out.get("text"):
        console.print(f"[red]{out.get('error') or '无可用 LLM 线路'}[/red]")
        raise typer.Exit(1)
    console.print(f"[dim]via {out.get('provider')}/{out.get('model')}[/dim]\n")
    console.print(out["text"])
    console.print(
        "\n[dim]提醒：假设 ≠ 结论。逐条回测（5年×3币、看滚动窗口），"
        "单币变好不算数。[/dim]"
    )


@app.command("cycle-outlook")
def cycle_outlook(
    timeframe: str = typer.Option("1d", "--timeframe", "-t", help="日历用的 K 线周期（建议 1d）"),
    days: int = typer.Option(800, "--days", help="拉取历史天数"),
    telegram: bool = typer.Option(False, "--telegram", help="同时推送到 Telegram"),
):
    """🔮 Wolfy 四年周期展望：刻舟求剑日历与转折点倒计时。"""
    from analyst.compute.cycle_theory import (
        attach_wave_index,
        evaluate_cycle_outlook,
        format_outlook_text,
    )
    from analyst.config import get_settings
    from analyst.data.fetcher import fetch_candles_history
    from analyst.monitor.notifier import build_default_notifier

    with console.status(f"[bold cyan]拉取 BTC {timeframe} × {days} 天..."):
        series = fetch_candles_history(
            "BTC/USDT", timeframe, days=days, market="futures"
        )
    outlook = evaluate_cycle_outlook(series)
    attach_wave_index(outlook)
    cal = outlook.calendar
    zh = {"bull": "牛市", "bear": "熊市"}

    body = (
        f"[bold]图1 刻舟求剑（日历）[/bold]\n"
        f"当前相位：{zh[cal.phase]} 第 {cal.phase_day}/{cal.phase_total_days} 天\n"
        f"下一轮里程碑：{cal.next_milestone.label}\n"
        f"预计日期：{cal.next_milestone.date:%Y-%m-%d}（还有 {cal.days_to_milestone} 天）\n"
        f"本周期牛市起点：{cal.cycle_bull_start:%Y-%m-%d}\n"
    )
    if outlook.wave_index:
        body += f"\n[bold]狼波指数[/bold]\n{outlook.wave_index.line()}\n"
        if outlook.wave_index.alerts:
            body += "\n".join(outlook.wave_index.alerts) + "\n"
    if outlook.alerts:
        body += "\n[bold yellow]提醒[/bold yellow]\n" + "\n".join(outlook.alerts)
    else:
        body += "\n[dim]暂无临近里程碑提醒（距节点 >90 天）[/dim]"

    console.print(
        Panel(
            body,
            title=L(f"🔮 周期展望 · BTC · {outlook.as_of:%Y-%m-%d}", f"🔮 Cycle outlook · BTC · {outlook.as_of:%Y-%m-%d}"),
            border_style="yellow",
        )
    )
    console.print(
        "[dim]日历：熊市底起算牛 1064 天 / 熊 364 天。"
        "狼波：区块高度纯函数，0=理论熊底，1=理论牛顶。[/dim]"
    )

    if telegram:
        settings = get_settings()
        text = format_outlook_text(outlook)
        build_default_notifier(
            telegram_bot_token=settings.telegram_bot_token,
            telegram_chat_id=settings.telegram_chat_id,
        ).send_text(text)
        console.print("[green]已尝试推送 Telegram[/green]")


@app.command("cycle-status")
def cycle_status(
    symbols: str = typer.Argument(
        "BTC,ETH,SOL,BNB", help="逗号分隔的币种列表"
    ),
    timeframe: str = typer.Option("4h", "--timeframe", "-t", help="K 线周期"),
):
    """🧭 当前牛熊相位 + cycle_switch 策略各币的实时目标仓位。"""
    from analyst.compute.cycle_theory import evaluate_cycle_outlook
    from analyst.backtest.classic import (
        HALVING_DATES,
        build_cycle_regime,
        halving_phase,
        positions_cycle_switch,
    )
    from analyst.data.fetcher import fetch_candles_history

    syms = [_normalize_symbol(s) for s in symbols.split(",") if s.strip()]
    with console.status("[bold cyan]拉取 BTC 历史构建牛熊判定..."):
        btc = fetch_candles_history("BTC/USDT", timeframe, days=1825,
                                    market="futures")
    # Wolfy 日历展望（1d 精度更适合四年周期）
    btc_1d = fetch_candles_history("BTC/USDT", "1d", days=800, market="futures")
    outlook = evaluate_cycle_outlook(btc_1d)
    wcal = outlook.calendar
    wzh = {"bull": L("牛市", "Bull"), "bear": L("熊市", "Bear")}
    wolfy_lines = L(
        f"刻舟求剑：{wzh[wcal.phase]} 第 {wcal.phase_day}/{wcal.phase_total_days} 天 · "
        f"距{wcal.next_milestone.label} {wcal.days_to_milestone} 天"
        f"（{wcal.next_milestone.date:%Y-%m-%d}）",
        f"Calendar: {wzh[wcal.phase]} day {wcal.phase_day}/{wcal.phase_total_days} · "
        f"{wcal.days_to_milestone} days to {wcal.next_milestone.label} "
        f"({wcal.next_milestone.date:%Y-%m-%d})",
    )
    if outlook.alerts:
        wolfy_lines += "\n" + "\n".join(outlook.alerts[:4])

    regime = build_cycle_regime(btc.candles)
    now_ts = btc.candles[-1].timestamp
    cal = halving_phase(now_ts)
    reg = regime.get(now_ts, "accum")
    days_since = (now_ts - max(h for h in HALVING_DATES if h <= now_ts)).days
    zh = {"bull": L("牛市", "Bull"), "bear": L("熊市", "Bear"), "accum": L("筑底/中性", "Accumulation / neutral")}
    console.print(
        Panel(
            wolfy_lines,
            title=L("🔮 Wolfy 周期展望（刻舟求剑日历）", "🔮 Wolfy cycle outlook (calendar model)"),
            border_style="yellow",
        )
    )
    console.print(
        Panel(
            L(
                f"减半日历相位：[bold]{zh[cal]}[/bold]（距上次减半 {days_since} 天）\n"
                f"双确认最终判定：[bold]{zh[reg]}[/bold]\n"
                f"[dim]规则：日历+200日线双确认才算熊；熊市清多、只空 z>1.5 的反弹[/dim]",
                f"Halving-calendar phase: [bold]{zh[cal]}[/bold] ({days_since} days since last halving)\n"
                f"Double-confirmed regime: [bold]{zh[reg]}[/bold]\n"
                f"[dim]Bear only if calendar + 200-day EMA agree; in bear close longs and only short z>1.5 bounces[/dim]",
            ),
            title=L(
                f"🧭 cycle_switch 执行相位（BTC · {timeframe} · {now_ts:%Y-%m-%d %H:%M} UTC）",
                f"🧭 cycle_switch execution phase (BTC · {timeframe} · {now_ts:%Y-%m-%d %H:%M} UTC)",
            ),
            border_style="cyan",
        )
    )

    t = Table(title=L("cycle_switch 当前目标仓位", "cycle_switch target positions"))
    t.add_column(L("品种", "Symbol"), style="cyan")
    t.add_column(L("目标仓位", "Target"), justify="right")
    t.add_column(L("现价", "Price"), justify="right")
    t.add_column(L("40根高点(入场)", "40-bar high (entry)"), justify="right")
    t.add_column(L("20根低点(离场)", "20-bar low (exit)"), justify="right")
    t.add_column("z-score", justify="right")
    for sym in syms:
        s = fetch_candles_history(sym, timeframe, days=1825, market="futures")
        c = s.candles
        pos = positions_cycle_switch(c, regime, symbol=sym)[-1]
        closes = [x.close for x in c]
        w = closes[-20:]
        mean = sum(w) / 20
        std = (sum((v - mean) ** 2 for v in w) / 20) ** 0.5
        z = (closes[-1] - mean) / std if std > 0 else 0.0
        hh = max(x.high for x in c[-41:-1])
        ll = min(x.low for x in c[-21:-1])
        pos_txt = (
            "[green]做多 100%[/green]" if pos > 0
            else (f"[red]做空 {abs(pos):.0%}[/red]" if pos < 0 else "空仓")
        )
        t.add_row(
            sym, pos_txt, f"{closes[-1]:.6g}", f"{hh:.6g}", f"{ll:.6g}",
            f"{z:+.2f}",
        )
    console.print(t)
    console.print(
        "[dim]仅提醒不下单；数据为最近收盘 K（缓存 24h 内）。[/dim]"
    )


# ═══════════════════════════════════════════════════════════════
# Web 界面
# ═══════════════════════════════════════════════════════════════
@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", help="监听地址"),
    port: int = typer.Option(8000, "--port", help="监听端口"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="自动打开浏览器"),
    lan: bool = typer.Option(
        False, "--lan", help="局域网可访问（绑定 0.0.0.0，供手机浏览器连接）"
    ),
):
    """🌐 启动 Web 界面（推文流风格）"""
    try:
        import analyst.web.server as web_server_mod
    except ImportError:
        console.print(
            "[bold red]❌ Web 依赖未安装[/bold red]\n"
            "请运行: [cyan]uv sync --extra web[/cyan]\n"
            "或: [cyan]pip install -e \".[web]\"[/cyan]"
        )
        raise typer.Exit(1) from None

    if lan:
        host = "0.0.0.0"

    url = f"http://{host}:{port}"
    console.print(f"[bold green]🌐 Web 界面启动中: [link]{url}[/link][/bold green]")
    if host in ("0.0.0.0", "::"):
        for ip in _lan_ipv4():
            console.print(f"[bold cyan]手机访问：http://{ip}:{port}[/bold cyan]")
    console.print(f"[dim]web.server 源码: {web_server_mod.__file__}[/dim]")

    if open_browser:
        import threading
        import webbrowser

        def _open():
            import time
            time.sleep(1.0)
            webbrowser.open(f"http://127.0.0.1:{port}" if host in ("0.0.0.0", "::") else url)

        threading.Thread(target=_open, daemon=True).start()

    web_server_mod.serve(host, port)


if __name__ == "__main__":
    app()

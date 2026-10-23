"""策略库目录。

实时策略（monitor / hub 收盘评估）：
  · cycle_switch  — 牛熊周期切换（4h 收盘）

组合策略（backtest / 多币组合）：
  · cycle_switch  — 牛熊周期切换（本包）
  · xs_momentum   — 横截面动量（多币 top2）
  · funding_carry — 资金费 delta 中性套利

列出全部：analyst strategies
"""

from __future__ import annotations

from dataclasses import dataclass

from analyst.i18n import L

_EN = {
    "cycle_switch": (
        "Bull/bear cycle switch (D)",
        "Halving calendar × 200-day EMA double confirmation; Donchian long-only in bull markets, "
        "bounce shorts + breakdown shorts (half size) in bear markets; alerts include a volatility-targeted "
        "position size (backtest MDD -46% → -28%)",
    ),
    "xs_momentum": (
        "Cross-sectional momentum",
        "Multi-coin momentum ranking: long the top 2, short the weakest in bear markets; "
        "14-day window (stable across 12–25 days)",
    ),
    "funding_carry": (
        "Funding carry",
        "Delta neutral: long spot + short perp to collect funding; direction-agnostic, 5-year drawdown <1.1%",
    ),
}


@dataclass(frozen=True)
class StrategyInfo:
    id: str
    name: str
    kind: str          # realtime | portfolio
    module: str
    description: str
    cli: str | None = None


STRATEGY_CATALOG: list[StrategyInfo] = [
    StrategyInfo(
        id="cycle_switch",
        name="牛熊周期切换（D）",
        kind="portfolio",
        module="analyst.compute.strategies.cycle_switch",
        description="减半日历×200日线双确认；牛市唐奇安只多，熊市反弹空+破位空（半仓）；"
                    "提醒附波动率目标化建议仓位（回测 MDD -46%→-28%）",
        cli="analyst backtest-classic BTC -s cycle_switch --days 1825",
    ),
    StrategyInfo(
        id="xs_momentum",
        name="横截面动量",
        kind="portfolio",
        module="analyst.compute.strategies.xs_momentum",
        description="多币动量排序：做多最强 top2、熊市空最弱；14 天窗口（12~25 天参数平原）",
        cli="analyst backtest-xs --days 1825",
    ),
    StrategyInfo(
        id="funding_carry",
        name="资金费套利",
        kind="portfolio",
        module="analyst.compute.strategies.funding_carry",
        description="delta 中性：现货多+永续空收资金费；方向无关，5 年回撤 <1.1%",
        cli="analyst backtest-carry BTC --days 1825",
    ),
]


def list_strategies(*, kind: str | None = None) -> list[StrategyInfo]:
    items = [s for s in STRATEGY_CATALOG if s.kind == kind] if kind else list(STRATEGY_CATALOG)
    out: list[StrategyInfo] = []
    for s in items:
        en_name, en_desc = _EN.get(s.id, (s.name, s.description))
        out.append(
            StrategyInfo(
                id=s.id,
                name=L(s.name, en_name),
                kind=s.kind,
                module=s.module,
                description=L(s.description, en_desc),
                cli=s.cli,
            )
        )
    return out

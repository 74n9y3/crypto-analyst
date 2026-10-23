"""回测稳健性：滚动样本外、成本敏感度、Deflated Sharpe、CSCV/PBO。

策略参数不在每个窗口里重新搜索。Walk-Forward 只检验「已经定下的仓位规则」
在连续样本外窗口是否还赚钱。PBO 用参数邻域当候选集合，衡量这组参数是不是
靠挑选才好看。加密波段交易笔数远少于外汇超短线，这里不套用「每窗 300 笔」。
连续通过门槛仍用指南的 6 个窗口。
"""

from __future__ import annotations

import math
from datetime import timedelta
from itertools import combinations

from analyst.backtest.classic import (
    BARS_PER_YEAR,
    ClassicReport,
    CostModel,
    simulate,
)
from analyst.data.fetcher import Candle
from analyst.i18n import L

_EULER = 0.5772156649015329
# 指南：连续样本外通过不少于 6 窗
CONSECUTIVE_PASS = 6


def walk_forward(
    candles: list[Candle],
    positions: list[float],
    *,
    strategy: str,
    symbol: str,
    timeframe: str,
    cost: CostModel | None = None,
    funding: list[tuple[int, float]] | None = None,
    oos_days: int = 180,
    step_days: int = 90,
    min_bars: int = 40,
) -> dict:
    """按固定长度的样本外窗口滚动模拟。窗口之间按 step_days 前移。"""
    if oos_days <= 0 or not candles:
        return _wf_payload([], oos_days, step_days)
    cost = cost or CostModel()
    last = candles[-1].timestamp
    cursor = candles[0].timestamp + timedelta(days=oos_days)
    windows: list[dict] = []
    while cursor <= last:
        start = cursor - timedelta(days=oos_days)
        seg_c, seg_p = _slice(candles, positions, start, cursor)
        if len(seg_c) >= min_bars:
            rep = simulate(
                seg_c,
                seg_p,
                strategy=strategy,
                symbol=symbol,
                timeframe=timeframe,
                cost=cost,
                funding=funding,
            )
            passed = (
                rep.total_return_pct > 0
                and rep.sharpe > 0
                and rep.max_drawdown_pct > -50
            )
            windows.append(
                {
                    "start": seg_c[0].timestamp.isoformat(),
                    "end": seg_c[-1].timestamp.isoformat(),
                    "total_return_pct": round(rep.total_return_pct, 2),
                    "sharpe": round(rep.sharpe, 2),
                    "max_drawdown_pct": round(rep.max_drawdown_pct, 2),
                    "trades": rep.trades,
                    "passed": passed,
                }
            )
        cursor += timedelta(days=step_days)
    return _wf_payload(windows, oos_days, step_days)


def cost_sensitivity(
    candles: list[Candle],
    positions: list[float],
    *,
    strategy: str,
    symbol: str,
    timeframe: str,
    cost: CostModel,
    funding: list[tuple[int, float]] | None = None,
    scales: tuple[float, ...] = (1.0, 1.5, 2.0),
) -> list[dict]:
    """把手续费、滑点、价差、波动滑点同时放大，看收益是否还为正。"""
    rows: list[dict] = []
    for scale in scales:
        scaled = CostModel(
            fee_pct=cost.fee_pct * scale,
            slippage_pct=cost.slippage_pct * scale,
            spread_pct=cost.spread_pct * scale,
            vol_slip_atr_frac=cost.vol_slip_atr_frac * scale,
        )
        rep = simulate(
            candles,
            positions,
            strategy=strategy,
            symbol=symbol,
            timeframe=timeframe,
            cost=scaled,
            funding=funding,
        )
        rows.append(
            {
                "scale": scale,
                "total_return_pct": round(rep.total_return_pct, 2),
                "sharpe": round(rep.sharpe, 2),
                "max_drawdown_pct": round(rep.max_drawdown_pct, 2),
            }
        )
    return rows


def deflated_sharpe(returns: list[float], n_trials: int, *, periods_per_year: int) -> dict:
    """Bailey & López de Prado 的 Deflated Sharpe。

    夏普用每根收益（未年化）。``n_trials`` 是看过的候选策略数；为 1 时不惩罚多重检验，
    只按偏度和峰度收缩。概率 > 0.95 记为 PASS。
    """
    clean = [r for r in returns if math.isfinite(r)]
    t = len(clean)
    empty = {
        "dsr_prob": None,
        "sr_per_bar": None,
        "sr_annual": None,
        "sr_benchmark": None,
        "n_trials": n_trials,
        "verdict": L("样本不足", "Insufficient sample"),
    }
    if t < 30:
        return empty
    mu = sum(clean) / t
    var = sum((r - mu) ** 2 for r in clean) / (t - 1)
    sd = math.sqrt(var)
    if sd <= 0:
        empty["verdict"] = L("收益没有波动", "Returns have no variance")
        return empty
    sr = mu / sd
    m3 = sum((r - mu) ** 3 for r in clean) / t
    m4 = sum((r - mu) ** 4 for r in clean) / t
    skew = m3 / (sd ** 3)
    kurt = m4 / (sd ** 4)  # 原始峰度，正态为 3
    n = max(int(n_trials), 1)
    if n <= 1:
        sr_star = 0.0
    else:
        z1 = _norm_ppf(1.0 - 1.0 / n)
        z2 = _norm_ppf(1.0 - 1.0 / (n * math.e))
        sr_star = math.sqrt(1.0 / (t - 1)) * ((1.0 - _EULER) * z1 + _EULER * z2)
    moment = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr
    if moment <= 1e-12:
        moment = 1e-12
    se = math.sqrt(moment / (t - 1))
    z = (sr - sr_star) / se if se > 0 else 0.0
    prob = _norm_cdf(z)
    annual = sr * math.sqrt(periods_per_year) if periods_per_year > 0 else sr
    return {
        "dsr_prob": round(prob, 4),
        "sr_per_bar": round(sr, 4),
        "sr_annual": round(annual, 2),
        "sr_benchmark": round(sr_star, 4),
        "n_trials": n,
        "verdict": "PASS" if prob > 0.95 else "FAIL",
    }


def cscv_pbo(returns_matrix: list[list[float]], n_splits: int = 8) -> dict:
    """CSCV 估计 PBO：样本内最优策略在样本外落到中位数以下的比例。

    PBO < 0.25 记 PASS，0.25–0.50 记 WARN，高于 0.50 记 FAIL。
    """
    n_strat = len(returns_matrix)
    if n_strat < 2:
        return {"pbo": None, "n_splits": n_splits, "n_strategies": n_strat, "verdict": L("候选不足", "Not enough candidates")}
    length = min(len(row) for row in returns_matrix)
    splits = n_splits if n_splits % 2 == 0 else n_splits - 1
    while splits >= 4 and length // splits < 20:
        splits -= 2
    if splits < 4 or length // splits < 5:
        return {
            "pbo": None,
            "n_splits": splits,
            "n_strategies": n_strat,
            "verdict": L("样本不足", "Insufficient sample"),
        }
    fold = length // splits
    blocks: list[list[float]] = []
    for row in returns_matrix:
        sums: list[float] = []
        for i in range(splits):
            chunk = row[i * fold : (i + 1) * fold]
            total = 0.0
            for r in chunk:
                total += math.log1p(max(min(r, 10.0), -0.999999))
            sums.append(total)
        blocks.append(sums)

    half = splits // 2
    below = 0
    total_splits = 0
    for is_idx in combinations(range(splits), half):
        is_set = set(is_idx)
        oos_idx = [i for i in range(splits) if i not in is_set]
        is_scores = [sum(b[i] for i in is_idx) for b in blocks]
        oos_scores = [sum(b[i] for i in oos_idx) for b in blocks]
        best = max(range(n_strat), key=lambda i: is_scores[i])
        better = sum(1 for s in oos_scores if s > oos_scores[best])
        if better >= n_strat / 2:
            below += 1
        total_splits += 1
    pbo = below / total_splits if total_splits else 1.0
    if pbo < 0.25:
        verdict = "PASS"
    elif pbo <= 0.50:
        verdict = "WARN"
    else:
        verdict = "FAIL"
    return {
        "pbo": round(pbo, 4),
        "n_splits": splits,
        "n_strategies": n_strat,
        "combinations": total_splits,
        "verdict": verdict,
    }


def robustness_bundle(
    candles: list[Candle],
    positions: list[float],
    report: ClassicReport,
    *,
    strategy: str,
    symbol: str,
    timeframe: str,
    cost: CostModel,
    funding: list[tuple[int, float]] | None = None,
    regime: dict | None = None,
    oos_days: int = 180,
    step_days: int = 90,
) -> dict:
    """一次回测附带的稳健性结果。``regime`` 仅 cycle_switch 的 PBO 邻域需要。"""
    wf = walk_forward(
        candles,
        positions,
        strategy=strategy,
        symbol=symbol,
        timeframe=timeframe,
        cost=cost,
        funding=funding,
        oos_days=oos_days,
        step_days=step_days,
    )
    sensitivity = cost_sensitivity(
        candles,
        positions,
        strategy=strategy,
        symbol=symbol,
        timeframe=timeframe,
        cost=cost,
        funding=funding,
    )
    trials, trial_note = _trial_matrix(
        candles,
        report.bar_returns,
        strategy=strategy,
        symbol=symbol,
        timeframe=timeframe,
        cost=cost,
        funding=funding,
        regime=regime,
    )
    n_trials = len(trials) if trials else 1
    bpy = BARS_PER_YEAR.get(timeframe, 365)
    dsr = deflated_sharpe(report.bar_returns, n_trials, periods_per_year=bpy)
    pbo = cscv_pbo(trials) if trials else {
        "pbo": None,
        "n_strategies": 1,
        "verdict": L("未计算", "Not computed"),
        "reason": trial_note,
    }
    doubled = next((row for row in sensitivity if row["scale"] == 2.0), None)
    return {
        "walk_forward": wf,
        "cost_sensitivity": sensitivity,
        "cost_2x_still_positive": bool(doubled and doubled["total_return_pct"] > 0),
        "deflated_sharpe": dsr,
        "pbo": pbo,
    }


def _trial_matrix(
    candles: list[Candle],
    base_returns: list[float],
    *,
    strategy: str,
    symbol: str,
    timeframe: str,
    cost: CostModel,
    funding: list[tuple[int, float]] | None,
    regime: dict | None,
) -> tuple[list[list[float]], str]:
    if strategy != "cycle_switch" or regime is None:
        return [], L("单一路径，没有参数邻域，不算 PBO", "Single path with no parameter neighborhood; PBO not computed")
    from analyst.compute.strategies.cycle_switch import positions_cycle_switch

    grid: list[tuple[int, int, bool]] = []
    for entry_n in (20, 40, 60):
        for exit_n in (10, 20):
            if exit_n >= entry_n:
                continue
            for bear in (True, False):
                grid.append((entry_n, exit_n, bear))
    matrix: list[list[float]] = []
    for entry_n, exit_n, bear in grid:
        pos = positions_cycle_switch(
            candles,
            regime,
            entry_n=entry_n,
            exit_n=exit_n,
            bear_trend_short=bear,
        )
        rep = simulate(
            candles,
            pos,
            strategy=strategy,
            symbol=symbol,
            timeframe=timeframe,
            cost=cost,
            funding=funding,
        )
        matrix.append(rep.bar_returns)
    if base_returns and matrix and len(base_returns) != len(matrix[0]):
        return [], L("参数邻域与基准收益长度不一致", "Parameter neighborhood length does not match baseline returns")
    return matrix, ""


def _slice(
    candles: list[Candle],
    positions: list[float],
    start,
    end,
) -> tuple[list[Candle], list[float]]:
    seg_c: list[Candle] = []
    seg_p: list[float] = []
    for c, p in zip(candles, positions, strict=True):
        if c.timestamp < start:
            continue
        if c.timestamp >= end:
            break
        seg_c.append(c)
        seg_p.append(p)
    return seg_c, seg_p


def _wf_payload(windows: list[dict], oos_days: int, step_days: int) -> dict:
    flags = [bool(w["passed"]) for w in windows]
    n = len(windows)
    n_pass = sum(flags)
    consec = _max_consecutive(flags)
    if n < 3:
        verdict = L("样本窗口不足", "Not enough windows")
    elif consec >= CONSECUTIVE_PASS:
        verdict = "PASS"
    elif n_pass >= n * 0.5:
        verdict = "WARN"
    else:
        verdict = "FAIL"
    return {
        "oos_days": oos_days,
        "step_days": step_days,
        "n_windows": n,
        "n_pass": n_pass,
        "max_consecutive": consec,
        "consecutive_required": CONSECUTIVE_PASS,
        "verdict": verdict,
        "windows": windows,
    }


def _max_consecutive(flags: list[bool]) -> int:
    best = cur = 0
    for flag in flags:
        cur = cur + 1 if flag else 0
        best = max(best, cur)
    return best


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    lo, hi = -8.0, 8.0
    for _ in range(64):
        mid = (lo + hi) / 2.0
        if _norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0

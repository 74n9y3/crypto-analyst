"""回测 K 线自检。

加密货币 7×24 连续交易，按周期步长查缺口，不按外汇的周末日历。
缺口和非法 OHLC 会让 ``ok`` 为假；单根大波动只记入警告，不当作数据错误。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from analyst.data.fetcher import Candle

TF_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1d": 86400,
    "1w": 604800,
}

# 缺 bar 占「实有 + 缺失」的比例超过这个值，自检不通过
_MISSING_FAIL = 0.02


@dataclass
class DataCheck:
    ok: bool
    bars: int
    step_sec: int
    missing_bars: int
    gap_events: int
    duplicate_ts: int
    invalid_ohlc: int
    jump_bars: int
    coverage_days: float
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "bars": self.bars,
            "step_sec": self.step_sec,
            "missing_bars": self.missing_bars,
            "gap_events": self.gap_events,
            "duplicate_ts": self.duplicate_ts,
            "invalid_ohlc": self.invalid_ohlc,
            "jump_bars": self.jump_bars,
            "coverage_days": round(self.coverage_days, 2),
            "warnings": list(self.warnings),
        }


def check_candles(candles: list[Candle], timeframe: str) -> DataCheck:
    """检查连续性、重复时间戳、OHLC 合法性，并统计异常跳变。"""
    step = TF_SECONDS.get(timeframe, 0)
    warnings: list[str] = []
    n = len(candles)
    if n == 0:
        return DataCheck(
            ok=False, bars=0, step_sec=step, missing_bars=0, gap_events=0,
            duplicate_ts=0, invalid_ohlc=0, jump_bars=0, coverage_days=0.0,
            warnings=["没有 K 线"],
        )
    if step <= 0:
        warnings.append(f"未知周期 {timeframe}，跳过缺 bar 计数")

    missing = 0
    gaps = 0
    dup = 0
    invalid = 0
    jumps = 0
    jump_limit = 0.30 if step >= 86400 else 0.15

    prev = candles[0]
    if not _ohlc_ok(prev):
        invalid += 1
    for cur in candles[1:]:
        if not _ohlc_ok(cur):
            invalid += 1
        delta = (cur.timestamp - prev.timestamp).total_seconds()
        if delta == 0:
            dup += 1
        elif step > 0 and delta > step * 1.5:
            miss = int(round(delta / step)) - 1
            if miss > 0:
                missing += miss
                gaps += 1
        if prev.close > 0:
            ret = abs(cur.close / prev.close - 1.0)
            if ret > jump_limit:
                jumps += 1
        prev = cur

    span = (candles[-1].timestamp - candles[0].timestamp).total_seconds()
    coverage_days = span / 86400.0
    denom = n + missing
    missing_ratio = missing / denom if denom else 0.0

    if missing_ratio > _MISSING_FAIL:
        warnings.append(f"缺 bar {missing} 根（{missing_ratio:.1%}），超过 {_MISSING_FAIL:.0%}")
    if dup:
        warnings.append(f"重复时间戳 {dup} 根")
    if invalid:
        warnings.append(f"非法 OHLC {invalid} 根")
    if jumps:
        warnings.append(f"单根涨跌超过 {jump_limit:.0%} 的有 {jumps} 根（可能是真实行情）")

    ok = missing_ratio <= _MISSING_FAIL and dup == 0 and invalid == 0 and n >= 2
    return DataCheck(
        ok=ok,
        bars=n,
        step_sec=step,
        missing_bars=missing,
        gap_events=gaps,
        duplicate_ts=dup,
        invalid_ohlc=invalid,
        jump_bars=jumps,
        coverage_days=coverage_days,
        warnings=warnings,
    )


def _ohlc_ok(c: Candle) -> bool:
    vals = (c.open, c.high, c.low, c.close, c.volume)
    if not all(math.isfinite(v) for v in vals):
        return False
    if c.high < c.low:
        return False
    if c.high + 1e-12 < max(c.open, c.close):
        return False
    if c.low - 1e-12 > min(c.open, c.close):
        return False
    return True

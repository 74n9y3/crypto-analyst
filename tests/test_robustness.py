"""滚动样本外、成本、DSR、PBO、K 线自检与落库。"""

import math
from datetime import datetime, timedelta

from analyst.backtest.classic import CostModel, simulate
from analyst.backtest.robustness import (
    cost_sensitivity,
    cscv_pbo,
    deflated_sharpe,
    walk_forward,
)
from analyst.data.bar_store import load_candles, record_history, upsert_candles
from analyst.data.fetcher import Candle
from analyst.data.quality import check_candles


def _bar(i: int, close: float, *, high: float | None = None, low: float | None = None) -> Candle:
    return Candle(
        timestamp=datetime(2024, 1, 1) + timedelta(hours=4 * i),
        open=close,
        high=high if high is not None else close + 1,
        low=low if low is not None else close - 1,
        close=close,
        volume=1,
    )


def _trend(n: int, start: float, step: float) -> list[Candle]:
    out = []
    px = start
    for i in range(n):
        out.append(_bar(i, px + step))
        px += step
    return out


def test_half_spread_is_part_of_one_way_cost():
    plain = CostModel(fee_pct=0.05, slippage_pct=0.02, spread_pct=0.0)
    wide = CostModel(fee_pct=0.05, slippage_pct=0.02, spread_pct=0.04)
    assert math.isclose(wide.one_way - plain.one_way, 0.0002, rel_tol=0, abs_tol=1e-12)


def test_vol_slip_costs_more_when_range_is_wide():
    candles = [_bar(i, 100.0, high=120.0, low=80.0) for i in range(40)]
    flip = [1.0 if i % 2 == 0 else -1.0 for i in range(40)]
    base = simulate(
        candles, flip, strategy="x", symbol="T", timeframe="4h",
        cost=CostModel(fee_pct=0.0, slippage_pct=0.0, vol_slip_atr_frac=0.0),
    )
    scaled = simulate(
        candles, flip, strategy="x", symbol="T", timeframe="4h",
        cost=CostModel(fee_pct=0.0, slippage_pct=0.0, vol_slip_atr_frac=0.5),
    )
    assert scaled.total_return_pct < base.total_return_pct


def test_cost_sensitivity_shrinks_return():
    candles = _trend(80, 100.0, 0.4)
    flip = [1.0 if i % 2 == 0 else 0.0 for i in range(80)]
    rows = cost_sensitivity(
        candles, flip, strategy="x", symbol="T", timeframe="4h",
        cost=CostModel(fee_pct=0.05, slippage_pct=0.02, spread_pct=0.02),
    )
    assert [row["scale"] for row in rows] == [1.0, 1.5, 2.0]
    assert rows[2]["total_return_pct"] < rows[0]["total_return_pct"]


def test_walk_forward_passes_on_uptrend_and_fails_on_downtrend():
    up = _trend(1200, 100.0, 1.0)
    down = _trend(1200, 5000.0, -1.0)
    long = [1.0] * 1200
    passed = walk_forward(
        up, long, strategy="buy_hold", symbol="T", timeframe="4h",
        cost=CostModel(fee_pct=0, slippage_pct=0), oos_days=20, step_days=10,
    )
    failed = walk_forward(
        down, long, strategy="buy_hold", symbol="T", timeframe="4h",
        cost=CostModel(fee_pct=0, slippage_pct=0), oos_days=20, step_days=10,
    )
    assert passed["n_windows"] >= 6
    assert passed["max_consecutive"] >= 6
    assert passed["verdict"] == "PASS"
    assert failed["n_pass"] == 0
    assert failed["verdict"] == "FAIL"


def test_dsr_falls_as_trial_count_grows():
    # 每根夏普约 0.12：单次试验过线，候选数极大时被多重检验门槛压下去
    returns = [0.0112 if i % 2 == 0 else -0.0088 for i in range(400)]
    few = deflated_sharpe(returns, 1, periods_per_year=365)
    many = deflated_sharpe(returns, 10**12, periods_per_year=365)
    assert few["dsr_prob"] > 0.95
    assert many["dsr_prob"] < 0.5


def test_pbo_is_zero_when_candidates_match_and_higher_when_they_flip():
    length = 80
    flat = [0.01] * length
    same = cscv_pbo([flat, list(flat)], n_splits=4)
    flipped_a = ([0.01] * 20 + [-0.02] * 20) * 2
    flipped_b = ([-0.01] * 20 + [0.02] * 20) * 2
    flip = cscv_pbo([flipped_a, flipped_b], n_splits=4)
    assert same["pbo"] == 0.0
    assert flip["pbo"] > same["pbo"]


def test_missing_bars_fail_the_check():
    candles = [_bar(i, 100 + i * 0.1) for i in range(100) if not 40 <= i < 50]
    report = check_candles(candles, "4h")
    assert report.missing_bars >= 9
    assert report.ok is False
    assert any("缺 bar" in note for note in report.warnings)


def test_bar_store_upserts_without_duplicating(tmp_path):
    db = tmp_path / "ohlcv.sqlite"
    candles = [_bar(i, 100 + i) for i in range(5)]
    upsert_candles(candles, symbol="BTC/USDT", timeframe="4h", market="futures", db_path=db)
    changed = [_bar(0, 999)] + candles[1:]
    upsert_candles(changed, symbol="BTC/USDT", timeframe="4h", market="futures", db_path=db)
    loaded = load_candles(symbol="BTC/USDT", timeframe="4h", market="futures", db_path=db)
    assert len(loaded) == 5
    assert loaded[0].close == 999


def test_record_history_writes_check(tmp_path):
    db = tmp_path / "ohlcv.sqlite"
    candles = [_bar(i, 100 + i) for i in range(30)]
    payload = record_history(
        candles, symbol="ETH/USDT", timeframe="4h", market="futures", db_path=db
    )
    assert payload["ok"] is True
    assert payload["stored_bars"] == 30
    assert payload["missing_bars"] == 0

"""现货雷达规则：筛选池、强度、急涨、突破、放量和均线穿越。"""

from datetime import UTC, datetime

import pytest

from analyst.monitor.spot_radar import (
    Alert,
    Candle,
    CooldownStore,
    RadarConfig,
    format_telegram,
    four_hour_return,
    impulse_return,
    is_leveraged_base,
    is_stable_base,
    ma_cross,
    pair_symbol,
    passes_signal,
    range_break,
    scan,
    select_universe,
    volume_spike,
)


def make_candles(closes, *, highs=None, lows=None, quote_volumes=None, start=0, step=3_600_000):
    candles = []
    for index, close in enumerate(closes):
        candles.append(
            Candle(
                open_time=start + index * step,
                open=closes[index - 1] if index else close,
                high=close if highs is None else highs[index],
                low=close if lows is None else lows[index],
                close=close,
                volume=1,
                close_time=start + (index + 1) * step - 1,
                quote_volume=100 if quote_volumes is None else quote_volumes[index],
            )
        )
    return candles


def test_leveraged_filter_keeps_jup():
    assert is_leveraged_base("BTCUP")
    assert is_leveraged_base("ETHDOWN")
    assert not is_leveraged_base("JUP")
    assert not is_leveraged_base("BTC")


def test_stable_filter_drops_rlusd_not_usual():
    assert is_stable_base("RLUSD")
    assert is_stable_base("USDC")
    assert not is_stable_base("USUAL")
    assert not is_stable_base("BTC")


def test_universe_keeps_liquid_spot_and_majors():
    symbols = [
        {"symbol": "BTCUSDT", "status": "TRADING", "quoteAsset": "USDT", "baseAsset": "BTC", "isSpotTradingAllowed": True},
        {"symbol": "ETHUSDT", "status": "TRADING", "quoteAsset": "USDT", "baseAsset": "ETH", "isSpotTradingAllowed": True},
        {"symbol": "SOLUSDT", "status": "TRADING", "quoteAsset": "USDT", "baseAsset": "SOL", "isSpotTradingAllowed": True},
        {"symbol": "USDCUSDT", "status": "TRADING", "quoteAsset": "USDT", "baseAsset": "USDC", "isSpotTradingAllowed": True},
        {"symbol": "BTCUPUSDT", "status": "TRADING", "quoteAsset": "USDT", "baseAsset": "BTCUP", "isSpotTradingAllowed": True},
        {"symbol": "TINYUSDT", "status": "TRADING", "quoteAsset": "USDT", "baseAsset": "TINY", "isSpotTradingAllowed": True},
    ]
    tickers = [
        {"symbol": "BTCUSDT", "lastPrice": "100", "quoteVolume": "50000000", "priceChangePercent": "1"},
        {"symbol": "ETHUSDT", "lastPrice": "10", "quoteVolume": "40000000", "priceChangePercent": "2"},
        {"symbol": "SOLUSDT", "lastPrice": "1", "quoteVolume": "30000000", "priceChangePercent": "3"},
        {"symbol": "USDCUSDT", "lastPrice": "1", "quoteVolume": "90000000", "priceChangePercent": "0"},
        {"symbol": "BTCUPUSDT", "lastPrice": "1", "quoteVolume": "80000000", "priceChangePercent": "4"},
        {"symbol": "TINYUSDT", "lastPrice": "1", "quoteVolume": "1000", "priceChangePercent": "9"},
    ]
    watch, core = select_universe(
        symbols,
        tickers,
        quote_asset="USDT",
        top_n=2,
        min_quote_volume=10_000_000,
        majors=["BTCUSDT", "ETHUSDT"],
    )
    assert core == ["BTCUSDT", "ETHUSDT"]
    assert [item[0] for item in watch] == ["BTCUSDT", "ETHUSDT"]


def test_four_hour_return_and_signal():
    candles = make_candles([100, 100, 100, 100, 103])
    assert four_hour_return(candles) == pytest.approx(0.03)
    assert passes_signal(rank=2, top_k=5, ret_4h=0.03, min_4h_return=0.02, above_ma=True)
    assert not passes_signal(rank=6, top_k=5, ret_4h=0.03, min_4h_return=0.02, above_ma=True)
    assert not passes_signal(rank=1, top_k=5, ret_4h=0.01, min_4h_return=0.02, above_ma=True)


def test_impulse():
    candles = make_candles([100, 103], step=900_000)
    assert impulse_return(candles) == pytest.approx(0.03)
    assert impulse_return(make_candles([100, 101], step=900_000)) == pytest.approx(0.01)


def test_range_break_uses_closed_range():
    candles = make_candles([100] * 24, highs=[100] * 24, lows=[90] * 24)
    assert range_break(candles, 100.4, min_break=0.003) == ("up", 100)
    assert range_break(candles, 100.1, min_break=0.003) is None
    assert range_break(candles, 89.5, min_break=0.003) == ("down", 90)


def test_volume_spike_needs_same_hour_and_price_move():
    count = 24 * 7 + 1
    closes = [100.0] * count
    closes[-1] = 102
    volumes = [100.0] * count
    volumes[-1] = 500
    candles = make_candles(closes, quote_volumes=volumes)
    hour = datetime.fromtimestamp(candles[-1].open_time / 1000, tz=UTC).hour
    assert hour == 0
    ratio, change = volume_spike(candles, multiple=2, min_abs_return=0.01)
    assert ratio >= 2
    assert change == pytest.approx(0.02)
    flat = make_candles([100.0] * count, quote_volumes=volumes)
    assert volume_spike(flat, multiple=2, min_abs_return=0.01) is None


def test_ma_cross_only_on_the_cross_bar():
    up = make_candles([100.0] * 60 + [110.0])
    assert ma_cross(up, 20, 60) == "up"
    still_up = make_candles([100.0] * 59 + [110.0, 111.0])
    assert ma_cross(still_up, 20, 60) is None
    down = make_candles([100.0] * 60 + [90.0])
    assert ma_cross(down, 20, 60) == "down"


def test_daily_brief_uses_last_closed_day_and_morning_window():
    from datetime import timedelta

    from analyst.monitor.spot_radar import daily_level_row, format_brief_text, in_brief_window

    day = make_candles([100, 110], highs=[101, 112], lows=[99, 108], step=86_400_000)
    row = daily_level_row("BTCUSDT", day)
    assert row is not None
    assert row["high"] == 112
    assert row["low"] == 108
    assert row["change"] == pytest.approx(0.1)
    text = format_brief_text("10-21", [row], [{"symbol": "PEPEUSDT", "ret_4h": 0.05}])
    assert "BTC/USDT 昨收" in text
    assert "今天盯住：上破" in text
    assert "PEPE +5.00%" in text
    morning = datetime(2026, 10, 21, 4, 10, tzinfo=UTC)
    assert in_brief_window(morning)
    assert not in_brief_window(morning - timedelta(hours=2))
    assert not in_brief_window(morning + timedelta(hours=13))


def test_pair_symbol_and_telegram_trim():
    assert pair_symbol("BTCUSDT") == "BTC/USDT"
    alerts = [
        {"symbol": f"C{i}USDT", "title": "急涨", "detail": "细节"}
        for i in range(10)
    ]
    text = format_telegram(alerts)
    assert "现货雷达 · 10 条" in text
    assert "另有 2 条" in text


def test_cooldown_blocks_repeat(tmp_path):
    store = CooldownStore(tmp_path / "state.json")
    alert = Alert("BTCUSDT", "impulse_15m", "up", "急涨", "细节", 100)
    config = RadarConfig(cooldown_seconds=3600)
    assert store.allow(alert.cooldown_key(), 1_000, alert.cooldown_seconds(config))
    assert not store.allow(alert.cooldown_key(), 1_500, alert.cooldown_seconds(config))
    assert store.allow(alert.cooldown_key(), 5_000, alert.cooldown_seconds(config))


class _FakeClient:
    def exchange_symbols(self):
        return [
            {"symbol": "BTCUSDT", "status": "TRADING", "quoteAsset": "USDT", "baseAsset": "BTC"},
            {"symbol": "ETHUSDT", "status": "TRADING", "quoteAsset": "USDT", "baseAsset": "ETH"},
        ]

    def ticker_24h(self):
        return [
            {"symbol": "BTCUSDT", "lastPrice": "104", "quoteVolume": "50000000", "priceChangePercent": "3"},
            {"symbol": "ETHUSDT", "lastPrice": "10", "quoteVolume": "40000000", "priceChangePercent": "0.2"},
        ]

    def klines(self, symbol, interval, limit):
        if interval == "15m":
            return make_candles([100, 100], step=900_000)
        closes = [100.0] * 29 + [103.0]
        return make_candles(closes, highs=[110.0] * 30, lows=[90.0] * 30)


def test_scan_emits_spot_signal_for_leader():
    alerts, board, meta = scan(RadarConfig(top_n=2, sma_fast=20), _FakeClient(), now_ms=10**15)
    assert meta["watched"] == 2
    assert any(alert.rule == "spot_signal" and alert.symbol == "BTCUSDT" for alert in alerts)
    assert board[0]["symbol"] == "BTCUSDT"
    assert board[0]["signal"] is True

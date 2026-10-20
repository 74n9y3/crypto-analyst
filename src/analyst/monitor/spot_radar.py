"""现货雷达：只读币安公开行情，命中后写入页面并推 Telegram。不下单。"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from analyst.config import Settings, get_settings

logger = logging.getLogger("analyst.monitor.spot_radar")
DUBAI = ZoneInfo("Asia/Dubai")

RULE_SIGNAL = "spot_signal"
RULE_IMPULSE = "impulse_15m"
RULE_RANGE = "range_break"
RULE_VOLUME = "volume_spike"
RULE_MA = "ma_cross"

STABLE_BASES = {
    "USDC",
    "FDUSD",
    "TUSD",
    "USDP",
    "DAI",
    "EUR",
    "AEUR",
    "EURI",
    "USD1",
    "USDE",
}

_scan_lock = threading.Lock()
_memory_lock = threading.Lock()
_memory: dict[str, Any] = {}


class MarketDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_volume: float


@dataclass
class RadarConfig:
    base_url: str = "https://data-api.binance.vision"
    quote_asset: str = "USDT"
    top_n: int = 30
    min_quote_volume_usdt: float = 10_000_000
    interval_seconds: int = 900
    cooldown_seconds: int = 3600
    signal_cooldown_seconds: int = 14400
    majors: tuple[str, ...] = ("BTCUSDT", "ETHUSDT")
    impulse_pct: float = 2.0
    major_impulse_pct: float = 1.2
    volume_spike_multiple: float = 2.0
    volume_spike_min_abs_pct: float = 1.0
    signal_top_k: int = 5
    signal_min_4h_pct: float = 2.0
    range_break_min_pct: float = 0.3
    sma_fast: int = 20
    sma_slow: int = 60
    telegram: bool = True
    enabled: bool = True

    @classmethod
    def from_settings(cls, settings: Settings) -> RadarConfig:
        majors = tuple(
            item.strip().upper()
            for item in (settings.spot_radar_majors or "").split(",")
            if item.strip()
        ) or ("BTCUSDT", "ETHUSDT")
        return cls(
            base_url=settings.spot_radar_base_url,
            top_n=settings.spot_radar_top_n,
            min_quote_volume_usdt=settings.spot_radar_min_quote_volume,
            interval_seconds=settings.spot_radar_interval_seconds,
            cooldown_seconds=settings.spot_radar_cooldown_seconds,
            signal_cooldown_seconds=settings.spot_radar_signal_cooldown_seconds,
            majors=majors,
            impulse_pct=settings.spot_radar_impulse_pct,
            major_impulse_pct=settings.spot_radar_major_impulse_pct,
            volume_spike_multiple=settings.spot_radar_volume_multiple,
            volume_spike_min_abs_pct=settings.spot_radar_volume_min_abs_pct,
            signal_top_k=settings.spot_radar_signal_top_k,
            signal_min_4h_pct=settings.spot_radar_signal_min_4h_pct,
            range_break_min_pct=settings.spot_radar_range_break_min_pct,
            sma_fast=settings.spot_radar_sma_fast,
            sma_slow=settings.spot_radar_sma_slow,
            telegram=settings.spot_radar_telegram,
            enabled=settings.spot_radar_enabled,
        )


@dataclass
class Alert:
    symbol: str
    rule: str
    direction: str
    title: str
    detail: str
    price: float

    def cooldown_key(self) -> str:
        return f"{self.symbol}|{self.rule}|{self.direction}"

    def cooldown_seconds(self, config: RadarConfig) -> int:
        if self.rule == RULE_SIGNAL:
            return config.signal_cooldown_seconds
        return config.cooldown_seconds

    def as_dict(self, stamp: str) -> dict[str, Any]:
        return {
            "time": stamp,
            "symbol": self.symbol,
            "pair": pair_symbol(self.symbol),
            "rule": self.rule,
            "direction": self.direction,
            "title": self.title,
            "detail": self.detail,
            "price": self.price,
            "timeframe": "15m" if self.rule == RULE_IMPULSE else "1h",
        }


def pair_symbol(symbol: str) -> str:
    raw = symbol.upper().replace("-", "").replace("/", "")
    if raw.endswith("USDT") and len(raw) > 4:
        return f"{raw[:-4]}/USDT"
    return symbol


def is_stable_base(base: str) -> bool:
    if base in STABLE_BASES:
        return True
    return base.endswith("USD")


def is_leveraged_base(base: str) -> bool:
    """币安杠杆代币一般是 BTCUP / ETHDOWN 这种，保留 JUP 这类短名称。"""
    for suffix in ("UP", "DOWN", "BULL", "BEAR"):
        if base.endswith(suffix) and len(base) > len(suffix) + 2:
            return True
    return False


def select_universe(
    symbols: list[dict],
    tickers: list[dict],
    *,
    quote_asset: str,
    top_n: int,
    min_quote_volume: float,
    majors: list[str] | tuple[str, ...],
) -> tuple[list[tuple[str, float, float, float]], list[str]]:
    """返回 (观察列表, 参与信号排名的交易对)。"""
    allowed: set[str] = set()
    for info in symbols:
        if info.get("status") != "TRADING":
            continue
        if info.get("quoteAsset") != quote_asset:
            continue
        if not info.get("isSpotTradingAllowed", True):
            continue
        base = str(info.get("baseAsset") or "")
        symbol = str(info.get("symbol") or "")
        if not symbol or is_stable_base(base) or is_leveraged_base(base):
            continue
        allowed.add(symbol)

    rows: list[tuple[str, float, float, float]] = []
    for ticker in tickers:
        symbol = str(ticker.get("symbol") or "")
        if symbol not in allowed:
            continue
        try:
            last_price = float(ticker["lastPrice"])
            quote_volume = float(ticker["quoteVolume"])
            change_pct = float(ticker.get("priceChangePercent") or 0.0)
        except (KeyError, TypeError, ValueError):
            continue
        if last_price <= 0 or quote_volume < min_quote_volume:
            continue
        rows.append((symbol, last_price, quote_volume, change_pct))
    rows.sort(key=lambda item: item[2], reverse=True)
    core = rows[:top_n]
    core_symbols = [item[0] for item in core]
    seen = set(core_symbols)
    by_symbol = {item[0]: item for item in rows}
    watch = list(core)
    for major in majors:
        if major in seen or major not in by_symbol:
            continue
        watch.append(by_symbol[major])
    return watch, core_symbols


def closed_candles(candles: list[Candle], now_ms: int) -> list[Candle]:
    return [candle for candle in candles if candle.close_time < now_ms and candle.close > 0]


def sma(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    window = values[-period:]
    return sum(window) / period


def four_hour_return(candles: list[Candle]) -> float | None:
    if len(candles) < 5 or candles[-5].close <= 0:
        return None
    return candles[-1].close / candles[-5].close - 1


def above_sma(candles: list[Candle], period: int) -> tuple[bool, float | None]:
    closes = [candle.close for candle in candles]
    average = sma(closes, period)
    if average is None:
        return False, None
    return closes[-1] > average, average


def passes_signal(
    *,
    rank: int | None,
    top_k: int,
    ret_4h: float | None,
    min_4h_return: float,
    above_ma: bool,
) -> bool:
    if rank is None or ret_4h is None:
        return False
    return rank <= top_k and ret_4h >= min_4h_return and above_ma


def impulse_return(candles: list[Candle]) -> float | None:
    if len(candles) < 2 or candles[-2].close <= 0:
        return None
    return candles[-1].close / candles[-2].close - 1


def range_break(
    candles: list[Candle],
    last_price: float,
    *,
    min_break: float,
) -> tuple[str, float] | None:
    """最新价突破最近 24 根已收盘小时线的高点或低点。"""
    if len(candles) < 24 or last_price <= 0:
        return None
    window = candles[-24:]
    high = max(candle.high for candle in window)
    low = min(candle.low for candle in window)
    if high > 0 and last_price > high * (1 + min_break):
        return "up", high
    if low > 0 and last_price < low * (1 - min_break):
        return "down", low
    return None


def volume_spike(
    candles: list[Candle],
    *,
    multiple: float,
    min_abs_return: float,
) -> tuple[float, float] | None:
    """最近一根已收盘小时线，对比过去同一 UTC 小时的均量。"""
    if len(candles) < 24 * 4:
        return None
    previous_close = candles[-2].close
    last = candles[-1]
    if previous_close <= 0:
        return None
    change = last.close / previous_close - 1
    if abs(change) < min_abs_return:
        return None
    hour = datetime.fromtimestamp(last.open_time / 1000, tz=UTC).hour
    samples = [
        candle.quote_volume
        for candle in candles[:-1]
        if datetime.fromtimestamp(candle.open_time / 1000, tz=UTC).hour == hour
        and candle.quote_volume > 0
    ][-7:]
    if len(samples) < 4:
        return None
    average = sum(samples) / len(samples)
    if average <= 0:
        return None
    ratio = last.quote_volume / average
    if ratio < multiple:
        return None
    return ratio, change


def ma_cross(candles: list[Candle], fast: int, slow: int) -> str | None:
    """只在刚穿过快均线、并且站在慢均线同一侧时提醒一次。"""
    closes = [candle.close for candle in candles]
    if len(closes) < slow + 1:
        return None
    previous_fast = sma(closes[:-1], fast)
    previous_slow = sma(closes[:-1], slow)
    current_fast = sma(closes, fast)
    current_slow = sma(closes, slow)
    if None in (previous_fast, previous_slow, current_fast, current_slow):
        return None
    previous_close = closes[-2]
    current_close = closes[-1]
    assert previous_fast is not None and current_fast is not None
    assert previous_slow is not None and current_slow is not None
    if (
        previous_close <= previous_fast
        and current_close > current_fast
        and current_close > current_slow
    ):
        return "up"
    if (
        previous_close >= previous_fast
        and current_close < current_fast
        and current_close < current_slow
    ):
        return "down"
    return None


class MarketClient:
    def __init__(self, base_url: str, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def exchange_symbols(self) -> list[dict]:
        payload = self._get("/api/v3/exchangeInfo")
        symbols = payload.get("symbols")
        if not isinstance(symbols, list):
            raise MarketDataError("交易对列表格式异常")
        return symbols

    def ticker_24h(self) -> list[dict]:
        payload = self._get("/api/v3/ticker/24hr")
        if not isinstance(payload, list):
            raise MarketDataError("24小时行情格式异常")
        return payload

    def klines(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        payload = self._get(
            "/api/v3/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )
        if not isinstance(payload, list):
            raise MarketDataError(f"{symbol} K线格式异常")
        candles: list[Candle] = []
        for row in payload:
            if not isinstance(row, list) or len(row) < 8:
                continue
            candles.append(
                Candle(
                    open_time=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    close_time=int(row[6]),
                    quote_volume=float(row[7]),
                )
            )
        return candles

    def _get(self, path: str, params: dict | None = None):
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "crypto-analyst/spot-radar"})
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode())
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code in (418, 429, 500, 503) and attempt < 3:
                    time.sleep(1.2 * (attempt + 1))
                    continue
                raise MarketDataError(f"行情请求失败: HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(1.2 * (attempt + 1))
                    continue
                raise MarketDataError(f"行情请求失败: {exc}") from exc
            if isinstance(payload, dict) and "code" in payload and "msg" in payload:
                raise MarketDataError(f"{payload['code']} {payload['msg']}")
            return payload
        raise MarketDataError(f"行情请求失败: {last_error}")


class CooldownStore:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, float] = {}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                loaded = None
            if isinstance(loaded, dict):
                self.data = {str(key): float(value) for key, value in loaded.items()}

    def allow(self, key: str, now: float, cooldown: int) -> bool:
        previous = self.data.get(key)
        if previous is not None and now - previous < cooldown:
            return False
        self.data[key] = now
        return True

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def format_price(price: float) -> str:
    if price >= 1000:
        return f"{price:,.2f}"
    if price >= 1:
        return f"{price:,.4f}"
    if price >= 0.01:
        return f"{price:.4f}"
    if price >= 0.0001:
        return f"{price:.6f}"
    return f"{price:.8f}"


def format_usdt(amount: float) -> str:
    if amount >= 1e8:
        return f"{amount / 1e8:.2f} 亿"
    if amount >= 1e4:
        return f"{amount / 1e4:.0f} 万"
    return f"{amount:.0f}"


def _paths() -> tuple[Path, Path]:
    root = get_settings().cache_path
    return root / "spot_radar_state.json", root / "spot_radar_snapshot.json"


def _stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _empty_snapshot(config: RadarConfig | None = None) -> dict[str, Any]:
    cfg = config or RadarConfig.from_settings(get_settings())
    return {
        "enabled": cfg.enabled,
        "ok": True,
        "error": None,
        "scanned_at": None,
        "watched": 0,
        "skipped": [],
        "leaderboard": [],
        "round_alerts": [],
        "fresh_alerts": [],
        "recent_alerts": [],
        "daily_brief": None,
        "interval_seconds": cfg.interval_seconds,
        "thresholds": {
            "top_n": cfg.top_n,
            "min_quote_volume_usdt": cfg.min_quote_volume_usdt,
            "impulse_pct": cfg.impulse_pct,
            "major_impulse_pct": cfg.major_impulse_pct,
            "signal_top_k": cfg.signal_top_k,
            "signal_min_4h_pct": cfg.signal_min_4h_pct,
            "range_break_min_pct": cfg.range_break_min_pct,
            "volume_spike_multiple": cfg.volume_spike_multiple,
        },
    }


def current_snapshot() -> dict[str, Any]:
    with _memory_lock:
        if _memory:
            return json.loads(json.dumps(_memory))
    _state, snap_path = _paths()
    if snap_path.is_file():
        try:
            loaded = json.loads(snap_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                with _memory_lock:
                    _memory.update(loaded)
                return loaded
        except (OSError, json.JSONDecodeError):
            logger.warning("spot radar snapshot unreadable", exc_info=True)
    try:
        return _empty_snapshot()
    except Exception:
        return {
            "enabled": False,
            "ok": False,
            "error": None,
            "scanned_at": None,
            "watched": 0,
            "skipped": [],
            "leaderboard": [],
            "round_alerts": [],
            "fresh_alerts": [],
            "recent_alerts": [],
            "daily_brief": None,
            "interval_seconds": 900,
            "thresholds": {},
        }


def _store_snapshot(snapshot: dict[str, Any]) -> None:
    _state, snap_path = _paths()
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with _memory_lock:
        _memory.clear()
        _memory.update(snapshot)


def _load_rows(
    client: MarketClient,
    watch: list[tuple[str, float, float, float]],
    now_ms: int,
) -> tuple[list[tuple], list[str]]:
    def load(item: tuple[str, float, float, float]):
        symbol, last_price, quote_volume, change_pct = item
        hourly = closed_candles(client.klines(symbol, "1h", 170), now_ms)
        quarter = closed_candles(client.klines(symbol, "15m", 4), now_ms)
        return symbol, last_price, quote_volume, change_pct, hourly, quarter

    rows = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(load, item): item[0] for item in watch}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                rows.append(future.result())
            except MarketDataError as exc:
                errors.append(f"{symbol}: {exc}")
    return rows, errors


def scan(
    config: RadarConfig,
    client: MarketClient,
    *,
    now_ms: int | None = None,
) -> tuple[list[Alert], list[dict[str, Any]], dict[str, Any]]:
    moment = int(time.time() * 1000) if now_ms is None else now_ms
    symbols = client.exchange_symbols()
    tickers = client.ticker_24h()
    majors = list(config.majors)
    watch, core_symbols = select_universe(
        symbols,
        tickers,
        quote_asset=config.quote_asset,
        top_n=config.top_n,
        min_quote_volume=config.min_quote_volume_usdt,
        majors=majors,
    )
    if not watch:
        raise MarketDataError("没有筛出符合成交额条件的现货交易对")

    loaded, errors = _load_rows(client, watch, moment)
    if not loaded:
        raise MarketDataError("K线全部读取失败")

    books = []
    for symbol, last_price, quote_volume, change_pct, hourly, quarter in loaded:
        ret_4h = four_hour_return(hourly)
        _above, average = above_sma(hourly, config.sma_fast)
        is_above = average is not None and last_price > average
        books.append(
            {
                "symbol": symbol,
                "last_price": last_price,
                "quote_volume": quote_volume,
                "change_pct": change_pct,
                "hourly": hourly,
                "quarter": quarter,
                "ret_4h": ret_4h,
                "above_ma": is_above,
                "sma20": average,
                "in_core": symbol in core_symbols,
            }
        )

    ranked = [item for item in books if item["in_core"] and item["ret_4h"] is not None]
    ranked.sort(key=lambda item: item["ret_4h"], reverse=True)
    ranks = {item["symbol"]: index + 1 for index, item in enumerate(ranked)}
    major_set = set(majors)
    min_4h = config.signal_min_4h_pct / 100
    range_buffer = config.range_break_min_pct / 100
    volume_move = config.volume_spike_min_abs_pct / 100
    alerts: list[Alert] = []

    for item in books:
        symbol = item["symbol"]
        price = item["last_price"]
        rank = ranks.get(symbol)
        if passes_signal(
            rank=rank,
            top_k=config.signal_top_k,
            ret_4h=item["ret_4h"],
            min_4h_return=min_4h,
            above_ma=item["above_ma"],
        ):
            alerts.append(
                Alert(
                    symbol=symbol,
                    rule=RULE_SIGNAL,
                    direction="up",
                    title="现货信号",
                    detail=(
                        f"4小时 {item['ret_4h']:+.2%}，成交额前{config.top_n}里第{rank}，"
                        f"现价 {format_price(price)} 高于{config.sma_fast}小时均线 "
                        f"{format_price(item['sma20'] or 0)}，"
                        f"24小时成交额 {format_usdt(item['quote_volume'])} USDT"
                    ),
                    price=price,
                )
            )

        move = impulse_return(item["quarter"])
        threshold = (
            config.major_impulse_pct if symbol in major_set else config.impulse_pct
        ) / 100
        if move is not None and abs(move) >= threshold:
            direction = "up" if move > 0 else "down"
            alerts.append(
                Alert(
                    symbol=symbol,
                    rule=RULE_IMPULSE,
                    direction=direction,
                    title="急涨" if direction == "up" else "急跌",
                    detail=f"最近一根已收盘15分钟K线 {move:+.2%}，现价 {format_price(price)}",
                    price=price,
                )
            )

        broken = range_break(item["hourly"], price, min_break=range_buffer)
        if broken is not None:
            direction, level = broken
            alerts.append(
                Alert(
                    symbol=symbol,
                    rule=RULE_RANGE,
                    direction=direction,
                    title="突破24小时高点" if direction == "up" else "跌破24小时低点",
                    detail=(
                        f"现价 {format_price(price)}，前24根小时线"
                        f"{'高点' if direction == 'up' else '低点'} {format_price(level)}"
                    ),
                    price=price,
                )
            )

        spiked = volume_spike(
            item["hourly"],
            multiple=config.volume_spike_multiple,
            min_abs_return=volume_move,
        )
        if spiked is not None:
            ratio, change = spiked
            direction = "up" if change > 0 else "down"
            alerts.append(
                Alert(
                    symbol=symbol,
                    rule=RULE_VOLUME,
                    direction=direction,
                    title="放量上涨" if direction == "up" else "放量下跌",
                    detail=(
                        f"上一小时成交额是近7个同一UTC小时均量的 {ratio:.1f} 倍，"
                        f"该小时 {change:+.2%}，现价 {format_price(price)}"
                    ),
                    price=price,
                )
            )

        crossed = ma_cross(item["hourly"], config.sma_fast, config.sma_slow)
        if crossed is not None:
            alerts.append(
                Alert(
                    symbol=symbol,
                    rule=RULE_MA,
                    direction=crossed,
                    title="均线转强" if crossed == "up" else "均线转弱",
                    detail=(
                        f"1小时收盘穿过{config.sma_fast}均线，并且"
                        f"{'站上' if crossed == 'up' else '跌到'}{config.sma_slow}均线"
                        f"{'上方' if crossed == 'up' else '下方'}，现价 {format_price(price)}"
                    ),
                    price=price,
                )
            )

    leaderboard = []
    for item in ranked[:8]:
        leaderboard.append(
            {
                "rank": ranks[item["symbol"]],
                "symbol": item["symbol"],
                "pair": pair_symbol(item["symbol"]),
                "price": item["last_price"],
                "ret_4h": item["ret_4h"],
                "change_pct": item["change_pct"],
                "quote_volume": item["quote_volume"],
                "above_ma": item["above_ma"],
                "signal": any(
                    alert.symbol == item["symbol"] and alert.rule == RULE_SIGNAL
                    for alert in alerts
                ),
            }
        )
    meta = {"watched": len(loaded), "skipped": errors}
    return alerts, leaderboard, meta


def take_fresh(alerts: list[Alert], config: RadarConfig, *, now: float | None = None) -> list[Alert]:
    state_path, _snap = _paths()
    store = CooldownStore(state_path)
    moment = time.time() if now is None else now
    fresh = [
        alert
        for alert in alerts
        if store.allow(alert.cooldown_key(), moment, alert.cooldown_seconds(config))
    ]
    store.save()
    return fresh


def format_telegram(alerts: list[dict[str, Any]]) -> str:
    lines = [f"现货雷达 · {len(alerts)} 条"]
    for alert in alerts[:8]:
        lines.append(f"{alert['symbol']} {alert['title']}")
        lines.append(alert["detail"])
    hidden = len(alerts) - 8
    if hidden > 0:
        lines.append(f"另有 {hidden} 条，见页面「现货雷达」")
    return "\n".join(lines)


def in_brief_window(now: datetime) -> bool:
    """迪拜 08:00–08:44。这个窗口里才推 Telegram，避免半夜重启补发。"""
    local = now.astimezone(DUBAI)
    return local.hour == 8 and local.minute < 45


def daily_level_row(symbol: str, candles: list[Candle]) -> dict[str, Any] | None:
    """用最近一根已收盘日线做昨天的高低和涨跌。"""
    if not candles:
        return None
    day = candles[-1]
    if day.open <= 0 or day.high <= 0 or day.low <= 0:
        return None
    return {
        "symbol": symbol,
        "pair": pair_symbol(symbol),
        "open": day.open,
        "high": day.high,
        "low": day.low,
        "close": day.close,
        "change": day.close / day.open - 1,
    }


def format_brief_text(day_label: str, rows: list[dict[str, Any]], leaders: list[dict[str, Any]]) -> str:
    lines = [f"现货简报 · {day_label}"]
    for row in rows:
        lines.append(
            f"{row['pair']} 昨收 {format_price(row['close'])}，日内 {row['change']:+.2%}"
        )
        lines.append(
            f"昨天高点 {format_price(row['high'])}，低点 {format_price(row['low'])}"
        )
        lines.append(
            f"今天盯住：上破 {format_price(row['high'])}，下破 {format_price(row['low'])}"
        )
    bits = []
    for item in leaders[:3]:
        ret = item.get("ret_4h")
        if ret is None:
            continue
        name = str(item.get("symbol") or "").removesuffix("USDT")
        bits.append(f"{name} {ret:+.2%}")
    if bits:
        lines.append("4小时靠前：" + "，".join(bits))
    return "\n".join(lines)


def _brief_path() -> Path:
    return get_settings().cache_path / "spot_radar_brief.json"


def _load_brief_state() -> dict[str, Any]:
    path = _brief_path()
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _save_brief_state(state: dict[str, Any]) -> None:
    path = _brief_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _patch_snapshot_brief(brief: dict[str, Any]) -> None:
    snapshot = current_snapshot()
    snapshot["daily_brief"] = brief
    _store_snapshot(snapshot)


def mark_brief_notified() -> None:
    state = _load_brief_state()
    state["notified"] = True
    _save_brief_state(state)


def refresh_brief(
    config: RadarConfig | None = None,
    client: MarketClient | None = None,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bool] | None:
    """保证今天有一份简报。返回 (简报, 是否该推 Telegram)；已有且不用推时返回 None。"""
    moment = now.astimezone(DUBAI) if now is not None else datetime.now(DUBAI)
    day = moment.date().isoformat()
    state = _load_brief_state()
    existing = state.get("brief") if state.get("date") == day else None
    if isinstance(existing, dict) and existing.get("text"):
        _patch_snapshot_brief(existing)
        if in_brief_window(moment) and not state.get("notified"):
            return existing, True
        return None

    cfg = config or RadarConfig.from_settings(get_settings())
    market = client or MarketClient(cfg.base_url)
    now_ms = int(moment.timestamp() * 1000)
    rows = []
    for symbol in cfg.majors:
        try:
            candles = closed_candles(market.klines(symbol, "1d", 5), now_ms)
        except MarketDataError as exc:
            logger.warning("spot brief skip %s: %s", symbol, exc)
            continue
        row = daily_level_row(symbol, candles)
        if row is not None:
            rows.append(row)
    if not rows:
        return None
    leaders = list(current_snapshot().get("leaderboard") or [])
    brief = {
        "date": day,
        "text": format_brief_text(moment.strftime("%m-%d"), rows, leaders),
        "rows": rows,
    }
    _save_brief_state({"date": day, "notified": False, "brief": brief})
    _patch_snapshot_brief(brief)
    logger.info("spot brief ready %s symbols=%s", day, ",".join(row["symbol"] for row in rows))
    if in_brief_window(moment):
        return brief, True
    return None


def scan_and_store(config: RadarConfig | None = None, client: MarketClient | None = None) -> dict[str, Any]:
    """扫一轮、按冷却去重，并写下页面用的快照。"""
    cfg = config or RadarConfig.from_settings(get_settings())
    with _scan_lock:
        stamp = _stamp()
        previous = current_snapshot()
        try:
            alerts, leaderboard, meta = scan(cfg, client or MarketClient(cfg.base_url))
        except MarketDataError as exc:
            snapshot = previous
            snapshot.update(
                {
                    "enabled": cfg.enabled,
                    "ok": False,
                    "error": str(exc),
                    "scanned_at": stamp,
                    "interval_seconds": cfg.interval_seconds,
                }
            )
            _store_snapshot(snapshot)
            logger.warning("spot radar scan failed: %s", exc)
            return snapshot

        fresh = take_fresh(alerts, cfg)
        fresh_rows = [alert.as_dict(stamp) for alert in fresh]
        recent = list(previous.get("recent_alerts") or [])
        recent.extend(fresh_rows)
        snapshot = _empty_snapshot(cfg)
        snapshot.update(
            {
                "ok": True,
                "error": None,
                "scanned_at": stamp,
                "watched": meta["watched"],
                "skipped": meta["skipped"],
                "leaderboard": leaderboard,
                "round_alerts": [alert.as_dict(stamp) for alert in alerts],
                "fresh_alerts": fresh_rows,
                "recent_alerts": recent[-80:],
                "daily_brief": previous.get("daily_brief"),
            }
        )
        _store_snapshot(snapshot)
        logger.info(
            "spot radar 观察 %d · 命中 %d · 新提醒 %d",
            meta["watched"],
            len(alerts),
            len(fresh_rows),
        )
        return snapshot


async def publish_scan(
    notify: Callable[[str], Awaitable[None]] | None = None,
    publish: Callable[[list[dict[str, Any]]], Awaitable[None]] | None = None,
    *,
    config: RadarConfig | None = None,
) -> dict[str, Any]:
    cfg = config or RadarConfig.from_settings(get_settings())
    snapshot = await asyncio.to_thread(scan_and_store, cfg)
    fresh = list(snapshot.get("fresh_alerts") or [])
    if fresh and cfg.telegram and notify is not None:
        try:
            await notify(format_telegram(fresh))
        except Exception:
            logger.exception("spot radar telegram failed")
    if fresh and publish is not None:
        try:
            await publish(fresh)
        except Exception:
            logger.exception("spot radar page publish failed")
    return snapshot


async def publish_brief(
    notify: Callable[[str], Awaitable[None]] | None = None,
) -> None:
    settings = get_settings()
    if not settings.spot_radar_brief_enabled:
        return
    try:
        result = await asyncio.to_thread(refresh_brief)
    except Exception:
        logger.exception("spot brief failed")
        return
    if not result or notify is None or not settings.spot_radar_telegram:
        return
    brief, should_notify = result
    if not should_notify:
        return
    try:
        await notify(str(brief.get("text") or ""))
    except Exception:
        logger.exception("spot brief telegram failed")
        return
    await asyncio.to_thread(mark_brief_notified)


async def run_spot_radar_loop(
    notify: Callable[[str], Awaitable[None]],
    publish: Callable[[list[dict[str, Any]]], Awaitable[None]],
) -> None:
    """服务启动后常驻扫描。关闭时只睡眠，不打行情。"""
    await asyncio.sleep(20)
    while True:
        try:
            settings = get_settings()
            if not settings.spot_radar_enabled:
                await asyncio.sleep(30)
                continue
            await publish_scan(notify, publish)
            await publish_brief(notify)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("spot radar loop error")
        interval = max(60, int(get_settings().spot_radar_interval_seconds or 900))
        await asyncio.sleep(interval)

"""回测用 K 线的本地库。

写在数据缓存目录的 ``ohlcv.sqlite``，和 AI 会话库分开。
同一根（品种 + 周期 + 市场 + 时间）重复写入会覆盖，不加倍。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from analyst.config import get_settings
from analyst.data.fetcher import Candle
from analyst.data.quality import DataCheck, check_candles

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    market TEXT NOT NULL,
    ts TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    PRIMARY KEY (symbol, timeframe, market, ts)
);
CREATE TABLE IF NOT EXISTS bar_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    market TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    bars INTEGER NOT NULL,
    ok INTEGER NOT NULL,
    report_json TEXT NOT NULL
);
"""


def ohlcv_db_path() -> Path:
    root = Path(get_settings().data_cache_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / "ohlcv.sqlite"


def upsert_candles(
    candles: list[Candle],
    *,
    symbol: str,
    timeframe: str,
    market: str,
    db_path: Path | None = None,
) -> int:
    """写入或覆盖 K 线，返回本次提交的根数。"""
    if not candles:
        return 0
    path = db_path or ohlcv_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        (
            symbol,
            timeframe,
            market,
            c.timestamp.isoformat(),
            c.open,
            c.high,
            c.low,
            c.close,
            c.volume,
        )
        for c in candles
    ]
    with sqlite3.connect(path) as conn:
        conn.executescript(_SCHEMA)
        conn.executemany(
            """
            INSERT INTO bars (symbol, timeframe, market, ts, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, timeframe, market, ts) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def load_candles(
    *,
    symbol: str,
    timeframe: str,
    market: str,
    db_path: Path | None = None,
) -> list[Candle]:
    path = db_path or ohlcv_db_path()
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        conn.executescript(_SCHEMA)
        found = conn.execute(
            """
            SELECT ts, open, high, low, close, volume
            FROM bars
            WHERE symbol=? AND timeframe=? AND market=?
            ORDER BY ts
            """,
            (symbol, timeframe, market),
        ).fetchall()
    out: list[Candle] = []
    for ts, o, h, low, c, v in found:
        out.append(
            Candle(
                timestamp=datetime.fromisoformat(ts),
                open=o,
                high=h,
                low=low,
                close=c,
                volume=v,
            )
        )
    return out


def record_history(
    candles: list[Candle],
    *,
    symbol: str,
    timeframe: str,
    market: str,
    db_path: Path | None = None,
) -> dict:
    """自检、落库、记下这次检查，返回可序列化的报告。"""
    check = check_candles(candles, timeframe)
    stored = upsert_candles(
        candles, symbol=symbol, timeframe=timeframe, market=market, db_path=db_path
    )
    save_check(
        check, symbol=symbol, timeframe=timeframe, market=market, db_path=db_path
    )
    payload = check.to_dict()
    payload["stored_bars"] = stored
    return payload


def save_check(
    check: DataCheck,
    *,
    symbol: str,
    timeframe: str,
    market: str,
    db_path: Path | None = None,
) -> None:
    path = db_path or ohlcv_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(_SCHEMA)
        conn.execute(
            """
            INSERT INTO bar_checks (symbol, timeframe, market, checked_at, bars, ok, report_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                timeframe,
                market,
                datetime.now(UTC).isoformat(),
                check.bars,
                1 if check.ok else 0,
                json.dumps(check.to_dict(), ensure_ascii=False),
            ),
        )
        conn.commit()

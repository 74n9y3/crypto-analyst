# Crypto Analyst

**English** | [中文](README.zh-CN.md)

A locally run crypto market monitor and analysis tool. Data comes from Binance public market feeds (the web UI is fixed to **USDⓈ-M perpetuals**; Spot Radar reads spot separately). Rules are evaluated on candle close or on the mark price, optionally handed to an LLM for commentary, and pushed to the page or Telegram.

**Alerts only, no real orders.** Paper trading matches locally on the mark price to validate the "buy dips in strong markets" plan; it never connects to a trading API.

Top bar: **Monitor** → **Cycle** → **Schedule** → **Spot Radar** → **Strategies** → **Backtest** → **Paper Trading** → **AI Assistant**. On mobile browsers you can "Add to Home Screen" (PWA).

**Interface language:** the UI supports Simplified Chinese and English. The first visit follows the browser language; the `EN` / `中文` button at the top right switches it, and the choice is saved in the browser. Manual AI analysis and follow-up chat answer in the current UI language. Backend-generated text (rule alert details, Telegram pushes, daily digest, news grading, Spot Radar descriptions) is still in Chinese.

<div align="center">
<h3>☕ Buy me a coffee</h3>
<p>This project is free. If it ever helped you watch the market, tips in <strong>USDT</strong> on the matching network are welcome.<br/>
<sub>Send on the network listed below; a mismatched network will not be credited.</sub></p>
<p>
  <img alt="BSC USDT" src="https://img.shields.io/badge/BSC-USDT%20BEP--20-F3BA2F?style=for-the-badge&logo=binance&logoColor=white" />
  <img alt="Solana USDT" src="https://img.shields.io/badge/Solana-USDT-9945FF?style=for-the-badge&logo=solana&logoColor=white" />
  <img alt="Tron USDT" src="https://img.shields.io/badge/Tron-USDT%20TRC--20-FF060A?style=for-the-badge&logo=tron&logoColor=white" />
</p>
</div>

| Network | Address |
|:-----|:---------|
| ![BSC](https://img.shields.io/badge/BSC-F3BA2F?style=flat-square&logo=binance&logoColor=white) **USDT · BEP-20** | `0x6E7359A42C466893E9A835fD6aFdb82E0D1Ed32d` |
| ![Solana](https://img.shields.io/badge/Solana-9945FF?style=flat-square&logo=solana&logoColor=white) **USDT** | `Hm7f6wGdvcmLmbcXV7sdLYGJKBdwGoFrJTZPzeN8dpan` |
| ![Tron](https://img.shields.io/badge/Tron-FF060A?style=flat-square&logo=tron&logoColor=white) **USDT · TRC-20** | `TGNrpZBqD8jnfNCb7B9W93qMmVHycoFsKJ` |

<p align="center">
  <img src="docs/images/web-dashboard.png" alt="Web monitor: candles, key levels and AI analysis" width="900" />
</p>
<p align="center"><em>Monitor page: candles on the left; a single collapsible sidebar on the right with vertical tabs "Key levels" and "AI analysis" (key levels include seed entry / stop / take-profit / support / resistance, with the playbook below support and resistance); alert log and analysis history at the bottom</em></p>

Requires Python **3.11+** and network access to Binance market data.

---

## Features at a glance

| Page | What it does | Extra setup |
|------|--------|----------------|
| **Monitor** | Multi-timeframe candles, rule alerts, key levels, manual AI analysis, price alerts, history at the bottom | Market data is enough for charts; AI needs an LLM key; pushes need Telegram |
| **Cycle** | Wolfy four-year cycle: calendar model, turning-point countdown, Wolfy Wave index, halving timeline | None. Fixed to BTC daily, refreshes about every 5 minutes |
| **Schedule** | Local-time clocks, Asia/Europe/US sessions, funding countdown, high-impact USD macro calendar | `MONITOR_SCHEDULE_*`; macro data from the Forex Factory weekly public JSON |
| **Spot Radar** | Top-volume USDT spot pairs: sudden moves, breakouts, volume spikes, MA crosses, 4h strength board; BTC/ETH brief pushed daily at 08:00 Dubai | `SPOT_RADAR_*` (enabled in the example) |
| **Strategies** | Catalog of `cycle_switch` / `xs_momentum` / `funding_carry`, with jumps to Backtest or Cycle | Evaluated on close only when the always-on monitor is running |
| **Backtest** | Classic portfolio backtest (compounding, costs, walk-forward out-of-sample, cost sensitivity, Deflated Sharpe, PBO) | Pulls historical candles on first run into `ohlcv.sqlite` |
| **Paper Trading** | Limit long at the 0.618 pullback in strong markets, mark-price matching, stop / half take-profit / breakeven / BOLL-mid exit | `PAPER_*` (enabled in the example) |
| **AI Assistant** | Daily digest, research ideas, news risk events | Digest and ideas need an LLM; the news sentinel needs `MONITOR_NEWS_*` |

```
Binance market data
  ├─ Perp WS candles / mark price  →  rule alerts + cycle / xs / carry + Eric
  │                                    ├─ page
  │                                    ├─ qualified candidate → AI review → Telegram
  │                                    ├─ paper matching (local, no orders)
  │                                    └─ optional: Binance Square short post
  ├─ Spot public data              →  Spot Radar → page + Telegram
  ├─ RSS / Binance announcements   →  news sentinel grading → high severity to Telegram
  └─ Manual / CLI analysis         →  analyst.db (plans, verification, chat)
```

Monitor chart timeframes default to **`5m / 15m / 1h / 4h`** (`MONITOR_CHART_TIMEFRAMES`). The always-on evaluation timeframes are set by `MONITOR_DAEMON_TIMEFRAMES` and are independent of the timeframe you switch to on the page.

---

## What's inside the monitor

### Rule alerts (evaluated on close, no LLM)

All enabled by default, and every hit shows on the page. Whether it goes to Telegram is decided by the `MONITOR_TG_TRADE_RULES` allowlist.

| Rule | Meaning |
|------|------|
| `macd_cross` / `ema_stack` / `boll_break` | Trend rules. ADX below `MONITOR_ADX_MIN_TREND` (default 18) is treated as ranging and not reported; `MONITOR_HTF_FILTER` drops signals against the higher-timeframe EMA stack |
| `volume` | Volume spike (default ≥ 2× the 20-bar average volume, with a large enough body) |
| `structure_touch` / `structure_flip` | Support/resistance touched and held, structure flip. Same level has a cooldown in bars |
| `fib_zone` | Fibonacci zone |
| `funding_extreme` / premium | Extreme funding or premium |
| `market_regime` / `playbook_setup` | Three-regime switch and playbook hints (strong / range / weak) |
| `cycle_switch` | Position change per monitored symbol. Page only and can be an AI candidate; not pushed directly to TG |
| `xs_momentum` / `funding_carry` | Cross-sectional momentum rebalances, funding carry signal changes |
| `ratio_shift` | ETH/BTC, BNB/BTC, UNI/BTC strength switches relative to the 200-day EMA |
| `eric_*` | BTC/ETH daily and weekly only (daily/weekly are fetched via REST on 4h close, so 1d/1w need not be chart timeframes) |
| `paper_*` | Paper orders, fills, take-profit, stop-loss, circuit breaker |
| `spot_*` | Spot Radar hits |

### Price alerts (no waiting for candle close)

On the Monitor page you can set mark-price alerts for the current contract: price reaches, cross up only, cross down only, percent change, absolute price change. The time window only applies to the last two (since set, or 1 / 5 / 15 / 60 minutes). Stored in `.cache/data/price_alerts.json`; hits are pushed to the page and Telegram.

### Three regimes and swing levels

Precomputed when creating an analysis and on every monitor candle close, injected into the LLM, and shown in the right-hand "Key levels" panel.

**Three regimes (`market_regime`)**

| Regime | Playbook |
|------|------|
| Strong | Small seed position at market + add on breaking near resistance / yesterday's high, take profit at new highs |
| Range | Buy low / wait for support after a wick; add on pullbacks that hold; take profit at 0.50–0.618 of the daily range |
| Weak | Daily turns bearish: seed short near resistance on bounces + add on support breaks |

Also covers whether the defense level has broken, 12h EMA6, previous day high/low, intraday take-profit, no chasing shorts below the halfway line, and the weekly BOLL mid as the pullback limit. Seed + adds default to no more than about 25% of equity (scaled down with leverage). Disable with `MONITOR_RULE_MARKET_REGIME=false`.

Seed position calculator: `GET /api/tools/seed-position?account=10000&leverage=25&seed_pct=0.04&max_total_pct=0.18&add_mode=pullback`. Implemented in `src/analyst/compute/position_sizing.py`. Kelly (`kelly.py`) handles per-trade risk fraction; the seed module handles the layered structure.

**Swing levels (`swing_levels`)**, written into `market_snapshot` and injected as `{swing_block}`:

| Field | Meaning |
|------|------|
| `rebound_382` / `rebound_618` | Rebound targets after a drop: `Low+(H−L)×0.382/0.618` |
| `daily_bias` | Daily bias: `up` / `down` / `range` |
| `defense_level` | Invalidation level |
| `htf_ready` / `horizon` | Whether the higher timeframe is mature; if not, short-term bounces are suggested |
| `confluence_*` | Whether Fibonacci levels sit near the daily BOLL mid |
| `touch_count` | Recent touches of the key resistance |
| `rs_note` | Relative-strength-vs-BTC summary |

Formulas are computed in code; prompts only add short rules (`prompts/system_v1.md`; the Groq pre-layer uses the shorter `prompts/system_groq.md`).

### Eric swings (BTC / ETH)

`MONITOR_RULE_ERIC`: daily and weekly RSI oversold/overbought + divergence + Buff score; `eric_rebound` / `eric_fade` fire only when the bar is met. BNB/SOL and 4h-and-below backtests show no edge, so they do not produce these signals.

`MONITOR_RULE_ERIC_SWING`: swing plan after a weekly oversold turn (watch, long, half take-profit, remainder, stop). Runs only on `MONITOR_ERIC_SWING_SYMBOLS=BTC/USDT,ETH/USDT` by default. State in `.cache/data/eric_swing_state.json`.

### AI review (cost-controlled)

With `MONITOR_AI_ON_CANDIDATE=true`, the LLM is called only when a qualified candidate appears on close. With `MONITOR_AI_REQUIRE_QUALITY=true`, a single volume or touch hit is not enough: it needs a quality rule, or at least two hits on the same bar.

- Verdict `long` / `short` → page + Telegram "Monitor review" (with stop and take-profit, alerts only)
- `wait` → not pushed
- Same symbol + analysis timeframe has a default 240-minute cooldown (`MONITOR_AI_COOLDOWN_MINUTES`)

With `MONITOR_AI_FREE_ONLY=true` (recommended), **automatic confirmation only uses b.ai and the free tier** and does not fall back to paid DeepSeek / Anthropic; one outage sends only one Telegram message. Manual "Analyze" on the Monitor page and `analyst practice` still use the full chain (free first, then paid on failure).

You can also ask follow-up questions about the current contract on the right (analyze first, then ask, for answers grounded in the chart). Sessions, plans and verifications are written to `analyst.db`. After expiry, use `analyst verify` or review results on the page.

---

## Where alerts go

| Type | Page | Telegram |
|------|------|----------|
| Rule noise (volume, touches, etc., not in the allowlist) | Yes | Not pushed by default |
| Allowlisted rules (MACD, EMA, volume, Bollinger, funding, Eric, paper, Spot Radar, etc.) | Yes | Pushed |
| Close candidate → AI `long`/`short` (`ai_plan`) | Yes | Pushed |
| `cycle_switch` position change | Yes (can trigger AI) | Not pushed directly |
| Daily cycle position `cycle_outlook` (BTC) | Yes | At most 1 per UTC day, not subject to the allowlist |
| Schedule: sessions / funding / macro | "Schedule" page | Pushed ahead of time (`MONITOR_SCHEDULE_TG`) |
| Price alerts | Yes | Pushed |
| AI daily digest | "AI Assistant" | 1 per day at a UTC time |
| News `high` / `critical` | "AI Assistant" | Pushed |
| Spot Radar + daily BTC/ETH brief | "Spot Radar" | `SPOT_RADAR_TELEGRAM` / `SPOT_RADAR_BRIEF_ENABLED` |

An empty allowlist means every rule is pushed to Telegram. See `MONITOR_TG_TRADE_RULES` in [`.env.example`](.env.example) for an example allowlist.

---

## Other modules

### Four-year cycle (Wolfy)

A positional reference based on BTC daily; not an order signal.

- **Calendar model**: anchored to past bear-market bottoms, bull 1064 days and bear 364 days, showing phase progress and the next turning point (highlighted on the page when ≤ 30 days away)
- **Wolfy Wave index**: the [Wolfy Wave Index](https://github.com/tangyiming/wolfy-wave-index) computed from block height (0 = theoretical bear bottom, 1 = theoretical bull top). Interactive chart on the Cycle page; the daily Telegram update includes the current reading. Also see [wolfy-wave-index](https://wolfyxbt.github.io/wolfy-wave-index/)
- **Timeline**: historical bull/bear bands, halving markers, price background

The execution phase of `cycle_switch` is a separate model: halving calendar × 200-day EMA double confirmation. Donchian long-only in bull markets, half-size bounce shorts in bear markets. BTC sets the phase; each coin uses its own candles.

### Spot Radar

Reads only `https://data-api.binance.vision`. Among top-volume USDT spot pairs whose 24h volume clears the threshold, it looks for 15-minute spikes, range breakouts, volume spikes, MA crosses, and 4-hour strength entering the leaders. Stablecoin quote pairs are filtered out. Regular alerts cool down for 1 hour by default, 4-hour strength signals for 4 hours. Every day at 08:00 (`Asia/Dubai`) it writes a BTC/ETH brief: yesterday's high/low, change, and today's levels to watch.

### Paper trading

Evaluates "buy dips in strong markets" on 4h close: places a limit long at the 0.618 pullback (configurable via `PAPER_ENTRY_PREF`) and matches on the live mark price. After a fill the stop moves to breakeven, and the remainder exits per `PAPER_EXIT_RULE` (default: break of the 4h BOLL mid). When intraday drawdown reaches `PAPER_DAILY_FUSE_PCT`, everything is closed and trading pauses until the next day. Equity, risk fraction, leverage cap and concurrent positions are all in `PAPER_*`. The ledger lives in `.cache/data/paper_state.json`.

### AI digest, research ideas, news sentinel

- **Digest** (`MONITOR_DIGEST_ENABLED`): at the scheduled time it aggregates facts already in the system and the LLM only summarizes. Default UTC 05:00 (09:00 Dubai). Falls back to a template when the LLM is unavailable. `analyst digest` / "Generate digest" on the page.
- **Research ideas**: proposes backtestable improvements based on recent conditions. Ideas are not conclusions; already falsified routes are excluded. `analyst research-ideas`.
- **News sentinel**: pulls RSS every `MONITOR_NEWS_INTERVAL_MIN`, plus official Binance announcements (feed name `binance`). The LLM grades them; only those reaching `MONITOR_NEWS_MIN_SEVERITY` (default `high`) are pushed to Telegram.

### Binance Square (optional)

With `SQUARE_POST_ENABLED=true` and `BINANCE_SQUARE_OPENAPI_KEY` configured, monitor triggers can auto-post short notes. Default is a short note + AI polish (trader tone; numbers, `$BTC` tags and the final CTA line are enforced, falling back to a template on failure).

| Trigger | Description | Default cooldown |
|------|------|----------|
| `market_regime` | Regime / direction switch | 2h per symbol and timeframe |
| `playbook_setup` | Golden cross / acceleration / wick setups | 6h |
| `structure_touch` | Support/resistance touched and held | 4h per level |
| Accelerating move | Single 4h candle move beyond threshold or volume spike | 4h per symbol |
| Eric oversold | BTC/ETH daily and weekly | 20h |
| Daily recap | Same UTC time as the digest, or `SQUARE_POST_RECAP_UTC_HOUR` | Once per day |

Images are rendered off-page with Playwright from `chart_capture.html` (candles + levels). Without it, posts automatically fall back to text only:

```bash
uv sync --extra square && playwright install chromium
```

Preview: `analyst square-post`. Test post: `analyst square-post --publish --text '...'`. Keep the key in `.env` only; never commit it.

### Relative strength

`MONITOR_RATIO_ENABLED` tracks `ETH/BTC,BNB/BTC,UNI/BTC` by default, against a long-term EMA (default 200-day) with a hysteresis band, plus N-day new highs/lows. Alerts only.

---

## 5-minute quick start

**1. Install** (from the project root)

```bash
uv sync --extra web
# or: python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[web]"
```

For Square images also run: `uv sync --extra web --extra square && playwright install chromium`.

**2. Configure**

```bash
cp .env.example .env
```

To just view charts and run manual analysis, fill in at least one LLM (the example defaults to DeepSeek):

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-your-key
LLM_MODEL=deepseek-v4-flash
```

To keep monitoring with the page closed and push to Telegram:

```bash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
MONITOR_ALWAYS_ON=true
```

Bot: create one with `@BotFather` in Telegram and fill in the token; add the bot to a chat, then get `TELEGRAM_CHAT_ID` via `@userinfobot` or `getUpdates`.

Initialize and self-check:

```bash
analyst db init
analyst config show          # keys show only the first few characters
analyst config test-llm      # runs a very short analysis to confirm the chain works
```

**3. Start the web UI**

```bash
./scripts/run-web.sh
# equivalent: analyst web
```

Open **http://127.0.0.1:8000**. The script frees the port before starting, so just rerun it after code changes. Use the `EN` / `中文` button at the top right to switch the interface language.

To view on a phone on the same Wi-Fi:

```bash
./scripts/run-web.sh --lan
# or: WEB_PORT=9000 ./scripts/run-web.sh
```

The terminal prints the LAN address. You can add it to your home screen in the browser.

The always-on monitor lives with the **web process**. When the process stops, WebSocket, digest, news, Spot Radar and Telegram all stop. With `MONITOR_ALWAYS_ON=false`, monitor rules are evaluated only while the page is open; the schedule / digest / news / Spot Radar loops still start with the process (each has its own `*_ENABLED` switch).

---

## Configuration

All variables with comments are in [`.env.example`](.env.example). Below are the groups you will actually change when getting started. After copying the example file, the "example" values below are what you start with; for anything not written into `.env`, the code defaults in `src/analyst/config.py` apply (a few switches are more conservative in code, e.g. Square posting is off by default).

### LLM (analysis, digest, news grading, Square polish)

Call order:

1. **b.ai** (with `BAI_API_KEY` + `BAI_MODEL` set and `LLM_TRY_BAI_AFTER_GROQ=true`) is tried first, with the full v1 prompt
2. **Free tier**: endpoints listed in `LLM_FREE_ORDER` that have a key configured. Code default order is `nvidia,groq,cerebras,openrouter,sambanova,gemini`
3. **Primary route** `LLM_PROVIDER`: `deepseek` (recommended) / `anthropic` / `openai` (compatible with Groq, OpenRouter, Ollama, official OpenAI)

With `MONITOR_AI_FREE_ONLY=true`, monitor auto-confirmation stops at steps 1–2.

| Variable | Purpose |
|------|------|
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_BASE_URL` | Primary route. DeepSeek console: https://platform.deepseek.com |
| `DEEPSEEK_API_KEY` | DeepSeek. `DEEPSEEK_THINKING_ENABLED` and `DEEPSEEK_REASONING_EFFORT` map to V4 thinking mode |
| `ANTHROPIC_API_KEY` | Used when `LLM_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | Key when the provider is `openai` (can also point to Ollama: `LLM_BASE_URL=http://localhost:11434/v1`) |
| `BAI_API_KEY` / `BAI_MODEL` | b.ai, example model `deepseek-v4-flash` |
| `GROQ_API_KEY` `CEREBRAS_API_KEY` `GEMINI_API_KEY` `OPENROUTER_API_KEY` `SAMBANOVA_API_KEY` `NVIDIA_API_KEY` | Free tier; whichever is configured gets used. Base URLs and recommended models are in the example file |
| `LLM_TEMPERATURE` / `LLM_MAX_TOKENS` | Sampling and output length. Example `0.3` / `4000` |
| `LLM_PROMPT_VERSION` | Main prompt version, default `v1`. The Groq pre-layer always uses the short `groq` version |
| `DEFAULT_ACCOUNT_USD` / `MAX_RISK_PER_TRADE_PCT` / `MAX_LEVERAGE` | Injected into the analysis prompt only, as position-sizing reference. Example `10000` / `1` / `10` |
| `DEFAULT_TIMEFRAME` | Default timeframe for CLI `practice`, example `4h` |
| `VERIFICATION_DELAY_HOURS` / `SESSION_EXPIRE_HOURS` | How long before a plan can be verified, and session retention. Example `72` / `168` |

### Symbols and always-on monitor

| Variable | Purpose |
|------|------|
| `EXCHANGE` | Market data exchange, default `binance` |
| `DEFAULT_SYMBOLS` | **The single default symbol list.** cycle / xs / carry `*_SYMBOLS` follow it when left empty. Example: `BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,AAVE/USDT,UNI/USDT,HYPE/USDT,ASTER/USDT` |
| `MONITOR_MARKET` | Web is fixed to `futures` (USDⓈ-M perpetuals) |
| `MONITOR_ALWAYS_ON` | `true`: while the web process runs, keep monitoring and pushing to TG even with the page closed. Example default `false` |
| `MONITOR_DAEMON_SYMBOLS` | Always-on symbol override; empty means follow `DEFAULT_SYMBOLS`. In always-on mode, adding/removing coins on the page hot-reloads without a restart |
| `MONITOR_DAEMON_TIMEFRAMES` | Always-on timeframes, one WS per symbol × timeframe. Example `15m,1h,4h,1d,1w` |
| `MONITOR_CHART_TIMEFRAMES` | Selectable chart timeframes. Only `5m,15m,1h,4h` are accepted |
| `MONITOR_TIMEFRAME` | Single timeframe when always-on timeframes are not configured, example `15m` |
| `DATA_CACHE_DIR` / `DATA_CACHE_TTL_MINUTES` | REST short-cache directory and TTL. Example `.cache/data` / `5` |
| `DATABASE_URL` | Default `sqlite:///./analyst.db` |
| `LOG_LEVEL` / `LOG_FILE` | Example `INFO` / `.logs/analyst.log` |

### Rules, AI confirmation, Telegram

| Variable | Purpose |
|------|------|
| `MONITOR_RULES_ENABLED` and `MONITOR_RULE_*` | Master switch and per-rule switches: MACD, EMA, Bollinger, volume, structure, Fibonacci, baseline plan, funding, premium, regimes, Eric |
| `MONITOR_ADX_MIN_TREND` / `MONITOR_HTF_FILTER` | Trend-rule noise reduction. Example `18` / `true` |
| `MONITOR_VOLUME_SPIKE_RATIO` / `MONITOR_TOUCH_COOLDOWN_BARS` | Volume multiple, cooldown bars for the same support/resistance. Example `2.0` / `12` |
| `MONITOR_FUNDING_EXTREME_PCT` / `MONITOR_PREMIUM_EXTREME_PCT` | Extreme funding and premium thresholds |
| `MONITOR_TG_TRADE_RULES` | Telegram allowlist, comma-separated rule names |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Pushes. Leave empty to show on the page only |
| `MONITOR_AI_ON_CANDIDATE` / `MONITOR_AI_REQUIRE_QUALITY` | Call AI only on candidates, and the quality bar |
| `MONITOR_AI_FREE_ONLY` / `MONITOR_AI_COOLDOWN_MINUTES` | No paid routes for auto-confirmation; cooldown minutes. Example `true` / `240` |
| `MONITOR_ERIC_RSI_OVERSOLD` / `MONITOR_ERIC_RSI_OVERBOUGHT` / `MONITOR_ERIC_MIN_BUFF` / `MONITOR_ERIC_COOLDOWN_BARS` | Eric filters. Example `30` / `70` / `4` / `8` |
| `MONITOR_ERIC_SWING_SYMBOLS` / `MONITOR_ERIC_SWING_RISK_PCT` | Swing-plan symbols and suggested risk fraction. Example BTC and ETH only; risk `2.0` |

### Strategy watchlists

Empty means follow the monitor symbols.

| Variable | Purpose |
|------|------|
| `MONITOR_CYCLE_SWITCH_ENABLED` / `MONITOR_CYCLE_SWITCH_TIMEFRAME` | Per-coin `cycle_switch`. Example on, `4h` |
| `MONITOR_CYCLE_ADX_MIN` | ADX threshold for new positions to become AI candidates. Example `20`; below it, page only |
| `MONITOR_CYCLE_SYMBOLS` | cycle allowlist override |
| `MONITOR_CYCLE_OUTLOOK_ENABLED` | Daily BTC cycle position update. Example `true` |
| `MONITOR_XS_ENABLED` / `MONITOR_XS_TOP_N` / `MONITOR_XS_REBALANCE_HOURS` / `MONITOR_XS_BEAR_SHORT` | Cross-sectional momentum. Example on, long top 2, rebalance every 168 hours, short the weakest in bear markets |
| `MONITOR_XS_SYMBOLS` | Momentum pool override |
| `MONITOR_CARRY_ENABLED` / `MONITOR_CARRY_SYMBOLS` | Funding carry signals (alerts only) |
| `MONITOR_RATIO_ENABLED` / `MONITOR_RATIO_PAIRS` | Ratio pairs. Code default `ETH/BTC,BNB/BTC,UNI/BTC` |
| `MONITOR_RATIO_EMA_DAYS` / `MONITOR_RATIO_BAND` / `MONITOR_RATIO_BREAK_DAYS` | Long-term EMA, hysteresis band, breakout days. Default `200` / `0.02` / `40` |

### Schedule, digest, news, Spot Radar

| Variable | Purpose |
|------|------|
| `MONITOR_SCHEDULE_ENABLED` / `MONITOR_SCHEDULE_TG` | Schedule page and advance reminders |
| `MONITOR_SCHEDULE_SESSION_LEADS` | Session lead minutes. Example `30,15` |
| `MONITOR_SCHEDULE_FUNDING_LEADS` | Funding lead minutes. Example `30` |
| `MONITOR_SCHEDULE_MACRO_LEADS` | Macro lead minutes. Example `60,30,15` |
| `MONITOR_SCHEDULE_MACRO_CURRENCIES` / `MONITOR_SCHEDULE_MACRO_IMPACTS` | Example keeps only `USD` + `High` |
| `MONITOR_DIGEST_ENABLED` / `MONITOR_DIGEST_UTC_HOUR` | Digest. Example on, UTC `5` |
| `MONITOR_NEWS_ENABLED` / `MONITOR_NEWS_INTERVAL_MIN` | News sentinel. Example on, every `30` minutes |
| `MONITOR_NEWS_FEEDS` | Comma-separated RSS; `binance` means the Binance announcements API |
| `MONITOR_NEWS_MIN_SEVERITY` | Push threshold: `high` or `critical` |
| `SPOT_RADAR_ENABLED` | Spot Radar master switch |
| `SPOT_RADAR_INTERVAL_SECONDS` / `SPOT_RADAR_TOP_N` / `SPOT_RADAR_MIN_QUOTE_VOLUME` | Scan interval, top N by volume, minimum 24h volume (USDT). Example `900` / `30` / `10000000` |
| `SPOT_RADAR_COOLDOWN_SECONDS` / `SPOT_RADAR_SIGNAL_COOLDOWN_SECONDS` | Regular alert / 4h strength signal cooldown. Example `3600` / `14400` |
| `SPOT_RADAR_TELEGRAM` / `SPOT_RADAR_BRIEF_ENABLED` | Push hits to TG; daily 08:00 Dubai BTC/ETH brief |

Finer settings such as the spike threshold (`SPOT_RADAR_IMPULSE_PCT`, etc.) exist only as code defaults; add them to `.env` when needed. See `spot_radar_*` in `config.py`.

### Paper trading

| Variable | Example | Purpose |
|------|------|------|
| `PAPER_ENABLED` | `true` | Master switch |
| `PAPER_SYMBOLS` | `BTC/USDT,ETH/USDT,SOL/USDT` | Symbols evaluated |
| `PAPER_EQUITY_USD` | `10000` | Simulated equity |
| `PAPER_RISK_PCT` | `1.0` | Risk per trade as % of equity |
| `PAPER_MAX_LEVERAGE` | `3` | Leverage cap |
| `PAPER_DAILY_FUSE_PCT` | `3` | Intraday drawdown circuit breaker |
| `PAPER_MAX_POSITIONS` | `2` | Max concurrent positions |
| `PAPER_EXIT_RULE` | `boll_mid` | Exit for the remainder |
| `PAPER_ENTRY_PREF` | `618` | Pullback order preference |

### Binance Square and reference tweets

| Variable | Purpose |
|------|------|
| `BINANCE_SQUARE_OPENAPI_KEY` | Creator Center OpenAPI key. Apply at: https://www.binance.com/square/creator-center/home |
| `SQUARE_POST_ENABLED` | `true` in the example; posting is skipped without a key |
| `SQUARE_POST_SYMBOLS` / `SQUARE_POST_TIMEFRAMES` | Posting symbols and timeframes. Timeframes must be available from always-on or REST, example `4h,1d,1w` |
| `SQUARE_POST_COOLDOWN_HOURS` and `SQUARE_POST_SETUP_*` / `TOUCH_*` / `MOVE_*` / `RECAP_*` / `ERIC_*` | Per-trigger switches and cooldowns, see the example file |
| `SQUARE_POST_COMPACT` / `SQUARE_POST_AI_POLISH` | Short notes; polish before posting while enforcing tags and CTA |
| `SQUARE_POST_CHART_ENABLED` plus width/height and candle count | Images. Requires Playwright |
| `X_BEARER_TOKEN` | Used only by `scripts/fetch_reference_tweets.py`; an X Developer bearer token, not an LLM key |

---

## Strategies

```bash
analyst strategies
```

| ID | Description | Backtest |
|----|------|------|
| `cycle_switch` | Halving calendar × 200-day EMA double confirmation. Donchian long-only in bull markets; half-size bounce shorts in bear markets. The monitor evaluates positions on close of the configured timeframe | `analyst backtest-classic BTC -s cycle_switch --days 1825` |
| `xs_momentum` | Multi-coin momentum: long the top 2, optionally short the weakest in bear markets. Rebalances about weekly | `analyst backtest-xs --days 1825` |
| `funding_carry` | Delta neutral: long spot + short perp to collect funding. Exits during negative funding. Live use needs a hedging account; here it is signals and backtests only | `analyst backtest-carry BTC --days 1825` |

Rule hit rate is a separate command, not the same as the portfolio backtest:

```bash
analyst backtest BTC -t 15m --bars 1000
analyst backtest SOL -t 1h --bars 1500 --json r.json
```

Uses the same rules as the live monitor, runs ATR-barrier look-ahead on historical candles, and outputs sample count, hit rate and average forward return. A hit rate around 50% means the rule has no edge on its own.

The classic portfolio backtest includes one-way fees and slippage, compounding, bull/bear segments, out-of-sample, plus rolling windows, cost sensitivity, Deflated Sharpe and PBO:

```bash
analyst backtest-classic BTC -s cycle_switch --days 1825
analyst backtest-classic BTC -s buy_hold --days 1825
```

The web "Backtest" page shares its engine with `backtest-classic`. Available strategies: `cycle_switch`, `buy_hold`. Cross-sectional momentum and funding carry use the dedicated commands above.

Read results conservatively when samples are few or the calendar boundaries fit history closely. Naked short legs often drag returns in crypto; `cycle_switch` only shorts bounces in bear markets.

---

## CLI

Running `analyst` with no arguments lists the commands.

| Command | Purpose |
|------|------|
| `analyst web [--lan] [--port 8000]` | Web + always-on monitor + schedule / digest / news / Spot Radar |
| `analyst practice BTC [--tf 4h]` | Pull multi-timeframe data, have the AI produce a plan and store it |
| `analyst verify` | Verify expired sessions |
| `analyst history` / `analyst review <id>` | History list / single review |
| `analyst progress` / `weakness` / `ai-benchmark` | Statistics and model comparison |
| `analyst backtest <symbol>` | Rule-alert look-ahead hit rate |
| `analyst backtest-classic <symbol> -s cycle_switch\|buy_hold` | Classic portfolio backtest |
| `analyst backtest-xs` / `backtest-carry <symbol>` | Cross-sectional momentum / funding carry |
| `analyst cycle-outlook [--telegram]` | View the calendar model and Wolfy Wave in the terminal; optionally push to TG |
| `analyst cycle-status [BTC,ETH,SOL,BNB]` | Execution phase + target position per coin |
| `analyst digest [--send]` | Generate the digest; `--send` pushes to Telegram |
| `analyst research-ideas` | Generate research ideas |
| `analyst square-post [--publish --text '...']` | Preview or actually publish a Square note |
| `analyst strategies` | Strategy catalog |
| `analyst config show` / `config test-llm` | Print config (keys masked) / test the LLM |
| `analyst db init` / `db backup` | Create the database / back up sqlite |
| `analyst data status` / `data refresh BTC` | Cache usage / force-refresh all timeframes for a symbol |

---

## What gets created locally

| Path | Contents |
|------|------|
| `analyst.db` | AI sessions, plans, verifications, chat |
| `ohlcv.sqlite` | Local candles for backtests and missing-bar checks |
| `.cache/data/monitor_daemon.json` | Always-on monitor symbols (the page watchlist can write back) |
| `.cache/data/price_alerts.json` | Price alerts |
| `.cache/data/paper_state.json` | Paper equity, positions, orders, log |
| `.cache/data/schedule_reminders.json` | Schedule reminder dedup |
| `.cache/data/cycle_outlook_tg.json` | Date stamp for the daily cycle update |
| `.cache/data/ai_confirm_cooldown.json` | AI candidate cooldown |
| `.cache/data/daily_digest_state.json` / `last_digest.json` / `last_research.json` | Digest scheduling and the latest digest and research ideas |
| `.cache/data/news_events.json` / `news_sentinel_seen.json` | News grading results and seen-item dedup |
| `.cache/data/square_regime_cooldown.json` | Square posting cooldown |
| `.cache/data/eric_swing_state.json` | Eric swing plan state |
| `.cache/data/` | Other REST short caches, safe to delete |
| `.env` / `.venv/` / `.logs/` | Keys, virtual environment, logs (gitignored) |

Live WS candles roll in memory only and are not a history store. Deleting `.cache/data` loses price alerts, the paper ledger and cooldown state; analysis sessions in the database remain.

---

## Development

```bash
uv sync --extra web --extra dev
pytest tests/ -q
python scripts/generate_favicon.py   # regenerate icons
```

```
crypto-analyst/
├── prompts/                 # full v1 prompt / short groq version
├── scripts/run-web.sh
├── src/analyst/
│   ├── cli.py               # analyst command
│   ├── config.py            # environment variables
│   ├── backtest/            # rule replay and classic portfolio backtest
│   ├── compute/             # indicators, levels, regimes, cycle, strategies, seed sizing
│   ├── exec/paper.py        # paper matching
│   ├── llm/                 # analysis, digest, research ideas
│   ├── monitor/             # monitor hub, rules, radar, news, schedule, Square
│   └── web/                 # FastAPI + single-page frontend (static/i18n.js holds the English dictionary)
└── tests/
```

Common APIs:

| Method | Path | Purpose |
|------|------|------|
| GET | `/api/health` `/api/config` | Liveness, current public config |
| GET | `/api/monitor/symbols` `/api/monitor/levels` `/api/monitor/alerts` | Watchlist, key levels, alerts |
| GET | `/api/monitor/cycle-timeline` | Cycle page data |
| GET | `/api/schedule?tz=Asia/Dubai` | Schedule |
| GET/POST | `/api/spot-radar` `/api/spot-radar/scan` | Radar snapshot / run a scan now |
| GET | `/api/paper/summary` | Paper positions and stats |
| GET/POST | `/api/price-alerts` | Price alerts |
| GET | `/api/monitor/digest` `/api/monitor/research-ideas` `/api/monitor/news-events` | Digest, ideas, news. Add `?refresh=1` to regenerate the first two |
| POST | `/api/backtest/classic` | Same portfolio backtest as the Backtest page |
| POST | `/api/monitor/analyze` `/api/monitor/chat` | Manual AI analysis / follow-up chat; body field `lang` (`zh` / `en`) controls the answer language |
| WS | `/api/monitor/ws` | Live candles and alerts |

---

## Notes

- No order API is connected. You are responsible for your own P&L and decisions. Paper results use simplified fee and slippage assumptions and cannot replace live trading.
- The cycle calendar is a "calendar model"; milestone dates risk overfitting history and should be read together with current price action.
- Swing levels, regime playbooks and Eric rules are structural or statistical heuristics, not guaranteed reproductions of any public trading notes.
- Posts auto-published to Binance Square are public. Review the copy with `analyst square-post` first, confirm the key and symbols, then enable `SQUARE_POST_ENABLED`.

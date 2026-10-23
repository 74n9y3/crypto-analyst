# Crypto Analyst

[English](README.md) | **中文**

本地运行的加密货币盯盘与分析工具。数据来自币安公开行情（Web 固定 **U 本位永续**；现货雷达另读现货）。规则在 K 线收盘或标记价上评估，可选再交给 LLM 点评，并推到页面或 Telegram。

**只提醒，不下真实单。** 纸面交易用标记价在本地撮合，用来验证「强势盘低多」计划，不会连接交易接口。

顶栏：**盯盘** → **周期** → **日程** → **现货雷达** → **策略库** → **回测** → **纸面交易** → **AI 助手**。手机浏览器可「添加到主屏幕」（PWA）。

**语言：** 支持简体中文与英文。右上角 `EN` / `中文` 按钮切换的是整个应用，不只是页面：选择保存在服务端（`.cache/data/ui_settings.json`），后端产出的所有文字都跟着变——AI 分析与追问、规则告警、关键位打法、Telegram 推送、日报、新闻分级、现货雷达、纸面交易、币安广场帖子和 CLI 输出。首次运行跟随浏览器语言；终端里可用 `analyst lang en` / `analyst lang zh` 切换。已经生成的内容（库里的 AI 会话、历史告警）保持当时的语言。

<div align="center">
<h3>☕ 请我一杯咖啡</h3>
<p>项目免费。若它帮你盯住过行情，欢迎用对应网络的 <strong>USDT</strong> 打赏。<br/>
<sub>请按下面的网络转入，网络不一致会无法入账。</sub></p>
<p>
  <img alt="BSC USDT" src="https://img.shields.io/badge/BSC-USDT%20BEP--20-F3BA2F?style=for-the-badge&logo=binance&logoColor=white" />
  <img alt="Solana USDT" src="https://img.shields.io/badge/Solana-USDT-9945FF?style=for-the-badge&logo=solana&logoColor=white" />
  <img alt="Tron USDT" src="https://img.shields.io/badge/Tron-USDT%20TRC--20-FF060A?style=for-the-badge&logo=tron&logoColor=white" />
</p>
</div>

| 网络 | 打赏地址 |
|:-----|:---------|
| ![BSC](https://img.shields.io/badge/BSC-F3BA2F?style=flat-square&logo=binance&logoColor=white) **USDT · BEP-20** | `0x6E7359A42C466893E9A835fD6aFdb82E0D1Ed32d` |
| ![Solana](https://img.shields.io/badge/Solana-9945FF?style=flat-square&logo=solana&logoColor=white) **USDT** | `Hm7f6wGdvcmLmbcXV7sdLYGJKBdwGoFrJTZPzeN8dpan` |
| ![Tron](https://img.shields.io/badge/Tron-FF060A?style=flat-square&logo=tron&logoColor=white) **USDT · TRC-20** | `TGNrpZBqD8jnfNCb7B9W93qMmVHycoFsKJ` |

<p align="center">
  <img src="docs/images/web-dashboard.png" alt="Web 盯盘：K 线、关键位与 AI 分析" width="900" />
</p>
<p align="center"><em>盯盘页：左侧 K 线；右侧同一条可收起侧栏，竖标签「关键位」「AI行情分析」（关键位含头仓 / 止损 / 止盈 / 支撑 / 阻力，打法在支撑阻力下方）；底部告警记录与历史分析</em></p>

需要 Python **3.11+**，以及能访问币安行情的网络。

---

## 能力一览

| 页面 | 做什么 | 要不要额外配置 |
|------|--------|----------------|
| **盯盘** | 多周期 K 线、规则告警、关键位、手动 AI 分析、价格告警、底部历史 | 行情即可看图；AI 需 LLM key；推送需 Telegram |
| **周期** | Wolfy 四年周期：刻舟求剑日历、转折点倒计时、狼波指数、减半时间轴 | 无。固定 BTC 日线，约 5 分钟刷新 |
| **日程** | 本地时区时钟、亚/欧/美时段、资金费倒计时、USD 高影响宏观日历 | `MONITOR_SCHEDULE_*`；宏观来自 Forex Factory 本周公开 JSON |
| **现货雷达** | 成交额靠前的 USDT 现货：急涨急跌、突破、放量、均线穿越、4h 强度榜；每天迪拜 08:00 推 BTC/ETH 简报 | `SPOT_RADAR_*`（示例里已开） |
| **策略库** | `cycle_switch` / `xs_momentum` / `funding_carry` 目录，可跳回测或周期页 | 常驻盯盘才会在收盘评估 |
| **回测** | 经典组合回测（复利、成本、滚动样本外、成本敏感度、Deflated Sharpe、PBO） | 首次会拉历史 K 线，写入 `ohlcv.sqlite` |
| **纸面交易** | 强势盘回踩 0.618 限价多单，标记价撮合，止损 / 一半止盈 / 保本 / BOLL 中轨离场 | `PAPER_*`（示例里已开） |
| **AI 助手** | 交易日报、研究假设、新闻风险事件 | 日报与假设要 LLM；新闻哨兵要 `MONITOR_NEWS_*` |

```
币安行情
  ├─ 永续 WS K 线 / 标记价  →  规则告警 + cycle / xs / carry + Eric
  │                              ├─ 页面
  │                              ├─ 合格候选 → AI 点评 → Telegram
  │                              ├─ 纸面撮合（本地，不下单）
  │                              └─ 可选：币安广场短评
  ├─ 现货公开行情            →  现货雷达 → 页面 + Telegram
  ├─ RSS / 币安公告          →  新闻哨兵分级 → 高危推 Telegram
  └─ 手动 / CLI 分析         →  analyst.db（计划、验证、聊天）
```

盯盘图表周期默认 **`5m / 15m / 1h / 4h`**（`MONITOR_CHART_TIMEFRAMES`）。常驻评估周期看 `MONITOR_DAEMON_TIMEFRAMES`，和页面上切换的图表周期互不影响。

---

## 盯盘里具体有什么

### 规则告警（收盘评估，无 LLM）

默认全开，命中都上页面。是否进 Telegram 由 `MONITOR_TG_TRADE_RULES` 白名单决定。

| 规则 | 含义 |
|------|------|
| `macd_cross` / `ema_stack` / `boll_break` | 趋势类。ADX 低于 `MONITOR_ADX_MIN_TREND`（默认 18）当震荡不报；`MONITOR_HTF_FILTER` 丢掉逆更高周期 EMA 排列的信号 |
| `volume` | 放量（默认 ≥ 20 根均量的 2 倍，且实体够大） |
| `structure_touch` / `structure_flip` | 支撑阻力触及守住、结构翻转。同一价位有冷却根数 |
| `fib_zone` | 斐波区域 |
| `funding_extreme` / premium | 资金费或溢价极端 |
| `market_regime` / `playbook_setup` | 三盘切换与打法提示（强势 / 震荡 / 弱势） |
| `cycle_switch` | 各盯盘币对仓位变化。只上页面并可作为 AI 候选，不直推 TG |
| `xs_momentum` / `funding_carry` | 横截面动量调仓、资金费套利信号变化 |
| `ratio_shift` | ETH/BTC、BNB/BTC、UNI/BTC 相对 200 日 EMA 的强弱切换 |
| `eric_*` | 仅 BTC/ETH 日线、周线（4h 收盘时用 REST 补日/周，不必把 1d/1w 放进图表周期） |
| `paper_*` | 纸面挂单、成交、止盈、止损、熔断 |
| `spot_*` | 现货雷达命中 |

### 价格告警（不等 K 线收盘）

盯盘里可对当前合约设标记价告警：价格达到、只上穿、只下穿、百分比变化、绝对价格变化。时间窗口只用于后两种（自设定起，或 1 / 5 / 15 / 60 分钟）。存在 `.cache/data/price_alerts.json`，命中推页面和 Telegram。

### 三盘与波段锁点

创建分析、以及盯盘 K 线收盘时都会预计算，注入 LLM，并显示在右侧「关键位」。

**三盘（`market_regime`）**

| 盘面 | 打法 |
|------|------|
| 强势盘 | 市价小头仓 + 突破近阻力/昨高加仓，新高止盈 |
| 震荡盘 | 低多 / 扎针后等支撑；回踩不破补仓；当日振幅 0.50–0.618 止盈 |
| 弱势盘 | 日线转空：反弹近阻力头仓空 + 跌破支撑加仓 |

另含防守位是否已破、12h EMA6、前一日高低、日内止盈、腰斩线以下不追空、周线 BOLL 中轨作回调极限。头仓 + 补仓默认不超过权益的约 25%（随杠杆下调）。关闭规则：`MONITOR_RULE_MARKET_REGIME=false`。

头仓试算：`GET /api/tools/seed-position?account=10000&leverage=25&seed_pct=0.04&max_total_pct=0.18&add_mode=pullback`。实现在 `src/analyst/compute/position_sizing.py`。Kelly（`kelly.py`）管单笔风险比例，头仓模块管分层结构。

**波段锁点（`swing_levels`）**，写入 `market_snapshot` 并注入 `{swing_block}`：

| 字段 | 含义 |
|------|------|
| `rebound_382` / `rebound_618` | 下跌后反弹目标：`Low+(H−L)×0.382/0.618` |
| `daily_bias` | 日线定调：`up` / `down` / `range` |
| `defense_level` | 失效防守位 |
| `htf_ready` / `horizon` | 高周期是否成熟；未成熟时建议短线反抽 |
| `confluence_*` | 斐波是否贴近日线 BOLL 中轨 |
| `touch_count` | 关键阻力近期触及次数 |
| `rs_note` | 相对 BTC 强弱摘要 |

公式在代码里算，提示词只加短纪律（`prompts/system_v1.md`，Groq 前置层用更短的 `prompts/system_groq.md`）。

### Eric 波段（BTC / ETH）

`MONITOR_RULE_ERIC`：日线、周线 RSI 超卖/超买 + 背离 + Buff 评分，达标才发 `eric_rebound` / `eric_fade`。BNB/SOL 与 4h 及以下回测没有优势，不会出这些信号。

`MONITOR_RULE_ERIC_SWING`：周线超卖拐头后的波段计划（观察、开多、一半止盈、余仓、止损）。默认只跑 `MONITOR_ERIC_SWING_SYMBOLS=BTC/USDT,ETH/USDT`。状态在 `.cache/data/eric_swing_state.json`。

### AI 点评（控成本）

`MONITOR_AI_ON_CANDIDATE=true` 时，收盘出现合格候选才调 LLM。`MONITOR_AI_REQUIRE_QUALITY=true` 时，单条放量或触及不够，需要质量规则，或同一根上至少两条。

- 结论 `long` / `short` → 页面 + Telegram「盯盘点评」（含止损止盈，仅提醒）
- `wait` → 不推
- 同品种 + 分析周期默认冷却 240 分钟（`MONITOR_AI_COOLDOWN_MINUTES`）

`MONITOR_AI_FREE_ONLY=true`（推荐）时，**自动确认只用 b.ai 和免费层**，失败不回落 DeepSeek / Anthropic 付费线路；同一次故障 Telegram 只推一条。盯盘里手动点「分析」、以及 `analyst practice`，仍走完整链路（免费优先，失败再付费）。

右侧还可对当前合约追问（先分析再问，回答会更贴盘面）。会话、计划、验证写入 `analyst.db`。到期后 `analyst verify` 或页面回溯结果。

---

## 告警怎么推

| 类型 | 页面 | Telegram |
|------|------|----------|
| 规则噪音（放量、触及等，不在白名单里） | 有 | 默认不推 |
| 白名单规则（MACD、均线、放量、布林、资金费、Eric、纸面、现货雷达等） | 有 | 推 |
| 收盘候选 → AI `long`/`short`（`ai_plan`） | 有 | 推 |
| `cycle_switch` 仓位变化 | 有（可触发 AI） | 不直推 |
| 周期位置日更 `cycle_outlook`（BTC） | 有 | UTC 每天最多 1 条，不受白名单限制 |
| 日程：时段 / 资金费 / 宏观 | 「日程」页 | 提前期推（`MONITOR_SCHEDULE_TG`） |
| 价格告警 | 有 | 推 |
| AI 日报 | 「AI 助手」 | 每天 UTC 定时 1 条 |
| 新闻 `high` / `critical` | 「AI 助手」 | 推 |
| 现货雷达 + 每日 BTC/ETH 简报 | 「现货雷达」 | `SPOT_RADAR_TELEGRAM` / `SPOT_RADAR_BRIEF_ENABLED` |

白名单留空表示全部规则都推 Telegram。示例白名单见 [`.env.example`](.env.example) 的 `MONITOR_TG_TRADE_RULES`。

---

## 其余模块

### 四年周期（Wolfy）

基于 BTC 日线的位置参考，不是下单信号。

- **刻舟求剑日历**：锚定历次熊市底部，牛市 1064 天、熊市 364 天，显示相位进度与下一转折点（≤30 天在页面高亮）
- **狼波指数**：按区块高度计算的 [Wolfy Wave Index](https://github.com/tangyiming/wolfy-wave-index)（0 = 理论熊底，1 = 理论牛顶）。交互图在周期页；日更 Telegram 带当前读数。页面亦见 [wolfy-wave-index](https://wolfyxbt.github.io/wolfy-wave-index/)
- **时间轴**：历史牛熊色带、减半标记、价格背景

`cycle_switch` 的执行相位是另一套：减半日历 × 200 日线双确认。牛市唐奇安只做多，熊市反弹做空半仓。相位用 BTC 定调，各币用自己的 K 线。

### 现货雷达

只读 `https://data-api.binance.vision`。在成交额靠前、且 24h 成交额达到门槛的 USDT 现货里找：15 分钟急涨急跌、区间突破、放量、均线穿越，以及 4 小时强度进入前排。稳定币计报价种会被滤掉。普通提醒默认冷却 1 小时，4 小时强度信号冷却 4 小时。每天 08:00（`Asia/Dubai`）写一份 BTC/ETH 简报：昨高低、涨跌幅、今天盯的价位。

### 纸面交易

4h 收盘评估「强势盘低多」：回踩 0.618（可由 `PAPER_ENTRY_PREF` 改）挂限价多，用实时标记价撮合。成交后止损上移成本，余仓按 `PAPER_EXIT_RULE`（默认破 4h BOLL 中轨）离场。日内回撤达到 `PAPER_DAILY_FUSE_PCT` 则全平并暂停到次日。权益、风险比例、杠杆上限、同时持仓数都在 `PAPER_*`。账本在 `.cache/data/paper_state.json`。

### AI 日报、研究假设、新闻哨兵

- **日报**（`MONITOR_DIGEST_ENABLED`）：到点聚合系统里已有事实，LLM 只做总结。默认 UTC 5 点（迪拜早 9 点）。LLM 不可用时降级为模板。`analyst digest` / 页面「生成日报」。
- **研究假设**：根据近况提可回测的改进方向。假设不是结论；已证伪路线会被排除。`analyst research-ideas`。
- **新闻哨兵**：按 `MONITOR_NEWS_INTERVAL_MIN` 拉 RSS，外加币安官方公告（feed 名写 `binance`）。LLM 分级，达到 `MONITOR_NEWS_MIN_SEVERITY`（默认 `high`）才推 Telegram。

### 币安广场（可选）

`SQUARE_POST_ENABLED=true` 且配置 `BINANCE_SQUARE_OPENAPI_KEY` 后，盯盘触发源可以自动发短评。默认短讯 + AI 润色（交易员口吻；数字、`$BTC` 标签、末行 CTA 强制保留，失败回退模板）。

| 触发 | 说明 | 默认冷却 |
|------|------|----------|
| `market_regime` | 三盘 / 方向切换 | 同币同周期 2h |
| `playbook_setup` | 金叉 / 加速 / 扎针等打法 | 6h |
| `structure_touch` | 支撑阻力触碰守住 | 同位 4h |
| 加速行情 | 4h 单根涨跌达阈值或放量 | 同品种 4h |
| Eric 超卖 | BTC/ETH 日线、周线 | 20h |
| 每日复盘 | 与日报同一 UTC 时刻，或 `SQUARE_POST_RECAP_UTC_HOUR` | 1 次/天 |

配图走 Playwright 离页渲染 `chart_capture.html`（K 线 + 锁点）。未安装时自动降级为纯文字：

```bash
uv sync --extra square && playwright install chromium
```

预览：`analyst square-post`。试发：`analyst square-post --publish --text '...'`。Key 只放 `.env`，不要提交。

### 相对强弱

`MONITOR_RATIO_ENABLED` 默认跟踪 `ETH/BTC,BNB/BTC,UNI/BTC`，相对长期 EMA（默认 200 日）加迟滞带，并看 N 日新高/新低。只告警。

---

## 5 分钟上手

**1. 安装**（项目根目录）

```bash
uv sync --extra web
# 或：python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[web]"
```

广场配图再加：`uv sync --extra web --extra square && playwright install chromium`。

**2. 配置**

```bash
cp .env.example .env
```

只想先看盘、做手动分析，至少填一条 LLM（示例默认 DeepSeek）：

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-你的key
LLM_MODEL=deepseek-v4-flash
```

要关页面也盯盘、并推 Telegram：

```bash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
MONITOR_ALWAYS_ON=true
```

Bot：在 Telegram 找 `@BotFather` 创建，把 token 填上；把 bot 拉进对话后，用 `@userinfobot` 或 `getUpdates` 拿到 `TELEGRAM_CHAT_ID`。

初始化并自检：

```bash
analyst db init
analyst config show          # 密钥只显示前几位
analyst config test-llm      # 打一条极短分析，确认链路通
```

**3. 启动 Web**

```bash
./scripts/run-web.sh
# 等价：analyst web
```

打开 **http://127.0.0.1:8000**。脚本会先释放端口再启动，改代码后直接重跑即可。右上角 `EN` / `中文` 切换界面语言。

同一 Wi-Fi 下用手机看：

```bash
./scripts/run-web.sh --lan
# 或：WEB_PORT=9000 ./scripts/run-web.sh
```

终端会打印局域网地址。浏览器里可添加到主屏幕。

常驻盯盘跟着 **Web 进程** 走。进程停了，WebSocket、日报、新闻、现货雷达和 Telegram 都会停。`MONITOR_ALWAYS_ON=false` 时，只有页面开着才评估盯盘规则；日程 / 日报 / 新闻 / 现货雷达循环仍会随进程启动（各自还有 `*_ENABLED` 开关）。

---

## 配置

全部变量和注释在 [`.env.example`](.env.example)。下面是上手时真正会改的分组。复制示例文件后，下面「示例」列就是你拿到的初值；不写进 `.env` 时，以 `src/analyst/config.py` 的代码默认值为准（少数开关代码默认更保守，例如广场发帖默认关）。

### LLM（分析、日报、新闻分级、广场润色）

调用顺序：

1. **b.ai**（配了 `BAI_API_KEY` + `BAI_MODEL`，且 `LLM_TRY_BAI_AFTER_GROQ=true`）最先试，用完整 v1 提示词
2. **免费层**：`LLM_FREE_ORDER` 里、并且配置了对应 key 的端点。代码默认顺序 `nvidia,groq,cerebras,openrouter,sambanova,gemini`
3. **主线路** `LLM_PROVIDER`：`deepseek`（推荐）/ `anthropic` / `openai`（兼容 Groq、OpenRouter、Ollama、OpenAI 官方）

盯盘自动确认在 `MONITOR_AI_FREE_ONLY=true` 时停在第 1–2 步。

| 变量 | 作用 |
|------|------|
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_BASE_URL` | 主线路。DeepSeek 控制台：https://platform.deepseek.com |
| `DEEPSEEK_API_KEY` | DeepSeek。`DEEPSEEK_THINKING_ENABLED`、`DEEPSEEK_REASONING_EFFORT` 对应 V4 思考模式 |
| `ANTHROPIC_API_KEY` | `LLM_PROVIDER=anthropic` 时使用 |
| `OPENAI_API_KEY` | provider 为 `openai` 时的 key（也可指向 Ollama：`LLM_BASE_URL=http://localhost:11434/v1`） |
| `BAI_API_KEY` / `BAI_MODEL` | b.ai，示例模型 `deepseek-v4-flash` |
| `GROQ_API_KEY` `CEREBRAS_API_KEY` `GEMINI_API_KEY` `OPENROUTER_API_KEY` `SAMBANOVA_API_KEY` `NVIDIA_API_KEY` | 免费层，配哪个用哪个。各 base URL 与推荐模型写在示例文件里 |
| `LLM_TEMPERATURE` / `LLM_MAX_TOKENS` | 采样与输出长度。示例 `0.3` / `4000` |
| `LLM_PROMPT_VERSION` | 主提示词版本，默认 `v1`。Groq 前置层固定短版 `groq` |
| `DEFAULT_ACCOUNT_USD` / `MAX_RISK_PER_TRADE_PCT` / `MAX_LEVERAGE` | 只注入分析提示词，作仓位建议参考。示例 `10000` / `1` / `10` |
| `DEFAULT_TIMEFRAME` | CLI `practice` 的默认周期，示例 `4h` |
| `VERIFICATION_DELAY_HOURS` / `SESSION_EXPIRE_HOURS` | 计划多久后可验证、会话保留。示例 `72` / `168` |

### 品种与常驻盯盘

| 变量 | 作用 |
|------|------|
| `EXCHANGE` | 行情所，默认 `binance` |
| `DEFAULT_SYMBOLS` | **唯一默认品种列表**。cycle / xs / carry 的 `*_SYMBOLS` 留空时都跟这份。示例：`BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,AAVE/USDT,UNI/USDT,HYPE/USDT,ASTER/USDT` |
| `MONITOR_MARKET` | Web 固定 `futures`（U 本位永续） |
| `MONITOR_ALWAYS_ON` | `true`：Web 进程在跑时，关页面也继续盯盘并推 TG。示例默认 `false` |
| `MONITOR_DAEMON_SYMBOLS` | 常驻品种覆盖；空则跟 `DEFAULT_SYMBOLS`。常驻模式下页面加减币会热更新，不必重启 |
| `MONITOR_DAEMON_TIMEFRAMES` | 常驻多周期，每个品种 × 周期一条 WS。示例 `15m,1h,4h,1d,1w` |
| `MONITOR_CHART_TIMEFRAMES` | 图表可选周期。只接受 `5m,15m,1h,4h` |
| `MONITOR_TIMEFRAME` | 未配置常驻多周期时的单一周期，示例 `15m` |
| `DATA_CACHE_DIR` / `DATA_CACHE_TTL_MINUTES` | REST 短缓存目录与 TTL。示例 `.cache/data` / `5` |
| `DATABASE_URL` | 默认 `sqlite:///./analyst.db` |
| `LOG_LEVEL` / `LOG_FILE` | 示例 `INFO` / `.logs/analyst.log` |

### 规则、AI 确认、Telegram

| 变量 | 作用 |
|------|------|
| `MONITOR_RULES_ENABLED` 与 `MONITOR_RULE_*` | 总开关和分项：MACD、EMA、布林、放量、结构、斐波、基线计划、资金费、溢价、三盘、Eric |
| `MONITOR_ADX_MIN_TREND` / `MONITOR_HTF_FILTER` | 趋势规则降噪。示例 `18` / `true` |
| `MONITOR_VOLUME_SPIKE_RATIO` / `MONITOR_TOUCH_COOLDOWN_BARS` | 放量倍数、同一支撑阻力冷却根数。示例 `2.0` / `12` |
| `MONITOR_FUNDING_EXTREME_PCT` / `MONITOR_PREMIUM_EXTREME_PCT` | 资金费、溢价极端阈值 |
| `MONITOR_TG_TRADE_RULES` | Telegram 白名单，逗号分隔规则名 |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | 推送。不填则只在页面显示 |
| `MONITOR_AI_ON_CANDIDATE` / `MONITOR_AI_REQUIRE_QUALITY` | 候选才调 AI、以及质量门槛 |
| `MONITOR_AI_FREE_ONLY` / `MONITOR_AI_COOLDOWN_MINUTES` | 自动确认不走付费；冷却分钟。示例 `true` / `240` |
| `MONITOR_ERIC_RSI_OVERSOLD` / `MONITOR_ERIC_RSI_OVERBOUGHT` / `MONITOR_ERIC_MIN_BUFF` / `MONITOR_ERIC_COOLDOWN_BARS` | Eric 过滤。示例 `30` / `70` / `4` / `8` |
| `MONITOR_ERIC_SWING_SYMBOLS` / `MONITOR_ERIC_SWING_RISK_PCT` | 波段计划品种与建议风险占比。示例只含 BTC、ETH；风险 `2.0` |

### 策略观察池

留空表示跟随盯盘品种。

| 变量 | 作用 |
|------|------|
| `MONITOR_CYCLE_SWITCH_ENABLED` / `MONITOR_CYCLE_SWITCH_TIMEFRAME` | 各币 `cycle_switch`。示例开、`4h` |
| `MONITOR_CYCLE_ADX_MIN` | 新开仓打进 AI 候选的 ADX 门槛。示例 `20`；不够只上页面 |
| `MONITOR_CYCLE_SYMBOLS` | cycle 白名单覆盖 |
| `MONITOR_CYCLE_OUTLOOK_ENABLED` | BTC 周期位置日更。示例 `true` |
| `MONITOR_XS_ENABLED` / `MONITOR_XS_TOP_N` / `MONITOR_XS_REBALANCE_HOURS` / `MONITOR_XS_BEAR_SHORT` | 横截面动量。示例开、做多 top 2、168 小时调仓、熊市空最弱 |
| `MONITOR_XS_SYMBOLS` | 动量池覆盖 |
| `MONITOR_CARRY_ENABLED` / `MONITOR_CARRY_SYMBOLS` | 资金费套利信号（只告警） |
| `MONITOR_RATIO_ENABLED` / `MONITOR_RATIO_PAIRS` | 汇率对。代码默认 `ETH/BTC,BNB/BTC,UNI/BTC` |
| `MONITOR_RATIO_EMA_DAYS` / `MONITOR_RATIO_BAND` / `MONITOR_RATIO_BREAK_DAYS` | 长期均线、迟滞带、突破天数。默认 `200` / `0.02` / `40` |

### 日程、日报、新闻、现货雷达

| 变量 | 作用 |
|------|------|
| `MONITOR_SCHEDULE_ENABLED` / `MONITOR_SCHEDULE_TG` | 日程页与提前提醒 |
| `MONITOR_SCHEDULE_SESSION_LEADS` | 时段提前分钟。示例 `30,15` |
| `MONITOR_SCHEDULE_FUNDING_LEADS` | 资金费提前分钟。示例 `30` |
| `MONITOR_SCHEDULE_MACRO_LEADS` | 宏观提前分钟。示例 `60,30,15` |
| `MONITOR_SCHEDULE_MACRO_CURRENCIES` / `MONITOR_SCHEDULE_MACRO_IMPACTS` | 示例只留 `USD` + `High` |
| `MONITOR_DIGEST_ENABLED` / `MONITOR_DIGEST_UTC_HOUR` | 日报。示例开、UTC `5` |
| `MONITOR_NEWS_ENABLED` / `MONITOR_NEWS_INTERVAL_MIN` | 新闻哨兵。示例开、每 `30` 分钟 |
| `MONITOR_NEWS_FEEDS` | 逗号分隔 RSS；`binance` 表示币安公告接口 |
| `MONITOR_NEWS_MIN_SEVERITY` | 推送门槛：`high` 或 `critical` |
| `SPOT_RADAR_ENABLED` | 现货雷达总开关 |
| `SPOT_RADAR_INTERVAL_SECONDS` / `SPOT_RADAR_TOP_N` / `SPOT_RADAR_MIN_QUOTE_VOLUME` | 扫描间隔、成交额前 N、最低 24h 成交额（USDT）。示例 `900` / `30` / `10000000` |
| `SPOT_RADAR_COOLDOWN_SECONDS` / `SPOT_RADAR_SIGNAL_COOLDOWN_SECONDS` | 普通提醒 / 4h 强度信号冷却。示例 `3600` / `14400` |
| `SPOT_RADAR_TELEGRAM` / `SPOT_RADAR_BRIEF_ENABLED` | 命中推 TG；每天迪拜 08:00 BTC/ETH 简报 |

急涨阈值等更细的项（`SPOT_RADAR_IMPULSE_PCT` 等）只在代码默认里，需要时再写进 `.env`。见 `config.py` 里 `spot_radar_*`。

### 纸面交易

| 变量 | 示例 | 作用 |
|------|------|------|
| `PAPER_ENABLED` | `true` | 总开关 |
| `PAPER_SYMBOLS` | `BTC/USDT,ETH/USDT,SOL/USDT` | 评估品种 |
| `PAPER_EQUITY_USD` | `10000` | 模拟权益 |
| `PAPER_RISK_PCT` | `1.0` | 单笔风险占权益 % |
| `PAPER_MAX_LEVERAGE` | `3` | 杠杆上限 |
| `PAPER_DAILY_FUSE_PCT` | `3` | 日内回撤熔断 |
| `PAPER_MAX_POSITIONS` | `2` | 同时持仓上限 |
| `PAPER_EXIT_RULE` | `boll_mid` | 余仓离场 |
| `PAPER_ENTRY_PREF` | `618` | 回踩挂单偏好 |

### 币安广场与参考推文

| 变量 | 作用 |
|------|------|
| `BINANCE_SQUARE_OPENAPI_KEY` | 创作者中心 OpenAPI Key。申请：https://www.binance.com/square/creator-center/home |
| `SQUARE_POST_ENABLED` | 示例为 `true`；没 key 时发帖会跳过 |
| `SQUARE_POST_SYMBOLS` / `SQUARE_POST_TIMEFRAMES` | 发帖品种与周期。周期需能在常驻或 REST 取到，示例 `4h,1d,1w` |
| `SQUARE_POST_COOLDOWN_HOURS` 及 `SQUARE_POST_SETUP_*` / `TOUCH_*` / `MOVE_*` / `RECAP_*` / `ERIC_*` | 各触发源开关与冷却，见示例文件 |
| `SQUARE_POST_COMPACT` / `SQUARE_POST_AI_POLISH` | 短讯；发帖前润色并强制保留标签与 CTA |
| `SQUARE_POST_CHART_ENABLED` 与宽高、K 线根数 | 配图。依赖 Playwright |
| `X_BEARER_TOKEN` | 仅 `scripts/fetch_reference_tweets.py` 使用，X Developer Bearer，不是 LLM key |

---

## 策略库

```bash
analyst strategies
```

| ID | 说明 | 回测 |
|----|------|------|
| `cycle_switch` | 减半日历 × 200 日线双确认。牛市唐奇安只多；熊市反弹做空半仓。盯盘在配置周期收盘评估仓位 | `analyst backtest-classic BTC -s cycle_switch --days 1825` |
| `xs_momentum` | 多币动量：做多最强 top 2，熊市可空最弱。约每周调仓 | `analyst backtest-xs --days 1825` |
| `funding_carry` | Delta 中性：现货多 + 永续空，收资金费。负费率期离场。实盘需要对冲账户，这里只做信号和回测 | `analyst backtest-carry BTC --days 1825` |

规则命中率是另一条命令，和组合回测不是同一套：

```bash
analyst backtest BTC -t 15m --bars 1000
analyst backtest SOL -t 1h --bars 1500 --json r.json
```

用与实时盯盘相同的规则，在历史 K 线上做 ATR 屏障前瞻，输出样本数、命中率、平均前瞻收益。命中率约 50% 表示该规则单独使用没有优势。

经典组合回测含单边手续费与滑点、复利、牛熊分段、样本外，以及滚动窗口、成本敏感度、Deflated Sharpe、PBO：

```bash
analyst backtest-classic BTC -s cycle_switch --days 1825
analyst backtest-classic BTC -s buy_hold --days 1825
```

Web「回测」页与 `backtest-classic` 同源。可选策略：`cycle_switch`、`buy_hold`。横截面与资金费套利走上面的专用命令。

样本很少、或日历边界贴合历史时，读数要保守。加密市场里裸做空腿经常拖累收益；`cycle_switch` 只在熊市用反弹做空。

---

## CLI

`analyst` 不加参数会列出命令。

| 命令 | 作用 |
|------|------|
| `analyst web [--lan] [--port 8000]` | Web + 常驻盯盘 + 日程 / 日报 / 新闻 / 现货雷达 |
| `analyst practice BTC [--tf 4h]` | 拉多周期数据，AI 出计划并落库 |
| `analyst verify` | 验证已到期会话 |
| `analyst history` / `analyst review <id>` | 历史列表 / 单条复盘 |
| `analyst progress` / `weakness` / `ai-benchmark` | 统计与模型对照 |
| `analyst backtest <symbol>` | 规则告警前瞻命中率 |
| `analyst backtest-classic <symbol> -s cycle_switch\|buy_hold` | 经典组合回测 |
| `analyst backtest-xs` / `backtest-carry <symbol>` | 横截面动量 / 资金费套利 |
| `analyst cycle-outlook [--telegram]` | 终端看刻舟求剑与狼波；可顺手推 TG |
| `analyst cycle-status [BTC,ETH,SOL,BNB]` | 执行相位 + 各币目标仓位 |
| `analyst digest [--send]` | 生成日报，`--send` 推 Telegram |
| `analyst research-ideas` | 生成研究假设 |
| `analyst square-post [--publish --text '...']` | 预览或真发广场短评 |
| `analyst strategies` | 策略目录 |
| `analyst config show` / `config test-llm` | 打印配置（密钥打码）/ 测 LLM |
| `analyst lang [zh\|en]` | 查看 / 设置全局输出语言 |
| `analyst db init` / `db backup` | 建库 / 备份 sqlite |
| `analyst data status` / `data refresh BTC` | 缓存占用 / 强制刷新该品种各周期 |

---

## 本地会生成什么

| 路径 | 内容 |
|------|------|
| `analyst.db` | AI 会话、计划、验证、聊天 |
| `ohlcv.sqlite` | 回测用的本地 K 线与缺 bar 检查 |
| `.cache/data/monitor_daemon.json` | 常驻盯盘品种（页面观察列表可写回） |
| `.cache/data/price_alerts.json` | 价格告警 |
| `.cache/data/paper_state.json` | 纸面权益、持仓、挂单、日志 |
| `.cache/data/schedule_reminders.json` | 日程提醒去重 |
| `.cache/data/cycle_outlook_tg.json` | 周期日更的日期戳 |
| `.cache/data/ai_confirm_cooldown.json` | AI 候选冷却 |
| `.cache/data/daily_digest_state.json` / `last_digest.json` / `last_research.json` | 日报调度与最近一份日报、研究假设 |
| `.cache/data/news_events.json` / `news_sentinel_seen.json` | 新闻分级结果与已读去重 |
| `.cache/data/square_regime_cooldown.json` | 广场发帖冷却 |
| `.cache/data/eric_swing_state.json` | Eric 波段计划状态 |
| `.cache/data/ui_settings.json` | 全局输出语言 |
| `.cache/data/` | 其余 REST 短缓存，可删 |
| `.env` / `.venv/` / `.logs/` | 密钥、虚拟环境、日志（已 gitignore） |

实时 WS K 线只在内存里滚动，不当历史库。删 `.cache/data` 会丢掉价格告警、纸面账本和冷却状态，数据库里的分析会话还在。

---

## 开发

```bash
uv sync --extra web --extra dev
pytest tests/ -q
python scripts/generate_favicon.py   # 重新生成图标
```

```
crypto-analyst/
├── prompts/                 # v1 完整提示词 / groq 短版
├── scripts/run-web.sh
├── src/analyst/
│   ├── cli.py               # analyst 命令
│   ├── config.py            # 环境变量
│   ├── backtest/            # 规则回放与经典组合回测
│   ├── compute/             # 指标、锁点、三盘、周期、策略、头仓
│   ├── exec/paper.py        # 纸面撮合
│   ├── llm/                 # 分析、日报、研究假设
│   ├── monitor/             # 盯盘 hub、规则、雷达、新闻、日程、广场
│   └── web/                 # FastAPI + 单页前端（static/i18n.js 为英文词典）
└── tests/
```

常用 API：

| 方法 | 路径 | 作用 |
|------|------|------|
| GET | `/api/health` `/api/config` | 存活、当前公开配置 |
| GET | `/api/monitor/symbols` `/api/monitor/levels` `/api/monitor/alerts` | 观察列表、关键位、告警 |
| GET | `/api/monitor/cycle-timeline` | 周期页数据 |
| GET | `/api/schedule?tz=Asia/Dubai` | 日程 |
| GET/POST | `/api/spot-radar` `/api/spot-radar/scan` | 雷达快照 / 立刻扫一轮 |
| GET | `/api/paper/summary` | 纸面持仓与统计 |
| GET/POST | `/api/price-alerts` | 价格告警 |
| GET | `/api/monitor/digest` `/api/monitor/research-ideas` `/api/monitor/news-events` | 日报、假设、新闻。加 `?refresh=1` 重新生成前两者 |
| POST | `/api/backtest/classic` | 与回测页相同的组合回测 |
| POST | `/api/monitor/analyze` `/api/monitor/chat` | 手动 AI 分析 / 追问；body 字段 `lang`（`zh` / `en`）可覆盖回答语言，不传则跟随全局语言 |
| GET/POST | `/api/settings/lang` | 读取 / 设置全局输出语言（`{"lang": "en"}`） |
| WS | `/api/monitor/ws` | 实时 K 线与告警 |

---

## 说明

- 不连接下单接口。盈亏与决策自负。纸面结果含简化的费率与滑点假设，不能代替实盘。
- 周期日历是「刻舟求剑」模型，里程碑日期有贴合历史的风险，要和当下盘面一起看。
- 波段锁点、三盘打法、Eric 规则都是结构或统计启发式，不是对任何公开交易笔记的复刻保证。
- 自动发到币安广场的内容会公开。先用 `analyst square-post` 看文案，确认 key 与品种后再开 `SQUARE_POST_ENABLED`。

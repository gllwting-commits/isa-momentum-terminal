# ISA MOMENTUM TERMINAL — CLAUDE.md
# Read this at the start of every session before writing any code.

## PROJECT
Stack: Python · Dash · yfinance · Render · GitHub
File: app.py (or whatever your main file is called)
Repo: github.com/gllwting-commits/isa-momentum-terminal
Live: isa-momentum-terminal.onrender.com

## FOUR RULES (NON-NEGOTIABLE)
1. Ask before assuming. If intent, architecture, or requirements
   are unclear, ask one question before writing a single line.
2. Simplest solution first. No abstractions or flexibility
   not explicitly requested.
3. Do not touch unrelated code. If a function or variable is
   not part of the current task, do not modify it.
4. Flag uncertainty explicitly. If not confident about an
   approach or technical detail, say so before proceeding.

## PERMANENT ARCHITECTURAL FACTS
These are decided. Do not re-derive them. Do not suggest alternatives
unless asked.

### GBp vs GBP CONVERSION (CRITICAL)
Tickers reporting in PENCE (divide by 100 at fetch, once only):
  SEMG.L, SGLS.L, EQQQ.L, SWDA.L

Tickers reporting in GBP pounds (no conversion):
  JEDG.L, VDPG.L, VAPX.L, SEMI.L

Tickers reporting in USD (no conversion):
  WTAI.L, FLXK.L

Rule: currency check is done in fetch_data() via currency == 'GBp'.
Applied once at fetch. All downstream receives already-converted values.
Do not convert again anywhere else.

### BENCHMARK PAIRS (DECIDED — DO NOT CHANGE WITHOUT ASKING)
SEMG: SOXX    (div)  — USD bench ÷ GBPUSD → GBP
SEMI: SOXX    (div)  — USD bench ÷ GBPUSD → GBP
WTAI: EQQQ.L  (mul)  — GBP bench × GBPUSD → USD
JEDG: UFO     (div)  — USD bench ÷ GBPUSD → GBP
SGLS: IGLN.L  (div)  — USD bench ÷ GBPUSD → GBP
VDPG: VAPX.L  (None) — both GBP, straight division
FLXK: EWY     (None) — both USD, straight division

### RS TREND RULES
- 30-day normalised percentage change of ratio series
- Deadband ±1.5% = neutral (amber). Applied to RS TREND only.
- Day% has NO deadband — pure sign-based colour.
- FX cancels in ratio-of-ratios. Trend is FX-neutral.

### 52W DRAWDOWN RULE
- ALWAYS use df['High'].max() — never df['Close'].max()
- Close.max() resets to 0% when new closing high is hit
- High.max() uses true intraday peak — immune to this error

### VARIABLE NAMING (CRITICAL — PREVENTS BUG 4)
day_color and day_arrow are RESERVED for Day% column only.
Never use chg_color or arrow as generic names — they get
clobbered by RSI delta and RS trend logic downstream.
Each column's colour/arrow variables must use a unique prefix:
  Day%:        day_color, day_arrow
  RSI delta:   rsi_color, rsi_arrow
  RS Trend:    rs_color, rs_arrow
  52W DD:      dd_color, dd_arrow

### FETCH ARCHITECTURE
fetch_intraday(ticker): runs every 60s during market hours
  - period='1d' interval='1m'
  - Returns: current_price, day_pct, intraday_volume
  - Uses fast_info.last_price for live price
  - Falls back to EOD outside 08:00-16:35 London time

fetch_daily(ticker): runs ONCE at startup, cached until midnight
  - period='1y' interval='1d'
  - Returns: RSI+delta, SMA20/50, 52W drawdown, RS trend 30d
  - RSI and SMA MUST stay on daily data. Intraday RSI is noise.
  - Do NOT move any of these calculations to intraday fetch.

### GBPUSD
_get_gbpusd() caches the rate for 5 minutes.
Do not re-fetch per row or per ticker. Cache is intentional.

### VOLUME DISPLAY
Before 14:00 London: ~ prefix + tooltip (partial session)
After 14:00 London: clean number (full-day projection reliable)
IWMO and SGLS show — (dash) for volume. This is intentional.

### PREVIOUS CLOSE
Use df['Close'].iloc[-2] — NOT fast_info.previous_close
fast_info.previous_close is unreliable across bank holidays.

### CHARTS TAB
Three chart modes: Price (normalised), RSI 14, Volume.
Ticker colour palette (fixed — do not reassign):
  JEDG  #ef4444  solid     SEMG  #22d3ee  solid
  SEMI  #6366f1  dashed    VDPG  #84cc16  solid
  WTAI  #facc15  dashed    SGLS  #f59e0b  solid
  FLXK  #e879f9  solid     SPX   #94a3b8  solid
  NDQ   #f97316  dashed
Benchmarks: SPX (^GSPC), NDQ (^IXIC) via fetch_benchmark_price().
Timeframe bar counts (all sliced from daily cache):
  1W=5, 1M=21, 3M=63, 6M=126, 1Y=252
All data served from _get_daily_df daily cache — no new fetches.

### SNAPSHOT STATS
4 stat rows per ETF: RSI 14 · 52W DD / Period Return ·
  RS Trend / RS vs Benchmark · Day%
Timeframe toggle: 1D / 1W / 1M / 3M / 6M / 1Y
  Independent of the main chart timeframe toggle.
1D mode:     RSI + 52W DD + RS 30d + Day%
Non-1D mode: RSI + Period Return % + RS vs Benchmark
             (Day% hidden on non-1D)
Background colour: #f0f4ff — do not change.
Implementation: pure html.Div components — no Plotly figures.
State stored in: dcc.Store(id='snapshot-tf', data='1d')

### THEME SYSTEM
7 themes in THEMES dict (top of app.py):
  Slate (default), Dusk, Carbon, Midnight,
  Terminal, Alpine, Parchment
Selection widget: dcc.Dropdown(id='theme-dropdown') in header.
apply_theme callback outputs style to these IDs only:
  app-root, header-bar, tabs-bar, macro-regime-strip
Card interiors stay Slate — full propagation deferred.
Do not thread theme into builder functions without asking first.

### SIGNAL TABLE
Sort options: Day% (default), WT%, RS 30d, RSI, 52W DD.
Row left border: action-based only.
  Exit / reduce = 3px solid RED
  Trim          = 3px solid AMBER
  All others    = transparent (no border)
  (Replaces old conviction-based border — do not revert.)
Sparkline: 15-day SVG, 70×22 px, rendered inline in ETF cell.

### RADAR TAB
Watchlist constants at top of app.py (near ETF_NAMES):
  WATCHLIST         — ordered list of short names
  WATCHLIST_TICKERS — short name → full ticker string
  WATCHLIST_NAMES   — short name → display name

Watchlist tickers (all verified live in yfinance):
  AIAI.L  USD    ISPY.L  GBp (÷100 via _get_daily_df)
  INRG.L  GBp    NUKZ.L  USD
  NATO.L  USD    ROBO.L  USD
  RBTX.L  GBp    EMQQ.L  USD
  NDIA.L  USD    HEAL.L  USD

GBp conversion for ISPY.L, INRG.L, RBTX.L handled
  automatically by _get_daily_df() currency check.
  Do NOT add these to the manual pence list — conversion
  is already applied at fetch.

RS benchmark for all radar tickers: SWDA.L
  SWDA.L is GBp — already in pence list.

Signal criteria (ALL THREE must be true):
  1. RSI crossed above 60 in last 5 days
     rsi_s.iloc[-1] > 60 and min(rsi_s.iloc[-6:-1]) < 60
  2. RS vs SWDA.L 30d > +1.5%
  3. 52W drawdown > -15%

fetch_radar_ticker(ticker_str) — new function
  Reads _get_daily_df() cache — no new fetch if cached.
  Wrapped in try/except — returns None on any failure.
  Do NOT call fetch_daily() for radar tickers.
  Do NOT add radar tickers to main ETFS list.

build_radar_table(rows) — new function
  Simple html.Table. Placed before render_tab().

Radar tab fires via existing render_tab() router.
  No new callback, no new dcc.Interval, no new dcc.Store.
  Repeat tab visits within same day = cache hits, no refetch.

## BEFORE ADDING ANY NEW LSE TICKER
1. Verify currency denomination in yfinance
2. Check if it reports GBp or GBP
3. Update the GBp conversion list above if needed
4. Verify yfinance ticker string pulls live data before using

## BEHAVIOUR AT SESSION END
When wrapping up, produce a brief summary of:
- What was changed and in which functions
- What was intentionally not touched
- Any uncertainty or follow-up needed
Add this to MEMORY.md under today's date.

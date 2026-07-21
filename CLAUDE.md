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
  VDPG.L, VAPX.L, SEMI.L

Tickers reporting in USD (no conversion):
  WTAI.L, FLXK.L

Rule: currency check is done in fetch_data() via currency == 'GBp'.
Applied once at fetch. All downstream receives already-converted values.
Do not convert again anywhere else.

### BENCHMARK PAIRS (DECIDED — DO NOT CHANGE WITHOUT ASKING)
SEMG: SOXX    (div)  — USD bench ÷ GBPUSD → GBP
SEMI: SOXX    (div)  — USD bench ÷ GBPUSD → GBP
WTAI: EQQQ.L  (mul)  — GBP bench × GBPUSD → USD
SGLS: IGLN.L  (div)  — USD bench ÷ GBPUSD → GBP
VDPG: VAPX.L  (None) — both GBP, straight division
FLXK: EWY     (None) — both USD, straight division

### RS-TILT RANKING BASIS (added 2026-07-21)
The RS-TILT allocation engine ranks all 15 tracked names (5 holdings
  ex-SGLS: SEMG/SEMI/WTAI/VDPG/FLXK, + 10 radar names) on one common
  metric: rs_vs_swda(ticker, lookback=31) — RS vs SWDA.L (iShares MSCI
  World), fixed 31-trading-day offset (radar's existing convention).
The per-sector pairs above are UNCHANGED and continue to feed the RS
  TREND 30d display only (fetch_rs_ratio/fetch_rs_persist/fetch_rs_flips,
  calendar-cutoff convention). They are not used for ranking. This is a
  new, separate metric added alongside them — not a repurposing of the
  "DO NOT CHANGE WITHOUT ASKING" pairs above.
SGLS is excluded from the 15 — held (hedged), zero new cash, per the
  2026-07-04 SGLS Position Review resolution.

### RS-TILT ALLOCATION ENGINE (added 2026-07-21, Feature B — DECIDED)
allocate_tilt(monthly_gbp=3000.0, last_split=None) -> dict, app.py, inserted
  after rs_vs_swda. Pure function, no UI wiring yet.
Pool: RS_TILT_POOL (the 15 names above). Weights: RS_TILT_TOP_WEIGHTS =
  [0.60, 0.30, 0.10], winner-take-most across the top 3 by rs_vs_swda.
£3,000/month default is a separate, configurable parameter — NOT
  MONTHLY_INVEST (=1,667), which is the unrelated ISA & Retirement
  growth-projection default. Do not conflate or reuse one for the other.
Four status states in the return dict, always present, mutually exclusive:
  'ok' (>=3 valid names) / 'reduced' (1-2 valid, weights renormalised to
  sum to 1.0) / 'fallback' (0 valid, last_split echoed back) /
  'unavailable' (0 valid, no last_split). All-negative-RS month is not a
  branch — least-bad top 3 still funds naturally via the sort (mandate:
  always deploy, momentum sizes not gates). £ amounts are full-precision
  floats, not rounded — display rounding is Feature C's concern.

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
  Entry Watch: entry_watch_

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

_get_sox_1y() / _sox_1y_cache: 24h TTL, separate cache dict (same pattern
  as _get_tnx_1y() / _tnx_1y_cache).
  - ^SOX primary, SOXX fallback — same fallback order as the macro strip's
    existing 3mo SOX display fetch, but resolved independently (own fetch,
    own cache). The two can diverge on ticker in a rare double-failover
    window — accepted edge case, not coded around.
  - Breach (last close vs 200d SMA) computed entirely within this single
    1y series — never assembled by comparing against the 3mo display price.
  - Feeds one additive 'sox_ma_breach' key into fetch_macro_regime()'s
    result. Display only — not scored into the regime.
  - Renders as a red "SOX < 200d" tag in build_macro_strip(), next to the
    existing SOX value. Shows nothing when above the SMA or on fetch
    failure — no muted/placeholder state.
  - Variable prefix sox_ma_ is reserved for this feature.

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
  SEMG  #22d3ee  solid     SEMI  #6366f1  dashed
  VDPG  #84cc16  solid     WTAI  #facc15  dashed
  SGLS  #f59e0b  solid     FLXK  #e879f9  solid
  SPX   #94a3b8  solid     NDQ   #f97316  dashed
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
  No new dcc.Interval. Repeat tab visits = cache hits, no refetch.

### RADAR PIN TO CHARTS
dcc.Store(id='radar-pinned', data=[]) — session-only, resets on refresh.
  Do NOT persist across sessions. This is intentional.

toggle_pin_radar callback:
  Input({'type':'pin-radar','index':ALL},'n_clicks') — MUST use ALL wildcard.
  Do NOT use explicit per-ticker Inputs — buttons are dynamically rendered,
  so non-signal rows have no button. Explicit IDs for missing components
  silently kill the callback.
  Uses ctx.triggered_id['index'] for extraction — NOT string prop_id parsing.

build_radar_table(rows, pin_pinned=[]):
  pin_worthy = rsi_cross OR rs_30d > +1.5% OR drawdown > -15% (any one).
  ✓ ENTRY text + green border: still requires ALL THREE conditions.
  Partial signal row: ＋ Charts button only, no ✓ ENTRY text.
  Pinned row: button shows ✕ Remove.

render_tab(): Input('radar-pinned','data') added — re-fires on pin/unpin.
  Passes pin_pinned to build_radar_table() to update button state.

update_price_chart() and update_chart_snapshot():
  Both have Input('radar-pinned','data').
  Pinned tickers appended to rsi_data/vol_data/price_data BEFORE sort.
  All pinned tickers: colour #a78bfa (soft purple), solid line.
  Snapshot: RSI, 1D dd/rs/day, multi-TF pret/rsp all include pinned rows.
  Multi-TF RS for pinned tickers: ETF period return − SWDA period return.
  No conviction card rendered for pinned radar tickers.
  Do NOT use CHART_COLORS for pinned tickers — use #a78bfa only.

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

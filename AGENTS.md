# ISA MOMENTUM TERMINAL — AGENTS.md
# Coding instructions for AI agents (Stitch, Claude Code, Cursor, Gemini CLI).
# Read this alongside DESIGN.md and CLAUDE.md before writing any code.

## PROJECT IDENTITY

**ISA Momentum Terminal** — a Python/Dash financial dashboard deployed on Render (free tier).
- Main file: `app.py`
- Repo: github.com/gllwting-commits/isa-momentum-terminal
- Live URL: isa-momentum-terminal.onrender.com
- Stack: Python · Dash · Plotly · yfinance · Render · GitHub

This is a single-file application. All layout, callbacks, and styling live in `app.py`.
There is no separate CSS file, no Tailwind, no component library. All styles are Python dicts
passed as `style=` props to Dash HTML components.

---

## DESIGN SYSTEM IMPLEMENTATION

All visual tokens are defined in `DESIGN.md`. The dashboard's `THEMES` dict at the top of
`app.py` maps these tokens. The active theme at runtime is `Slate` (the default). When
implementing visual changes, always reference DESIGN.md tokens and translate them to the
equivalent Slate theme key or inline `style={}` dict.

### Token → Python Style Translation

```python
# DESIGN.md token → Python dict equivalent
# colors.background  → {'backgroundColor': '#0a0c10'}
# colors.card        → {'backgroundColor': '#141720'}
# colors.accent      → {'color': '#5b8dee'}
# colors.green       → {'color': '#22c55e'}
# colors.red         → {'color': '#ef4444'}
# colors.amber       → {'color': '#f59e0b'}
# colors.text        → {'color': '#e2e8f4'}
# colors.text-secondary → {'color': '#8892aa'}
# colors.text-muted  → {'color': '#4a5270'}
# typography.data-primary → {'fontFamily': "'JetBrains Mono', 'Fira Mono', monospace",
#                            'fontSize': '15px', 'fontWeight': '500'}
# typography.data-secondary → {'fontFamily': "'JetBrains Mono', 'Fira Mono', monospace",
#                              'fontSize': '11px', 'fontWeight': '400'}
# typography.label   → {'fontFamily': 'Inter, system-ui, sans-serif',
#                        'fontSize': '10px', 'fontWeight': '600',
#                        'letterSpacing': '0.08em', 'textTransform': 'uppercase'}
```

---

## ARCHITECTURAL CONSTRAINTS — READ BEFORE TOUCHING ANYTHING

These are permanent decisions. Do not re-derive, do not suggest alternatives.

### NEVER TOUCH THESE FUNCTIONS
- `fetch_daily(ticker)` — daily OHLCV + RSI + SMA + drawdown + RS trend
- `fetch_intraday(ticker)` — live price + day% + volume
- `_get_daily_df(ticker)` — daily cache accessor
- `build_summary_table(rows)` — the signal table renderer
- `fetch_benchmark_price()` — chart benchmark data
- All benchmark logic inside `fetch_daily()`
- `RS_BENCHMARKS` dict — benchmark pairs are decided
- GBp/GBP conversion logic inside `fetch_data()` / `_get_daily_df()`
- All existing callback `Output()` and `Input()` registrations
- `_get_gbpusd()` — FX cache
- `_signal_history` dict — in-memory signal age tracking

If you need to change any of these, stop and ask first.

### BANNED VARIABLE NAMES
- `chg_color` — clobbered by downstream RSI/RS logic; use `day_color` for Day%
- `arrow` — clobbered by downstream logic; use prefixed names

### VARIABLE PREFIX RULES (MUST FOLLOW)
Every column's colour and arrow variables must use a unique prefix:
- Day%: `day_color`, `day_arrow`
- RSI delta: `rsi_color`, `rsi_arrow`
- RS Trend: `rs_color`, `rs_arrow`
- 52W DD: `dd_color`, `dd_arrow`
- SMA extension: `sma_ext_color`
- Rate beta: `rate_beta_` prefix

New features must declare their prefix before implementation.

### GBp vs GBP CONVERSION — CRITICAL
Tickers reporting in pence (divide by 100 at fetch, once only):
`SEMG.L, SGLS.L, EQQQ.L, SWDA.L, ISPY.L, INRG.L, RBTX.L`

Tickers reporting in GBP pounds (no conversion):
`JEDG.L, VDPG.L, VAPX.L, SEMI.L`

Tickers reporting in USD (no conversion):
`WTAI.L, FLXK.L`

Rule: conversion is done once at fetch via `currency == 'GBp'` check.
Do NOT convert again anywhere downstream. Do NOT add new tickers to the pence list
without verifying `fast_info.currency` in yfinance first.

### FETCH ARCHITECTURE
Two separate fetch paths — do not merge them:

1. `fetch_intraday(ticker)` — runs every 60s during market hours (08:00–16:35 London).
   Returns: `current_price`, `day_pct`, `intraday_volume`.
   Uses `fast_info.last_price` for live price.
   Falls back to EOD outside market hours.

2. `fetch_daily(ticker)` — runs ONCE at startup, cached until midnight.
   Returns: RSI+delta, SMA20/50, 52W drawdown, RS trend 30d, rate beta.
   RSI and SMA MUST stay on daily data. Intraday RSI is noise.

Do NOT add new `yfinance` fetches without explicit approval.
Do NOT move any daily calculations into the intraday fetch.

### PREVIOUS CLOSE
Use `df['Close'].iloc[-2]` — NOT `fast_info.previous_close`.
`fast_info.previous_close` is unreliable across bank holidays.

### 52W DRAWDOWN
ALWAYS use `df['High'].max()` — never `df['Close'].max()`.
Close.max() returns 0% drawdown on new closing high days.

### TIMEZONE
London timezone uses `pytz.timezone('Europe/London')` — NOT `ZoneInfo`.
`pytz` is in `requirements.txt`. Do not switch back to ZoneInfo.

### PREVIOUS CLOSE EOD
`close_s = df['Close'].dropna()` is the source for `close_eod` and `prev_eod`.
Guards against trailing NaN rows from yfinance weekend partial bars.

---

## VISUAL CHANGE RULES

When implementing a design change from DESIGN.md:

1. **Identify the exact component** — which function builds it? (`build_summary_table`,
   `build_macro_strip`, `build_radar_table`, `update_price_chart`, etc.)
2. **Change only that function.** Do not touch adjacent functions.
3. **Use a unique variable prefix** for any new colour/arrow variable you introduce.
4. **Monospace all numbers.** Every numeric value in every cell must use
   `fontFamily: "'JetBrains Mono', 'Fira Mono', monospace"`.
5. **Semantic colour only.** Do not introduce a new colour that isn't in DESIGN.md.
6. **Max border-radius: 8px.** No exceptions.
7. **No horizontal scroll at ≥1200px.** Test column widths if touching table layout.

---

## SIGNAL TABLE COLUMN SPECS

For reference when implementing visual changes to `build_summary_table()`:

| Column | Width | Align | Font | Notes |
|---|---|---|---|---|
| ETF | ~180px | left | Inter body + mono for ticker | sparkline 70×22px inline |
| PRICE/Day% | 110px | right | data-primary (price) + data-secondary (day%) | arrow + colour on day% |
| VOLUME | 90px | right | data-secondary | flag emoji prefix, ~ before 14:00 |
| CONVICTION | 90px | center | label (badge) | age stamp below in text-muted |
| ACTION | 90px | center | body | age stamp below in text-muted |
| ENTRY AT | 80px | center | body | SMA20/SMA50/Avoid |
| RSI 14 | 90px | right | data-primary + data-secondary | value / delta, colour on delta |
| SMA POSITION | 120px | right | data-secondary | two values + label + % from SMA50 |
| 52W DRAWDOWN | 90px | right | data-primary | colour thresholds: 0% green, -5% amber, -15% red |
| RS TREND 30d | 110px | right | data-secondary | persist Nd + flip count + beta |

---

## RADAR TAB CONSTRAINTS

- `WATCHLIST`, `WATCHLIST_TICKERS`, `WATCHLIST_NAMES` constants — do not modify
- `fetch_radar_ticker()` must use `_get_daily_df()` cache — no new yfinance calls
- `build_radar_table(rows, pin_pinned=[])` — do not change function signature
- `toggle_pin_radar` callback uses `Input({'type':'pin-radar','index':ALL},'n_clicks')` — ALL wildcard mandatory
- Pinned tickers always use colour `#a78bfa` (purple) — never CHART_COLORS

---

## CHARTS TAB CONSTRAINTS

CHART_COLORS palette is fixed — do not reassign:
```python
CHART_COLORS = {
    'JEDG':  '#ef4444',  # solid
    'SEMG':  '#22d3ee',  # solid
    'SEMI':  '#6366f1',  # dashed
    'VDPG':  '#84cc16',  # solid
    'WTAI':  '#facc15',  # dashed
    'SGLS':  '#f59e0b',  # solid
    'FLXK':  '#e879f9',  # solid
    'SPX':   '#94a3b8',  # solid
    'NDQ':   '#f97316',  # dashed
}
# Pinned radar tickers: #a78bfa (purple) — not in CHART_COLORS
```

Timeframe bar counts (sliced from daily cache — no new fetches):
`1W=5, 1M=21, 3M=63, 6M=126, 1Y=252`

---

## MACRO STRIP CONSTRAINTS

Tickers: `^TNX` (US10Y), `^VIX`, `UUP` (DXY proxy — display label is "DXY"), `^SOX` (display only)
Fallbacks: `^TNX` → TLT (inverted); `^SOX` → SOXX
Regime scoring: 3 inputs only (US10Y, VIX, DXY). SOX is NOT scored.
`_macro_cache` TTL: 60 minutes. Separate from `_tnx_1y_cache` (24h).
Fetch failure: shows `N/A` in text-muted. Never triggers CAUTION falsely.

---

## THEME SYSTEM

7 themes in `THEMES` dict: Slate (default), Dusk, Carbon, Midnight, Terminal, Alpine, Parchment.
`apply_theme` callback outputs style to IDs: `app-root`, `header-bar`, `tabs-bar`, `macro-regime-strip`.
Card interiors are NOT theme-propagated yet — they stay Slate colours.
Do NOT thread theme into `build_summary_table()` or other builders without explicit approval.

---

## TASK FORMAT

When given a design task, respond with:

1. **Which function(s) will be modified** — name them explicitly
2. **Which functions will NOT be touched** — name them explicitly
3. **Variable prefix for any new colour/arrow variables**
4. **The diff** — show the exact lines changing before writing any code
5. **Verification step** — what to look for in the browser

Never start writing code before completing steps 1–3.

---

## WRAPPING UP

At end of every session:
1. Update `MEMORY.md` with what changed, which functions were modified, what was not touched
2. Update `CLAUDE.md` if any architectural facts changed
3. Update `VERSION` file with new version number
4. Commit all three with message matching version: `v1.X.Y — [description]`
5. `git push origin main`
6. Confirm push succeeded before ending session

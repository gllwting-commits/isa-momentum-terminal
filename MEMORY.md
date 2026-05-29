# ISA MOMENTUM TERMINAL — MEMORY.md
# Updated at end of each session. Read at start of each session.

## DECISIONS LOG
What was decided, why, and what was rejected.

### 2026-05-28 — v1.0 to v1.7 session
DECIDED: GC=F rejected as SGLS benchmark.
  Reason: full oz futures contract vs fractional ETC share
  is not like-for-like regardless of price level.
  Replaced with IGLN.L (iShares Physical Gold ETC, unhedged).

DECIDED: df['High'].max() for 52W drawdown, not df['Close'].max().
  Reason: Close.max() returns 0% drawdown on days ETF closes
  at new 52W closing high. High.max() uses true intraday peak.

DECIDED: day_color/day_arrow as reserved variable names for Day%.
  Reason: chg_color and arrow were being silently overwritten
  by RSI delta logic at line 821 and RS trend at line 869.

DECIDED: ARKK rejected as JEDG benchmark.
  Reason: ARKK is US active growth fund, no space mandate.
  UFO (Procure Space ETF) is the only liquid thematic peer.

DECIDED: fetch_daily / fetch_intraday split.
  Reason: Reduced yfinance downloads from 21 to 7 per 60s cycle.
  RSI and SMA must stay on daily data — intraday versions are noise.

DECIDED: fast_info.previous_close rejected for Day% calculation.
  Reason: spans bank holidays incorrectly, produces wrong values.
  Replaced with df['Close'].iloc[-2].

## ERRORS LOG
What failed after two attempts, what worked instead.

### 2026-05-28
FAILED: Using raw RS ratio as a column value.
  Problem: 0.2304 is meaningless as a standalone number.
  Worked instead: RS TREND 30d — percentage change of ratio
  over 30 days, normalised to day-0=100.

FAILED: Generic variable names for colour/arrow across columns.
  Problem: Later column logic overwrites earlier column variables.
  Worked instead: Unique prefixed names per column (see CLAUDE.md).

FAILED: df['Close'].max() for 52W high.
  Problem: Returns 0% drawdown on new closing high days.
  Worked instead: df['High'].max().

## CURRENT STATE
Version: v1.8.0 (code correct on disk — rendering issue unresolved, see below)
Dashboard columns (intended): ETF, PRICE/Day%, VOLUME,
CONVICTION (+ grey age stamp), ACTION (+ grey age stamp),
ENTRY AT, RSI 14, SMA POSITION, 52W DRAWDOWN, RS TREND 30d.
SIGNAL CHANGED column removed in v1.8.0 code.

### 2026-05-28 — v1.8.0 session
BUILT: Removed SIGNAL CHANGED column from headers list (10 cols, not 11).
BUILT: _signal_history now tracks conviction and action independently,
  each with their own datetime timestamp.
BUILT: _update_signal_history(etf, conviction, action) returns
  (conv_age, action_age) tuple.
BUILT: _format_age() buckets elapsed days into:
  today / Nd ago / 1w ago / 2w ago / 1m ago / 2m ago / 3m+ ago.
BUILT: conv_cell and action_cell each render a grey Div(age) below
  the badge/text. Falls back to "unknown" if no history entry.
NOT TOUCHED: fetch_intraday, fetch_daily, benchmarks, GBp conversion,
  all other columns.

### 2026-05-28 — UNRESOLVED RENDERING ISSUE
PROBLEM: Browser shows old layout (SIGNAL CHANGED column present,
  middle-dot in PRICE header) even after server restart.
CONFIRMED ON DISK:
  - grep finds zero occurrences of "SIGNAL CHANGED" in app.py
  - Line 740 reads 'PRICE / ' + period_label (slash, not middle dot)
  - ast.parse confirms file is valid Python
  - Python inspect.getfile() confirms it loads C:\Users\User\isa-terminal\app.py
  - app.py is 67,900 bytes dated 3:45 PM, newer than any .pyc
  - __pycache__ was deleted and confirmed absent
SUSPECTED CAUSE: Dash component tree may be cached at import time or
  the Dash renderer is serving a stale client-side bundle. The layout
  function build_summary_table is called inside a callback, so it
  should re-execute on each refresh — but something is preventing the
  new column structure from reaching the browser.
NEXT SESSION: Investigate why Dash is not re-rendering the table
  layout on restart. Try: adding debug=True to see reload messages,
  checking if app_old.py is somehow still being imported, and
  verifying the callback output reaches the browser via DevTools
  Network tab (look for /_dash-update-component response body).

### 2026-05-29 — v1.9.0 session
BUILT: "⊟ Table" / "≡ Summary" sub-tab toggle inside Signal Summary card.
BUILT: _view_btn_style() helper — TAB_STYLE-matched bottom-border toggle buttons.
BUILT: build_summary_view() — Label/Vals inline ranked display.
  Ranked rows (sorted): Price/Day%, Volume, RSI 14, 52W DD, RS Trend (with bench label).
  Listed rows (chg_pct order): Conviction, Action (abbreviated), Entry At, SMA 20/50.
  Signal Age row: placeholder comment, not yet implemented.
  RSI coloring: >80 red, >70 amber, <30 red, <50 amber, 50–70 green.
  ETF ticker colors: Exit action = red, Watch/Monitor = blue (ACCENT), else TEXT.
BUILT: dcc.Store(id='summary-view', data='table') in app.layout.
BUILT: toggle_summary_view callback — btn clicks → Store.
BUILT: switch_summary_view callback (prevent_initial_call=True) — Store → display toggle.
BUILT: style_view_buttons callback — Store → button highlight state.
BUILT: update_signal_summary now accepts State('summary-view') — sets correct
  initial display on both containers so refresh doesn't reset view state.
  Both views always built; no extra fetches (all data cached in rows dict).
NOT TOUCHED: fetch_intraday, fetch_daily, fetch_rs_ratio, benchmarks,
  GBp conversion, FX logic, build_summary_table, all other columns.
UNRESOLVED (carried forward): v1.8.0 rendering issue (SIGNAL CHANGED column
  still visible in browser). Investigate DevTools Network tab for stale bundle.

### 2026-05-29 — pytz fix session
ROOT CAUSE: ZoneInfo requires the tzdata package to resolve named timezones
  on Linux (Render's runtime). tzdata was not in requirements.txt, so
  ZoneInfo('Europe/London') silently fell back to UTC. The _is_market_open()
  check compared UTC time against 08:00–16:35 — during BST (UTC+1) the window
  was effectively 09:00–17:35 UTC, meaning the 08:00–09:00 LSE open was always
  missed and fetch_intraday never ran intraday mode all day on the live server.

FIX:
  - Replaced `from zoneinfo import ZoneInfo` with `import pytz` (app.py import)
  - Replaced `_LONDON_TZ = ZoneInfo('Europe/London')` with
    `_LONDON_TZ = pytz.timezone('Europe/London')` (line ~259)
  - Added `pytz>=2024.1` to requirements.txt
  - All downstream calls `datetime.now(_LONDON_TZ)` unchanged — pytz timezone
    objects are drop-in replacements for ZoneInfo objects in datetime.now(tz).
  - Removed temporary [DEBUG] print after verification confirmed London hour=19
    vs UTC hour=18 with +1:00:00 offset (BST correct).

VERIFICATION PENDING: 2026-05-30 at 08:00 BST — confirm "Daily stats as of"
  timestamp in Signal Summary header updates, confirming intraday fetch fired.

NOT TOUCHED: fetch_daily, benchmarks, GBp conversion, column rendering,
  all calculation logic.

### 2026-05-29 — volume flag + RS persist session
BUILT: Volume direction flag — 🟢/🔴 emoji prepended to volume multiple
  based on data['chg_pct'] sign. Deadband ±0.1% = no flag.
  Flat/unavailable falls back gracefully (no flag, no crash).
  Variable prefix: vol_dir. Modified: build_summary_table volume cell only.

BUILT: fetch_rs_persist(etf) — counts consecutive days RS ratio moved
  in same direction using same _get_daily_df calls (cache hits, no new fetch).
  Returns ('pos', N) or ('neg', N), None if series < 2.
  Rendered as small grey "pos Nd" / "neg Nd" third line in RS TREND 30d cell.
  Variable prefix: rs_persist. Modified: fetch_rs_persist (new function),
  update loop (one line), build_summary_table RS cell only.

NOT TOUCHED: fetch_intraday, fetch_daily, benchmarks, GBp conversion,
  all other columns, function signatures.

### 2026-05-29 — RS flip counter + macro regime strip session
BUILT: fetch_rs_flips(etf) — counts direction sign changes in 30-day RS
  ratio diffs. Returns int (0+), None if series < 5 days. No new fetch.
  Rendered as fourth line in RS TREND cell:
    0-1 flips → "stable" (MUTED grey)
    2-3 flips → "🟡 N flips" (YELLOW)
    4+ flips  → "🔴 N flips" (RED)
  Variable prefix: rs_flips. Modified: fetch_rs_flips (new), update loop
  (one line), build_summary_table RS cell only.

BUILT: Macro regime strip — replaced TNX/TYX/SOX three-card panel entirely.
  REMOVED: fetch_macro_indicators, get_macro_status, _MACRO_META,
    build_macro_panel, _macro_threshold_reference, MACRO_STATUS_* dicts,
    macro-alert-panel div, update_macro_panel callback. All dead code deleted.
  ADDED: _macro_cache (60-min TTL, separate dict), fetch_macro_regime()
    fetches ^TNX, ^VIX, ^DXY (period='1mo' interval='1d').
    Scoring: US10Y falling=+1/rising=-1, VIX<20=+1/>=20=-1,
    DXY falling=+1/rising=-1. Total >=2 → RISK ON/LEANING ON (green),
    <=-2 → RISK OFF (red), else CAUTION (amber).
  ADDED: build_macro_strip() — compact flex strip with badge + three
    value+arrow spans, flexWrap for mobile, subtitle below.
  ADDED: macro-regime-strip div in layout, update_macro_strip callback.
  NOT TOUCHED: fetch_intraday, fetch_daily, ETF table, all columns.

## REMAINING BUILD ITEMS
1. ~~RESOLVED 2026-05-29~~: v1.8.0 rendering — SIGNAL CHANGED column
   no longer visible in browser. Fix confirmed.

2. Signal Age row in Summary view — awaiting persistent history scope.

3. Signal Audit Log — HIGH PRIORITY (partially done via v1.8)
   In-memory age stamps are now live. Full audit log would add
   persistent JSON, old→new transitions, price/RSI at change,
   and a dedicated Signal History tab.

4. SGLS Position Review — URGENT
   -21.6% drawdown while gold at USD ATH.
   Decision needed: keep SGLS hedged or switch to IGLN.L unhedged.

5. Correlation Heatmap — LOW PRIORITY
6. Vol-Adjusted Sizing — LOWEST PRIORITY (wrong tool for mandate)

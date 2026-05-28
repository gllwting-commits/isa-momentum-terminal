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

## REMAINING BUILD ITEMS
1. UNRESOLVED: v1.8.0 rendering — fix SIGNAL CHANGED column still
   showing in browser despite correct code on disk (see above).

2. Signal Audit Log — HIGH PRIORITY (partially done via v1.8)
   In-memory age stamps are now live. Full audit log would add
   persistent JSON, old→new transitions, price/RSI at change,
   and a dedicated Signal History tab.

2. SGLS Position Review — URGENT
   -21.6% drawdown while gold at USD ATH.
   Decision needed: keep SGLS hedged or switch to IGLN.L unhedged.

3. Correlation Heatmap — LOW PRIORITY
4. Vol-Adjusted Sizing — LOWEST PRIORITY (wrong tool for mandate)

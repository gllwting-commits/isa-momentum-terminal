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
Version: v1.13.0
Dashboard columns: ETF, PRICE/Day%, VOLUME, CONVICTION (+ grey age stamp),
  ACTION (+ grey age stamp), ENTRY AT, RSI 14, SMA POSITION, 52W DRAWDOWN,
  RS TREND 30d (+ persist Nd + flip count).
Macro strip: RISK ON/LEANING ON/RISK OFF/CAUTION badge + US10Y, VIX, DXY, SOX.
  SOX display only — not scored. Fetch failure shows N/A in grey.
Portfolio: JEDG, SEMG, SEMI, VDPG, WTAI, SGLS, FLXK. IWMO removed.
  SEMI.L added 2026-05-30 (GBP, SOXX benchmark).
Outside-hours price: fast_info.last_price + regular_market_previous_close.
  Trailing NaN Close row stripped in fetch_daily() via df['Close'].dropna().

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
    fetches ^TNX, ^VIX, ^DXY (period='3mo' interval='1d').
    Scoring: US10Y falling=+1/rising=-1, VIX<20=+1/>=20=-1,
    DXY falling=+1/rising=-1. Total >=2 → RISK ON/LEANING ON (green),
    <=-2 → RISK OFF (red), else CAUTION (amber).
  ADDED: build_macro_strip() — compact flex strip with badge + three
    value+arrow spans, flexWrap for mobile, subtitle below.
  ADDED: macro-regime-strip div in layout, update_macro_strip callback.
  NOT TOUCHED: fetch_intraday, fetch_daily, ETF table, all columns.

FIXED (same session): macro strip data missing — ^TNX and ^DXY showing —→.
  ^TNX: now falls back to TLT price direction (inverted) if ^TNX feed dry.
  ^DXY: replaced with UUP (Invesco DB USD Bull ETF) — more reliable feed.
  Partial data: if < 3 inputs scored, regime = 'PARTIAL' → grey outlined
    "Macro data partial" badge instead of a false CAUTION.
  Modified: fetch_macro_regime() and badge span in build_macro_strip() only.

### /memory Render route — ABANDONED, DO NOT RETRY
Attempted: Flask route serving MEMORY.md as plain text at /memory
  inside the main Dash app, and as a standalone memory_server.py
  deployed as a separate Render service (isa-memory-server).
Failed reasons:
  1. Dash WSGI catch-all intercepts all unknown routes before Flask
     router runs — Flask routes unreachable inside Dash app.
  2. Claude cannot fetch arbitrary Render URLs due to fetch permission
     restrictions — even a working Render endpoint is not reachable
     by Claude at session start.
  3. raw.githubusercontent.com CDN caching problem remains — GitHub
     raw URL may serve a stale cached version of MEMORY.md.
Workaround: if MEMORY.md is stale at session start, user pastes it
  manually into the conversation.
NOTE: isa-memory-server on Render is deployed but unused — can be
  deleted. memory_server.py in repo can also be removed when ready.

### 2026-05-30 — SOX added to macro strip (v1.11.0) — VERIFICATION PENDING
BUILT: SOX (^SOX) added to macro panel header bar — display only, not scored.
  ^SOX primary, SOXX fallback (same pattern as ^TNX/TLT).
  Renders: label 'SOX:', price (integer format), trend arrow.
  Fetch failure shows N/A in MUTED grey — same rule as other macro tickers.
  Regime scoring logic (US10Y/VIX/DXY) completely untouched.
  Commit: c02964c. Modified: fetch_macro_regime(), build_macro_strip() only.
VERIFICATION PENDING: cross-check SOX value against TradingView Monday
  market open. Confirm value displays and arrow direction matches trend.

### 2026-05-30 — macro fetch robustness fix ✓ VERIFIED (US10Y 4.45% live)
FIXED: ^TNX returning no data with period='1mo' on weekends/holidays.
  _fetch(): changed period='1mo' → period='3mo' — more rows, less fragility.
  _dir(): changed len(df) < 2 → len(df) < 1 — single-row df now valid.
FIXED: fetch failure no longer changes regime label.
  macro_inputs_scored < 3 → reads prior cached regime instead of 'PARTIAL'.
FIXED: macro_val_span renders 'N/A' in MUTED grey for None values (not '—').
  Modified: fetch_macro_regime() and macro_val_span() in build_macro_strip().

FIXED (same session): fetch_rs_flips() noise — 8 raw flips vs 4 genuine.
  Root cause: day-to-day oscillations at 4th–5th decimal of RS ratio
    registered as flips (e.g. +0.000005 then -0.000001).
  Fix: apply 3-day rolling mean to RS ratio series before computing diffs.
    WTAI: 8 raw flips → 4 smoothed, current run pos 7d (verified correct).
  Modified: fetch_rs_flips() only — two lines added (rolling + dropna guard).

### 2026-05-30 — portfolio composition changes
REMOVED: IWMO from dashboard entirely — ETFS list, ETF_NAMES,
  RS_BENCHMARKS (was SWDA.L mul), both chart default fallbacks
  changed to JEDG. CLAUDE.md updated (removed from USD list
  and benchmark pairs).

ADDED: SEMI.L (iShares MSCI Global Semiconductors UCITS ETF)
  Currency: GBP (not GBp — no /100 conversion).
  Benchmark: SOXX (div) — USD bench ÷ GBPUSD → GBP, same as SEMG.
  Volume: enabled (added to VOLUME_ETFS).
  Position in ETFS list: after SEMG.
  CLAUDE.md updated with currency and benchmark facts.

CONTEXT: SEMI.L YTD +86% vs SEMG.L +56%, 3M +59% vs +43.5%.
  Both near 52W highs. Added as watching position.

### yfinance LSE outside-hours price (permanent architectural fact)
fast_info fields for LSE tickers — verified 2026-05-30:
  fast_info.last_price                  — actual last market price ✓ USE THIS
  fast_info.regular_market_previous_close — previous session close  ✓ USE THIS
  fast_info.previous_close              — unreliable, not a real session close ✗ AVOID

Outside market hours, fetch_intraday uses fast_info.last_price as
  close and regular_market_previous_close as Day% denominator.
  GBp conversion (÷100) applied to both fields for LSE pence tickers.
  Falls back to daily['close_eod'] if fast_info raises an exception.
  Verified working on weekend — shows Friday close correctly.

### 2026-05-30 — EOD price fix (trailing NaN row)
ROOT CAUSE: yfinance returns a partial Friday bar (Close=NaN) that
  survives _get_daily_df's dropna() because Open/Volume have values.
  df['Close'].iloc[-1] picked up that NaN → close_eod=nan → price/Day% broken.
FIXED in fetch_daily(): use close_s = df['Close'].dropna() as source
  for close_eod and prev_eod. NaN rows skipped; last real close used.
  Also added guard: if close_s.empty → return None.
ALSO FIXED: removed _eod_snapshot and _intraday_cache. Both caches
  caused stale mid-session values outside market hours.

OUTSIDE-HOURS PATH (fetch_intraday) — verified working 2026-05-30:
  fast_info.last_price / regular_market_previous_close with GBp ÷100.
  Correctly shows Friday close on weekends. Falls back to close_eod.

### 2026-05-30 — v1.12.0 Task 3: US10Y 10d delta in macro strip ✓ VERIFIED
BUILT: US10Y in macro strip now shows level + 10d delta on one line.
  Format: "4.45% ↓ / -1pp" (level + existing direction arrow + delta).
  Delta = close[-1] - close[-11] on ^TNX daily series (period='3mo', already fetched).
  Delta expressed in pp: raw_delta * 100, rounded to integer. 1pp = 0.01 yield change.
  Coloring: positive delta = RED (rising rates), negative = GREEN (falling),
    zero = MUTED grey (flat / deadband rounds to 0).
  Fallback: if ^TNX series < 11 rows or exception → "/ —" in MUTED grey.
  No new fetch. Regime scoring (US10Y/VIX/DXY) untouched.
  Modified: fetch_macro_regime() (delta calc + macro_result key),
    build_macro_strip() (extract delta, compute display vars, inline US10Y span).
VERIFIED: browser confirmed level + delta visible. Delta −1pp (May 29 4.453 vs May 14 4.461).

### 2026-05-30 — v1.13.0 Task 4: Regime badge prominence + conviction modifier ✓ VERIFIED
BUILT: Regime badge in build_macro_strip() made larger — font 12px→15px,
  weight 700→800, padding 3px 12px→4px 16px, letterSpacing 0.5→0.6px.
  Badge is now the visual anchor of the macro strip.

BUILT: HIGH conviction regime modifier in build_summary_table().
  Reads _macro_cache directly (no new fetch, no parameter change).
  When conv == 'HIGH' and regime == 'RISK OFF' → small grey Div "regime: stress"
  When conv == 'HIGH' and regime == 'CAUTION'  → small grey Div "regime: caution"
  All other convictions / regimes: nothing rendered.
  Style: MUTED grey, fontSize 10px, marginTop 2px — same as age stamps.
  Display only — no change to signal logic, conviction scoring, or action values.
  If _macro_cache empty: _mc_regime = None → modifier skipped, no crash.
  Modified: build_macro_strip() (badge style only),
    build_summary_table() (one-line cache read at top, modifier in conv_cell).

### 2026-05-31 — v1.14.0 visual overhaul + Charts tab + theme switcher

#### T1–T4: Charts tab (earlier sessions, logged here for completeness)
BUILT: Charts tab with dcc.Tabs routing.
  Price mode: multi-ticker normalised price chart. Ticker buttons
    toggle membership. Legend sorted by last value descending.
  RSI mode: RSI 14 for each selected ETF. Reference lines at 70/50/30
    labelled overbought/momentum/oversold. Legend sorted by last value.
  Volume mode: grouped bar chart + 20d rolling average line.
    Legend shows period average (not last bar). IWMO/SGLS excluded.
  Timeframes: 1W / 1M / 3M / 6M / 1Y. SPX and NDQ toggleable overlays.

#### T7: Snapshot section below chart
BUILT: Compact stat tracks (dot-lane design) below price chart.
  Each ETF has one row. Stats shown as dot positioned on a labelled
  scale lane. Conviction badge in first column.
  Staircase boundary labels on each lane.
  Snapshot background: #f0f4ff light blue-grey (distinct from card).
  Timeframe toggle: 1D / 1W / 1M / 3M / 6M / 1Y.
    1D shows: RSI + 52W DD + RS 30d + Day%.
    Non-1D shows: RSI + Period Return + RS vs Benchmark (no Day%).
    1Y: RSI uses iloc[-1] (last row); RS uses slice_bars to get
      correct window — these differ because yfinance returns more
      than 252 rows for 1Y period.
  FIXED: 1Y N/A bug — RSI always iloc[-1]; RS uses slice_bars window.
  FIXED: snapshot background was dark; added explicit light bg + dark
    text overrides for all stat labels.

#### T8: DEFERRED
News & Catalysts tab: requires Anthropic API credit.
  Implementation paused — no credit configured on Render.
  Resume when API credit is available.

#### T9: Theme switcher — SIMPLIFIED
BUILT: THEMES dict (7 themes): Slate, Dusk, Carbon, Midnight,
  Terminal, Alpine, Parchment. Values: bg/surface/card/border/
  border_l/accent/green/red/amber/muted/dim/text/header_border/
  border_radius.
BUILT: theme-dropdown in header (dcc.Dropdown, 110px, 11px monospace).
  Selected theme updates: app-root bg, header-bar bg, tabs-bar bg,
  macro-regime-strip bg.
DEFERRED: Full propagation (card interiors, charts, signal table).
  Would require threading theme as State through 200+ inline style
  references across all builder functions. Deferred — not worth the
  churn for a personal single-user tool where Slate is the default.
VERIFIED: outer chrome visibly changes on theme selection.
  Theme persists when switching tabs (dropdown value held in DOM).

### 2026-05-31 — v1.15.0 % from SMA50
BUILT: Third line in SMA POSITION cell — % from SMA50.
  Formula: pct50 = (close - sma50) / sma50 * 100 (pre-computed in rows builder).
  Display: "+12.3% from SMA50" — green ≥+5%, amber +2–5%, grey 0–+2%, red <0%.
  Guard: sma_ext_pct = data.get('pct50') — None check skips line if missing.
  Variable prefix: sma_ext_. Modified: build_summary_table() only.
  Commit: 424491d.
NOT TOUCHED: fetch_daily, fetch_intraday, pct50 computation in rows builder,
  all other columns, GBp conversion, RS logic.

### 2026-05-31 — v1.15.0 rate sensitivity beta
BUILT: fetch_rate_beta(etf) — 1Y daily beta of ETF returns vs ^TNX moves.
  New cache: _tnx_1y_cache (24h TTL). New fetch: _get_tnx_1y() fetches
  ^TNX period='1y' interval='1d', separate from _macro_cache (3mo, 60min TTL).
  Alignment: pd.merge inner join on normalized date index.
  Guard: < 20 aligned rows → returns None (no crash, no display).
  Computation: np.polyfit(tnx_returns, etf_returns, 1)[0], rounded 2dp.
  Display: "β -0.42" MUTED grey, appended as fifth line in RS TREND 30d cell.
  Variable prefix: rate_beta_. Commit: 10d1f64.
VERIFICATION NOTE: SEMG is long-duration growth — expect NEGATIVE beta.
  Positive beta on SEMG = investigate date alignment first.
FIXED (same session): two bugs in fetch_rate_beta(). Commit: 711a739.
  1. KeyError 'Close': yfinance returns multi-level column DataFrame.
     Fix: .squeeze() on both tnx_raw and df['Close'] before .rename().
  2. Exception propagating up and killing entire callback.
     Fix: entire function body wrapped in try/except Exception: return None.
VERIFIED beta values (2026-05-31):
  Working:  SEMG β -0.12 · SEMI β -0.18 · WTAI β -0.23 · SGLS β +0.00
  Absent:   VDPG, FLXK, JEDG — yfinance returns insufficient 1Y data.
  Not a code issue. pd.merge inner join is correct. Do not debug further.
NOT TOUCHED: fetch_macro_regime(), _macro_cache, fetch_daily() return signature,
  fetch_intraday(), _get_daily_df(), all GBp/benchmark/RS logic.

## CURRENT STATE
Version: v1.16.0
Dashboard columns: ETF (+ sparkline), PRICE/Day%, VOLUME, CONVICTION
  (+ grey age stamp), ACTION (+ grey age stamp), ENTRY AT, RSI 14,
  SMA POSITION (+ % from SMA50 third line), 52W DRAWDOWN,
  RS TREND 30d (+ persist Nd + flip count + β rate sensitivity).
Macro strip: RISK ON/LEANING ON/RISK OFF/CAUTION badge + US10Y (level
  + 10d delta), VIX, DXY, SOX. SOX display only — not scored.
  Fetch failure shows N/A in grey.
Portfolio: JEDG, SEMG, SEMI, VDPG, WTAI, SGLS, FLXK.
  IWMO removed 2026-05-30. SEMI.L added 2026-05-30.
Charts tab: Price / RSI 14 / Volume modes. Timeframes 1W–1Y.
  Snapshot stat lanes below chart. Timeframe toggle 1D–1Y.
Theme switcher: outer chrome only (bg/header/tabs/macro strip).
  Card interiors stay Slate until full propagation is built.

## REMAINING BUILD ITEMS
1. SOX verify — cross-check SOX value against TradingView at Monday
   market open. Confirm arrow direction matches trend.

2. T8 News & Catalysts tab — DEFERRED until Anthropic API credit
   is configured on Render.

3. SGLS Position Review — URGENT
   -21.6% drawdown while gold at USD ATH.
   Decision needed: keep SGLS hedged or switch to IGLN.L unhedged.

4. Signal Audit Log — HIGH PRIORITY
   In-memory age stamps live. Full log: persistent JSON, old→new
   transitions, price/RSI at change, dedicated Signal History tab.

5. Theme full propagation — LOW PRIORITY
   Thread theme State through builder functions so card interiors
   also respond. Parchment (light) theme unusable without this.

6. Correlation Heatmap — LOW PRIORITY
7. Vol-Adjusted Sizing — LOWEST PRIORITY (wrong tool for mandate)

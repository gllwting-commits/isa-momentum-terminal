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
Version: v1.7.0
Dashboard columns (all verified): ETF, PRICE·Day%, VOLUME,
CONVICTION, ACTION, ENTRY AT, RSI 14, SMA POSITION,
52W DRAWDOWN, RS TREND 30d, SIGNAL CHANGED.

## REMAINING BUILD ITEMS
1. Signal Audit Log — HIGH PRIORITY
   Timestamped JSON on every conviction/action change.
   Fields: ticker, timestamp, old_conviction, new_conviction,
   old_action, new_action, price_at_change, rsi_at_change.
   New "Signal History" tab. Show days unchanged per signal.

2. SGLS Position Review — URGENT
   -21.6% drawdown while gold at USD ATH.
   Decision needed: keep SGLS hedged or switch to IGLN.L unhedged.

3. Correlation Heatmap — LOW PRIORITY
4. Vol-Adjusted Sizing — LOWEST PRIORITY (wrong tool for mandate)

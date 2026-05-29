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
  IWMO.L, WTAI.L, FLXK.L

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
IWMO: SWDA.L  (mul)  — GBP bench × GBPUSD → USD

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

# ISA Momentum Terminal

**Live:** https://isa-momentum-terminal.onrender.com  
**Repo:** https://github.com/gllwting-commits/isa-momentum-terminal  
**Version:** v1.18.0

A professional portfolio intelligence dashboard for a UK Stocks & Shares ISA with a maximum growth, early retirement mandate. Built in Python/Dash, deployed on Render free tier.

---

## What It Does

Monitors 7 ETF positions and 10 watchlist tickers in real time. Generates momentum-based buy/hold/exit signals. Displays macro regime context. Enables entry timing via RSI, relative strength, and drawdown tracking.

This is a single-user tool. There is no multi-tenancy, no authentication, and no mobile-first requirement. Desktop browser at ≥1200px is the design target.

---

## Portfolio Context

| Field | Value |
|---|---|
| Platform | Trading 212 Stocks & Shares ISA |
| Mandate | Maximum growth, 20-year horizon, early retirement |
| Strategy | Upward momentum ETFs — LSE-listed, GBP-denominated, ISA-eligible |
| Monthly contribution | £1,667 (£20,000 ISA allowance / year) |

### Current Holdings

| Ticker | Name | Theme |
|---|---|---|
| SEMG.L | Amundi MSCI Semiconductors ESG Screened | Semiconductors |
| SEMI.L | iShares MSCI Global Semiconductors | Semiconductors |
| WTAI.L | WisdomTree Artificial Intelligence | Artificial Intelligence |
| VDPG.L | Vanguard FTSE Dev Asia Pac ex-JP | Asia Pacific |
| FLXK.L | Franklin FTSE Korea | South Korea |
| SGLS.L | Invesco Physical Gold ETC (GBP Hedged) | Gold |
| JEDG.L | VanEck Space Innovators | Space |

---

## Architecture

```
app.py                   — Single-file Dash application (all layout + callbacks)
requirements.txt         — Python dependencies
VERSION                  — Current version number (authoritative)
CLAUDE.md                — Architectural facts and coding constraints for Claude Code
MEMORY.md                — Session log: decisions, errors, current state, build queue
DESIGN.md                — Visual design system (tokens + rationale) for Stitch
AGENTS.md                — Coding agent implementation guide
```

### Stack

| Layer | Technology |
|---|---|
| Framework | Python · Dash (Plotly) |
| Data | yfinance (15-min delayed, free tier) |
| Deployment | Render (free tier, auto-deploy from GitHub) |
| Keepalive | UptimeRobot (prevents Render sleep) |
| Version control | GitHub (main branch = production) |

---

## Dashboard Structure

### Tabs

1. **Signal Summary** — primary view. Signal table + macro regime strip.
2. **Charts** — multi-ticker price / RSI / volume charts with timeframe toggle and snapshot stat lanes.
3. **ISA & Retirement** — contribution calculator and retirement projection.
4. **Radar** — momentum entry scanner for 10 watchlist ETFs.

### Signal Table Columns

| Column | Description |
|---|---|
| ETF | Ticker + full name + 15-day sparkline |
| PRICE / Day% | 15-min delayed price + daily change |
| VOLUME | Intraday volume with direction flag. ~ prefix before 14:00 London. |
| CONVICTION | HIGH / MED / LOW badge + signal age stamp |
| ACTION | Add / Hold / Trim / Exit / Watch + signal age stamp |
| ENTRY AT | SMA20 / SMA50 / Avoid |
| RSI 14 | RSI value + 10-day delta |
| SMA POSITION | SMA20 and SMA50 values + Above/Below + % from SMA50 |
| 52W DRAWDOWN | % from 52-week intraday high |
| RS TREND 30d | 30-day relative strength trend vs benchmark + persistence + flip count + rate beta |

### Macro Regime Strip

Shows: **RISK ON / LEANING ON / CAUTION / RISK OFF** regime badge (scored from US10Y direction + VIX level + DXY direction) plus live readings for US10Y (level + 10-day delta), VIX, DXY (via UUP proxy), and SOX (display only, not scored).

---

## Signal Logic

### Conviction & Action
Derived from RSI level, RSI delta, RS trend, 52W drawdown, and SMA positioning. Unrecognised action strings default to WATCH.

### Entry Framework
All three conditions must be met before adding to a position:
1. RSI stabilised in 55–65 range (not at apparent bottom)
2. Price reclaiming SMA20
3. RS trend turning positive vs benchmark

### Benchmark Pairs (decided — do not change)

| ETF | Benchmark | FX Method |
|---|---|---|
| SEMG.L | SOXX | div (USD bench ÷ GBPUSD) |
| SEMI.L | SOXX | div (USD bench ÷ GBPUSD) |
| WTAI.L | EQQQ.L | mul (GBP bench × GBPUSD) |
| JEDG.L | UFO | div (USD bench ÷ GBPUSD) |
| SGLS.L | IGLN.L | div (USD bench ÷ GBPUSD) |
| VDPG.L | VAPX.L | None (both GBP) |
| FLXK.L | EWY | None (both USD) |

---

## Design System

See `DESIGN.md` for the full visual specification. Summary:

- **Aesthetic:** Bloomberg-meets-Linear. Dark terminal. Colour = signal, never decoration.
- **Fonts:** Inter (UI chrome) + JetBrains Mono (all numeric data)
- **Palette:** Near-black surfaces, single blue accent, strict semantic green/red/amber
- **Shapes:** Flat. Max `border-radius: 8px`. No shadows on table rows.
- **Density:** 52px row height, 12px horizontal cell padding. Dense but readable.

---

## Coding Instructions

See `AGENTS.md` for full implementation rules. Non-negotiable summary:

1. Never touch `fetch_daily`, `fetch_intraday`, `_get_daily_df`, `build_summary_table`, benchmarks, or GBp conversion
2. Banned variable names: `chg_color`, `arrow` (use prefixed alternatives)
3. Every new column's colour/arrow variables need a unique prefix
4. No new yfinance fetches without explicit approval
5. One task at a time. Verify in browser before proceeding to next

---

## Remaining Build Queue

Priority order:

1. **Signal Audit Log** — HIGH PRIORITY. Persistent JSON of every conviction/action change. Dedicated Signal History tab. Directly improves entry timing.
2. **SGLS Position Review** — URGENT. −21.6% drawdown while gold at USD ATH. GBP hedge destroying value. Decision: keep or switch to IGLN.L.
3. **T8 News & Catalysts tab** — DEFERRED. Requires Anthropic API credit on Render.
4. **Theme full propagation** — LOW. Card interiors stay Slate until built.
5. **Correlation Heatmap** — LOW.
6. **Vol-Adjusted Sizing** — LOWEST (wrong tool for max growth mandate).

---

## Development Workflow

```
Claude.ai  → Design / prototype / diagnose tracebacks
Claude Code → Implementation (Windows CMD)
```

Session start checklist:
```
1. Ctrl+C if Claude Code already running
2. git pull origin main
3. claude
4. Read CLAUDE.md and MEMORY.md — confirm version before starting
```

Session end checklist:
```
1. Update MEMORY.md with changes made
2. Update CLAUDE.md if architectural facts changed
3. Update VERSION file
4. git commit -am "v1.X.Y — description"
5. git push origin main
6. Confirm push succeeded
```

---

## Key Technical Facts

- Render free tier: 7 intraday yfinance downloads per 60s refresh cycle (after fetch split)
- Daily cache computed once at startup, refreshed at midnight
- London timezone: `pytz.timezone('Europe/London')` — NOT ZoneInfo (tzdata unavailable on Render Linux)
- GBp tickers divide by 100 at fetch, once only — never downstream
- GBPUSD cached 5 minutes via `_get_gbpusd()`
- Previous close: `df['Close'].iloc[-2]` — NOT `fast_info.previous_close`
- 52W high: `df['High'].max()` — NOT `df['Close'].max()`
- Volume caveat: `~` prefix before 14:00 London; clean after 14:00

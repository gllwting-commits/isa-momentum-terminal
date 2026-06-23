---
name: ISA Momentum Terminal
colors:
  background: "#0a0c10"
  surface: "#0f1117"
  card: "#141720"
  card-elevated: "#1a1e2a"
  border: "#1e2330"
  border-accent: "#252b3b"
  primary: "#e2e8f4"
  muted: "#4a5270"
  dim: "#2a3050"
  accent: "#5b8dee"
  green: "#22c55e"
  red: "#ef4444"
  amber: "#f59e0b"
  cyan: "#22d3ee"
  purple: "#a78bfa"
  text: "#e2e8f4"
  text-secondary: "#8892aa"
  text-muted: "#4a5270"
  badge-high-bg: "#0f2a1a"
  badge-high-text: "#22c55e"
  badge-med-bg: "#2a1f05"
  badge-med-text: "#f59e0b"
  badge-low-bg: "#1a0f0f"
  badge-low-text: "#ef4444"
  action-exit-bg: "#1f0808"
  action-exit-text: "#ef4444"
  action-add-bg: "#0a1f10"
  action-add-text: "#22c55e"
  action-watch-bg: "#0c1428"
  action-watch-text: "#5b8dee"
  macro-risk-on-bg: "#0a1f10"
  macro-risk-on-text: "#22c55e"
  macro-caution-bg: "#1f1505"
  macro-caution-text: "#f59e0b"
  macro-risk-off-bg: "#1f0808"
  macro-risk-off-text: "#ef4444"
typography:
  display:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: "32px"
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: "20px"
    letterSpacing: "0.06em"
  body:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "20px"
  body-mono:
    fontFamily: "'JetBrains Mono', 'Fira Mono', monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "20px"
  data-primary:
    fontFamily: "'JetBrains Mono', 'Fira Mono', monospace"
    fontSize: "15px"
    fontWeight: 500
    lineHeight: "22px"
  data-secondary:
    fontFamily: "'JetBrains Mono', 'Fira Mono', monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: "16px"
  label:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "10px"
    fontWeight: 600
    lineHeight: "14px"
    letterSpacing: "0.08em"
  macro-badge:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    lineHeight: "16px"
    letterSpacing: "0.10em"
rounded:
  none: "0px"
  sm: "3px"
  DEFAULT: "5px"
  md: "6px"
  lg: "8px"
  badge: "4px"
  pill: "999px"
spacing:
  unit: "4px"
  cell-pad-x: "12px"
  cell-pad-y: "10px"
  card-gap: "1px"
  section-gap: "16px"
  header-height: "44px"
  macro-strip-height: "36px"
  row-height: "52px"
  compact-row-height: "40px"
elevation:
  card: "0 1px 3px rgba(0,0,0,0.4)"
  elevated: "0 4px 16px rgba(0,0,0,0.5)"
  strip: "0 1px 0 rgba(255,255,255,0.04)"
components:
  signal-row:
    backgroundColor: "{colors.card}"
    borderBottom: "1px solid {colors.border}"
    height: "{spacing.row-height}"
    hoverBackground: "{colors.card-elevated}"
  signal-row-exit:
    borderLeft: "3px solid {colors.red}"
  signal-row-trim:
    borderLeft: "3px solid {colors.amber}"
  badge-high:
    backgroundColor: "{colors.badge-high-bg}"
    textColor: "{colors.badge-high-text}"
    rounded: "{rounded.badge}"
    fontSize: "10px"
    fontWeight: 700
    padding: "2px 8px"
    letterSpacing: "0.08em"
  badge-med:
    backgroundColor: "{colors.badge-med-bg}"
    textColor: "{colors.badge-med-text}"
    rounded: "{rounded.badge}"
    fontSize: "10px"
    fontWeight: 700
    padding: "2px 8px"
    letterSpacing: "0.08em"
  badge-low:
    backgroundColor: "{colors.badge-low-bg}"
    textColor: "{colors.badge-low-text}"
    rounded: "{rounded.badge}"
    fontSize: "10px"
    fontWeight: 700
    padding: "2px 8px"
    letterSpacing: "0.08em"
  macro-strip:
    backgroundColor: "{colors.surface}"
    height: "{spacing.macro-strip-height}"
    borderBottom: "1px solid {colors.border}"
  tab-bar:
    backgroundColor: "{colors.surface}"
    borderBottom: "1px solid {colors.border}"
    activeIndicator: "2px solid {colors.accent}"
  header:
    backgroundColor: "{colors.surface}"
    borderBottom: "1px solid {colors.border}"
    height: "{spacing.header-height}"
  sparkline:
    color: "{colors.accent}"
    width: "70px"
    height: "22px"
    strokeWidth: "1.5px"
  column-header:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-muted}"
    fontSize: "9px"
    fontWeight: 600
    letterSpacing: "0.1em"
    borderBottom: "1px solid {colors.border}"
    padding: "6px 12px"
---

## Overview

**ISA Momentum Terminal** is a professional-grade portfolio intelligence dashboard for a single-user ISA trading on a 20-year maximum growth mandate. The visual language is **Bloomberg-meets-Linear**: dense data presented with surgical precision, zero decorative noise, and a dark-field terminal aesthetic that treats colour as signal — not decoration.

The UI must feel like a financial instrument, not a web app. Every pixel either carries information or creates breathing room that makes information more readable. The default emotional register is calm authority. Green means go, red means danger, amber means caution — always, without exception.

## Colors

The palette is built on near-black surfaces with a single warm-blue accent. Colour is reserved strictly for semantic roles — it is never used decoratively.

- **Background (`#0a0c10`):** The deepest layer. Body background only. Never used for cards.
- **Surface (`#0f1117`):** Header, tab bar, macro strip, column headers. One step lighter than background.
- **Card (`#141720`):** Signal table rows, chart backgrounds, panel interiors.
- **Card Elevated (`#1a1e2a`):** Hovered rows, modals, selected states.
- **Border (`#1e2330`):** All dividers. Never heavier than 1px.
- **Accent (`#5b8dee`):** Active tab indicator, links, Watch/Monitor action, pinned radar tickers. Used sparingly.
- **Green (`#22c55e`):** Positive day%, RSI in momentum zone, RS trend up, HIGH conviction badge, Add action, RISK ON badge.
- **Red (`#ef4444`):** Negative day%, RSI overbought, high drawdown, LOW conviction badge, Exit action, RISK OFF badge.
- **Amber (`#f59e0b`):** Neutral RS trend, RSI near threshold, MED conviction badge, Trim action, CAUTION badge.
- **Cyan (`#22d3ee`):** SEMG chart line only.
- **Purple (`#a78bfa`):** Pinned radar tickers on charts only.
- **Text (`#e2e8f4`):** Primary text. Headlines, data values.
- **Text Secondary (`#8892aa`):** Sub-labels, age stamps, benchmark labels.
- **Text Muted (`#4a5270`):** Column headers, placeholder text, disabled states.

Do not use colour for anything other than its defined semantic role. Every coloured element must convey meaning.

## Typography

Two font families only:

1. **Inter** — All UI chrome: labels, badges, tab names, column headers, body copy.
2. **JetBrains Mono** (fallback: Fira Mono) — All numeric data: prices, percentages, RSI values, drawdown, RS trend. Monospace alignment is non-negotiable for scanning columns of figures.

Numeric hierarchy within a table cell:
- Primary value: `data-primary` (15px, weight 500, mono)
- Secondary value / delta: `data-secondary` (11px, weight 400, mono, text-secondary colour)
- Tertiary meta (age stamp, persist count, beta): 10px, text-muted colour

Column headers: `label` style — all-caps, 9-10px, wide letter-spacing, text-muted colour. Must not compete visually with data.

## Layout

Strict vertical stack: Header → Macro Strip → Tab Bar → Content. No sidebars. No floating panels.

The **Signal Summary table** is the primary view. Full-width fixed-layout table, columns in order:
1. ETF (ticker + long name + sparkline)
2. PRICE / Day% — right-aligned numeric pair
3. VOLUME — right-aligned with direction flag
4. CONVICTION — centre-aligned badge + age stamp
5. ACTION — centre-aligned + age stamp
6. ENTRY AT — centre-aligned
7. RSI 14 — right-aligned value + delta
8. SMA POSITION — two-line: values + Above/Below label + % from SMA50
9. 52W DRAWDOWN — right-aligned percentage
10. RS TREND 30d — right-aligned with persist + flip count + beta

Row height: 52px. Cell padding: 12px horizontal, 10px vertical. No horizontal scroll at ≥1200px.

## Elevation & Depth

Depth through background lightness steps only — no shadows on rows, no blur effects.

- Layer 0 (deepest): `#0a0c10` — page background
- Layer 1: `#0f1117` — header, tab bar, macro strip, column headers
- Layer 2: `#141720` — card/row backgrounds
- Layer 3: `#1a1e2a` — hovered/selected rows, elevated panels

Border `#1e2330` separates layers at 1px. No `box-shadow` on table rows. Shadows reserved for chart tooltips and modals.

## Shapes

Flat. Borders define structure, not rounded corners.

- Table rows: `border-radius: 0`
- Badges (conviction, action): `4px`
- Buttons (tab bar, chart toggles): `3px`
- Chart tooltips: `5px`
- Macro regime badge: `4px` with uppercase text

Maximum `border-radius` anywhere in the application: `8px`.

## Components

### Signal Table Row
52px height. Left border: 3px solid red (Exit), 3px solid amber (Trim), transparent (all others). Background: `{card}`. Hover: `{card-elevated}` at 100ms ease. Row separator: 1px `{border}`.

### Conviction Badge
4px radius pill. Semantic colour pairs: HIGH green, MED amber, LOW red. 10px, bold, uppercase, 0.08em letter-spacing. Grey age stamp below at 10px text-muted.

### Macro Regime Strip
Full-width, 36px. Background: `{surface}`. Flex row: regime badge (left anchor) then US10Y (level+delta+arrow), VIX (value+arrow), DXY (value+arrow), SOX (value+arrow). Regime badge is the visual anchor — 11px, weight 700, all-caps, 4px radius. All values monospace. Single unbroken horizontal line.

### Tab Bar
`{surface}` background. Active tab: 2px `{accent}` bottom border. Inactive: `{text-muted}`. 12px Inter weight 500. No filled backgrounds — indicator line only.

### Sparkline
70×22px SVG inline in ETF cell. Stroke: `{accent}`, 1.5px. No fill, no axes, no labels. Trajectory signal only.

### Chart
Paper and plot background: `{card}`. Grid lines: `{border}` 0.5 opacity. Axis labels: `{text-muted}` 11px mono. Legend right-aligned, 12px mono, sorted by last value. RSI reference lines: 70 red dashed, 50 amber dashed, 30 red dashed, labelled at right edge.

## Do's and Don'ts

**Do:**
- Use monospace for every number in every table cell
- Keep colour strictly semantic — one role per colour token, always
- Show arrows (↑ ↓ →) before every directional value
- Left-align ETF names, right-align all numeric columns
- Keep badge text uppercase and ≤10px
- Use 1px hairline borders between all sections

**Don't:**
- Use `border-radius > 8px` anywhere
- Use colour for decoration — every coloured element must convey meaning
- Show horizontal scrollbars at ≥1200px
- Mix font weights beyond the defined scale
- Use opacity < 1 on text (use text-secondary or text-muted tokens instead)
- Add gradients, glow effects, or animations beyond 100ms ease hover transitions

## Agent Prompt Guide

When generating or modifying UI for this dashboard:
1. Read all token values from the YAML front matter before writing any style
2. Apply `data-primary` typography to all price, percentage, RSI, and drawdown values
3. Apply `label` typography to all column headers — all-caps, wide tracking, text-muted
4. Treat semantic colour roles as inviolable: green = positive, red = negative, amber = caution/neutral
5. Signal table is the primary artefact — optimise all layout decisions for it first
6. Default to `border` not `box-shadow` for separation between elements
7. Never add decorative elements that don't carry information
8. The existing Slate theme tokens in the dashboard's THEMES dict map to these tokens as the authoritative source

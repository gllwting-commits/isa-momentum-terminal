import json
import os
import socket
from datetime import datetime, timedelta
from flask import redirect, request, session

import dash
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from dash import Input, Output, State, dcc, html
from plotly.subplots import make_subplots

# ── Config ───────────────────────────────────────────────────────────────────
ETFS = ['IWMO', 'JEDG', 'SEMG', 'VDPG', 'WTAI', 'SGLS', 'FLXK']
TICKERS = {e: f'{e}.L' for e in ETFS}
ETF_NAMES = {
    'IWMO': 'iShares MSCI World Momentum',
    'JEDG': 'JPM Global Equity Multi-Factor',
    'SEMG': 'iShares MSCI EM IMI ESG Screened',
    'VDPG': 'Vanguard FTSE Dev World',
    'WTAI': 'WisdomTree AI',
    'SGLS': 'iShares Global Clean Energy',
    'FLXK': 'Franklin FTSE Korea',
}
TIMEFRAMES = {'1W': 7, '1M': 30, '3M': 90, '6M': 180, '1Y': 365}
# Minimum history fed to fetch_data() so EWM-based RSI stabilises identically
# in both Signal Summary and Charts — must be >= max(TIMEFRAMES.values()).
_INDICATOR_DAYS = 365
ISA_ALLOWANCE = 20_000
MONTHLY_INVEST = 1_667
ANNUAL_RETURN  = 0.12
PROJ_YEARS     = 20

# ── Palette ──────────────────────────────────────────────────────────────────
BG     = '#0d1117'
CARD   = '#161b22'
BORDER = '#30363d'
TEXT   = '#e6edf3'
MUTED  = '#8b949e'
ACCENT = '#58a6ff'
GREEN  = '#3fb950'
RED    = '#f85149'
YELLOW = '#d29922'
ORANGE = '#f97316'

MACRO_STATUS_COLOR = {
    'CLEAR':   GREEN,
    'WATCH':   YELLOW,
    'WARNING': ORANGE,
    'ALERT':   RED,
}
MACRO_STATUS_BG = {
    'CLEAR':   '#0d1a0d',
    'WATCH':   '#1a1600',
    'WARNING': '#1a0e00',
    'ALERT':   '#1a0d0d',
}
MACRO_STATUS_TEXT_COLOR = {
    'CLEAR': '#000', 'WATCH': '#000', 'WARNING': '#000', 'ALERT': '#fff',
}

SIG_COLOR = {
    'BUY':  GREEN,
    'HOLD': YELLOW,
    'SELL': RED,
}
SIG_DESC = {
    'BUY':  'Oversold conditions detected — favourable entry point',
    'HOLD': 'No clear edge — hold existing positions or watch',
    'SELL': 'Overbought / extended — avoid chasing, wait for pullback',
}
REC_COLOR = {'BUY': GREEN, 'HOLD': YELLOW, 'SELL': RED}

TAB_STYLE = {
    'background': BG,
    'color': MUTED,
    'border': 'none',
    'borderBottom': f'2px solid transparent',
    'padding': '10px 22px',
    'fontFamily': 'monospace',
    'fontSize': '13px',
    'fontWeight': '600',
    'cursor': 'pointer',
}
TAB_SELECTED = {
    **TAB_STYLE,
    'color': TEXT,
    'borderBottom': f'2px solid {ACCENT}',
    'background': CARD,
}

# ── Calculations ──────────────────────────────────────────────────────────────
def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def get_signal(rsi: float, close: float, sma20: float, sma50: float) -> str:
    if rsi < 30 and close < sma20:
        return 'BUY'
    if rsi < 45 and close < sma50:
        return 'BUY'
    if rsi > 70 or close > sma50 * 1.10:
        return 'SELL'
    return 'HOLD'


def get_recommendation(rsi: float, close: float, sma20: float, sma50: float):
    """Same logic as get_signal(); adds a plain-English reason sentence."""
    rec   = get_signal(rsi, close, sma20, sma50)
    pct20 = (close - sma20) / sma20 * 100
    pct50 = (close - sma50) / sma50 * 100
    vs20  = 'above' if close >= sma20 else 'below'
    vs50  = 'above' if close >= sma50 else 'below'

    if rec == 'BUY':
        if rsi < 30:
            reason = (f'RSI deeply oversold at {rsi:.0f} and price {abs(pct20):.1f}% '
                      f'below SMA20 — high-probability bounce entry.')
        else:
            reason = (f'RSI at {rsi:.0f} with price {abs(pct50):.1f}% below the 50-day '
                      f'trend line — momentum building, attractive entry on weakness.')
    elif rec == 'SELL':
        if rsi > 70:
            reason = (f'RSI overbought at {rsi:.0f} and price {pct50:.1f}% above SMA50 '
                      f'— rally looks stretched, wait for a pullback.')
        else:
            reason = (f'Price extended {pct50:.1f}% above SMA50 — momentum overstretched '
                      f'and risk/reward has deteriorated.')
    else:  # HOLD
        if close > sma20 and close > sma50:
            reason = (f'Uptrend intact, RSI {rsi:.0f} — price {vs20} SMA20 and {vs50} '
                      f'SMA50 with no overbought pressure, hold and let it run.')
        elif close < sma20 and close > sma50:
            reason = (f'Price dipped {abs(pct20):.1f}% below SMA20 but holds {vs50} '
                      f'SMA50, RSI {rsi:.0f} — wait for stabilisation.')
        else:
            reason = (f'Mixed signals, RSI {rsi:.0f} — price {vs20} SMA20 and {vs50} '
                      f'SMA50. No clear edge, watch for a directional move.')

    return rec, reason


def fetch_data(ticker: str, days: int) -> pd.DataFrame:
    start = datetime.today() - timedelta(days=days + 80)
    df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA50'] = df['Close'].rolling(50).mean()
    df['RSI']   = compute_rsi(df['Close'])
    return df


def fetch_latest(ticker: str) -> dict | None:
    df = fetch_data(ticker, _INDICATOR_DAYS)
    if df.empty:
        return None
    close  = float(df['Close'].iloc[-1])
    prev   = float(df['Close'].iloc[-2]) if len(df) > 1 else close
    rsi_s  = df['RSI'].dropna()
    s20_s  = df['SMA20'].dropna()
    s50_s  = df['SMA50'].dropna()
    rsi    = float(rsi_s.iloc[-1])  if not rsi_s.empty  else 50.0
    sma20  = float(s20_s.iloc[-1]) if not s20_s.empty else close
    sma50  = float(s50_s.iloc[-1]) if not s50_s.empty else close
    chg_pct = (close - prev) / prev * 100 if prev else 0
    rec, reason = get_recommendation(rsi, close, sma20, sma50)
    return {
        'close': close, 'chg_pct': chg_pct,
        'rsi': rsi, 'sma20': sma20, 'sma50': sma50,
        'vs20': 'Above' if close >= sma20 else 'Below',
        'vs50': 'Above' if close >= sma50 else 'Below',
        'pct20': (close - sma20) / sma20 * 100,
        'pct50': (close - sma50) / sma50 * 100,
        'rec': rec, 'reason': reason,
    }


def fetch_macro_indicators() -> dict:
    result = {}
    for key, ticker in [('TNX', '^TNX'), ('TYX', '^TYX'), ('SOX', '^SOX')]:
        try:
            start = datetime.today() - timedelta(days=365)
            df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
            if df.empty:
                result[key] = None
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df = df[['Close']].dropna()
            close = float(df['Close'].iloc[-1])
            ma200 = float(df['Close'].rolling(200).mean().dropna().iloc[-1]) if len(df) >= 200 else None
            ma200_prev = (float(df['Close'].rolling(200).mean().dropna().iloc[-11])
                          if len(df) >= 210 else None)
            result[key] = {
                'close': close,
                'ma200': ma200,
                'ma200_prev': ma200_prev,
                'as_of': datetime.now().strftime('%H:%M:%S'),
            }
        except Exception:
            result[key] = None
    return result


def get_macro_status(key: str, data: dict) -> tuple:
    if data is None:
        return 'UNKNOWN', 'No data available', ''
    close = data['close']

    if key == 'TNX':
        if close >= 5.0:
            return ('ALERT',
                    f'{close:.3f}%  ≥ 5.0% threshold',
                    'Redirect contributions — SGLS gets 40% of monthly')
        if close >= 4.8:
            return ('WARNING',
                    f'{close:.3f}%  ≥ 4.8% threshold',
                    'Pause SEMG/WTAI new buys — delay IWMO entry')
        if close >= 4.5:
            return ('WATCH',
                    f'{close:.3f}%  ≥ 4.5% threshold',
                    '')
        return ('CLEAR', f'{close:.3f}%  below 4.5%', '')

    if key == 'TYX':
        if close >= 5.3:
            return ('ALERT',
                    f'{close:.3f}%  ≥ 5.3% threshold',
                    'Structural regime shift — multi-year re-rating risk')
        if close >= 5.0:
            return ('WARNING',
                    f'{close:.3f}%  ≥ 5.0% threshold',
                    '')
        if close >= 4.8:
            return ('WATCH',
                    f'{close:.3f}%  ≥ 4.8% threshold',
                    '')
        return ('CLEAR', f'{close:.3f}%  below 4.8%', '')

    if key == 'SOX':
        ma200 = data.get('ma200')
        if ma200 is None:
            return 'UNKNOWN', 'Insufficient history for 200DMA', ''
        ma200_prev = data.get('ma200_prev')
        pct = (close - ma200) / ma200 * 100
        ma_declining = (ma200_prev is not None) and (ma200 < ma200_prev)
        if close < ma200 and ma_declining:
            return ('ALERT',
                    f'{close:,.1f}  —  {pct:.1f}% vs 200DMA ({ma200:,.1f}), MA declining',
                    'Pause SEMG additions — redirect to VDPG/SGLS')
        if close < ma200:
            return ('WARNING',
                    f'{close:,.1f}  —  {pct:.1f}% vs 200DMA ({ma200:,.1f})',
                    'Pause SEMG additions — redirect to VDPG/SGLS')
        if pct <= 3.0:
            return ('WATCH',
                    f'{close:,.1f}  —  +{pct:.1f}% vs 200DMA ({ma200:,.1f})',
                    '')
        return ('CLEAR',
                f'{close:,.1f}  —  +{pct:.1f}% vs 200DMA ({ma200:,.1f})',
                '')

    return 'UNKNOWN', '', ''


_MACRO_META = {
    'TNX': ('TNX', '10Y Treasury Yield'),
    'TYX': ('TYX', '30Y Treasury Yield'),
    'SOX': ('SOX', 'Philadelphia Semiconductor Index'),
}


def build_macro_panel(macro_data: dict) -> html.Div:
    cards = []
    for key in ['TNX', 'TYX', 'SOX']:
        data = macro_data.get(key)
        status, threshold_label, action = get_macro_status(key, data)
        color     = MACRO_STATUS_COLOR.get(status, MUTED)
        bg        = MACRO_STATUS_BG.get(status, CARD)
        txt_color = MACRO_STATUS_TEXT_COLOR.get(status, '#fff')
        ticker_label, full_name = _MACRO_META[key]
        as_of = data.get('as_of', '') if data else ''

        card_children = [
            html.Div([
                html.Span(status, style={
                    'background': color, 'color': txt_color,
                    'padding': '2px 10px', 'borderRadius': '20px',
                    'fontWeight': '700', 'fontSize': '11px',
                    'marginRight': '10px', 'letterSpacing': '0.5px',
                }),
                html.Span(ticker_label, style={
                    'color': TEXT, 'fontWeight': '700', 'fontSize': '15px',
                    'marginRight': '8px',
                }),
                html.Span(full_name, style={'color': MUTED, 'fontSize': '11px'}),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '6px'}),
            html.P(threshold_label, style={
                'color': TEXT, 'fontSize': '13px', 'margin': '0 0 4px 0',
                'fontFamily': 'monospace', 'fontWeight': '600',
            }),
        ]
        if action:
            card_children.append(html.P(f'Action: {action}', style={
                'color': color, 'fontSize': '12px', 'margin': '4px 0 0 0',
                'fontStyle': 'italic',
            }))
        if as_of:
            card_children.append(html.Span(f'as of {as_of}', style={
                'color': MUTED, 'fontSize': '10px', 'display': 'block', 'marginTop': '6px',
            }))

        cards.append(html.Div(card_children, style={
            'background': bg,
            'border': f'1px solid {color}',
            'borderLeft': f'4px solid {color}',
            'borderRadius': '8px',
            'padding': '12px 16px',
            'flex': '1',
            'minWidth': '260px',
            'boxShadow': f'0 0 14px {color}28',
        }))

    return html.Div([
        html.Div([
            html.Span('MACRO CONDITIONS', style={
                'color': MUTED, 'fontWeight': '700', 'fontSize': '11px',
                'letterSpacing': '1px',
            }),
            html.Span('  ·  Rates & Semiconductor Health  ·  refreshes every 60s',
                      style={'color': MUTED, 'fontSize': '11px'}),
        ], style={'marginBottom': '10px'}),
        html.Div(cards, style={'display': 'flex', 'gap': '12px', 'flexWrap': 'wrap'}),
    ], style={'maxWidth': '1100px', 'margin': '0 auto', 'padding': '12px 16px 4px'})


def retirement_projection():
    months = PROJ_YEARS * 12
    mr, mr_c, mr_a = ANNUAL_RETURN / 12, 0.08 / 12, 0.15 / 12
    base, cons, aggr = [0.0], [0.0], [0.0]
    for _ in range(months):
        base.append(base[-1] * (1 + mr)   + MONTHLY_INVEST)
        cons.append(cons[-1] * (1 + mr_c) + MONTHLY_INVEST)
        aggr.append(aggr[-1] * (1 + mr_a) + MONTHLY_INVEST)
    return [i / 12 for i in range(months + 1)], base, cons, aggr


# ── Style helpers ─────────────────────────────────────────────────────────────
def etf_btn_style(etf: str, selected: str) -> dict:
    active = etf == selected
    return {
        'background': ACCENT if active else 'transparent',
        'color': '#000' if active else TEXT,
        'border': f'1px solid {ACCENT if active else BORDER}',
        'borderRadius': '6px', 'padding': '7px 13px', 'cursor': 'pointer',
        'fontFamily': 'monospace', 'fontWeight': '700', 'fontSize': '13px',
    }


def tf_btn_style(tf: str, selected: str) -> dict:
    active = tf == selected
    return {
        'background': ACCENT if active else 'transparent',
        'color': '#000' if active else MUTED,
        'border': 'none', 'padding': '4px 11px', 'cursor': 'pointer',
        'fontFamily': 'monospace', 'fontSize': '12px',
        'fontWeight': '600', 'borderRadius': '4px',
    }


def card(children, extra_style=None):
    s = {'background': CARD, 'border': f'1px solid {BORDER}',
         'borderRadius': '10px', 'padding': '20px', 'marginBottom': '20px'}
    if extra_style:
        s.update(extra_style)
    return html.Div(children, style=s)


def stat_box(label, value, color):
    return html.Div([
        html.P(label, style={'color': MUTED, 'fontSize': '11px', 'margin': '0'}),
        html.P(value, style={'color': color, 'fontSize': '20px', 'fontWeight': '700',
                             'margin': '2px 0', 'fontFamily': 'monospace'}),
    ], style={'flex': '1', 'textAlign': 'center', 'background': BG,
              'borderRadius': '8px', 'padding': '10px'})


# ── Retirement chart (static) ─────────────────────────────────────────────────
def build_projection_fig():
    years, base, cons, aggr = retirement_projection()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=years, y=[v/1e6 for v in cons], name='Conservative 8%',
                             line=dict(color=YELLOW, dash='dash', width=1.5)))
    fig.add_trace(go.Scatter(x=years, y=[v/1e6 for v in base], name='Base 12%',
                             line=dict(color=ACCENT, width=2.5),
                             fill='tonexty', fillcolor='rgba(88,166,255,0.09)'))
    fig.add_trace(go.Scatter(x=years, y=[v/1e6 for v in aggr], name='Optimistic 15%',
                             line=dict(color=GREEN, dash='dash', width=1.5),
                             fill='tonexty', fillcolor='rgba(63,185,80,0.07)'))
    fig.add_annotation(x=19.4, y=base[-1]/1e6 + 0.15, text=f'£{base[-1]/1e6:.2f}M',
                       showarrow=False, font=dict(color=ACCENT, size=13, family='monospace'))
    fig.update_layout(
        template='plotly_dark', paper_bgcolor=CARD, plot_bgcolor=CARD,
        font=dict(family='monospace', color=TEXT), margin=dict(l=10, r=10, t=10, b=40),
        height=260, legend=dict(orientation='h', y=-0.18, x=0, font=dict(size=11)),
        xaxis=dict(title='Years', gridcolor=BORDER, title_font=dict(size=11)),
        yaxis=dict(title='Portfolio (£M)', gridcolor=BORDER, title_font=dict(size=11)),
        hovermode='x unified',
    )
    return fig, base[-1], MONTHLY_INVEST * PROJ_YEARS * 12


PROJ_FIG, PROJ_FINAL, PROJ_CONTRIB = build_projection_fig()

# ── Signal Summary table builder ──────────────────────────────────────────────
TH_STYLE = {
    'padding': '10px 14px', 'color': MUTED, 'fontSize': '11px',
    'fontWeight': '600', 'textAlign': 'left', 'borderBottom': f'1px solid {BORDER}',
    'whiteSpace': 'nowrap',
}
TD_STYLE = {
    'padding': '14px 14px', 'fontSize': '13px', 'verticalAlign': 'middle',
    'borderBottom': f'1px solid {BORDER}',
}


def vs_cell(label: str, pct: float) -> html.Td:
    color = GREEN if label == 'Above' else RED
    return html.Td([
        html.Span(label, style={'color': color, 'fontWeight': '700'}),
        html.Span(f'  {pct:+.1f}%', style={'color': MUTED, 'fontSize': '11px'}),
    ], style=TD_STYLE)


def rec_cell(rec: str) -> html.Td:
    color = REC_COLOR[rec]
    bg    = color + '22'
    return html.Td(
        html.Span(rec, style={
            'background': bg, 'color': color,
            'border': f'1px solid {color}',
            'padding': '3px 12px', 'borderRadius': '20px',
            'fontWeight': '700', 'fontSize': '12px', 'letterSpacing': '0.5px',
        }),
        style=TD_STYLE,
    )


def build_summary_table(rows: list[dict]) -> html.Table:
    headers = ['Signal', 'Reason', 'ETF', 'Price (p)', 'RSI 14',
               'SMA 20', 'SMA 50', 'vs SMA20', 'vs SMA50']
    thead = html.Thead(html.Tr([html.Th(h, style=TH_STYLE) for h in headers]))

    tbody_rows = []
    for row in rows:
        etf  = row['etf']
        data = row.get('data')

        if data is None:
            tr = html.Tr([
                html.Td('—', style={**TD_STYLE, 'color': MUTED}),
                html.Td('—', style={**TD_STYLE, 'color': MUTED}),
                html.Td(etf, style={**TD_STYLE, 'fontWeight': '700', 'color': TEXT}),
                html.Td('—', colSpan=6, style={**TD_STYLE, 'color': MUTED}),
            ], style={'borderBottom': f'1px solid {BORDER}'})
        else:
            chg_color = GREEN if data['chg_pct'] >= 0 else RED
            arrow     = '+' if data['chg_pct'] >= 0 else ''
            tr = html.Tr([
                # Signal badge — first
                rec_cell(data['rec']),
                # Reason — second
                html.Td(data['reason'], style={
                    **TD_STYLE,
                    'color': MUTED, 'fontSize': '12px',
                    'maxWidth': '300px', 'lineHeight': '1.5',
                }),
                # ETF name
                html.Td([
                    html.Div(etf, style={'color': TEXT, 'fontWeight': '700', 'fontSize': '14px'}),
                    html.Div(ETF_NAMES[etf], style={'color': MUTED, 'fontSize': '10px', 'marginTop': '2px'}),
                ], style=TD_STYLE),
                # Price
                html.Td([
                    html.Span(f'{data["close"]:.2f}', style={'color': TEXT, 'fontWeight': '700'}),
                    html.Br(),
                    html.Span(f'{arrow}{data["chg_pct"]:.2f}%',
                              style={'color': chg_color, 'fontSize': '11px'}),
                ], style=TD_STYLE),
                # RSI
                html.Td(
                    html.Span(f'{data["rsi"]:.1f}', style={
                        'color': RED if data['rsi'] > 70 else (GREEN if data['rsi'] < 30 else TEXT),
                        'fontWeight': '600',
                    }),
                    style=TD_STYLE,
                ),
                # SMA20
                html.Td(f'{data["sma20"]:.2f}', style={**TD_STYLE, 'color': '#ffa657'}),
                # SMA50
                html.Td(f'{data["sma50"]:.2f}', style={**TD_STYLE, 'color': '#d2a8ff'}),
                # vs SMA20 / SMA50
                vs_cell(data['vs20'], data['pct20']),
                vs_cell(data['vs50'], data['pct50']),
            ], style={'transition': 'background 0.15s'})

        tbody_rows.append(tr)

    return html.Table(
        [thead, html.Tbody(tbody_rows)],
        style={'width': '100%', 'borderCollapse': 'collapse', 'fontFamily': 'monospace'},
    )


# ── App & Layout ──────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    title='ISA Momentum Terminal',
    meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1'}],
    suppress_callback_exceptions=True,
)

# ── Auth ──────────────────────────────────────────────────────────────────────
server = app.server
server.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
DASHBOARD_PASSWORD = os.environ.get('DASHBOARD_PASSWORD')

_LOGIN_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ISA Momentum Terminal</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1117;min-height:100vh;display:flex;align-items:center;justify-content:center;font-family:monospace}
.card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:40px;width:100%;max-width:360px}
h1{color:#e6edf3;font-size:16px;font-weight:700;margin-bottom:4px;letter-spacing:.5px}
.sub{color:#8b949e;font-size:11px;margin-bottom:28px}
label{display:block;color:#8b949e;font-size:11px;margin-bottom:6px}
input{width:100%;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#e6edf3;padding:10px 12px;font-family:monospace;font-size:14px;margin-bottom:16px;outline:none}
input:focus{border-color:#58a6ff}
button{width:100%;background:#58a6ff;color:#000;border:none;border-radius:6px;padding:10px;font-family:monospace;font-size:13px;font-weight:700;cursor:pointer}
button:hover{background:#79baff}
.err{color:#f85149;font-size:11px;margin-bottom:12px}
</style>
</head>
<body>
<div class="card">
<h1>ISA Momentum Terminal</h1>
<p class="sub">LSE ETF Tracker · Live Data · yfinance</p>
ERROR_HTML
<form method="POST" action="/login">
<label>Password</label>
<input type="password" name="password" placeholder="Enter password" autofocus>
<button type="submit">Sign In</button>
</form>
</div>
</body>
</html>"""


@server.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == DASHBOARD_PASSWORD:
            session['authenticated'] = True
            return redirect('/')
        return _LOGIN_PAGE.replace('ERROR_HTML', '<p class="err">Incorrect password.</p>'), 401
    return _LOGIN_PAGE.replace('ERROR_HTML', '')


@server.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect('/login')


@server.before_request
def _require_auth():
    if not DASHBOARD_PASSWORD:
        return
    if request.path.startswith(('/login', '/logout')):
        return
    if not session.get('authenticated'):
        if request.path.startswith('/_dash'):
            return 'Unauthorized', 401
        return redirect('/login')


app.layout = html.Div([

    # ── Header ────────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.H1('ISA Momentum Terminal', style={
                'color': TEXT, 'margin': '0', 'fontSize': '18px',
                'fontWeight': '700', 'letterSpacing': '0.5px',
            }),
            html.P('LSE ETF Tracker  ·  Live Data  ·  yfinance', style={
                'color': MUTED, 'margin': '2px 0 0 0', 'fontSize': '11px',
            }),
        ]),
        html.Div(id='header-updated', style={
            'color': MUTED, 'fontSize': '11px', 'textAlign': 'right',
        }),
    ], style={
        'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
        'padding': '14px 20px', 'background': CARD,
        'borderBottom': f'1px solid {BORDER}',
    }),

    # ── Macro Alert Panel ─────────────────────────────────────────────────────
    html.Div(id='macro-alert-panel'),

    # ── Alert Banners ─────────────────────────────────────────────────────────
    html.Div(id='buy-alert-banner'),
    html.Div(id='sell-alert-banner'),

    # ── Tabs ──────────────────────────────────────────────────────────────────
    html.Div([
        dcc.Tabs(
            id='main-tabs',
            value='signal-summary',
            children=[
                dcc.Tab(
                    label='Signal Summary',
                    value='signal-summary',
                    style=TAB_STYLE,
                    selected_style=TAB_SELECTED,
                ),
                dcc.Tab(
                    label='Charts',
                    value='charts',
                    style=TAB_STYLE,
                    selected_style=TAB_SELECTED,
                ),
                dcc.Tab(
                    label='ISA & Retirement',
                    value='isa',
                    style=TAB_STYLE,
                    selected_style=TAB_SELECTED,
                ),
            ],
            colors={'border': BORDER, 'primary': ACCENT, 'background': BG},
        ),
    ], style={'background': CARD, 'borderBottom': f'1px solid {BORDER}', 'marginBottom': '20px'}),

    # ── Tab content ───────────────────────────────────────────────────────────
    html.Div(id='tab-content',
             style={'maxWidth': '1100px', 'margin': '0 auto', 'padding': '0 16px 40px'}),

    # ── Stores & intervals ────────────────────────────────────────────────────
    dcc.Store(id='selected-etf', data='IWMO'),
    dcc.Store(id='selected-tf',  data='1M'),
    dcc.Store(id='prev-signals', data={}),
    dcc.Store(id='buy-trigger',  data=[]),
    dcc.Store(id='sell-trigger', data=[]),
    html.Div(id='notif-dummy',      style={'display': 'none'}),
    html.Div(id='notif-sell-dummy', style={'display': 'none'}),
    dcc.Interval(id='refresh', interval=60_000, n_intervals=0),

], style={'background': BG, 'minHeight': '100vh', 'fontFamily': 'monospace'})


# ── Tab router ────────────────────────────────────────────────────────────────
@app.callback(
    Output('tab-content', 'children'),
    Input('main-tabs', 'value'),
    [State('selected-etf', 'data'), State('selected-tf', 'data')],
)
def render_tab(tab, sel_etf, sel_tf):
    if tab == 'signal-summary':
        return html.Div([
            card([
                html.Div([
                    html.Div([
                        html.H2('Signal Summary', style={
                            'color': TEXT, 'margin': '0', 'fontSize': '15px', 'fontWeight': '700',
                        }),
                        html.P('Live BUY / HOLD / SELL recommendations across all ETFs',
                               style={'color': MUTED, 'fontSize': '11px', 'margin': '2px 0 0 0'}),
                    ]),
                    html.Div([
                        html.Div(id='summary-updated',
                                 style={'color': MUTED, 'fontSize': '11px', 'marginBottom': '6px'}),
                        html.Div([
                            html.Button('Test Buy', id='test-alert-btn', n_clicks=0, style={
                                'background': 'transparent', 'border': f'1px solid {GREEN}',
                                'color': GREEN, 'padding': '3px 10px', 'borderRadius': '4px',
                                'cursor': 'pointer', 'fontFamily': 'monospace', 'fontSize': '11px',
                                'marginRight': '6px',
                            }),
                            html.Button('Test Sell', id='test-sell-btn', n_clicks=0, style={
                                'background': 'transparent', 'border': f'1px solid {RED}',
                                'color': RED, 'padding': '3px 10px', 'borderRadius': '4px',
                                'cursor': 'pointer', 'fontFamily': 'monospace', 'fontSize': '11px',
                            }),
                        ], style={'display': 'flex'}),
                    ], style={'textAlign': 'right'}),
                ], style={'display': 'flex', 'justifyContent': 'space-between',
                          'alignItems': 'flex-start', 'marginBottom': '16px'}),
                dcc.Loading(
                    html.Div(id='signal-table'),
                    color=ACCENT,
                ),
            ], {'overflowX': 'auto'}),
        ])

    if tab == 'charts':
        return html.Div([
            card(html.Div(
                [html.Button(etf, id={'type': 'etf-btn', 'index': etf}, n_clicks=0,
                             style=etf_btn_style(etf, sel_etf or 'IWMO'))
                 for etf in ETFS],
                style={'display': 'flex', 'gap': '8px', 'flexWrap': 'wrap'},
            ), {'padding': '14px 16px'}),

            card([
                html.Div([
                    html.Div([
                        html.H2(id='chart-title', style={
                            'color': TEXT, 'margin': '0', 'fontSize': '15px', 'fontWeight': '700',
                        }),
                        html.P(id='chart-subtitle', style={
                            'color': MUTED, 'margin': '2px 0 0 0', 'fontSize': '11px',
                        }),
                    ]),
                    html.Div([
                        html.Div(id='price-display'),
                        html.Div(id='signal-badge', style={'marginTop': '6px'}),
                    ], style={'textAlign': 'right'}),
                ], style={'display': 'flex', 'justifyContent': 'space-between',
                          'alignItems': 'flex-start', 'marginBottom': '14px'}),

                html.Div(
                    [html.Button(tf, id={'type': 'tf-btn', 'index': tf}, n_clicks=0,
                                 style=tf_btn_style(tf, sel_tf or '1M'))
                     for tf in TIMEFRAMES],
                    style={'display': 'flex', 'gap': '4px', 'marginBottom': '10px'},
                ),

                html.Div(id='signal-desc', style={
                    'color': MUTED, 'fontSize': '11px', 'marginBottom': '10px',
                    'padding': '6px 10px', 'background': BG, 'borderRadius': '6px',
                }),
                dcc.Loading(
                    dcc.Graph(id='main-chart', config={'displayModeBar': False}),
                    color=ACCENT,
                ),
            ]),
        ])

    # ISA & Retirement
    return html.Div([
        card([
            html.H3('ISA Allowance Tracker', style={
                'color': TEXT, 'marginBottom': '14px', 'fontSize': '15px', 'marginTop': '0',
            }),
            html.Div([
                html.Label('Amount invested this tax year (£)', style={
                    'color': MUTED, 'fontSize': '12px', 'display': 'block', 'marginBottom': '6px',
                }),
                dcc.Input(
                    id='isa-invested', type='number', value=0,
                    min=0, max=ISA_ALLOWANCE, step=100,
                    style={
                        'width': '100%', 'boxSizing': 'border-box',
                        'background': BG, 'border': f'1px solid {BORDER}',
                        'color': TEXT, 'padding': '8px 12px',
                        'borderRadius': '6px', 'fontSize': '16px', 'fontFamily': 'monospace',
                    },
                ),
            ], style={'marginBottom': '16px'}),
            html.Div(id='isa-stats'),
            dcc.Graph(id='isa-chart', config={'displayModeBar': False}),
        ]),

        card([
            html.H3('20-Year Retirement Projection', style={
                'color': TEXT, 'marginBottom': '4px', 'fontSize': '15px', 'marginTop': '0',
            }),
            html.P(f'£{MONTHLY_INVEST:,}/month  ·  {int(ANNUAL_RETURN*100)}% base annual return  ·  {PROJ_YEARS} years',
                   style={'color': MUTED, 'fontSize': '11px', 'marginBottom': '14px'}),
            html.Div([
                stat_box('Base Case (12%)',   f'£{PROJ_FINAL:,.0f}',              ACCENT),
                stat_box('Total Contributed', f'£{PROJ_CONTRIB:,.0f}',            TEXT),
                stat_box('Investment Growth', f'£{PROJ_FINAL - PROJ_CONTRIB:,.0f}', GREEN),
            ], style={'display': 'flex', 'gap': '10px', 'marginBottom': '14px'}),
            dcc.Graph(figure=PROJ_FIG, config={'displayModeBar': False}),
        ]),
    ])


# ── Signal Summary callback ───────────────────────────────────────────────────
@app.callback(
    [Output('signal-table',   'children'),
     Output('summary-updated', 'children')],
    [Input('main-tabs', 'value'),
     Input('refresh',   'n_intervals')],
)
def update_signal_summary(tab, _):
    if tab != 'signal-summary':
        return dash.no_update, dash.no_update

    rows = []
    for etf in ETFS:
        data = fetch_latest(TICKERS[etf])
        rows.append({'etf': etf, 'data': data})

    now = datetime.now().strftime('%H:%M:%S')
    return build_summary_table(rows), f'Updated {now}'


# ── ETF / TF store callbacks ──────────────────────────────────────────────────
@app.callback(
    Output('selected-etf', 'data'),
    [Input({'type': 'etf-btn', 'index': etf}, 'n_clicks') for etf in ETFS],
    prevent_initial_call=True,
)
def select_etf(*_):
    triggered = dash.callback_context.triggered[0]['prop_id'].split('.')[0]
    return json.loads(triggered)['index']


@app.callback(
    Output('selected-tf', 'data'),
    [Input({'type': 'tf-btn', 'index': tf}, 'n_clicks') for tf in TIMEFRAMES],
    prevent_initial_call=True,
)
def select_tf(*_):
    triggered = dash.callback_context.triggered[0]['prop_id'].split('.')[0]
    return json.loads(triggered)['index']


@app.callback(
    [Output({'type': 'etf-btn', 'index': etf}, 'style') for etf in ETFS],
    Input('selected-etf', 'data'),
)
def style_etf_buttons(selected):
    return [etf_btn_style(e, selected) for e in ETFS]


@app.callback(
    [Output({'type': 'tf-btn', 'index': tf}, 'style') for tf in TIMEFRAMES],
    Input('selected-tf', 'data'),
)
def style_tf_buttons(selected):
    return [tf_btn_style(t, selected) for t in TIMEFRAMES]


# ── Chart callback ────────────────────────────────────────────────────────────
@app.callback(
    [
        Output('main-chart',     'figure'),
        Output('chart-title',    'children'),
        Output('chart-subtitle', 'children'),
        Output('price-display',  'children'),
        Output('signal-badge',   'children'),
        Output('signal-desc',    'children'),
        Output('header-updated', 'children'),
    ],
    [
        Input('selected-etf', 'data'),
        Input('selected-tf',  'data'),
        Input('refresh',      'n_intervals'),
    ],
)
def update_chart(etf, tf, _):
    ticker = TICKERS[etf]
    days   = TIMEFRAMES[tf]
    df     = fetch_data(ticker, max(days, _INDICATOR_DAYS))
    now    = datetime.now().strftime('%H:%M:%S')

    def empty_fig(msg='No data available'):
        fig = go.Figure()
        fig.update_layout(
            template='plotly_dark', paper_bgcolor=CARD, plot_bgcolor=CARD, height=380,
            annotations=[dict(text=msg, x=0.5, y=0.5, showarrow=False,
                              font=dict(color=MUTED, size=15))],
        )
        return fig

    if df.empty:
        return empty_fig(), etf, ticker, '', '', 'Data unavailable', f'Updated {now}'

    cutoff     = pd.Timestamp.today() - pd.Timedelta(days=days)
    display_df = df[df.index >= cutoff]
    if display_df.empty:
        display_df = df.tail(20)

    close    = float(df['Close'].iloc[-1])
    prev     = float(df['Close'].iloc[-2]) if len(df) > 1 else close
    chg      = close - prev
    chg_pct  = (chg / prev * 100) if prev else 0
    rsi_s    = df['RSI'].dropna()
    sma20_s  = df['SMA20'].dropna()
    sma50_s  = df['SMA50'].dropna()
    rsi      = float(rsi_s.iloc[-1])   if not rsi_s.empty   else 50.0
    sma20    = float(sma20_s.iloc[-1]) if not sma20_s.empty else close
    sma50    = float(sma50_s.iloc[-1]) if not sma50_s.empty else close
    signal   = get_signal(rsi, close, sma20, sma50)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.70, 0.30], vertical_spacing=0.04)

    fig.add_trace(go.Candlestick(
        x=display_df.index,
        open=display_df['Open'], high=display_df['High'],
        low=display_df['Low'],   close=display_df['Close'],
        name='Price',
        increasing_line_color=GREEN, increasing_fillcolor=GREEN,
        decreasing_line_color=RED,   decreasing_fillcolor=RED,
    ), row=1, col=1)

    for col_name, color in [('SMA20', '#ffa657'), ('SMA50', '#d2a8ff')]:
        s = display_df[col_name].dropna()
        if not s.empty:
            fig.add_trace(go.Scatter(x=s.index, y=s, name=col_name,
                                     line=dict(color=color, width=1.5)), row=1, col=1)

    rsi_disp = display_df['RSI'].dropna()
    if not rsi_disp.empty:
        fig.add_trace(go.Scatter(
            x=rsi_disp.index, y=rsi_disp, name='RSI 14',
            line=dict(color=ACCENT, width=1.5),
            fill='tozeroy', fillcolor='rgba(88,166,255,0.10)',
        ), row=2, col=1)
        for level, lcolor in [(70, RED), (30, GREEN), (50, BORDER)]:
            fig.add_hline(y=level, line_dash='dot', line_color=lcolor,
                          line_width=1, row=2, col=1)

    fig.update_layout(
        template='plotly_dark', paper_bgcolor=CARD, plot_bgcolor=CARD,
        font=dict(family='monospace', color=TEXT, size=11),
        margin=dict(l=0, r=0, t=0, b=0), height=400, showlegend=True,
        legend=dict(orientation='h', y=1.03, x=0,
                    font=dict(size=10), bgcolor='rgba(0,0,0,0)'),
        xaxis_rangeslider_visible=False, hovermode='x unified',
    )
    fig.update_xaxes(gridcolor=BORDER, zeroline=False)
    fig.update_yaxes(gridcolor=BORDER, zeroline=False)
    fig.update_yaxes(title_text='Price (p)', row=1, col=1, title_font_size=10)
    fig.update_yaxes(title_text='RSI', row=2, col=1, range=[0, 100], title_font_size=10)

    arrow   = '+' if chg >= 0 else ''
    c_color = GREEN if chg >= 0 else RED
    price_el = html.Div([
        html.Span(f'{close:.2f}p', style={'color': TEXT, 'fontSize': '20px', 'fontWeight': '700'}),
        html.Span(f'  {arrow}{chg_pct:.2f}%', style={'color': c_color, 'fontSize': '13px', 'marginLeft': '6px'}),
        html.Br(),
        html.Span(f'RSI {rsi:.1f}  ·  SMA20 {sma20:.1f}  ·  SMA50 {sma50:.1f}',
                  style={'color': MUTED, 'fontSize': '10px'}),
    ])
    sig_color = SIG_COLOR[signal]
    badge = html.Span(signal, style={
        'background': sig_color,
        'color': '#000' if signal == 'BUY' else '#fff',
        'padding': '3px 12px', 'borderRadius': '20px',
        'fontWeight': '700', 'fontSize': '11px',
    })

    return (fig,
            f'{etf}  —  {ETF_NAMES.get(etf, "")}',
            f'{ticker}  ·  {tf} chart',
            price_el, badge, SIG_DESC[signal],
            f'Updated {now}')


# ── ISA callback ──────────────────────────────────────────────────────────────
@app.callback(
    [Output('isa-stats', 'children'), Output('isa-chart', 'figure')],
    Input('isa-invested', 'value'),
)
def update_isa(invested):
    invested  = min(float(invested or 0), ISA_ALLOWANCE)
    remaining = ISA_ALLOWANCE - invested
    used_pct  = invested / ISA_ALLOWANCE * 100
    today     = datetime.today()
    if today.month > 4 or (today.month == 4 and today.day >= 6):
        year_end = datetime(today.year + 1, 4, 5)
    else:
        year_end = datetime(today.year, 4, 5)
    days_left    = max((year_end - today).days, 1)
    monthly_left = remaining / (days_left / 30.44)

    stats = html.Div([html.Div([
        stat_box('Invested',         f'£{invested:,.0f}',     ACCENT),
        stat_box('Remaining',        f'£{remaining:,.0f}',    GREEN),
        stat_box('Days to Year End', str(days_left),          YELLOW),
        stat_box('Monthly Budget',   f'£{monthly_left:,.0f}', TEXT),
    ], style={'display': 'flex', 'gap': '10px', 'marginBottom': '14px'})])

    fig = go.Figure(go.Pie(
        values=[invested, remaining], labels=['Used', 'Remaining'],
        hole=0.70, marker=dict(colors=[ACCENT, BORDER]),
        textinfo='none', hovertemplate='%{label}: £%{value:,.0f}<extra></extra>',
    ))
    fig.add_annotation(x=0.5, y=0.58, text=f'{used_pct:.1f}%', showarrow=False,
                       font=dict(color=TEXT, size=20, family='monospace'))
    fig.add_annotation(x=0.5, y=0.38, text='used', showarrow=False,
                       font=dict(color=MUTED, size=11, family='monospace'))
    fig.update_layout(
        template='plotly_dark', paper_bgcolor=CARD, plot_bgcolor=CARD,
        font=dict(family='monospace', color=TEXT),
        margin=dict(l=0, r=0, t=0, b=0), height=200,
        legend=dict(orientation='h', y=-0.08, x=0.25, font=dict(size=11)),
    )
    return stats, fig


# ── Macro panel callback ─────────────────────────────────────────────────────
@app.callback(
    Output('macro-alert-panel', 'children'),
    Input('refresh', 'n_intervals'),
)
def update_macro_panel(_):
    return build_macro_panel(fetch_macro_indicators())


# ── Alert: transition detector (BUY + SELL) ───────────────────────────────────
@app.callback(
    [Output('prev-signals', 'data'),
     Output('buy-trigger',  'data'),
     Output('sell-trigger', 'data')],
    Input('refresh', 'n_intervals'),
    State('prev-signals', 'data'),
)
def check_alerts(_, prev):
    now_str      = datetime.now().strftime('%H:%M')
    new_signals  = {}
    buy_hits     = []
    sell_hits    = []

    for etf in ETFS:
        data = fetch_latest(TICKERS[etf])
        if data is None:
            new_signals[etf] = prev.get(etf, 'HOLD')
            continue
        rec      = data['rec']
        prev_rec = prev.get(etf)   # None on first load — skip alerting
        new_signals[etf] = rec

        if prev_rec is None:
            continue

        payload = {
            'etf':    etf,
            'name':   ETF_NAMES[etf],
            'price':  data['close'],
            'rsi':    data['rsi'],
            'pct20':  data['pct20'],
            'reason': data['reason'],
            'time':   now_str,
        }
        if prev_rec != 'BUY'  and rec == 'BUY':
            buy_hits.append(payload)
        if prev_rec != 'SELL' and rec == 'SELL':
            sell_hits.append(payload)

    return new_signals, buy_hits, sell_hits


# ── Buy Alert: banner renderer ────────────────────────────────────────────────
@app.callback(
    Output('buy-alert-banner', 'children'),
    Input('buy-trigger', 'data'),
)
def render_buy_banner(triggered):
    return _alert_banner(triggered, 'BUY')


# ── Buy Alert: dismiss ────────────────────────────────────────────────────────
@app.callback(
    Output('buy-trigger', 'data', allow_duplicate=True),
    Input('dismiss-alert-btn', 'n_clicks'),
    prevent_initial_call=True,
)
def dismiss_buy_alert(_):
    return []


# ── Sell Alert: banner renderer ───────────────────────────────────────────────
def _alert_banner(triggered, rec_type):
    if not triggered:
        return None
    color   = RED   if rec_type == 'SELL' else GREEN
    bg      = '#1a0d0d' if rec_type == 'SELL' else '#0d2018'
    glow    = 'rgba(248,81,73,0.18)' if rec_type == 'SELL' else 'rgba(63,185,80,0.18)'
    label   = f'{len(triggered)} ETF{"s" if len(triggered) > 1 else ""} entered {rec_type} territory'
    dismiss_id = 'dismiss-sell-btn' if rec_type == 'SELL' else 'dismiss-alert-btn'

    cards = []
    for item in triggered:
        cards.append(html.Div([
            html.Div([
                html.Span(rec_type, style={
                    'background': color, 'color': '#fff' if rec_type == 'SELL' else '#000',
                    'padding': '2px 10px', 'borderRadius': '20px',
                    'fontWeight': '700', 'fontSize': '11px',
                    'marginRight': '10px', 'letterSpacing': '0.5px',
                }),
                html.Span(item['etf'], style={
                    'color': TEXT, 'fontWeight': '700', 'fontSize': '16px', 'marginRight': '8px',
                }),
                html.Span(item['name'], style={'color': MUTED, 'fontSize': '12px'}),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '6px'}),
            html.P(item['reason'], style={
                'color': TEXT, 'fontSize': '12px', 'margin': '0 0 6px 0', 'lineHeight': '1.5',
            }),
            html.Div([
                html.Span(f"Price: {item['price']:.2f}p",
                          style={'color': MUTED, 'fontSize': '11px', 'marginRight': '14px'}),
                html.Span(f"RSI: {item['rsi']:.1f}",
                          style={'color': MUTED, 'fontSize': '11px', 'marginRight': '14px'}),
                html.Span(f"vs SMA20: {item['pct20']:+.1f}%",
                          style={'color': MUTED, 'fontSize': '11px', 'marginRight': '14px'}),
                html.Span(f"Detected: {item['time']}",
                          style={'color': MUTED, 'fontSize': '11px'}),
            ]),
        ], style={
            'background': bg,
            'border':     f'1px solid {color}',
            'borderLeft': f'4px solid {color}',
            'borderRadius': '8px',
            'padding':    '14px 16px',
            'marginBottom': '8px',
            'boxShadow':  f'0 0 18px {glow}',
        }))

    return html.Div([
        html.Div([
            html.Div([
                html.Span(f'NEW {rec_type} SIGNAL', style={
                    'color': color, 'fontWeight': '700', 'fontSize': '11px', 'letterSpacing': '1px',
                }),
                html.Span(f'  ·  {label}', style={'color': MUTED, 'fontSize': '11px'}),
            ]),
            html.Button('Dismiss', id=dismiss_id, n_clicks=0, style={
                'background': 'transparent', 'border': f'1px solid {BORDER}',
                'color': MUTED, 'padding': '3px 12px', 'borderRadius': '4px',
                'cursor': 'pointer', 'fontFamily': 'monospace', 'fontSize': '11px',
            }),
        ], style={'display': 'flex', 'justifyContent': 'space-between',
                  'alignItems': 'center', 'marginBottom': '10px'}),
        *cards,
    ], style={'maxWidth': '1100px', 'margin': '0 auto', 'padding': '12px 16px 4px'})


@app.callback(
    Output('sell-alert-banner', 'children'),
    Input('sell-trigger', 'data'),
)
def render_sell_banner(triggered):
    return _alert_banner(triggered, 'SELL')


@app.callback(
    Output('sell-trigger', 'data', allow_duplicate=True),
    Input('dismiss-sell-btn', 'n_clicks'),
    prevent_initial_call=True,
)
def dismiss_sell_alert(_):
    return []


# ── Browser notifications (clientside) ───────────────────────────────────────
def _notify_js(signal_type):
    return f"""
    function(triggered) {{
        if (!triggered || triggered.length === 0)
            return window.dash_clientside.no_update;
        if (!('Notification' in window)) return '';
        function doNotify() {{
            triggered.forEach(function(item) {{
                new Notification('{signal_type} Signal: ' + item.etf, {{
                    body: item.reason, tag: 'isa-' + item.etf + '-{signal_type.lower()}',
                }});
            }});
        }}
        if (Notification.permission === 'granted') {{
            doNotify();
        }} else if (Notification.permission === 'default') {{
            Notification.requestPermission().then(function(p) {{
                if (p === 'granted') doNotify();
            }});
        }}
        return '';
    }}
    """

app.clientside_callback(
    _notify_js('BUY'),
    Output('notif-dummy', 'children'),
    Input('buy-trigger', 'data'),
)

app.clientside_callback(
    _notify_js('SELL'),
    Output('notif-sell-dummy', 'children'),
    Input('sell-trigger', 'data'),
)


# ── Test alert callbacks ──────────────────────────────────────────────────────
@app.callback(
    Output('buy-trigger', 'data', allow_duplicate=True),
    Input('test-alert-btn', 'n_clicks'),
    prevent_initial_call=True,
)
def test_buy_alert(_):
    return [{
        'etf': 'IWMO', 'name': ETF_NAMES['IWMO'],
        'price': 2547.50, 'rsi': 28.3, 'pct20': -3.1,
        'reason': ('RSI is deeply oversold at 28 and price sits 3.1% below its '
                   '20-day average, pointing to a high-probability bounce entry.'),
        'time': datetime.now().strftime('%H:%M'),
    }]


@app.callback(
    Output('sell-trigger', 'data', allow_duplicate=True),
    Input('test-sell-btn', 'n_clicks'),
    prevent_initial_call=True,
)
def test_sell_alert(_):
    return [{
        'etf': 'WTAI', 'name': ETF_NAMES['WTAI'],
        'price': 1823.40, 'rsi': 74.6, 'pct20': 11.2,
        'reason': ('RSI is overbought at 75 and price has extended 11.2% above its '
                   '50-day average — the rally looks stretched and a pullback is likely.'),
        'time': datetime.now().strftime('%H:%M'),
    }]


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = '0.0.0.0'

    print("\n" + "=" * 52)
    print("  ISA Momentum Terminal")
    print("  Local:   http://localhost:8050")
    print(f"  Network: http://{local_ip}:8050")
    print("  (use Network URL to open on iPhone)")
    print("=" * 52 + "\n")
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8050)))

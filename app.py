import json
import os
import socket
from datetime import datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from flask import redirect, request, session

import dash
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from dash import Input, Output, State, dcc, html
from plotly.subplots import make_subplots

# ── Config ────────────────────────────────────────────────────────────────────
ETFS = ['IWMO', 'JEDG', 'SEMG', 'VDPG', 'WTAI', 'SGLS', 'FLXK']
TICKERS = {e: f'{e}.L' for e in ETFS}
ETF_NAMES = {
    'IWMO': 'iShares Edge MSCI World Momentum Factor UCITS ETF',
    'JEDG': 'VanEck Space Innovators UCITS ETF',
    'SEMG': 'Amundi MSCI Semiconductors ESG Screened UCITS ETF',
    'VDPG': 'Vanguard FTSE Dev Asia Pac ex-JP',
    'WTAI': 'WisdomTree AI',
    'SGLS': 'Invesco Physical Gold ETC (GBP Hedged)',
    'FLXK': 'Franklin FTSE Korea',
}
VOLUME_ETFS    = ['JEDG', 'VDPG', 'SEMG', 'FLXK']
WTAI_VOL_PROXY = 'AIAG.L'
# RS ratio pairs: etf → (benchmark_ticker, fx)
# fx='div': bench is USD, ETF is GBP → bench_gbp = bench_usd / GBPUSD
# fx='mul': bench is GBP, ETF is USD → bench_usd = bench_gbp * GBPUSD
RS_BENCHMARKS = {
    'SEMG': ('SOXX',   'div'),
    'IWMO': ('SWDA.L', 'mul'),
    'WTAI': ('EQQQ.L', 'mul'),
    'JEDG': ('UFO',    'div'),
    'SGLS': ('IGLN.L', 'div'),
    'VDPG': ('VAPX.L', None),
    'FLXK': ('EWY',    None),
}
TIMEFRAMES = {'1W': 7, '1M': 30, '3M': 90, '6M': 180, '1Y': 365}
_INDICATOR_DAYS = 365
ISA_ALLOWANCE  = 20_000
MONTHLY_INVEST = 1_667
ANNUAL_RETURN  = 0.12
PROJ_YEARS     = 20

# ── Palette ───────────────────────────────────────────────────────────────────
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

MACRO_STATUS_COLOR = {'CLEAR': GREEN, 'WATCH': YELLOW, 'WARNING': ORANGE, 'ALERT': RED}
MACRO_STATUS_BG    = {'CLEAR': '#0d1a0d', 'WATCH': '#1a1600', 'WARNING': '#1a0e00', 'ALERT': '#1a0d0d'}
MACRO_STATUS_TEXT_COLOR = {'CLEAR': '#000', 'WATCH': '#000', 'WARNING': '#000', 'ALERT': '#fff'}

SIG_COLOR  = {'BUY': GREEN, 'HOLD': YELLOW, 'SELL': RED}
SIG_DESC   = {
    'BUY':  'Oversold conditions detected — favourable entry point',
    'HOLD': 'No clear edge — hold existing positions or watch',
    'SELL': 'Overbought / extended — avoid chasing, wait for pullback',
}
REC_COLOR  = {'BUY': GREEN, 'HOLD': YELLOW, 'SELL': RED}
CONVICTION_COLOR = {'HIGH': GREEN, 'MED': YELLOW, 'LOW': MUTED}

_ACTION_TEXT = {
    ('BUY',  'HIGH'): 'Add full position at SMA20',
    ('BUY',  'MED'):  'Add partial — await confirmation',
    ('BUY',  'LOW'):  'Monitor — entry on pullback',
    ('HOLD', 'MED'):  'Watch — potential setup forming',
    ('HOLD', 'LOW'):  'Hold — no new entries',
    ('SELL', 'HIGH'): 'Exit / reduce position now',
    ('SELL', 'MED'):  'Trim on strength',
    ('SELL', 'LOW'):  'Hold — avoid adding here',
}


def get_action_text(rec: str, conviction: str) -> str:
    return _ACTION_TEXT.get((rec, conviction), 'Hold — monitor')


def get_row_tint(rec: str, conviction: str) -> str:
    if rec == 'BUY':
        if conviction == 'HIGH':
            return 'rgba(63,185,80,0.10)'
        if conviction == 'MED':
            return 'rgba(63,185,80,0.06)'
        return 'rgba(63,185,80,0.03)'
    if rec == 'SELL':
        if conviction == 'HIGH':
            return 'rgba(248,81,73,0.12)'
        return 'rgba(248,81,73,0.05)'
    if rec == 'HOLD' and conviction == 'MED':
        return 'rgba(88,166,255,0.06)'
    return 'transparent'

TAB_STYLE = {
    'background': BG, 'color': MUTED, 'border': 'none',
    'borderBottom': '2px solid transparent', 'padding': '10px 22px',
    'fontFamily': 'monospace', 'fontSize': '13px', 'fontWeight': '600', 'cursor': 'pointer',
}
TAB_SELECTED = {**TAB_STYLE, 'color': TEXT, 'borderBottom': f'2px solid {ACCENT}', 'background': CARD}

# ── Signal history (in-process; resets on server restart) ─────────────────────
_signal_history: dict = {}


def _update_signal_history(etf: str, new_signal: str) -> str:
    now  = datetime.now()
    prev = _signal_history.get(etf)
    if prev is None or prev['signal'] != new_signal:
        _signal_history[etf] = {'signal': new_signal, 'changed_at': now}
        return 'Just now'
    elapsed = now - prev['changed_at']
    if elapsed.days >= 1:
        return f'{elapsed.days}d ago'
    hours = elapsed.seconds // 3600
    if hours >= 1:
        return f'{hours}h ago'
    mins = elapsed.seconds // 60
    return f'{max(mins, 1)}m ago'


# ── Calculations ──────────────────────────────────────────────────────────────
def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta    = close.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
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


def get_conviction(signal: str, rsi: float, pct20: float, pct50: float) -> str:
    if signal == 'BUY':
        if rsi < 30 and pct20 < -2:
            return 'HIGH'
        if rsi < 38 or pct50 < -3:
            return 'MED'
        return 'LOW'
    if signal == 'SELL':
        if rsi > 70:
            return 'HIGH'
        if pct50 > 12 or rsi > 65:
            return 'MED'
        return 'LOW'
    if 43 <= rsi <= 58:
        return 'MED'
    return 'LOW'


def get_recommendation(rsi: float, close: float, sma20: float, sma50: float):
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
    else:
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
    try:
        if yf.Ticker(ticker).fast_info.currency == 'GBp':
            for col in ('Open', 'High', 'Low', 'Close'):
                df[col] = df[col] / 100
    except Exception:
        pass
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA50'] = df['Close'].rolling(50).mean()
    df['RSI']   = compute_rsi(df['Close'])
    return df


_gbpusd_cache: dict = {}

def _get_gbpusd() -> float:
    now = datetime.now()
    cached = _gbpusd_cache.get('rate')
    if cached and (now - _gbpusd_cache['ts']).seconds < 300:
        return cached
    try:
        rate = float(yf.Ticker('GBPUSD=X').fast_info.last_price)
        _gbpusd_cache.update({'rate': rate, 'ts': now})
        return rate
    except Exception:
        return cached or 1.34


# ── London market hours ───────────────────────────────────────────────────────
_LONDON_TZ    = ZoneInfo('Europe/London')
_MARKET_OPEN  = dt_time(8,  0)
_MARKET_CLOSE = dt_time(16, 35)


def _is_market_open() -> bool:
    now = datetime.now(_LONDON_TZ)
    if now.weekday() >= 5:
        return False
    return _MARKET_OPEN <= now.time() <= _MARKET_CLOSE


# ── Daily data cache (refreshes once per calendar day) ────────────────────────
_daily_cache: dict = {}


def _get_daily_df(ticker: str) -> pd.DataFrame:
    """1y daily OHLCV + SMA/RSI, cached per calendar day."""
    today  = datetime.today().date()
    cached = _daily_cache.get(ticker)
    if cached and cached['date'] == today:
        return cached['df']
    df = yf.download(ticker, period='1y', progress=False, auto_adjust=True)
    if not df.empty:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        try:
            if yf.Ticker(ticker).fast_info.currency == 'GBp':
                for col in ('Open', 'High', 'Low', 'Close'):
                    df[col] = df[col] / 100
        except Exception:
            pass
        df['SMA20'] = df['Close'].rolling(20).mean()
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['RSI']   = compute_rsi(df['Close'])
    _daily_cache[ticker] = {'date': today, 'ts': datetime.now(), 'df': df}
    return df


def fetch_daily(ticker: str) -> dict | None:
    """RSI, SMA20/50, drawdown — cached per calendar day, fetched once at startup."""
    df = _get_daily_df(ticker)
    if df.empty:
        return None
    rsi_s      = df['RSI'].dropna()
    s20_s      = df['SMA20'].dropna()
    s50_s      = df['SMA50'].dropna()
    close_eod  = float(df['Close'].iloc[-1])
    prev_eod   = float(df['Close'].iloc[-2]) if len(df) > 1 else close_eod
    sma20      = float(s20_s.iloc[-1]) if not s20_s.empty else close_eod
    sma50      = float(s50_s.iloc[-1]) if not s50_s.empty else close_eod
    rsi        = float(rsi_s.iloc[-1])  if not rsi_s.empty  else 50.0
    rsi_change = float(rsi_s.iloc[-1] - rsi_s.iloc[-11]) if len(rsi_s) >= 11 else None
    high_52w   = float(df['Close'].max())
    drawdown   = (close_eod / high_52w - 1) * 100 if high_52w else None
    vol_20d_avg = float(df['Volume'].iloc[max(-21, -len(df)):-1].mean()) if len(df) >= 3 else None
    return {
        'rsi': rsi, 'rsi_change': rsi_change,
        'sma20': sma20, 'sma50': sma50,
        'drawdown': drawdown,
        'close_eod': close_eod, 'prev_eod': prev_eod,
        'vol_20d_avg': vol_20d_avg,
        'cached_at': _daily_cache[ticker]['ts'].strftime('%H:%M'),
    }


def fetch_intraday(ticker: str, daily: dict) -> dict:
    """Live price + day% every 60s. Falls back to EOD outside 08:00–16:35 London."""
    prev = daily['prev_eod']
    if not _is_market_open():
        close   = daily['close_eod']
        chg_pct = (close / prev - 1) * 100 if prev else 0.0
        return {'close': close, 'chg_pct': chg_pct, 'vol_ratio': None, 'is_intraday': False}
    try:
        fi      = yf.Ticker(ticker).fast_info
        div     = 100 if fi.currency == 'GBp' else 1
        close   = float(fi.last_price) / div
        chg_pct = (close / prev - 1) * 100 if prev else 0.0
        df_1d   = yf.download(ticker, period='1d', interval='1m', progress=False, auto_adjust=True)
        vol_ratio = None
        if not df_1d.empty:
            if isinstance(df_1d.columns, pd.MultiIndex):
                df_1d.columns = df_1d.columns.droplevel(1)
            if 'Volume' in df_1d.columns:
                intraday_vol = float(df_1d['Volume'].sum())
                avg = daily.get('vol_20d_avg')
                if avg and avg > 0:
                    vol_ratio = intraday_vol / avg
        return {'close': close, 'chg_pct': chg_pct, 'vol_ratio': vol_ratio, 'is_intraday': True}
    except Exception:
        close   = daily['close_eod']
        chg_pct = (close / prev - 1) * 100 if prev else 0.0
        return {'close': close, 'chg_pct': chg_pct, 'vol_ratio': None, 'is_intraday': False}


def fetch_rs_ratio(etf: str) -> float | None:
    """Return 30-day % change of the ETF/benchmark RS ratio. FX cancels in ratio-of-ratios."""
    if etf not in RS_BENCHMARKS:
        return None
    bench_ticker, _ = RS_BENCHMARKS[etf]
    etf_df   = _get_daily_df(TICKERS[etf])
    bench_df = _get_daily_df(bench_ticker)
    if etf_df.empty or bench_df.empty:
        return None
    combined = pd.DataFrame({'etf': etf_df['Close'], 'bench': bench_df['Close']}).dropna()
    cutoff   = pd.Timestamp.today() - pd.Timedelta(days=30)
    window   = combined[combined.index >= cutoff]
    if len(window) < 2:
        return None
    rs = window['etf'] / window['bench']
    return (rs.iloc[-1] / rs.iloc[0] - 1) * 100


def _compute_vol_ratio(df: pd.DataFrame) -> float | None:
    if df.empty or 'Volume' not in df.columns or len(df) < 5:
        return None
    today_vol = float(df['Volume'].iloc[-1])
    window    = df['Volume'].iloc[max(-21, -len(df)):-1]
    avg_vol   = float(window.mean()) if len(window) > 0 else 0.0
    return today_vol / avg_vol if avg_vol > 0 else None


def fetch_latest(ticker: str, vol_proxy: str | None = None) -> dict | None:
    daily = fetch_daily(ticker)
    if daily is None:
        return None
    intra  = fetch_intraday(ticker, daily)
    close  = intra['close']
    sma20  = daily['sma20']
    sma50  = daily['sma50']
    pct20  = (close - sma20) / sma20 * 100
    pct50  = (close - sma50) / sma50 * 100
    rec, reason = get_recommendation(daily['rsi'], close, sma20, sma50)
    conviction  = get_conviction(rec, daily['rsi'], pct20, pct50)

    # Volume: intraday cumulative ratio if market open, else last EOD bar ratio
    vol_ratio   = intra['vol_ratio']
    proxy_label = None
    if vol_ratio is None:
        vol_ratio = _compute_vol_ratio(_get_daily_df(ticker))
    if vol_ratio is None and vol_proxy:
        vol_ratio = _compute_vol_ratio(_get_daily_df(vol_proxy))
        if vol_ratio is not None:
            proxy_label = vol_proxy

    # Weekly change: first EOD close in current ISO week vs current price
    eod_df     = _get_daily_df(ticker)
    last_date  = eod_df.index[-1]
    week_start = last_date - pd.Timedelta(days=last_date.dayofweek)
    week_df    = eod_df[eod_df.index >= week_start]
    if len(week_df) >= 2:
        wk_base      = float(week_df['Close'].iloc[0])
        week_chg_pct = (close - wk_base) / wk_base * 100
    else:
        week_chg_pct = 0.0

    return {
        'close': close, 'chg_pct': intra['chg_pct'], 'week_chg_pct': week_chg_pct,
        'vol_ratio': vol_ratio, 'vol_proxy': proxy_label,
        'rsi': daily['rsi'], 'sma20': sma20, 'sma50': sma50,
        'vs20': 'Above' if close >= sma20 else 'Below',
        'vs50': 'Above' if close >= sma50 else 'Below',
        'pct20': pct20, 'pct50': pct50,
        'rec': rec, 'reason': reason, 'conviction': conviction,
        'drawdown': daily['drawdown'], 'rsi_change': daily['rsi_change'],
        'daily_cached_at': daily['cached_at'],
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
            close      = float(df['Close'].iloc[-1])
            ma200      = float(df['Close'].rolling(200).mean().dropna().iloc[-1]) if len(df) >= 200 else None
            ma200_prev = (float(df['Close'].rolling(200).mean().dropna().iloc[-11])
                          if len(df) >= 210 else None)
            result[key] = {'close': close, 'ma200': ma200, 'ma200_prev': ma200_prev,
                           'as_of': datetime.now().strftime('%H:%M:%S')}
        except Exception:
            result[key] = None
    return result


def get_macro_status(key: str, data: dict) -> tuple:
    if data is None:
        return 'UNKNOWN', 'No data available', ''
    close = data['close']
    if key == 'TNX':
        if close >= 5.0:
            return ('ALERT', f'{close:.3f}% — ALERT zone (5.00%+)',
                    'Redirect contributions — SGLS gets 40% of monthly')
        if close >= 4.8:
            return ('WARNING', f'{close:.3f}% — WARNING zone (4.80–4.99%)',
                    'Pause SEMG/WTAI new buys — delay IWMO entry')
        if close >= 4.5:
            return ('WATCH', f'{close:.3f}% — WATCH zone (4.50–4.79%)', '')
        return ('CLEAR', f'{close:.3f}% — CLEAR zone (below 4.50%)', '')
    if key == 'TYX':
        if close >= 5.3:
            return ('ALERT', f'{close:.3f}% — ALERT zone (5.30%+)',
                    'Structural regime shift — multi-year re-rating risk')
        if close >= 5.0:
            return ('WARNING', f'{close:.3f}% — WARNING zone (5.00–5.29%)', '')
        if close >= 4.8:
            return ('WATCH', f'{close:.3f}% — WATCH zone (4.80–4.99%)', '')
        return ('CLEAR', f'{close:.3f}% — CLEAR zone (below 4.80%)', '')
    if key == 'SOX':
        ma200 = data.get('ma200')
        if ma200 is None:
            return 'UNKNOWN', 'Insufficient history for 200DMA', ''
        ma200_prev  = data.get('ma200_prev')
        pct         = (close - ma200) / ma200 * 100
        pct_str     = f'+{pct:.1f}%' if pct >= 0 else f'{pct:.1f}%'
        ma_declining = (ma200_prev is not None) and (ma200 < ma200_prev)
        if close < ma200 and ma_declining:
            return ('ALERT',
                    f'{close:,.1f} — {pct_str} vs 200DMA ({ma200:,.0f}) — ALERT zone (sustained break, MA declining)',
                    'Pause SEMG additions — redirect to VDPG/SGLS')
        if close < ma200:
            return ('WARNING',
                    f'{close:,.1f} — {pct_str} vs 200DMA ({ma200:,.0f}) — WARNING zone (below 200DMA)',
                    'Pause SEMG additions — redirect to VDPG/SGLS')
        if pct <= 3.0:
            return ('WATCH',
                    f'{close:,.1f} — {pct_str} vs 200DMA ({ma200:,.0f}) — WATCH zone (within 3% of 200DMA)', '')
        return ('CLEAR',
                f'{close:,.1f} — {pct_str} vs 200DMA ({ma200:,.0f}) — CLEAR zone (>3% above 200DMA)', '')
    return 'UNKNOWN', '', ''


_MACRO_META = {
    'TNX': ('TNX', '10Y Treasury Yield'),
    'TYX': ('TYX', '30Y Treasury Yield'),
    'SOX': ('SOX', 'Philadelphia Semiconductor Index'),
}


def build_macro_panel(macro_data: dict) -> html.Div:
    cards = []
    for key in ['TNX', 'TYX', 'SOX']:
        data      = macro_data.get(key)
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
                html.Span(ticker_label, style={'color': TEXT, 'fontWeight': '700', 'fontSize': '15px', 'marginRight': '8px'}),
                html.Span(full_name, style={'color': MUTED, 'fontSize': '11px'}),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '6px'}),
            html.P(threshold_label, style={
                'color': TEXT, 'fontSize': '13px', 'margin': '0 0 4px 0',
                'fontFamily': 'monospace', 'fontWeight': '600',
            }),
        ]
        if action:
            card_children.append(html.P(f'Action: {action}', style={
                'color': color, 'fontSize': '12px', 'margin': '4px 0 0 0', 'fontStyle': 'italic',
            }))
        if as_of:
            card_children.append(html.Span(f'as of {as_of}', style={
                'color': MUTED, 'fontSize': '10px', 'display': 'block', 'marginTop': '6px',
            }))
        cards.append(html.Div(card_children, style={
            'background': bg, 'border': f'1px solid {color}',
            'borderLeft': f'4px solid {color}', 'borderRadius': '8px',
            'padding': '12px 16px', 'flex': '1', 'minWidth': '260px',
            'boxShadow': f'0 0 14px {color}28',
        }))

    return html.Div([
        html.Div([
            html.Span('MACRO CONDITIONS', style={'color': MUTED, 'fontWeight': '700', 'fontSize': '11px', 'letterSpacing': '1px'}),
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
        'fontFamily': 'monospace', 'fontSize': '12px', 'fontWeight': '600', 'borderRadius': '4px',
    }


def toggle_btn_style(this_val: str, current_val: str) -> dict:
    active = this_val == current_val
    return {
        'background': ACCENT if active else 'transparent',
        'color': '#000' if active else MUTED,
        'border': f'1px solid {ACCENT if active else BORDER}',
        'borderRadius': '5px', 'padding': '4px 13px', 'cursor': 'pointer',
        'fontFamily': 'monospace', 'fontSize': '11px', 'fontWeight': '700',
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

# ── Table styles ──────────────────────────────────────────────────────────────
TH_STYLE = {
    'padding': '10px 14px', 'color': MUTED, 'fontSize': '11px',
    'fontWeight': '600', 'textAlign': 'left', 'borderBottom': f'1px solid {BORDER}',
    'whiteSpace': 'nowrap',
}
TD_STYLE = {
    'padding': '12px 14px', 'fontSize': '13px', 'verticalAlign': 'middle',
    'borderBottom': f'1px solid {BORDER}',
}


# ── Macro threshold reference panel ──────────────────────────────────────────
def _macro_threshold_reference() -> html.Div:
    TH_C = {**TH_STYLE, 'textAlign': 'left', 'whiteSpace': 'nowrap', 'paddingLeft': '14px'}
    TD_C = {**TD_STYLE, 'fontSize': '12px', 'verticalAlign': 'top', 'paddingLeft': '14px'}

    def tier_col(label, color, range_text, action=None):
        children = [
            html.Span(label, style={
                'background': color + '22', 'color': color,
                'border': f'1px solid {color}',
                'padding': '2px 9px', 'borderRadius': '20px',
                'fontWeight': '700', 'fontSize': '11px', 'letterSpacing': '0.4px',
                'display': 'inline-block', 'marginBottom': '5px',
            }),
            html.Div(range_text, style={'color': color, 'fontSize': '12px', 'fontWeight': '600',
                                        'marginBottom': '4px' if action else '0'}),
        ]
        if action:
            children.append(html.Div(action, style={
                'color': MUTED, 'fontSize': '11px', 'lineHeight': '1.5',
                'borderLeft': f'2px solid {color}', 'paddingLeft': '6px', 'marginTop': '2px',
            }))
        return html.Td(children, style={**TD_C, 'minWidth': '160px'})

    rows = [
        html.Tr([
            html.Td([
                html.Div('TNX', style={'color': TEXT, 'fontWeight': '700', 'fontSize': '13px'}),
                html.Div('10Y Treasury Yield', style={'color': MUTED, 'fontSize': '10px', 'marginTop': '2px'}),
            ], style=TD_C),
            tier_col('CLEAR',   GREEN,  'below 4.50%'),
            tier_col('WATCH',   YELLOW, '4.50 – 4.79%'),
            tier_col('WARNING', ORANGE, '4.80 – 4.99%', 'Pause SEMG/WTAI new buys\nDelay IWMO entry'),
            tier_col('ALERT',   RED,    '5.00%+',        'Redirect contributions\nSGLS gets 40% of monthly'),
        ], style={'borderBottom': f'1px solid {BORDER}'}),
        html.Tr([
            html.Td([
                html.Div('TYX', style={'color': TEXT, 'fontWeight': '700', 'fontSize': '13px'}),
                html.Div('30Y Treasury Yield', style={'color': MUTED, 'fontSize': '10px', 'marginTop': '2px'}),
            ], style=TD_C),
            tier_col('CLEAR',   GREEN,  'below 4.80%'),
            tier_col('WATCH',   YELLOW, '4.80 – 4.99%'),
            tier_col('WARNING', ORANGE, '5.00 – 5.29%'),
            tier_col('ALERT',   RED,    '5.30%+', 'Structural regime shift\nMulti-year re-rating risk'),
        ], style={'borderBottom': f'1px solid {BORDER}'}),
        html.Tr([
            html.Td([
                html.Div('SOX', style={'color': TEXT, 'fontWeight': '700', 'fontSize': '13px'}),
                html.Div('Semiconductor Index', style={'color': MUTED, 'fontSize': '10px', 'marginTop': '2px'}),
            ], style=TD_C),
            tier_col('CLEAR',   GREEN,  '>3% above 200DMA'),
            tier_col('WATCH',   YELLOW, 'Within 3% of 200DMA'),
            tier_col('WARNING', ORANGE, 'First close below 200DMA',      'Pause SEMG additions\nRedirect to VDPG/SGLS'),
            tier_col('ALERT',   RED,    'Sustained break + MA declining', 'Pause SEMG additions\nRedirect to VDPG/SGLS'),
        ]),
    ]
    thead = html.Thead(html.Tr([html.Th(h, style=TH_C) for h in ['Indicator', 'CLEAR', 'WATCH', 'WARNING', 'ALERT']]))
    return card([
        html.H3('Macro Alert Thresholds & Rationale', style={
            'color': TEXT, 'margin': '0 0 4px 0', 'fontSize': '14px', 'fontWeight': '700',
        }),
        html.P('Static reference — thresholds applied to the live macro panel above',
               style={'color': MUTED, 'fontSize': '11px', 'margin': '0 0 16px 0'}),
        html.Div(
            html.Table([thead, html.Tbody(rows)],
                       style={'width': '100%', 'borderCollapse': 'collapse', 'fontFamily': 'monospace'}),
            style={'overflowX': 'auto'},
        ),
    ])


# ── Signal Summary table ──────────────────────────────────────────────────────
def build_summary_table(rows: list[dict], show_week: bool = False) -> html.Table:
    period_label = 'Wk %' if show_week else 'Day %'
    headers = ['ETF', f'PRICE · {period_label}', 'VOLUME', 'CONVICTION', 'ACTION', 'ENTRY AT', 'RSI 14', 'SMA POSITION', '52W DRAWDOWN', 'RS TREND 30d', 'SIGNAL CHANGED']
    thead = html.Thead(html.Tr([html.Th(h, style=TH_STYLE) for h in headers]))

    tbody_rows = []
    for row in rows:
        etf         = row['etf']
        data        = row.get('data')
        sig_changed = row.get('sig_changed', '—')

        if data is None:
            tr = html.Tr([
                html.Td([
                    html.Div(etf, style={'color': TEXT, 'fontWeight': '700', 'fontSize': '14px'}),
                    html.Div(ETF_NAMES[etf], style={'color': MUTED, 'fontSize': '10px', 'marginTop': '2px'}),
                ], style=TD_STYLE),
                html.Td('No data', colSpan=10, style={**TD_STYLE, 'color': MUTED}),
            ], style={'borderBottom': f'1px solid {BORDER}'})
        else:
            rec        = data['rec']
            conv       = data['conviction']
            chg_pct    = data['week_chg_pct'] if show_week else data['chg_pct']
            chg_color  = GREEN if chg_pct > 0 else (RED if chg_pct < 0 else MUTED)
            arrow      = '+' if chg_pct >= 0 else ''
            row_bg     = get_row_tint(rec, conv)
            conv_color = CONVICTION_COLOR[conv]
            rec_color  = REC_COLOR[rec]

            # ETF name cell — WTAI gets AIAG.L proxy note
            etf_name_children = [
                html.Div(etf, style={'color': TEXT, 'fontWeight': '700', 'fontSize': '14px'}),
                html.Div(ETF_NAMES[etf], style={'color': MUTED, 'fontSize': '10px', 'marginTop': '2px'}),
            ]
            if etf == 'WTAI':
                etf_name_children.append(html.Div(
                    'vol: AIAG.L',
                    style={'color': MUTED, 'fontSize': '10px', 'fontStyle': 'italic', 'marginTop': '2px'},
                ))
            etf_cell = html.Td(etf_name_children, style=TD_STYLE)

            # Volume cell
            vr = data.get('vol_ratio')
            if vr is not None:
                vol_color  = GREEN if vr >= 1.3 else (YELLOW if vr >= 0.8 else MUTED)
                proxy_note = data.get('vol_proxy')
                vol_cell = html.Td([
                    html.Span(f'{vr:.1f}×', style={'color': vol_color, 'fontWeight': '700'}),
                    html.Div(
                        f'vs 20d avg{" (proxy)" if proxy_note else ""}',
                        style={'color': MUTED, 'fontSize': '10px'},
                    ),
                ], style=TD_STYLE)
            else:
                vol_cell = html.Td('—', style={**TD_STYLE, 'color': MUTED, 'fontSize': '12px'})

            # Conviction cell
            conv_cell = html.Td(
                html.Span(conv, style={
                    'background': conv_color + '22', 'color': conv_color,
                    'border': f'1px solid {conv_color}',
                    'padding': '2px 9px', 'borderRadius': '20px',
                    'fontWeight': '700', 'fontSize': '11px',
                }),
                style=TD_STYLE,
            )

            # Action cell — specific instruction text
            action_cell = html.Td(
                html.Div(get_action_text(rec, conv), style={
                    'color': rec_color, 'fontSize': '12px', 'fontWeight': '600',
                }),
                style=TD_STYLE,
            )

            # Entry AT cell
            if rec == 'BUY':
                entry_val   = f'{data["sma20"]:.2f}'
                entry_sub   = 'near SMA20'
                entry_color = GREEN
            elif rec == 'SELL':
                entry_val   = 'Avoid'
                entry_sub   = 'wait for pullback'
                entry_color = RED
            else:
                entry_val   = f'{data["sma50"]:.2f}'
                entry_sub   = 'watch SMA50'
                entry_color = MUTED
            entry_cell = html.Td([
                html.Div(entry_val, style={'color': entry_color, 'fontWeight': '700', 'fontSize': '13px'}),
                html.Div(entry_sub, style={'color': MUTED, 'fontSize': '10px', 'marginTop': '2px'}),
            ], style=TD_STYLE)

            # RSI 14 cell
            rsi_val    = data['rsi']
            rsi_color  = RED if rsi_val > 70 else (GREEN if rsi_val < 30 else TEXT)
            rsi_chg    = data.get('rsi_change')
            rsi_chg_el = []
            if rsi_chg is not None:
                chg_sign  = '+' if rsi_chg >= 0 else ''
                chg_color = GREEN if rsi_chg > 1.5 else (RED if rsi_chg < -1.5 else YELLOW)
                rsi_chg_el = [html.Span(
                    f'  {chg_sign}{rsi_chg:.1f}',
                    style={'color': chg_color, 'fontSize': '10px'},
                )]
            rsi_cell = html.Td(
                [html.Span(f'{rsi_val:.1f}', style={'color': rsi_color, 'fontWeight': '600'})] + rsi_chg_el,
                style=TD_STYLE,
            )

            # SMA POSITION cell
            vs20_color = GREEN if data['vs20'] == 'Above' else RED
            vs50_color = GREEN if data['vs50'] == 'Above' else RED
            sma_cell   = html.Td([
                html.Div([
                    html.Span('20: ', style={'color': MUTED, 'fontSize': '10px'}),
                    html.Span(f'{data["sma20"]:.2f}', style={'color': '#ffa657', 'fontSize': '12px'}),
                    html.Span(f'  {data["vs20"]}', style={'color': vs20_color, 'fontSize': '10px'}),
                ]),
                html.Div([
                    html.Span('50: ', style={'color': MUTED, 'fontSize': '10px'}),
                    html.Span(f'{data["sma50"]:.2f}', style={'color': '#d2a8ff', 'fontSize': '12px'}),
                    html.Span(f'  {data["vs50"]}', style={'color': vs50_color, 'fontSize': '10px'}),
                ], style={'marginTop': '3px'}),
            ], style=TD_STYLE)

            # Signal changed cell
            changed_color = ACCENT if sig_changed == 'Just now' else MUTED
            changed_cell  = html.Td(
                html.Span(sig_changed, style={'color': changed_color, 'fontSize': '12px'}),
                style=TD_STYLE,
            )

            # 52W drawdown cell
            dd = data.get('drawdown')
            if dd is not None:
                dd_color = GREEN if dd > -5 else (RED if dd < -10 else YELLOW)
                dd_cell  = html.Td(
                    html.Span(f'{dd:.1f}%', style={'color': dd_color, 'fontWeight': '700', 'fontSize': '13px'}),
                    style=TD_STYLE,
                )
            else:
                dd_cell = html.Td('—', style={**TD_STYLE, 'color': MUTED, 'fontSize': '12px'})

            # RS trend cell
            rs_trend    = data.get('rs_ratio')
            bench_label = RS_BENCHMARKS.get(etf, (None,))[0]
            if rs_trend is not None:
                arrow = '↑' if rs_trend > 1.5 else ('↓' if rs_trend < -1.5 else '→')
                color = GREEN if rs_trend > 1.5 else (RED if rs_trend < -1.5 else YELLOW)
                sign  = '+' if rs_trend >= 0 else ''
                rs_cell = html.Td([
                    html.Div(f'{arrow} {sign}{rs_trend:.1f}%', style={'color': color, 'fontWeight': '700', 'fontSize': '13px'}),
                    html.Div(f'vs {bench_label}', style={'color': MUTED, 'fontSize': '10px', 'marginTop': '2px'}),
                ], style=TD_STYLE)
            else:
                rs_cell = html.Td('—', style={**TD_STYLE, 'color': MUTED, 'fontSize': '12px'})

            tr = html.Tr([
                etf_cell,
                html.Td([
                    html.Span(f'{data["close"]:.2f}', style={'color': TEXT, 'fontWeight': '700'}),
                    html.Br(),
                    html.Span(f'{arrow}{chg_pct:.2f}%', style={'color': chg_color, 'fontSize': '11px'}),
                ], style=TD_STYLE),
                vol_cell,
                conv_cell,
                action_cell,
                entry_cell,
                rsi_cell,
                sma_cell,
                dd_cell,
                rs_cell,
                changed_cell,
            ], style={
                'background': row_bg,
                'borderLeft': f'4px solid {conv_color}',
                'transition': 'background 0.15s',
                'borderBottom': f'1px solid {BORDER}',
            })

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
                'color': TEXT, 'margin': '0', 'fontSize': '18px', 'fontWeight': '700', 'letterSpacing': '0.5px',
            }),
            html.P('LSE ETF Tracker  ·  Live Data  ·  yfinance', style={
                'color': MUTED, 'margin': '2px 0 0 0', 'fontSize': '11px',
            }),
        ]),
        html.Div(id='header-updated', style={'color': MUTED, 'fontSize': '11px', 'textAlign': 'right'}),
    ], style={
        'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
        'padding': '14px 20px', 'background': CARD, 'borderBottom': f'1px solid {BORDER}',
    }),

    # ── Macro Alert Panel ─────────────────────────────────────────────────────
    html.Div(id='macro-alert-panel'),

    # ── Tabs ──────────────────────────────────────────────────────────────────
    html.Div([
        dcc.Tabs(
            id='main-tabs', value='signal-summary',
            children=[
                dcc.Tab(label='Signal Summary', value='signal-summary',
                        style=TAB_STYLE, selected_style=TAB_SELECTED),
                dcc.Tab(label='Charts',          value='charts',
                        style=TAB_STYLE, selected_style=TAB_SELECTED),
                dcc.Tab(label='ISA & Retirement', value='isa',
                        style=TAB_STYLE, selected_style=TAB_SELECTED),
            ],
            colors={'border': BORDER, 'primary': ACCENT, 'background': BG},
        ),
    ], style={'background': CARD, 'borderBottom': f'1px solid {BORDER}', 'marginBottom': '20px'}),

    # ── Tab content ───────────────────────────────────────────────────────────
    html.Div(id='tab-content',
             style={'maxWidth': '1100px', 'margin': '0 auto', 'padding': '0 16px 40px'}),

    # ── Stores & intervals ────────────────────────────────────────────────────
    dcc.Store(id='selected-etf',  data='IWMO'),
    dcc.Store(id='selected-tf',   data='1M'),
    dcc.Store(id='price-period',  data='today'),
    dcc.Interval(id='refresh', interval=60_000, n_intervals=0),

], style={'background': BG, 'minHeight': '100vh', 'fontFamily': 'monospace'})


# ── Tab router ────────────────────────────────────────────────────────────────
@app.callback(
    Output('tab-content', 'children'),
    Input('main-tabs', 'value'),
    [State('selected-etf', 'data'), State('selected-tf', 'data'), State('price-period', 'data')],
)
def render_tab(tab, sel_etf, sel_tf, price_period):
    if tab == 'signal-summary':
        period = price_period or 'today'
        return html.Div([
            card([
                html.Div([
                    html.Div([
                        html.H2('Signal Summary', style={
                            'color': TEXT, 'margin': '0', 'fontSize': '15px', 'fontWeight': '700',
                        }),
                        html.P('Live BUY / HOLD / SELL recommendations · sorted by daily gain',
                               style={'color': MUTED, 'fontSize': '11px', 'margin': '2px 0 0 0'}),
                    ]),
                    html.Div([
                        html.Div([
                            html.Span('Show change:', style={'color': MUTED, 'fontSize': '11px', 'marginRight': '8px'}),
                            html.Button('Today', id='btn-today', n_clicks=0,
                                        style=toggle_btn_style('today', period)),
                            html.Button('This Week', id='btn-week', n_clicks=0,
                                        style={**toggle_btn_style('week', period), 'marginLeft': '4px'}),
                        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '6px'}),
                        html.Div(id='summary-updated', style={'color': MUTED, 'fontSize': '11px', 'textAlign': 'right'}),
                    ], style={'textAlign': 'right'}),
                ], style={'display': 'flex', 'justifyContent': 'space-between',
                          'alignItems': 'flex-start', 'marginBottom': '16px'}),
                dcc.Loading(html.Div(id='signal-table'), color=ACCENT),
            ], {'overflowX': 'auto'}),
            _macro_threshold_reference(),
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
                        html.P(id='chart-subtitle', style={'color': MUTED, 'margin': '2px 0 0 0', 'fontSize': '11px'}),
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
                dcc.Loading(dcc.Graph(id='main-chart', config={'displayModeBar': False}), color=ACCENT),
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
                stat_box('Base Case (12%)',    f'£{PROJ_FINAL:,.0f}',              ACCENT),
                stat_box('Total Contributed',  f'£{PROJ_CONTRIB:,.0f}',            TEXT),
                stat_box('Investment Growth',  f'£{PROJ_FINAL - PROJ_CONTRIB:,.0f}', GREEN),
            ], style={'display': 'flex', 'gap': '10px', 'marginBottom': '14px'}),
            dcc.Graph(figure=PROJ_FIG, config={'displayModeBar': False}),
        ]),
    ])


# ── Price period toggle ───────────────────────────────────────────────────────
@app.callback(
    Output('price-period', 'data'),
    [Input('btn-today', 'n_clicks'), Input('btn-week', 'n_clicks')],
    prevent_initial_call=True,
)
def toggle_price_period(n_today, n_week):
    triggered = dash.callback_context.triggered[0]['prop_id']
    return 'week' if 'btn-week' in triggered else 'today'


@app.callback(
    [Output('btn-today', 'style'), Output('btn-week', 'style')],
    Input('price-period', 'data'),
)
def style_toggle_buttons(period):
    p = period or 'today'
    return toggle_btn_style('today', p), {**toggle_btn_style('week', p), 'marginLeft': '4px'}


# ── Signal Summary callback ───────────────────────────────────────────────────
@app.callback(
    [Output('signal-table',    'children'),
     Output('summary-updated', 'children')],
    [Input('main-tabs',    'value'),
     Input('refresh',      'n_intervals'),
     Input('price-period', 'data')],
)
def update_signal_summary(tab, _, price_period):
    if tab != 'signal-summary':
        return dash.no_update, dash.no_update

    show_week = (price_period or 'today') == 'week'
    rows = []
    for etf in ETFS:
        proxy     = WTAI_VOL_PROXY if etf == 'WTAI' else None
        data      = fetch_latest(TICKERS[etf], vol_proxy=proxy)
        # Clear volume for ETFs not in VOLUME_ETFS and not WTAI
        if data and etf not in VOLUME_ETFS and etf != 'WTAI':
            data['vol_ratio'] = None
        if data:
            data['rs_ratio'] = fetch_rs_ratio(etf)
        sig_changed = _update_signal_history(etf, data['rec']) if data else '—'
        rows.append({'etf': etf, 'data': data, 'sig_changed': sig_changed})

    # Sort gainers first (by today's daily change regardless of toggle)
    rows.sort(key=lambda r: r['data']['chg_pct'] if r['data'] else -999.0, reverse=True)

    now      = datetime.now().strftime('%H:%M:%S')
    daily_ts = next((r['data']['daily_cached_at'] for r in rows if r['data']), None)
    updated_el = html.Div([
        html.Div(f'Updated {now}', style={'color': MUTED, 'fontSize': '11px'}),
        html.Div(
            f'Daily stats as of {daily_ts}' if daily_ts else '',
            style={'color': MUTED, 'fontSize': '10px', 'marginTop': '1px'},
        ),
    ])
    return build_summary_table(rows, show_week=show_week), updated_el


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
    ticker     = TICKERS[etf]
    days       = TIMEFRAMES[tf]
    df         = fetch_data(ticker, max(days, _INDICATOR_DAYS))
    now        = datetime.now().strftime('%H:%M:%S')
    has_volume = etf in VOLUME_ETFS

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

    close   = float(df['Close'].iloc[-1])
    prev    = float(df['Close'].iloc[-2]) if len(df) > 1 else close
    chg     = close - prev
    chg_pct = (chg / prev * 100) if prev else 0
    rsi_s   = df['RSI'].dropna()
    sma20_s = df['SMA20'].dropna()
    sma50_s = df['SMA50'].dropna()
    rsi     = float(rsi_s.iloc[-1])   if not rsi_s.empty   else 50.0
    sma20   = float(sma20_s.iloc[-1]) if not sma20_s.empty else close
    sma50   = float(sma50_s.iloc[-1]) if not sma50_s.empty else close
    signal  = get_signal(rsi, close, sma20, sma50)

    # Determine volume source
    wtai_volume = etf == 'WTAI'
    show_volume = has_volume or wtai_volume

    if show_volume:
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                            row_heights=[0.55, 0.25, 0.20], vertical_spacing=0.03)
    else:
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
            fig.add_hline(y=level, line_dash='dot', line_color=lcolor, line_width=1, row=2, col=1)

    if wtai_volume:
        proxy_df = fetch_data(WTAI_VOL_PROXY, max(days, _INDICATOR_DAYS))
        if not proxy_df.empty:
            proxy_disp = proxy_df[proxy_df.index >= cutoff]
            if proxy_disp.empty:
                proxy_disp = proxy_df.tail(20)
            vol_colors = [
                GREEN if float(r['Close']) >= float(r['Open']) else RED
                for _, r in proxy_disp.iterrows()
            ]
            fig.add_trace(go.Bar(
                x=proxy_disp.index, y=proxy_disp['Volume'],
                name='Volume (AIAG.L)', marker_color=vol_colors, opacity=0.65,
            ), row=3, col=1)
            avg_proxy = proxy_df['Volume'].rolling(20).mean()
            avg_proxy_disp = avg_proxy[avg_proxy.index >= cutoff].dropna()
            if not avg_proxy_disp.empty:
                fig.add_trace(go.Scatter(
                    x=avg_proxy_disp.index, y=avg_proxy_disp, name='Avg Vol 20d',
                    line=dict(color=YELLOW, width=1.2, dash='dot'),
                ), row=3, col=1)
    elif has_volume and 'Volume' in display_df.columns:
        vol_colors = [
            GREEN if float(row['Close']) >= float(row['Open']) else RED
            for _, row in display_df.iterrows()
        ]
        fig.add_trace(go.Bar(
            x=display_df.index, y=display_df['Volume'],
            name='Volume', marker_color=vol_colors, opacity=0.65,
        ), row=3, col=1)
        avg_vol_s = df['Volume'].rolling(20).mean()
        avg_disp  = avg_vol_s[avg_vol_s.index >= cutoff].dropna()
        if not avg_disp.empty:
            fig.add_trace(go.Scatter(
                x=avg_disp.index, y=avg_disp, name='Avg Vol 20d',
                line=dict(color=YELLOW, width=1.2, dash='dot'),
            ), row=3, col=1)

    chart_height = 460 if show_volume else 400
    fig.update_layout(
        template='plotly_dark', paper_bgcolor=CARD, plot_bgcolor=CARD,
        font=dict(family='monospace', color=TEXT, size=11),
        margin=dict(l=0, r=0, t=0, b=0), height=chart_height, showlegend=True,
        legend=dict(orientation='h', y=1.03, x=0, font=dict(size=10), bgcolor='rgba(0,0,0,0)'),
        xaxis_rangeslider_visible=False, hovermode='x unified',
    )
    fig.update_xaxes(gridcolor=BORDER, zeroline=False)
    fig.update_yaxes(gridcolor=BORDER, zeroline=False)
    fig.update_yaxes(title_text='Price (p)', row=1, col=1, title_font_size=10)
    fig.update_yaxes(title_text='RSI',       row=2, col=1, range=[0, 100], title_font_size=10)
    if show_volume:
        vol_label = 'Vol (AIAG.L)' if wtai_volume else 'Volume'
        fig.update_yaxes(title_text=vol_label, row=3, col=1, title_font_size=10)

    arrow    = '+' if chg >= 0 else ''
    c_color  = GREEN if chg >= 0 else RED
    price_el = html.Div([
        html.Span(f'{close:.2f}p', style={'color': TEXT, 'fontSize': '20px', 'fontWeight': '700'}),
        html.Span(f'  {arrow}{chg_pct:.2f}%', style={'color': c_color, 'fontSize': '13px', 'marginLeft': '6px'}),
        html.Br(),
        html.Span(f'RSI {rsi:.1f}  ·  SMA20 {sma20:.1f}  ·  SMA50 {sma50:.1f}',
                  style={'color': MUTED, 'fontSize': '10px'}),
    ])
    sig_color = SIG_COLOR[signal]
    badge = html.Span(signal, style={
        'background': sig_color, 'color': '#000' if signal == 'BUY' else '#fff',
        'padding': '3px 12px', 'borderRadius': '20px', 'fontWeight': '700', 'fontSize': '11px',
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


# ── Macro panel callback ──────────────────────────────────────────────────────
@app.callback(
    Output('macro-alert-panel', 'children'),
    Input('refresh', 'n_intervals'),
)
def update_macro_panel(_):
    return build_macro_panel(fetch_macro_indicators())


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

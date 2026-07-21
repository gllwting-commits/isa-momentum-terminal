import json
import os
import socket
from datetime import datetime, timedelta, time as dt_time
import pytz
from flask import redirect, request, session

import dash
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from dash import ALL, Input, Output, State, dcc, html
from plotly.subplots import make_subplots

# ── Config ────────────────────────────────────────────────────────────────────
ETFS = ['SEMG', 'SEMI', 'VDPG', 'WTAI', 'SGLS', 'FLXK']
TICKERS = {e: f'{e}.L' for e in ETFS}
ETF_NAMES = {
    'SEMG': 'Amundi MSCI Semiconductors ESG Screened UCITS ETF',
    'SEMI': 'iShares MSCI Global Semiconductors UCITS ETF',
    'VDPG': 'Vanguard FTSE Dev Asia Pac ex-JP',
    'WTAI': 'WisdomTree AI',
    'SGLS': 'Invesco Physical Gold ETC (GBP Hedged)',
    'FLXK': 'Franklin FTSE Korea',
}

WATCHLIST = ['AIAI', 'ISPY', 'INRG', 'NUKZ', 'NATO', 'ROBO', 'RBTX', 'EMQQ', 'NDIA', 'HEAL']
WATCHLIST_TICKERS = {
    'AIAI': 'AIAI.L', 'ISPY': 'ISPY.L', 'INRG': 'INRG.L', 'NUKZ': 'NUKZ.L',
    'NATO': 'NATO.L', 'ROBO': 'ROBO.L', 'RBTX': 'RBTX.L', 'EMQQ': 'EMQQ.L',
    'NDIA': 'NDIA.L', 'HEAL': 'HEAL.L',
}
WATCHLIST_NAMES = {
    'AIAI': 'AI / Technology',    'ISPY': 'Cybersecurity',
    'INRG': 'Clean Energy',       'NUKZ': 'Nuclear',
    'NATO': 'Defence',            'ROBO': 'Robotics',
    'RBTX': 'Robotics Alt',       'EMQQ': 'Emerging Markets',
    'NDIA': 'India',              'HEAL': 'Healthcare',
}
VOLUME_ETFS    = ['VDPG', 'SEMG', 'SEMI', 'FLXK']
WTAI_VOL_PROXY = 'AIAG.L'
ETF_WEIGHTS    = {
    'SEMG': 51.39, 'WTAI': 15.02, 'VDPG': 11.41,
    'SGLS': 10.80, 'FLXK':  5.28, 'SEMI': 0.0,
}
# RS ratio pairs: etf → (benchmark_ticker, fx)
# fx='div': bench is USD, ETF is GBP → bench_gbp = bench_usd / GBPUSD
# fx='mul': bench is GBP, ETF is USD → bench_usd = bench_gbp * GBPUSD
RS_BENCHMARKS = {
    'SEMG': ('SOXX',   'div'),
    'SEMI': ('SOXX',   'div'),
    'WTAI': ('EQQQ.L', 'mul'),
    'SGLS': ('IGLN.L', 'div'),
    'VDPG': ('VAPX.L', None),
    'FLXK': ('EWY',    None),
}
# RS-TILT allocation pool (Feature B): 5 holdings ex-SGLS + 10 radar, 15 names total.
RS_TILT_POOL = ['SEMG', 'SEMI', 'VDPG', 'WTAI', 'FLXK'] + WATCHLIST
RS_TILT_TOP_WEIGHTS = [0.60, 0.30, 0.10]
TIMEFRAMES = {'1W': 7, '1M': 30, '3M': 90, '6M': 180, '1Y': 365}
TF_BARS       = {'1W': 5, '1M': 21, '3M': 63, '6M': 126, '1Y': 252}
SNAP_TF_BARS  = {'1d': 1, '1w': 5, '1m': 21, '3m': 63, '6m': 126, '1y': 252}
CHART_TICKERS_ALL = ETFS + ['SPX', 'NDQ']
_INDICATOR_DAYS = 365
ISA_ALLOWANCE  = 20_000
MONTHLY_INVEST = 1_667
ANNUAL_RETURN  = 0.12
PROJ_YEARS     = 20

# ── Palette ───────────────────────────────────────────────────────────────────
SLATE_THEME = {
    'bg':       '#0f1117',
    'surface':  '#161b27',
    'card':     '#1c2333',
    'border':   '#253047',
    'border_l': '#2d3a54',
    'accent':   '#f59e0b',
    'green':    '#10b981',
    'red':      '#ef4444',
    'amber':    '#f59e0b',
    'muted':    '#8b9ab0',
    'dim':      '#3d4f68',
    'text':     '#dde5f0',
}

THEMES = {
    'Slate':    {'bg': '#0f1117', 'surface': '#161b27', 'card': '#1c2333', 'border': '#253047',
                 'border_l': '#2d3a54', 'accent': '#f59e0b', 'green': '#10b981', 'red': '#ef4444',
                 'amber': '#f59e0b', 'muted': '#8b9ab0', 'dim': '#3d4f68', 'text': '#dde5f0',
                 'header_border': '#f59e0b', 'border_radius': '10px'},
    'Dusk':     {'bg': '#1a0a2e', 'surface': '#2d1b69', 'card': '#1e1035', 'border': '#4c2885',
                 'border_l': '#6b21a8', 'accent': '#a855f7', 'green': '#10b981', 'red': '#ef4444',
                 'amber': '#f59e0b', 'muted': '#9ca3af', 'dim': '#6b21a8', 'text': '#e9d5ff',
                 'header_border': '#a855f7', 'border_radius': '10px'},
    'Carbon':   {'bg': '#0d0d0d', 'surface': '#171717', 'card': '#1c1c1c', 'border': '#2d2d2d',
                 'border_l': '#404040', 'accent': '#3b82f6', 'green': '#22c55e', 'red': '#ef4444',
                 'amber': '#f59e0b', 'muted': '#737373', 'dim': '#404040', 'text': '#e5e5e5',
                 'header_border': '#3b82f6', 'border_radius': '8px'},
    'Midnight': {'bg': '#0a0f1e', 'surface': '#0f1729', 'card': '#141f35', 'border': '#1e2d4a',
                 'border_l': '#2d4a6f', 'accent': '#60a5fa', 'green': '#34d399', 'red': '#f87171',
                 'amber': '#fbbf24', 'muted': '#64748b', 'dim': '#1e3a5f', 'text': '#e2e8f0',
                 'header_border': '#60a5fa', 'border_radius': '12px'},
    'Terminal': {'bg': '#000000', 'surface': '#001100', 'card': '#001a00', 'border': '#003300',
                 'border_l': '#004400', 'accent': '#00ff41', 'green': '#00ff41', 'red': '#ff4444',
                 'amber': '#ffaa00', 'muted': '#00aa20', 'dim': '#003300', 'text': '#00ff41',
                 'header_border': '#00ff41', 'border_radius': '4px'},
    'Alpine':   {'bg': '#1e2733', 'surface': '#252f3d', 'card': '#2c3848', 'border': '#3d4f68',
                 'border_l': '#4a6080', 'accent': '#38bdf8', 'green': '#34d399', 'red': '#f87171',
                 'amber': '#fbbf24', 'muted': '#94a3b8', 'dim': '#475569', 'text': '#f1f5f9',
                 'header_border': '#38bdf8', 'border_radius': '10px'},
    'Parchment':{'bg': '#f5f0e8', 'surface': '#faf7f0', 'card': '#ffffff', 'border': '#d4c5a9',
                 'border_l': '#b5a48a', 'accent': '#b45309', 'green': '#15803d', 'red': '#dc2626',
                 'amber': '#d97706', 'muted': '#78716c', 'dim': '#a8a29e', 'text': '#292524',
                 'header_border': '#b45309', 'border_radius': '10px'},
}

BG       = SLATE_THEME['bg']
SURFACE  = SLATE_THEME['surface']
CARD     = SLATE_THEME['card']
BORDER   = SLATE_THEME['border']
BORDER_L = SLATE_THEME['border_l']
TEXT     = SLATE_THEME['text']
MUTED    = SLATE_THEME['muted']
ACCENT   = SLATE_THEME['accent']
GREEN    = SLATE_THEME['green']
RED      = SLATE_THEME['red']
AMBER    = SLATE_THEME['amber']
YELLOW   = SLATE_THEME['amber']
ORANGE   = '#f97316'
DIM      = SLATE_THEME['dim']

CHART_COLORS = {
    'SEMG': '#22d3ee', 'SEMI': '#6366f1', 'VDPG': '#84cc16',
    'WTAI': '#facc15', 'SGLS': '#f59e0b', 'FLXK': '#e879f9',
    'SPX':  '#94a3b8', 'NDQ':  '#f97316',
}
CHART_DASH = {
    'SEMI': '#6366f1',
    'NDQ':  '#f97316',
    'WTAI': '#facc15',
}

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
            return 'rgba(16,185,129,0.10)'
        if conviction == 'MED':
            return 'rgba(16,185,129,0.06)'
        return 'rgba(16,185,129,0.03)'
    if rec == 'SELL':
        if conviction == 'HIGH':
            return 'rgba(239,68,68,0.12)'
        return 'rgba(239,68,68,0.05)'
    if rec == 'HOLD' and conviction == 'MED':
        return 'rgba(245,158,11,0.06)'
    return 'transparent'

TAB_STYLE = {
    'background': BG, 'color': MUTED, 'border': 'none',
    'borderBottom': '2px solid transparent', 'padding': '10px 22px',
    'fontFamily': 'monospace', 'fontSize': '13px', 'fontWeight': '600', 'cursor': 'pointer',
}
TAB_SELECTED = {**TAB_STYLE, 'color': TEXT, 'borderBottom': f'2px solid {ACCENT}', 'background': CARD}

# ── Signal history (in-process; resets on server restart) ─────────────────────
_signal_history: dict = {}


def _format_age(changed_at: datetime) -> str:
    days = (datetime.now() - changed_at).days
    if days < 1:
        return 'today'
    if days < 7:
        return f'{days}d ago'
    if days < 14:
        return '1w ago'
    if days < 28:
        return '2w ago'
    if days < 60:
        return '1m ago'
    if days < 90:
        return '2m ago'
    return '3m+ ago'


def _update_signal_history(etf: str, conviction: str, action: str) -> tuple[str, str]:
    now   = datetime.now()
    entry = _signal_history.get(etf)
    if entry is None:
        _signal_history[etf] = {
            'conviction': conviction, 'conviction_at': now,
            'action': action,         'action_at': now,
        }
        return 'today', 'today'
    if entry['conviction'] != conviction:
        entry['conviction']    = conviction
        entry['conviction_at'] = now
    if entry['action'] != action:
        entry['action']    = action
        entry['action_at'] = now
    return _format_age(entry['conviction_at']), _format_age(entry['action_at'])


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
_LONDON_TZ    = pytz.timezone('Europe/London')
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
    close_s    = df['Close'].dropna()
    if close_s.empty:
        return None
    close_eod  = float(close_s.iloc[-1])
    prev_eod   = float(close_s.iloc[-2]) if len(close_s) > 1 else close_eod
    sma20      = float(s20_s.iloc[-1]) if not s20_s.empty else close_eod
    sma50      = float(s50_s.iloc[-1]) if not s50_s.empty else close_eod
    rsi        = float(rsi_s.iloc[-1])  if not rsi_s.empty  else 50.0
    rsi_change = float(rsi_s.iloc[-1] - rsi_s.iloc[-11]) if len(rsi_s) >= 11 else None
    high_52w   = float(df['High'].max())  # intraday high = standard 52W high definition
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
    """Live price + day% every 60s during 08:00–16:35 London. Outside hours, returns EOD values from daily cache."""
    prev = daily['prev_eod']

    if not _is_market_open():
        try:
            fi      = yf.Ticker(ticker).fast_info
            div     = 100 if fi.currency == 'GBp' else 1
            close   = float(fi.last_price) / div
            rmp     = fi.regular_market_previous_close
            ref     = float(rmp) / div if (rmp and rmp > 0) else daily['close_eod']
            chg_pct = (close / ref - 1) * 100 if ref else 0.0
            return {'close': close, 'chg_pct': chg_pct, 'vol_ratio': None,
                    'is_intraday': False, 'vol_partial': False}
        except Exception:
            pass
        close   = daily['close_eod']
        chg_pct = (close / prev - 1) * 100 if prev else 0.0
        return {'close': close, 'chg_pct': chg_pct, 'vol_ratio': None,
                'is_intraday': False, 'vol_partial': False, 'is_d1': True}

    london_now  = datetime.now(_LONDON_TZ)
    vol_partial = london_now.time() < dt_time(14, 0)
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
        return {'close': close, 'chg_pct': chg_pct, 'vol_ratio': vol_ratio,
                'is_intraday': True, 'vol_partial': vol_partial}
    except Exception:
        close   = daily['close_eod']
        chg_pct = (close / prev - 1) * 100 if prev else 0.0
        return {'close': close, 'chg_pct': chg_pct, 'vol_ratio': None,
                'is_intraday': False, 'vol_partial': False}


_bench_cache: dict = {}


def fetch_benchmark_price(yf_ticker: str) -> 'pd.Series | None':
    """Close series for SPX/NDQ, cached per calendar day."""
    today  = datetime.today().date()
    cached = _bench_cache.get(yf_ticker)
    if cached and cached['date'] == today:
        return cached['series']
    try:
        df = yf.download(yf_ticker, period='1y', interval='1d', progress=False, auto_adjust=True)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        series = df['Close'].dropna()
        _bench_cache[yf_ticker] = {'date': today, 'series': series}
        return series
    except Exception as e:
        print(f'[WARN] fetch_benchmark_price({yf_ticker}): {e}')
        return None


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


def fetch_rs_persist(etf: str) -> tuple[str, int] | None:
    """Return (direction, count) for consecutive days RS ratio moved in same direction."""
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
    rs_vals = (window['etf'] / window['bench']).values
    diffs   = [rs_vals[i] - rs_vals[i - 1] for i in range(1, len(rs_vals))]
    if not diffs:
        return None
    rs_persist_dir = 'pos' if diffs[-1] >= 0 else 'neg'
    rs_persist_n   = 0
    for d in reversed(diffs):
        if (d >= 0) == (diffs[-1] >= 0):
            rs_persist_n += 1
        else:
            break
    return (rs_persist_dir, rs_persist_n)


def fetch_rs_flips(etf: str) -> int | None:
    """Return number of RS direction flips in the 30-day window using 3-day smoothed ratio. None if series < 5 days."""
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
    if len(window) < 5:
        return None
    rs_smoothed    = (window['etf'] / window['bench']).rolling(3).mean().dropna()
    if len(rs_smoothed) < 2:
        return None
    rs_vals        = rs_smoothed.values
    diffs          = [rs_vals[i] - rs_vals[i - 1] for i in range(1, len(rs_vals))]
    rs_flips_count = sum(
        1 for i in range(1, len(diffs)) if (diffs[i] >= 0) != (diffs[i - 1] >= 0)
    )
    return rs_flips_count


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
        'vol_partial': intra.get('vol_partial', False),
    }


_macro_cache: dict = {}
_tnx_1y_cache: dict = {}
_sox_1y_cache: dict = {}


def _get_tnx_1y() -> 'pd.Series | None':
    """^TNX 1Y daily closes for beta regression. Cached 24h."""
    now    = datetime.now()
    cached = _tnx_1y_cache.get('data')
    if cached and (now - cached['ts']).total_seconds() < 86400:
        return cached['series']
    try:
        df = yf.download('^TNX', period='1y', interval='1d', progress=False, auto_adjust=True)
        if df.empty or 'Close' not in df.columns:
            return None
        s       = df['Close'].dropna()
        s.index = pd.to_datetime(s.index).normalize()
        _tnx_1y_cache['data'] = {'ts': now, 'series': s}
        return s
    except Exception:
        return None


def _get_sox_1y() -> 'dict | None':
    """^SOX 1Y daily closes for 200d SMA breach check. ^SOX primary, SOXX fallback. Cached 24h."""
    now    = datetime.now()
    cached = _sox_1y_cache.get('data')
    if cached and (now - cached['ts']).total_seconds() < 86400:
        return cached['result']

    def _fetch_sox_1y(ticker):
        try:
            df = yf.download(ticker, period='1y', interval='1d', progress=False, auto_adjust=True)
            if df.empty:
                return None
            return df
        except Exception:
            return None

    try:
        df = _fetch_sox_1y('^SOX')
        if df is None:
            df = _fetch_sox_1y('SOXX')
        if df is None or 'Close' not in df.columns:
            return None
        sox_ma_close = df['Close'].squeeze().dropna()
        if len(sox_ma_close) < 200:
            return None
        sox_ma_last    = float(sox_ma_close.iloc[-1])
        sox_ma_200     = float(sox_ma_close.rolling(200).mean().iloc[-1])
        sox_ma_breach  = sox_ma_last < sox_ma_200
        result = {'sox_ma_last': sox_ma_last, 'sox_ma_200': sox_ma_200, 'sox_ma_breach': sox_ma_breach}
        _sox_1y_cache['data'] = {'ts': now, 'result': result}
        return result
    except Exception:
        return None


def fetch_rate_beta(etf: str) -> 'float | None':
    """1Y daily beta of ETF returns vs ^TNX moves. None if < 20 aligned rows."""
    try:
        tnx_raw = _get_tnx_1y()
        if tnx_raw is None or (hasattr(tnx_raw, 'empty') and tnx_raw.empty):
            return None
        df = _get_daily_df(etf)
        if df is None or df.empty:
            return None
        tnx_s       = tnx_raw.squeeze().dropna()
        etf_s       = df['Close'].squeeze().dropna()
        tnx_s.index = pd.to_datetime(tnx_s.index).normalize()
        etf_s.index = pd.to_datetime(etf_s.index).normalize()
        merged = pd.merge(
            tnx_s.rename('tnx'), etf_s.rename('etf'),
            left_index=True, right_index=True, how='inner',
        )
        if len(merged) < 20:
            return None
        aligned = pd.concat([
            merged['tnx'].pct_change(),
            merged['etf'].pct_change(),
        ], axis=1).dropna()
        if len(aligned) < 20:
            return None
        slope = np.polyfit(aligned['tnx'].values, aligned['etf'].values, 1)[0]
        return round(float(slope), 2)
    except Exception:
        return None


def fetch_radar_ticker(ticker_str: str) -> 'dict | None':
    """Fetch radar signal data for a single watchlist ticker. Returns None on failure."""
    try:
        df = _get_daily_df(ticker_str)
        if df is None or df.empty:
            return None

        # RSI crossover: currently above 60, was below 60 within prior 5 bars
        rsi_s = df['RSI'].dropna()
        if len(rsi_s) < 6:
            return None
        rsi_now   = float(rsi_s.iloc[-1])
        rsi_cross = rsi_now > 60 and float(rsi_s.iloc[-6:-1].min()) < 60

        # 52W drawdown — use High.max() per architectural rule
        high_52w  = float(df['High'].max())
        close_now = float(df['Close'].dropna().iloc[-1])
        drawdown  = (close_now - high_52w) / high_52w * 100

        # RS vs SWDA.L — 30d pct change of ratio
        swda_df = _get_daily_df('SWDA.L')
        rs_30d  = None
        if swda_df is not None and not swda_df.empty:
            etf_close        = df['Close'].dropna().squeeze()
            swda_close       = swda_df['Close'].dropna().squeeze()
            etf_close.index  = pd.to_datetime(etf_close.index).normalize()
            swda_close.index = pd.to_datetime(swda_close.index).normalize()
            merged = pd.merge(
                etf_close.rename('etf'), swda_close.rename('swda'),
                left_index=True, right_index=True, how='inner',
            )
            if len(merged) >= 32:
                ratio  = merged['etf'] / merged['swda']
                rs_30d = float((ratio.iloc[-1] / ratio.iloc[-31] - 1) * 100)

        signal = (
            rsi_cross and
            rs_30d is not None and rs_30d > 1.5 and
            drawdown > -15.0
        )
        return {
            'rsi': rsi_now, 'rsi_cross': rsi_cross,
            'drawdown': drawdown, 'rs_30d': rs_30d,
            'signal': signal,
        }
    except Exception:
        return None


def rs_vs_swda(ticker: str, lookback: int = 31) -> float | None:
    """30d RS vs SWDA.L (iShares MSCI World), fixed trading-day offset — radar's
    convention, standardised here for use across all 15 RS-TILT names (5 holdings
    ex-SGLS + 10 radar). `ticker` is the full yfinance string (e.g. 'SEMG.L',
    'AIAI.L'), not a short name. Returns None on any missing/insufficient data.
    """
    try:
        df      = _get_daily_df(ticker)
        swda_df = _get_daily_df('SWDA.L')
        if df is None or df.empty or swda_df is None or swda_df.empty:
            return None
        etf_close        = df['Close'].dropna().squeeze()
        swda_close       = swda_df['Close'].dropna().squeeze()
        etf_close.index  = pd.to_datetime(etf_close.index).normalize()
        swda_close.index = pd.to_datetime(swda_close.index).normalize()
        merged = pd.merge(
            etf_close.rename('etf'), swda_close.rename('swda'),
            left_index=True, right_index=True, how='inner',
        )
        if len(merged) < lookback + 1:
            return None
        ratio = merged['etf'] / merged['swda']
        return float((ratio.iloc[-1] / ratio.iloc[-lookback] - 1) * 100)
    except Exception:
        return None


def allocate_tilt(monthly_gbp: float = 3000.0, last_split: 'dict | None' = None) -> dict:
    """RS-TILT allocation engine (Feature B). Ranks RS_TILT_POOL (15 names) on
    rs_vs_swda and splits monthly_gbp winner-take-most across the top 3 (60/30/10).
    Pure function, no UI. Always deploys — least-bad top 3 still funded in an
    all-negative-RS month. status is one of:
      'ok'          - >=3 valid names, standard 60/30/10 split
      'reduced'     - 1-2 valid names, weights renormalised to sum to 1.0
      'fallback'    - 0 valid names, last_split echoed back unchanged
      'unavailable' - 0 valid names and no last_split to fall back to
    """
    tilt_ticker_map = {**TICKERS, **WATCHLIST_TICKERS}

    tilt_ranked, tilt_excluded = [], []
    for tilt_name in RS_TILT_POOL:
        tilt_rs = rs_vs_swda(tilt_ticker_map[tilt_name])
        if tilt_rs is None:
            tilt_excluded.append(tilt_name)
        else:
            tilt_ranked.append((tilt_name, tilt_rs))
    tilt_ranked.sort(key=lambda p: (-p[1], p[0]))

    tilt_ranked_all = [
        {'ticker': tilt_ticker_map[n], 'name': n, 'rs': rs} for n, rs in tilt_ranked
    ]

    if not tilt_ranked:
        if last_split is not None:
            return {**last_split, 'status': 'fallback'}
        return {
            'status': 'unavailable', 'monthly_gbp': monthly_gbp,
            'allocations': [], 'ranked_all': [], 'excluded': list(RS_TILT_POOL),
        }

    tilt_top    = tilt_ranked[:3]
    tilt_status = 'ok' if len(tilt_top) >= 3 else 'reduced'
    tilt_weights_raw = RS_TILT_TOP_WEIGHTS[:len(tilt_top)]
    tilt_weight_sum  = sum(tilt_weights_raw)
    tilt_weights = [w / tilt_weight_sum for w in tilt_weights_raw]

    tilt_allocations = [
        {
            'ticker': tilt_ticker_map[tilt_name],
            'name': tilt_name,
            'rs': tilt_rs,
            'weight': tilt_weight,
            'gbp': monthly_gbp * tilt_weight,
        }
        for (tilt_name, tilt_rs), tilt_weight in zip(tilt_top, tilt_weights)
    ]

    return {
        'status': tilt_status,
        'monthly_gbp': monthly_gbp,
        'allocations': tilt_allocations,
        'ranked_all': tilt_ranked_all,
        'excluded': tilt_excluded,
    }


def fetch_macro_regime() -> dict:
    """Fetch US10Y (^TNX/TLT fallback), VIX, DXY (UUP) and return composite risk regime. Cached 60 minutes."""
    now = datetime.now()
    cached = _macro_cache.get('data')
    if cached and (now - cached['ts']).total_seconds() < 3600:
        return cached['result']

    def _fetch(ticker):
        try:
            df = yf.download(ticker, period='3mo', interval='1d', progress=False, auto_adjust=True)
            if df.empty:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            return df[['Close']].dropna()
        except Exception:
            return None

    def _dir(df, threshold=0.5):
        if df is None or len(df) < 1:
            return None, '→'
        val_now = float(df['Close'].iloc[-1])
        idx_20d = max(0, len(df) - 21)
        val_20d = float(df['Close'].iloc[idx_20d])
        pct_chg = (val_now - val_20d) / abs(val_20d) * 100 if val_20d != 0 else 0
        arrow   = '↑' if pct_chg > threshold else ('↓' if pct_chg < -threshold else '→')
        return val_now, arrow

    # US10Y: ^TNX primary, TLT fallback (price direction inverted)
    macro_tnx_df        = _fetch('^TNX')
    macro_us10y_val, macro_us10y_dir = _dir(macro_tnx_df)
    macro_us10y_delta = None
    if macro_tnx_df is not None and len(macro_tnx_df) >= 11:
        try:
            _tnx_close        = macro_tnx_df['Close']
            _raw_delta        = float(_tnx_close.iloc[-1]) - float(_tnx_close.iloc[-11])
            macro_us10y_delta = round(_raw_delta * 100)
        except Exception:
            pass
    if macro_us10y_val is None:
        macro_tlt_df = _fetch('TLT')
        _, macro_tlt_dir = _dir(macro_tlt_df)
        macro_us10y_dir  = {'↑': '↓', '↓': '↑', '→': '→'}.get(macro_tlt_dir, '→')
        macro_us10y_scored = macro_tlt_df is not None and len(macro_tlt_df) >= 2
    else:
        macro_us10y_scored = True

    # VIX
    macro_vix_df             = _fetch('^VIX')
    macro_vix_val, macro_vix_dir = _dir(macro_vix_df)
    macro_vix_scored         = macro_vix_val is not None

    # DXY via UUP (Invesco DB USD Bull ETF — more reliable feed than ^DXY)
    macro_uup_df             = _fetch('UUP')
    macro_dxy_val, macro_dxy_dir = _dir(macro_uup_df)
    macro_dxy_scored         = macro_dxy_val is not None

    # SOX: display only — not scored for regime
    macro_sox_df = _fetch('^SOX')
    if macro_sox_df is None:
        macro_sox_df = _fetch('SOXX')
    macro_sox_val, macro_sox_dir = _dir(macro_sox_df)

    # SOX 200d SMA breach: display only — not scored for regime
    sox_ma_data = _get_sox_1y()
    macro_sox_ma_breach = sox_ma_data['sox_ma_breach'] if sox_ma_data else None

    # Score only inputs that returned data; partial if < 3
    macro_inputs_scored = 0
    macro_score         = 0

    if macro_us10y_scored:
        macro_inputs_scored += 1
        macro_score += 1 if macro_us10y_dir == '↓' else -1

    if macro_vix_scored:
        macro_inputs_scored += 1
        macro_score += 1 if macro_vix_val < 20 else -1

    if macro_dxy_scored:
        macro_inputs_scored += 1
        macro_score += 1 if macro_dxy_dir == '↓' else -1

    if macro_inputs_scored < 3:
        # Keep last known regime — a fetch failure must not change the label
        prior        = _macro_cache.get('data', {}).get('result', {})
        macro_regime = prior.get('regime', 'PARTIAL')
    elif macro_score >= 2:
        macro_regime = 'RISK ON' if macro_score == 3 else 'LEANING ON'
    else:
        macro_regime = 'RISK OFF' if macro_score <= -2 else 'CAUTION'

    macro_result = {
        'regime':      macro_regime,
        'us10y':       macro_us10y_val,
        'us10y_dir':   macro_us10y_dir,
        'vix':         macro_vix_val,
        'vix_dir':     macro_vix_dir,
        'dxy':         macro_dxy_val,
        'dxy_dir':     macro_dxy_dir,
        'sox':         macro_sox_val,
        'sox_dir':     macro_sox_dir,
        'us10y_delta': macro_us10y_delta,
        'sox_ma_breach': macro_sox_ma_breach,
    }
    _macro_cache['data'] = {'ts': now, 'result': macro_result}
    return macro_result


def build_macro_strip(macro_data: dict) -> html.Div:
    macro_regime      = macro_data.get('regime')
    macro_us10y       = macro_data.get('us10y')
    macro_us10y_dir   = macro_data.get('us10y_dir', '→')
    macro_vix         = macro_data.get('vix')
    macro_vix_dir     = macro_data.get('vix_dir', '→')
    macro_dxy         = macro_data.get('dxy')
    macro_dxy_dir     = macro_data.get('dxy_dir', '→')
    macro_sox         = macro_data.get('sox')
    macro_sox_dir     = macro_data.get('sox_dir', '→')
    macro_sox_ma_breach = macro_data.get('sox_ma_breach')
    macro_us10y_delta = macro_data.get('us10y_delta')

    if macro_us10y_delta is None:
        _us10y_delta_str   = '/ —'
        _us10y_delta_color = MUTED
    elif macro_us10y_delta == 0:
        _us10y_delta_str   = '/ ±0pp'
        _us10y_delta_color = MUTED
    elif macro_us10y_delta > 0:
        _us10y_delta_str   = f'/ +{macro_us10y_delta}pp'
        _us10y_delta_color = RED
    else:
        _us10y_delta_str   = f'/ {macro_us10y_delta}pp'
        _us10y_delta_color = GREEN

    if macro_regime is None:
        return html.Div('Macro data unavailable',
                        style={'color': MUTED, 'fontSize': '12px',
                               'padding': '8px 20px'})

    if macro_regime == 'PARTIAL':
        macro_badge_color = MUTED
    elif macro_regime in ('RISK ON', 'LEANING ON'):
        macro_badge_color = GREEN
    elif macro_regime == 'CAUTION':
        macro_badge_color = YELLOW
    else:
        macro_badge_color = RED

    def macro_val_span(label, val, fmt, arrow):
        if val is not None:
            val_str   = fmt.format(val) + f' {arrow}'
            val_style = {'color': TEXT, 'fontWeight': '600'}
        else:
            val_str   = 'N/A'
            val_style = {'color': MUTED, 'fontWeight': '400'}
        return html.Span(
            [html.Span(label, style={'color': MUTED}),
             html.Span(f' {val_str}', style=val_style)],
            style={'marginRight': '10px', 'whiteSpace': 'nowrap'},
        )

    return html.Div([
        html.Div([
            html.Span(
                'Macro data partial' if macro_regime == 'PARTIAL' else macro_regime,
                style={
                    'background': 'transparent' if macro_regime == 'PARTIAL' else macro_badge_color,
                    'color': MUTED if macro_regime == 'PARTIAL' else BG,
                    'border': f'1px solid {MUTED}' if macro_regime == 'PARTIAL' else 'none',
                    'padding': '4px 16px', 'borderRadius': '20px',
                    'fontWeight': '800', 'fontSize': '15px',
                    'marginRight': '16px', 'letterSpacing': '0.6px',
                    'whiteSpace': 'nowrap',
                }),
            html.Span(
                [html.Span('US10Y:', style={'color': MUTED}),
                 html.Span(
                     f' {macro_us10y:.2f}% {macro_us10y_dir}' if macro_us10y is not None else ' N/A',
                     style={'color': TEXT if macro_us10y is not None else MUTED,
                            'fontWeight': '600' if macro_us10y is not None else '400'},
                 ),
                 html.Span(f' {_us10y_delta_str}',
                           style={'color': _us10y_delta_color, 'fontWeight': '600'})],
                style={'marginRight': '10px', 'whiteSpace': 'nowrap'},
            ),
            html.Span('·', style={'color': MUTED, 'marginRight': '10px'}),
            macro_val_span('VIX:', macro_vix, '{:.1f}', macro_vix_dir),
            html.Span('·', style={'color': MUTED, 'marginRight': '10px'}),
            macro_val_span('DXY:', macro_dxy, '{:.1f}', macro_dxy_dir),
            html.Span('·', style={'color': MUTED, 'marginRight': '10px'}),
            macro_val_span('SOX:', macro_sox, '{:.0f}', macro_sox_dir),
            (html.Span('SOX < 200d', style={
                'background': RED, 'color': BG, 'fontWeight': '800',
                'fontSize': '9px', 'padding': '2px 6px', 'borderRadius': '10px',
                'marginLeft': '-6px', 'marginRight': '10px', 'letterSpacing': '0.4px',
                'whiteSpace': 'nowrap',
            }) if macro_sox_ma_breach else None),
        ], style={
            'display': 'flex', 'alignItems': 'center', 'flexWrap': 'wrap',
            'gap': '4px', 'fontSize': '12px',
        }),
        html.Div('Rates & risk regime · refreshes every 60s',
                 style={'color': MUTED, 'fontSize': '10px', 'marginTop': '4px'}),
    ], style={'padding': '8px 20px', 'borderBottom': f'1px solid {BORDER}'})


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


def _view_btn_style(this_val: str, current_val: str) -> dict:
    active = this_val == current_val
    return {
        'background': 'transparent',
        'color': TEXT if active else MUTED,
        'border': 'none',
        'borderBottom': f'2px solid {ACCENT}' if active else '2px solid transparent',
        'padding': '7px 16px',
        'cursor': 'pointer',
        'fontFamily': 'monospace',
        'fontSize': '12px',
        'fontWeight': '600',
    }


def _chart_ticker_btn_style(ticker: str, active: bool, greyed: bool = False) -> dict:
    if greyed:
        return {
            'background': 'transparent', 'color': DIM, 'border': f'1px solid {DIM}',
            'borderRadius': '20px', 'padding': '4px 12px', 'cursor': 'not-allowed',
            'fontFamily': 'monospace', 'fontSize': '12px', 'fontWeight': '700', 'opacity': '0.4',
        }
    color = CHART_COLORS.get(ticker, TEXT)
    return {
        'background': color if active else 'transparent',
        'color': '#0f1117' if active else color,
        'border': f'1px solid {color}',
        'borderRadius': '20px', 'padding': '4px 12px', 'cursor': 'pointer',
        'fontFamily': 'monospace', 'fontSize': '12px', 'fontWeight': '700',
    }


def _chart_mode_btn_style(this_mode: str, current_mode: str) -> dict:
    active = this_mode == current_mode
    return {
        'background': ACCENT if active else 'transparent',
        'color': '#000' if active else MUTED,
        'border': f'1px solid {ACCENT if active else BORDER}',
        'borderRadius': '4px', 'padding': '4px 12px', 'cursor': 'pointer',
        'fontFamily': 'monospace', 'fontSize': '12px', 'fontWeight': '600',
    }


def _sort_btn_style(btn_mode: str, current_mode: str) -> dict:
    active = btn_mode == current_mode
    return {
        'background': ACCENT if active else 'transparent',
        'color': '#000' if active else MUTED,
        'border': f'1px solid {ACCENT if active else BORDER}',
        'borderRadius': '4px', 'padding': '3px 8px', 'cursor': 'pointer',
        'fontFamily': 'monospace', 'fontSize': '11px', 'fontWeight': '600',
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
                             fill='tonexty', fillcolor='rgba(245,158,11,0.09)'))
    fig.add_trace(go.Scatter(x=years, y=[v/1e6 for v in aggr], name='Optimistic 15%',
                             line=dict(color=GREEN, dash='dash', width=1.5),
                             fill='tonexty', fillcolor='rgba(16,185,129,0.07)'))
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


# ── Charts tab snapshot helpers ───────────────────────────────────────────────
_LANE_H     = 14   # px between dot lane centres
_DOT_R      = 5    # dot radius px
_LABEL_H    = 22   # px per staircase step
_LABEL_PROX = 8    # % proximity threshold for label stagger


def _build_stat_track(
    stat_label: str,
    entries: list,            # [{'etf','val','tcol','vcol','dstr'}, …]
    min_val: float,
    max_val: float,
    track_zones: list,        # [(start_pct, end_pct, color), …]
    marker_lines: list = None,       # [(value, color, opacity, width_px), …]
    zone_label_defs: list = None,    # [(start_pct, end_pct, text, color), …]
    axis_labels: tuple = None,       # (left_str, center_str, right_str)
) -> html.Div:
    n = len(entries)
    if n == 0:
        return html.Div()

    sorted_e = sorted(entries, key=lambda x: x['val'])
    for i, e in enumerate(sorted_e):
        e['lane_idx'] = i

    dot_area_h   = n * _LANE_H + 8
    ZONE_LBL_H   = 18 if zone_label_defs else 0
    AXIS_H       = 14 if axis_labels else 0
    dot_area_y   = ZONE_LBL_H
    track_y_in_dot = int(np.ceil(n / 2)) * _LANE_H
    track_abs_y  = dot_area_y + track_y_in_dot - 2
    axis_y       = dot_area_y + dot_area_h
    label_area_y = axis_y + AXIS_H

    for e in sorted_e:
        e['dot_y'] = dot_area_y + (e['lane_idx'] + 0.5) * _LANE_H + 4

    def val_to_pct(v: float) -> float:
        if max_val == min_val:
            return 50.0
        return max(0.0, min(100.0, (v - min_val) / (max_val - min_val) * 100.0))

    for e in sorted_e:
        e['pct'] = val_to_pct(e['val'])

    placed: list = []
    for e in sorted_e:
        lvl = 0
        while any(abs(x['pct'] - e['pct']) < _LABEL_PROX and x['level'] == lvl
                  for x in placed):
            lvl += 1
        e['level'] = lvl
        placed.append(e)

    max_level    = max(e['level'] for e in sorted_e)
    label_area_h = (max_level + 1) * _LABEL_H + 10
    total_h      = label_area_y + label_area_h

    kids: list = []

    # Zone labels above track
    if zone_label_defs:
        for sp, ep, text, color in zone_label_defs:
            mid = (sp + ep) / 2
            kids.append(html.Span(text, style={
                'position': 'absolute', 'zIndex': '1',
                'top': '0px',
                'left': f'{mid:.2f}%', 'transform': 'translateX(-50%)',
                'color': color, 'fontSize': '9px', 'fontFamily': 'monospace',
                'whiteSpace': 'nowrap',
            }))

    # Track base (DIM)
    kids.append(html.Div(style={
        'position': 'absolute', 'zIndex': '2',
        'left': '0', 'right': '0',
        'top': f'{track_abs_y}px', 'height': '4px',
        'background': '#e0e7ff', 'borderRadius': '2px',
    }))
    # Coloured zone segments
    for sp, ep, tz_col in track_zones:
        kids.append(html.Div(style={
            'position': 'absolute', 'zIndex': '3',
            'left': f'{sp:.2f}%', 'width': f'{ep - sp:.2f}%',
            'top': f'{track_abs_y}px', 'height': '4px',
            'background': tz_col,
        }))

    # Vertical marker lines (span dot area height)
    if marker_lines:
        for mval, mcol, mopa, mw in marker_lines:
            mpct = val_to_pct(mval)
            kids.append(html.Div(style={
                'position': 'absolute', 'zIndex': '4',
                'left': f'calc({mpct:.2f}% - {mw / 2:.1f}px)',
                'top': f'{dot_area_y}px',
                'width': f'{mw}px', 'height': f'{dot_area_h}px',
                'background': mcol, 'opacity': str(mopa),
            }))

    # Axis labels
    if axis_labels:
        left_l, center_l, right_l = axis_labels
        ay = axis_y + 1
        kids += [
            html.Span(left_l, style={
                'position': 'absolute', 'top': f'{ay}px', 'left': '0',
                'color': '#64748b', 'fontSize': '9px', 'fontFamily': 'monospace',
            }),
            html.Span(center_l, style={
                'position': 'absolute', 'top': f'{ay}px', 'left': '50%',
                'transform': 'translateX(-50%)',
                'color': '#64748b', 'fontSize': '9px', 'fontFamily': 'monospace',
            }),
            html.Span(right_l, style={
                'position': 'absolute', 'top': f'{ay}px', 'right': '0',
                'color': '#64748b', 'fontSize': '9px', 'fontFamily': 'monospace',
            }),
        ]

    # Dots, connectors, label pills
    for e in sorted_e:
        pct   = e['pct']
        dy    = e['dot_y']
        lbl_y = label_area_y + 4 + e['level'] * _LABEL_H

        # Connector line from dot bottom to label pill
        conn_top = dy + _DOT_R + 1
        conn_bot = lbl_y - 4
        conn_h   = conn_bot - conn_top
        if conn_h > 2:
            kids.append(html.Div(style={
                'position': 'absolute', 'zIndex': '5',
                'left': f'calc({pct:.2f}% - 0.5px)',
                'top': f'{conn_top}px',
                'width': '1px', 'height': f'{conn_h}px',
                'background': e['tcol'], 'opacity': '0.35',
            }))
            kids.append(html.Span('▾', style={
                'position': 'absolute', 'zIndex': '5',
                'left': f'calc({pct:.2f}% - 4px)',
                'top': f'{conn_bot - 1}px',
                'color': e['tcol'], 'fontSize': '8px',
                'opacity': '0.5', 'lineHeight': '1',
            }))

        # Dot (title attr gives browser-native hover tooltip)
        kids.append(html.Div(
            title=f'{e["etf"]}: {e["dstr"]}',
            style={
                'position': 'absolute', 'zIndex': '10',
                'left': f'calc({pct:.2f}% - {_DOT_R}px)',
                'top': f'{dy - _DOT_R}px',
                'width': f'{_DOT_R * 2}px', 'height': f'{_DOT_R * 2}px',
                'borderRadius': '50%',
                'background': e['tcol'],
                'border': '2px solid white',
                'boxShadow': '0 1px 4px rgba(0,0,0,0.5)',
                'cursor': 'pointer',
            }
        ))

        # Label pill (always visible, centred on dot x)
        kids.append(html.Div([
            html.Span(e['etf'], style={
                'fontWeight': '700', 'color': '#1e293b',
                'fontSize': '10px', 'marginRight': '3px',
                'fontFamily': 'monospace',
            }),
            html.Span(e['dstr'], style={
                'color': e['vcol'], 'fontSize': '10px',
                'fontFamily': 'monospace', 'fontWeight': '600',
            }),
        ], style={
            'position': 'absolute', 'zIndex': '20',
            'left': f'{pct:.2f}%', 'transform': 'translateX(-50%)',
            'top': f'{lbl_y}px',
            'background': e['tcol'] + '1f',
            'border': f'1px solid {e["tcol"]}70',
            'borderRadius': '10px', 'padding': '2px 7px',
            'whiteSpace': 'nowrap', 'userSelect': 'none',
        }))

    return html.Div([
        html.Div(stat_label, style={
            'color': '#1e293b', 'fontSize': '11px', 'fontWeight': '600',
            'fontFamily': 'monospace', 'marginBottom': '4px',
            'letterSpacing': '0.5px',
        }),
        html.Div(kids, style={
            'position': 'relative', 'width': '100%',
            'height': f'{total_h}px', 'overflow': 'visible',
        }),
    ], style={'marginBottom': '24px'})


def _conv_card(etf: str, data: dict) -> html.Div:
    weight     = ETF_WEIGHTS.get(etf, 0.0)
    conv       = data['conviction']
    rec        = data['rec']
    conv_color = CONVICTION_COLOR[conv]
    rec_color  = REC_COLOR[rec]
    t_color    = CHART_COLORS.get(etf, TEXT)
    rs_trend   = data.get('rs_ratio')
    entry_val  = (f'{data["sma20"]:.2f}' if rec == 'BUY' else
                  'Avoid' if rec == 'SELL' else f'{data["sma50"]:.2f}')
    rs_el = []
    if rs_trend is not None:
        rs_c  = GREEN if rs_trend > 1.5 else RED if rs_trend < -1.5 else AMBER
        rs_el = [html.Div([
            html.Span('RS: ', style={'color': MUTED, 'fontSize': '10px'}),
            html.Span(f'{rs_trend:+.1f}%',
                      style={'color': rs_c, 'fontSize': '10px', 'fontWeight': '600'}),
        ], style={'marginTop': '2px', 'fontFamily': 'monospace'})]
    return html.Div([
        html.Div([
            html.Span('●', style={'color': t_color, 'marginRight': '4px', 'fontSize': '10px'}),
            html.Span(etf, style={'color': TEXT, 'fontWeight': '700', 'fontSize': '13px'}),
            html.Span(f'  {weight:.1f}%', style={'color': MUTED, 'fontSize': '11px'}),
        ], style={'marginBottom': '8px', 'fontFamily': 'monospace'}),
        html.Span(conv, style={
            'background': conv_color + '22', 'color': conv_color,
            'border': f'1px solid {conv_color}',
            'padding': '1px 8px', 'borderRadius': '20px',
            'fontWeight': '700', 'fontSize': '10px',
        }),
        html.Div(get_action_text(rec, conv), style={
            'color': rec_color, 'fontSize': '11px', 'fontWeight': '600',
            'marginTop': '8px', 'borderLeft': f'3px solid {rec_color}',
            'paddingLeft': '6px', 'fontFamily': 'monospace',
        }),
        html.Div([
            html.Span('Entry: ', style={'color': MUTED, 'fontSize': '10px'}),
            html.Span(entry_val, style={'color': TEXT, 'fontSize': '10px', 'fontWeight': '600'}),
        ], style={'marginTop': '6px', 'fontFamily': 'monospace'}),
        html.Div([
            html.Span('SMA: ', style={'color': MUTED, 'fontSize': '10px'}),
            html.Span(f'{data["vs20"]} 20 · {data["vs50"]} 50',
                      style={'color': TEXT, 'fontSize': '10px'}),
        ], style={'marginTop': '2px', 'fontFamily': 'monospace'}),
        *rs_el,
    ], style={
        'background': SURFACE, 'border': f'1px solid {BORDER}',
        'borderRadius': '8px', 'padding': '12px',
        'flex': '1', 'minWidth': '155px', 'maxWidth': '220px',
    })


# ── Signal Summary table ──────────────────────────────────────────────────────
def _make_sparkline(closes: pd.Series, color: str) -> html.Div:
    vals = closes.dropna().tolist()
    if len(vals) < 2:
        return html.Div()
    mn, mx = min(vals), max(vals)
    rng = mx - mn if mx != mn else 1.0
    bars = '▁▂▃▄▅▆▇█'
    spark = ''.join(bars[min(7, int((v - mn) / rng * 7.99))] for v in vals)
    return html.Div(spark, style={
        'color': color, 'fontSize': '8px', 'letterSpacing': '1px',
        'marginTop': '4px', 'lineHeight': '1',
    })



def build_summary_table(rows: list[dict], show_week: bool = False, sort_mode: str = 'daypct') -> html.Table:
    if sort_mode == 'rs':
        rows = sorted(rows, key=lambda r: (r['data']['rs_ratio'] if r.get('data') and r['data'].get('rs_ratio') is not None else -999.0), reverse=True)
    elif sort_mode == 'rsi':
        rows = sorted(rows, key=lambda r: (r['data']['rsi'] if r.get('data') else -999.0), reverse=True)
    elif sort_mode == 'dd':
        rows = sorted(rows, key=lambda r: (r['data']['drawdown'] if r.get('data') and r['data'].get('drawdown') is not None else 0.0))
    elif sort_mode == 'weight':
        rows = sorted(rows, key=lambda r: ETF_WEIGHTS.get(r['etf'], 0.0), reverse=True)
    else:  # daypct
        rows = sorted(rows, key=lambda r: (r['data']['chg_pct'] if r.get('data') else -999.0), reverse=True)
    _mc_regime = _macro_cache.get('data', {}).get('result', {}).get('regime')
    period_label = 'Wk %' if show_week else 'Day %'
    headers = [
        'ETF',
        'PRICE / ' + period_label,
        'VOLUME',
        'CONVICTION',
        'ACTION',
        'ENTRY AT',
        'RSI 14',
        'SMA POSITION',
        '52W DRAWDOWN',
        'RS TREND 30d',
    ]
    thead = html.Thead(html.Tr([html.Th(h, style=TH_STYLE) for h in headers]))

    tbody_rows = []
    for row in rows:
        etf        = row['etf']
        data       = row.get('data')
        conv_age   = row.get('conv_age',   'unknown')
        action_age = row.get('action_age', 'unknown')

        if data is None:
            tr = html.Tr([
                html.Td([
                    html.Div(etf, style={'color': TEXT, 'fontWeight': '700', 'fontSize': '14px'}),
                    html.Div(ETF_NAMES[etf], style={'color': MUTED, 'fontSize': '10px', 'marginTop': '2px'}),
                ], style=TD_STYLE),
                html.Td('No data', colSpan=9, style={**TD_STYLE, 'color': MUTED}),
            ], style={'borderBottom': f'1px solid {BORDER}'})
        else:
            rec        = data['rec']
            conv       = data['conviction']
            chg_pct    = data['week_chg_pct'] if show_week else data['chg_pct']
            day_color  = GREEN if chg_pct > 0 else (RED if chg_pct < 0 else MUTED)
            day_arrow  = '+' if chg_pct > 0 else ('-' if chg_pct < 0 else ' ')
            if rec == 'SELL' and conv == 'HIGH':
                row_bg     = RED + '09'
                row_border = f'3px solid {RED}'
            elif rec == 'SELL' and conv == 'MED':
                row_bg     = AMBER + '07'
                row_border = f'3px solid {AMBER}'
            else:
                row_bg     = 'transparent'
                row_border = '3px solid transparent'
            conv_color = CONVICTION_COLOR[conv]
            rec_color  = REC_COLOR[rec]

            # ETF name cell
            etf_name_children = [
                html.Div(etf, style={'color': TEXT, 'fontWeight': '700', 'fontSize': '14px'}),
                html.Div(ETF_NAMES[etf], style={'color': MUTED, 'fontSize': '10px', 'marginTop': '2px'}),
            ]
            if etf == 'WTAI':
                etf_name_children.append(html.Div(
                    'vol: AIAG.L',
                    style={'color': MUTED, 'fontSize': '10px', 'fontStyle': 'italic', 'marginTop': '2px'},
                ))
            spark_series = _get_daily_df(TICKERS[etf])['Close'].dropna().iloc[-15:]
            spark_color  = GREEN if chg_pct >= 0 else RED
            etf_name_children.append(_make_sparkline(spark_series, spark_color))
            etf_cell = html.Td(etf_name_children, style=TD_STYLE)

            # Volume cell
            vr          = data.get('vol_ratio')
            vol_partial = data.get('vol_partial', False)
            if vr is not None:
                vol_color  = GREEN if vr >= 1.3 else (YELLOW if vr >= 0.8 else MUTED)
                proxy_note = data.get('vol_proxy')
                prefix     = '~' if vol_partial else ''
                tooltip    = 'Partial session - volume will increase through the day.' if vol_partial else None
                _vol_day_pct = data.get('chg_pct')
                if _vol_day_pct is None:
                    vol_dir = ''
                elif _vol_day_pct > 0.1:
                    vol_dir = '🟢 '
                elif _vol_day_pct < -0.1:
                    vol_dir = '🔴 '
                else:
                    vol_dir = ''
                vol_cell = html.Td([
                    html.Span(f'{vol_dir}{prefix}{vr:.1f}x', style={'color': vol_color, 'fontWeight': '700'}),
                    html.Div(
                        'vs 20d avg' + (' (proxy)' if proxy_note else ''),
                        style={'color': MUTED, 'fontSize': '10px'},
                    ),
                ], style=TD_STYLE, title=tooltip)
            else:
                vol_cell = html.Td('-', style={**TD_STYLE, 'color': MUTED, 'fontSize': '12px'})

            # CONVICTION cell: badge on top, grey age stamp below, optional regime modifier
            _regime_modifier = None
            if conv == 'HIGH' and _mc_regime == 'RISK OFF':
                _regime_modifier = 'regime: stress'
            elif conv == 'HIGH' and _mc_regime == 'CAUTION':
                _regime_modifier = 'regime: caution'
            conv_cell = html.Td([
                html.Span(conv, style={
                    'background': conv_color + '22',
                    'color': conv_color,
                    'border': '1px solid ' + conv_color,
                    'padding': '2px 9px',
                    'borderRadius': '20px',
                    'fontWeight': '700',
                    'fontSize': '11px',
                }),
                html.Div(conv_age, style={
                    'color': MUTED,
                    'fontSize': '10px',
                    'marginTop': '4px',
                }),
                *([html.Div(_regime_modifier, style={
                    'color': MUTED,
                    'fontSize': '10px',
                    'marginTop': '2px',
                })] if _regime_modifier else []),
            ], style=TD_STYLE)

            # ACTION cell: instruction text on top, grey age stamp below
            action_cell = html.Td([
                html.Div(get_action_text(rec, conv), style={
                    'color': rec_color,
                    'fontSize': '12px',
                    'fontWeight': '600',
                }),
                html.Div(action_age, style={
                    'color': MUTED,
                    'fontSize': '10px',
                    'marginTop': '4px',
                }),
            ], style=TD_STYLE)

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
            entry_watch_pct50 = data.get('pct50')
            entry_watch_rsi_chg = data.get('rsi_change')
            entry_watch_el = []
            if entry_watch_pct50 is not None and entry_watch_rsi_chg is not None:
                if abs(entry_watch_pct50) <= 3.0 and abs(entry_watch_rsi_chg) < 2.0:
                    entry_watch_el = [html.Div('⊙ ENTRY WATCH', style={
                        'color': GREEN,
                        'fontSize': '10px',
                        'marginTop': '2px',
                        'padding': '1px 6px',
                        'border': f'1px solid {GREEN}',
                        'borderRadius': '10px',
                        'display': 'inline-block',
                    })]
            entry_cell = html.Td([
                html.Div(entry_val, style={'color': entry_color, 'fontWeight': '700', 'fontSize': '13px'}),
                html.Div(entry_sub, style={'color': MUTED, 'fontSize': '10px', 'marginTop': '2px'}),
            ] + entry_watch_el, style=TD_STYLE)

            # RSI 14 cell
            rsi_val       = data['rsi']
            rsi_color     = RED if rsi_val > 70 else (GREEN if rsi_val < 30 else TEXT)
            rsi_bar_color = (RED if rsi_val > 70 else GREEN if rsi_val < 30 else
                             AMBER if rsi_val > 55 else MUTED)
            rsi_chg       = data.get('rsi_change')
            rsi_delta_el  = []
            if rsi_chg is not None:
                chg_sign     = '+' if rsi_chg >= 0 else ''
                chg_color    = GREEN if rsi_chg > 1.5 else (RED if rsi_chg < -1.5 else YELLOW)
                rsi_delta_el = [html.Span(
                    f' {chg_sign}{rsi_chg:.1f}',
                    style={'color': chg_color, 'fontSize': '10px'},
                )]
            rsi_bar  = html.Div(
                html.Div(style={
                    'width': f'{rsi_val / 100 * 42:.0f}px', 'height': '3px',
                    'background': rsi_bar_color, 'borderRadius': '2px',
                }),
                style={'width': '42px', 'height': '3px', 'background': DIM,
                       'borderRadius': '2px', 'marginBottom': '5px'},
            )
            rsi_cell = html.Td([
                rsi_bar,
                html.Div(
                    [html.Span(f'{rsi_val:.1f}', style={'color': rsi_color, 'fontWeight': '600'})]
                    + rsi_delta_el,
                ),
            ], style=TD_STYLE)

            # SMA POSITION cell
            vs20_color  = GREEN if data['vs20'] == 'Above' else RED
            vs50_color  = GREEN if data['vs50'] == 'Above' else RED
            sma_ext_pct = data.get('pct50')  # (close - sma50) / sma50 * 100, pre-computed
            if sma_ext_pct is not None:
                sma_ext_text  = f'{sma_ext_pct:+.1f}% from SMA50'
                sma_ext_color = (GREEN if sma_ext_pct >= 5
                                 else AMBER if sma_ext_pct >= 2
                                 else MUTED if sma_ext_pct >= 0
                                 else RED)
            sma_cell   = html.Td([
                html.Div([
                    html.Span('20: ', style={'color': MUTED, 'fontSize': '10px'}),
                    html.Span(f'{data["sma20"]:.2f}', style={'color': '#ffa657', 'fontSize': '12px'}),
                    html.Span('  ' + data['vs20'], style={'color': vs20_color, 'fontSize': '10px'}),
                ]),
                html.Div([
                    html.Span('50: ', style={'color': MUTED, 'fontSize': '10px'}),
                    html.Span(f'{data["sma50"]:.2f}', style={'color': '#d2a8ff', 'fontSize': '12px'}),
                    html.Span('  ' + data['vs50'], style={'color': vs50_color, 'fontSize': '10px'}),
                ], style={'marginTop': '3px'}),
                *([html.Div(sma_ext_text, style={'color': sma_ext_color, 'fontSize': '10px', 'marginTop': '3px'})]
                  if sma_ext_pct is not None else []),
            ], style=TD_STYLE)

            # 52W drawdown cell
            dd = data.get('drawdown')
            if dd is not None:
                dd_color = GREEN if dd > -5 else (RED if dd < -10 else YELLOW)
                dd_cell  = html.Td(
                    html.Span(f'{dd:.1f}%', style={'color': dd_color, 'fontWeight': '700', 'fontSize': '13px'}),
                    style=TD_STYLE,
                )
            else:
                dd_cell = html.Td('-', style={**TD_STYLE, 'color': MUTED, 'fontSize': '12px'})

            # RS trend cell
            rs_trend    = data.get('rs_ratio')
            bench_label = RS_BENCHMARKS.get(etf, (None,))[0]
            if rs_trend is not None:
                rs_sign  = '+' if rs_trend >= 0 else ''
                rs_color = GREEN if rs_trend > 1.5 else (RED if rs_trend < -1.5 else YELLOW)
                rs_label = 'up' if rs_trend > 1.5 else ('dn' if rs_trend < -1.5 else '->')
                rs_persist_data = data.get('rs_persist')
                if rs_persist_data is not None:
                    rs_persist_dir, rs_persist_n = rs_persist_data
                    rs_persist_label = f'{rs_persist_dir} {rs_persist_n}d'
                else:
                    rs_persist_label = '—'
                rs_cell = html.Td([
                    html.Div(rs_label + ' ' + rs_sign + f'{rs_trend:.1f}%',
                             style={'color': rs_color, 'fontWeight': '700', 'fontSize': '13px'}),
                    html.Div('vs ' + str(bench_label),
                             style={'color': MUTED, 'fontSize': '10px', 'marginTop': '2px'}),
                    html.Div(rs_persist_label,
                             style={'color': MUTED, 'fontSize': '10px', 'marginTop': '2px'}),
                    html.Div(
                        children=('—' if data.get('rs_flips') is None
                                  else 'stable' if data['rs_flips'] <= 1
                                  else f'🟡 {data["rs_flips"]} flips' if data['rs_flips'] <= 3
                                  else f'🔴 {data["rs_flips"]} flips'),
                        style={'color': (MUTED if data.get('rs_flips') is None or data['rs_flips'] <= 1
                                         else YELLOW if data['rs_flips'] <= 3 else RED),
                               'fontSize': '10px', 'marginTop': '2px'},
                    ),
                    *([html.Div(f'β {data["rate_beta"]:+.2f}',
                                style={'color': MUTED, 'fontSize': '10px', 'marginTop': '2px'})]
                      if data.get('rate_beta') is not None else []),
                ], style=TD_STYLE)
            else:
                rs_cell = html.Td('-', style={**TD_STYLE, 'color': MUTED, 'fontSize': '12px'})

            tr = html.Tr([
                etf_cell,
                html.Td([
                    html.Span(f'{data["close"]:.2f}', style={'color': TEXT, 'fontWeight': '700'}),
                    html.Br(),
                    html.Span(f'{day_arrow}{abs(chg_pct):.2f}%', style={'color': day_color, 'fontSize': '11px'}),
                ], style=TD_STYLE),
                vol_cell,
                conv_cell,
                action_cell,
                entry_cell,
                rsi_cell,
                sma_cell,
                dd_cell,
                rs_cell,
            ], style={
                'background': row_bg,
                'borderLeft': row_border,
                'transition': 'background 0.15s',
                'borderBottom': '1px solid ' + BORDER,
            })

        tbody_rows.append(tr)

    return html.Table(
        [thead, html.Tbody(tbody_rows)],
        style={'width': '100%', 'borderCollapse': 'collapse', 'fontFamily': 'monospace'},
    )


# ── Summary view (Label/Vals inline ranked display) ───────────────────────────
def build_summary_view(rows: list[dict], show_week: bool = False) -> html.Div:
    LBL = {
        'minWidth': '75px', 'display': 'inline-block', 'color': MUTED,
        'fontSize': '11px', 'flexShrink': '0',
    }
    SEP      = {'borderTop': f'1px solid {BORDER}', 'margin': '6px 0'}
    ROW_BASE = {'fontFamily': 'monospace', 'fontSize': '12px',
                'display': 'flex', 'alignItems': 'baseline', 'padding': '3px 0'}

    def _etf_color(row: dict) -> str:
        if not row['data']:
            return MUTED
        action = get_action_text(row['data']['rec'], row['data']['conviction'])
        if 'Exit' in action or 'reduce' in action:
            return RED
        if 'Watch' in action or 'Monitor' in action:
            return ACCENT
        return TEXT

    def _rsi_color(rsi: float) -> str:
        if rsi > 80 or rsi < 30:
            return RED
        if rsi > 70 or rsi < 50:
            return YELLOW
        return GREEN

    def _make_row(label: str, item_spans: list) -> html.Div:
        parts: list = []
        for i, span in enumerate(item_spans):
            parts.append(span)
            if i < len(item_spans) - 1:
                parts.append(html.Span('  ·  ', style={'color': MUTED}))
        return html.Div([
            html.Span(label, style=LBL),
            html.Span(parts),
        ], style=ROW_BASE)

    period_key = 'week_chg_pct' if show_week else 'chg_pct'

    # ── Ranked rows ───────────────────────────────────────────────────────────
    # 1. Price / Day% — sorted descending by change
    def _price_key(r):
        return r['data'][period_key] if r['data'] else -999.0
    price_spans = []
    for r in sorted(rows, key=_price_key, reverse=True):
        if not r['data']:
            price_spans.append(html.Span([
                html.Span(r['etf'], style={'color': MUTED}),
                html.Span('(—)', style={'color': MUTED}),
            ]))
            continue
        d   = r['data']
        chg = d[period_key]
        cc  = GREEN if chg > 0 else (RED if chg < 0 else MUTED)
        sgn = '+' if chg > 0 else ''
        price_spans.append(html.Span([
            html.Span(r['etf'], style={'color': _etf_color(r)}),
            html.Span(f'(£{d["close"]:.2f} {sgn}{chg:.1f}%)', style={'color': cc}),
        ]))

    # 2. Volume — sorted descending, None treated as 0 → sorted to end
    def _vol_key(r):
        return (r['data']['vol_ratio'] or 0) if r['data'] else 0
    vol_spans = []
    for r in sorted(rows, key=_vol_key, reverse=True):
        if not r['data']:
            vol_spans.append(html.Span([
                html.Span(r['etf'], style={'color': MUTED}),
                html.Span('(—)', style={'color': MUTED}),
            ]))
            continue
        vr = r['data']['vol_ratio']
        if vr is not None:
            vc = GREEN if vr >= 1.3 else (YELLOW if vr >= 0.8 else MUTED)
            vol_spans.append(html.Span([
                html.Span(r['etf'], style={'color': _etf_color(r)}),
                html.Span(f'({vr:.1f}x)', style={'color': vc}),
            ]))
        else:
            vol_spans.append(html.Span([
                html.Span(r['etf'], style={'color': MUTED}),
                html.Span('(—)', style={'color': MUTED}),
            ]))

    # 3. RSI 14 — sorted descending by RSI value
    def _rsi_key(r):
        return r['data']['rsi'] if r['data'] else -999.0
    rsi_spans = []
    for r in sorted(rows, key=_rsi_key, reverse=True):
        if not r['data']:
            rsi_spans.append(html.Span([
                html.Span(r['etf'], style={'color': MUTED}),
                html.Span('(—)', style={'color': MUTED}),
            ]))
            continue
        d      = r['data']
        rv     = d['rsi']
        rc     = _rsi_color(rv)
        rchg   = d.get('rsi_change')
        delta_parts: list = []
        if rchg is not None:
            ds = '+' if rchg >= 0 else ''
            dc = GREEN if rchg > 1.5 else (RED if rchg < -1.5 else YELLOW)
            delta_parts = [html.Span(f' {ds}{rchg:.1f}', style={'color': dc, 'fontSize': '10px'})]
        rsi_spans.append(html.Span([
            html.Span(r['etf'], style={'color': _etf_color(r)}),
            html.Span('(', style={'color': MUTED}),
            html.Span(f'{rv:.1f}', style={'color': rc}),
            *delta_parts,
            html.Span(')', style={'color': MUTED}),
        ]))

    # 4. 52W DD — sorted best (least negative) first
    def _dd_key(r):
        if r['data'] and r['data'].get('drawdown') is not None:
            return r['data']['drawdown']
        return -999.0
    dd_spans = []
    for r in sorted(rows, key=_dd_key, reverse=True):
        if not r['data']:
            dd_spans.append(html.Span([
                html.Span(r['etf'], style={'color': MUTED}),
                html.Span('(—)', style={'color': MUTED}),
            ]))
            continue
        dd = r['data'].get('drawdown')
        if dd is not None:
            dc = GREEN if dd > -5 else (RED if dd < -10 else YELLOW)
            dd_spans.append(html.Span([
                html.Span(r['etf'], style={'color': _etf_color(r)}),
                html.Span(f'({dd:.1f}%)', style={'color': dc}),
            ]))
        else:
            dd_spans.append(html.Span([
                html.Span(r['etf'], style={'color': MUTED}),
                html.Span('(—)', style={'color': MUTED}),
            ]))

    # 5. RS Trend — sorted descending, benchmark label included
    def _rs_key(r):
        if r['data'] and r['data'].get('rs_ratio') is not None:
            return r['data']['rs_ratio']
        return -999.0
    rs_spans = []
    for r in sorted(rows, key=_rs_key, reverse=True):
        bench = RS_BENCHMARKS.get(r['etf'], (None,))[0] or ''
        if not r['data']:
            rs_spans.append(html.Span([
                html.Span(r['etf'], style={'color': MUTED}),
                html.Span(f'(— {bench})', style={'color': MUTED}),
            ]))
            continue
        rs = r['data'].get('rs_ratio')
        if rs is not None:
            rc  = GREEN if rs > 1.5 else (RED if rs < -1.5 else YELLOW)
            sgn = '+' if rs >= 0 else ''
            arr = '↑' if rs > 1.5 else ('↓' if rs < -1.5 else '→')
            rs_spans.append(html.Span([
                html.Span(r['etf'], style={'color': _etf_color(r)}),
                html.Span(f'({arr}{sgn}{rs:.1f}% {bench})', style={'color': rc}),
            ]))
        else:
            rs_spans.append(html.Span([
                html.Span(r['etf'], style={'color': MUTED}),
                html.Span(f'(— {bench})', style={'color': MUTED}),
            ]))

    # ── Listed rows (same order as table: chg_pct descending) ────────────────
    # 6. Conviction
    conv_spans = []
    for r in rows:
        if not r['data']:
            conv_spans.append(html.Span([
                html.Span(r['etf'], style={'color': MUTED}),
                html.Span('(—)', style={'color': MUTED}),
            ]))
            continue
        conv = r['data']['conviction']
        cc   = CONVICTION_COLOR[conv]
        conv_spans.append(html.Span([
            html.Span(r['etf'], style={'color': _etf_color(r)}),
            html.Span(f'({conv})', style={'color': cc}),
        ]))

    # 7. Action (abbreviated)
    action_spans = []
    for r in rows:
        if not r['data']:
            action_spans.append(html.Span([
                html.Span(r['etf'], style={'color': MUTED}),
                html.Span('(—)', style={'color': MUTED}),
            ]))
            continue
        d      = r['data']
        action = get_action_text(d['rec'], d['conviction'])
        if 'Exit' in action or 'reduce' in action:
            short, ac = 'Exit',    RED
        elif 'Add full' in action:
            short, ac = 'Add',     GREEN
        elif 'Add partial' in action:
            short, ac = 'Add~',    GREEN
        elif 'Trim' in action:
            short, ac = 'Trim',    YELLOW
        elif 'Watch' in action:
            short, ac = 'Watch',   ACCENT
        elif 'Monitor' in action:
            short, ac = 'Monitor', ACCENT
        else:
            short, ac = 'Hold',    MUTED
        action_spans.append(html.Span([
            html.Span(r['etf'], style={'color': _etf_color(r)}),
            html.Span(f'({short})', style={'color': ac}),
        ]))

    # 8. Entry At
    entry_spans = []
    for r in rows:
        if not r['data']:
            entry_spans.append(html.Span([
                html.Span(r['etf'], style={'color': MUTED}),
                html.Span('(—)', style={'color': MUTED}),
            ]))
            continue
        d = r['data']
        if d['rec'] == 'BUY':
            ev, ec = 'SMA20', GREEN
        elif d['rec'] == 'SELL':
            ev, ec = 'Avoid', RED
        else:
            ev, ec = 'SMA50', MUTED
        entry_spans.append(html.Span([
            html.Span(r['etf'], style={'color': _etf_color(r)}),
            html.Span(f'({ev})', style={'color': ec}),
        ]))

    # 9. SMA 20/50 position arrows (↑ = above, ↓ = below; first = SMA20, second = SMA50)
    sma_spans = []
    for r in rows:
        if not r['data']:
            sma_spans.append(html.Span([
                html.Span(r['etf'], style={'color': MUTED}),
                html.Span('(—)', style={'color': MUTED}),
            ]))
            continue
        d   = r['data']
        a20 = '↑' if d['vs20'] == 'Above' else '↓'
        a50 = '↑' if d['vs50'] == 'Above' else '↓'
        c20 = GREEN if d['vs20'] == 'Above' else RED
        c50 = GREEN if d['vs50'] == 'Above' else RED
        sma_spans.append(html.Span([
            html.Span(r['etf'], style={'color': _etf_color(r)}),
            html.Span('(', style={'color': MUTED}),
            html.Span(a20, style={'color': c20}),
            html.Span(a50, style={'color': c50}),
            html.Span(')', style={'color': MUTED}),
        ]))

    # 10. Signal Age — not yet implemented (requires persistent history)
    # TODO: Signal Age row

    return html.Div([
        _make_row('Price/Day%', price_spans),
        _make_row('Volume',     vol_spans),
        _make_row('RSI 14',     rsi_spans),
        _make_row('52W DD',     dd_spans),
        _make_row('RS Trend',   rs_spans),
        html.Div(style=SEP),
        _make_row('Conviction', conv_spans),
        _make_row('Action',     action_spans),
        _make_row('Entry At',   entry_spans),
        _make_row('SMA 20/50',  sma_spans),
    ], style={'padding': '4px 0'})


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
body{background:#0f1117;min-height:100vh;display:flex;align-items:center;justify-content:center;font-family:monospace}
.card{background:#1c2333;border:1px solid #253047;border-radius:10px;padding:40px;width:100%;max-width:360px}
h1{color:#dde5f0;font-size:16px;font-weight:700;margin-bottom:4px;letter-spacing:.5px}
.sub{color:#8b9ab0;font-size:11px;margin-bottom:28px}
label{display:block;color:#8b9ab0;font-size:11px;margin-bottom:6px}
input{width:100%;background:#0f1117;border:1px solid #253047;border-radius:6px;color:#dde5f0;padding:10px 12px;font-family:monospace;font-size:14px;margin-bottom:16px;outline:none}
input:focus{border-color:#f59e0b}
button{width:100%;background:#f59e0b;color:#000;border:none;border-radius:6px;padding:10px;font-family:monospace;font-size:13px;font-weight:700;cursor:pointer}
button:hover{background:#fbbf24}
.err{color:#ef4444;font-size:11px;margin-bottom:12px}
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
        html.Div([
            html.Div(id='header-updated', style={'color': MUTED, 'fontSize': '11px', 'marginBottom': '6px'}),
            html.Div([
                html.Span('Theme:', style={'color': MUTED, 'fontSize': '10px',
                                           'fontFamily': 'monospace', 'marginRight': '6px'}),
                dcc.Dropdown(
                    id='theme-dropdown',
                    options=[{'label': t, 'value': t} for t in THEMES],
                    value='Slate',
                    clearable=False,
                    style={'width': '110px', 'fontSize': '11px', 'fontFamily': 'monospace'},
                ),
            ], style={'display': 'flex', 'alignItems': 'center'}),
        ], style={'textAlign': 'right'}),
    ], id='header-bar', style={
        'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
        'padding': '14px 20px', 'background': SURFACE, 'borderBottom': f'1px solid {BORDER}',
    }),

    # ── Macro Regime Strip ────────────────────────────────────────────────────
    html.Div(id='macro-regime-strip', style={'background': SURFACE}),

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
                dcc.Tab(label='Radar',            value='radar',
                        style=TAB_STYLE, selected_style=TAB_SELECTED),
            ],
            colors={'border': BORDER, 'primary': ACCENT, 'background': BG},
        ),
    ], id='tabs-bar', style={'background': CARD, 'borderBottom': f'1px solid {BORDER}', 'marginBottom': '20px'}),

    # ── Tab content ───────────────────────────────────────────────────────────
    html.Div(id='tab-content',
             style={'maxWidth': '1100px', 'margin': '0 auto', 'padding': '0 16px 40px'}),

    # ── Stores & intervals ────────────────────────────────────────────────────
    dcc.Store(id='selected-etf',  data='SEMG'),
    dcc.Store(id='selected-tf',   data='1M'),
    dcc.Store(id='price-period',  data='today'),
    dcc.Store(id='summary-view',  data='table'),
    dcc.Store(id='sort-mode',     data='daypct'),
    dcc.Store(id='chart-tickers', data=['SEMG', 'WTAI']),
    dcc.Store(id='chart-mode',    data='price'),
    dcc.Store(id='snapshot-tf',   data='1d'),
    dcc.Store(id='radar-pinned',  data=[]),
    dcc.Interval(id='refresh', interval=60_000, n_intervals=0),

], id='app-root', style={'background': BG, 'minHeight': '100vh', 'fontFamily': 'monospace'})


# ── Radar tab ─────────────────────────────────────────────────────────────────
def build_radar_table(rows: list, pin_pinned: list = []) -> html.Table:
    header = html.Tr([
        html.Th(h, style={**TH_STYLE})
        for h in ['ETF', 'NAME', 'RSI 14', 'RS vs SWDA', '52W DD', 'SIGNAL']
    ])
    trs = []
    for row in rows:
        etf  = row['etf']
        data = row['data']
        if data is None:
            trs.append(html.Tr([
                html.Td(etf,                   style={**TD_STYLE, 'color': TEXT, 'fontWeight': '700'}),
                html.Td(WATCHLIST_NAMES[etf],  style={**TD_STYLE, 'color': MUTED}),
                html.Td('data unavailable', colSpan=4,
                        style={**TD_STYLE, 'color': MUTED, 'fontStyle': 'italic'}),
            ], style={'borderBottom': f'1px solid {BORDER}'}))
            continue
        row_border = f'3px solid {GREEN}' if data['signal'] else '3px solid transparent'
        rsi_c   = GREEN if data['rsi_cross'] else (AMBER if data['rsi'] > 60 else MUTED)
        rsi_cell = html.Td([
            html.Div(f'{data["rsi"]:.0f}',
                     style={'color': rsi_c, 'fontWeight': '700', 'fontSize': '13px'}),
            html.Div('crossed ↑' if data['rsi_cross'] else '—',
                     style={'color': rsi_c, 'fontSize': '10px', 'marginTop': '2px'}),
        ], style=TD_STYLE)
        rs_val  = data['rs_30d']
        if rs_val is None:
            rs_c, rs_txt = MUTED, '—'
        else:
            rs_c   = GREEN if rs_val > 1.5 else (RED if rs_val < 0 else AMBER)
            rs_txt = f'{rs_val:+.1f}%'
        rs_cell  = html.Td(rs_txt, style={**TD_STYLE, 'color': rs_c,
                                          'fontWeight': '700', 'fontSize': '13px'})
        dd       = data['drawdown']
        dd_c     = GREEN if dd > -5 else (RED if dd < -15 else AMBER)
        dd_cell  = html.Td(f'{dd:.1f}%', style={**TD_STYLE, 'color': dd_c,
                                                 'fontWeight': '700', 'fontSize': '13px'})
        pin_worthy = (
            data.get('rsi_cross') or
            (data.get('rs_30d') is not None and data['rs_30d'] > 1.5) or
            (data.get('drawdown') is not None and data['drawdown'] > -15.0)
        )
        if pin_worthy:
            pin_already = etf in pin_pinned
            pin_btn = html.Button(
                '✕ Remove' if pin_already else '＋ Charts',
                id={'type': 'pin-radar', 'index': etf},
                n_clicks=0,
                style={
                    'fontSize': '10px', 'fontFamily': 'monospace',
                    'padding': '2px 7px', 'marginLeft': '8px',
                    'background': 'transparent', 'cursor': 'pointer',
                    'color': RED if pin_already else ACCENT,
                    'border': f'1px solid {RED if pin_already else ACCENT}',
                    'borderRadius': '3px',
                },
            )
            sig_cell = html.Td(
                [*([html.Span('✓ ENTRY', style={'color': GREEN, 'fontWeight': '700',
                                                'fontSize': '13px'})] if data['signal'] else []),
                 pin_btn],
                style={**TD_STYLE, 'whiteSpace': 'nowrap'},
            )
        else:
            sig_cell = html.Td('—', style={**TD_STYLE, 'color': MUTED, 'fontSize': '13px'})
        trs.append(html.Tr([
            html.Td(etf, style={**TD_STYLE, 'color': TEXT,
                                'fontWeight': '700', 'fontSize': '14px',
                                'borderLeft': row_border}),
            html.Td(WATCHLIST_NAMES[etf], style={**TD_STYLE, 'color': MUTED, 'fontSize': '11px'}),
            rsi_cell, rs_cell, dd_cell, sig_cell,
        ], style={'borderBottom': f'1px solid {BORDER}'}))
    return html.Table([html.Thead(header), html.Tbody(trs)],
                      style={'width': '100%', 'borderCollapse': 'collapse'})


# ── Tab router ────────────────────────────────────────────────────────────────
@app.callback(
    Output('tab-content', 'children'),
    [Input('main-tabs', 'value'), Input('radar-pinned', 'data')],
    [State('selected-etf', 'data'), State('selected-tf', 'data'),
     State('price-period', 'data'), State('chart-tickers', 'data'),
     State('chart-mode',   'data'), State('snapshot-tf',   'data')],
)
def render_tab(tab, pin_pinned, sel_etf, sel_tf, price_period, chart_tickers, chart_mode, snap_tf):
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
                          'alignItems': 'flex-start', 'marginBottom': '4px'}),
                html.Div([
                    html.Div([
                        html.Button('⊟ Table',   id='btn-view-table',   n_clicks=0,
                                    style=_view_btn_style('table',   'table')),
                        html.Button('≡ Summary', id='btn-view-summary', n_clicks=0,
                                    style=_view_btn_style('summary', 'table')),
                    ], style={'display': 'flex'}),
                    html.Div([
                        html.Span('Sort:', style={'color': MUTED, 'fontSize': '11px',
                                                  'marginRight': '6px', 'alignSelf': 'center'}),
                        html.Button('Day%',   id='btn-sort-daypct', n_clicks=0,
                                    style=_sort_btn_style('daypct', 'daypct')),
                        html.Button('WT%',    id='btn-sort-weight', n_clicks=0,
                                    style={**_sort_btn_style('weight', 'daypct'), 'marginLeft': '4px'}),
                        html.Button('RS 30d', id='btn-sort-rs',     n_clicks=0,
                                    style={**_sort_btn_style('rs',  'daypct'), 'marginLeft': '4px'}),
                        html.Button('RSI',    id='btn-sort-rsi',    n_clicks=0,
                                    style={**_sort_btn_style('rsi', 'daypct'), 'marginLeft': '4px'}),
                        html.Button('52W DD', id='btn-sort-dd',     n_clicks=0,
                                    style={**_sort_btn_style('dd',  'daypct'), 'marginLeft': '4px'}),
                    ], style={'display': 'flex', 'alignItems': 'center'}),
                ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
                          'borderBottom': f'1px solid {BORDER}', 'marginBottom': '12px'}),
                dcc.Loading(html.Div(id='signal-table'), color=ACCENT),
            ], {'overflowX': 'auto'}),
        ])

    if tab == 'charts':
        active_tickers  = set(chart_tickers or ['SEMG', 'WTAI'])
        mode            = chart_mode or 'price'
        rsi_mode        = mode == 'rsi'
        return html.Div([
            card(html.Div(
                [html.Button(t, id={'type': 'chart-ticker-btn', 'index': t}, n_clicks=0,
                             style=_chart_ticker_btn_style(
                                 t, t in active_tickers,
                                 greyed=(rsi_mode and t in ('SPX', 'NDQ'))))
                 for t in CHART_TICKERS_ALL],
                style={'display': 'flex', 'gap': '8px', 'flexWrap': 'wrap'},
            ), {'padding': '14px 16px'}),

            card([
                html.Div([
                    html.Button('Price',  id={'type': 'chart-mode-btn', 'index': 'price'},  n_clicks=0,
                                style=_chart_mode_btn_style('price', mode)),
                    html.Button('RSI 14', id={'type': 'chart-mode-btn', 'index': 'rsi'},    n_clicks=0,
                                style={**_chart_mode_btn_style('rsi', mode),    'marginLeft': '4px'}),
                    html.Button('Volume', id={'type': 'chart-mode-btn', 'index': 'volume'}, n_clicks=0,
                                style={**_chart_mode_btn_style('volume', mode), 'marginLeft': '4px'}),
                ], style={'display': 'flex', 'marginBottom': '10px'}),
                html.Div(
                    [html.Button(tf, id={'type': 'tf-btn', 'index': tf}, n_clicks=0,
                                 style=tf_btn_style(tf, sel_tf or '1M'))
                     for tf in TIMEFRAMES],
                    style={'display': 'flex', 'gap': '4px', 'marginBottom': '12px'},
                ),
                dcc.Loading(dcc.Graph(id='price-chart', config={'displayModeBar': False}), color=ACCENT),
                html.Div(id='price-chart-legend',
                         style={'marginTop': '10px', 'fontSize': '12px', 'fontFamily': 'monospace'}),
            ]),
            html.Div(
                [html.Span('Snapshot:', style={
                    'color': MUTED, 'fontSize': '11px', 'fontFamily': 'monospace',
                    'marginRight': '8px', 'alignSelf': 'center',
                })] + [
                    html.Button(
                        tf.upper(), id=f'snap-tf-{tf}', n_clicks=0,
                        style={**toggle_btn_style(tf, snap_tf or '1d'),
                               **({'marginLeft': '4px'} if i > 0 else {})},
                    )
                    for i, tf in enumerate(['1d', '1w', '1m', '3m', '6m', '1y'])
                ],
                style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '8px'},
            ),
            html.Div(id='chart-stats-bars'),
            html.Div(id='chart-conv-cards'),
        ])

    if tab == 'radar':
        radar_rows = [
            {'etf': etf, 'data': fetch_radar_ticker(WATCHLIST_TICKERS[etf])}
            for etf in WATCHLIST
        ]
        return card([
            html.H2('Radar — Momentum Entry Scanner',
                    style={'color': TEXT, 'margin': '0 0 4px 0',
                           'fontSize': '15px', 'fontWeight': '700'}),
            html.P('RSI crossed above 60 · RS vs SWDA positive · 52W DD better than −15%',
                   style={'color': MUTED, 'fontSize': '11px', 'margin': '0 0 16px 0'}),
            build_radar_table(radar_rows, pin_pinned or []),
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
     Input('price-period', 'data'),
     Input('sort-mode',    'data')],
    [State('summary-view', 'data')],
)
def update_signal_summary(tab, _, price_period, sort_mode, current_view):
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
            data['rs_ratio']   = fetch_rs_ratio(etf)
            data['rs_persist'] = fetch_rs_persist(etf)
            data['rs_flips']   = fetch_rs_flips(etf)
            data['rate_beta']  = fetch_rate_beta(etf)
            action_text = get_action_text(data['rec'], data['conviction'])
            conv_age, action_age = _update_signal_history(etf, data['conviction'], action_text)
        else:
            conv_age = action_age = 'unknown'
        rows.append({'etf': etf, 'data': data, 'conv_age': conv_age, 'action_age': action_age})

    now      = datetime.now().strftime('%H:%M:%S')
    daily_ts = next((r['data']['daily_cached_at'] for r in rows if r['data']), None)
    updated_el = html.Div([
        html.Div(f'Updated {now}', style={'color': MUTED, 'fontSize': '11px'}),
        html.Div(
            f'Daily stats as of {daily_ts}' if daily_ts else '',
            style={'color': MUTED, 'fontSize': '10px', 'marginTop': '1px'},
        ),
    ])

    # Render both views; show the correct one based on current_view State
    view          = current_view or 'table'
    table_style   = {'display': 'none'} if view == 'summary' else {}
    summary_style = {}                  if view == 'summary' else {'display': 'none'}
    content = html.Div([
        html.Div(build_summary_table(rows, show_week, sort_mode or 'weight'), id='view-table-container',   style=table_style),
        html.Div(build_summary_view(rows, show_week),  id='view-summary-container', style=summary_style),
    ])
    return content, updated_el


# ── Summary view toggle callbacks ────────────────────────────────────────────
@app.callback(
    Output('summary-view', 'data'),
    [Input('btn-view-table', 'n_clicks'), Input('btn-view-summary', 'n_clicks')],
    prevent_initial_call=True,
)
def toggle_summary_view(_, __):
    triggered = dash.callback_context.triggered[0]['prop_id']
    return 'summary' if 'btn-view-summary' in triggered else 'table'


@app.callback(
    Output('sort-mode', 'data'),
    [Input('btn-sort-daypct', 'n_clicks'),
     Input('btn-sort-weight', 'n_clicks'),
     Input('btn-sort-rs',     'n_clicks'),
     Input('btn-sort-rsi',    'n_clicks'),
     Input('btn-sort-dd',     'n_clicks')],
    prevent_initial_call=True,
)
def update_sort_mode(_, __, ___, ____, _____):
    triggered = dash.callback_context.triggered[0]['prop_id']
    if 'btn-sort-daypct' in triggered: return 'daypct'
    if 'btn-sort-rsi'    in triggered: return 'rsi'
    if 'btn-sort-weight' in triggered: return 'weight'
    if 'btn-sort-rs'     in triggered: return 'rs'
    if 'btn-sort-dd'     in triggered: return 'dd'
    return 'daypct'


@app.callback(
    [Output('btn-sort-daypct', 'style'),
     Output('btn-sort-weight', 'style'),
     Output('btn-sort-rs',     'style'),
     Output('btn-sort-rsi',    'style'),
     Output('btn-sort-dd',     'style')],
    Input('sort-mode', 'data'),
)
def style_sort_buttons(sort_mode):
    m = sort_mode or 'daypct'
    return (
        _sort_btn_style('daypct', m),
        {**_sort_btn_style('weight', m), 'marginLeft': '4px'},
        {**_sort_btn_style('rs',     m), 'marginLeft': '4px'},
        {**_sort_btn_style('rsi',    m), 'marginLeft': '4px'},
        {**_sort_btn_style('dd',     m), 'marginLeft': '4px'},
    )


@app.callback(
    [Output('view-table-container', 'style'), Output('view-summary-container', 'style')],
    Input('summary-view', 'data'),
    prevent_initial_call=True,
)
def switch_summary_view(view):
    if view == 'summary':
        return {'display': 'none'}, {}
    return {}, {'display': 'none'}


@app.callback(
    [Output('btn-view-table', 'style'), Output('btn-view-summary', 'style')],
    Input('summary-view', 'data'),
)
def style_view_buttons(view):
    v = view or 'table'
    return _view_btn_style('table', v), _view_btn_style('summary', v)


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


# ── Chart mode callbacks (T5) ────────────────────────────────────────────────
@app.callback(
    Output('chart-mode', 'data'),
    [Input({'type': 'chart-mode-btn', 'index': m}, 'n_clicks') for m in ('price', 'rsi', 'volume')],
    prevent_initial_call=True,
)
def update_chart_mode(*_):
    triggered = dash.callback_context.triggered[0]['prop_id']
    return json.loads(triggered.split('.')[0])['index']


@app.callback(
    [Output({'type': 'chart-mode-btn', 'index': m}, 'style') for m in ('price', 'rsi', 'volume')],
    Input('chart-mode', 'data'),
)
def style_chart_mode_buttons(mode):
    m = mode or 'price'
    return [_chart_mode_btn_style('price', m),
            {**_chart_mode_btn_style('rsi',    m), 'marginLeft': '4px'},
            {**_chart_mode_btn_style('volume', m), 'marginLeft': '4px'}]


# ── Price chart callback (T4/T5) ──────────────────────────────────────────────
@app.callback(
    [
        Output('price-chart',        'figure'),
        Output('price-chart-legend', 'children'),
        Output('header-updated',     'children'),
    ],
    [
        Input('chart-tickers', 'data'),
        Input('selected-tf',   'data'),
        Input('refresh',       'n_intervals'),
        Input('chart-mode',    'data'),
        Input('radar-pinned',  'data'),
    ],
)
def update_price_chart(tickers, tf, _, mode, pin_pinned):
    bars    = TF_BARS.get(tf or '1M', 21)
    now     = datetime.now().strftime('%H:%M:%S')
    active  = list(tickers or ['SEMG', 'WTAI'])
    mode    = mode or 'price'

    # ── RSI mode ──────────────────────────────────────────────────────────────
    if mode == 'rsi':
        fig          = go.Figure()
        legend_items = []

        rsi_data = []
        for ticker in active:
            if ticker in ('SPX', 'NDQ'):
                continue
            color = CHART_DASH.get(ticker, CHART_COLORS.get(ticker, TEXT))
            df    = _get_daily_df(TICKERS[ticker])
            if df.empty:
                continue
            rsi_s = df['RSI'].dropna().iloc[-bars:]
            if len(rsi_s) < 2:
                continue
            rsi_data.append((ticker, color, rsi_s))
        for pin_etf in (pin_pinned or []):
            pin_df = _get_daily_df(WATCHLIST_TICKERS.get(pin_etf, ''))
            if pin_df is None or pin_df.empty:
                continue
            rsi_s = pin_df['RSI'].dropna().iloc[-bars:]
            if len(rsi_s) < 2:
                continue
            rsi_data.append((pin_etf, '#a78bfa', rsi_s))
        rsi_data.sort(key=lambda x: float(x[2].iloc[-1]), reverse=True)
        for ticker, color, rsi_s in rsi_data:
            current_rsi = float(rsi_s.iloc[-1])
            fig.add_trace(go.Scatter(
                x=rsi_s.index, y=rsi_s.values,
                name=ticker, mode='lines',
                line=dict(color=color, width=2,
                          dash='dash' if ticker in CHART_DASH else 'solid'),
                hovertemplate=f'{ticker}: %{{y:.1f}}<extra></extra>',
            ))
            legend_items.append((ticker, color, current_rsi))

        for level, lcolor, label in [(70, RED, 'Overbought'), (50, MUTED, 'Midline'), (30, GREEN, 'Oversold')]:
            fig.add_hline(y=level, line_dash='dash', line_color=lcolor, line_width=1,
                          annotation_text=label, annotation_position='right',
                          annotation_font=dict(color=lcolor, size=10, family='monospace'))

        base_layout = dict(
            template='plotly_dark', paper_bgcolor=SURFACE, plot_bgcolor=CARD,
            font=dict(family='monospace', color=TEXT, size=11),
            margin=dict(l=0, r=50, t=10, b=0), height=340,
            showlegend=False, hovermode='x unified',
            yaxis=dict(title='RSI 14', range=[0, 100], gridcolor=BORDER, zeroline=False),
            xaxis=dict(gridcolor=BORDER, zeroline=False),
        )
        fig.update_layout(**base_layout)

        if not legend_items:
            return fig, '', f'Updated {now}'

        rsi_color = lambda v: RED if v > 70 else (GREEN if v < 30 else (AMBER if v > 55 else MUTED))
        legend_el = html.Div([
            html.Span([
                html.Span('● ', style={'color': c}),
                html.Span(t, style={'color': TEXT, 'marginRight': '4px'}),
                html.Span(f'{v:.1f}', style={'color': rsi_color(v), 'marginRight': '20px'}),
            ])
            for t, c, v in legend_items
        ], style={'display': 'flex', 'flexWrap': 'wrap'})
        return fig, legend_el, f'Updated {now}'

    # ── Volume mode ────────────────────────────────────────────────────────────
    if mode == 'volume':
        fig          = go.Figure()
        legend_items = []
        vol_data     = []

        for ticker in active:
            if ticker in ('SPX', 'NDQ'):
                continue
            color = CHART_DASH.get(ticker, CHART_COLORS.get(ticker, TEXT))
            df    = _get_daily_df(TICKERS[ticker])
            if df.empty or 'Volume' not in df.columns:
                continue
            vol_s = df['Volume'].dropna().iloc[-bars:]
            if len(vol_s) < 1:
                continue
            vol_data.append((ticker, color, vol_s, df))
        for pin_etf in (pin_pinned or []):
            pin_df = _get_daily_df(WATCHLIST_TICKERS.get(pin_etf, ''))
            if pin_df is None or pin_df.empty or 'Volume' not in pin_df.columns:
                continue
            vol_s = pin_df['Volume'].dropna().iloc[-bars:]
            if len(vol_s) < 1:
                continue
            vol_data.append((pin_etf, '#a78bfa', vol_s, pin_df))

        vol_data.sort(key=lambda x: float(x[2].mean()), reverse=True)

        for ticker, color, vol_s, df in vol_data:
            period_avg = float(vol_s.mean())
            fig.add_trace(go.Bar(
                x=vol_s.index, y=vol_s.values,
                name=ticker, marker_color=color, opacity=0.8,
                hovertemplate=f'{ticker}: %{{y:,.0f}}<extra></extra>',
            ))
            avg_s = df['Volume'].rolling(20).mean().dropna().iloc[-bars:]
            if len(avg_s) > 0:
                fig.add_trace(go.Scatter(
                    x=avg_s.index, y=avg_s.values,
                    name=f'{ticker} avg', mode='lines',
                    line=dict(color=color, width=1.5, dash='dash'),
                    opacity=0.5, showlegend=False,
                    hovertemplate=f'{ticker} 20d avg: %{{y:,.0f}}<extra></extra>',
                ))
            legend_items.append((ticker, color, period_avg))

        if not legend_items:
            fig.update_layout(
                template='plotly_dark', paper_bgcolor=SURFACE, plot_bgcolor=CARD, height=340,
                annotations=[dict(text='No data', x=0.5, y=0.5, showarrow=False,
                                  font=dict(color=MUTED, size=14))],
            )
            return fig, '', f'Updated {now}'

        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor=SURFACE, plot_bgcolor=CARD,
            font=dict(family='monospace', color=TEXT, size=11),
            margin=dict(l=0, r=0, t=10, b=0), height=340,
            barmode='group', showlegend=False, hovermode='x unified',
            yaxis=dict(title='Volume', gridcolor=BORDER, zeroline=False),
            xaxis=dict(gridcolor=BORDER, zeroline=False),
        )

        legend_el = html.Div([
            html.Span([
                html.Span('■ ', style={'color': c}),
                html.Span(t, style={'color': TEXT, 'marginRight': '4px'}),
                html.Span(f'avg {int(v):,}', style={'color': MUTED, 'marginRight': '20px'}),
            ])
            for t, c, v in legend_items
        ], style={'display': 'flex', 'flexWrap': 'wrap'})
        return fig, legend_el, f'Updated {now}'

    # ── Price mode (default) ───────────────────────────────────────────────────

    fig          = go.Figure()
    legend_items = []

    price_data = []
    for ticker in active:
        color = CHART_COLORS.get(ticker, TEXT)
        if ticker == 'SPX':
            series = fetch_benchmark_price('^GSPC')
        elif ticker == 'NDQ':
            series = fetch_benchmark_price('^IXIC')
        else:
            df = _get_daily_df(TICKERS[ticker])
            if df.empty:
                series = fetch_benchmark_price(TICKERS[ticker])
            else:
                close_s = df['Close'].dropna()
                series  = close_s if not close_s.empty else None

        if series is None or len(series) < 2:
            continue
        series = series.iloc[-bars:]
        if len(series) < 2:
            continue
        norm        = (series / series.iloc[0]) * 100
        period_ret  = (series.iloc[-1] / series.iloc[0] - 1) * 100
        trace_color = CHART_DASH.get(ticker, color)
        price_data.append((ticker, norm, period_ret, trace_color))
    for pin_etf in (pin_pinned or []):
        pin_df = _get_daily_df(WATCHLIST_TICKERS.get(pin_etf, ''))
        if pin_df is None or pin_df.empty:
            continue
        close_s = pin_df['Close'].dropna()
        if close_s.empty:
            continue
        series = close_s.iloc[-bars:]
        if len(series) < 2:
            continue
        norm       = (series / series.iloc[0]) * 100
        period_ret = (series.iloc[-1] / series.iloc[0] - 1) * 100
        price_data.append((pin_etf, norm, period_ret, '#a78bfa'))

    price_data.sort(key=lambda x: float(x[1].iloc[-1]), reverse=True)

    for ticker, norm, period_ret, trace_color in price_data:
        if ticker in CHART_DASH:
            fig.add_trace(go.Scatter(
                x=norm.index, y=norm.values,
                name=ticker, mode='lines',
                line=dict(dash='dash', color=trace_color, width=2.5),
                hovertemplate=f'{ticker}: %{{y:.1f}}<extra></extra>',
            ))
        else:
            fig.add_trace(go.Scatter(
                x=norm.index, y=norm.values,
                name=ticker, mode='lines',
                line=dict(color=trace_color, width=2),
                hovertemplate=f'{ticker}: %{{y:.1f}}<extra></extra>',
            ))
        legend_items.append((ticker, trace_color, period_ret))

    if not legend_items:
        fig.update_layout(
            template='plotly_dark', paper_bgcolor=SURFACE, plot_bgcolor=CARD, height=340,
            annotations=[dict(text='No data', x=0.5, y=0.5, showarrow=False,
                              font=dict(color=MUTED, size=14))],
        )
        return fig, '', f'Updated {now}'

    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor=SURFACE, plot_bgcolor=CARD,
        font=dict(family='monospace', color=TEXT, size=11),
        margin=dict(l=0, r=0, t=10, b=0), height=340,
        showlegend=False, hovermode='x unified',
        yaxis=dict(title='Indexed (start = 100)', gridcolor=BORDER, zeroline=False),
        xaxis=dict(gridcolor=BORDER, zeroline=False),
    )

    legend_el = html.Div([
        html.Span([
            html.Span('● ', style={'color': color}),
            html.Span(ticker, style={'color': TEXT, 'marginRight': '4px'}),
            html.Span(
                f'{ret:+.1f}%',
                style={'color': GREEN if ret >= 0 else RED, 'marginRight': '20px'},
            ),
        ])
        for ticker, color, ret in legend_items
    ], style={'display': 'flex', 'flexWrap': 'wrap'})

    return fig, legend_el, f'Updated {now}'


# ── Chart ticker multi-select callbacks ───────────────────────────────────────
@app.callback(
    Output('chart-tickers', 'data'),
    Input({'type': 'chart-ticker-btn', 'index': dash.ALL}, 'n_clicks'),
    [State('chart-tickers', 'data'), State('chart-mode', 'data')],
    prevent_initial_call=True,
)
def toggle_chart_ticker(_, current_tickers, mode):
    triggered = dash.callback_context.triggered[0]['prop_id']
    ticker    = json.loads(triggered.split('.')[0])['index']
    if (mode or 'price') == 'rsi' and ticker in ('SPX', 'NDQ'):
        return current_tickers
    tickers = list(current_tickers or ['SEMG', 'WTAI'])
    if ticker in tickers:
        if len(tickers) > 1:
            tickers.remove(ticker)
    else:
        tickers.append(ticker)
    return tickers


@app.callback(
    [Output({'type': 'chart-ticker-btn', 'index': t}, 'style') for t in CHART_TICKERS_ALL],
    [Input('chart-tickers', 'data'), Input('chart-mode', 'data')],
)
def style_chart_ticker_buttons(tickers, mode):
    selected  = set(tickers or ['SEMG', 'WTAI'])
    rsi_mode  = (mode or 'price') == 'rsi'
    return [_chart_ticker_btn_style(t, t in selected,
                                    greyed=(rsi_mode and t in ('SPX', 'NDQ')))
            for t in CHART_TICKERS_ALL]


# ── Snapshot timeframe callbacks ──────────────────────────────────────────────
@app.callback(
    Output('snapshot-tf', 'data'),
    [Input(f'snap-tf-{tf}', 'n_clicks') for tf in ['1d', '1w', '1m', '3m', '6m', '1y']],
    prevent_initial_call=True,
)
def set_snapshot_tf(*_args):
    return dash.callback_context.triggered[0]['prop_id'].split('.')[0].replace('snap-tf-', '')


@app.callback(
    [Output(f'snap-tf-{tf}', 'style') for tf in ['1d', '1w', '1m', '3m', '6m', '1y']],
    Input('snapshot-tf', 'data'),
)
def style_snapshot_tf_buttons(snap_tf):
    m = snap_tf or '1d'
    return [
        {**toggle_btn_style(tf, m), **({'marginLeft': '4px'} if i > 0 else {})}
        for i, tf in enumerate(['1d', '1w', '1m', '3m', '6m', '1y'])
    ]


# ── Chart snapshot callback (T7) ─────────────────────────────────────────────
@app.callback(
    [Output('chart-stats-bars', 'children'),
     Output('chart-conv-cards', 'children')],
    [Input('chart-tickers', 'data'), Input('snapshot-tf', 'data'),
     Input('refresh', 'n_intervals'), Input('radar-pinned', 'data')],
)
def update_chart_snapshot(tickers, snap_tf, _, pin_pinned):
    active  = [t for t in (tickers or ['SEMG', 'WTAI']) if t not in ('SPX', 'NDQ')]
    snap_tf = snap_tf or '1d'
    bars    = SNAP_TF_BARS[snap_tf]

    etf_data: dict = {}
    cards: list    = []
    for etf in active:
        proxy = WTAI_VOL_PROXY if etf == 'WTAI' else None
        data  = fetch_latest(TICKERS[etf], vol_proxy=proxy)
        if data is None:
            continue
        data['rs_ratio'] = fetch_rs_ratio(etf)
        etf_data[etf]    = data
        cards.append(_conv_card(etf, data))

    if not etf_data:
        return html.Div(), html.Div()

    # ── Pinned radar ticker data ──────────────────────────────────────────────
    pin_data: dict = {}
    swda_df = _get_daily_df('SWDA.L')
    for pin_etf in (pin_pinned or []):
        if pin_etf not in WATCHLIST_TICKERS:
            continue
        try:
            pin_df = _get_daily_df(WATCHLIST_TICKERS[pin_etf])
            if pin_df is None or pin_df.empty:
                continue
            close_s = pin_df['Close'].dropna()
            if len(close_s) < 2:
                continue
            high_52w  = float(pin_df['High'].max())
            drawdown  = (float(close_s.iloc[-1]) - high_52w) / high_52w * 100
            chg_pct   = float((close_s.iloc[-1] / close_s.iloc[-2] - 1) * 100)
            rs_ratio  = None
            if swda_df is not None and not swda_df.empty:
                ec = close_s.squeeze().copy()
                sc = swda_df['Close'].dropna().squeeze()
                ec.index = pd.to_datetime(ec.index).normalize()
                sc.index = pd.to_datetime(sc.index).normalize()
                mg = pd.merge(ec.rename('etf'), sc.rename('swda'),
                              left_index=True, right_index=True, how='inner')
                if len(mg) >= 32:
                    r        = mg['etf'] / mg['swda']
                    rs_ratio = float((r.iloc[-1] / r.iloc[-31] - 1) * 100)
            pin_data[pin_etf] = {'drawdown': drawdown, 'rs_ratio': rs_ratio, 'chg_pct': chg_pct}
        except Exception:
            continue

    # ── RSI row (all timeframes) ────────────────────────────────────────────
    rsi_e: list = []
    for etf in active:
        if etf not in etf_data:
            continue
        tc  = CHART_COLORS.get(etf, TEXT)
        df  = _get_daily_df(TICKERS[etf])
        if df.empty or 'RSI' not in df.columns:
            rsi_val = None
        else:
            rsi_s = df['RSI'].dropna()
            if snap_tf == '1d':
                rsi_val = float(rsi_s.iloc[-1]) if len(rsi_s) >= 1 else None
            else:
                rsi_val = float(rsi_s.iloc[-1]) if len(rsi_s) >= 1 else None
        if rsi_val is None:
            rsi_e.append({'etf': etf, 'val': 50, 'tcol': MUTED, 'vcol': MUTED, 'dstr': 'N/A'})
        else:
            rsi_vc = RED if rsi_val > 70 else GREEN if rsi_val < 30 else AMBER if rsi_val > 55 else MUTED
            rsi_e.append({'etf': etf, 'val': rsi_val, 'tcol': tc, 'vcol': rsi_vc, 'dstr': f'{rsi_val:.1f}'})
    for pin_etf in pin_data:
        pin_df = _get_daily_df(WATCHLIST_TICKERS[pin_etf])
        if pin_df is None or pin_df.empty or 'RSI' not in pin_df.columns:
            continue
        rsi_s   = pin_df['RSI'].dropna()
        rsi_val = float(rsi_s.iloc[-1]) if len(rsi_s) >= 1 else None
        if rsi_val is None:
            continue
        rsi_vc = RED if rsi_val > 70 else GREEN if rsi_val < 30 else AMBER if rsi_val > 55 else MUTED
        rsi_e.append({'etf': pin_etf, 'val': rsi_val, 'tcol': '#a78bfa',
                      'vcol': rsi_vc, 'dstr': f'{rsi_val:.1f}'})

    rsi_track = _build_stat_track(
        'RSI 14', rsi_e, 20, 100,
        track_zones=[
            (0, 12.5, '#bbf7d0'), (12.5, 43.75, '#fef9c3'),
            (43.75, 62.5, '#e0f2fe'), (62.5, 100, '#fecaca'),
        ],
        marker_lines=[(30, '#f59e0b', 0.3, 1), (55, '#8b9ab0', 0.25, 1), (70, '#ef4444', 0.5, 2)],
        zone_label_defs=[
            (0, 12.5, 'oversold <30', '#1e293b'), (12.5, 43.75, 'neutral 30–55', '#1e293b'),
            (43.75, 62.5, 'momentum 55–70', '#1e293b'), (62.5, 100, 'overbought >70', '#1e293b'),
        ],
        axis_labels=('20', 'danger >70', '100'),
    )

    if snap_tf == '1d':
        # ── 1D: original 4 rows ─────────────────────────────────────────────
        dd_e: list = []; rs_e: list = []; day_e: list = []
        for etf, d in etf_data.items():
            tc = CHART_COLORS.get(etf, TEXT)
            dd = d.get('drawdown')
            if dd is not None:
                dd_e.append({'etf': etf, 'val': dd, 'tcol': tc, 'vcol': RED, 'dstr': f'{dd:.1f}%'})
            rs = d.get('rs_ratio')
            if rs is not None:
                rs_vc = GREEN if rs > 1.5 else RED if rs < -1.5 else AMBER
                rs_e.append({'etf': etf, 'val': rs, 'tcol': tc, 'vcol': rs_vc, 'dstr': f'{rs:+.1f}%'})
            day = d['chg_pct']
            day_vc = GREEN if day > 0 else RED
            day_e.append({'etf': etf, 'val': day, 'tcol': tc, 'vcol': day_vc, 'dstr': f'{day:+.2f}%'})
        for pin_etf, pd_ in pin_data.items():
            dd = pd_.get('drawdown')
            if dd is not None:
                dd_e.append({'etf': pin_etf, 'val': dd, 'tcol': '#a78bfa',
                             'vcol': RED, 'dstr': f'{dd:.1f}%'})
            rs = pd_.get('rs_ratio')
            if rs is not None:
                rs_vc = GREEN if rs > 1.5 else RED if rs < -1.5 else AMBER
                rs_e.append({'etf': pin_etf, 'val': rs, 'tcol': '#a78bfa',
                             'vcol': rs_vc, 'dstr': f'{rs:+.1f}%'})
            day    = pd_.get('chg_pct', 0.0)
            day_vc = GREEN if day > 0 else RED
            day_e.append({'etf': pin_etf, 'val': day, 'tcol': '#a78bfa',
                          'vcol': day_vc, 'dstr': f'{day:+.2f}%'})

        dd_track = _build_stat_track(
            '52W Drawdown', dd_e, -25, 0,
            track_zones=[(0, 50, '#fecaca'), (50, 100, '#bbf7d0')],
            marker_lines=[(0, '#8b9ab0', 0.2, 2)],
            zone_label_defs=[(0, 50, '◄ deeper DD', '#1e293b'), (50, 100, 'shallow DD ►', '#1e293b')],
            axis_labels=('−25%', '', '0%'),
        )
        rs_track = _build_stat_track(
            'RS Trend 30d', rs_e, -10, 10,
            track_zones=[(0, 50, '#fecaca'), (50, 100, '#bbf7d0')],
            marker_lines=[(0, '#8b9ab0', 0.2, 2)],
            zone_label_defs=[(0, 50, '◄ lagging', '#1e293b'), (50, 100, 'outperforming ►', '#1e293b')],
            axis_labels=('−10%', '0', '+10%'),
        )
        day_track = _build_stat_track(
            'Day %', day_e, -3, 3,
            track_zones=[(0, 50, '#fecaca'), (50, 100, '#bbf7d0')],
            marker_lines=[(0, '#8b9ab0', 0.2, 2)],
            zone_label_defs=[(0, 50, '◄ down', '#1e293b'), (50, 100, 'up ►', '#1e293b')],
            axis_labels=('−3%', '0', '+3%'),
        )
        tracks = [rsi_track, dd_track, rs_track, day_track]

    else:
        # ── Multi-TF: period return + RS vs benchmark ────────────────────────
        pret_e: list = []; rsp_e: list = []
        for etf in active:
            if etf not in etf_data:
                continue
            tc    = CHART_COLORS.get(etf, TEXT)
            df    = _get_daily_df(TICKERS[etf])
            close = df['Close'].dropna()
            period_ret = ((close.iloc[-1] / close.iloc[-bars] - 1) * 100
                          if len(close) >= bars else None)
            pret_vc = GREEN if (period_ret or 0) > 0 else RED
            pret_e.append({
                'etf': etf,
                'val': period_ret if period_ret is not None else 0,
                'tcol': tc if period_ret is not None else MUTED,
                'vcol': pret_vc if period_ret is not None else MUTED,
                'dstr': f'{period_ret:+.1f}%' if period_ret is not None else 'N/A',
            })

            rs_period = None
            if etf in RS_BENCHMARKS and period_ret is not None:
                bench_s = fetch_benchmark_price(RS_BENCHMARKS[etf][0])
                if bench_s is not None and len(bench_s) >= 2:
                    slice_bars = min(bars, len(bench_s), len(close))
                    etf_ret    = (close.iloc[-1] / close.iloc[-slice_bars] - 1) * 100
                    bench_ret  = (bench_s.iloc[-1] / bench_s.iloc[-slice_bars] - 1) * 100
                    rs_period  = etf_ret - bench_ret
            rsp_vc = GREEN if (rs_period or 0) > 0 else RED
            rsp_e.append({
                'etf': etf,
                'val': rs_period if rs_period is not None else 0,
                'tcol': tc if rs_period is not None else MUTED,
                'vcol': rsp_vc if rs_period is not None else MUTED,
                'dstr': f'{rs_period:+.1f}%' if rs_period is not None else 'N/A',
            })
        for pin_etf in pin_data:
            pin_df = _get_daily_df(WATCHLIST_TICKERS[pin_etf])
            if pin_df is None or pin_df.empty:
                continue
            close      = pin_df['Close'].dropna()
            period_ret = ((close.iloc[-1] / close.iloc[-bars] - 1) * 100
                          if len(close) >= bars else None)
            pret_vc = GREEN if (period_ret or 0) > 0 else RED
            pret_e.append({
                'etf':  pin_etf,
                'val':  period_ret if period_ret is not None else 0,
                'tcol': '#a78bfa'  if period_ret is not None else MUTED,
                'vcol': pret_vc    if period_ret is not None else MUTED,
                'dstr': f'{period_ret:+.1f}%' if period_ret is not None else 'N/A',
            })
            rs_period = None
            if swda_df is not None and not swda_df.empty:
                swda_close = swda_df['Close'].dropna()
                sl = min(bars, len(swda_close), len(close))
                if sl >= 2:
                    rs_period = ((close.iloc[-1] / close.iloc[-sl] - 1) * 100
                                 - (swda_close.iloc[-1] / swda_close.iloc[-sl] - 1) * 100)
            rsp_vc = GREEN if (rs_period or 0) > 0 else RED
            rsp_e.append({
                'etf':  pin_etf,
                'val':  rs_period if rs_period is not None else 0,
                'tcol': '#a78bfa' if rs_period is not None else MUTED,
                'vcol': rsp_vc    if rs_period is not None else MUTED,
                'dstr': f'{rs_period:+.1f}%' if rs_period is not None else 'N/A',
            })

        # Dynamic symmetric scale with 4% margin each side (spec: ±46% of scale)
        pret_vals  = [e['val'] for e in pret_e if e['dstr'] != 'N/A']
        pret_abs   = max(abs(v) for v in pret_vals) if pret_vals else 1.0
        pret_scale = pret_abs * 50 / 46

        rsp_vals  = [e['val'] for e in rsp_e if e['dstr'] != 'N/A']
        rsp_abs   = max(abs(v) for v in rsp_vals) if rsp_vals else 1.0
        rsp_scale = rsp_abs * 50 / 46

        pret_track = _build_stat_track(
            'Period Return', pret_e, -pret_scale, pret_scale,
            track_zones=[(0, 50, '#fecaca'), (50, 100, '#bbf7d0')],
            marker_lines=[(0, '#8b9ab0', 0.2, 2)],
            zone_label_defs=[(0, 50, '← loss', '#1e293b'), (50, 100, 'gain →', '#1e293b')],
            axis_labels=('← loss', '0', 'gain →'),
        )
        rsp_track = _build_stat_track(
            'RS vs Benchmark', rsp_e, -rsp_scale, rsp_scale,
            track_zones=[(0, 50, '#fecaca'), (50, 100, '#bbf7d0')],
            marker_lines=[(0, '#8b9ab0', 0.2, 2)],
            zone_label_defs=[(0, 50, '← lagging', '#1e293b'), (50, 100, 'outperforming →', '#1e293b')],
            axis_labels=('← lagging', '0', 'outperforming →'),
        )
        tracks = [rsi_track, pret_track, rsp_track]

    stats_section = card([
        html.P('Snapshot', style={'color': '#1e293b', 'fontSize': '11px', 'fontWeight': '600',
                                   'letterSpacing': '0.5px', 'margin': '0 0 16px 0'}),
        *tracks,
    ], {'background': '#f0f4ff', 'border': '1px solid #c7d2fe'})
    cards_section = card(html.Div(cards, style={
        'display': 'flex', 'flexWrap': 'wrap', 'gap': '10px',
    }))
    return stats_section, cards_section


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


# ── Macro regime strip callback ───────────────────────────────────────────────
@app.callback(
    Output('macro-regime-strip', 'children'),
    Input('refresh', 'n_intervals'),
)
def update_macro_strip(_):
    return build_macro_strip(fetch_macro_regime())


# ── Theme switcher ────────────────────────────────────────────────────────────
@app.callback(
    [Output('app-root',          'style'),
     Output('header-bar',        'style'),
     Output('tabs-bar',          'style'),
     Output('macro-regime-strip','style')],
    Input('theme-dropdown', 'value'),
)
def apply_theme(theme_name):
    t = THEMES.get(theme_name, THEMES['Slate'])
    return (
        {'background': t['bg'], 'minHeight': '100vh', 'fontFamily': 'monospace'},
        {'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
         'padding': '14px 20px', 'background': t['surface'],
         'borderBottom': f'1px solid {t["border"]}'},
        {'background': t['card'], 'borderBottom': f'1px solid {t["border"]}',
         'marginBottom': '20px'},
        {'background': t['surface']},
    )


# ── Radar pin callback ────────────────────────────────────────────────────────
@app.callback(
    Output('radar-pinned', 'data'),
    Input({'type': 'pin-radar', 'index': ALL}, 'n_clicks'),
    State('radar-pinned', 'data'),
    prevent_initial_call=True,
)
def toggle_pin_radar(n_clicks_list, pin_pinned):
    pin_pinned = list(pin_pinned or [])
    ctx = dash.callback_context
    if not ctx.triggered or not isinstance(ctx.triggered_id, dict):
        raise dash.exceptions.PreventUpdate
    pin_etf = ctx.triggered_id['index']
    if pin_etf in pin_pinned:
        return [e for e in pin_pinned if e != pin_etf]
    return pin_pinned + [pin_etf]


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


# prediction_method_v3.py
"""Extended prediction utilities for the *v3* experiment.

This module builds on the v2 baseline by adding two additional features
mentioned in the notes:

1. **Volume‑breadth** – the proportion of recent days where volume exceeds
   its moving average.  A high breadth typically indicates a broad market move.
2. **Seasonality** – a simple factor based on the average return for the
   current calendar day‑of‑month and month‑of‑year.

Both features are normalised and combined with the original indicators via
configurable weights.  The default weights are chosen heuristically; they can
be tuned later in a back‑test.
"""

import pandas as pd
import numpy as np

try:
    import ta
except Exception as e:  # pragma: no cover
    ta = None
    _IMPORT_ERROR = e

# ---------------------------------------------------------------------------
# Original v2 helper functions (copied for reuse)
# ---------------------------------------------------------------------------

def _efficiency_ratio(close: pd.Series, period: int = 10) -> pd.Series:
    diff = close.diff()
    absolute_change = diff.abs().rolling(window=period).sum()
    direction = (close - close.shift(period)).abs()
    er = direction / absolute_change.replace(0, np.nan)
    return er

def _kama(close: pd.Series, period: int = 10, fast_period: int = 2, slow_period: int = 30) -> pd.Series:
    """Kaufman Adaptive Moving Average (KAMA) – manual implementation.

    Formula from Kaufman's *Trading Systems and Methods*:
        ER   = |Close_t - Close_{t-period}| / sum(|ΔClose|)
        SC   = [ER * (2/(fast+1) - 2/(slow+1)) + 2/(slow+1)]²
        KAMA_t = KAMA_{t-1} + SC * (Close_t - KAMA_{t-1})
    """
    close = close.values.astype(float)
    n = len(close)
    kama = np.full(n, np.nan)

    fast_sc = 2.0 / (fast_period + 1)
    slow_sc = 2.0 / (slow_period + 1)

    if n <= period:
        return pd.Series(kama)

    kama[period - 1] = close[period - 1]

    for i in range(period, n):
        direction = abs(close[i] - close[i - period])
        volatility = sum(abs(close[j] - close[j - 1]) for j in range(i - period + 1, i + 1))
        if volatility == 0:
            er = 0.0
        else:
            er = direction / volatility
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        kama[i] = kama[i - 1] + sc * (close[i] - kama[i - 1])

    return pd.Series(kama)


def _kama_slope(df: pd.DataFrame, period: int = 10) -> pd.Series:
    """Slope (first difference) of KAMA."""
    k = _kama(df['Close'], period=period)
    k.index = df.index
    return k.diff()

def _rsi_fast(close: pd.Series, period: int = 2) -> pd.Series:
    if ta is None:
        return pd.Series(np.nan, index=close.index)
    return ta.momentum.RSIIndicator(close=close, window=period).rsi()

def _macd_hist(df: pd.DataFrame) -> pd.Series:
    if ta is None:
        return pd.Series(np.nan, index=df.index)
    macd = ta.trend.MACD(close=df['Close'])
    return macd.macd_diff()

def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    if ta is None:
        return pd.Series(np.nan, index=df.index)
    return ta.volatility.AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=period).average_true_range()

# ---------------------------------------------------------------------------
# New v3 features
# ---------------------------------------------------------------------------

def _volume_breadth(df: pd.DataFrame, window: int = 20) -> float:
    """Proportion of the last *window* days where volume > its moving average.
    Result in the range [0, 1]."""
    if 'Volume' not in df.columns:
        return 0.0
    vol_ma = df['Volume'].rolling(window=window).mean()
    above = df['Volume'] > vol_ma
    return float(above.tail(window).mean())

def _seasonality_factor(df: pd.DataFrame) -> float:
    """Simple seasonality factor based on day‑of‑month and month‑of‑year.
    Computes average returns for the current day and month and averages them.
    """
    if len(df) < 30:
        return 0.0
    # Ensure Date column is datetime
    if not pd.api.types.is_datetime64_any_dtype(df['Date']):
        df = df.copy()
        df['Date'] = pd.to_datetime(df['Date'])
    returns = df['Close'].pct_change()
    df_tmp = df.copy()
    df_tmp['Return'] = returns
    df_tmp['Day'] = df_tmp['Date'].dt.day
    df_tmp['Month'] = df_tmp['Date'].dt.month
    cur_day = df_tmp['Day'].iloc[-1]
    cur_month = df_tmp['Month'].iloc[-1]
    day_factor = df_tmp.loc[df_tmp['Day'] == cur_day, 'Return'].mean()
    month_factor = df_tmp.loc[df_tmp['Month'] == cur_month, 'Return'].mean()
    # Replace NaN with 0 and average
    day_factor = day_factor if pd.notna(day_factor) else 0.0
    month_factor = month_factor if pd.notna(month_factor) else 0.0
    return float((day_factor + month_factor) / 2)

# ---------------------------------------------------------------------------
# Scoring function
# ---------------------------------------------------------------------------

def _safe_div(numerator: float, denom: float, default: float = 1.0) -> float:
    """Divide, falling back to `default` as the denominator when `denom` is
    NaN or zero. See v2/prediction_method.py's copy of this helper for why
    `denom if denom else default` is unsafe (NaN is truthy in Python).
    """
    if pd.isna(denom) or denom == 0:
        return numerator / default
    return numerator / denom


def next_candle_score_v3(df: pd.DataFrame,
                         weight_kama: float = 0.35,
                         weight_rsi: float = 0.15,
                         weight_macd: float = 0.15,
                         weight_er: float = 0.10,
                         weight_vol: float = 0.10,
                         weight_season: float = 0.15) -> float | None:
    """Composite next‑candle score using v3 features.

    Returns a value in ``[-1, 1]`` where a positive sign suggests an up‑move.
    All components are normalised; the weights can be tweaked for tuning.
    """
    if ta is None:
        raise ImportError("The 'ta' package is required. Install with `pip install ta`.")

    if len(df) < 30:
        return None

    er = _efficiency_ratio(df['Close']).iloc[-1]
    kama_s = _kama_slope(df).iloc[-1]
    rsi = _rsi_fast(df['Close']).iloc[-1]
    macd = _macd_hist(df).iloc[-1]
    atr_val = _atr(df).iloc[-1]

    # Normalise core components
    kama_norm = _safe_div(kama_s, atr_val)
    rsi_norm = (rsi - 50) / 50 if pd.notna(rsi) else 0
    macd_norm = _safe_div(macd, atr_val)

    # New features
    vol_breadth = _volume_breadth(df)
    season_factor = _seasonality_factor(df)
    # Map volume breadth from [0,1] to [-1,1]
    vol_norm = (vol_breadth - 0.5) * 2
    # Rough scaling of seasonality to comparable range (may be small)
    season_norm = season_factor * 2

    # Components
    trend = kama_norm * er
    momentum = rsi_norm * (1 - er)
    macd_comp = macd_norm * er

    score = (weight_kama * trend +
             weight_rsi * momentum +
             weight_macd * macd_comp +
             weight_er * er +
             weight_vol * vol_norm +
             weight_season * season_norm)

    return float(np.clip(score, -1, 1))


if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) < 2:
        print("Usage: python prediction_method_v3.py <csv_path>")
        sys.exit(1)
    df = pd.read_csv(sys.argv[1], parse_dates=["Date"]) if "Date" in pd.read_csv(sys.argv[1]).columns else pd.read_csv(sys.argv[1])
    print("Score:", next_candle_score_v3(df))

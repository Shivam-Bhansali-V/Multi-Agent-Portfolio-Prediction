# prediction_method.py
"""Utility functions to generate a lightweight next‑candle signal
based on the concepts described in the *v2* notes (Kaufman, Trading Systems
and Methods). The aim is to give a simple, deterministic formula that can be
used as a baseline before moving to more complex machine‑learning models.

The approach combines a few indicators that the notes highlight as useful:

1. **Efficiency Ratio (ER)** – measures market noise. Low ER ⇒ noisy
   market, favour short‑term mean‑reversion; high ER ⇒ trending market.
2. **KAMA slope** – adaptive moving average that follows the trend in low‑noise
   periods. The sign of the KAMA slope indicates direction.
3. **RSI (2‑period)** – a fast momentum oscillator useful for timing entries.
4. **MACD histogram** – captures changes in momentum.
5. **ATR** – normalises thresholds by volatility.

The function `next_candle_score` computes a weighted score from these
components and returns a probability‑like value in ``[-1, 1]`` where
``>0`` suggests an up‑move and ``<0`` a down‑move.  A simple linear model
is used; the weights were chosen heuristically from the book’s take‑aways.

Usage example::

    import pandas as pd
    from prediction_method import next_candle_score

    # df must contain columns: ['Open','High','Low','Close','Volume']
    df = pd.read_csv('historical.csv')
    prob = next_candle_score(df)
    if prob > 0.1:
        print('Long signal')
    elif prob < -0.1:
        print('Short signal')
    else:
        print('No clear edge')

The implementation relies on the `ta` Python package (pip install ta) for
most indicator calculations.  If the package is unavailable the function
fails gracefully and returns ``None``.
"""

import pandas as pd
import numpy as np

try:
    import ta
except Exception as e:  # pragma: no cover
    ta = None
    _IMPORT_ERROR = e


def _efficiency_ratio(close: pd.Series, period: int = 10) -> pd.Series:
    """Calculate the Efficiency Ratio (ER) over *period*.

    ER = |Close_t - Close_{t-period}| / sum(|ΔClose|) over the period.
    """
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

    # Seed KAMA with the close value at index (period - 1)
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
    """Slope (first difference) of KAMA.

    Positive slope → upward trend, negative → downward.
    """
    k = _kama(df['Close'], period=period)
    k.index = df.index
    return k.diff()


def _rsi_fast(close: pd.Series, period: int = 2) -> pd.Series:
    """Fast RSI (default 2 periods)."""
    if ta is None:
        return pd.Series(np.nan, index=close.index)
    return ta.momentum.RSIIndicator(close=close, window=period).rsi()


def _macd_hist(df: pd.DataFrame) -> pd.Series:
    """MACD histogram (MACD – signal)."""
    if ta is None:
        return pd.Series(np.nan, index=df.index)
    macd = ta.trend.MACD(close=df['Close'])
    return macd.macd_diff()


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (ATR)."""
    if ta is None:
        return pd.Series(np.nan, index=df.index)
    return ta.volatility.AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=period).average_true_range()


def _safe_div(numerator: float, denom: float, default: float = 1.0) -> float:
    """Divide, falling back to `default` as the denominator when `denom` is
    NaN or zero.

    `denom if denom else default` is NOT a safe NaN guard: NaN is truthy in
    Python (``bool(float('nan')) is True``), so that pattern silently divides
    by NaN instead of falling back, and the NaN then propagates through the
    whole score. This divides by `default` whenever `denom` is NaN or exactly
    zero, and by `denom` otherwise.
    """
    if pd.isna(denom) or denom == 0:
        return numerator / default
    return numerator / denom


def next_candle_score(df: pd.DataFrame) -> float | None:
    """Return a single score indicating the likely direction of the next candle.

    Parameters
    ----------
    df : pandas.DataFrame
        Must contain the columns ``Open, High, Low, Close, Volume``.
        The most recent row (last index) is considered the *current* candle.

    Returns
    -------
    float or None
        A value in ``[-1, 1]`` where positive suggests an up‑move. ``None`` is
        returned if required libraries are missing or the data is insufficient.
    """
    if ta is None:
        # The user might not have the `ta` library – we give a helpful hint.
        raise ImportError(
            "The 'ta' package is required for indicator calculations. "
            "Install it with `pip install ta` and retry."
        )

    # Ensure we have enough rows for the longest rolling window.
    min_rows = 30
    if len(df) < min_rows:
        return None

    # Compute the latest values of each component.
    er = _efficiency_ratio(df['Close']).iloc[-1]
    kama_s = _kama_slope(df).iloc[-1]
    rsi = _rsi_fast(df['Close']).iloc[-1]
    macd = _macd_hist(df).iloc[-1]
    atr_val = _atr(df).iloc[-1]

    # Normalise each term to make them comparable.
    # ER is already between 0 and 1.
    # KAMA slope: divide by recent ATR to express in volatility units.
    kama_norm = _safe_div(kama_s, atr_val)
    # RSI: centre around 50 and scale to [-1, 1].
    rsi_norm = (rsi - 50) / 50 if pd.notna(rsi) else 0
    # MACD histogram: also normalise by ATR.
    macd_norm = _safe_div(macd, atr_val)

    # Heuristic weights derived from the book's emphasis:
    #   • Trend (KAMA) – 0.4
    #   • Momentum (RSI) – 0.2
    #   • MACD – 0.2
    #   • Noise (ER) – 0.1 (higher ER favours trend, lower favours mean‑reversion)
    #   • Volatility scaling – already applied.
    weight_kama = 0.4
    weight_rsi = 0.2
    weight_macd = 0.2
    weight_er = 0.1

    # Combine the signals. ER is used as a multiplier: when ER is high we trust
    # the trend more, when low we dampen it.
    trend_component = kama_norm * er
    momentum_component = rsi_norm * (1 - er)  # mean‑reversion weight when noisy
    macd_component = macd_norm * er

    score = (
        weight_kama * trend_component +
        weight_rsi * momentum_component +
        weight_macd * macd_component
    )

    # Clip to the [-1, 1] interval for interpretability.
    return float(np.clip(score, -1, 1))


if __name__ == "__main__":  # pragma: no cover
    # Simple demo when run directly.
    sample_path = "sample_data.csv"
    try:
        data = pd.read_csv(sample_path)
        print("Score for next candle:", next_candle_score(data))
    except Exception as exc:
        print(f"Unable to run demo: {exc}")

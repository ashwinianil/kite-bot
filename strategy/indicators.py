"""
Technical indicator calculations shared across scripts.

Uses pandas-ta-classic (actively maintained fork of pandas_ta) for
Supertrend and RSI.
"""

import pandas as pd
import pandas_ta_classic as ta


def add_indicators(df: pd.DataFrame, supertrend_period: int = 10, supertrend_multiplier: float = 3.0,
                    rsi_period: int = 14) -> pd.DataFrame:
    """
    Takes a DataFrame with columns: date, open, high, low, close, volume
    (as returned by kite.historical_data), and adds:
        - supertrend: the Supertrend line value
        - supertrend_direction: 1 (uptrend, price above line) or -1 (downtrend)
        - rsi: RSI value

    Returns a new DataFrame with these columns added. Requires at least
    ~max(supertrend_period, rsi_period) + a buffer of prior candles to
    produce non-NaN values for the earliest rows.
    """
    df = df.copy()
    df = df.sort_values("date").reset_index(drop=True)

    supertrend_df = ta.supertrend(
        high=df["high"], low=df["low"], close=df["close"],
        length=supertrend_period, multiplier=supertrend_multiplier,
    )
    # Column naming (e.g. SUPERT_10_3.0 vs SUPERT_10_3) can vary slightly
    # between library versions, so find them by prefix instead of exact match.
    st_col = next(c for c in supertrend_df.columns if c.startswith("SUPERT_"))
    std_col = next(c for c in supertrend_df.columns if c.startswith("SUPERTd_"))

    df["supertrend"] = supertrend_df[st_col]
    df["supertrend_direction"] = supertrend_df[std_col]

    df["rsi"] = ta.rsi(df["close"], length=rsi_period)

    return df

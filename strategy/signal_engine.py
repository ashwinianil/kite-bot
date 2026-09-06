"""
Entry/exit signal engine for the bull put credit spread strategy.

Implements the state machine as defined:
  - No open position, not armed:
        RSI closes above entry_rsi_threshold (60) -> ARM, record x = that RSI value
  - Armed, no open position:
        RSI closes below entry_rsi_threshold (60) before triggering -> reset (never armed)
        RSI closes above x AND Supertrend direction is up (+1)     -> ENTER
  - In position:
        RSI closes below exit_rsi_threshold (40)  -> EXIT (reason: rsi_below_40)
        Supertrend direction flips down (-1)      -> EXIT (reason: supertrend_flip)

This engine only concerns itself with underlying price/indicator signals.
Stop-loss (50% of max spread loss) and the 1-day-before-expiry forced close
are position-management concerns handled by the paper trading / live
execution layer, not here — this engine has no visibility into the actual
option spread's P&L or the expiry calendar.

Works for any underlying (Nifty, BankNifty, etc.) — just feed it that
underlying's RSI + Supertrend direction series. Each underlying should get
its OWN SignalEngine instance, since "one position at a time" applies
per-underlying, not globally.
"""

import pandas as pd


class SignalEngine:
    def __init__(self, entry_rsi_threshold: float = 60, exit_rsi_threshold: float = 40):
        self.entry_rsi_threshold = entry_rsi_threshold
        self.exit_rsi_threshold = exit_rsi_threshold
        self.reset()

    def reset(self):
        """Fully clears state — no armed setup, no open position."""
        self.armed = False
        self.x = None
        self.in_position = False
        self.last_exit_reason = None

    def process_candle(self, rsi, supertrend_direction):
        """
        Feed one candle's RSI and Supertrend direction (+1 uptrend / -1
        downtrend) into the engine. Returns one of:
            'ENTER'  — open a new position now
            'EXIT'   — close the open position now (check .last_exit_reason
                       for 'rsi_below_40' or 'supertrend_flip')
            None     — no action this candle

        Call this once per new candle, in chronological order, per
        underlying — the engine is stateful across calls.
        """
        if pd.isna(rsi) or pd.isna(supertrend_direction):
            # Indicators not yet warmed up (early candles) — skip, no state change.
            return None

        if self.in_position:
            if rsi < self.exit_rsi_threshold:
                self.last_exit_reason = "rsi_below_40"
                self._close_position()
                return "EXIT"
            if supertrend_direction == -1:
                self.last_exit_reason = "supertrend_flip"
                self._close_position()
                return "EXIT"
            return None

        if not self.armed:
            if rsi > self.entry_rsi_threshold:
                self.armed = True
                self.x = rsi
            return None

        # Armed, waiting for a later close above x (with Supertrend confirming uptrend)
        if rsi < self.entry_rsi_threshold:
            # Lost momentum before ever triggering — reset and wait for a fresh setup
            self.armed = False
            self.x = None
            return None

        if rsi > self.x and supertrend_direction == 1:
            self.in_position = True
            return "ENTER"

        return None

    def _close_position(self):
        self.in_position = False
        self.armed = False
        self.x = None


def generate_signals(df: pd.DataFrame, entry_rsi_threshold: float = 60,
                      exit_rsi_threshold: float = 40) -> pd.DataFrame:
    """
    Runs a fresh SignalEngine over an entire historical DataFrame (as loaded
    from one of our data/csv/<SYMBOL>.csv files) and returns a copy with two
    new columns:
        signal       — 'ENTER', 'EXIT', or None per row
        exit_reason  — 'rsi_below_40' / 'supertrend_flip' on EXIT rows, else None

    Expects columns: rsi, supertrend_direction (sorted chronologically —
    use the same DataFrame shape produced by strategy/indicators.py).
    """
    engine = SignalEngine(entry_rsi_threshold, exit_rsi_threshold)
    df = df.sort_values("date").reset_index(drop=True).copy()

    signals = []
    reasons = []
    for _, row in df.iterrows():
        signal = engine.process_candle(row["rsi"], row["supertrend_direction"])
        signals.append(signal)
        reasons.append(engine.last_exit_reason if signal == "EXIT" else None)

    df["signal"] = signals
    df["exit_reason"] = reasons
    return df

"""
Paper trading runner for the Nifty bull put credit spread strategy.

Single underlying (Nifty) for now — BankNifty support can be added later
by generalizing this into a loop, once this is validated.

Logic per run:
    1. Load Nifty's historical hourly data, run the signal engine over the
       full history to get the CURRENT state (armed/in-position/flat) as of
       the latest candle. Recomputed fresh each run — not persisted — so
       this is self-healing if a run is ever missed.
    2. If we have an open paper position:
        - Check exit conditions in priority order: expiry force-close,
          then signal-based exit, then stop-loss.
        - Close (log the trade) if any of them fire.
    3. If we're flat and the signal engine says ENTER on the latest candle:
        - Open a new paper position (live quotes, delta-based strike
          selection, no real order placed).

Safe to run repeatedly (e.g. every 15 min via the scheduler) — a run with
nothing to do just prints status and exits.

Requires: a valid Kite access token for today (run scripts/login.py first).

Run:
    python scripts/paper_trade.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.kite_client import get_kite
from strategy.signal_engine import generate_signals
from strategy.paper_trading import (
    get_position, open_paper_position, close_paper_position,
    check_stop_loss, check_expiry_force_close,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UNDERLYING = "NIFTY_50"        # our data/csv/ filename for the Nifty index
OPTIONS_NAME = "NIFTY"         # Kite's NFO instrument "name" field for Nifty options
INDEX_CSV = PROJECT_ROOT / "data" / "csv" / f"{UNDERLYING}.csv"


def get_latest_signal():
    """Runs the signal engine over Nifty's full historical data, returns
    (latest_signal, latest_spot, latest_date) from the most recent candle."""
    if not INDEX_CSV.exists():
        return None, None, None

    df = pd.read_csv(INDEX_CSV, parse_dates=["date"])
    if df.empty:
        return None, None, None

    result = generate_signals(df)
    last_row = result.iloc[-1]
    return last_row["signal"], last_row["close"], last_row["date"]


def main():
    print(f"=== Nifty paper trading check ===")

    latest_signal, spot, candle_date = get_latest_signal()
    if spot is None:
        print(f"No data found in {INDEX_CSV} — run update_data.py first.")
        return

    print(f"Latest candle: {candle_date} | spot: {spot:.2f} | signal engine says: {latest_signal or 'no action'}")

    kite = get_kite()
    position = get_position(UNDERLYING)

    if position:
        print(f"Currently holding: sold {position['short_strike']}PE / bought {position['hedge_strike']}PE, "
              f"entry credit {position['entry_credit']:.2f}, expiry {position['expiry']}")

        if check_expiry_force_close(position):
            close_paper_position(kite, position, "expiry_force_close")
        elif latest_signal == "EXIT":
            close_paper_position(kite, position, "signal_exit")
        elif check_stop_loss(kite, position):
            close_paper_position(kite, position, "stop_loss")
        else:
            print("  No exit condition met — holding.")

    else:
        print("No open position.")
        if latest_signal == "ENTER":
            open_paper_position(kite, UNDERLYING, OPTIONS_NAME, spot)
        else:
            print("  Signal engine did not fire ENTER — nothing to do.")

    print("Done.")


if __name__ == "__main__":
    main()

"""
Fetches the latest hourly candles for the Nifty 50 index + all constituent
stocks, computes Supertrend + RSI, and appends any NEW candles to each
symbol's CSV file under data/csv/.

Safe to run repeatedly (e.g. every hour during market hours) — it only
appends candles that aren't already in the CSV, so re-running never
creates duplicates.

Prerequisites:
    - config/instrument_tokens.csv must exist (run get_instrument_tokens.py
      once first, and again whenever nifty50_constituents.csv changes).
    - A valid access token (run scripts/login.py if it's a new trading day).

Run:
    python scripts/update_data.py
"""

import sys
import csv
import time
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.kite_client import get_kite
from strategy.indicators import add_indicators

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOKENS_FILE = PROJECT_ROOT / "config" / "instrument_tokens.csv"
CSV_DIR = PROJECT_ROOT / "data" / "csv"

INTERVAL = "60minute"

# How far back to pull on a fresh (empty) CSV — enough history for the
# indicators to have valid (non-NaN) values from early on.
INITIAL_LOOKBACK_DAYS = 60

# Kite rate limit is ~3 requests/second; this keeps us safely under that
# across historical_data calls for ~51 symbols.
SECONDS_BETWEEN_CALLS = 0.4


def load_instruments():
    if not TOKENS_FILE.exists():
        raise FileNotFoundError(
            f"{TOKENS_FILE} not found. Run scripts/get_instrument_tokens.py first."
        )
    instruments = []
    with open(TOKENS_FILE) as f:
        reader = csv.DictReader(f)
        for row in reader:
            instruments.append(row)
    return instruments


def csv_path_for(symbol: str) -> Path:
    # Sanitize symbol for filesystem (Kite's index symbol has a space: "NIFTY 50")
    safe_name = symbol.replace(" ", "_")
    return CSV_DIR / f"{safe_name}.csv"


def get_last_timestamp(path: Path):
    """Returns the last datetime present in an existing CSV, or None if the file doesn't exist / is empty."""
    if not path.exists():
        return None
    try:
        existing = pd.read_csv(path, parse_dates=["date"])
    except (pd.errors.EmptyDataError, ValueError):
        return None
    if existing.empty:
        return None
    return existing["date"].max()


def fetch_and_update(kite, symbol: str, instrument_token: int):
    path = csv_path_for(symbol)
    last_ts = get_last_timestamp(path)

    to_date = datetime.now()
    if last_ts is not None:
        # Start just after the last candle we already have
        from_date = last_ts + timedelta(minutes=1)
    else:
        from_date = to_date - timedelta(days=INITIAL_LOOKBACK_DAYS)

    if from_date >= to_date:
        print(f"  {symbol}: already up to date.")
        return

    try:
        candles = kite.historical_data(
            instrument_token=int(instrument_token),
            from_date=from_date,
            to_date=to_date,
            interval=INTERVAL,
        )
    except Exception as e:
        print(f"  {symbol}: FAILED to fetch — {e}")
        return

    if not candles:
        print(f"  {symbol}: no new candles.")
        return

    new_df = pd.DataFrame(candles)
    new_df["date"] = pd.to_datetime(new_df["date"]).dt.tz_localize(None)

    if last_ts is not None:
        # Need enough trailing history for indicators to compute correctly on
        # the new rows, so re-read existing data, recompute on the combined
        # set, then keep only the genuinely new rows for appending.
        existing = pd.read_csv(path, parse_dates=["date"])
        raw_existing = existing[["date", "open", "high", "low", "close", "volume"]]
        combined_raw = pd.concat([raw_existing, new_df], ignore_index=True)
        combined_raw = combined_raw.drop_duplicates(subset="date").sort_values("date")

        combined_with_indicators = add_indicators(combined_raw)
        new_rows = combined_with_indicators[combined_with_indicators["date"] > last_ts]

        if new_rows.empty:
            print(f"  {symbol}: no new candles.")
            return

        new_rows.to_csv(path, mode="a", header=False, index=False)
        print(f"  {symbol}: appended {len(new_rows)} new candle(s).")
    else:
        # Fresh file — compute indicators on the full initial batch and write from scratch
        with_indicators = add_indicators(new_df)
        CSV_DIR.mkdir(parents=True, exist_ok=True)
        with_indicators.to_csv(path, index=False)
        print(f"  {symbol}: created with {len(with_indicators)} candle(s).")


def main():
    instruments = load_instruments()
    print(f"Updating data for {len(instruments)} instruments...\n")

    kite = get_kite()

    for inst in instruments:
        fetch_and_update(kite, inst["tradingsymbol"], inst["instrument_token"])
        time.sleep(SECONDS_BETWEEN_CALLS)

    print("\nDone.")


if __name__ == "__main__":
    main()

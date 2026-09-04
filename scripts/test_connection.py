"""
Quick sanity check: confirms auth is working and prints your profile,
margins, and a sample historical data fetch (Nifty 50 index, last 5 days).

Run this after login.py, any time you want to confirm the bot can talk to Kite.

Run:
    python scripts/test_connection.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.kite_client import get_kite


def main():
    kite = get_kite()

    profile = kite.profile()
    print(f"Logged in as: {profile['user_name']} ({profile['user_id']})")

    margins = kite.margins()
    available = margins["equity"]["available"]["live_balance"]
    print(f"Available equity margin: ₹{available}")

    # NIFTY 50 index instrument token (constant, well-known)
    nifty_token = 256265

    to_date = datetime.now()
    from_date = to_date - timedelta(days=5)

    candles = kite.historical_data(
        instrument_token=nifty_token,
        from_date=from_date,
        to_date=to_date,
        interval="60minute",
    )

    print(f"\nFetched {len(candles)} hourly candles for NIFTY 50 index.")
    if candles:
        last = candles[-1]
        print(f"Most recent candle: {last['date']} | Close: {last['close']}")

    print("\nAll checks passed — auth, margins, and historical data all working.")


if __name__ == "__main__":
    main()

"""
Collects hourly snapshots of option prices (+ computed IV/delta) for BOTH
puts and calls, for the current month's expiry, within ~15% of spot on
each side (puts below spot, calls above spot — the OTM zone on each side).

Why this exists: we can't get historical option prices retroactively, so
this collects them PROSPECTIVELY, hour by hour, specifically so that in a
few months there's real historical option data to backtest against —
rather than the paper trading engine only ever being able to simulate
forward from "right now" using live quotes.

Safe to re-run repeatedly (e.g. every hour, alongside update_data.py) —
appends one row per strike per run, never duplicates (dedupes by
(date, strike, option_type)).

Run:
    python scripts/update_options_data.py
"""

import sys
import time
from pathlib import Path
from datetime import datetime, date

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.kite_client import get_kite
from strategy.options_pricing import implied_volatility, delta as delta_fn
from strategy.options_chain import pick_current_expiry, days_to_expiry

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OPTIONS_CSV_DIR = PROJECT_ROOT / "data" / "options_csv"

# Underlying index CSV (for live spot price) -> options "name" field in
# Kite's NFO instrument dump (NOT the index tradingsymbol — options use a
# different name convention, e.g. index is "NIFTY 50" but options are "NIFTY").
UNDERLYINGS = {
    "NIFTY_50": "NIFTY",
    "NIFTY_BANK": "BANKNIFTY",
}

STRIKE_WINDOW_PCT = 0.15  # window on each side of spot
FORCE_CLOSE_DAYS_BEFORE_EXPIRY = 1  # matches strategy/paper_trading.py

CSV_FIELDS = ["date", "option_type", "strike", "ltp", "implied_vol", "delta"]


def get_latest_spot(index_csv_symbol: str):
    path = PROJECT_ROOT / "data" / "csv" / f"{index_csv_symbol}.csv"
    if not path.exists():
        return None, None
    df = pd.read_csv(path, parse_dates=["date"])
    if df.empty:
        return None, None
    last_row = df.iloc[-1]
    return last_row["close"], last_row["date"]


def get_option_instruments(kite, options_name: str):
    all_nfo = kite.instruments("NFO")
    return [inst for inst in all_nfo if inst.get("name") == options_name]


def get_existing_snapshot_keys(path: Path):
    """Returns the set of (date_str, option_type, strike) already recorded, to avoid duplicate rows."""
    if not path.exists():
        return set()
    try:
        existing = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return set()
    if existing.empty:
        return set()
    return set(zip(existing["date"].astype(str), existing["option_type"], existing["strike"]))


def collect_for_underlying(kite, index_csv_symbol: str, options_name: str):
    print(f"\n{index_csv_symbol} ({options_name}):")

    spot, spot_date = get_latest_spot(index_csv_symbol)
    if spot is None:
        print(f"  No index data found for {index_csv_symbol} — run update_data.py first.")
        return

    today = date.today()

    option_instruments = get_option_instruments(kite, options_name)
    if not option_instruments:
        print(f"  No option instruments found for '{options_name}'.")
        return

    available_expiries = sorted({inst["expiry"] for inst in option_instruments if inst.get("expiry")})
    expiry = pick_current_expiry(available_expiries, today, FORCE_CLOSE_DAYS_BEFORE_EXPIRY)
    if expiry is None:
        print(f"  No suitable expiry found.")
        return

    dte = days_to_expiry(expiry, today)

    # Puts: strikes below spot (OTM puts). Calls: strikes above spot (OTM calls).
    put_low = spot * (1 - STRIKE_WINDOW_PCT)
    call_high = spot * (1 + STRIKE_WINDOW_PCT)

    candidates = [
        inst for inst in option_instruments
        if inst.get("expiry") == expiry
        and (
            (inst.get("instrument_type") == "PE" and put_low <= inst.get("strike", 0) < spot)
            or (inst.get("instrument_type") == "CE" and spot < inst.get("strike", 0) <= call_high)
        )
    ]
    if not candidates:
        print(f"  No candidate strikes found in window (spot={spot}, expiry={expiry}).")
        return

    csv_path = OPTIONS_CSV_DIR / f"{index_csv_symbol}_{expiry.isoformat()}.csv"
    already_recorded = get_existing_snapshot_keys(csv_path)

    now_str = datetime.now().replace(microsecond=0).isoformat()

    keys = [f"{inst['exchange']}:{inst['tradingsymbol']}" for inst in candidates]
    try:
        quotes = kite.quote(keys)
    except Exception as e:
        print(f"  FAILED to fetch quotes: {e}")
        return

    rows = []
    for inst in candidates:
        key = f"{inst['exchange']}:{inst['tradingsymbol']}"
        quote = quotes.get(key)
        if not quote or quote.get("last_price", 0) <= 0:
            continue

        strike = inst["strike"]
        option_type = "put" if inst["instrument_type"] == "PE" else "call"

        if (now_str, option_type, strike) in already_recorded:
            continue  # already have this exact snapshot (re-running within same run window)

        ltp = quote["last_price"]
        iv = None
        delta_val = None
        try:
            iv = implied_volatility(ltp, spot, strike, dte, option_type)
            if iv is not None:
                delta_val = delta_fn(spot, strike, dte, iv, option_type)
        except Exception:
            pass  # leave iv/delta as None if calculation fails for this strike

        rows.append({
            "date": now_str,
            "option_type": option_type,
            "strike": strike,
            "ltp": ltp,
            "implied_vol": iv,
            "delta": delta_val,
        })

    if not rows:
        print(f"  No new snapshot rows to add (already recorded, or no live quotes).")
        return

    OPTIONS_CSV_DIR.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    new_df = pd.DataFrame(rows)
    new_df.to_csv(csv_path, mode="a", header=not file_exists, index=False)

    n_puts = sum(1 for r in rows if r["option_type"] == "put")
    n_calls = sum(1 for r in rows if r["option_type"] == "call")
    print(f"  Saved {len(rows)} snapshot(s) ({n_puts} puts, {n_calls} calls) to "
          f"{csv_path.relative_to(PROJECT_ROOT)} (expiry {expiry}, {dte} days out, spot {spot:.2f})")


def main():
    kite = get_kite()
    for index_csv_symbol, options_name in UNDERLYINGS.items():
        collect_for_underlying(kite, index_csv_symbol, options_name)
        time.sleep(0.4)  # stay well under Kite's rate limit

    print("\nDone.")


if __name__ == "__main__":
    main()

"""
Resolves Nifty 50 constituent symbols (from config/nifty50_constituents.csv)
into Kite instrument tokens, and caches the result.

Kite's historical_data API needs a numeric `instrument_token`, not just the
symbol name — this script builds that mapping once, using Kite's own
instrument dump (kite.instruments()), so it always matches whatever Kite
currently has listed (correct even through symbol renames, etc).

Also adds the NIFTY 50 index itself (fixed instrument token, since indices
aren't "tradable" instruments and don't appear the same way in the dump).

Run:
    python scripts/get_instrument_tokens.py

Output:
    config/instrument_tokens.csv  (tradingsymbol, instrument_token, exchange)
"""

import sys
import csv
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.kite_client import get_kite

CONSTITUENTS_FILE = Path(__file__).resolve().parent.parent / "config" / "nifty50_constituents.csv"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "config" / "instrument_tokens.csv"

# NIFTY 50 index — fixed, well-known instrument token on Kite (NSE INDICES segment)
NIFTY50_INDEX = {
    "tradingsymbol": "NIFTY 50",
    "instrument_token": 256265,
    "exchange": "NSE_INDICES",
}


def load_constituents():
    if not CONSTITUENTS_FILE.exists():
        raise FileNotFoundError(f"{CONSTITUENTS_FILE} not found.")

    symbols = []
    with open(CONSTITUENTS_FILE) as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row.get("tradingsymbol", "").strip()
            if symbol:
                symbols.append(symbol)

    if not symbols:
        print(f"\nWARNING: {CONSTITUENTS_FILE} has no symbols listed yet.")
        print("Open config/README_nifty50_constituents.md for instructions on filling it in.")
    return symbols


def main():
    symbols = load_constituents()
    if not symbols:
        return

    print(f"Loaded {len(symbols)} symbols from {CONSTITUENTS_FILE.name}")

    kite = get_kite()
    print("Fetching full NSE instrument dump from Kite (this can take a few seconds)...")
    all_instruments = kite.instruments("NSE")

    # Build a lookup: tradingsymbol -> instrument_token
    lookup = {inst["tradingsymbol"]: inst["instrument_token"] for inst in all_instruments}

    resolved = [NIFTY50_INDEX]
    missing = []

    for symbol in symbols:
        token = lookup.get(symbol)
        if token:
            resolved.append({
                "tradingsymbol": symbol,
                "instrument_token": token,
                "exchange": "NSE",
            })
        else:
            missing.append(symbol)

    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["tradingsymbol", "instrument_token", "exchange"])
        writer.writeheader()
        writer.writerows(resolved)

    print(f"\nResolved {len(resolved)} instruments (including NIFTY 50 index).")
    print(f"Saved to {OUTPUT_FILE}")

    if missing:
        print(f"\nCould NOT find instrument tokens for {len(missing)} symbol(s):")
        for m in missing:
            print(f"  - {m}")
        print("Double-check these match Kite's exact tradingsymbol spelling.")


if __name__ == "__main__":
    main()

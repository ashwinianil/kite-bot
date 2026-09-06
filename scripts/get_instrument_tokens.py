"""
Resolves Nifty 50 constituent symbols (from config/nifty50_constituents.csv)
plus the NIFTY 50 and NIFTY BANK indices into Kite instrument tokens, and
caches the result.

Kite's historical_data API needs a numeric `instrument_token`, not just the
symbol name — this script builds that mapping once, using Kite's own
instrument dump, so it always matches whatever Kite currently has listed.

Index tokens (NIFTY 50, NIFTY BANK) are looked up dynamically from Kite's
own instrument dump rather than hardcoded — instrument tokens are Kite-
internal identifiers, not something to guess from memory. A hardcoded
fallback exists ONLY as a last resort if the dynamic lookup fails, and it
prints a clear warning if that fallback is used, so it's never silently
trusted for a live trading tool.

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

# Indices we track alongside the Nifty 50 constituent stocks.
INDEX_SYMBOLS = ["NIFTY 50", "NIFTY BANK"]

# Last-resort fallback ONLY — used if the dynamic lookup below can't find
# these in Kite's instrument dump. Printed loudly if ever used, since a
# stale/wrong hardcoded token would silently corrupt every trade decision.
FALLBACK_INDEX_TOKENS = {
    "NIFTY 50": 256265,
    "NIFTY BANK": 260105,
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


def resolve_indices(all_instruments_all_exchanges):
    """
    Looks up NIFTY 50 / NIFTY BANK index instrument tokens dynamically from
    Kite's dump (segment == INDICES). Falls back to a hardcoded token only
    if the dynamic lookup fails, with a loud warning either way it's used.
    """
    index_lookup = {
        inst["tradingsymbol"]: inst
        for inst in all_instruments_all_exchanges
        if inst.get("segment") == "INDICES"
    }

    resolved = []
    for symbol in INDEX_SYMBOLS:
        inst = index_lookup.get(symbol)
        if inst:
            resolved.append({
                "tradingsymbol": symbol,
                "instrument_token": inst["instrument_token"],
                "exchange": "NSE_INDICES",
            })
        else:
            fallback_token = FALLBACK_INDEX_TOKENS.get(symbol)
            print(f"\nWARNING: Could not find '{symbol}' dynamically in Kite's instrument dump.")
            if fallback_token:
                print(f"  Using hardcoded fallback token {fallback_token} — VERIFY this is still "
                      f"correct before trusting live trades on it (e.g. cross-check against "
                      f"Kite's docs or support).")
                resolved.append({
                    "tradingsymbol": symbol,
                    "instrument_token": fallback_token,
                    "exchange": "NSE_INDICES",
                })
            else:
                print(f"  No fallback available either — '{symbol}' will be MISSING from the output.")

    return resolved


def main():
    symbols = load_constituents()
    if not symbols:
        return

    print(f"Loaded {len(symbols)} symbols from {CONSTITUENTS_FILE.name}")

    kite = get_kite()

    print("Fetching full NSE instrument dump from Kite (this can take a few seconds)...")
    nse_instruments = kite.instruments("NSE")

    print("Fetching full instrument dump across all exchanges (for index lookup)...")
    all_instruments = kite.instruments()

    resolved = resolve_indices(all_instruments)

    # Build a lookup: tradingsymbol -> instrument_token (equities, NSE only)
    lookup = {inst["tradingsymbol"]: inst["instrument_token"] for inst in nse_instruments}

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

    print(f"\nResolved {len(resolved)} instruments (including NIFTY 50 and NIFTY BANK indices).")
    print(f"Saved to {OUTPUT_FILE}")

    if missing:
        print(f"\nCould NOT find instrument tokens for {len(missing)} stock symbol(s):")
        for m in missing:
            print(f"  - {m}")
        print("Double-check these match Kite's exact tradingsymbol spelling.")


if __name__ == "__main__":
    main()

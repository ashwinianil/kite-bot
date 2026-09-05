"""
Fetches the official, current Nifty 50 constituent list directly from NSE
and writes it to config/nifty50_constituents.csv.

Why this exists as a separate script (not hardcoded in Python): Nifty 50
constituents are rebalanced twice a year (last trading day of March and
September). Re-running this script after each rebalance keeps the list
accurate without you having to manually track down and retype the new list.

NSE's site blocks requests that don't look like a real browser, so this
script sends a browser-like User-Agent and first hits the homepage to
pick up required session cookies before requesting the actual CSV.

Run:
    python scripts/fetch_nifty50_list.py

Run this:
    - Once now, to populate the list for the first time.
    - Again every March/September after NSE announces a rebalance.
"""

import csv
import sys
from pathlib import Path

import requests

OUTPUT_FILE = Path(__file__).resolve().parent.parent / "config" / "nifty50_constituents.csv"

NSE_HOMEPAGE = "https://www.nseindia.com"
NSE_CSV_URL = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/csv,application/csv,*/*",
}


def fetch_symbols():
    session = requests.Session()
    session.headers.update(HEADERS)

    # NSE requires a session cookie from the homepage before it'll serve
    # the CSV — hitting the CSV URL directly (without this) usually 403s.
    print("Establishing session with nseindia.com...")
    session.get(NSE_HOMEPAGE, timeout=10)

    print(f"Fetching {NSE_CSV_URL} ...")
    response = session.get(NSE_CSV_URL, timeout=10)
    response.raise_for_status()

    lines = response.text.splitlines()
    reader = csv.DictReader(lines)

    symbols = []
    for row in reader:
        symbol = row.get("Symbol", "").strip()
        if symbol:
            symbols.append(symbol)

    return symbols


def main():
    try:
        symbols = fetch_symbols()
    except requests.exceptions.RequestException as e:
        print(f"\nFAILED to fetch from NSE: {e}")
        print(
            "\nThis can happen if NSE is blocking automated requests from this "
            "network/IP, or their site structure changed. If it keeps failing, "
            "fall back to the manual method: see config/README_nifty50_constituents.md"
        )
        sys.exit(1)

    if len(symbols) != 50:
        print(f"\nWARNING: expected 50 symbols, got {len(symbols)}. "
              "NSE's CSV format may have changed — double check before trusting this list.")

    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["tradingsymbol"])
        for symbol in symbols:
            writer.writerow([symbol])

    print(f"\nSaved {len(symbols)} symbols to {OUTPUT_FILE}")
    print("Next: run scripts/get_instrument_tokens.py to resolve these into Kite instrument tokens.")


if __name__ == "__main__":
    main()

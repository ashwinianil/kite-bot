# Nifty 50 Constituents — Setup Note

`nifty50_constituents.csv` in this folder is the **single source of truth**
for which 50 stocks the data pipeline tracks. It's intentionally left for
you to populate rather than hardcoded, because:

- Nifty 50 constituents are rebalanced **twice a year** (March & September) —
  a hardcoded list in Python would silently go stale.
- Getting even one symbol wrong in a trading tool has real consequences, so
  this should come from an official source you control, not guessed.

## How to fill it in

1. Get the current official list from:
   - https://www.nseindia.com/products-services/indices-nifty50-index, or
   - https://niftyindices.com/indices/equity/broad-based-indices/nifty-50
2. Add one symbol per line under the `tradingsymbol` header, exactly matching
   Kite's `tradingsymbol` field (this is normally identical to the NSE symbol,
   e.g. `RELIANCE`, `TCS`, `HDFCBANK`, `BAJFINANCE`).
3. Save the file. `scripts/get_instrument_tokens.py` reads this list and
   resolves each symbol to its Kite instrument token automatically.

## Reminder

Re-check this list every March and September (or whenever NSE announces an
index change) and update the CSV accordingly.

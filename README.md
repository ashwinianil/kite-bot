# Kite Trading Bot — Bull Put Credit Spread (Nifty)

## Setup

1. Create a venv with **Python 3.11** specifically (see `AGENTS.md` for why):
   ```
   python3.11 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create your `.env` file:
   ```
   cp .env.example .env
   ```
   Then fill in `KITE_API_KEY` and `KITE_API_SECRET` from developers.kite.trade
   (your "takeaswing" app).

4. Log in (must be done once every trading day — tokens expire daily):
   ```
   python scripts/login.py
   ```
   This opens a login flow, exchanges the request_token for an access_token,
   and saves it into `.env`.

5. Verify the connection:
   ```
   python scripts/test_connection.py
   ```
   This confirms auth works and pulls your margin + a sample of Nifty hourly data.

## Data pipeline (hourly candles + Supertrend + RSI)

6. Fetch the current Nifty 50 constituent list from NSE:
   ```
   python scripts/fetch_nifty50_list.py
   ```
   Run this once now, and again every March/September after NSE announces
   the semi-annual index rebalance. Falls back to a manual method
   (see `config/README_nifty50_constituents.md`) if NSE blocks the request.

7. Resolve those symbols into Kite instrument tokens:
   ```
   python scripts/get_instrument_tokens.py
   ```
   Re-run this any time step 6 changes the symbol list.

8. Fetch/update hourly candle data + Supertrend + RSI for all 51 instruments
   (Nifty 50 index + 50 stocks):
   ```
   python scripts/update_data.py
   ```
   Safe to re-run anytime (e.g. hourly during market hours) — only appends
   genuinely new candles, never duplicates. Data is saved to `data/csv/`
   (one file per symbol) — this is the source of truth for strategy code.

9. Generate Excel workbooks for human viewing (not the data source itself):
   ```
   python scripts/export_to_excel.py
   ```
   Creates one workbook per month under `data/excel/<year>/<year>-<month>.xlsx`,
   with one sheet per symbol.

## Project structure

```
config/         Shared client setup, Nifty 50 constituent list, instrument tokens
scripts/        Standalone scripts: login, connection test, data pipeline
strategy/       Strategy logic — indicators.py done, entry/exit rules TBD
data/csv/       Source-of-truth hourly candle + indicator data (one CSV per symbol)
data/excel/     Generated Excel workbooks for reference/viewing only
logs/           Trade logs, error logs
.env            Your actual credentials (never commit this)
.env.example    Template for .env
```

## Status

- [x] Project skeleton
- [x] Auth flow (daily login script)
- [x] Data pipeline: Nifty 50 list, instrument tokens, hourly candles + Supertrend/RSI, Excel export
- [ ] Entry/exit trigger rules — still being defined
- [ ] Strike selection + expiry logic
- [ ] Order execution (multi-leg spread)
- [ ] Margin/risk checks
- [ ] Logging & alerts
- [ ] Deployment (VPS/cloud, market-hours uptime)

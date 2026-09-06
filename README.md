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

Two wrapper scripts run the whole pipeline in one command each — use these
day-to-day instead of running the individual scripts below by hand.

**One-time setup, and again every March/September** (Nifty rebalance months):
```
./scripts/refresh_constituents.sh
```
Fetches the current Nifty 50 list from NSE and resolves it to Kite instrument
tokens. Falls back to a manual method (see
`config/README_nifty50_constituents.md`) if NSE blocks the request.

**Routine update** (run anytime, e.g. hourly during market hours 9:15am–3:30pm IST):
```
./scripts/update_hourly.sh
```
Pulls the latest hourly candles + Supertrend/RSI for all 51 instruments, then
refreshes the Excel reference workbooks. Requires a valid access token for
today (`python scripts/login.py` first if you haven't logged in yet today).

<details>
<summary>What each wrapper runs, if you want to run steps individually</summary>

`refresh_constituents.sh` runs, in order:
6. Fetch the current Nifty 50 constituent list from NSE:
   ```
   python scripts/update_nifty50_list_march_sept.py
   ```
7. Resolve those symbols into Kite instrument tokens:
   ```
   python scripts/get_instrument_tokens.py
   ```
8. Archive data for any symbol that's dropped out of the index (moves the
   CSV to `data/csv/archived/`, doesn't delete it — history is preserved,
   it just stops being updated):
   ```
   python scripts/cleanup_removed_constituents.py
   ```

`update_hourly.sh` runs, in order:
8. Fetch/update hourly candle data + Supertrend + RSI for all 51 instruments
   (Nifty 50 index + 50 stocks):
   ```
   python scripts/update_data.py
   ```
   Safe to re-run anytime — only appends genuinely new candles, never
   duplicates. Data is saved to `data/csv/` (one file per symbol) — this is
   the source of truth for strategy code.
9. Generate Excel workbooks for human viewing (not the data source itself):
   ```
   python scripts/export_to_excel.py
   ```
   Creates one workbook per month under `data/excel/<year>/<year>-<month>.xlsx`,
   with one sheet per symbol.
</details>

## Project structure

```
config/         Shared client setup, Nifty 50 constituent list, instrument tokens
scripts/        Standalone scripts + refresh_constituents.sh / update_hourly.sh wrappers
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

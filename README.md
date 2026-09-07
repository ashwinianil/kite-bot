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
Pulls the latest hourly candles + Supertrend/RSI for all 52 instruments, then
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
8. Fetch/update hourly candle data + Supertrend + RSI for all 52 instruments
   (Nifty 50 index + Nifty Bank index + 50 stocks):
   ```
   python scripts/update_data.py
   ```
   Safe to re-run anytime — only appends genuinely new candles, never
   duplicates. Data is saved to `data/csv/` (one file per symbol) — this is
   the source of truth for strategy code.
9. Collect options price snapshots for Nifty + BankNifty puts (current
   month expiry, strikes within ~15% below spot):
   ```
   python scripts/update_options_data.py
   ```
   Collected prospectively (hour by hour) since historical option prices
   can't be fetched retroactively — this builds up real historical option
   data over time for future backtesting. Saved to `data/options_csv/`,
   split by underlying + expiry. **Committed to git** (unlike other data/
   files) since it's irreplaceable if lost.
10. Generate Excel workbooks for human viewing (not the data source itself):
   ```
   python scripts/export_to_excel.py
   ```
   Creates one workbook per month under `data/excel/<year>/<year>-<month>.xlsx`,
   with one sheet per symbol.
</details>

## Automated scheduling (macOS)

Three **fully independent** scheduled jobs, not one combined script — a
failure or hiccup in any one (e.g. paper trading hitting a live Kite API
error) has zero effect on the others. This matters most for options data
collection, since a missed snapshot can't be recovered retroactively.

| Job | Runs | Log file |
|---|---|---|
| `com.kitebot.marketdata` | `update_data.py` + `export_to_excel.py` | `logs/market_data.log` |
| `com.kitebot.optionsdata` | `update_options_data.py` | `logs/options_data.log` |
| `com.kitebot.papertrade` | `paper_trade.py` | `logs/paper_trade.log` |

Each is gated by `scripts/run_if_market_open.sh` — a shared helper that
checks NSE market hours **in IST** (via `scripts/market_hours.py`,
timezone-safe regardless of what timezone your Mac itself is set to) and
only actually runs when the market is open; outside those hours it's a
cheap no-op.

**Setup — repeat for all three plists:**

1. Edit each of `scripts/com.kitebot.marketdata.plist`,
   `scripts/com.kitebot.optionsdata.plist`, and
   `scripts/com.kitebot.papertrade.plist`, replacing
   `REPLACE_WITH_FULL_PATH_TO_REPO` (appears 3 times in each file) with the
   actual full path to this repo on your machine (e.g.
   `/Users/ashwini/Downloads/repos/kite-bot`).

2. Copy all three into place and load them:
   ```
   cp scripts/com.kitebot.*.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.kitebot.marketdata.plist
   launchctl load ~/Library/LaunchAgents/com.kitebot.optionsdata.plist
   launchctl load ~/Library/LaunchAgents/com.kitebot.papertrade.plist
   ```
   Each runs its own script every 15 minutes, completely independently.

3. To stop one (or all):
   ```
   launchctl unload ~/Library/LaunchAgents/com.kitebot.marketdata.plist
   launchctl unload ~/Library/LaunchAgents/com.kitebot.optionsdata.plist
   launchctl unload ~/Library/LaunchAgents/com.kitebot.papertrade.plist
   ```

4. Check the log files listed in the table above if something doesn't seem
   to be updating — each job logs independently, so you can tell exactly
   which one (if any) is having trouble.

**Want to run everything manually once instead** (e.g. for testing)?
`./scripts/update_hourly.sh` still does that — it's kept as a convenience
for manual runs, but is NOT what the automated scheduling above uses.

**Two important limitations to know about:**
- **Daily login is still manual.** Kite access tokens expire every day and
  require a browser-based login (password + 2FA) — this can't be automated
  headlessly with the current setup. All three scheduled jobs will fail
  every run until you've run `python scripts/login.py` yourself that day.
- **Your Mac must be awake and online** during market hours for this to
  work — launchd doesn't wake a sleeping Mac by default. If you close the
  lid or it sleeps, updates during that window are simply missed (though
  harmlessly for market data/paper trading — the next successful run just
  picks up from where things left off; options data snapshots during that
  window, however, are genuinely lost, since they can't be fetched
  retroactively). For genuine 24/7 reliability regardless of your laptop's
  state, a cloud VPS is the real fix (still on the roadmap, see Status
  below) — this local setup is a reasonable way to get started now.

## Project structure

```
config/            Shared client setup, Nifty 50 constituent list, instrument tokens
scripts/           Standalone scripts + wrapper shell scripts (refresh_constituents.sh,
                    update_hourly.sh, scheduled_update.sh) + launchd plist
strategy/          Strategy logic: indicators, signal engine, options pricing/chain
data/csv/          Source-of-truth hourly candle + indicator data (one CSV per symbol)
data/csv/archived/ Data for stocks dropped from the Nifty 50 index (preserved, not deleted)
data/options_csv/  Hourly options price snapshots (puts + calls) — committed to git,
                    since this data is irreplaceable if lost (see AGENTS.md)
data/excel/        Generated Excel workbooks for reference/viewing only
logs/              Trade logs, scheduler logs, error logs
.env               Your actual credentials (never commit this)
.env.example       Template for .env
```

## Status

See `AGENTS.md` for the full, current status and strategy specification —
kept up to date there rather than duplicated here.


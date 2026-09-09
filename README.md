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

## Automated daily login (for unattended/remote setups, e.g. a VPS)

`scripts/login.py` needs a browser open on the same machine — fine on your
Mac, not possible on a headless remote server. `scripts/headless_login.py`
automates the whole flow instead: a headless browser fills in your
credentials + computes the current TOTP code itself (same algorithm your
phone's authenticator uses), captures the redirect, and saves the access
token — no human needed.

**Only set this up if you're deploying somewhere you can't open a browser**
(e.g. a VPS). If you're running everything on your own Mac, skip this
entirely and keep using `scripts/login.py` by hand each morning.

**Setup:**

1. Install Playwright's browser binary (one-time, needed on whatever
   machine runs this):
   ```
   playwright install chromium
   ```
   On a fresh Linux VPS, you may also need system libraries:
   ```
   playwright install-deps chromium
   ```

2. Fill in the extra `.env` fields (see `.env.example` for details on each):
   `KITE_USER_ID`, `KITE_PASSWORD`, `KITE_TOTP_SECRET` — that last one is
   the **permanent secret key**, not the 6-digit code that rotates every
   30 seconds. It's shown once during 2FA setup, or you can reset 2FA in
   Kite Console (Account > Security > 2FA) to get a fresh one.

3. **Security note, seriously:** these three fields are meaningfully more
   sensitive than the API key/secret alone — anyone with this `.env` file
   could fully log into your trading account. Only do this on a machine
   you fully control, with SSH-key-only access (no password login), and
   treat the file accordingly.

4. Test it first with the browser visible, so you can actually watch what
   happens and catch anything that doesn't match (the automation's
   selectors are based on Kite's commonly documented login flow, but
   weren't verified against the live site — Kite may have changed things):
   ```
   python scripts/headless_login.py --visible
   ```
   If a step fails, it saves a screenshot to `logs/headless_login_failure.png`
   showing exactly what the page looked like at that point — useful for
   figuring out what selector needs adjusting.

5. Once it works reliably, run it for real (headless, as it'll run via the
   scheduler):
   ```
   python scripts/headless_login.py
   ```

**Automated scheduling for this** runs during a pre-market window
(8:30–9:10am IST) rather than a fixed clock time — see
`scripts/market_hours.py`'s `is_premarket_login_window()` and the
`com.kitebot.dailylogin` job in the next section. It also skips re-running
the browser automation if a working token already exists (e.g. an earlier
attempt that morning already succeeded), so it won't hammer Zerodha's
login page repeatedly within the window.

## Automated scheduling (macOS)

Three **fully independent** scheduled jobs, not one combined script — a
failure or hiccup in any one (e.g. paper trading hitting a live Kite API
error) has zero effect on the others. This matters most for options data
collection, since a missed snapshot can't be recovered retroactively.

| Job | Runs | Log file |
|---|---|---|
| `com.kitebot.dailylogin` | `headless_login.py` (pre-market window only, optional — see above) | `logs/daily_login.log` |
| `com.kitebot.marketdata` | `update_data.py` + `export_to_excel.py` | `logs/market_data.log` |
| `com.kitebot.optionsdata` | `update_options_data.py` | `logs/options_data.log` |
| `com.kitebot.papertrade` | `paper_trade.py` | `logs/paper_trade.log` |

Each is gated by `scripts/run_if_market_open.sh` — a shared helper that
checks NSE market hours **in IST** (via `scripts/market_hours.py`,
timezone-safe regardless of what timezone your Mac itself is set to) and
only actually runs when the market is open; outside those hours it's a
cheap no-op.

**Setup — repeat for all three plists:**

1. Edit each plist file, replacing
   `REPLACE_WITH_FULL_PATH_TO_REPO` (appears 3 times in each file) with the
   actual full path to this repo on your machine (e.g.
   `/Users/ashwini/Downloads/repos/kite-bot`). Skip `com.kitebot.dailylogin.plist`
   if you're not using headless login (see previous section) — only load
   that one if you've set it up.

2. Copy them into place and load them:
   ```
   cp scripts/com.kitebot.*.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.kitebot.marketdata.plist
   launchctl load ~/Library/LaunchAgents/com.kitebot.optionsdata.plist
   launchctl load ~/Library/LaunchAgents/com.kitebot.papertrade.plist
   launchctl load ~/Library/LaunchAgents/com.kitebot.dailylogin.plist   # only if using headless login
   ```
   Each runs its own script independently — market data and options data
   every 15 minutes, paper trade checks every 15 minutes, daily login every
   5 minutes but only within its pre-market window.

3. To stop one (or all):
   ```
   launchctl unload ~/Library/LaunchAgents/com.kitebot.marketdata.plist
   launchctl unload ~/Library/LaunchAgents/com.kitebot.optionsdata.plist
   launchctl unload ~/Library/LaunchAgents/com.kitebot.papertrade.plist
   launchctl unload ~/Library/LaunchAgents/com.kitebot.dailylogin.plist
   ```

4. Check the log files listed in the table above if something doesn't seem
   to be updating — each job logs independently, so you can tell exactly
   which one (if any) is having trouble.

**Want to run everything manually once instead** (e.g. for testing)?
`./scripts/update_hourly.sh` still does that — it's kept as a convenience
for manual runs, but is NOT what the automated scheduling above uses.

**Two important limitations to know about:**
- **Daily login is manual by default**, unless you've set up
  `scripts/headless_login.py` + the `com.kitebot.dailylogin` job (see the
  "Automated daily login" section above) — that makes it fully automated,
  but requires storing your Zerodha password + TOTP secret, a real security
  tradeoff you should weigh deliberately, not something to set up casually.
  Without it, all scheduled jobs will fail every run until you've run
  `python scripts/login.py` yourself that day.
- **Your Mac must be awake and online** during market hours for this to
  work — launchd doesn't wake a sleeping Mac by default. If you close the
  lid or it sleeps, updates during that window are simply missed (though
  harmlessly for market data/paper trading — the next successful run just
  picks up from where things left off; options data snapshots during that
  window, however, are genuinely lost, since they can't be fetched
  retroactively). For genuine 24/7 reliability regardless of your laptop's
  state, a cloud VPS is the real fix — see the next section.

## Running on a Linux VM / VPS (for true 24/7 reliability)

A laptop that can sleep or lose power isn't ideal for something meant to
run continuously — a cheap Linux VPS (Oracle Cloud Free Tier, Vultr, etc.)
is the real fix. This project's scripts are already portable (plain
bash/Python, nothing macOS-specific), so the same logic runs on Linux —
just with `cron` instead of macOS's `launchd` for scheduling.

**Before deploying here:** verify `headless_login.py` actually works
using `--visible` mode on your Mac FIRST (see the previous section) — a
headless VM has no display, so you can't debug `--visible` mode there.
Only bring already-confirmed-working automation to the VM.

**Setup, on a fresh VM:**

1. Clone the repo:
   ```
   git clone https://github.com/ashwinianil/kite-bot.git
   cd kite-bot
   ```

2. Run the one-shot setup script:
   ```
   chmod +x scripts/setup_linux.sh
   ./scripts/setup_linux.sh
   ```
   This installs Python 3.11 (via the deadsnakes PPA if your distro's
   default repos don't have it), creates the venv, installs all Python
   dependencies + Playwright's Chromium browser (and its Linux system
   libraries, via `playwright install-deps`), creates `.env` from the
   template if missing, and installs the crontab (`scripts/crontab.txt`,
   with the repo path substituted in automatically).

   **If you already have other cron jobs on this machine**, the script
   detects that and asks for confirmation before overwriting your
   crontab — installing `scripts/crontab.txt` directly replaces your
   entire crontab, not just adds to it.

3. Fill in `.env` with your real credentials — same fields as
   `.env.example` describes, including the headless-login ones
   (`KITE_USER_ID`, `KITE_PASSWORD`, `KITE_TOTP_SECRET`) if you're using
   automated login here.

4. Test headless login once manually (no `--visible` — no display on this
   VM):
   ```
   python scripts/headless_login.py
   ```

5. Once that works, cron takes over automatically. Check `crontab -l` to
   confirm the jobs are installed, and watch the log files under `logs/`
   (`daily_login.log`, `market_data.log`, `options_data.log`,
   `paper_trade.log`) to confirm things are actually running.

## Project structure

```
config/            Shared client setup, Nifty 50 constituent list, instrument tokens
scripts/           Standalone scripts + wrapper shell scripts (refresh_constituents.sh,
                    update_hourly.sh) + launchd plists (macOS) + setup_linux.sh /
                    crontab.txt (Linux VM)
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


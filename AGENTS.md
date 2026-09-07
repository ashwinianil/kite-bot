# Agent notes for this repo

## Environment

- **Python version: 3.11** (specifically). The system default Python on this
  Mac is 3.14, which is too new — `pandas-ta-classic` and other deps don't
  install cleanly on it yet. Always use a venv built with `python3.11`.

- **Virtual environment**: create with `python3.11 -m venv venv`, activate
  with `source venv/bin/activate` before installing or running anything.

- Do NOT install dependencies system-wide. Homebrew's Python is
  externally-managed and will block `pip install` outside a venv anyway.

- SSL certificate errors on this Mac (corporate network) were fixed via
  `pip install pip-system-certs`, which makes Python use the system trust
  store instead of only certifi's public CA bundle.

## Setup (fresh clone)

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in KITE_API_KEY / KITE_API_SECRET
python scripts/login.py
python scripts/test_connection.py
```

## Notes

- `pandas_ta` (original package) is unmaintained and doesn't support
  Python 3.12+. We use `pandas-ta-classic` instead — same API, actively
  maintained, supports Python 3.10–3.14.
- Kite access tokens expire daily — `scripts/login.py` must be re-run each
  trading day before running anything that hits the live API.
- Instrument tokens (including NIFTY 50 / NIFTY BANK indices) are looked up
  dynamically from Kite's own instrument dump, never hardcoded from memory —
  see `scripts/get_instrument_tokens.py`. Same principle for the Nifty 50
  constituent list itself (`scripts/update_nifty50_list_march_sept.py` pulls
  it live from NSE) — these are financial facts that change over time and
  must come from a live source, not be guessed.

## Strategy: Nifty/BankNifty bull put credit spread

Full spec, as decided through discussion with the user:

**Scope:** Nifty index AND BankNifty index (added after initial Nifty-only
design). "One open position at a time" applies PER underlying — Nifty and
BankNifty can each have their own open position simultaneously.

**Entry logic** (implemented in `strategy/signal_engine.py`):
1. Only if no open position for that underlying.
2. On the hourly chart, when RSI closes above 60, record that RSI value as `x`.
3. On a later candle, when RSI closes above `x` again (not a retest of x —
   a fresh higher close than the original breakout print) AND Supertrend
   is below spot (uptrend) at that same candle → ENTER.
4. If RSI drops back below 60 before ever closing above `x`, the setup
   resets (armed state clears, waiting for a fresh RSI>60 close).

**Exit logic** (whichever hits first):
- RSI closes below 40, OR
- Supertrend flips down, OR
- Stop-loss: current loss reaches 50% of max possible loss on the spread, OR
- Forced close 1 trading day before expiry, regardless of signal.

**Position construction:**
- Sell a put at ~15–20 delta (target range, prefer in-range over closest-
  to-midpoint — see `strategy/options_chain.py::select_short_strike_by_delta`).
- Buy a put 200 points further OTM as the hedge (fixed width, not delta-based
  — this is standard practice, defines max loss predictably).
- 1 lot only, always (no dynamic position sizing).
- Monthly expiry (the latest expiry within the current calendar month is
  always the monthly one, whether or not weeklies are also listed).

**Why delta must be computed, not looked up:** Kite Connect doesn't provide
option Greeks directly. `strategy/options_pricing.py` implements Black-Scholes
pricing + an implied-volatility solver (bisection) to back out IV from the
option's live market price, then computes delta from that IV. Verified
against known reference values, put-call parity, and round-trip IV recovery.

**Ops decisions:**
- No alerts (Telegram/email) — logs checked manually for now.
- Paper trade first (simulate signals, log hypothetical trades, no real
  orders) before ever going live with real money. This is a hard requirement
  from the user — do not build/wire real order placement until they
  explicitly say the paper results look right.

## Data pipeline

- `data/csv/<SYMBOL>.csv` — hourly OHLC + Supertrend + RSI for Nifty 50
  index, BankNifty index, and all 50 Nifty constituent stocks. Source of
  truth; append-only, never rewritten in full after initial creation.
- `data/excel/<year>/<year>-<month>.xlsx` — generated FROM the CSVs, for
  human viewing only. Never read from; always regenerable.
- `data/csv/archived/` — CSVs for stocks that dropped out of the Nifty 50
  index (moved here, not deleted, when `refresh_constituents.sh` runs).
- `data/options_csv/<UNDERLYING>_<EXPIRY>.csv` — hourly snapshots of BOTH
  put and call option prices + computed IV/delta, for the current month's
  expiry, within ~15% of spot on each side (puts below spot, calls above).
  Being collected prospectively (no historical options data exists
  retroactively) specifically so that in a few months there's real
  historical option price data to backtest against, rather than only being
  able to forward-simulate from "now".

## Timestamps: always IST, never local system time

The dev machine's system timezone is NOT IST (e.g. it's been Singapore
time, UTC+8, 2.5hrs ahead of IST) — but NSE and everything in this project
operates in IST. Every place that captures "now" or "today" MUST use
`config/ist_time.py` (`now_ist()`, `now_ist_naive()`, `today_ist()`) —
never bare `datetime.now()` / `date.today()` in Python, never bare `date`
in bash (use `TZ='Asia/Kolkata' date` instead, as in
`scripts/scheduled_update.sh`). This applies to EVERYTHING: historical
data query windows, expiry day-count math, log timestamps, options
snapshot timestamps, archive filenames — no exceptions. Getting this wrong
silently shifts day-boundary calculations, which is worst exactly when
it's hardest to notice (near midnight IST). This was a real bug caught
and fixed once already (2026-09-07) — stay vigilant for it creeping back
in on any new script.

## Automated scheduling

- `scripts/market_hours.py` checks NSE market hours (9:15am-3:30pm IST,
  Mon-Fri) using explicit IST timezone conversion (zoneinfo, stdlib) —
  NOT the machine's local system timezone, since the user's Mac may be set
  to a different zone (e.g. Singapore, 2.5hrs ahead of IST). Tested against
  9 scenarios including the SGT->IST conversion specifically.
- `scripts/run_if_market_open.sh` is a generic, reusable market-hours-gated
  runner: `./scripts/run_if_market_open.sh <python_script> <log_file>`.
  Tested (both success and failure paths) before being built on.
- THREE fully independent scheduled jobs sit on top of that shared runner —
  NOT one combined script. This was a deliberate correction: the original
  design chained market data + paper trading + options data collection
  together in one script, and the user correctly pushed back that options
  data collection (irreplaceable if a snapshot is missed) must not be able
  to fail just because paper trading hit a live Kite API hiccup elsewhere
  in the same script. Real process-level independence via three separate
  launchd jobs, not just try/except patches within one script:
  - `scripts/scheduled_market_data.sh` + `com.kitebot.marketdata.plist`
  - `scripts/scheduled_options_data.sh` + `com.kitebot.optionsdata.plist`
  - `scripts/scheduled_paper_trade.sh` + `com.kitebot.papertrade.plist`
  Each logs to its own file under `logs/` — see README's "Automated
  scheduling" section for setup steps.
- `scripts/update_hourly.sh` still exists but is now MANUAL-USE ONLY (runs
  everything in sequence, for testing/convenience) — it is NOT used by the
  automated scheduling above anymore. Don't reintroduce a combined
  automated path without a good reason; the independence was intentional.
- KNOWN LIMITATION (told to user clearly, not hidden): daily login is
  still manual — Kite tokens expire daily and need browser-based 2FA login,
  which isn't automated. All three scheduled jobs will fail until
  `scripts/login.py` is run that day. Also, the Mac must be awake/online
  during market hours — launchd doesn't wake a sleeping Mac. A cloud VPS
  is the real fix for full reliability, still pending (see Status below).

## Where things stand (update as work progresses)

- [x] Auth flow, project skeleton, GitHub repo
- [x] Data pipeline: Nifty 50 list, instrument tokens (Nifty + BankNifty),
      hourly candles + Supertrend/RSI, Excel export, constituent archiving
- [x] Options pricing module (Black-Scholes + IV solver + delta)
- [x] Signal engine (entry/exit state machine) — tested, 7 scenarios passing
- [x] Options chain logic (expiry selection, strike interval detection,
      delta-based strike picking) — tested, 11 scenarios passing
- [x] Options price data collection (puts + calls, hourly, prospective)
- [x] Automated scheduling (macOS launchd) — daily login still manual,
      Mac must be awake/online during market hours
- [x] Paper trading engine for Nifty (state persistence + live quote-based
      simulated entries/exits + trade log) — scoped to Nifty only for now,
      per user's request to validate one underlying before generalizing to
      BankNifty. Wired into update_hourly.sh (runs every scheduled cycle).
      `strategy/paper_trading.py` (logic) + `scripts/paper_trade.py`
      (runner). Tested: state persistence, expiry force-close, stop-loss
      math, signal engine integration. NOT tested: actual live Kite quote
      fetching / option instrument lookup (no Kite access in dev sandbox)
      — user needs to run it live and report back if anything's off there.
- [ ] Review paper trading results with the user (need some real trading
      days to pass first, then look at data/paper_trades.csv together)
- [ ] Generalize paper trading to BankNifty too (straightforward — same
      logic, just needs looping over both underlyings instead of hardcoding
      Nifty in scripts/paper_trade.py)
- [ ] Live order execution — DO NOT BUILD until paper trading is validated
      and the user explicitly asks to go live
- [ ] Cloud VPS deployment (for true always-on reliability, beyond what a
      laptop can offer) — not yet started

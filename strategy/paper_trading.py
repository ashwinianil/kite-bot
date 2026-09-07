"""
Paper trading: opens/closes SIMULATED positions using live option quotes,
persists state between runs, and logs closed trades. No real orders are
ever placed here — this only reads market data and writes to local files.

State persistence: since this runs periodically (e.g. every 15 min via the
scheduler, not as one continuous process), whether we're currently
"holding" a paper position is saved to data/paper_positions.json between
runs. The underlying's signal (armed/in-position per the RSI+Supertrend
rules) is NOT persisted — it's cheap to recompute from the full historical
CSV on every run via strategy.signal_engine.generate_signals(), which is
simpler and self-healing (no state-corruption risk if a run is missed).

All dates/times here are IST (config/ist_time.py) — see AGENTS.md.
"""

import json
import csv
from pathlib import Path
from datetime import date

from config.ist_time import today_ist
from strategy.options_chain import (
    pick_current_expiry, get_strike_interval, select_short_strike_by_delta,
    compute_hedge_strike, days_to_expiry,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POSITIONS_FILE = PROJECT_ROOT / "data" / "paper_positions.json"
TRADE_LOG_FILE = PROJECT_ROOT / "data" / "paper_trades.csv"

HEDGE_WIDTH_POINTS = 200
TARGET_DELTA_LOW = 0.15
TARGET_DELTA_HIGH = 0.20
STOP_LOSS_PCT_OF_MAX_LOSS = 0.50
FORCE_CLOSE_DAYS_BEFORE_EXPIRY = 1

TRADE_LOG_FIELDS = [
    "underlying", "entry_date", "exit_date", "expiry",
    "short_strike", "hedge_strike", "entry_credit", "exit_debit",
    "pnl", "exit_reason",
]


def _load_all_positions():
    if not POSITIONS_FILE.exists():
        return {}
    with open(POSITIONS_FILE) as f:
        return json.load(f)


def _save_all_positions(all_positions):
    POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POSITIONS_FILE, "w") as f:
        json.dump(all_positions, f, indent=2, default=str)


def get_position(underlying: str):
    """Returns the open position dict for this underlying, or None if flat."""
    return _load_all_positions().get(underlying)


def _set_position(underlying: str, position_dict_or_none):
    all_positions = _load_all_positions()
    if position_dict_or_none is None:
        all_positions.pop(underlying, None)
    else:
        all_positions[underlying] = position_dict_or_none
    _save_all_positions(all_positions)


def _get_option_instruments(kite, options_name: str):
    """
    Fetches all NFO option instruments for this underlying (e.g. "NIFTY" —
    the `name` field Kite uses for the underlying in its F&O instrument
    dump, NOT the index tradingsymbol "NIFTY 50").
    """
    all_nfo = kite.instruments("NFO")
    return [inst for inst in all_nfo if inst.get("name") == options_name]


def _get_put_candidates_below_spot(option_instruments, expiry: date, spot: float, window_pct: float = 0.15):
    """Puts below spot only — that's the short-strike zone for a bull put spread."""
    low_bound = spot * (1 - window_pct)
    return [
        inst for inst in option_instruments
        if inst.get("instrument_type") == "PE"
        and inst.get("expiry") == expiry
        and low_bound <= inst.get("strike", 0) < spot
    ]


def _fetch_quotes(kite, instruments: list):
    """
    Fetches live LTPs for a list of instrument dicts (each needs
    'exchange' and 'tradingsymbol'). Returns {instrument_token: ltp}.
    """
    if not instruments:
        return {}
    keys = [f"{inst['exchange']}:{inst['tradingsymbol']}" for inst in instruments]
    quotes = kite.quote(keys)

    result = {}
    for inst in instruments:
        key = f"{inst['exchange']}:{inst['tradingsymbol']}"
        quote = quotes.get(key)
        if quote:
            result[inst["instrument_token"]] = quote["last_price"]
    return result


def open_paper_position(kite, underlying: str, options_name: str, spot: float):
    """
    Selects an expiry + strikes via delta, fetches live quotes, and saves a
    new open paper position. Returns the position dict, or None if it
    couldn't be opened (e.g. no valid expiry, no quotes available).
    """
    entry_date = today_ist()

    option_instruments = _get_option_instruments(kite, options_name)
    if not option_instruments:
        print(f"  [{underlying}] No option instruments found for '{options_name}' — cannot open position.")
        return None

    available_expiries = sorted({inst["expiry"] for inst in option_instruments if inst.get("expiry")})
    expiry = pick_current_expiry(available_expiries, entry_date, FORCE_CLOSE_DAYS_BEFORE_EXPIRY)
    if expiry is None:
        print(f"  [{underlying}] No suitable expiry found — cannot open position.")
        return None

    dte = days_to_expiry(expiry, entry_date)

    candidates_raw = _get_put_candidates_below_spot(option_instruments, expiry, spot)
    if not candidates_raw:
        print(f"  [{underlying}] No candidate strikes found near spot for expiry {expiry} — cannot open position.")
        return None

    quotes = _fetch_quotes(kite, candidates_raw)
    candidates = [
        {"strike": inst["strike"], "ltp": quotes[inst["instrument_token"]]}
        for inst in candidates_raw if inst["instrument_token"] in quotes and quotes[inst["instrument_token"]] > 0
    ]
    if not candidates:
        print(f"  [{underlying}] No live quotes available for candidate strikes — cannot open position.")
        return None

    short_choice = select_short_strike_by_delta(candidates, spot, dte, TARGET_DELTA_LOW, TARGET_DELTA_HIGH)
    if short_choice is None:
        print(f"  [{underlying}] Could not compute a valid delta for any candidate — cannot open position.")
        return None

    strike_interval = get_strike_interval([c["strike"] for c in candidates_raw])
    hedge_strike_price = compute_hedge_strike(short_choice["strike"], HEDGE_WIDTH_POINTS, strike_interval)

    hedge_matches = [c for c in candidates_raw if c["strike"] == hedge_strike_price]
    if not hedge_matches:
        print(f"  [{underlying}] Computed hedge strike {hedge_strike_price} not found in listed instruments.")
        return None

    hedge_quotes = _fetch_quotes(kite, hedge_matches)
    hedge_inst = hedge_matches[0]
    hedge_ltp = hedge_quotes.get(hedge_inst["instrument_token"])
    if not hedge_ltp:
        print(f"  [{underlying}] No live quote for hedge strike {hedge_strike_price} — cannot open position.")
        return None

    entry_credit = short_choice["ltp"] - hedge_ltp

    position = {
        "underlying": underlying,
        "options_name": options_name,
        "entry_date": entry_date.isoformat(),
        "expiry": expiry.isoformat(),
        "short_strike": short_choice["strike"],
        "hedge_strike": hedge_strike_price,
        "short_entry_price": short_choice["ltp"],
        "hedge_entry_price": hedge_ltp,
        "entry_credit": entry_credit,
        "short_delta_at_entry": short_choice["delta"],
    }
    _set_position(underlying, position)

    print(f"  [{underlying}] PAPER ENTRY: sold {short_choice['strike']}PE @ {short_choice['ltp']:.2f}, "
          f"bought {hedge_strike_price}PE @ {hedge_ltp:.2f} (hedge), "
          f"net credit {entry_credit:.2f}, expiry {expiry}, delta {short_choice['delta']:.3f}")

    return position


def _get_leg_quotes(kite, position: dict):
    """Fetches current live quotes for both legs of an open position. Returns (short_price, hedge_price), either possibly None."""
    options_name = position["options_name"]
    short_strike = position["short_strike"]
    hedge_strike = position["hedge_strike"]
    expiry = date.fromisoformat(position["expiry"])

    option_instruments = _get_option_instruments(kite, options_name)
    matches = [
        inst for inst in option_instruments
        if inst.get("expiry") == expiry and inst.get("instrument_type") == "PE"
        and inst.get("strike") in (short_strike, hedge_strike)
    ]
    quotes = _fetch_quotes(kite, matches) if matches else {}

    short_inst = next((i for i in matches if i["strike"] == short_strike), None)
    hedge_inst = next((i for i in matches if i["strike"] == hedge_strike), None)

    short_price = quotes.get(short_inst["instrument_token"]) if short_inst else None
    hedge_price = quotes.get(hedge_inst["instrument_token"]) if hedge_inst else None
    return short_price, hedge_price


def check_stop_loss(kite, position: dict) -> bool:
    """
    Fetches live quotes for the currently held strikes and checks whether
    the current loss has reached STOP_LOSS_PCT_OF_MAX_LOSS of the max
    possible loss on this spread.
    """
    underlying = position["underlying"]
    short_price, hedge_price = _get_leg_quotes(kite, position)

    if short_price is None or hedge_price is None:
        print(f"  [{underlying}] WARNING: missing live quote for stop-loss check — skipping this check.")
        return False

    current_cost_to_close = short_price - hedge_price
    current_loss = current_cost_to_close - position["entry_credit"]

    spread_width = abs(position["short_strike"] - position["hedge_strike"])
    max_loss = spread_width - position["entry_credit"]

    if max_loss <= 0:
        return False  # shouldn't happen with a real credit spread, but avoid divide-by-zero weirdness

    loss_fraction = current_loss / max_loss
    if loss_fraction >= STOP_LOSS_PCT_OF_MAX_LOSS:
        print(f"  [{underlying}] Stop-loss triggered: current loss {current_loss:.2f} is "
              f"{loss_fraction*100:.0f}% of max loss {max_loss:.2f}")
        return True
    return False


def check_expiry_force_close(position: dict) -> bool:
    """True if we're within FORCE_CLOSE_DAYS_BEFORE_EXPIRY of the held expiry."""
    expiry = date.fromisoformat(position["expiry"])
    today = today_ist()
    return days_to_expiry(expiry, today) <= FORCE_CLOSE_DAYS_BEFORE_EXPIRY


def close_paper_position(kite, position: dict, exit_reason: str):
    """
    Fetches live exit prices for the held strikes, computes P&L, appends a
    row to the trade log CSV, and clears the open position state.
    """
    underlying = position["underlying"]
    exit_date = today_ist()

    short_price, hedge_price = _get_leg_quotes(kite, position)

    if short_price is not None and hedge_price is not None:
        exit_debit = short_price - hedge_price
        pnl = position["entry_credit"] - exit_debit
    else:
        # Contracts may have expired/delisted (e.g. exiting exactly on/after
        # expiry) — log what we can, mark P&L as unknown rather than guessing.
        exit_debit = None
        pnl = None
        print(f"  [{underlying}] WARNING: couldn't get live exit quotes (contracts may be expired). "
              f"Logging trade with exit_debit/pnl as blank.")

    TRADE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_exists = TRADE_LOG_FILE.exists()
    with open(TRADE_LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TRADE_LOG_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "underlying": underlying,
            "entry_date": position["entry_date"],
            "exit_date": exit_date.isoformat(),
            "expiry": position["expiry"],
            "short_strike": position["short_strike"],
            "hedge_strike": position["hedge_strike"],
            "entry_credit": position["entry_credit"],
            "exit_debit": exit_debit,
            "pnl": pnl,
            "exit_reason": exit_reason,
        })

    pnl_str = f"{pnl:.2f}" if pnl is not None else "unknown"
    print(f"  [{underlying}] PAPER EXIT ({exit_reason}): P&L = {pnl_str}")

    _set_position(underlying, None)

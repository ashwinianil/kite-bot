"""
Options chain logic: expiry selection, strike-interval detection, and
delta-based strike selection. Pure logic — no live Kite calls here, so this
is fully unit-testable. Live quote-fetching lives in paper_trading.py.
"""

from datetime import date
from strategy.options_pricing import delta_from_market_price


def days_to_expiry(expiry: date, today: date) -> int:
    return (expiry - today).days


def pick_current_expiry(available_expiries: list, today: date, min_days_before_expiry: int = 1):
    """
    Picks the expiry to trade: the LATEST expiry within the current calendar
    month (this is always the monthly expiry, whether or not weeklies are
    also listed — monthly is by definition the last expiry of the month).

    If that expiry is already too close (<= min_days_before_expiry days
    away — matches our force-close rule) or has already passed, rolls
    forward to the next available expiry instead (next month's monthly).

    available_expiries: list of date objects (from Kite's option instrument
    dump for the underlying) — not hardcoded, since expiry dates shift
    around holidays and this must reflect what's actually tradable.

    Returns None if no suitable expiry is found at all (empty list, or
    everything available is too close/passed).
    """
    if not available_expiries:
        return None

    future_expiries = sorted(e for e in available_expiries if e >= today)
    if not future_expiries:
        return None

    current_month_expiries = [
        e for e in future_expiries if e.month == today.month and e.year == today.year
    ]

    if current_month_expiries:
        candidate = max(current_month_expiries)
        if days_to_expiry(candidate, today) > min_days_before_expiry:
            return candidate
        # This month's expiry is too close (or today IS expiry day) — roll forward.

    later_expiries = [e for e in future_expiries if e > (max(current_month_expiries) if current_month_expiries else today)]
    if later_expiries:
        # Next month's monthly = the last expiry within that next month
        next_month = min(later_expiries)
        next_month_expiries = [e for e in later_expiries if e.month == next_month.month and e.year == next_month.year]
        return max(next_month_expiries)

    return None


def get_strike_interval(strikes: list) -> float:
    """
    Detects the standard strike spacing (e.g. 50 for Nifty, 100 for
    BankNifty) from a list of actually-listed strikes, rather than
    hardcoding per-underlying — spacing can change over time as the
    underlying's price level changes.

    Returns the most common gap between consecutive sorted unique strikes.
    """
    unique_sorted = sorted(set(strikes))
    if len(unique_sorted) < 2:
        raise ValueError("Need at least 2 distinct strikes to detect interval")

    gaps = [round(b - a, 2) for a, b in zip(unique_sorted, unique_sorted[1:])]
    # Most common gap (mode) — robust to occasional missing/illiquid strikes
    # that would otherwise create a double-sized gap.
    return max(set(gaps), key=gaps.count)


def select_short_strike_by_delta(candidates: list, spot: float, days_to_expiry_val: int,
                                  target_delta_low: float = 0.15, target_delta_high: float = 0.20,
                                  option_type: str = "put"):
    """
    Given a list of candidate strikes with their live LTPs, computes each
    one's delta (via Black-Scholes IV back-out) and picks the best match
    for the target delta range.

    candidates: list of dicts, each {"strike": float, "ltp": float}
    Returns: the chosen candidate dict, augmented with "delta" key, or None
    if no candidate produced a valid delta (e.g. all quotes were stale/zero).

    Preference order: a candidate whose |delta| falls WITHIN [target_delta_low,
    target_delta_high] is always preferred over one outside that range, even
    if the outside one is numerically closer to the midpoint — being in-range
    matters more than being centered.
    """
    target_mid = (target_delta_low + target_delta_high) / 2
    scored = []

    for c in candidates:
        d = delta_from_market_price(c["ltp"], spot, c["strike"], days_to_expiry_val, option_type)
        if d is None:
            continue
        abs_d = abs(d)
        in_range = target_delta_low <= abs_d <= target_delta_high
        distance = abs(abs_d - target_mid)
        scored.append({**c, "delta": d, "_in_range": in_range, "_distance": distance})

    if not scored:
        return None

    # Sort: in-range candidates first (True sorts after False, so negate),
    # then by distance to target midpoint.
    scored.sort(key=lambda c: (not c["_in_range"], c["_distance"]))
    best = scored[0]
    best.pop("_in_range")
    best.pop("_distance")
    return best


def compute_hedge_strike(short_strike: float, hedge_width_points: float, strike_interval: float) -> float:
    """
    Hedge strike = short_strike - hedge_width_points, rounded to the
    nearest valid strike interval (so it lands on an actually-listed strike,
    not an arbitrary number).
    """
    raw = short_strike - hedge_width_points
    return round(raw / strike_interval) * strike_interval

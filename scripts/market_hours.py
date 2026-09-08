"""
Checks whether NSE is currently in market hours (9:15am-3:30pm IST,
Monday-Friday). Uses IST explicitly via zoneinfo (stdlib, no extra
dependency) rather than relying on the machine's local system timezone —
this matters because a scheduler running on a machine set to a different
timezone (e.g. Singapore, which is 2.5 hours ahead of IST) would otherwise
compute the wrong window.

Does NOT account for NSE trading holidays (Diwali, Republic Day, etc.) —
those shift year to year and aren't tracked here. On a holiday, this will
say "market hours" (correct weekday + time window) even though NSE is
closed — the scripts will simply find no new data and no-op harmlessly,
so this is a low-cost gap, not a dangerous one.
"""

import sys
from pathlib import Path
from datetime import datetime, time

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.ist_time import IST, now_ist

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

# Pre-market window for the daily automated login — before market open,
# with enough buffer that a re-try or two still lands before 9:15.
PREMARKET_LOGIN_START = time(8, 30)
PREMARKET_LOGIN_END = time(9, 10)


def is_market_hours(now: datetime = None) -> bool:
    """
    now: optional datetime to check instead of the current time (useful for
    testing). If it has no timezone info, it's assumed to already be IST.
    """
    if now is None:
        now = now_ist()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    else:
        now = now.astimezone(IST)

    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


def is_premarket_login_window(now: datetime = None) -> bool:
    """
    True during the pre-market window when the automated daily login should
    run (weekdays only). Kept as a separate window from is_market_hours()
    rather than a calendar-time launchd trigger, because launchd's
    StartCalendarInterval uses the MACHINE's local timezone to decide when
    to fire — which would be wrong on a machine not set to IST, the same
    problem this whole module exists to avoid elsewhere. Checking the
    window in Python (IST-explicit) and running on the same frequent
    StartInterval as the other jobs sidesteps that entirely.
    """
    if now is None:
        now = now_ist()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    else:
        now = now.astimezone(IST)

    if now.weekday() >= 5:
        return False

    return PREMARKET_LOGIN_START <= now.time() <= PREMARKET_LOGIN_END


if __name__ == "__main__":
    # Quick manual check: `python scripts/market_hours.py`
    now = now_ist()
    status = "OPEN" if is_market_hours() else "CLOSED"
    print(f"Current IST time: {now.strftime('%Y-%m-%d %H:%M:%S %A')}")
    print(f"Market status: {status}")

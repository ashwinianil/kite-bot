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

from datetime import datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


def is_market_hours(now: datetime = None) -> bool:
    """
    now: optional datetime to check instead of the current time (useful for
    testing). If it has no timezone info, it's assumed to already be IST.
    """
    if now is None:
        now = datetime.now(IST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    else:
        now = now.astimezone(IST)

    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


if __name__ == "__main__":
    # Quick manual check: `python scripts/market_hours.py`
    now_ist = datetime.now(IST)
    status = "OPEN" if is_market_hours() else "CLOSED"
    print(f"Current IST time: {now_ist.strftime('%Y-%m-%d %H:%M:%S %A')}")
    print(f"Market status: {status}")

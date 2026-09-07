"""
Single source of truth for "current time" across this project — always
IST, regardless of the machine's own system timezone. NSE trades in IST;
using local system time anywhere in this codebase is a bug, not a
convenience — it can silently shift day-boundary calculations (expiry day
counts, "today's date" for logging/filenames, historical data query
windows) by hours, which matters most exactly when it's hardest to notice
(near midnight IST).
"""

from datetime import datetime, date
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """Current time, timezone-aware, in IST."""
    return datetime.now(IST)


def now_ist_naive() -> datetime:
    """
    Current time in IST, but with tzinfo stripped — for comparing against
    our stored candle data, which is naive-but-represents-IST (Kite's API
    returns IST-native timestamps; we strip the tz offset on ingest since
    it's redundant once we know everything in this project is IST).
    """
    return now_ist().replace(tzinfo=None)


def today_ist() -> date:
    """Current date in IST (not the machine's local date)."""
    return now_ist().date()

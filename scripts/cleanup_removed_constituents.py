"""
Archives (moves, doesn't delete) CSV data files for any symbol that's no
longer in the current Nifty 50 constituent list. Run this after
get_instrument_tokens.py has been refreshed with the latest list.

Why archive instead of delete: historical data for a stock that dropped out
of the index is still potentially useful for reference/backtesting later —
this just moves it out of the actively-updated folder so update_data.py
stops touching it, without losing the data.

Run:
    python scripts/cleanup_removed_constituents.py
"""

import sys
import csv
import shutil
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.ist_time import today_ist

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOKENS_FILE = PROJECT_ROOT / "config" / "instrument_tokens.csv"
CSV_DIR = PROJECT_ROOT / "data" / "csv"
ARCHIVE_DIR = PROJECT_ROOT / "data" / "csv" / "archived"


def load_current_symbols():
    if not TOKENS_FILE.exists():
        raise FileNotFoundError(
            f"{TOKENS_FILE} not found. Run get_instrument_tokens.py first."
        )
    symbols = set()
    with open(TOKENS_FILE) as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row["tradingsymbol"].replace(" ", "_")
            symbols.add(symbol)
    return symbols


def main():
    current_symbols = load_current_symbols()

    if not CSV_DIR.exists():
        print("No data/csv/ folder yet — nothing to clean up.")
        return

    existing_files = [f for f in CSV_DIR.glob("*.csv")]
    to_archive = [f for f in existing_files if f.stem not in current_symbols]

    if not to_archive:
        print("Nothing to archive — every data file matches a current Nifty 50 constituent.")
        return

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    today_str = today_ist().isoformat()

    print(f"Archiving {len(to_archive)} file(s) for symbols no longer in the Nifty 50:")
    for f in to_archive:
        dest = ARCHIVE_DIR / f"{f.stem}_removed_{today_str}.csv"
        shutil.move(str(f), str(dest))
        print(f"  {f.name} -> data/csv/archived/{dest.name}")

    print("\nDone. Archived files are preserved in data/csv/archived/ if you need them later.")


if __name__ == "__main__":
    main()

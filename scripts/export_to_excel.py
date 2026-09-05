"""
Generates a monthly Excel workbook from the CSV data — for viewing/reference
only. The CSVs in data/csv/ remain the source of truth; this script never
reads FROM Excel, only writes TO it.

Creates one workbook per (year, month) that has data, with one sheet per
symbol, e.g.:
    data/excel/2026/2026-09.xlsx

Re-running overwrites the month's workbook with the latest data each time,
so it's always safe to re-run after update_data.py.

Run:
    python scripts/export_to_excel.py                # exports all months found in the CSVs
    python scripts/export_to_excel.py --month 2026-09 # exports just one month
"""

import sys
import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_DIR = PROJECT_ROOT / "data" / "csv"
EXCEL_DIR = PROJECT_ROOT / "data" / "excel"


def sheet_name_for(symbol: str) -> str:
    # Excel sheet names: max 31 chars, no []:*?/\\
    name = symbol.replace(" ", "_")
    return name[:31]


def export_month(year: int, month: int, all_data: dict):
    month_str = f"{year}-{month:02d}"
    out_dir = EXCEL_DIR / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{month_str}.xlsx"

    wrote_any = False
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for symbol, df in all_data.items():
            month_df = df[(df["date"].dt.year == year) & (df["date"].dt.month == month)]
            if month_df.empty:
                continue
            month_df.to_excel(writer, sheet_name=sheet_name_for(symbol), index=False)
            wrote_any = True

    if wrote_any:
        print(f"  Wrote {out_path.relative_to(PROJECT_ROOT)}")
    else:
        # Nothing for this month after all — remove the empty file
        out_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", help="Export only this month, format YYYY-MM (default: all months found)")
    args = parser.parse_args()

    if not CSV_DIR.exists() or not any(CSV_DIR.glob("*.csv")):
        print(f"No CSV files found in {CSV_DIR}. Run update_data.py first.")
        return

    print("Loading CSV data...")
    all_data = {}
    for csv_file in sorted(CSV_DIR.glob("*.csv")):
        symbol = csv_file.stem
        df = pd.read_csv(csv_file, parse_dates=["date"])
        if not df.empty:
            all_data[symbol] = df

    if not all_data:
        print("No data to export yet.")
        return

    if args.month:
        year, month = map(int, args.month.split("-"))
        print(f"Exporting {args.month}...")
        export_month(year, month, all_data)
    else:
        # Find every (year, month) combination present across all symbols
        year_months = set()
        for df in all_data.values():
            for ym in df["date"].dt.to_period("M").unique():
                year_months.add((ym.year, ym.month))

        print(f"Exporting {len(year_months)} month(s) of data...")
        for year, month in sorted(year_months):
            export_month(year, month, all_data)

    print("\nDone.")


if __name__ == "__main__":
    main()

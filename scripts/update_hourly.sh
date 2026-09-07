#!/bin/bash
# Run this to update hourly candle data + Supertrend/RSI for all Nifty 50
# instruments, and refresh the Excel reference workbooks.
#
# Safe to run repeatedly (e.g. every hour during market hours 9:15am-3:30pm
# IST) — never creates duplicate data.
#
# Requires: a valid access token for today (run scripts/login.py first if
# you haven't logged in yet today — tokens expire daily).
#
# Usage:
#   ./scripts/update_hourly.sh

set -e  # stop immediately if any step fails

cd "$(dirname "$0")/.."  # move to project root regardless of where this is run from

if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "No venv/ found. Create one first: python3.11 -m venv venv"
    exit 1
fi

echo "=== Step 1/4: Updating hourly candle data + indicators ==="
python scripts/update_data.py

echo ""
echo "=== Step 2/4: Checking Nifty paper trading signal (entry/exit) ==="
python scripts/paper_trade.py

echo ""
echo "=== Step 3/4: Collecting options price snapshots (Nifty + BankNifty puts) ==="
python scripts/update_options_data.py

echo ""
echo "=== Step 4/4: Refreshing Excel reference workbooks ==="
python scripts/export_to_excel.py

echo ""
echo "Done. Data, paper trading check, options snapshots, and Excel workbooks are all up to date."

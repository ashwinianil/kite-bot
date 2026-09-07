#!/bin/bash
# MANUAL convenience script — runs everything in sequence once, for when
# you want to trigger a full update by hand.
#
# For AUTOMATED/scheduled running, this is NOT what gets used — see
# scripts/scheduled_market_data.sh, scheduled_options_data.sh, and
# scheduled_paper_trade.sh instead, which run as three fully independent
# processes (so a failure in one, e.g. paper trading hitting a live Kite
# API hiccup, can never affect the others — see README's "Automated
# scheduling" section for why this separation matters).
#
# Requires: a valid access token for today (run scripts/login.py first if
# you haven't logged in yet today — tokens expire daily).
#
# Usage:
#   ./scripts/update_hourly.sh

set -e  # stop immediately if any step fails — fine for a manual run where
        # you're watching the output and want to know right away

cd "$(dirname "$0")/.."

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

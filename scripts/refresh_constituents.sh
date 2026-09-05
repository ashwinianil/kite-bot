#!/bin/bash
# Run this:
#   - Once, the first time you set up the project
#   - Again every March/September after NSE announces the Nifty 50 rebalance
#
# Usage:
#   ./scripts/refresh_constituents.sh

set -e  # stop immediately if any step fails

cd "$(dirname "$0")/.."  # move to project root regardless of where this is run from

if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "No venv/ found. Create one first: python3.11 -m venv venv"
    exit 1
fi

echo "=== Step 1/2: Fetching current Nifty 50 constituent list from NSE ==="
python scripts/update_nifty50_list_march_sept.py

echo ""
echo "=== Step 2/2: Resolving symbols to Kite instrument tokens ==="
python scripts/get_instrument_tokens.py

echo ""
echo "Done. Constituent list and instrument tokens are up to date."

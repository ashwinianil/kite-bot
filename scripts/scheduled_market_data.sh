#!/bin/bash
# Independent scheduled task: updates hourly candle data + indicators, and
# refreshes Excel reference workbooks. Runs as its own process — has NO
# dependency on paper trading or options data collection succeeding or
# failing; see scripts/scheduled_options_data.sh and
# scripts/scheduled_paper_trade.sh for those.
#
# Usage: ./scripts/scheduled_market_data.sh
# (called automatically by com.kitebot.marketdata.plist via launchd)

cd "$(dirname "$0")/.."
./scripts/run_if_market_open.sh scripts/update_data.py market_data.log
./scripts/run_if_market_open.sh scripts/export_to_excel.py market_data.log

#!/bin/bash
# Independent scheduled task: checks the Nifty paper trading signal
# (entry/exit) and manages the simulated position. Runs as its own process
# — completely independent of options data collection and market data
# updates; a failure here has zero effect on those.
#
# Usage: ./scripts/scheduled_paper_trade.sh
# (called automatically by com.kitebot.papertrade.plist via launchd)

cd "$(dirname "$0")/.."
./scripts/run_if_market_open.sh scripts/paper_trade.py paper_trade.log

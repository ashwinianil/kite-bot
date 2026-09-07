#!/bin/bash
# Independent scheduled task: collects options price snapshots (puts +
# calls, Nifty + BankNifty). Runs as its own process — has NO dependency on
# paper trading succeeding or failing, so a paper-trading bug or Kite
# hiccup there can never prevent this historical data collection from
# running. This is the one thing we specifically don't want to ever miss,
# since it can't be backfilled retroactively once a snapshot is missed.
#
# Usage: ./scripts/scheduled_options_data.sh
# (called automatically by com.kitebot.optionsdata.plist via launchd)

cd "$(dirname "$0")/.."
./scripts/run_if_market_open.sh scripts/update_options_data.py options_data.log

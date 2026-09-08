#!/bin/bash
# Independent scheduled task: automated daily login (no browser interaction
# needed), during the 8:30-9:10am IST pre-market window. Runs as its own
# process — same independence principle as the other scheduled jobs.
#
# Usage: ./scripts/scheduled_headless_login.sh
# (called automatically by com.kitebot.dailylogin.plist via launchd)

cd "$(dirname "$0")/.."
./scripts/run_if_premarket.sh scripts/headless_login.py daily_login.log

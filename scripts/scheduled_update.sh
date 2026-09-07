#!/bin/bash
# Runs update_hourly.sh, but ONLY if NSE market hours are currently active
# (checked in IST regardless of the machine's system timezone). Designed to
# be called frequently (e.g. every 15 min) by a scheduler (launchd/cron) —
# it's cheap to no-op outside market hours, so over-calling is harmless.
#
# All log timestamps use IST explicitly (TZ='Asia/Kolkata' date), not the
# machine's local system time — this project stores and logs everything in
# IST throughout, regardless of what timezone the machine itself is set to.
#
# IMPORTANT LIMITATION: Kite access tokens expire daily and require a
# browser-based login (password + 2FA) — this CANNOT be automated headlessly
# with the current setup. This scheduled job will fail every run until you
# manually run `python scripts/login.py` each trading day. See AGENTS.md /
# README for a note on TOTP-based semi-automated login as a possible future
# enhancement — not built yet.
#
# Usage (manual test):
#   ./scripts/scheduled_update.sh
#
# Usage (via launchd — see scripts/com.kitebot.hourlyupdate.plist):
#   Installed automatically by that plist once loaded with launchctl.

cd "$(dirname "$0")/.."  # move to project root regardless of where this is run from

IST_NOW="$(TZ='Asia/Kolkata' date '+%Y-%m-%d %H:%M:%S IST')"

if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "$IST_NOW: No venv/ found. Skipping." >> logs/scheduled_update.log
    exit 1
fi

if python scripts/market_hours.py | grep -q "OPEN"; then
    echo "$IST_NOW: Market open — running update." >> logs/scheduled_update.log
    ./scripts/update_hourly.sh >> logs/scheduled_update.log 2>&1
else
    echo "$IST_NOW: Market closed — skipping." >> logs/scheduled_update.log
fi

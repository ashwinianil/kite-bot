#!/bin/bash
# Generic market-hours-gated runner. Runs the given Python script ONLY if
# NSE market hours are currently active (checked in IST, regardless of the
# machine's system timezone), logging to the given log file.
#
# This is a shared building block — scheduled_market_data.sh,
# scheduled_options_data.sh, and scheduled_paper_trade.sh each call this
# with their own script + log file, so they run as fully independent
# processes: a crash or hang in one has ZERO effect on the others (real
# OS-level process independence, not just error handling within one script).
#
# Usage:
#   ./scripts/run_if_market_open.sh <python_script_path> <log_file_name>
#
# Example:
#   ./scripts/run_if_market_open.sh scripts/update_options_data.py options_data.log

set -e

cd "$(dirname "$0")/.."  # move to project root regardless of where this is run from

PYTHON_SCRIPT="$1"
LOG_NAME="$2"

if [ -z "$PYTHON_SCRIPT" ] || [ -z "$LOG_NAME" ]; then
    echo "Usage: $0 <python_script_path> <log_file_name>"
    exit 1
fi

LOG_PATH="logs/$LOG_NAME"
IST_NOW="$(TZ='Asia/Kolkata' date '+%Y-%m-%d %H:%M:%S IST')"

if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "$IST_NOW: No venv/ found. Skipping." >> "$LOG_PATH"
    exit 1
fi

if python scripts/market_hours.py | grep -q "OPEN"; then
    echo "$IST_NOW: Market open — running $PYTHON_SCRIPT" >> "$LOG_PATH"
    set +e  # capture the exit code below instead of dying here — we want to log it either way
    python "$PYTHON_SCRIPT" >> "$LOG_PATH" 2>&1
    EXIT_CODE=$?
    set -e
    echo "$IST_NOW: Finished (exit code $EXIT_CODE)" >> "$LOG_PATH"
else
    echo "$IST_NOW: Market closed — skipping $PYTHON_SCRIPT" >> "$LOG_PATH"
fi

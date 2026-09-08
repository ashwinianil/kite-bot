#!/bin/bash
# Like run_if_market_open.sh, but gates on the PRE-MARKET login window
# (8:30-9:10am IST) instead of full market hours. Used specifically for
# the automated daily login.
#
# Usage:
#   ./scripts/run_if_premarket.sh <python_script_path> <log_file_name>

set -e

cd "$(dirname "$0")/.."

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

IS_PREMARKET=$(python -c "
import sys
sys.path.insert(0, '.')
from scripts.market_hours import is_premarket_login_window
print('YES' if is_premarket_login_window() else 'NO')
")

if [ "$IS_PREMARKET" = "YES" ]; then
    echo "$IST_NOW: Pre-market window — running $PYTHON_SCRIPT" >> "$LOG_PATH"
    set +e
    python "$PYTHON_SCRIPT" >> "$LOG_PATH" 2>&1
    EXIT_CODE=$?
    set -e
    echo "$IST_NOW: Finished (exit code $EXIT_CODE)" >> "$LOG_PATH"
else
    echo "$IST_NOW: Outside pre-market window — skipping $PYTHON_SCRIPT" >> "$LOG_PATH"
fi

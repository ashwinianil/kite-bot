#!/bin/bash
# One-time setup script for a fresh Linux VM (tested pattern: Ubuntu/Debian).
# Installs Python 3.11, sets up the venv, installs dependencies (including
# Playwright's browser), and installs the crontab for automated scheduling.
#
# IMPORTANT: verify headless_login.py actually works (via `--visible` mode)
# on your Mac FIRST, before deploying here — a headless VM has no display,
# so you can't debug --visible mode on the VM itself. Only bring already-
# working automation here.
#
# Usage (from the repo root, after cloning it onto the VM):
#   chmod +x scripts/setup_linux.sh
#   ./scripts/setup_linux.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"
echo "=== Kite Trading Bot — Linux VM Setup ==="
echo "Repo path: $REPO_DIR"
echo ""

# --- 1. Python 3.11 ---
if command -v python3.11 &> /dev/null; then
    echo "Python 3.11 already installed."
else
    echo "Installing Python 3.11..."
    sudo apt update
    if ! sudo apt install -y python3.11 python3.11-venv python3.11-dev 2>/dev/null; then
        echo "python3.11 not in default repos — adding deadsnakes PPA..."
        sudo apt install -y software-properties-common
        sudo add-apt-repository -y ppa:deadsnakes/ppa
        sudo apt update
        sudo apt install -y python3.11 python3.11-venv python3.11-dev
    fi
fi

# --- 2. Virtual environment ---
if [ ! -d "venv" ]; then
    echo "Creating venv..."
    python3.11 -m venv venv
else
    echo "venv/ already exists — reusing it."
fi
source venv/bin/activate

# --- 3. Python dependencies ---
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# --- 4. Playwright browser + Linux system dependencies ---
echo "Installing Playwright's Chromium browser..."
playwright install chromium
echo "Installing Chromium's Linux system dependencies (needs sudo)..."
sudo venv/bin/playwright install-deps chromium

# --- 5. .env setup ---
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "Created .env from template — YOU MUST fill it in before anything will work:"
    echo "  KITE_API_KEY, KITE_API_SECRET, KITE_USER_ID, KITE_PASSWORD, KITE_TOTP_SECRET"
else
    echo ".env already exists — leaving it as is."
fi

# --- 6. logs/ directory ---
mkdir -p logs

# --- 7. Crontab ---
echo ""
echo "=== Crontab setup ==="
EXISTING_CRON=$(crontab -l 2>/dev/null || echo "")
if [ -n "$EXISTING_CRON" ]; then
    echo "WARNING: you already have existing crontab entries on this machine:"
    echo "---"
    echo "$EXISTING_CRON"
    echo "---"
    echo "Installing scripts/crontab.txt would REPLACE all of the above entirely."
    read -p "Continue and overwrite your crontab? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "Skipped. To add these jobs manually without overwriting your existing"
        echo "crontab, run: crontab -e, then paste in scripts/crontab.txt's contents"
        echo "(with REPLACE_WITH_FULL_PATH_TO_REPO substituted for: $REPO_DIR)"
        echo ""
        echo "=== Setup otherwise complete — see notes above ==="
        exit 0
    fi
fi

sed "s|REPLACE_WITH_FULL_PATH_TO_REPO|$REPO_DIR|g" scripts/crontab.txt > /tmp/kitebot_crontab.txt
crontab /tmp/kitebot_crontab.txt
rm /tmp/kitebot_crontab.txt
echo "Crontab installed. Verify with: crontab -l"

echo ""
echo "=== Setup complete ==="
echo "NEXT STEPS:"
echo "1. Fill in .env with your real credentials (see above)."
echo "2. Test headless login ONCE manually first: python scripts/headless_login.py"
echo "   (no --visible here — this VM has no display; you already verified"
echo "   --visible works correctly on your Mac before deploying here, right?)"
echo "3. Once that works, cron takes over automatically — check logs/ for"
echo "   daily_login.log, market_data.log, options_data.log, paper_trade.log"

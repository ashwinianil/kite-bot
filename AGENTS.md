# Agent notes for this repo

## Environment

- **Python version: 3.11** (specifically). The system default Python on this
  Mac is 3.14, which is too new — `pandas-ta-classic` and other deps don't
  install cleanly on it yet. Always use a venv built with `python3.11`.

- **Virtual environment**: create with `python3.11 -m venv venv`, activate
  with `source venv/bin/activate` before installing or running anything.

- Do NOT install dependencies system-wide. Homebrew's Python is
  externally-managed and will block `pip install` outside a venv anyway.

## Setup (fresh clone)

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in KITE_API_KEY / KITE_API_SECRET
python scripts/login.py
python scripts/test_connection.py
```

## Notes

- `pandas_ta` (original package) is unmaintained and doesn't support
  Python 3.12+. We use `pandas-ta-classic` instead — same API, actively
  maintained, supports Python 3.10–3.14.
- Kite access tokens expire daily — `scripts/login.py` must be re-run each
  trading day before running anything that hits the live API.

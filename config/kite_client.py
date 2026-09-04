"""
Shared Kite Connect client. Import get_kite() from anywhere in the project
to get an authenticated client using the token saved by scripts/login.py.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from kiteconnect import KiteConnect

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def get_kite() -> KiteConnect:
    load_dotenv(ENV_PATH, override=True)

    api_key = os.getenv("KITE_API_KEY")
    access_token = os.getenv("KITE_ACCESS_TOKEN")

    if not api_key:
        raise RuntimeError("KITE_API_KEY missing from .env")
    if not access_token:
        raise RuntimeError(
            "KITE_ACCESS_TOKEN missing. Run `python scripts/login.py` first "
            "(access tokens expire daily, so this is needed once per trading day)."
        )

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return kite

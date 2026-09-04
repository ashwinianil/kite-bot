"""
Daily login script for Kite Connect.

Kite access tokens expire every day at ~6 AM IST, so this needs to be run
once each trading day before the bot starts.

Flow:
1. Prints a login URL -> you open it, log in with Zerodha credentials + 2FA
2. Zerodha redirects to your Redirect URL with a `request_token` in the query string
3. You paste that request_token back here
4. Script exchanges it for an access_token and saves it to .env

Run:
    python scripts/login.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv, set_key
from kiteconnect import KiteConnect

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def main():
    load_dotenv(ENV_PATH)

    api_key = os.getenv("KITE_API_KEY")
    api_secret = os.getenv("KITE_API_SECRET")

    if not api_key or not api_secret:
        print("ERROR: KITE_API_KEY / KITE_API_SECRET not found.")
        print(f"Make sure you've created a .env file at {ENV_PATH}")
        print("(copy .env.example to .env and fill in your credentials)")
        return

    kite = KiteConnect(api_key=api_key)

    login_url = kite.login_url()
    print("\nStep 1: Open this URL in your browser and log in:\n")
    print(login_url)
    print("\nStep 2: After logging in, you'll be redirected to your Redirect URL.")
    print("Copy the 'request_token' value from that URL's query string.")
    print("Example redirect: http://127.0.0.1:5000/callback?request_token=XXXXX&action=login&status=success\n")

    request_token = input("Paste request_token here: ").strip()

    try:
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
    except Exception as e:
        print(f"\nLogin failed: {e}")
        print("Common causes: request_token expired (they're single-use and expire fast),")
        print("or wrong api_secret. Re-run this script and try again quickly.")
        return

    set_key(str(ENV_PATH), "KITE_ACCESS_TOKEN", access_token)
    print(f"\nSuccess! Access token saved to {ENV_PATH}")

    # Sanity check: fetch profile + margins to confirm the token actually works
    kite.set_access_token(access_token)
    try:
        profile = kite.profile()
        margins = kite.margins()
        print(f"\nLogged in as: {profile['user_name']} ({profile['user_id']})")
        print(f"Available equity margin: ₹{margins['equity']['available']['live_balance']}")
    except Exception as e:
        print(f"\nToken saved, but sanity check call failed: {e}")


if __name__ == "__main__":
    main()

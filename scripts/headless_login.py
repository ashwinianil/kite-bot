"""
Fully automated, no-browser-interaction Kite login. For unattended/remote
setups (e.g. a VPS) where scripts/login.py's manual browser flow isn't
possible. Uses Playwright (headless Chromium) to drive the actual Kite
login page, and pyotp to compute the current valid TOTP code from your
permanent secret — the same algorithm your phone's authenticator app uses.

SECURITY: this requires KITE_USER_ID, KITE_PASSWORD, and KITE_TOTP_SECRET
in .env — meaningfully more sensitive than the API key/secret alone. See
.env.example for details. Only fill these in on a machine you trust and
control (e.g. your own VPS with SSH-key-only access), never share this
.env file, and it's already gitignored.

IMPORTANT — selectors not verified against the live site: this was built
without the ability to browse to kite.zerodha.com and inspect its actual
page structure. The element selectors below follow Kite's commonly
documented login flow (userid -> password -> submit -> TOTP -> submit ->
redirect), but Kite may have changed their page since. Run with
--visible first (see below) to watch it click through and fix any
selectors that don't match, before trusting this unattended.

Usage:
    python scripts/headless_login.py              # headless (for cron/VPS use)
    python scripts/headless_login.py --visible     # shows the browser window,
                                                     # for debugging/verifying
                                                     # selectors actually work
"""

import sys
import time
import argparse
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pyotp
from dotenv import load_dotenv, set_key
from kiteconnect import KiteConnect
from playwright.sync_api import sync_playwright

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.ist_time import now_ist

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def get_request_token(api_key: str, user_id: str, password: str, totp_secret: str,
                       headless: bool = True, timeout_ms: int = 20000) -> str:
    """
    Drives the actual Kite login page in a headless browser and returns the
    request_token from the resulting redirect URL.

    Raises RuntimeError with a clear message (and saves a screenshot to
    logs/) if any step doesn't behave as expected — since these selectors
    are unverified against the live site, failures here are the most
    likely first thing to need fixing.
    """
    login_url = f"https://kite.zerodha.com/connect/login?api_key={api_key}&v=3"
    totp = pyotp.TOTP(totp_secret)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            page.goto(login_url, timeout=timeout_ms)

            # --- Step 1: user ID + password ---
            page.fill("input#userid", user_id, timeout=timeout_ms)
            page.fill("input#password", password, timeout=timeout_ms)
            page.click("button[type='submit']", timeout=timeout_ms)

            # --- Step 2: TOTP ---
            # Kite regenerates the TOTP field fresh on this step; compute the
            # code right before filling it in so it's valid for the ~30s window.
            page.wait_for_selector("input#userid", state="detached", timeout=timeout_ms)
            totp_input_selector = "input[type='text'], input[type='number'], input#totp, input#pin"
            page.wait_for_selector(totp_input_selector, timeout=timeout_ms)
            code = totp.now()
            page.fill(totp_input_selector, code, timeout=timeout_ms)

            # Kite's 2FA step sometimes auto-submits once all digits are
            # entered; try clicking submit too in case it doesn't.
            try:
                page.click("button[type='submit']", timeout=3000)
            except Exception:
                pass  # already auto-submitted, or no explicit button — fine either way

            # --- Step 3: wait for the redirect containing request_token ---
            page.wait_for_url("**request_token=**", timeout=timeout_ms)
            redirect_url = page.url

        except Exception as e:
            screenshot_path = Path(__file__).resolve().parent.parent / "logs" / "headless_login_failure.png"
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(screenshot_path))
            except Exception:
                pass
            browser.close()
            raise RuntimeError(
                f"Headless login failed at some step: {e}\n"
                f"Screenshot saved to {screenshot_path} — check it to see what the "
                f"page actually looked like. The selectors in get_request_token() "
                f"were NOT verified against the live Kite login page and likely "
                f"need adjusting. Run with --visible to watch it happen live."
            )

        browser.close()

    parsed = urlparse(redirect_url)
    request_token = parse_qs(parsed.query).get("request_token", [None])[0]
    if not request_token:
        raise RuntimeError(f"Reached the redirect but couldn't find request_token in: {redirect_url}")

    return request_token


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--visible", action="store_true",
                         help="Show the browser window instead of running headless (for debugging)")
    args = parser.parse_args()

    load_dotenv(ENV_PATH)
    import os
    api_key = os.getenv("KITE_API_KEY")
    api_secret = os.getenv("KITE_API_SECRET")
    user_id = os.getenv("KITE_USER_ID")
    password = os.getenv("KITE_PASSWORD")
    totp_secret = os.getenv("KITE_TOTP_SECRET")
    existing_token = os.getenv("KITE_ACCESS_TOKEN")

    # If we already have a working token (e.g. an earlier run this same
    # morning already succeeded), skip the browser automation entirely —
    # this job may run several times within the pre-market window, and
    # repeated fresh logins are both wasteful and risk tripping Zerodha's
    # bot/rate-limit detection.
    if existing_token:
        try:
            test_kite = KiteConnect(api_key=api_key)
            test_kite.set_access_token(existing_token)
            profile = test_kite.profile()
            print(f"Already logged in today as {profile['user_name']} — skipping, nothing to do.")
            sys.exit(0)
        except Exception:
            pass  # existing token doesn't work (expired/new day) — proceed to log in fresh

    missing = [name for name, val in [
        ("KITE_API_KEY", api_key), ("KITE_API_SECRET", api_secret),
        ("KITE_USER_ID", user_id), ("KITE_PASSWORD", password),
        ("KITE_TOTP_SECRET", totp_secret),
    ] if not val]
    if missing:
        print(f"ERROR: missing from .env: {', '.join(missing)}")
        print("See .env.example for what each one is and where to find it.")
        sys.exit(1)

    print(f"[{now_ist().strftime('%Y-%m-%d %H:%M:%S IST')}] Starting headless login...")

    try:
        request_token = get_request_token(api_key, user_id, password, totp_secret,
                                           headless=not args.visible)
    except RuntimeError as e:
        print(f"FAILED: {e}")
        sys.exit(1)

    kite = KiteConnect(api_key=api_key)
    try:
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
    except Exception as e:
        print(f"FAILED to exchange request_token for access_token: {e}")
        sys.exit(1)

    set_key(str(ENV_PATH), "KITE_ACCESS_TOKEN", access_token)
    print(f"Success! Access token saved to {ENV_PATH}")

    # Sanity check, same as login.py does
    kite.set_access_token(access_token)
    try:
        profile = kite.profile()
        margins = kite.margins()
        print(f"Logged in as: {profile['user_name']} ({profile['user_id']})")
        print(f"Available equity margin: ₹{margins['equity']['available']['live_balance']}")
    except Exception as e:
        print(f"Token saved, but sanity check call failed: {e}")


if __name__ == "__main__":
    main()

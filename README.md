# Kite Trading Bot — Bull Put Credit Spread (Nifty)

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Create your `.env` file:
   ```
   cp .env.example .env
   ```
   Then fill in `KITE_API_KEY` and `KITE_API_SECRET` from developers.kite.trade.

3. Log in (must be done once every trading day — tokens expire daily):
   ```
   python scripts/login.py
   ```
   This opens a login flow, exchanges the request_token for an access_token,
   and saves it into `.env`.

4. Verify the connection:
   ```
   python scripts/test_connection.py
   ```
   This confirms auth works and pulls your margin + a sample of Nifty hourly data.

## Project structure

```
config/         Shared client setup (kite_client.py)
scripts/        Standalone scripts: login, connection test, etc.
strategy/       Strategy logic (entry/exit rules, strike selection) — TBD
logs/           Trade logs, error logs
.env            Your actual credentials (never commit this)
.env.example    Template for .env
```

## Status

- [x] Project skeleton
- [x] Auth flow (daily login script)
- [ ] Entry/exit trigger rules — still being defined
- [ ] Strike selection + expiry logic
- [ ] Order execution (multi-leg spread)
- [ ] Margin/risk checks
- [ ] Logging & alerts
- [ ] Deployment (VPS/cloud, market-hours uptime)

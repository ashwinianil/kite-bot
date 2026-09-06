"""
Black-Scholes options pricing utilities.

Kite Connect gives us live option prices (LTP) but NOT Greeks (delta, etc.)
directly. To pick a strike by delta (as decided for this strategy — ~15-20
delta short strike), we need to:

    1. Back out the implied volatility (IV) from the option's live market
       price (since IV isn't directly observable, only inferable).
    2. Use that IV to compute delta via the Black-Scholes formula.

Works generically for any underlying (Nifty, BankNifty, etc.) — just pass
in spot price, strike, days to expiry, and option price.
"""

import math
from scipy.stats import norm

# Approximate risk-free rate (India ~91-day T-bill yield). Delta is not
# very sensitive to small changes in this, so a reasonable constant is fine
# — adjust here if you want to track the actual current rate.
RISK_FREE_RATE = 0.07


def _d1_d2(spot, strike, time_to_expiry_years, volatility, risk_free_rate):
    d1 = (
        math.log(spot / strike)
        + (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry_years
    ) / (volatility * math.sqrt(time_to_expiry_years))
    d2 = d1 - volatility * math.sqrt(time_to_expiry_years)
    return d1, d2


def black_scholes_price(spot, strike, days_to_expiry, volatility, option_type="put",
                         risk_free_rate=RISK_FREE_RATE):
    """
    Theoretical option price under Black-Scholes.

    option_type: "put" or "call"
    days_to_expiry: calendar days remaining until expiry
    volatility: annualized volatility as a decimal (e.g. 0.15 for 15%)
    """
    if days_to_expiry <= 0 or volatility <= 0:
        raise ValueError("days_to_expiry and volatility must be positive")

    t = days_to_expiry / 365.0
    d1, d2 = _d1_d2(spot, strike, t, volatility, risk_free_rate)

    if option_type == "call":
        price = spot * norm.cdf(d1) - strike * math.exp(-risk_free_rate * t) * norm.cdf(d2)
    elif option_type == "put":
        price = strike * math.exp(-risk_free_rate * t) * norm.cdf(-d2) - spot * norm.cdf(-d1)
    else:
        raise ValueError("option_type must be 'put' or 'call'")

    return price


def delta(spot, strike, days_to_expiry, volatility, option_type="put",
          risk_free_rate=RISK_FREE_RATE):
    """
    Black-Scholes delta. For puts this is negative (standard convention) —
    e.g. a "20-delta put" has delta approximately -0.20. Callers comparing
    against a target like 0.20 should compare against abs(delta(...)).
    """
    if days_to_expiry <= 0 or volatility <= 0:
        raise ValueError("days_to_expiry and volatility must be positive")

    t = days_to_expiry / 365.0
    d1, _ = _d1_d2(spot, strike, t, volatility, risk_free_rate)

    if option_type == "call":
        return norm.cdf(d1)
    elif option_type == "put":
        return norm.cdf(d1) - 1
    else:
        raise ValueError("option_type must be 'put' or 'call'")


def implied_volatility(option_price, spot, strike, days_to_expiry, option_type="put",
                        risk_free_rate=RISK_FREE_RATE, tolerance=1e-5, max_iterations=100):
    """
    Solves for the implied volatility that makes the Black-Scholes price
    match the observed market price, via bisection (robust even though
    slower than Newton-Raphson — fine for our use case, we're not calling
    this in a tight loop).

    Returns None if no solution is found in the search range (can happen
    for prices that are inconsistent with any reasonable IV — e.g. stale
    quotes, or extremely close to expiry with a wide bid-ask).
    """
    if option_price <= 0:
        return None

    low, high = 0.001, 5.0  # 0.1% to 500% annualized vol — generous bounds

    price_at_low = black_scholes_price(spot, strike, days_to_expiry, low, option_type, risk_free_rate)
    price_at_high = black_scholes_price(spot, strike, days_to_expiry, high, option_type, risk_free_rate)

    if not (price_at_low <= option_price <= price_at_high):
        return None  # observed price is outside what any vol in our range could produce

    for _ in range(max_iterations):
        mid = (low + high) / 2
        price_at_mid = black_scholes_price(spot, strike, days_to_expiry, mid, option_type, risk_free_rate)

        if abs(price_at_mid - option_price) < tolerance:
            return mid

        if price_at_mid < option_price:
            low = mid
        else:
            high = mid

    return mid  # best estimate after max_iterations, even if not within tolerance


def delta_from_market_price(option_price, spot, strike, days_to_expiry, option_type="put",
                             risk_free_rate=RISK_FREE_RATE):
    """
    Convenience function combining the two steps: back out IV from the
    observed market price, then compute delta using that IV.

    Returns None if IV couldn't be solved (see implied_volatility()).
    """
    iv = implied_volatility(option_price, spot, strike, days_to_expiry, option_type, risk_free_rate)
    if iv is None:
        return None
    return delta(spot, strike, days_to_expiry, iv, option_type, risk_free_rate)

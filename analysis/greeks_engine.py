import math
import numpy as np
from scipy.stats import norm
import logging

logger = logging.getLogger(__name__)


def black_scholes_greeks(
    S: float,      # Spot price
    K: float,      # Strike price
    T: float,      # Time to expiry in years
    r: float,      # Risk-free rate (0.065 for India)
    sigma: float,  # Implied volatility (decimal)
    option_type: str = "CE",
) -> dict:
    """
    Full Black-Scholes Greeks calculator.
    Returns delta, gamma, theta (per day), vega (per 1% IV move), rho.
    """
    if T <= 0 or sigma <= 0 or S <= 0:
        return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0, "rho": 0, "price": 0}

    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        if option_type == "CE":
            price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
            delta = norm.cdf(d1)
            rho = K * T * math.exp(-r * T) * norm.cdf(d2) / 100
            theta = (
                -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
                - r * K * math.exp(-r * T) * norm.cdf(d2)
            ) / 365
        else:  # PE
            price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            delta = norm.cdf(d1) - 1
            rho = -K * T * math.exp(-r * T) * norm.cdf(-d2) / 100
            theta = (
                -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
                + r * K * math.exp(-r * T) * norm.cdf(-d2)
            ) / 365

        gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
        vega = S * norm.pdf(d1) * math.sqrt(T) / 100  # per 1% change in IV

        return {
            "price": round(price, 2),
            "delta": round(delta, 4),
            "gamma": round(gamma, 6),
            "theta": round(theta, 2),      # daily theta decay in INR
            "vega": round(vega, 2),         # per 1% IV change
            "rho": round(rho, 4),
        }
    except Exception as e:
        logger.error(f"Greeks calculation error: {e}")
        return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0, "rho": 0, "price": 0}


def compute_iv_from_price(
    S: float, K: float, T: float, r: float, market_price: float, option_type: str = "CE"
) -> float:
    """
    Newton-Raphson implied volatility solver.
    Returns IV as decimal (e.g., 0.18 = 18%).
    """
    if market_price <= 0 or T <= 0:
        return 0.0

    sigma = 0.25  # initial guess
    for _ in range(100):
        greeks = black_scholes_greeks(S, K, T, r, sigma, option_type)
        price_diff = greeks["price"] - market_price
        vega = greeks["vega"] * 100  # convert back from per-1%
        if abs(price_diff) < 0.01:
            break
        if vega < 1e-6:
            break
        sigma -= price_diff / vega
        sigma = max(0.001, min(sigma, 5.0))  # clamp

    return round(sigma, 4)


def iv_rank(current_iv: float, iv_history: list) -> float:
    """IV Rank: where is current IV relative to 52-week range (0-100)."""
    if not iv_history or len(iv_history) < 2:
        return 50.0
    iv_min = min(iv_history)
    iv_max = max(iv_history)
    if iv_max == iv_min:
        return 50.0
    return round((current_iv - iv_min) / (iv_max - iv_min) * 100, 1)


def iv_percentile(current_iv: float, iv_history: list) -> float:
    """IV Percentile: % of days in past year where IV was below current IV."""
    if not iv_history:
        return 50.0
    below = sum(1 for iv in iv_history if iv < current_iv)
    return round(below / len(iv_history) * 100, 1)


def interpret_greeks(greeks: dict, option_type: str, days_to_expiry: int) -> str:
    """Plain-English interpretation of Greeks for the report."""
    lines = []
    delta = greeks["delta"]
    theta = greeks["theta"]
    vega = greeks["vega"]

    lines.append(f"Delta {delta:+.3f}: for every ₹1 move in spot, option changes by ₹{abs(delta):.2f}.")

    if theta < -50:
        lines.append(f"Theta {theta:.2f}/day: HIGH time decay — avoid buying with {days_to_expiry}d left.")
    elif theta < -20:
        lines.append(f"Theta {theta:.2f}/day: moderate decay. Buy early in the week if possible.")
    else:
        lines.append(f"Theta {theta:.2f}/day: low decay — relatively safe to hold.")

    if vega > 50:
        lines.append(f"Vega {vega:.2f}: IV-sensitive. A 1% IV drop costs ₹{vega:.0f} per lot.")

    return " | ".join(lines)


def suggest_strategy(
    trend: str,
    iv_rank_val: float,
    days_to_expiry: int,
    pcr: float,
    budget: int,
) -> dict:
    """
    Suggest F&O strategy based on market conditions.
    trend: 'bullish', 'bearish', 'neutral'
    """
    strategy = {}

    if iv_rank_val > 70:
        # High IV — sell premium strategies
        if trend == "neutral":
            strategy = {
                "name": "Iron Condor",
                "rationale": f"IV Rank {iv_rank_val:.0f}% (high). Premium is expensive — collect it via Iron Condor.",
                "legs": "Sell OTM CE + Buy further OTM CE | Sell OTM PE + Buy further OTM PE",
                "ideal_dte": "15-30 days",
            }
        elif trend == "bullish":
            strategy = {
                "name": "Bull Put Spread",
                "rationale": f"Bullish bias + High IV {iv_rank_val:.0f}%. Sell ATM PE, buy OTM PE. Net credit.",
                "legs": "Sell ATM PE + Buy (ATM-100) PE",
                "ideal_dte": "7-15 days",
            }
        else:
            strategy = {
                "name": "Bear Call Spread",
                "rationale": f"Bearish bias + High IV {iv_rank_val:.0f}%. Sell ATM CE, buy OTM CE. Net credit.",
                "legs": "Sell ATM CE + Buy (ATM+100) CE",
                "ideal_dte": "7-15 days",
            }
    elif iv_rank_val < 30:
        # Low IV — buy options, directional
        if trend == "bullish":
            strategy = {
                "name": "Long CE (ATM or slightly OTM)",
                "rationale": f"Bullish + Low IV {iv_rank_val:.0f}%. Cheap to buy options now before IV expansion.",
                "legs": "Buy ATM CE or (ATM+50) CE",
                "ideal_dte": "15-30 days",
            }
        elif trend == "bearish":
            strategy = {
                "name": "Long PE (ATM or slightly OTM)",
                "rationale": f"Bearish + Low IV {iv_rank_val:.0f}%. Buy puts before potential move.",
                "legs": "Buy ATM PE or (ATM-50) PE",
                "ideal_dte": "15-30 days",
            }
        else:
            strategy = {
                "name": "Long Straddle / Strangle",
                "rationale": f"Neutral + Low IV {iv_rank_val:.0f}%. Expect a big move — buy both sides.",
                "legs": "Buy ATM CE + Buy ATM PE",
                "ideal_dte": "10-20 days",
            }
    else:
        # Medium IV
        if trend == "bullish":
            strategy = {
                "name": "Bull Call Spread",
                "rationale": f"Bullish + Medium IV {iv_rank_val:.0f}%. Defined risk, defined reward.",
                "legs": "Buy ATM CE + Sell (ATM+100) CE",
                "ideal_dte": "7-20 days",
            }
        elif trend == "bearish":
            strategy = {
                "name": "Bear Put Spread",
                "rationale": f"Bearish + Medium IV {iv_rank_val:.0f}%. Defined risk.",
                "legs": "Buy ATM PE + Sell (ATM-100) PE",
                "ideal_dte": "7-20 days",
            }
        else:
            strategy = {
                "name": "Short Strangle (if PCR extreme)",
                "rationale": f"Neutral market. PCR {pcr:.2f}. Range-bound — collect premium.",
                "legs": "Sell OTM CE + Sell OTM PE (hedge with spread)",
                "ideal_dte": "5-10 days",
            }

    return strategy

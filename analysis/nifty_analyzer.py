import yfinance as yf
import pandas as pd
import numpy as np
import logging
from datetime import datetime, date
from data.nse_data import (
    get_nifty_option_chain, parse_option_chain,
    get_pcr, get_max_pain, get_support_resistance_from_oi, get_upcoming_expiries,
)
from analysis.greeks_engine import (
    black_scholes_greeks, iv_rank, iv_percentile, suggest_strategy,
)
from config import NIFTY_YF

logger = logging.getLogger(__name__)

RISK_FREE_RATE = 0.065  # RBI repo rate approx


def get_nifty_spot() -> float:
    try:
        df = yf.Ticker(NIFTY_YF).history(period="1d", interval="1m")
        return float(df["Close"].iloc[-1])
    except Exception as e:
        logger.error(f"NIFTY spot error: {e}")
        return 0.0


def get_nifty_technicals() -> dict:
    df = yf.Ticker(NIFTY_YF).history(period="100d", auto_adjust=True)
    if df.empty:
        return {}

    close = df["Close"].squeeze()
    ema20 = close.ewm(span=20).mean()
    ema50 = close.ewm(span=50).mean()
    ema200 = close.ewm(span=200).mean()

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = float((100 - (100 / (1 + gain / loss.replace(0, np.nan)))).iloc[-1])

    # Bollinger Bands
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper_bb = sma20 + 2 * std20
    lower_bb = sma20 - 2 * std20

    spot = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    change_pct = round((spot / prev - 1) * 100, 2)

    # Trend determination
    if spot > float(ema20.iloc[-1]) > float(ema50.iloc[-1]) > float(ema200.iloc[-1]):
        trend = "STRONG BULLISH"
    elif spot > float(ema20.iloc[-1]) > float(ema50.iloc[-1]):
        trend = "BULLISH"
    elif spot < float(ema20.iloc[-1]) < float(ema50.iloc[-1]) < float(ema200.iloc[-1]):
        trend = "STRONG BEARISH"
    elif spot < float(ema20.iloc[-1]) < float(ema50.iloc[-1]):
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    return {
        "spot": round(spot, 2),
        "change_pct": change_pct,
        "trend": trend,
        "rsi": round(rsi, 1),
        "ema20": round(float(ema20.iloc[-1]), 2),
        "ema50": round(float(ema50.iloc[-1]), 2),
        "ema200": round(float(ema200.iloc[-1]), 2),
        "bb_upper": round(float(upper_bb.iloc[-1]), 2),
        "bb_lower": round(float(lower_bb.iloc[-1]), 2),
        "bb_mid": round(float(sma20.iloc[-1]), 2),
    }


def days_to_expiry(expiry_str: str) -> int:
    """Parse expiry like '27-Jun-2024' and return DTE."""
    try:
        expiry = datetime.strptime(expiry_str, "%d-%b-%Y").date()
        return max((expiry - date.today()).days, 0)
    except Exception:
        return 7


def full_nifty_analysis(budget: int) -> dict:
    """
    Master NIFTY F&O analysis combining all data.
    Returns a structured dict for the report.
    """
    technicals = get_nifty_technicals()
    spot = technicals.get("spot", 0)
    trend = technicals.get("trend", "NEUTRAL")

    raw_chain = get_nifty_option_chain()
    chain_df = parse_option_chain(raw_chain)
    expiries = get_upcoming_expiries()

    weekly_expiry = expiries[0] if expiries else "N/A"
    monthly_expiry = expiries[1] if len(expiries) > 1 else expiries[0] if expiries else "N/A"
    dte_weekly = days_to_expiry(weekly_expiry)
    dte_monthly = days_to_expiry(monthly_expiry)

    pcr = get_pcr(chain_df) if not chain_df.empty else 0.0
    max_pain = get_max_pain(chain_df) if not chain_df.empty else spot
    oi_levels = get_support_resistance_from_oi(chain_df, spot) if not chain_df.empty else {}

    # ATM strike (round to nearest 50)
    atm_strike = round(spot / 50) * 50

    # Get IV from ATM options (chain may be empty outside market hours)
    if not chain_df.empty and "strike" in chain_df.columns:
        atm_row = chain_df[chain_df["strike"] == atm_strike]
        atm_ce_iv = float(atm_row["ce_iv"].values[0]) / 100 if not atm_row.empty else 0.15
        atm_pe_iv = float(atm_row["pe_iv"].values[0]) / 100 if not atm_row.empty else 0.15
    else:
        atm_ce_iv = 0.15
        atm_pe_iv = 0.15

    # Historical IV proxy using 30-day realized vol
    nifty_hist = yf.Ticker(NIFTY_YF).history(period="252d", auto_adjust=True)
    if not nifty_hist.empty:
        returns = nifty_hist["Close"].pct_change().dropna()
        rolling_vol = returns.rolling(20).std() * (252 ** 0.5)
        iv_hist_list = rolling_vol.dropna().tolist()
    else:
        iv_hist_list = [0.15] * 100

    ivr = iv_rank(atm_ce_iv, iv_hist_list)
    ivp = iv_percentile(atm_ce_iv, iv_hist_list)

    # Greeks for ATM CE & PE (weekly)
    T_weekly = dte_weekly / 365
    T_monthly = dte_monthly / 365

    weekly_ce_greeks = black_scholes_greeks(spot, atm_strike, T_weekly, RISK_FREE_RATE, atm_ce_iv, "CE")
    weekly_pe_greeks = black_scholes_greeks(spot, atm_strike, T_weekly, RISK_FREE_RATE, atm_pe_iv, "PE")
    monthly_ce_greeks = black_scholes_greeks(spot, atm_strike, T_monthly, RISK_FREE_RATE, atm_ce_iv, "CE")
    monthly_pe_greeks = black_scholes_greeks(spot, atm_strike, T_monthly, RISK_FREE_RATE, atm_pe_iv, "PE")

    # PCR interpretation
    if pcr > 1.3:
        pcr_signal = "OVERSOLD / POTENTIAL REVERSAL UP — put sellers dominating"
    elif pcr < 0.7:
        pcr_signal = "OVERBOUGHT / POTENTIAL REVERSAL DOWN — call sellers dominating"
    elif 0.9 <= pcr <= 1.1:
        pcr_signal = "NEUTRAL — balanced market"
    else:
        pcr_signal = "MILDLY DIRECTIONAL"

    # Suggested strategy
    trend_simple = "bullish" if "BULLISH" in trend else ("bearish" if "BEARISH" in trend else "neutral")
    strategy = suggest_strategy(trend_simple, ivr, dte_weekly, pcr, budget)

    return {
        "spot": spot,
        "trend": trend,
        "technicals": technicals,
        "weekly_expiry": weekly_expiry,
        "monthly_expiry": monthly_expiry,
        "dte_weekly": dte_weekly,
        "dte_monthly": dte_monthly,
        "atm_strike": atm_strike,
        "atm_ce_iv_pct": round(atm_ce_iv * 100, 2),
        "atm_pe_iv_pct": round(atm_pe_iv * 100, 2),
        "iv_rank": ivr,
        "iv_percentile": ivp,
        "pcr": pcr,
        "pcr_signal": pcr_signal,
        "max_pain": max_pain,
        "oi_support": oi_levels.get("support", []),
        "oi_resistance": oi_levels.get("resistance", []),
        "weekly_greeks": {
            "ce": weekly_ce_greeks,
            "pe": weekly_pe_greeks,
        },
        "monthly_greeks": {
            "ce": monthly_ce_greeks,
            "pe": monthly_pe_greeks,
        },
        "suggested_strategy": strategy,
    }

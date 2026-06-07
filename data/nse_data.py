import requests
import pandas as pd
import logging
from nsepython import nse_optionchain_scrapper, nse_eq

logger = logging.getLogger(__name__)

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com",
}


def get_nifty_option_chain() -> dict:
    """Fetch NIFTY 50 option chain from NSE."""
    try:
        data = nse_optionchain_scrapper("NIFTY")
        return data
    except Exception as e:
        logger.error(f"NSE option chain error: {e}")
        return {}


def parse_option_chain(raw_data: dict) -> pd.DataFrame:
    """
    Parse raw NSE option chain JSON into a DataFrame with CE/PE side-by-side.
    Returns columns: strike, ce_oi, ce_chg_oi, ce_ltp, ce_iv, pe_oi, pe_chg_oi, pe_ltp, pe_iv
    """
    if not raw_data or "records" not in raw_data:
        return pd.DataFrame()

    records = raw_data["records"].get("data", [])
    rows = []
    for item in records:
        strike = item.get("strikePrice", 0)
        ce = item.get("CE", {})
        pe = item.get("PE", {})
        rows.append({
            "strike": strike,
            "ce_oi": ce.get("openInterest", 0),
            "ce_chg_oi": ce.get("changeinOpenInterest", 0),
            "ce_ltp": ce.get("lastPrice", 0),
            "ce_iv": ce.get("impliedVolatility", 0),
            "ce_volume": ce.get("totalTradedVolume", 0),
            "pe_oi": pe.get("openInterest", 0),
            "pe_chg_oi": pe.get("changeinOpenInterest", 0),
            "pe_ltp": pe.get("lastPrice", 0),
            "pe_iv": pe.get("impliedVolatility", 0),
            "pe_volume": pe.get("totalTradedVolume", 0),
        })

    df = pd.DataFrame(rows).sort_values("strike").reset_index(drop=True)
    return df


def get_pcr(df: pd.DataFrame) -> float:
    """Put-Call Ratio based on OI."""
    total_pe_oi = df["pe_oi"].sum()
    total_ce_oi = df["ce_oi"].sum()
    return round(total_pe_oi / total_ce_oi, 3) if total_ce_oi > 0 else 0.0


def get_max_pain(df: pd.DataFrame) -> float:
    """
    Max pain = strike price where total option buyer loss is maximum.
    Calculated as strike where sum of (CE OI * max(0, strike - S)) + (PE OI * max(0, S - strike)) is minimized.
    """
    strikes = df["strike"].values
    min_pain = float("inf")
    max_pain_strike = strikes[0]

    for s in strikes:
        ce_loss = sum(df["ce_oi"] * [max(0, s - k) for k in strikes])
        pe_loss = sum(df["pe_oi"] * [max(0, k - s) for k in strikes])
        total = ce_loss + pe_loss
        if total < min_pain:
            min_pain = total
            max_pain_strike = s

    return float(max_pain_strike)


def get_support_resistance_from_oi(df: pd.DataFrame, spot: float, levels: int = 3) -> dict:
    """
    High CE OI = resistance, High PE OI = support.
    Returns top N levels above and below spot.
    """
    above = df[df["strike"] > spot].nlargest(levels, "ce_oi")["strike"].tolist()
    below = df[df["strike"] < spot].nlargest(levels, "pe_oi")["strike"].tolist()
    return {"resistance": sorted(above), "support": sorted(below, reverse=True)}


def get_upcoming_expiries() -> list:
    """Parse expiry dates from NSE option chain."""
    try:
        raw = nse_optionchain_scrapper("NIFTY")
        expiries = raw.get("records", {}).get("expiryDates", [])
        return expiries
    except Exception as e:
        logger.error(f"Expiry fetch error: {e}")
        return []
